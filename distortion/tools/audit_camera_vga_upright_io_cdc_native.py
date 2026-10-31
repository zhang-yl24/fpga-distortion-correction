"""CPU-only native completion of actual upright IO/CDC structural evidence.

Batch preparation preserves all exact expected pairs; grouped native top-N
reports never substitute for per-pair, per-corner, setup/hold coverage.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re

import audit_camera_vga_upright_io_cdc as structure
import audit_camera_vga_cdc_native as syntax

prep, inspect, cdc, io = structure.prep, structure.inspect, structure.cdc, structure.io
require, sha = prep.require, prep.sha
SELF = Path(__file__).resolve()
SCHEMA = "camera-vga-upright-io-cdc-native-v1"
BATCH_SCHEMA = "camera-vga-upright-io-cdc-batch-v1"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def add(watched, path, digest=None):
    path = Path(path).absolute()
    require(path == path.resolve() and path.is_file(), "canonical existing evidence required")
    current = sha(path)
    require(digest is None or current == digest, "evidence drift: " + str(path))
    require(path not in watched or watched[path] == current, "conflicting evidence identity")
    watched[path] = current
    return path


def digest_map(value, watched):
    require(isinstance(value, dict) and value, "nonempty hash inventory required")
    for name, digest in value.items():
        require(isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest), "invalid evidence hash")
        add(watched, name, digest)


def actual_queries(scalar, resets, replicas):
    rows = scalar + resets + [chain for tree in replicas for chain in tree["Chains"]]
    unique = {}
    for row in rows:
        for query in row["NativeQueries"]:
            key = (query["Source"], query["Endpoint"])
            require(key not in unique or unique[key] == query, "conflicting actual interstage query")
            unique[key] = query
    return [unique[k] for k in sorted(unique)]


def native_receipt(path, mode, source_sha, build_sha, watched):
    path = Path(path).absolute()
    schema = read(path).get("Schema")
    if schema == "camera-vga-upright-derived-inspection-v1":
        import run_camera_vga_upright_derived_inspect as derived
        value = derived.bind_receipt(path, watched)
        require(value["Mode"] == mode and value["SourceADFSHA256"] == source_sha
                and value["BuildPlanSHA256"] == build_sha, "derived receipt candidate/mode differs")
        add(watched, derived.__file__)
        return path, value
    require(schema == inspect.SCHEMA and mode in ("query", "export"), "unsupported native receipt identity")
    import audit_camera_vga_upright_reset as binding
    value = read(path)
    bound = binding.inspection_receipt(path, mode, value["BuildPlan"], value["SourceADF"], source_sha, watched)
    require(bound["BuildPlanSHA256"] == build_sha, "original inspection belongs to different build")
    add(watched, binding.__file__)
    return path, bound


def derive_structure(build_plan, source, source_sha, export_path, output, report_path=None):
    """Re-evaluate the FINAL export, including derived candidates, without global patches."""
    build_plan = Path(build_plan).absolute()
    original = build_plan.parent / "place_route" / (prep.TARGET + "_pnr.adf")
    build, watched = inspect.bind(build_plan, original, sha(original))
    source = add(watched, source, source_sha)
    er, export = native_receipt(export_path, "export", source_sha, sha(build_plan), watched)
    rr, reported = (er, export) if report_path is None else native_receipt(
        report_path, read(report_path)["Mode"], source_sha, sha(build_plan), watched)
    netlist = structure.artifact(er, export, prep.TARGET + "_sim.v")
    require(export["Netlist"] == {"Path": str(netlist), "SHA256": sha(netlist), "Bytes": netlist.stat().st_size}
            and export.get("NativeNetlistWithFFloc") is True, "actual final native export binding differs")
    text = netlist.read_text(encoding="utf-8-sig")
    graph = cdc.Graph(structure.functional(text))
    gray, scalar = cdc.gray_structures(graph), cdc.scalar_structures(graph)
    resets, replicas = cdc.reset_structures(graph)
    fdc = add(watched, build_plan.parent / "compiled" / build["Constraints"]["FDC"], build["InputSHA256"][build["Constraints"]["FDC"]])
    gray_report = structure.artifact(rr, reported, prep.TARGET + "_exception.rtr")
    constraints, groups, missing, stats = structure.gray_coverage(gray, gray_report, fdc)
    queries = actual_queries(scalar, resets, replicas)
    gray_queries = []
    for endpoint in sorted({r["Endpoint"] for r in missing}):
        bit = cdc.one([b for b in gray if b["NativeEndpoint"] == endpoint], "actual missing Gray bit")
        gray_queries.append({"Label": bit["Label"], "Source": cdc.native_parent(bit["Source"]) + "/CLK", "Endpoint": endpoint,
                             "SourceClock": bit["SourceClock"], "DestinationClock": bit["DestinationClock"],
                             "Purpose": "missing current Gray max-delay path; both corners"})
    paths = {"top": prep.PROJECT / prep.TOP, "pcf": build_plan.parent / "device_map" / (prep.TARGET + ".pcf"),
             "prt": build_plan.parent / "place_route" / (prep.TARGET + "_prr_route_optimize.prt"),
             "official": prep.PROJECT / "platform/video_base/HDMI_IN_DDR3_HDMI_OUT_top.fdc",
             "cam_reference": prep.PROJECT / "board/raw_camera_capture_cam2_ref.fdc",
             "cam_pins": prep.PROJECT / "board/raw_camera_capture_cam2_ref-pins.json"}
    texts = {key: add(watched, path).read_text(encoding="utf-8-sig") for key, path in paths.items()}
    top_text, top_adapt = structure.io_syntax(texts["top"])
    net_text, net_adapt = structure.io_syntax(text)
    pins = io.pin_audit(top_text, fdc.read_text(), texts["pcf"], texts["prt"], net_text, texts["official"], texts["cam_reference"], json.loads(texts["cam_pins"]))
    for module in (structure, syntax, cdc, syntax.path_syntax, io, inspect, prep, cdc.physical, cdc.physical.dialect,
                   io.pin_parser, io.net_parser, io.tx_parser, cdc.physical.native, cdc.physical.hold):
        add(watched, module.__file__)
    add(watched, SELF)
    provenance = {"Target": prep.TARGET, "CandidateADF": {"Path": str(source), "SHA256": source_sha},
                  "BuildPlanSHA256": sha(build_plan), "ActualNetlist": {"Path": str(netlist), "SHA256": sha(netlist)},
                  "InputSHA256": {str(p): h for p, h in watched.items()}, "ToolSHA256": {str(p): h for p, h in watched.items() if p.suffix == ".py"}}
    result = {"Schema": "camera-vga-upright-io-cdc-structure-v1", **provenance, "AuditedUTC": prep.utc(), "StructuralAuditPassed": True,
              "ActualCellCount": len(graph.cells), "ActualFFCount": len(graph.ff), "GrayBitSynchronizers": gray, "ScalarSynchronizers": scalar,
              "ResetReleaseStructure": {"PackedOrSingleSecondStageChains": resets, "ReplicatedSecondStageTrees": replicas},
              "ConstraintInventory": constraints, "GrayPhysicalGroups": groups, "Pins": pins, "ClockTopology": graph.clock_cache,
              "GrayCoverageReport": {"Path": str(gray_report), "SHA256": sha(gray_report)},
              "ExportReceipt": {"Path": str(er), "SHA256": sha(er)}, "ReportReceipt": {"Path": str(rr), "SHA256": sha(rr)},
              "SourceContract": {"FinalExportReevaluated": True, "OriginalRoutedADF": {"Path": str(original), "SHA256": sha(original)},
                                 "ParserOnlyModuleTokenAdaptations": {"Top": top_adapt, "Export": net_adapt}},
              "Summary": {"GrayBits": len(gray), "ScalarChains": len(scalar), "ResetChains": len(resets),
                          "ReplicatedResetSecondStages": sum(r["SecondStageCount"] for r in replicas), "InterstageQueryPairs": len(queries),
                          "MissingGrayQueryPairs": len(gray_queries), "PinCount": pins["TopPortCount"], **stats},
              "Scope": {"NativeInterstageTimingComplete": False, "GrayDatapathBoundComplete": not missing, "AnalogMTBFProven": False,
                        "AllCDCUniversallyProven": False, "ExternalACTimingAccepted": False, "NativeElectricalSettingsVerified": False},
              "HardwareAccessed": False, "EDAExecuted": False, "TimingAccepted": False, "HardwareReleaseAllowed": False}
    plan = {"Schema": "camera-vga-upright-io-cdc-query-plan-v1", **provenance, "Queries": queries, "GrayCoverageQueries": gray_queries,
            "MissingGrayCases": missing, "IOSites": sorted({r["Site"] for r in pins["PinInventory"]}), "OneNativeContext": True, "HardwareAccessed": False}
    body, _ = batch_body(plan)
    output = prep.work_path(output)
    require(not output.exists() and not inspect.drift(watched), "fresh final structural directory and stable inputs required")
    output.mkdir()
    for name, value in (("io-cdc-structure.json", result), ("query-plan.json", plan)):
        inspect.diagnostic.write(output / name, value)
    (output / "query-body.tcl").write_text(body, encoding="ascii", newline="\n")
    return result


def load_structure(structure_path, query_path):
    watched = {}
    structure_path, query_path = add(watched, structure_path), add(watched, query_path)
    old, plan = read(structure_path), read(query_path)
    require(old.get("Schema") == "camera-vga-upright-io-cdc-structure-v1"
            and old.get("Target") == prep.TARGET and old.get("StructuralAuditPassed") is True,
            "actual upright structural proof required")
    require(plan.get("Schema") == "camera-vga-upright-io-cdc-query-plan-v1" and plan.get("Target") == prep.TARGET
            and old["CandidateADF"] == plan["CandidateADF"] and old["ActualNetlist"] == plan["ActualNetlist"]
            and old["BuildPlanSHA256"] == plan["BuildPlanSHA256"], "query/structure candidate differs")
    for value in (old, plan):
        digest_map(value["InputSHA256"], watched)
        require(value.get("ToolSHA256"), "structure tool closure absent")
        for name, digest in value["ToolSHA256"].items():
            require(value["InputSHA256"].get(name) == digest, "structural tool absent from input closure")
    source = add(watched, old["CandidateADF"]["Path"], old["CandidateADF"]["SHA256"])
    netlist = add(watched, old["ActualNetlist"]["Path"], old["ActualNetlist"]["SHA256"])
    require(str(netlist) in old["InputSHA256"], "actual netlist not in original structural closure")
    graph = cdc.Graph(structure.functional(netlist.read_text(encoding="utf-8-sig")))
    gray, scalar = cdc.gray_structures(graph), cdc.scalar_structures(graph)
    resets, replicas = cdc.reset_structures(graph)
    require(old["GrayBitSynchronizers"] == gray and old["ScalarSynchronizers"] == scalar
            and old["ResetReleaseStructure"] == {"PackedOrSingleSecondStageChains": resets, "ReplicatedSecondStageTrees": replicas}
            and old["ActualCellCount"] == len(graph.cells) and old["ActualFFCount"] == len(graph.ff),
            "structure differs from actual final functional netlist")
    if "GrayCoverageReport" in old:
        gray_report = add(watched, old["GrayCoverageReport"]["Path"], old["GrayCoverageReport"]["SHA256"])
        fdc = add(watched, old["ConstraintInventory"]["Path"], old["ConstraintInventory"]["SHA256"])
        constraints, physical_groups, actual_missing, _ = structure.gray_coverage(gray, gray_report, fdc)
        require(constraints == old["ConstraintInventory"] and physical_groups == old["GrayPhysicalGroups"]
                and actual_missing == plan["MissingGrayCases"], "actual native initial Gray evidence differs from structure")
    queries = actual_queries(scalar, resets, replicas)
    require(plan["Queries"] == queries, "interstage query plan differs from current graph")
    missing = {bit["NativeEndpoint"] for bit in gray if any(group["Group"] == bit["Group"] and
               bit["NativeEndpoint"] not in {p["Endpoint"] for p in group["Paths"]} for group in old["GrayPhysicalGroups"])}
    expected_gray = []
    for endpoint in sorted(missing):
        bit = cdc.one([b for b in gray if b["NativeEndpoint"] == endpoint], "current missing Gray bit")
        expected_gray.append({"Label": bit["Label"], "Source": cdc.native_parent(bit["Source"]) + "/CLK", "Endpoint": endpoint,
                              "SourceClock": bit["SourceClock"], "DestinationClock": bit["DestinationClock"],
                              "Purpose": "missing current Gray max-delay path; both corners"})
    require(plan["GrayCoverageQueries"] == expected_gray, "Gray query plan differs from actual structural gap")
    require(plan["IOSites"] == sorted({r["Site"] for r in old["Pins"]["PinInventory"]}), "IO site query plan differs")
    for module in (structure, syntax, cdc, syntax.path_syntax, io, inspect, prep, cdc.physical, cdc.physical.dialect):
        add(watched, module.__file__)
    add(watched, SELF)
    return old, plan, watched


def batch_body(plan):
    """Actual clocks/source families set groups; exact pair checks remain final."""
    groups = {}
    for query in plan["Queries"]:
        is_reset = re.search(r"reset(?:_sync)?\[0\]/", query["Source"]) is not None
        key = ("reset", query["Clock"], query["Source"]) if is_reset else ("scalar", query["Clock"], "")
        groups.setdefault(key, []).append(query)
    if plan["GrayCoverageQueries"]:
        groups[("gray", "mixed_crossings", "")] = plan["GrayCoverageQueries"]
    body, records = ["# One STA context; full actual expected pairs remain individually coverage-checked."], []
    for key, queries in sorted(groups.items()):
        sources, endpoints = sorted({q["Source"] for q in queries}), sorted({q["Endpoint"] for q in queries})
        for name in sources + endpoints:
            require(re.fullmatch(r"[A-Za-z0-9_./\[\]-]+", name), "unsafe actual timing endpoint")
        command = "report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE -from {" + " ".join(sources) + "} -to {" + " ".join(endpoints) + "}"
        body.append(command)
        records.append({"Kind": key[0], "Clock": key[1], "Sources": sources, "Endpoints": endpoints,
                        "ExpectedPairs": [{"Source": q["Source"], "Endpoint": q["Endpoint"]} for q in queries], "Command": command})
    for site in plan["IOSites"]:
        require(re.fullmatch(r"[A-Za-z0-9_]+", site), "unsafe actual IO site")
        body.append("show -dev_instance {" + site + "}")
    text = "\n".join(body) + "\n"
    inspect.query_commands(text)
    return text, records


def save(output, filename, result, watched, payloads=None):
    output = prep.work_path(output)
    require(not output.exists() and not inspect.drift(watched), "fresh output and stable evidence required")
    result["InputSHA256"] = {str(p): h for p, h in sorted(watched.items(), key=lambda x: str(x[0]))}
    result["ToolSHA256"] = {str(p): h for p, h in watched.items() if p.suffix == ".py"}
    output.mkdir()
    for name, content in (payloads or {}).items():
        with (output / name).open("x", encoding="ascii", newline="\n") as stream:
            stream.write(content)
    inspect.diagnostic.write(output / filename, result)
    return result


def batch(structure_path, query_path, output):
    old, plan, watched = load_structure(structure_path, query_path)
    body, groups = batch_body(plan)
    result = {"Schema": BATCH_SCHEMA, "Target": prep.TARGET, "CandidateADF": old["CandidateADF"],
              "Structure": {"Path": str(Path(structure_path).absolute()), "SHA256": sha(structure_path)},
              "QueryPlan": {"Path": str(Path(query_path).absolute()), "SHA256": sha(query_path)},
              "QueryBodySHA256": hashlib.sha256(body.encode()).hexdigest(), "Groups": groups,
              "ExactInterstagePairs": len(plan["Queries"]), "ExactMissingGrayPairs": len(plan["GrayCoverageQueries"]),
              "NativeCommandCount": len(inspect.query_commands(body)), "CoverageAssumedFromGrouping": False,
              "HardwareAccessed": False, "EDAExecuted": False, "HardwareReleaseAllowed": False}
    return save(output, "batch-plan.json", result, watched, {"query-body.tcl": body})


def query_receipt(path, old, watched):
    stage, receipt = native_receipt(path, "query", old["CandidateADF"]["SHA256"], old["BuildPlanSHA256"], watched)
    require(receipt.get("EDAExecuted") is True and not receipt.get("Error")
            and receipt.get("Cleanup", {}).get("Complete") is True, "native query process did not finish cleanly")
    stage_plan = read(stage.parent / "stage-plan.json")
    require(all(receipt.get(k) == v for k, v in stage_plan.items()), "native result differs from prepared stage")
    require(stage_plan["TclSHA256"] == sha(stage.parent / "stage.tcl"), "executed query Tcl drift")
    body = Path(receipt["QueryBody"]).absolute()
    require(str(body) in receipt["InputSHA256"] and sha(body) == receipt["InputSHA256"][str(body)], "query body unbound")
    require(receipt["Artifacts"].get("stdout.log") == sha(stage.parent / "stdout.log"), "native site log unbound")
    return stage, receipt, body


def collect_paths(reports, queries, gray_queries):
    expected = {(q["Source"], q["Endpoint"]): q for q in queries}
    expected_gray = {(q["Source"], q["Endpoint"]): q for q in gray_queries}
    rows, gray_rows, seen, gray_seen = [], [], set(), set()
    for report in reports:
        for lines, line in syntax.blocks(report):
            text = "".join(lines)
            pair = (syntax.field(r"^Startpoint\s*:\s*(.+?)\s*$", text, "path source"),
                    syntax.field(r"^Endpoint\s*:\s*(.+?)\s*$", text, "path endpoint"))
            if pair in expected and not report.name.endswith("_exception.rtr"):
                value = syntax.normal_record(lines, report, line, expected[pair])
                if value["PathSHA256"] not in seen:
                    rows.append(value)
                    seen.add(value["PathSHA256"])
            if pair in expected_gray and "MaxDelay Path" in text and re.search(r"^Path Type\s*:\s*max ", text, re.M):
                value = syntax.gray_record(lines, report, line)
                signature = tuple(value[k] for k in ("Source", "Endpoint", "Corner", "ArrivalNS", "SlackNS", "BoundNS"))
                if signature not in gray_seen:
                    gray_rows.append(value)
                    gray_seen.add(signature)
    bounds = syntax.coverage(rows, queries)
    actual_gray = {(p["Source"], p["Endpoint"], p["Corner"]) for p in gray_rows}
    wanted_gray = {(q["Source"], q["Endpoint"], corner) for q in gray_queries for corner in ("slow", "fast")}
    require(actual_gray == wanted_gray, "targeted Gray native corner coverage incomplete")
    return rows, bounds, gray_rows


def complete_gray(old, supplemental):
    groups = copy.deepcopy(old["GrayPhysicalGroups"])
    expected_groups = {(b["Group"], corner) for b in old["GrayBitSynchronizers"] for corner in ("slow", "fast")}
    require(len(groups) == len(expected_groups) and {(g["Group"], g["Corner"]) for g in groups} == expected_groups,
            "Gray physical groups omit/duplicate a current bus/corner")
    for group in groups:
        bits = [b for b in old["GrayBitSynchronizers"] if b["Group"] == group["Group"]]
        targets = {b["NativeEndpoint"] for b in bits}
        records = {row["Endpoint"]: row for row in group["Paths"]}
        require(len(records) == len(group["Paths"]), "duplicate initial Gray target")
        for row in supplemental:
            if row["Corner"] != group["Corner"] or row["Endpoint"] not in targets:
                continue
            bit = cdc.one([b for b in bits if b["NativeEndpoint"] == row["Endpoint"]], "actual Gray source")
            require(row["Source"] == cdc.native_parent(bit["Source"]) + "/CLK" and row["BoundNS"] == group["Constraint"]["BoundNS"]
                    and row["SlackNS"] >= 0 and 0 <= row["ArrivalNS"] < group["SourcePeriodNS"], "Gray source/delay bound differs")
            if row["Endpoint"] in records:
                require(all(records[row["Endpoint"]][k] == row[k] for k in ("Source", "Endpoint", "Corner", "BoundNS", "SlackNS", "ArrivalNS")),
                        "conflicting reported Gray timing")
            records[row["Endpoint"]] = row
        require(set(records) == targets, "full actual Gray bus coverage incomplete")
        for row in records.values():
            bit = cdc.one([b for b in bits if b["NativeEndpoint"] == row["Endpoint"]], "actual complete Gray bit")
            require(row["Source"] == cdc.native_parent(bit["Source"]) + "/CLK" and row["Corner"] == group["Corner"]
                    and row["BoundNS"] == group["Constraint"]["BoundNS"] and row["SlackNS"] >= 0
                    and 0 <= row["ArrivalNS"] < group["SourcePeriodNS"], "initial/final Gray path bound invalid")
        group.update(Paths=[records[k] for k in sorted(records)], CoverageComplete=True,
                     MaximumArrivalNS=max(row["ArrivalNS"] for row in records.values()),
                     ConservativeSkewUpperBoundNS=max(row["ArrivalNS"] for row in records.values()))
    return groups


def audit(structure_path, query_path, receipt_path, output, batch_path=None):
    old, plan, watched = load_structure(structure_path, query_path)
    stage, receipt, body_path = query_receipt(receipt_path, old, watched)
    body = body_path.read_text(encoding="ascii")
    if batch_path:
        batch_path = add(watched, batch_path)
        prepared = read(batch_path)
        expected_body, groups = batch_body(plan)
        require(prepared.get("Schema") == BATCH_SCHEMA and prepared.get("Target") == prep.TARGET
                and prepared["CandidateADF"] == old["CandidateADF"] and prepared["Groups"] == groups
                and prepared["Structure"] == {"Path": str(Path(structure_path).absolute()), "SHA256": sha(structure_path)}
                and prepared["QueryPlan"] == {"Path": str(Path(query_path).absolute()), "SHA256": sha(query_path)}
                and prepared["QueryBodySHA256"] == hashlib.sha256(expected_body.encode()).hexdigest()
                and body == expected_body, "executed grouped queries differ from exact prepared inventory")
        digest_map(prepared["InputSHA256"], watched)
    else:
        expected = ["report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {" + q["Source"] + "} -to {" + q["Endpoint"] + "}"
                    for q in plan["Queries"] + plan["GrayCoverageQueries"]]
        expected += ["show -dev_instance {" + site + "}" for site in plan["IOSites"]]
        grouped_body, _ = batch_body(plan)
        require(inspect.query_commands(body) == expected or body == grouped_body,
                "executed queries differ from actual structure")
    reports = []
    for name, digest in receipt["Artifacts"].items():
        if name.endswith(".rtr"):
            reports.append(add(watched, stage.parent / name, digest))
    require(reports, "native query report absent")
    rows, bounds, supplemental = collect_paths(reports, plan["Queries"], plan["GrayCoverageQueries"])
    gray = complete_gray(old, supplemental)
    pins = copy.deepcopy(old["Pins"])
    io.apply_native_sites(pins, (stage.parent / "stdout.log").read_text(encoding="gb18030"))
    result = {"Schema": SCHEMA, "Target": prep.TARGET, "CandidateADF": old["CandidateADF"], "AuditedUTC": prep.utc(),
              "StructuralAuditPassed": True, "NativeAuditPassed": True, "ActualNetlist": old["ActualNetlist"],
              "StructureProof": {"Path": str(Path(structure_path).absolute()), "SHA256": sha(structure_path)},
              "NativeReceipt": {"Path": str(stage), "SHA256": sha(stage)}, "Pins": pins,
              "GrayBitSynchronizers": old["GrayBitSynchronizers"], "GrayPhysicalGroups": gray,
              "ScalarSynchronizers": old["ScalarSynchronizers"], "ResetReleaseStructure": old["ResetReleaseStructure"],
              "InterstagePaths": rows, "InterstageBounds": bounds, "SupplementalGrayPaths": supplemental,
              "Summary": {"GrayBits": len(old["GrayBitSynchronizers"]), "GrayCornerCases": sum(len(g["Paths"]) for g in gray),
                          "ScalarChains": len(old["ScalarSynchronizers"]), "ExactInterstagePairs": len(plan["Queries"]),
                          "ExactInterstageCornerKindCases": len(plan["Queries"]) * 4, "NativeInterstageVariants": len(rows),
                          "MinimumInterstageSetupNS": min((p["SlackNS"] for p in rows if p["Kind"] == "setup"), default=None),
                          "MinimumInterstageHoldNS": min((p["SlackNS"] for p in rows if p["Kind"] == "hold"), default=None),
                          "MaximumGrayArrivalNS": max(g["MaximumArrivalNS"] for g in gray), "NativePinCount": pins["TopPortCount"]},
              "Scope": {**old["Scope"], "NativeInterstageTimingComplete": True, "GrayDatapathBoundComplete": True,
                        "AnalogMTBFProven": False, "AllCDCUniversallyProven": False, "ExternalACTimingAccepted": False,
                        "NativeElectricalSettingsVerified": False}, "HardwareAccessed": False, "EDAExecuted": False,
              "TimingAccepted": False, "HardwareReleaseAllowed": False,
              "Limits": "Exact current ordinary interstage setup/hold, full Gray-bit datapath bound and final native site mappings only. Same-BLE structural chains use placement proof. No MTBF, universal CDC, measured external AC, or hardware release."}
    return save(output, "io-cdc-native-proof.json", result, watched)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("structure", "batch", "audit"))
    for name in ("structure", "query-plan", "output-dir"):
        parser.add_argument("--" + name, type=Path, required=name == "output-dir")
    for name in ("build-plan", "source-adf", "export-receipt", "report-receipt"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--source-adf-sha256")
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--batch-plan", type=Path)
    args = parser.parse_args()
    if args.mode == "structure":
        require(args.build_plan and args.source_adf and args.source_adf_sha256 and args.export_receipt,
                "structure needs build plan, exact ADF/hash and final export receipt")
        result = derive_structure(args.build_plan, args.source_adf, args.source_adf_sha256, args.export_receipt, args.output_dir, args.report_receipt)
    elif args.mode == "batch":
        require(args.structure and args.query_plan, "structure and query plan required")
        require(args.receipt is None and args.batch_plan is None, "batch preparation takes no receipt")
        result = batch(args.structure, args.query_plan, args.output_dir)
    else:
        require(args.structure and args.query_plan and args.receipt, "structure, query plan and native receipt required")
        result = audit(args.structure, args.query_plan, args.receipt, args.output_dir, args.batch_plan)
    print(json.dumps({k: result[k] for k in ("Schema", "CandidateADF", "StructuralAuditPassed", "NativeAuditPassed", "Summary",
                                           "ExactInterstagePairs", "ExactMissingGrayPairs", "NativeCommandCount") if k in result}))


if __name__ == "__main__":
    main()
