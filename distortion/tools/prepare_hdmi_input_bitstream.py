"""Prepare exact HDMI input-observer bit export; no EDA or hardware is run.

The committed evidence manifest pins the source ADF and prior native reports.
PDS re-runs STA on that ADF, then a runtime gate compares every summary and
exception before allowing bit generation. This is not hardware acceptance.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import argparse
import gzip
import hashlib
import io
import json
import math
import re
import sys

import audit_ddr_final_timing as timing
import prepare_ddr_native_recovery_constraints as recovery

ROOT = Path(__file__).resolve().parents[1]
TARGET = "hdmi_uart_input_diag"
ADF_SHA256 = "d7858e4b705469e6619ba3c99df2c78bf47e2e4f515aeb3b328ea67c70c676a8"
MANIFEST_SHA256 = "f21377c3251ef6571b15c24befce1fd7507b62903cde7063deaf44e5f9992fc7"
EVIDENCE = "results/hdmi-input-observer-20261030"
NUM = r"[-+]?\d+(?:\.\d+)?"
EX_TYPES = ("set_max_delay(setup)", "set_max_delay(recovery)",
            "set_min_delay(hold)", "set_min_delay(removal)",
            "set_multicycle_path(setup)", "set_multicycle_path(hold)",
            "set_multicycle_path(recovery)", "set_multicycle_path(removal)",
            "set_false_path(setup)", "set_false_path(hold)",
            "set_false_path(recovery)", "set_false_path(removal)")


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inside(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    require(path.is_relative_to(root), "path escapes expected root")
    return path


def literal(path):
    value = Path(path).resolve().as_posix()
    require(not any(c in value for c in "{}\r\n"), "unsafe Tcl path")
    return "{" + value + "}"


def read_text(path):
    with Path(path).open(encoding="utf-8-sig", errors="replace") as stream:
        return stream.read()


def _field(pattern, text, label):
    values = re.findall(pattern, text, re.M)
    require(len(values) == 1, "missing or ambiguous " + label)
    return values[0]


def max_delay_record(text):
    source = _field(r"^Startpoint\s*:\s*(\S+)\s*$", text, "MaxDelay source")
    endpoint = _field(r"^Endpoint\s*:\s*(\S+)\s*$", text, "MaxDelay endpoint")
    group = _field(r"^Path Group\s*:\s*(\S+)\s*$", text, "MaxDelay group")
    corner = _field(r"^Path Type\s*:\s*max \((slow|fast) corner\)\s*$", text, "MaxDelay corner")
    require(_field(r"^Path Class\s*:\s*(.+?)\s*$", text, "MaxDelay class") == "sequential timing path",
            "MaxDelay class is not sequential")
    bound = float(_field(r"^Timing Exception\s*:\s*MaxDelay Path (" + NUM + r")ns -datapath_only\s*$", text, "MaxDelay bound"))
    require(bound == 8.0, "only the audited 8 ns datapath-only bound is supported")
    numbers = {}
    for label, pattern in (
        ("ArrivalNS", r"^ Data arrival time\s+(" + NUM + r")(?:\s+Logic Levels:\s*\d+)?\s*$"),
        ("RequiredNS", r"^ Data required time\s+(" + NUM + r")\s*$"),
        ("SlackNS", r"^ Slack \(MET\)\s+(" + NUM + r")\s*$"),
    ):
        values = [float(v) for v in re.findall(pattern, text, re.M)]
        require(values and all(math.isfinite(v) and v == values[0] for v in values),
                "missing/nonfinite/inconsistent MaxDelay " + label)
        numbers[label] = values[0]
    require(numbers["SlackNS"] >= 0 and numbers["ArrivalNS"] >= 0 and
            abs(numbers["RequiredNS"] - numbers["ArrivalNS"] - numbers["SlackNS"]) <= .0021,
            "MaxDelay slack/arrival/required disagree")
    return dict(Source=source, Endpoint=endpoint, Corner=corner, CaptureClock=group,
                MaxDelayNS=bound, **numbers)


def exception_inventory(path):
    text = read_text(path)
    # Split all 24 tables, including empty types, so unexpected exceptions fail.
    headers = list(re.finditer(r"^\| Exception type\s*:\s*(\S+)\s*\n\| (Slow|Fast) Corner\s*$", text, re.M))
    sections, maxima = {}, []
    for i, header in enumerate(headers):
        key = (header[2].lower(), header[1])
        require(key not in sections, "duplicate native exception table")
        body = text[header.end():headers[i + 1].start() if i + 1 < len(headers) else len(text)]
        starts = list(re.finditer(r"^Startpoint\s*:", body, re.M))
        sections[key] = len(starts)
        if key[1] == "set_max_delay(setup)":
            for j, start in enumerate(starts):
                block = body[start.start():starts[j + 1].start() if j + 1 < len(starts) else len(body)]
                record = max_delay_record(block)
                require(record["Corner"] == key[0], "MaxDelay section corner differs")
                maxima.append(record)
    require(set(sections) == {(corner, kind) for corner in ("slow", "fast") for kind in EX_TYPES},
            "all 24 native exception tables required")
    for (corner, kind), count in sections.items():
        expected = {"set_max_delay(setup)": 167, "set_false_path(hold)": 167,
                    "set_false_path(recovery)": 4, "set_false_path(removal)": 4}.get(kind, 0)
        require(count == expected, "unexpected exception count: " + corner + " " + kind)
    false = timing.parse_false_paths(io.StringIO(text))
    for key, rows in false.items():
        identities = [tuple(row[k] for k in ("Source", "Endpoint", "LaunchClock", "CaptureClock",
                                              "LaunchEdge", "CaptureEdge", "LaunchDataTransition")) for row in rows]
        require(len(identities) == len(set(identities)), "duplicate false-path identity")
    identities = [(p["Corner"], p["Endpoint"]) for p in maxima]
    require(len(identities) == len(set(identities)), "duplicate MaxDelay endpoint")
    return sections, false, maxima


def report_summaries(path):
    with Path(path).open(encoding="utf-8-sig", errors="replace") as stream:
        tables, clocks = timing.parse_summaries(stream)
    for rows in tables.values():
        for row in rows.values():
            require(row["FailingChecks"] == 0 and row["TotalNegativeSlackNS"] == 0 and
                    row["WorstSlackNS"] >= 0 and row["TotalChecks"] > 0,
                    "native timing check failed or is empty")
    with Path(path).open(encoding="utf-8-sig", errors="replace") as stream:
        header = "".join(line for _, line in zip(range(220), stream))
    require(re.search(r"(?m)^Design Summary\s*:\s*All Constraints Met\.\s*$", header),
            "native all-constraints-met declaration missing")
    for key, expected in (("Design", TARGET), ("Device", "PG2L100H"), ("Speed Grade", "-6"), ("Package", "FBG676")):
        require(re.search(r"(?m)^\| " + re.escape(key) + r"\s*:\s*" + re.escape(expected) + r"\s*$", header),
                "native report design/device mismatch: " + key)
    return tables, clocks


def compare_native(baseline_report, baseline_exceptions, report, exceptions):
    baseline = report_summaries(baseline_report)
    current = report_summaries(report)
    require(current == baseline, "native summary or clock inventory changed")
    old_sections, old_false, old_max = exception_inventory(baseline_exceptions)
    sections, false, maxima = exception_inventory(exceptions)
    require(sections == old_sections, "native exception table counts changed")
    keys = ("Source", "Endpoint", "LaunchClock", "CaptureClock", "LaunchEdge", "CaptureEdge", "LaunchDataTransition")
    for key in false:
        require(Counter(tuple(p[k] for k in keys) for p in false[key]) ==
                Counter(tuple(p[k] for k in keys) for p in old_false[key]),
                "native false-path identities changed")
    key = lambda p: (p["Corner"], p["Endpoint"], p["Source"])
    require(sorted(maxima, key=key) == sorted(old_max, key=key), "native MaxDelay identities or values changed")
    return {"AllTenTimingTypesPassed": True, "NativeSummariesAndClocksUnchanged": True,
            "ExactFalsePathsUnchanged": True, "AllMaxDelayChecksUnchanged": True,
            "MaxDelayCountPerCorner": {c: sum(p["Corner"] == c for p in maxima) for c in ("slow", "fast")},
            "FalsePathCountPerCorner": {c: {k: len(false[(c, k)]) for k in ("setup", "hold", "recovery", "removal")} for c in ("slow", "fast")},
            "WorstSlackNS": {c: {k: min(row["WorstSlackNS"] for row in current[0][(c, k)].values()) for k in timing.KINDS} for c in ("slow", "fast")}}


def evidence_entries(project):
    package = inside(project, EVIDENCE)
    manifest_path = package / "manifest.json"
    require(sha(manifest_path) == MANIFEST_SHA256, "committed evidence manifest changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = {row["File"]: row for row in manifest["Files"]}
    require(len(entries) == len(manifest["Files"]), "duplicate evidence path")
    return package, entries


def evidence_bytes(package, entries, name):
    row = entries[name]
    path = inside(package, name)
    data = path.read_bytes()
    require(len(data) == row["Bytes"] and digest(data) == row["SHA256"], "stored evidence changed: " + name)
    require(row["Encoding"] in ("identity", "gzip"), "unknown evidence encoding")
    if row["Encoding"] == "gzip":
        data = gzip.decompress(data)
    require(len(data) == row["SourceBytes"] and digest(data) == row["SourceSHA256"], "decoded evidence changed: " + name)
    return data


def verify_inputs(project, work, plan):
    require(plan["Target"] == TARGET and plan["FinalADFSHA256"] == ADF_SHA256,
            "bitstream plan target/ADF changed")
    for name, wanted in plan["ProjectInputSHA256"].items():
        require(sha(inside(project, name)) == wanted, "project input changed: " + name)
    for name, wanted in plan["WorkInputSHA256"].items():
        require(sha(inside(work, name)) == wanted, "prepared input changed: " + name)
    require(sha(work / "audited-final.adf") == ADF_SHA256, "prepared ADF changed")
    # Re-anchor at runtime instead of trusting caller-editable plan hash values.
    package, entries = evidence_entries(project)
    build = json.loads(evidence_bytes(package, entries, "native-build/build-plan.json"))
    require(all(plan["ProjectInputSHA256"].get(name) == wanted and
                sha(inside(project, name)) == wanted
                for name, wanted in build["InputSHA256"].items()),
            "runtime source closure differs from committed native build")
    for local, frozen in (("baseline.rtr", "scoped-cdc/hdmi_uart_input_diag.rtr.gz"),
                          ("baseline-exceptions.rtr", "scoped-cdc/hdmi_uart_input_diag_exception.rtr.gz"),
                          ("context.fdc", "native-build/hdmi_uart_diag.fdc")):
        require(sha(work / local) == entries[frozen]["SourceSHA256"],
                "runtime baseline differs from committed evidence: " + local)


def prepare(work, *, project=ROOT):
    project, work = Path(project).resolve(), Path(work).resolve()
    require(work.parent == project / "build/hdmi-uart-diagnostic" and work.name.startswith("input-bit-"),
            "fresh input-bit-* child of build/hdmi-uart-diagnostic required")
    require(not work.exists(), "bitstream work directory must not exist")
    package, entries = evidence_entries(project)
    get = lambda name: evidence_bytes(package, entries, name)
    build = json.loads(get("native-build/build-plan.json"))
    require(build["Target"] == TARGET and len(build["Pins"]) == 46, "source build identity differs")
    watched = {EVIDENCE + "/manifest.json": MANIFEST_SHA256}
    for name, wanted in build["InputSHA256"].items():
        require(sha(inside(project, name)) == wanted, "current source differs from native build: " + name)
        require(digest(get("source-inputs/" + name)) == wanted, "source snapshot differs: " + name)
        watched[name] = wanted
    for name in ("tools/prepare_hdmi_input_bitstream.py", "tools/audit_ddr_final_timing.py",
                 "tools/prepare_ddr_native_recovery_constraints.py"):
        watched[name] = sha(inside(project, name))
    adf = get("scoped-cdc/input.adf.gz")
    require(digest(adf) == ADF_SHA256, "audited final ADF identity differs")
    original = get("native-build/build.tcl").decode("utf-8")
    require(digest(original.encode("utf-8")) == build["TclSHA256"], "source Tcl binding differs")
    fdc = get("native-build/hdmi_uart_diag.fdc")
    require(digest(fdc) == build["FDCSHA256"], "source FDC binding differs")
    scoped = json.loads(get("scoped-cdc/scoped-cdc-review.json"))
    connectivity = json.loads(get("functional-export/connectivity-review.json"))
    require(scoped["ReportedScopeAuditPassed"] and scoped["AllTenReportedTimingTypesPass"] and
            scoped["MaxDelayNotOverriddenByFalsePath"] and scoped["ScopedADFSHA256"] == ADF_SHA256,
            "bound scoped audit did not pass")
    require(connectivity["all_81_stage_connections_verified"] and connectivity["verified_ff_count"] == 161 and
            connectivity["same_site_stage_link_count"] == 81, "bound mapped synchronizer review differs")
    config = json.loads((project.parent / "team-config.local.json").read_text(encoding="utf-8-sig"))
    pds = Path(config["pds_bin"]) / "pds_shell.exe"
    python = project.parent / ".venv/Scripts/python.exe"
    require(pds.is_file() and python.is_file(), "configured PDS and Python must exist")
    # Map each original declaration to one member of the hash-bound closure.
    names = []
    for path in re.findall(r"(?m)^add_design \{([^{}]+)\}\s*$", original):
        matches = [n for n in build["InputSHA256"] if path.endswith("/" + n)]
        require(len(matches) == 1 and matches[0] not in names, "source declaration does not map uniquely")
        names.append(matches[0])
    require(len(names) == 12, "exactly twelve diagnostic sources required")
    work.mkdir()
    saved = {
        "audited-final.adf": adf, "context.fdc": fdc,
        "baseline.rtr": get("scoped-cdc/hdmi_uart_input_diag.rtr.gz"),
        "baseline-exceptions.rtr": get("scoped-cdc/hdmi_uart_input_diag_exception.rtr.gz"),
        "source-build-plan.json": get("native-build/build-plan.json"),
        "source-scoped-review.json": get("scoped-cdc/scoped-cdc-review.json"),
        "source-connectivity-review.json": get("functional-export/connectivity-review.json"),
    }
    for name in names:
        saved["sources/" + name] = get("source-inputs/" + name)
    for name, data in saved.items():
        path = inside(work, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    # The explicit final database makes PDS skip prior stages. Keep full context
    # for its project parser; only fresh STA and gated bit export are requested.
    context = ["add_design " + literal(work / "sources" / name) for name in names]
    context += ["add_constraint " + literal(work / "context.fdc"),
                "set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676",
                "compile -top_module " + TARGET, "synthesize -ads -selected_syn_tool_opt 2", "dev_map",
                "pnr -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE",
                "report_timing -force_to_run -input_db_file " + literal(work / "audited-final.adf") +
                " -delay_type min_max -max_path 1000 -nworst 1 -report_exception TRUE",
                "if {[info script] ne {}} {",
                "    set checked [exec " + literal(python) + " " + literal(project / "tools/prepare_hdmi_input_bitstream.py") + " --audit-work " + literal(work) + "]",
                "    puts $checked",
                "    if {[string first {HDMI_INPUT_PRE_BIT_AUDIT_PASS " + ADF_SHA256 + "} $checked] < 0} {error {Pre-bit audit marker absent}}",
                "    gen_bit_stream -force_to_run -input_db_file " + literal(work / "audited-final.adf") + " -scbv {High Voltage} -unused_io_status UNUSED",
                "    puts {HDMI_INPUT_BITSTREAM_COMPLETE}", "    flush stdout", "}"]
    (work / "export.tcl").write_text("\n".join(context) + "\n", encoding="utf-8", newline="\n")
    native = compare_native(work / "baseline.rtr", work / "baseline-exceptions.rtr",
                            work / "baseline.rtr", work / "baseline-exceptions.rtr")
    plan = {"Schema": "hdmi-input-bitstream-plan-v1", "Target": TARGET,
            "ProjectRoot": str(project), "WorkDirectory": str(work), "FinalADFSHA256": ADF_SHA256,
            "ProjectInputSHA256": watched,
            "WorkInputSHA256": {name: sha(work / name) for name in (*saved, "export.tcl")},
            "Command": [str(pds), "-file", str(work / "export.tcl"), "-work_dir", str(work), "-project_name", TARGET],
            "SourceNativeAudit": native, "SourcePins": build["Pins"],
            "HardwareAccessed": False, "HardwareReleaseAllowed": False,
            "BitstreamRequested": True, "EDAExecutedByPreparer": False,
            "ExpectedActualStages": ["report_timing", "runtime_native_audit", "gen_bit_stream"],
            "Limits": "Exact offline observer diagnostic export only; no DDR, camera pixels, optical correction, external AC acceptance or hardware download."}
    verify_inputs(project, work, plan)
    with (work / "bitstream-plan.json").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(plan, indent=2) + "\n")
    return plan


def audit_work(work):
    work = Path(work).resolve()
    plan = json.loads((work / "bitstream-plan.json").read_text(encoding="utf-8"))
    project = Path(plan["ProjectRoot"]).resolve()
    require(project == ROOT.resolve(), "runtime project root differs from audit tool")
    require(work == Path(plan["WorkDirectory"]).resolve() and
            work.parent == project / "build/hdmi-uart-diagnostic", "audit work directory identity differs")
    verify_inputs(project, work, plan)
    native = compare_native(work / "baseline.rtr", work / "baseline-exceptions.rtr",
                            work / "report_timing" / (TARGET + ".rtr"),
                            work / "report_timing" / (TARGET + "_exception.rtr"))
    verify_inputs(project, work, plan)
    result = dict(Schema="hdmi-input-pre-bit-audit-v1", AuditPassed=True, Target=TARGET,
                  CheckedUTC=datetime.now(timezone.utc).isoformat(), FinalADFSHA256=ADF_SHA256,
                  HardwareAccessed=False, HardwareReleaseAllowed=False, **native)
    result["EvidenceSHA256"] = {name: sha(work / name) for name in
                               ("bitstream-plan.json", "audited-final.adf", "export.tcl",
                                "report_timing/" + TARGET + ".rtr", "report_timing/" + TARGET + "_exception.rtr")}
    with (work / "pre-bit-audit.json").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--workdir", type=Path)
    mode.add_argument("--audit-work", type=Path)
    args = parser.parse_args()
    if args.audit_work:
        audit_work(args.audit_work)
        print("HDMI_INPUT_PRE_BIT_AUDIT_PASS " + ADF_SHA256)
    else:
        plan = prepare(args.workdir)
        print(json.dumps({"PreparedOnly": True, "Plan": str(args.workdir / "bitstream-plan.json"), "Command": plan["Command"]}))


if __name__ == "__main__":
    main()
