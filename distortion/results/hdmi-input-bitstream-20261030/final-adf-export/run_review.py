"""Export and inspect the exact bit-export ADF; never access hardware."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
SOURCE = ROOT / "build/hdmi-uart-diagnostic/input-bit-1030-a"
sys.path.insert(0, str(ROOT / "tools"))
import prepare_hdmi_input_bitstream as bit
import audit_checked_io_netlist as native


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, value):
    with (WORK / name).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def require(value, message):
    if not value:
        raise ValueError(message)


def parse(raw):
    require(raw.count("module hdmi_uart_input_diag") == 1, "unexpected top")
    return native.parse(raw.replace("module hdmi_uart_input_diag", "module board1080_top", 1), native.LIBRARY)


def sites(raw):
    result = {}
    pattern = r"\b(V_\w+)\s*/\*\s*([^*]+?)\s*\*/\s*(?:#\((.*?)\)\s*)?(\\[^\s]+)\s*\("
    for match in re.finditer(pattern, raw, re.S):
        name = native.canonical(match[4])
        require(name not in result, "duplicate placement")
        result[name] = match[2].strip()
    return result


def attrs(raw):
    result = {}
    for match in re.finditer(r"\(\*\s*(.*?)\s*\*\)\s*(input|output|inout)\s+(\w+)\s*;", raw, re.S):
        properties = dict(re.findall(r'(PAP_\w+)="([^"]*)"', match[1]))
        if "PAP_IO_LOC" in properties:
            require(match[3] not in result, "duplicate port attributes")
            result[match[3]] = dict(Direction=match[2], Attributes=properties)
    return result


def main():
    require(set(p.name for p in WORK.iterdir()) == {"run_review.py"}, "fresh work required")
    plan = json.loads((SOURCE / "bitstream-plan.json").read_text(encoding="utf-8"))
    bit.verify_inputs(ROOT, SOURCE, plan)
    package, entries = bit.evidence_entries(ROOT)
    adf = SOURCE / "audited-final.adf"
    bound = {str(p):sha(p) for p in [adf, SOURCE / "bitstream-plan.json", Path(__file__), Path(bit.__file__), Path(native.__file__)]}
    require(sha(adf) == bit.ADF_SHA256, "source ADF differs")
    prefix = (SOURCE / "export.tcl").read_text(encoding="utf-8").split("report_timing -force_to_run", 1)[0]
    for name in re.findall(r"^add_design \{([^{}]+)\}$", prefix, re.M):
        path = Path(name)
        require(path.is_relative_to(SOURCE / "sources"), "unbound source path")
        dest = WORK / path.relative_to(SOURCE)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
        bound[str(path)] = sha(path)
    shutil.copyfile(adf, WORK / "input.adf")
    shutil.copyfile(SOURCE / "context.fdc", WORK / "context.fdc")
    bound[str(SOURCE / "context.fdc")] = sha(SOURCE / "context.fdc")
    files = {"baseline-sim.v":"functional-export/generate_netlist/hdmi_uart_input_diag_sim.v.gz",
             "baseline-connectivity.json":"functional-export/connectivity-review.json",
             "baseline-pins.prt":"native-build/place_route/hdmi_uart_input_diag_prr_route_optimize.prt"}
    for local, frozen in files.items():
        (WORK / local).write_bytes(bit.evidence_bytes(package, entries, frozen))
    prefix = prefix.replace(SOURCE.as_posix(), WORK.as_posix())
    tcl = prefix + "report_timing -force_to_run -input_db_file " + bit.literal(WORK / "input.adf") + " -delay_type min_max -max_path 5 -report_exception TRUE\n"
    tcl += "if {[info script] ne {}} {\n    gen_netlist -force_to_run -input_db_file " + bit.literal(WORK / "input.adf") + " -func_sim_only\n    puts {HDMI_EXACT_FINAL_NETLIST_COMPLETE}\n    flush stdout\n}\n"
    (WORK / "export.tcl").write_text(tcl, encoding="utf-8", newline="\n")
    prepared = {str(p):sha(p) for p in WORK.rglob("*") if p.is_file()}
    command = [plan["Command"][0], "-file", str(WORK / "export.tcl"), "-work_dir", str(WORK), "-project_name", bit.TARGET]
    save("export-plan.json", dict(Schema="hdmi-exact-final-netlist-plan-v1", SourceADF=str(adf), SourceADFSHA256=bit.ADF_SHA256,
         InputSHA256=bound, PreparedInputSHA256=prepared, Command=command, ExpectedActualStages=["Report Timing", "Generate Netlist"],
         HardwareAccessed=False, BitstreamRequested=False, ConstraintsApplied=False, ADFSaved=False))
    started, begin = datetime.now(timezone.utc).isoformat(), time.monotonic()
    with (WORK / "native-stdout.log").open("xb") as out, (WORK / "native-stderr.log").open("xb") as err:
        process = subprocess.Popen(command, cwd=WORK, stdout=out, stderr=err)
        try:
            code = process.wait(timeout=180)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise
    output = (WORK / "native-stdout.log").read_text(encoding="utf-8", errors="replace")
    stages = re.findall(r'^Process "([^"]+)" started\.', output, re.M)
    drift = [name for name,digest in (bound | prepared).items() if sha(name) != digest]
    execution = dict(Schema="hdmi-exact-final-netlist-execution-v1", StartedUTC=started, EndedUTC=datetime.now(timezone.utc).isoformat(),
        ReturnCode=code, OwnedPID=process.pid, ElapsedSeconds=round(time.monotonic()-begin,3), ActualExecutedStages=stages, InputDrift=drift,
        OriginalADFUnchanged=sha(adf)==bit.ADF_SHA256, CopiedADFUnchanged=sha(WORK / "input.adf")==bit.ADF_SHA256,
        HardwareAccessed=False, BitstreamRequested=False)
    execution["ExportExecutionAccepted"] = code == 0 and stages == ["Report Timing", "Generate Netlist"] and not drift and not re.search(r"(?m)^(?:E:|F:|ERROR:|FATAL:)", output) and not (WORK / "native-stderr.log").stat().st_size and "HDMI_EXACT_FINAL_NETLIST_COMPLETE" in output
    execution["OutputSHA256"] = {p.relative_to(WORK).as_posix():sha(p) for p in WORK.rglob("*") if p.is_file()}
    save("execution.json", execution)
    require(execution["ExportExecutionAccepted"], "native export failed")
    netlist = WORK / "generate_netlist/hdmi_uart_input_diag_sim.v"
    raw, old = netlist.read_text(encoding="utf-8"), (WORK / "baseline-sim.v").read_text(encoding="utf-8")
    cells, ports, drivers, libraries = parse(raw)
    old_cells, old_ports, old_drivers, old_libraries = parse(old)
    placement, old_placement = sites(raw), sites(old)
    attributes, old_attributes = attrs(raw), attrs(old)
    require(cells == old_cells and ports == old_ports and drivers == old_drivers, "functional graph changed")
    require(placement == old_placement, "primitive placement changed")
    require(attributes == old_attributes, "scalar IO attributes changed")
    pin_by_site, expected, directions = {}, {}, {}
    for line in (WORK / "baseline-pins.prt").read_text(encoding="utf-8").splitlines():
        fields = line.split("|")
        if len(fields) >= 7:
            require(fields[1] not in pin_by_site, "duplicate package site")
            pin_by_site[fields[1]] = fields[0]
            if fields[4]:
                require(fields[6] == "YES", "inactive port")
                expected[fields[4]], directions[fields[4]] = fields[0], fields[5]
    require(expected == plan["SourcePins"] and len(expected) == 46, "pin closure differs")
    evidence, actual, actual_dirs = [], {}, {}
    for name, wanted in expected.items():
        if name in attributes:
            pin, direction = attributes[name]["Attributes"]["PAP_IO_LOC"], attributes[name]["Direction"]
            source = dict(Kind="native_scalar_port_attributes", **attributes[name])
        else:
            matches = [(key,cell) for key,cell in cells.items() if cell["Type"] == "V_OBUFT" and native.scalar(cell["Ports"]["O"]) == name]
            require(len(matches) == 1, "unique output primitive required: " + name)
            key, cell = matches[0]
            require(key in placement and placement[key] in pin_by_site, "output site missing")
            pin, direction = pin_by_site[placement[key]], "output"
            source = dict(Kind="native_output_primitive_site_to_package_pin", Instance=key, Site=placement[key], Parameters=cell["Parameters"])
        require(pin == wanted and direction == directions[name], "port mapping differs: " + name)
        actual[name], actual_dirs[name] = pin, direction
        evidence.append(dict(Port=name, Pin=pin, Direction=direction, Evidence=source))
    require(len(set(actual.values())) == 46, "duplicate package pin")
    prior = json.loads((WORK / "baseline-connectivity.json").read_text(encoding="utf-8"))
    for name,register in prior["registers"].items():
        key = register["native_instance"]
        require(cells[key]["Type"] == register["primitive"] and cells[key]["Ports"] == register["ports"] and cells[key]["Parameters"] == register["parameters"], "synchronizer changed: " + name)
        require(placement[key] == register["location"]["site"], "synchronizer moved")
    links = []
    for link in prior["stage_links"]:
        akey, bkey = prior["registers"][link["first"]]["native_instance"], prior["registers"][link["second"]]["native_instance"]
        a, b = cells[akey], cells[bkey]
        q, d = native.scalar(a["Ports"]["Q"]), native.scalar(b["Ports"]["D"])
        criteria = dict(DirectQToD=q == d, SoleDriver=drivers[d] == [(akey,"Q")],
            SameClock=native.scalar(a["Ports"]["CK"]) == native.scalar(b["Ports"]["CK"]),
            FirstEnabled=native.constant(native.scalar(a["Ports"]["CE"])) == 1,
            SecondEnabled=native.constant(native.scalar(b["Ports"]["CE"])) == 1, SameSite=placement[akey] == placement[bkey])
        require(all(criteria.values()), "stage connection changed")
        links.append(dict(First=link["first"], Second=link["second"], Criteria=criteria))
    require(len(prior["registers"]) == 161 and len(links) == 81, "sync inventory differs")
    bit.verify_inputs(ROOT, SOURCE, plan)
    require(sha(adf) == bit.ADF_SHA256 and sha(WORK / "input.adf") == bit.ADF_SHA256, "ADF changed")
    result = dict(Schema="hdmi-exact-final-netlist-review-v1", CreatedUTC=datetime.now(timezone.utc).isoformat(), AuditPassed=True,
        SourceADFSHA256=bit.ADF_SHA256, NativeNetlistSHA256=sha(netlist), BaselineNetlistSHA256=sha(WORK / "baseline-sim.v"),
        EntireParsedFunctionalGraphUnchanged=True, EntirePrimitivePlacementUnchanged=True, ScalarIOAttributesUnchanged=True,
        ParsedCellCount=len(cells), ActualPinCount=46, All46PinsAndDirectionsMatch=True, Pins=actual, Directions=actual_dirs, PinEvidence=evidence,
        VerifiedSynchronizerFFCount=161, VerifiedStageLinkCount=81, SameSiteStageLinkCount=81, StageLinks=links,
        EvidenceSHA256={str(p):sha(p) for p in [WORK / "execution.json",WORK / "export-plan.json",netlist,WORK / "baseline-pins.prt",WORK / "baseline-connectivity.json",WORK / "input.adf"]},
        PrimitiveLibrarySHA256=libraries, HardwareAccessed=False, HardwareReleaseAllowed=False, PhysicalCDCSignoff=False,
        Limits="Exact ADF functional connectivity, placement and IO mapping only. Output primitive sites map via the unchanged device/package pin report. No external AC, MTBF, board power or real input/pixel acceptance.")
    save("review.json", result)
    print(json.dumps({key:result[key] for key in ["AuditPassed","SourceADFSHA256","NativeNetlistSHA256","ParsedCellCount","ActualPinCount","VerifiedSynchronizerFFCount","VerifiedStageLinkCount"]}))


if __name__ == "__main__":
    main()
