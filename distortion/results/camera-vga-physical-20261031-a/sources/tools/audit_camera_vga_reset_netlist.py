"""Inspect the current camera candidate's actual exported DDR reset graph.

The graph-walk method derives from the processed-output checker, while every
proposed source/endpoint comes from this candidate's freshly reconstructed STA
inventory. No historical target counts or endpoint list is accepted. Original
netlist bytes and every primitive/connection remain unchanged; only the top
module declaration token is adapted in memory for the shared V_* parser.
"""
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import hashlib
import json
import re

import audit_ddr_entry_reset_netlist as syntax
import prepare_camera_vga_reset_scope as reference

require, sha = reference.require, reference.sha


def audit_text(text, queries):
    require(len(re.findall(r"(?m)^module\s+camera_vga_output_top\b", text)) == 1,
            "one camera_vga_output_top declaration required")
    normalized = re.sub(r"(?m)^module\s+camera_vga_output_top\b", "module board1080_top", text, count=1)
    clean, cells = syntax.parse(normalized)
    refs = defaultdict(list)
    for cell in cells:
        for pin, value in cell.ports.items():
            for net in set(syntax.TOKEN.findall(value)):
                refs[net].append((cell, pin))
    def one(values, label):
        require(len(values) == 1, label + " must match once")
        return values[0]
    def driver(net, primitive, pin):
        return one([c for c, p in refs[net] if c.primitive == primitive and p == pin and c.ports[p] == net],
                   primitive + "." + pin + " driver for " + net)
    def record(c):
        return {"Name": c.name, "Primitive": c.primitive, "Parameters": c.parameters,
                "Ports": c.ports, "Line": clean.count("\n", 0, c.offset) + 1}
    chain = [c for c in cells if c.name.startswith(syntax.SYNC)]
    require(len(chain) == 2 and all(c.primitive == "V_FFASYN" for c in chain), "two asynchronous FF stages required")
    first = one([c for c in chain if c.ports.get("D") == syntax.LOCK], "LOCK first stage")
    second = one([c for c in chain if c.ports.get("Q") == syntax.OUTPUT], "second stage output")
    require(first is not second and first.ports["Q"] == second.ports["D"], "direct two-stage cascade required")
    for c in chain:
        require(set(c.ports) == {"Q", "CE", "CK", "D", "SR"} and c.ports["CE"] == "1'b1", "unexpected stage controls")
        require(c.parameters == {"GRS_EN": '"TRUE"', "SET_RESET": '"RESET"', "LRS_EN": '"TRUE"', "INIT": "1'b0"},
                "stage must be an initialized asynchronous-clear FF")
    require(first.ports["CK"] == second.ports["CK"] and first.ports["SR"] == second.ports["SR"],
            "stages must share clock and clear")
    middle = first.ports["Q"]
    require({(c.name, p) for c, p in refs[middle]} == {(first.name, "Q"), (second.name, "D")},
            "first-stage functional fanout must only be second stage")
    leaf = driver(first.ports["CK"], "V_BUF", "Z")
    require(leaf.ports == {"Z": first.ports["CK"], "I": syntax.RST_CLOCK}, "wrong entry clock buffer")
    mux = driver(syntax.RST_CLOCK, "V_USCM", "CLKOUT")
    require(mux.parameters.get("USCM_MODE") == '"BUF_A"', "rst clock is muxed")
    pll = driver(syntax.LOCK, "V_GPLL", "LOCK")
    require(mux.ports.get("CLK0") == pll.ports.get("CLKOUT0"), "entry clock and LOCK use different PLLs")
    require({(c.name, p) for c, p in refs[syntax.LOCK]} == {(pll.name, "LOCK"), (first.name, "D")},
            "LOCK has feedback or extra fanout")
    clear_records, clear_nets, clear_buffers = [], set(), []
    for clear in sorted({first.ports["SR"], pll.ports["RST"]}):
        lut = driver(clear, "V_LUT6CARRY", "Z")
        require(lut.parameters.get("I5_TO_LUT") == '"TRUE"' and
                re.fullmatch(r"64'h[0-9a-fA-F]{16}", lut.parameters.get("INIT", "")), "unsupported clear LUT")
        inputs = [lut.ports.get("I" + str(i)) for i in range(6)]
        require({v for v in inputs if v not in ("1'b0", "1'b1")} == {"nt_reset_n", "power_ready"},
                "clear LUT has unexpected dependency or LOCK feedback")
        init, truth = int(lut.parameters["INIT"][4:], 16), []
        for reset in (0, 1):
            for ready in (0, 1):
                values = {"nt_reset_n": reset, "power_ready": ready, "1'b0": 0, "1'b1": 1}
                address = sum(values[v] << i for i, v in enumerate(inputs))
                actual = (init >> address) & 1
                require(actual == int(not (reset and ready)), "clear LUT truth table is not ~(reset_n & power_ready)")
                truth.append({"ResetN": reset, "PowerReady": ready, "Clear": actual})
        pending, tree = [(clear, lut)], []
        while pending:
            net, parent = pending.pop()
            require(net not in clear_nets, "clear tree is cyclic or has merged roots")
            clear_nets.add(net)
            for c, pin in refs[net]:
                require(c.ports[pin] == net, "clear has an indirect expression/alias")
                if c is parent and pin == "Z":
                    continue
                valid = ((c.primitive in ("V_FFASYN", "V_FFSYN") and pin == "SR") or
                         (c is pll and pin == "RST") or
                         (c.primitive == "V_LUT6CARRY" and pin in {"I0", "I1", "I2", "I3", "I4", "I5"}))
                if c.primitive == "V_BUF" and pin == "I":
                    require(not c.parameters and set(c.ports) == {"I", "Z"} and syntax.TOKEN.fullmatch(c.ports["Z"]),
                            "clear buffer is not an identity buffer")
                    pending.append((c.ports["Z"], c)); clear_buffers.append(c); valid = True
                require(valid, "clear has an unexpected driver or consumer")
                tree.append({"Name": c.name, "Primitive": c.primitive, "Pin": pin, "Net": net})
        clear_records.append({"RootNet": clear, "LUT": record(lut), "TruthTable": truth, "Loads": tree})
    reset_buffer = driver("nt_reset_n", "V_BUF", "Z")
    ibuf = driver(reset_buffer.ports.get("I"), "V_IBUF", "O")
    require(ibuf.ports.get("I") == "reset_n", "raw reset is not the board reset port")
    power = driver("power_ready", "V_FFASYN", "Q")
    output_loads = [(c, p) for c, p in refs[syntax.OUTPUT] if (c.name, p) != (second.name, "Q")]
    require(output_loads and all(c.primitive == "V_INV" and p == "I" and c.name.startswith(
            (syntax.PREFIX + "ddrphy_reset_ctrl/", syntax.PREFIX + "u_ddrphy_gpll_phase/")) for c, p in output_loads),
            "synchronized output has unexpected fanout")
    critical = {middle, syntax.OUTPUT, syntax.LOCK, first.ports["CK"], syntax.RST_CLOCK,
                mux.ports["CLK0"], "nt_reset_n", "power_ready", reset_buffer.ports["I"], *clear_nets}
    counts = Counter(t for t in syntax.TOKEN.findall(clean) if t in critical)
    for net in critical:
        require(counts[net] == 1 + len(refs[net]), "unparsed alias/reference to " + net)
    groups = []
    for q in queries:
        if q["EntryRDC"]:
            continue
        targets, target_nets = [], set()
        for target in q["Targets"]:
            parent, pin = target.rsplit("/", 1)
            kind, exported = {"ISR_IOLHR": ("V_ISERDES_E2", "RST"), "OSR_IOLHR": ("V_OSERDES_E2", "RST"),
                              "TSR": ("V_OSERDES_E2", "RST"), "RST_TRAINING_N": ("V_DDC_E2", "RST_TRAINING_N"),
                              "RST": ("V_CLKPD" if "cpd_inst" in parent else "V_DDC_E2", "RST")}[pin]
            cell = one([c for c in cells if c.name.startswith(parent + "/") and c.primitive == kind],
                       "actual direct reset target " + target)
            net = cell.ports.get(exported, "")
            require(syntax.TOKEN.fullmatch(net), "reset target is not a direct scalar net")
            target_nets.add(net)
            targets.append({"NativeTarget": target, "FunctionalCell": cell.name,
                            "Primitive": cell.primitive, "Pin": exported, "Net": net})
        require(len(target_nets) == 1, "native group targets do not share one actual reset net")
        net = target_nets.pop()
        source = driver(net, "V_FFASYN", "Q")
        require(source.name.startswith(q["Source"].rsplit("/", 1)[0] + "/"), "native source does not match functional FF")
        clock = driver(source.ports["CK"], "V_BUF", "Z")
        expected_clock = "core_clk" if "training_ctrl/" in q["Source"] else syntax.RST_CLOCK
        require(clock.ports == {"Z": source.ports["CK"], "I": expected_clock}, "reset source clock differs")
        require(sum(token == net for token in syntax.TOKEN.findall(clean)) == 1 + len(refs[net]),
                "unparsed alias/reference to internal reset " + net)
        groups.append({"NativeSource": q["Source"], "FunctionalSource": record(source),
                       "ClockBuffer": record(clock), "TargetCount": len(targets), "Targets": targets})
    expected_internal = [q for q in queries if not q['EntryRDC']]
    require(len(groups) == len(expected_internal) and
            sum(g['TargetCount'] for g in groups) == sum(len(q['Targets']) for q in expected_internal),
            'functional groups differ from current report-derived scope')
    entry_groups = [q for q in queries if q['EntryRDC']]
    require(len(entry_groups) == 1 and len(entry_groups[0]['Targets']) == 1,
            'one report-derived entry pair required')
    entry_query = entry_groups[0]
    require(power.name.startswith(entry_query['Source'].rsplit('/', 1)[0] + '/') and
            first.name.startswith(entry_query['Targets'][0].rsplit('/', 1)[0] + '/'),
            'actual entry source or first stage differs from report')
    return {"Status": "pass", "ParsedPrimitiveCellCount": len(cells), "Stages": [record(first), record(second)],
            "FirstStageFunctionalFanout": 1, "ClockBuffer": record(leaf), "ClockMux": record(mux),
            "StartupPLL": record(pll), "RawClearFunction": "~(reset_n & power_ready)",
            "DistinctEquivalentClearRootCount": len(clear_records), "ClearRoots": clear_records,
            "ClearBufferCount": len(clear_buffers), "PowerReadyFF": record(power),
            "OutputLoadCount": len(output_loads), "OutputLoads": [record(c) for c, p in output_loads],
            "CriticalNetReferenceCounts": dict(counts), "InternalDriverGroups": groups,
            "InternalFunctionalTargetsVerified": sum(g["TargetCount"] for g in groups), "AnalogMTBFProven": False,
            "OtherGlobalResetConsumersOnlyInventoried": True, "TimingExceptionApplied": False,
            "HeaderOnlyAdapter": "camera_vga_output_top to board1080_top for reused strict V_* parser"}

