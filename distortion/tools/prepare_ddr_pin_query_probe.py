"""Prepare an after-map PDS pin-query probe; never run EDA or load an FDC.

PDS documents get_pins, but not its collection serialization. This probe logs
raw returns and accepts only an exact Tcl list of expected backend pin names.
Opaque collections therefore fail validation; no sizeof_collection or guessed
name conversion is used. Audit-only is the default and catches query failures.
Even a matching probe does not apply or accept the candidate timing exceptions.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re

import prepare_ddr_ip_reset_constraints as reset


PROJECT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
MODE = ("audit-only", "strict")


def report_command(max_path=250):
    if type(max_path) is not int or not 250 <= max_path <= 10000:
        raise ValueError("report max_path must be an integer in 250..10000")
    return f"report_timing -force_to_run -delay_type min_max -max_path {max_path} -nworst 1"


def _braced(value):
    if not isinstance(value, str) or any(c in value for c in "{}\r\n"):
        raise ValueError("unsafe Tcl literal")
    return "{" + value + "}"


def _pin_list(pins):
    return "[list " + " ".join(_braced(pin) for pin in pins) + "]"


def make_probe(objects, map_adf, runtime_log, candidate_sha256, *, mode="audit-only"):
    if mode not in MODE or not re.fullmatch(r"[0-9a-f]{64}", candidate_sha256):
        raise ValueError("explicit supported mode and candidate SHA256 required")
    reset.closure.tcl_path(map_adf)
    reset.closure.tcl_path(runtime_log)
    _, queries = reset.make_fdc(objects)
    lines = ["# Prepared only. Insert after dev_map, before any separate candidate add_constraint.",
             "# This script NEVER loads the candidate. PASS means exact query names only.",
             "# PDS return serialization remains unverified until this executes in PDS.",
             "proc __ddr_probe_query {stream label query expected} {",
             "    puts $stream [list QUERY $label $query]",
             "    puts $stream [list EXPECTED $label $expected]",
             "    if {[catch {uplevel 1 $query} raw]} {",
             "        puts $stream [list QUERY_ERROR $label $raw]",
             "        flush $stream",
             "        return 0",
             "    }",
             "    puts $stream [list RAW $label $raw]",
             "    if {[catch {llength $raw} count]} {",
             "        puts $stream [list NOT_TCL_LIST $label $raw]",
             "        flush $stream",
             "        return 0",
             "    }",
             "    puts $stream [list COUNT $label $count [llength $expected]]",
             "    foreach pin $raw {puts $stream [list ACTUAL $label $pin]}",
             "    set exact 1",
             "    if {$count != [llength $expected]} {set exact 0}",
             "    if {[llength [lsort -unique $raw]] != $count} {set exact 0}",
             "    foreach pin $raw {if {[lsearch -exact $expected $pin] < 0} {set exact 0}}",
             "    puts $stream [list EXACT_NAME_SET $label $exact]",
             "    flush $stream",
             "    return $exact",
             "}",
             "if {![file exists " + _braced(map_adf) + "]} {",
             "    puts [list PDS_DDR_PIN_PROBE DEFERRED_NO_MAP " + _braced(mode) + "]",
             "} else {",
             "    set __ddr_probe_stream {}",
             "    set __ddr_probe_status [catch {",
             "        set __ddr_probe_stream [open " + _braced(runtime_log) + " a]",
             "        puts $__ddr_probe_stream [list BEGIN [clock seconds] " + _braced(mode)
             + " " + _braced(candidate_sha256) + " " + _braced(map_adf) + " [file mtime " + _braced(map_adf) + "]]",
             "        set __ddr_probe_all_exact 1"]
    for family, query in zip(reset.SOURCES, queries):
        for role, pattern, pins in (
                ("from", query["FromRegex"], [objects["Sources"][family]["ActualClockPin"]]),
                ("to", query["ToRegex"], objects["CandidateTargets"][family])):
            command = "[list get_pins -hierarchical -regexp " + _braced(pattern) + "]"
            lines.append("        if {![__ddr_probe_query $__ddr_probe_stream " + _braced(family + ":" + role)
                         + " " + command + " " + _pin_list(pins) + "]} {set __ddr_probe_all_exact 0}")
    lines += ["        puts $__ddr_probe_stream [list END [clock seconds] $__ddr_probe_all_exact NOT_APPLIED]",
              "        flush $__ddr_probe_stream", "        close $__ddr_probe_stream",
              "        set __ddr_probe_stream {}",
              "        if {!$__ddr_probe_all_exact} {error {DDR pin queries did not return exact expected names}}",
              "    } __ddr_probe_problem]",
              "    if {$__ddr_probe_status} {",
              "        if {$__ddr_probe_stream ne {}} {",
              "            catch {puts $__ddr_probe_stream [list PROBE_ERROR $__ddr_probe_problem]}",
              "            catch {close $__ddr_probe_stream}",
              "        }",
              "        puts [list PDS_DDR_PIN_PROBE FAILED NOT_APPLIED $__ddr_probe_problem]"]
    if mode == "strict":
        lines.append("        error $__ddr_probe_problem")
    lines += ["    } else {", "        puts [list PDS_DDR_PIN_PROBE EXACT_QUERY_NAMES_MATCHED NOT_APPLIED]",
              "    }", "}"]
    return "\n".join(lines) + "\n"


def _repo_input(repo, path):
    path = Path(path).resolve()
    if not path.is_relative_to(repo) or not path.is_file():
        raise ValueError("input must exist inside this repository")
    return path


def load_candidate(project, path):
    repo = Path(project).resolve().parent
    path = _repo_input(repo, path)
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if (data.get("Schema") != "ddr-ip-reset-constraints-candidate-v1"
            or data.get("DiagnosticOnly") is not True or data.get("NotApplied") is not True):
        raise ValueError("unapplied diagnostic reset candidate plan required")
    hashes = data.get("InputSHA256RepoRelative")
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError("candidate input hashes required")
    for name, digest in hashes.items():
        reset.closure.relative_name(name)
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("invalid candidate input hash")
        if reset.closure.sha(_repo_input(repo, repo / name)) != digest:
            raise ValueError("candidate input changed: " + name)
    inventory_path = _repo_input(repo, repo / reset.closure.relative_name(data["InventorySource"]))
    expected = reset.inventory(reset.parse_netlist(inventory_path))
    if data.get("Objects") != expected:
        raise ValueError("candidate inventory differs from its readable source")
    content, queries = reset.make_fdc(expected)
    if data.get("Queries") != queries:
        raise ValueError("candidate queries differ from the exact source/target inventory")
    fdc = _repo_input(repo, repo / reset.closure.relative_name(data["CandidateFDC"]["Path"]))
    if (fdc.read_bytes() != content.encode("ascii")
            or reset.closure.sha(fdc) != data["CandidateFDC"].get("SHA256")):
        raise ValueError("candidate FDC hash/content mismatch")
    hashes = dict(hashes)
    hashes[path.relative_to(repo).as_posix()] = reset.closure.sha(path)
    hashes[fdc.relative_to(repo).as_posix()] = reset.closure.sha(fdc)
    return data, hashes


def prepare(project, candidate_plan, flow_work_dir, out_dir, *, repo_alias="P:/", mode="audit-only", max_path=250):
    project = Path(project).resolve()
    repo = project.parent
    candidate, hashes = load_candidate(project, candidate_plan)
    alias = reset.closure.validate_repo_alias(project, repo_alias)
    flow = Path(flow_work_dir).resolve()
    build = project / "build"
    if flow == build or not flow.is_relative_to(build) or flow.exists() and not flow.is_dir():
        raise ValueError("flow work directory must be under distortion/build")
    map_path = flow / "device_map/board1080_top_map.adf"
    log_path = flow / "ddr-pin-query-probe.log"
    if map_path.exists() or log_path.exists():
        raise ValueError("probe must target a fresh fullflow without an existing map or probe log")
    root = project / "build/ddr-ip-query-probes"
    output = Path(out_dir).absolute()
    if (root.resolve() != root or output.resolve() != output or output.parent != root
            or not re.fullmatch(r"[A-Za-z0-9_-]+", output.name)
            or output.exists() and (not output.is_dir() or any(output.iterdir()))):
        raise ValueError("output must be a fresh child of build/ddr-ip-query-probes")
    script = make_probe(candidate["Objects"], reset.closure.alias_path(project, alias, map_path),
                        reset.closure.alias_path(project, alias, log_path), candidate["CandidateFDC"]["SHA256"], mode=mode)
    for helper in (SELF, Path(reset.__file__).resolve()):
        helper = _repo_input(repo, helper)
        hashes[helper.relative_to(repo).as_posix()] = reset.closure.sha(helper)
    for name, digest in hashes.items():
        if reset.closure.sha(_repo_input(repo, repo / name)) != digest:
            raise ValueError("probe input changed before preparation: " + name)
    plan = {"Schema": "ddr-pin-query-probe-preparation-v1", "PreparedUTC": datetime.now(timezone.utc).isoformat(),
            "DiagnosticOnly": True, "NotApplied": True, "EDAStarted": False, "HardwareAccessed": False,
            "HardwareReleaseAllowed": False, "Mode": mode, "InputSHA256RepoRelative": hashes,
            "CandidatePlan": Path(candidate_plan).resolve().relative_to(repo).as_posix(),
            "CandidateFDCSHA256": candidate["CandidateFDC"]["SHA256"],
            "MapADF": reset.closure.alias_path(project, alias, map_path),
            "RuntimeLog": reset.closure.alias_path(project, alias, log_path),
            "RuntimeLogFormat": "Tcl list records: BEGIN QUERY EXPECTED RAW COUNT ACTUAL EXACT_NAME_SET END; failures retain QUERY_ERROR/NOT_TCL_LIST/PROBE_ERROR",
            "Probe": {"Path": reset.closure.alias_path(project, alias, output / "query-probe.tcl"),
                      "SHA256": hashlib.sha256(script.encode("ascii")).hexdigest()},
            "ExpectedGroups": [{"Family": q["Family"], "FromCount": 1, "ToCount": q["ExpectedTargetObjects"]} for q in candidate["Queries"]],
            "PDSReturnSerializationVerified": False, "ExpectedReturn": "Exact Tcl list of canonical backend inst:pin names; opaque collection tokens reject",
            "TclStandardLibrarySemanticsTestedWithoutPDS": True,
            "LoadCandidateAutomatically": False, "All244ChecksMatched": False,
            "RecommendedFinalReportCommand": report_command(max_path),
            "FailureEnumerationComplete": False,
            "Integration": ["Insert source query-probe.tcl after dev_map in a fresh complete flow. Initial parse without MAP logs DEFERRED and runs no queries.",
                "Default audit-only catches query/serialization errors so control-flow PNR continues; it never authorizes or loads scope FDC.",
                "Strict mode aborts on any error/mismatch. Even exact-query success proves object names only; inspect raw records and native timing exceptions before applying scope.",
                "No sizeof_collection/get_object_name/foreach_in_collection dependency. PDS collection return shape remains an explicit runtime probe.",
                "report_timing -max_path>=250 -nworst1 is documented; post-report compare actual unique per-group recovery paths to native failing/total counts. Do not assume the larger cap guarantees completeness."]}
    output.mkdir(parents=True, exist_ok=True)
    with (output / "query-probe.tcl").open("x", encoding="ascii", newline="\n") as stream:
        stream.write(script)
    with (output / "probe-plan.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(plan, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-plan", required=True, type=Path)
    parser.add_argument("--flow-work-dir", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--repo-alias", default="P:/")
    parser.add_argument("--mode", choices=MODE, default="audit-only")
    parser.add_argument("--report-max-path", type=int, default=250)
    args = parser.parse_args(argv)
    try:
        plan = prepare(PROJECT, args.candidate_plan, args.flow_work_dir, args.out_dir,
                       repo_alias=args.repo_alias, mode=args.mode, max_path=args.report_max_path)
    except (ValueError, OSError, KeyError, UnicodeError) as exc:
        parser.error(str(exc))
    print(json.dumps({"PreparedOnly": True, "Mode": plan["Mode"], "NotApplied": True, "Probe": plan["Probe"]["Path"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
