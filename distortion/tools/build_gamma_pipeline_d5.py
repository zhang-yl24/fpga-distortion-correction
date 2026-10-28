"""Small source-bound Gamma pipeline PDS wrapper. Default plan; no board path.

Only --execute-build invokes the existing pds_shell.exe. The only product is an
offline SRAM file. Historical lens parameters must never be called new-lens
correction. Work/logs are fresh children of the approved scratch root.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

import prepare_gamma_pipeline_d5 as prepared
import pds_gate_log_audit as gate_log

ROOT, TARGET = prepared.ROOT, prepared.TARGET
APPROVED = ROOT / "build/offline-20261024"
sha = prepared.sha
load = lambda p: json.loads(Path(p).read_text(encoding="utf-8-sig"))


def write_new(path, value):
    with Path(path).open("x", encoding="utf-8") as out:
        json.dump(value, out, indent=2, allow_nan=False)
        out.write("\n")


def verify_prepared(profile_binding=None):
    return prepared.verify_clone(profile_binding) if profile_binding else prepared.verify_clone()


def validate_simulation(path, profile_binding=None):
    path = Path(path).resolve()
    if not path.is_relative_to(APPROVED.resolve()):
        raise ValueError("simulation evidence must be under approved scratch")
    proof = load(path)
    if (proof.get("Passed") is not True or proof.get("Target") != TARGET or
            proof.get("HardwareAccessed") is not False or proof.get("PDSAccessed") is not False or
            not isinstance(proof.get("SourceSHA256"), dict) or
            proof.get("SourceSHA256") != proof.get("SourceSHA256After")):
        raise ValueError("simulation target/source/completion contract differs")
    current = verify_prepared(profile_binding)
    if (proof.get("IntegrationContract") != current.get("IntegrationContract") or
            proof.get("CacheLayout") != current.get("CacheLayout")):
        raise ValueError("simulation cache layout/integration contract differs from current candidate")
    compiled = proof.get("CompileSources")
    cache = current["IntegrationContract"]["cache"]
    if (not isinstance(compiled, dict) or compiled.get(cache) != current["SourceSHA256"][cache] or
            any(name in compiled for name in prepared.CACHE_FILES.values() if name != cache) or
            any(current["SourceSHA256"].get(name) != digest for name, digest in compiled.items())):
        raise ValueError("simulation compiled cache/source hashes differ from current candidate")
    previous = proof["SourceSHA256"]
    if profile_binding and (proof.get("ProfileBinding") != current.get("ProfileBinding") or
                            not proof.get("NativeReference",{}).get("SourceCaptures")):
        raise ValueError("real branch needs fresh profile-bound simulation and actual native source records")
    moved = False
    reverse = {v: k for k, v in prepared.PARAMETER_MOVES.items()}
    for name, digest in current["SourceSHA256"].items():
        if previous.get(name, "").lower() == digest.lower():
            continue
        if profile_binding:
            raise ValueError("real profile requires exact current source hashes; historical relocation bridge forbidden")
        # Explicit, narrow equivalence: private parameter files retain identical
        # bytes; only their two include paths/list entries moved after simulation.
        if name in reverse and previous.get(reverse[name], "").lower() == digest.lower():
            moved = True
            continue
        if name == f"board/{TARGET}.v":
            payload = (ROOT/name).read_bytes()
            for private, old in reverse.items():
                payload = payload.replace(("/"+private+'"').encode(), ("/"+old+'"').encode())
        elif name == f"board/{TARGET}-sources.json":
            names = [reverse.get(n, n) for n in load(ROOT/name)]
            payload = (json.dumps(names, indent=2)+"\n").encode()
        else:
            raise ValueError("current synthesis input differs from tested RTL/parameters: "+name)
        if hashlib.sha256(payload).hexdigest() != previous.get(name, "").lower():
            raise ValueError("unapproved change beyond private equal-byte include relocation: "+name)
        moved = True
    markers = {"small": "PASS Gamma parity small regression:",
               "video": "PASS Gamma parity DDR video:",
               "native": "PASS Gamma parity twelve native regression:"}
    for kind, marker in markers.items():
        record = proof.get("Suites", {}).get(kind, {})
        log = path.parent/kind/"simulation.log"
        if record.get("Passed") is not True or sha(log) != record.get("LogSHA256"):
            raise ValueError("suite log/completion differs: "+kind)
        text = log.read_text(encoding="utf-8", errors="replace")
        if marker not in text or re.search(r"(?im)^\s*(?:fatal|error):", text):
            raise ValueError("suite log did not pass: "+kind)
    if (len(proof.get("NativeCycles", [])) != 12 or proof.get("NativeReference", {}).get("pixels") != 3686400 or
            sha(path.parent/"native/cycles.csv") != proof.get("NativeCyclesSHA256")):
        raise ValueError("native full-frame evidence differs")
    for name, digest in proof.get("FixtureSHA256", {}).items():
        fixture = (path.parent/name).resolve()
        if not fixture.is_relative_to(path.parent) or sha(fixture) != digest:
            raise ValueError("simulation fixture changed: "+name)
    for record in proof.get("NativeReference",{}).get("SourceCaptures",[]):
        if record.get("physical_capture_record") is not True:
            raise ValueError("native simulation source is not a bound physical capture")
        for name,key in (("metadata_path","metadata_sha256"),("raw_path","raw_sha256"),("image_path","image_sha256")):
            if sha(Path(record[name]))!=record[key]:raise ValueError("actual source changed after simulation")
    return {"Path": str(path), "SHA256": sha(path),
            "SourceBinding": "equal-byte private include relocation" if moved else "exact current sources",
            "HistoricalParametersOnly": not bool(profile_binding), "NewLensCorrectionVerified": False,
            "RealProfileUsed": bool(profile_binding)}


def port_direction(port):
    if re.fullmatch(r"clk_27m|clk_p|clk_n|key0_n|cam_pclk|cam_vsync|cam_href|cam_data\[\d+\]|uart_rxd", port):
        return "input"
    if re.fullmatch(r"cam_rst_n|cam_scl|cam_sda|hd_scl|hd_sda|mem_dq\[\d+\]|mem_dqs(_n)?\[\d+\]", port):
        return "inout"
    return "output"


def validate_pins(path):
    active = {}
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        fields = [f.strip() for f in line.split("|")]
        if len(fields) >= 7 and fields[4]:
            pad, port, direction, enabled = fields[0], fields[4], fields[5], fields[6]
            if port in active or enabled != "YES" or direction != port_direction(port):
                raise ValueError("duplicate/inactive/wrong-direction routed port: "+port)
            active[port] = pad
    expected = load(ROOT/f"board/{TARGET}-pins.json")
    if (len(active) != 130 or len(set(active.values())) != 130 or active != expected or
            active.get("cam_data[5]") != "AA23" or active.get("uart_rxd") != "B24"):
        raise ValueError("actual routed130 pin map/D5AA23/RXB24 differs")
    return active


def read_text(path):
    data = Path(path).read_bytes()
    return data.decode("utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8", errors="replace")


def validate_artifacts(work, before, simulation, profile_binding=None, cad_script_role=gate_log.CANONICAL_MAIN):
    checked_sim = validate_simulation(simulation["Path"],profile_binding) if profile_binding else validate_simulation(simulation["Path"])
    if verify_prepared(profile_binding) != before or checked_sim != simulation:
        raise ValueError("source or simulation evidence changed during build")
    log_audit = gate_log.audit_gate_log(work, TARGET, cad_script_role)
    after_hold = work/"place_route"/f"{TARGET}_timing_summary_after_hold_fix.txt"
    final = work/"report_timing"/f"{TARGET}.rtr"
    routed = work/"place_route"/f"{TARGET}_pnr.adf"
    pins = work/"place_route"/f"{TARGET}_prr.prt"
    bit = work/"generate_bitstream"/f"{TARGET}.sbit"
    # PDS can apply another hold fix after writing its PNR summary. The actual
    # final gate is report_timing from the saved final routed DB, as in the
    # stable Gamma flow; retain the earlier summary without upgrading its result.
    hold_text, final_text = read_text(after_hold), read_text(final)
    if (not hold_text.strip() or len(re.findall(r"(?m)^Design Summary\s*:", final_text)) != 1
            or not re.search(r"(?m)^Design Summary\s*:\s*All Constraints Met\.\s*$", final_text)):
        raise ValueError("missing hold summary or final saved-DB timing did not meet all constraints")
    if str(routed).replace("\\", "/").lower() not in final_text.replace("\\", "/").lower():
        raise ValueError("final report does not identify this saved routed DB")
    if final.stat().st_mtime_ns < routed.stat().st_mtime_ns or bit.stat().st_mtime_ns < final.stat().st_mtime_ns:
        raise ValueError("final report predates routed DB or bitstream predates final timing")
    validate_pins(pins)
    if bit.stat().st_size == 0:
        raise ValueError("empty SRAM file")
    return {"Target": TARGET, "Device": "PG2L100H", "Package": "FBG676", "SCBV": "High Voltage",
            "UnusedIO": "UNUSED", "Bitstream": str(bit), "SHA256": sha(bit).upper(),
            "TimingReport": str(final), "TimingSHA256": sha(final).upper(),
            "AfterHoldTimingReport": str(after_hold), "AfterHoldTimingSHA256": sha(after_hold).upper(),
            "AfterHoldSummaryAllMet": bool(re.search(r"(?m)^Design Summary\s*:\s*All Constraints Met\.\s*$", hold_text)),
            "FinalRoutedDatabase": str(routed), "FinalRoutedDatabaseSHA256": sha(routed).upper(),
            "PinReport": str(pins), "PinReportSHA256": sha(pins).upper(), "RoutedPinCount": 130,
            "SourceSHA256": before["SourceSHA256"], "SourceSHA256After": verify_prepared(profile_binding)["SourceSHA256"],
            "IntegrationContract": before["IntegrationContract"], "SimulationEvidence": simulation,
            "ProfileBinding": before.get("ProfileBinding"),
            "PrivateParameterSHA256": {n: sha(ROOT/n) for n in prepared.PARAMETER_MOVES.values()},
            "BuildValidation": "final saved routed-DB report_timing after hold fix passed; all130 pins checked; native exit0. Earlier PNR summary result retained separately.",
            "ProcessExitCode": 0, "HardwareAccessed": False, "NewLensCorrectionVerified": False,
            "BuilderSHA256": sha(Path(__file__)), "PreparationHelperSHA256": sha(Path(prepared.__file__)),
            "PDSLogAudit": log_audit, "PDSLogAuditHelperSHA256": sha(Path(gate_log.__file__)),
            "ValidationStage": "post_build_before_hardware", "PreBitGateExecutionProven": False,
            "Limits": ("Offline explicit profile-bound integration bit only; development status remains as bound. No programming/Flash path or measured optical/hardware acceptance."
                       if profile_binding else "Offline historical-parameter integration bit only. No programming/Flash path. Not an authorization to apply old lens correction to the new lens, nor measured resource/fps/optical acceptance.")}


def stop_owned(child, work):
    if child.poll() is not None:
        return
    if os.name == "nt":
        with (work/"owned-stop.log").open("xb") as out:
            subprocess.run([str(Path(os.environ["SystemRoot"])/"System32/taskkill.exe"),
                            "/PID", str(child.pid), "/T", "/F"], stdout=out, stderr=subprocess.STDOUT,
                           check=False, creationflags=subprocess.CREATE_NO_WINDOW, timeout=20)
    else:
        child.kill()
    child.wait(timeout=20)


def run_build(workdir, *, execute=False, simulation_evidence, pds_bin=None, timeout_seconds=1200, profile_binding=None):
    if type(execute) is not bool or type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or not 60 <= timeout_seconds <= 7200:
        raise ValueError("explicit execute flag and finite60..7200s offline bound required")
    work = Path(workdir).resolve()
    if (not APPROVED.is_dir() or work == APPROVED.resolve() or not work.is_relative_to(APPROVED.resolve())
            or not work.parent.is_dir() or work.exists()):
        raise ValueError("fresh output below existing approved scratch required; no overwrite")
    before = verify_prepared(profile_binding)
    simulation = validate_simulation(simulation_evidence,profile_binding) if profile_binding else validate_simulation(simulation_evidence)
    config_path = ROOT.parent/"team-config.local.json"
    config = load(config_path) if config_path.is_file() else {}
    pds = Path(pds_bin or os.environ.get("FPGA_PDS_BIN") or config.get("pds_bin") or r"E:\Pango\PDS_2022.2-SP6.4\bin").resolve()
    if execute and not (pds/"pds_shell.exe").is_file():
        raise ValueError("existing PDS pds_shell.exe required")
    command = [str(pds/"pds_shell.exe"), "-file", str(ROOT/f"board/build-{TARGET}.tcl"),
               "-work_dir", str(work), "-project_name", TARGET]
    work.mkdir()
    plan = {"Target": TARGET, "ExecuteBuild": execute, "HardwareAccessed": False,
            "Operation": "offline_compile_route_sram_file_only", "NoFlashOrProgrammingOperation": True,
            "SourceSHA256": before["SourceSHA256"], "SourceCount": len(before["SourceSHA256"]),
            "OutputDirectory": str(work), "Command": command, "SimulationEvidence": simulation,
            "IntegrationContract": before["IntegrationContract"], "BuilderSHA256": sha(Path(__file__)),
            "ProfileBinding": before.get("ProfileBinding"),
            "PreparationHelperSHA256": sha(Path(prepared.__file__)), "NewLensCorrectionVerified": False}
    plan["PDSLogAuditHelperSHA256"] = sha(Path(gate_log.__file__))
    write_new(work/"plan.json", plan)
    if not execute:
        return plan
    result = {"Target": TARGET, "Passed": False, "HardwareAccessed": False,
              "StartedUtc": datetime.now(timezone.utc).isoformat(), "OutputDirectory": str(work),
              "SourceSHA256": before["SourceSHA256"], "ProcessExitCode": None, "TimedOut": False}
    child = None
    try:
        flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        with (work/"build-stdout.log").open("xb") as stdout, (work/"build-stderr.log").open("xb") as stderr:
            child = subprocess.Popen(command, cwd=work, stdout=stdout, stderr=stderr, **flags)
            result["OwnedPID"] = child.pid
            try:
                result["ProcessExitCode"] = child.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                result["TimedOut"] = True
                stop_owned(child, work)
                raise ValueError("owned offline PDS process exceeded bound")
        if type(result["ProcessExitCode"]) is not int or result["ProcessExitCode"] != 0:
            raise ValueError("native PDS exit nonzero or unavailable")
        if (sha(Path(__file__)) != plan["BuilderSHA256"] or sha(Path(prepared.__file__)) != plan["PreparationHelperSHA256"]
                or sha(Path(gate_log.__file__)) != plan["PDSLogAuditHelperSHA256"]):
            raise ValueError("builder/preparation helper changed during build")
        manifest = validate_artifacts(work, before, simulation,profile_binding)
        write_new(work/"validated-build.json", manifest)
        result.update(Passed=True, ValidatedBuild=str(work/"validated-build.json"),
                      ValidatedBuildSHA256=sha(work/"validated-build.json"))
    except (Exception, KeyboardInterrupt) as exc:
        result["Error"] = type(exc).__name__+": "+str(exc)
    finally:
        if child is not None and child.poll() is None:
            try:
                stop_owned(child, work)
            except Exception as exc:
                result["CleanupError"] = str(exc); result["Passed"] = False
        result["SourceSHA256After"] = {n: sha(ROOT/n) if (ROOT/n).is_file() else None
                                        for n in before["SourceSHA256"]}
        if result["SourceSHA256After"] != before["SourceSHA256"]:
            result["Passed"] = False
            result["SourceDrift"] = True
        result["EndedUtc"] = datetime.now(timezone.utc).isoformat()
        write_new(work/"gamma-pipeline-build-result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--simulation-evidence", required=True)
    parser.add_argument("--execute-build", action="store_true")
    parser.add_argument("--profile-binding", type=Path)
    parser.add_argument("--pds-bin")
    parser.add_argument("--timeout-seconds", type=float, default=1200)
    args = parser.parse_args()
    try:
        result = run_build(args.workdir, execute=args.execute_build, simulation_evidence=args.simulation_evidence,
                           pds_bin=args.pds_bin, timeout_seconds=args.timeout_seconds,profile_binding=args.profile_binding)
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr); return 1
    print(json.dumps(result, indent=2))
    return 0 if not args.execute_build or result.get("Passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
