"""Fixed R1 K320 triplet offline builder. Default plan; no device/Flash path."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import re
import subprocess

import prepare_gamma_capture_k320_dev as candidate

ROOT = candidate.ROOT
TARGET = "gamma_capture_k320_dev"
APPROVED = ROOT / "build/offline-20261024"
sha = candidate.sha


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_new(path, record):
    with Path(path).open("x", encoding="utf-8") as out:
        json.dump(record, out, indent=2, ensure_ascii=False, allow_nan=False)
        out.write("\n")


def read_text(path):
    data = Path(path).read_bytes()
    return data.decode("utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8", errors="replace")


def verify_prepared():
    result = candidate.verify()
    binding, pins = result["ProfileBinding"], result["Pins"]
    names = load(ROOT / f"board/{TARGET}-sources.json")
    if (result.get("Target") != TARGET or type(names) is not list or len(names) != 117
            or len(set(names)) != 117 or set(names) != set(result["SourceSHA256"])
            or len(pins) != 128 or len(set(pins.values())) != 128
            or pins.get("cam_data[5]") != "AA23" or pins.get("uart_txd") != "C24"
            or "uart_rxd" in pins or binding.get("Revision") != "R1"
            or binding.get("DevelopmentOnly") is not True or binding.get("CalibrationAccepted") is not False
            or binding.get("HardwareReleaseAllowed") is not False or binding.get("GroupSeed") != 0x70595DD
            or binding.get("OneShot") is not True or binding.get("UartBaud") != 921600):
        raise ValueError("fixed R1/117-source/128-pin/AA23/seed/development contract differs")
    for name, digest in result["SourceSHA256"].items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT.resolve()) or sha(path) != digest:
            raise ValueError("source closure changed or escaped: " + name)
    return result


def validate_simulation():
    # This independent evidence reader checks R1 dark plus the narrowly
    # normalized R0 actual-input bridge. It never relabels the failed R0 report.
    import gamma_capture_k320_dev_evidence as evidence
    return evidence.verify_simulation()


def helper_hashes():
    names = ("tools/build_gamma_capture_k320_dev.py", "tools/prepare_gamma_capture_k320_dev.py",
             "tools/gamma_capture_k320_dev_evidence.py")
    return {name: sha(ROOT / name) for name in names}


def port_direction(port):
    if re.fullmatch(r"clk_27m|clk_p|clk_n|cam_pclk|cam_vsync|cam_href|cam_data\[\d+\]", port):
        return "input"
    if re.fullmatch(r"cam_rst_n|cam_scl|cam_sda|hd_scl|hd_sda|mem_dq\[\d+\]|mem_dqs(_n)?\[\d+\]", port):
        return "inout"
    return "output"


def validate_pins(path, expected):
    active = {}
    for line in read_text(path).splitlines():
        fields = [field.strip() for field in line.split("|")]
        if len(fields) >= 7 and fields[4]:
            pad, port, direction, enabled = fields[0], fields[4], fields[5], fields[6]
            if port in active or enabled != "YES" or direction != port_direction(port):
                raise ValueError("duplicate/inactive/wrong-direction routed port: " + port)
            active[port] = pad
    if (active != expected or len(active) != 128 or len(set(active.values())) != 128
            or active.get("cam_data[5]") != "AA23" or active.get("uart_txd") != "C24"):
        raise ValueError("routed fixed128 pin map/AA23/C24 differs")
    return active


def validate_artifacts(work, before, simulation):
    work = Path(work).resolve()
    if verify_prepared() != before or validate_simulation() != simulation:
        raise ValueError("R1 source or numerical evidence changed during build")
    text = read_text(work / "build-stdout.log") + "\n" + read_text(work / "build-stderr.log")
    if re.search(r"(?m)^\s*E:", text) or not re.search(
            r"(?m)^Executing : gen_bit_stream (?:-force_to_run )?-scbv \{High Voltage\} -unused_io_status UNUSED successfully\.\s*$", text):
        raise ValueError("PDS did not complete HighVoltage/UNUSED SRAM file generation")
    routed = work / "place_route" / f"{TARGET}_pnr.adf"
    hold = work / "place_route" / f"{TARGET}_timing_summary_after_hold_fix.txt"
    final = work / "report_timing" / f"{TARGET}.rtr"
    pin_report = work / "place_route" / f"{TARGET}_prr.prt"
    bit = work / "generate_bitstream" / f"{TARGET}.sbit"
    hold_text, final_text = read_text(hold), read_text(final)
    if not hold_text.strip() or not re.search(r"(?m)^Design Summary\s*:\s*All Constraints Met\.\s*$", final_text):
        raise ValueError("missing hold summary or final saved-DB timing did not meet all constraints")
    if str(routed).replace("\\", "/").lower() not in final_text.replace("\\", "/").lower():
        raise ValueError("final timing report does not identify this saved routed DB")
    if final.stat().st_mtime_ns < routed.stat().st_mtime_ns or bit.stat().st_mtime_ns < final.stat().st_mtime_ns:
        raise ValueError("final report predates routed DB or bitstream predates final timing")
    validate_pins(pin_report, before["Pins"])
    if bit.stat().st_size == 0:
        raise ValueError("empty named SRAM file")
    return {"Target": TARGET, "Revision": "R1", "Device": "PG2L100H", "Package": "FBG676",
            "SCBV": "High Voltage", "UnusedIO": "UNUSED", "Bitstream": str(bit), "SHA256": sha(bit).upper(),
            "TimingReport": str(final), "TimingSHA256": sha(final).upper(),
            "AfterHoldTimingReport": str(hold), "AfterHoldTimingSHA256": sha(hold).upper(),
            "AfterHoldSummaryAllMet": bool(re.search(r"(?m)^Design Summary\s*:\s*All Constraints Met\.\s*$", hold_text)),
            "FinalRoutedDatabase": str(routed), "FinalRoutedDatabaseSHA256": sha(routed).upper(),
            "PinReport": str(pin_report), "PinReportSHA256": sha(pin_report).upper(), "RoutedPinCount": 128,
            "SourceSHA256": before["SourceSHA256"], "SourceSHA256After": verify_prepared()["SourceSHA256"],
            "ProfileBinding": before["ProfileBinding"], "SimulationEvidence": simulation,
            "BuildHelperSHA256": helper_hashes(), "ProcessExitCode": 0, "HardwareAccessed": False,
            "DevelopmentOnly": True, "CalibrationAccepted": False, "HardwareReleaseAllowed": False,
            "BuildValidation": "native exit0; final saved-DB timing after hold fix; exact128 routed pins and fresh SRAM file",
            "Limits": candidate.LIMITS}


def stop_owned(child, work):
    if child.poll() is not None:
        return
    if os.name == "nt":
        with (Path(work) / "owned-stop.log").open("xb") as out:
            subprocess.run([str(Path(os.environ["SystemRoot"]) / "System32/taskkill.exe"),
                            "/PID", str(child.pid), "/T", "/F"], stdout=out, stderr=subprocess.STDOUT,
                           timeout=20, check=False, creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        child.kill()
    child.wait(timeout=20)


def run_build(workdir, *, execute=False, timeout_seconds=7200, pds_bin=None):
    if (type(execute) is not bool or type(timeout_seconds) not in (int, float)
            or not math.isfinite(timeout_seconds) or not 60 <= timeout_seconds <= 7200):
        raise ValueError("explicit execute and finite60..7200s offline bound required")
    work = Path(workdir).resolve()
    if (not APPROVED.is_dir() or work == APPROVED.resolve() or not work.is_relative_to(APPROVED.resolve())
            or not work.parent.is_dir() or work.exists()):
        raise ValueError("new output below existing approved scratch required; no overwrite")
    before, simulation = verify_prepared(), validate_simulation()
    config_path = ROOT.parent / "team-config.local.json"
    config = load(config_path) if config_path.is_file() else {}
    pds = Path(pds_bin or os.environ.get("FPGA_PDS_BIN") or config.get("pds_bin") or r"E:\Pango\PDS_2022.2-SP6.4\bin").resolve()
    if execute and not (pds / "pds_shell.exe").is_file():
        raise ValueError("existing PDS pds_shell.exe required")
    command = [str(pds / "pds_shell.exe"), "-file", str(ROOT / f"board/build-{TARGET}.tcl"),
               "-work_dir", str(work), "-project_name", TARGET]
    plan = {"Target": TARGET, "ExecuteBuild": execute, "HardwareAccessed": False,
            "Operation": "offline_compile_route_sram_file_only", "NoFlashOrProgrammingOperation": True,
            "SourceSHA256": before["SourceSHA256"], "SourceCount": 117, "OutputDirectory": str(work),
            "Command": command, "TimeoutSeconds": timeout_seconds, "SimulationEvidence": simulation,
            "ProfileBinding": before["ProfileBinding"], "BuildHelperSHA256": helper_hashes(),
            "DevelopmentOnly": True, "CalibrationAccepted": False, "HardwareReleaseAllowed": False}
    work.mkdir(exist_ok=False)
    write_new(work / "plan.json", plan)
    if not execute:
        return plan
    child = None
    result = {"Target": TARGET, "Passed": False, "HardwareAccessed": False,
              "StartedUtc": datetime.now(timezone.utc).isoformat(), "SourceSHA256": before["SourceSHA256"],
              "ProcessExitCode": None, "TimedOut": False, "OutputDirectory": str(work)}
    try:
        flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
        with (work / "build-stdout.log").open("xb") as out, (work / "build-stderr.log").open("xb") as err:
            child = subprocess.Popen(command, cwd=work, stdout=out, stderr=err, **flags)
            result["OwnedPID"] = child.pid
            try:
                result["ProcessExitCode"] = child.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                result["TimedOut"] = True
                stop_owned(child, work)
                raise ValueError("owned offline PDS process exceeded explicit bound")
        if type(result["ProcessExitCode"]) is not int or result["ProcessExitCode"] != 0:
            raise ValueError("native PDS exit nonzero or unavailable")
        if helper_hashes() != plan["BuildHelperSHA256"]:
            raise ValueError("build helpers changed during offline build")
        manifest = validate_artifacts(work, before, simulation)
        write_new(work / "validated-build.json", manifest)
        result.update(Passed=True, ValidatedBuild=str(work / "validated-build.json"),
                      ValidatedBuildSHA256=sha(work / "validated-build.json"))
    except (Exception, KeyboardInterrupt) as exc:
        result["Error"] = type(exc).__name__ + ": " + str(exc)
    finally:
        if child is not None and child.poll() is None:
            try:
                stop_owned(child, work)
            except Exception as exc:
                result["CleanupError"] = str(exc)
                result["Passed"] = False
        result["SourceSHA256After"] = {n: sha(ROOT / n) if (ROOT / n).is_file() else None for n in before["SourceSHA256"]}
        if result["SourceSHA256After"] != before["SourceSHA256"]:
            result.update(Passed=False, SourceDrift=True)
        result["EndedUtc"] = datetime.now(timezone.utc).isoformat()
        write_new(work / "build-result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--pds-bin", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=7200)
    parser.add_argument("--execute-build", action="store_true")
    args = parser.parse_args()
    result = run_build(args.workdir, execute=args.execute_build, pds_bin=args.pds_bin, timeout_seconds=args.timeout_seconds)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if not args.execute_build or result["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
