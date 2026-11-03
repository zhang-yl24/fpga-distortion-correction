"""Audit the DDR entry synchronizer in a public PDS functional simulation export.

This deliberately accepts the observed flat, named-port V_* export format only.
It never reads encrypted vendor sources, runs EDA, writes constraints, or claims
that a functional connectivity audit proves analog metastability MTBF.
"""
from pathlib import Path
import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import re


PREFIX = "u_ddr3_test_h/u_ddrphy_top/"
SYNC = PREFIX + "u_ddrphy_rst_seq_rstn_sync/"
LOCK = "\\" + PREFIX + "rst_gpll_lock"
OUTPUT = "\\" + PREFIX + "rst_seq_rstn"
RST_CLOCK = "\\" + PREFIX + "rst_clk"
TOKEN = re.compile(r"\\[^\s]+|[A-Za-z_$][\w$]*")
CELL = re.compile(
    r"^[ \t]*(?P<primitive>V_\w+)\s*"
    r"(?:#\s*\((?P<parameters>.*?)\)\s*)?"
    r"(?P<name>\\\S+|[A-Za-z_$][\w$]*)\s*\((?P<ports>.*?)\)\s*;",
    re.MULTILINE | re.DOTALL,
)
BINDING = re.compile(r"\.(\w+)\s*\(([^()]*)\)\s*(?:,|$)")


@dataclass
class Cell:
    name: str
    primitive: str
    parameters: dict
    ports: dict
    offset: int


def require(condition, message):
    if not condition:
        raise ValueError(message)


def bindings(body):
    result, end = {}, 0
    for match in BINDING.finditer(body or ""):
        require(not body[end:match.start()].strip(), "unsupported named binding syntax")
        name, value = match.groups()
        require(name not in result, "duplicate named binding: " + name)
        result[name] = value.strip()
        end = match.end()
    require(not (body or "")[end:].strip(), "unparsed named binding syntax")
    return result


def parse(text):
    # This is an audit of the specific PDS export dialect, not a Verilog compiler.
    clean = re.sub(r"/\*.*?\*/|//[^\n]*|\(\*.*?\*\)",
                   lambda m: "\n" * m.group().count("\n"), text, flags=re.DOTALL)
    require(len(re.findall(r"(?m)^module\s+board1080_top\b", clean)) == 1,
            "one board1080_top module is required")
    require(len(re.findall(r"(?m)^endmodule\b", clean)) == 1,
            "hierarchical or ambiguous simulation exports are unsupported")
    cells = []
    for match in CELL.finditer(clean):
        cells.append(Cell(match["name"].lstrip("\\"), match["primitive"],
                          bindings(match["parameters"]), bindings(match["ports"]),
                          match.start()))
    require(len(cells) == len(re.findall(r"(?m)^[ \t]*V_\w+\b", clean)),
            "not every V_* cell was parsed")
    require(len({cell.name for cell in cells}) == len(cells), "duplicate cell names")
    return clean, cells


