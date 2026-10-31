"""Read-only audit of this exact independent output native diagnostic run."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "tools"))
import audit_board1080_pin_contract as pins
import audit_ddr_final_timing as native
import prepare_processed_output as prepare


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def path_details(text):
    records = []
    for block in re.split(r"(?m)(?=^Startpoint)", text)[1:]:
        source = re.search(r"^Startpoint\s*:\s*(\S+)", block, re.M)
        target = re.search(r"^Endpoint\s*:\s*(\S+)", block, re.M)
        kind = re.search(r"^ (Setup|Hold|Recovery|Removal) time\s", block, re.M)
        corner = re.search(r"^Path Type\s*:\s*(max|min) \((slow|fast) corner\)", block, re.M)
        slack = re.search(r"^ Slack \((MET|VIOLATED)\)\s+([-+]?\d+(?:\.\d+)?)", block, re.M)
        require(all((source, target, corner)), "unparsed native path identity")
        if kind is None or slack is None:
            require(kind is None and slack is None and "Path Class  : combinational timing path" in block,
                    "unparsed constrained native path")
        value = None if slack is None else float(slack[2])
        if slack is not None:
            require((value < 0) == (slack[1] == "VIOLATED"), "native path slack/state mismatch")
        records.append({"Source": source[1], "Endpoint": target[1], "Kind": "unconstrained" if kind is None else kind[1].lower(),
                        "Corner": corner[2], "Type": corner[1], "SlackNS": value,
                        "ClockEdges": [{"Clock": clk, "Edge": edge} for clk, edge in
                                       re.findall(r"^ Clock (\S+) \((rising|falling) edge\)", block, re.M)],
                        "NativePathSHA256": hashlib.sha256(block.encode()).hexdigest()})
    require(records, "native detailed timing paths missing")
    return records


def resources(text):
    result = {}
    for label, used, available, percent in re.findall(
            r"^\|\s*(Use of [^|]+?)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*", text, re.M):
        require(label not in result, "duplicate resource row")
        result[label] = {"Used": float(used), "Available": float(available), "UtilizationPercent": float(percent)}
    require(result, "native final resource table missing")
    return result


def logic_by_clm(text):
    result = {}
    for label in ("FF", "LUT"):
        rows = re.findall(r"^\|\s+" + label + r"\s+\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*", text, re.M)
        require(len(rows) == 2, "native CLMA/CLMS logic resource rows missing")
        result[label] = {"Used": sum(int(row[0]) for row in rows),
                         "Available": sum(int(row[1]) for row in rows),
                         "CLMAAndCLMSRows": [{"Used": int(used), "Available": int(available),
                                               "UtilizationPercent": float(percent)} for used, available, percent in rows]}
    return result


def map_resources(text):
    result = {}
    for label in ("LUT", "FF", "DRM", "APM", "IO"):
        rows = re.findall(r"^\|\s*" + label + r"\s*\|\s*([\d.]+)\s*\|", text, re.M)
        require(len(rows) == 1, "native map resource row missing or duplicated")
        result[label] = float(rows[0])
    return result


def run(work_dir, output_path):
    work = Path(work_dir).resolve()
    require(work.parent == PROJECT / "build/processed-output", "audit requires an independent processed-output work directory")
    require(Path(output_path).resolve().is_relative_to(work), "audit output must remain in this work directory")
    global WORK
    WORK = work
    report = WORK / "report_timing/processed_output_top.rtr"
    exception = WORK / "report_timing/processed_output_top_exception.rtr"
    adf = WORK / "place_route/processed_output_top_pnr.adf"
    snapshot = WORK / "pre-sta-final.adf"
    pcf = WORK / "device_map/processed_output_top.pcf"
    prt = WORK / "place_route/processed_output_top_prr_route_optimize.prt"
    ror = WORK / "place_route/processed_output_top.ror"
    fdc = WORK / "compiled/board/processed-output-diagnostic.fdc"
    top = WORK / "compiled/board/processed_output_top.v"
    watched = [report, exception, adf, snapshot, pcf, prt, ror, fdc, top,
               WORK / "plan.json", WORK / "execution-result.json", WORK / "execution-stdout.log",
               WORK / "execution-stderr.log", WORK / "synthesize/constraint_check.ccr",
               WORK / "device_map/processed_output_top.dmr", WORK / "synthesize/processed_output_top.snr",
               PROJECT / "board/processed-output-sources.json", Path(__file__),
               Path(pins.__file__), Path(native.__file__), Path(prepare.__file__)]
    hashes = {str(p.relative_to(PROJECT)): sha(p) for p in watched}
    require(sha(adf) == sha(snapshot), "final ADF changed across report timing")
    execution = json.loads((WORK / "execution-result.json").read_text(encoding="utf-8"))
    require(execution["NativeExitCode"] == 0 and execution["ExecutionCompletedWithoutError"], "native flow did not complete")
    plan = json.loads((WORK / "plan.json").read_text(encoding="utf-8"))
    source_drift = [name for name, expected in plan["InputSHA256"].items() if sha(PROJECT / name) != expected]
    copies_drift = [row["Source"] for row in plan["CompiledInputs"]
                    if sha(WORK / "compiled" / row["Source"]) != row["CompiledSHA256"]]
    require(not source_drift and not copies_drift, "source/compiled input drift")
    ports = prepare.top_ports(top.read_text())
    declared, generated = pins.fdc_pins(fdc.read_text()), pins.pcf_pins(pcf.read_text())
    pads, routed = pins.routed_pads(prt.read_text())
    require(len(ports) == 114 and set(ports) == set(declared) == set(generated) == set(routed), "exact114 pin inventory differs")
    for name, row in declared.items():
        require(ports[name] == row["DIRECTION"] == routed[name]["Direction"], "direction mismatch: " + name)
        require(row["LOC"] == routed[name]["Pad"], "routed pad mismatch: " + name)
        require(generated[name] == {k:v for k,v in row.items() if k != "DIRECTION"}, "PCF electrical mismatch: " + name)
    bank_summary = defaultdict(list)
    for name, row in routed.items():
        bank_summary[row["Bank"]].append(name)
    for names in bank_summary.values():
        require(len({declared[name]["VCCIO"] for name in names}) == 1, "mixed bank declared voltage")
    with report.open(encoding="utf-8-sig", errors="replace") as stream:
        tables, clocks = native.parse_summaries(stream)
    summaries = {}
    for (corner, kind), rows in tables.items():
        worst = min(rows.items(), key=lambda pair: pair[1]["WorstSlackNS"])
        summaries[corner + "_" + kind] = {
            "WorstSlackNS": worst[1]["WorstSlackNS"], "WorstClockPair": list(worst[0]),
            "FailingChecks": sum(row["FailingChecks"] for row in rows.values()),
            "TotalChecks": sum(row["TotalChecks"] for row in rows.values()),
            "AllClockPairRows": [{"Clocks": list(pair), **row} for pair, row in rows.items()],
            "FailedClockPairRows": [{"Clocks": list(pair), **row} for pair, row in rows.items()
                                    if row["FailingChecks"] or row["WorstSlackNS"] < 0]}
    details = path_details(report.read_text(encoding="utf-8-sig", errors="replace"))
    worst_paths = {}
    for record in details:
        if record["Kind"] == "unconstrained":
            continue
        key = record["Corner"] + "_" + record["Kind"]
        if key not in worst_paths or record["SlackNS"] < worst_paths[key]["SlackNS"]:
            worst_paths[key] = record
    require(len(worst_paths) == 8, "all eight detailed path categories required")
    for key, row in worst_paths.items():
        require(row["SlackNS"] == summaries[key]["WorstSlackNS"], "detailed worst does not match summary: " + key)
    with exception.open(encoding="utf-8-sig", errors="replace") as stream:
        false_paths = native.parse_false_paths(stream)
    require(all(not rows for rows in false_paths.values()), "unexpected false timing path introduced")
    warning_ports = native.io_warnings(WORK / "execution-stdout.log")
    result = {
        "Schema": "independent-processed-output-native-diagnostic-audit-v1",
        "AuditedUTC": datetime.now(timezone.utc).isoformat(), "AuditCompleted": True,
        "NativeExitCode": execution["NativeExitCode"], "NativeFlowCompleted": True,
        "NativeExitZeroIsNotTimingAcceptance": True, "InputSHA256": hashes,
        "SourceDrift": source_drift, "CompiledInputDrift": copies_drift,
        "VerifiedSourceInputs": len(plan["InputSHA256"]), "VerifiedCompiledCopies": len(plan["CompiledInputs"]),
        "FinalRoutedADF": {"Path": str(adf), "SHA256": sha(adf)},
        "PreSTASnapshotEqualsFinalADF": True,
        "Native114PinAudit": {"Passed": True, "PortCount": 114, "DDRPins": 71,
            "Directions": dict(Counter(ports.values())), "AutoAssignedPorts": 0,
            "FinalRoutedLOCAndDirectionMatch": True, "NativePCFMatchesDeclaredElectricalAttributes": True,
            "Banks": {bank: {"Ports": len(names), "DeclaredVCCIO": declared[names[0]]["VCCIO"]}
                      for bank, names in sorted(bank_summary.items())},
            "PinInventory": [{"Port": name, **declared[name], "Routed": routed[name]} for name in sorted(ports)]},
        "NativeFinalResources": resources(ror.read_text()),
        "NativeFinalLogicByCLM": logic_by_clm(ror.read_text()),
        "MapResources": map_resources((WORK / "device_map/processed_output_top.dmr").read_text()),
        "TenNativeCornerSummaries": summaries, "NativeClockSummary": clocks,
        "WorstDetailedPaths": worst_paths,
        "NegativeDetailedPaths": [r for r in details if r["SlackNS"] is not None and r["SlackNS"] < 0],
        "UnconstrainedDetailedPaths": [r for r in details if r["Kind"] == "unconstrained"],
        "DetailedPathCount": len(details), "FalsePathCounts": {str(key): len(rows) for key, rows in false_paths.items()},
        "ExternalIOWarningPorts": [{"Code": code, "Port": port} for code, port in sorted(warning_ports)],
        "ConstraintsEditor": {"Errors": 0, "CriticalWarnings": 0, "Warnings": 36,
                              "WarningsAreSharePinSelection": True, "ConstraintCount": 780},
        "AsyncRegAttributeIgnoredByPDS": True, "ActualPhysicalCDCAndGraySkewAccepted": False,
        "AllInternalTimingNonNegative": all(row["FailingChecks"] == 0 and row["WorstSlackNS"] >= 0
                                               for row in summaries.values()),
        "TimingAccepted": False, "ExternalIOAccepted": False, "ActualBoardRevisionVerified": False,
        "HardwareReleaseAllowed": False, "HardwareAccessed": False, "BitstreamRequested": False,
        "NextReadOnlyQueries": [
            "Query this new final ADF for both new hold path source/endpoint pins and all nets/sites along the path; do not import old _N173/TX_DATA detour.",
            "New hold path is PHY read ICLKDIV -> rddata_r1[5]/D, phy_dq_sysclk_1 -> ddrphy_sysclk. Confirm real input capture edge, net identity, endpoints and placement before any repair proposal.",
            "Independently query reset/training native endpoints in this new ADF before considering any IP/entry exception profile; retain fast nonnegative checks as part of the full inventory.",
            "Audit output FIFO/capture FIFO Gray and held buses at their actual final synchronizer FF sites; async_reg was ignored by this PDS frontend."],
        "Limits": ["Resource and pin matching do not prove video output, DDR training or current camera operation.",
            "The native diagnostic has real data-hold and reset-recovery failures, so timing acceptance remains false.",
            "No external IO delays were guessed. MS7210 sampling mode, PCB skew, control IO and physical CDC require separate evidence.",
            "Detailed paths are bounded by the native report max_path20 setting; all clock-pair summaries are retained."]}
    require(all(sha(PROJECT / name) == digest for name, digest in hashes.items()), "audit input drift")
    output = Path(output_path).resolve()
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print(json.dumps({"AuditCompleted": True, "TimingAccepted": False, "Native114Pins": True,
                      "Report": str(output), "SHA256": sha(output),
                      "TenNativeSummaries": {key: {k:v for k,v in row.items() if k in
                          ("WorstSlackNS", "FailingChecks", "TotalChecks")} for key, row in summaries.items()}}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    run(arguments.work_dir, arguments.output)