def audit_text(text):
    clean, cells = parse(text)

    def one(values, description):
        require(len(values) == 1, description + " must match exactly once")
        return values[0]

    def driving(net, primitive, pin):
        return one([c for c in cells if c.primitive == primitive and c.ports.get(pin) == net],
                   primitive + "." + pin + " driver of " + net)

    def connections(net):
        return [(c, port) for c in cells for port, value in c.ports.items()
                if net in TOKEN.findall(value)]

    def record(cell):
        return {"Name": cell.name, "Primitive": cell.primitive,
                "Line": clean.count("\n", 0, cell.offset) + 1,
                "Parameters": cell.parameters, "Ports": cell.ports}

    chain = [c for c in cells if c.name.startswith(SYNC)]
    require(len(chain) == 2 and all(c.primitive == "V_FFASYN" for c in chain),
            "entry synchronizer must contain exactly two V_FFASYN cells")
    first = one([c for c in chain if c.ports.get("D") == LOCK], "LOCK first stage")
    second = one([c for c in chain if c.ports.get("Q") == OUTPUT], "output second stage")
    require(first is not second, "first and second stage must be distinct")
    require(first.ports.keys() == second.ports.keys() == {"Q", "CE", "CK", "D", "SR"},
            "unexpected synchronizer ports")
    for cell in chain:
        require(cell.parameters == {"GRS_EN": '"TRUE"', "SET_RESET": '"RESET"',
                                    "LRS_EN": '"TRUE"', "INIT": "1'b0"},
                "unexpected asynchronous clear or initialization parameters")
        require(cell.ports["CE"] == "1'b1", "synchronizer CE must be constant one")
    middle = first.ports["Q"]
    require(second.ports["D"] == middle, "stages are not directly cascaded")
    require(first.ports["CK"] == second.ports["CK"], "stages use different clocks")
    require(first.ports["SR"] == second.ports["SR"], "stages use different clears")
    middle_connections = connections(middle)
    require({(c.name, p) for c, p in middle_connections} == {(first.name, "Q"), (second.name, "D")},
            "first-stage output has extra drivers or functional fanout")

    clock_buffer = driving(first.ports["CK"], "V_BUF", "Z")
    require(clock_buffer.ports == {"Z": first.ports["CK"], "I": RST_CLOCK},
            "synchronizer clock is not a direct rst_clk buffer")
    clock_mux = driving(RST_CLOCK, "V_USCM", "CLKOUT")
    require(clock_mux.parameters.get("USCM_MODE") == '"BUF_A"', "rst_clk uses a clock mux")
    pll = driving(LOCK, "V_GPLL", "LOCK")
    require({(c.name, p) for c, p in connections(LOCK)} == {(pll.name, "LOCK"), (first.name, "D")},
            "startup LOCK has an unexpected driver or fanout")
    require(clock_mux.ports.get("CLK0") == pll.ports.get("CLKOUT0"),
            "rst_clk and LOCK do not come from the same startup PLL")
    clear = first.ports["SR"]
    require(pll.ports.get("RST") == clear, "startup PLL reset does not use the same raw clear")
    reset_lut = driving(clear, "V_LUT6CARRY", "Z")
    # PDS control-chain exports can distribute this same clear through V_BUF
    # cells. Walk the entire tree, accepting only identity buffers and SR leaves;
    # an arbitrary buffer input alone is not evidence of a safe reset fanout.
    clear_nets, clear_buffers = {clear}, []
    pending = [(clear, reset_lut)]
    while pending:
        net, driver = pending.pop()
        consumers = 0
        for cell, pin in connections(net):
            require(cell.ports[pin] == net, "raw clear has a non-direct connection")
            if cell is driver and pin == "Z":
                continue
            if ((cell.primitive == "V_FFASYN" and pin == "SR") or
                    (net == clear and cell is pll and pin == "RST")):
                consumers += 1
                continue
            require(cell.primitive == "V_BUF" and pin == "I",
                    "raw clear has an unexpected driver or use")
            require(not cell.parameters and cell.ports.keys() == {"I", "Z"},
                    "raw clear buffer has unexpected parameters or ports")
            output = cell.ports["Z"]
            require(TOKEN.fullmatch(output) and output not in clear_nets,
                    "raw clear buffer output is invalid, reused or cyclic")
            clear_nets.add(output)
            clear_buffers.append(cell)
            pending.append((output, cell))
            consumers += 1
        require(consumers, "raw clear buffer has no reset loads")
    require(reset_lut.parameters.get("I5_TO_LUT") == '"TRUE"', "unsupported reset LUT mode")
    require(re.fullmatch(r"64'h[0-9A-Fa-f]{16}", reset_lut.parameters.get("INIT", "")),
            "unsupported reset LUT truth table")
    init = int(reset_lut.parameters["INIT"].split("h")[1], 16)
    reset_ports = [reset_lut.ports.get("I" + str(i)) for i in range(6)]
    variables = {value for value in reset_ports if value not in ("1'b0", "1'b1")}
    require(variables == {"nt_reset_n", "power_ready"}, "raw clear has unexpected dependencies")
    for reset_n in (0, 1):
        for ready in (0, 1):
            values = {"nt_reset_n": reset_n, "power_ready": ready, "1'b0": 0, "1'b1": 1}
            address = sum(values[value] << i for i, value in enumerate(reset_ports))
            require(((init >> address) & 1) == (not (reset_n and ready)),
                    "raw clear is not ~(reset_n & power_ready)")
    reset_buffer = driving("nt_reset_n", "V_BUF", "Z")
    reset_ibuf = driving(reset_buffer.ports.get("I"), "V_IBUF", "O")
    require(reset_ibuf.ports.get("I") == "reset_n", "raw reset does not trace to reset_n port")
    power_ff = driving("power_ready", "V_FFASYN", "Q")

    output_connections = connections(OUTPUT)
    loads = [(c, p) for c, p in output_connections if (c.name, p) != (second.name, "Q")]
    require(loads and all(c.primitive == "V_INV" and p == "I" and
                         c.name.startswith((PREFIX + "ddrphy_reset_ctrl/",
                                            PREFIX + "u_ddrphy_gpll_phase/")) for c, p in loads),
            "synchronized reset has an unexpected driver or load")
    critical = {middle, OUTPUT, clear, LOCK, first.ports["CK"], RST_CLOCK,
                clock_mux.ports["CLK0"], "nt_reset_n", "power_ready", reset_buffer.ports["I"]}
    critical.update(clear_nets)
    counts = Counter(t for t in TOKEN.findall(clean) if t in critical)
    # One wire declaration plus all named-port occurrences; aliases are rejected.
    for net in critical:
        require(counts[net] == 1 + len(connections(net)), "unparsed references to " + net)
    result = {"Status": "pass", "Scope": "DDR entry functional connectivity only",
            "Stages": [record(first), record(second)], "FirstStageFunctionalFanout": 1,
            "ClockBuffer": record(clock_buffer), "ClockMux": record(clock_mux),
            "StartupPLL": record(pll), "RawClearLUT": record(reset_lut),
            "RawClearFunction": "~(reset_n & power_ready)", "PowerReadyFF": record(power_ff),
            "CriticalNetReferenceCounts": dict(sorted(counts.items())),
            "ParsedPrimitiveCellCount": len(cells),
            "OutputLoads": [{"Name": c.name, "Primitive": c.primitive, "Pin": p} for c, p in loads],
            "OutputLoadCount": len(loads), "HardwareValidated": False,
            "AnalogMTBFProven": False, "TimingExceptionApplied": False}
    if clear_buffers:
        # Keep unbuffered historical reports byte-for-byte equivalent.
        result["RawClearBuffers"] = [record(cell) for cell in clear_buffers]
        result["RawClearBufferCount"] = len(clear_buffers)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("netlist", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    data = args.netlist.read_bytes()
    result = audit_text(data.decode("utf-8"))
    result["Input"] = {"Path": str(args.netlist.resolve()), "Bytes": len(data),
                       "SHA256": hashlib.sha256(data).hexdigest()}
    result["AuditToolSHA256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
