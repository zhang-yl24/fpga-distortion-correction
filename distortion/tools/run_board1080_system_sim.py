"""Bounded actual-input/DDR/real-pixel-scan RTL integration; no CAD/device IO.

This runner only uses existing independent CPU fixtures. It never creates a
hardware plan, regenerates optical parameters, or substitutes DDR readback
completion for a display pixel scan. Root serializes all RTL executions.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json
import re
import time

import run_hdmi1080_continuous_sim as fixtures

ROOT = fixtures.ROOT
BASE = ROOT / "build/offline-20261024/board1080-integration-20261027-a"
TOP = "tb_board1080_system"
SNAPSHOT = "board1080_system"
REPORT = "board1080-system-simulation.json"
MARKER = "PASS board1080 system:"
COMPILE = tuple("tests/tb_board1080_system.sv" if name == "tests/tb_hdmi1080_continuous.sv" else name
                for name in fixtures.COMPILE) + (
    "rtl/experimental/ddr_video_output_1080_board.v",
    "rtl/experimental/hdmi1080_video_system.v",
)
HEADERS = fixtures.previous.base.HEADERS
HELPERS = (*fixtures.HELPERS, "tools/run_board1080_system_sim.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON " + value)))


def child(path):
    path = Path(path).resolve()
    if not path.is_dir() or path == BASE.resolve() or not path.is_relative_to(BASE.resolve()):
        raise ValueError("existing child of approved board1080 integration scratch required")
    return path


def _hash_result_files(work):
    return {path.name: sha(path) for name in ("summary.json", "frames.csv", "scans.csv", "events.csv")
            if (path := work/name).is_file()}


def _rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _positive(value):
    return type(value) is int and value > 0


def run(args):
    work = child(args.workdir)
    if any(work.iterdir()):
        raise ValueError("fresh empty work directory required; existing evidence is never overwritten")
    maximum = (300 if args.mode == "small" else 7200) if args.maximum_seconds is None else args.maximum_seconds
    ceiling = 300 if args.mode == "small" else 7200
    if type(maximum) is not int or not 1 <= maximum <= ceiling:
        raise ValueError(f"{args.mode} wall-clock budget must be in 1..{ceiling} seconds")
    sequence, inputs, copied = fixtures.fixture_sequence(args.sequence_dir, args.mode)
    sources = {name: sha(ROOT/name) for name in (*COMPILE, *HEADERS, *HELPERS)}
    for name, expected in fixtures.previous.FROZEN.items():
        if sources.get(name) != expected:
            raise ValueError("existing frozen input/cache revision differs: " + name)
    small_path = None
    if args.mode == "native":
        if args.small_report is None:
            raise ValueError("native requires this same-source completed small system report")
        small_path = Path(args.small_report).resolve()
        small = load(small_path)
        if (not small_path.is_relative_to(BASE.resolve()) or small.get("Mode") != "small" or
                small.get("Passed") is not True or small.get("FunctionalPassed") is not True or
                small.get("SourceSHA256") != sources or small.get("SourceSHA256After") != sources):
            raise ValueError("small system result did not pass or its exact source closure changed")
        commands = small.get("Commands")
        if not isinstance(commands, list) or [item.get("Stage") for item in commands] != ["compile", "elaborate", "simulate"] or any(item.get("ReturnCode") != 0 for item in commands):
            raise ValueError("small system requires all three completed native stages")
        if not {"compile-stdout.log", "elaborate-stdout.log", "simulation.log"}.issubset(small.get("LogSHA256", {})) or not {"summary.json", "frames.csv", "scans.csv", "events.csv"}.issubset(small.get("ResultFiles", {})):
            raise ValueError("small gate logs/result tables are incomplete")
        small_summary = small.get("Summary", {})
        if small_summary.get("fault_isolation_passed") is not True or small_summary.get("release_edge_fault_isolated") is not True or small_summary.get("common_reset_recovered") is not True:
            raise ValueError("small fault/common-reset evidence is missing")
        if any(not _positive(small_summary.get(name)) for name in ("forced_result_aw_hold_cycles", "forced_display_ar_hold_cycles", "forced_write_dual_clients_seen", "forced_read_dual_clients_seen")):
            raise ValueError("small explicit dual-client coverage was not exercised")
        for name, expected in small.get("LogSHA256", {}).items():
            if sha(small_path.parent/name) != expected:
                raise ValueError("small system log changed")
        for name, expected in small.get("ResultFiles", {}).items():
            if sha(small_path.parent/name) != expected:
                raise ValueError("small system result file changed")
    if args.mode == "small":
        ht, vt, x0, y0, hs, vs, cycles = 80, 40, 10, 3, 4, 1, 5000000
    else:
        ht, vt, x0, y0, hs, vs, cycles = 2200, 1125, 192, 41, 44, 5, 80000000
    copied["timing.vh"] = (
        f"localparam integer SIM_HT={ht},SIM_VT={vt},SIM_X0={x0},SIM_Y0={y0},SIM_HS={hs},SIM_VS={vs};\n"
        f"localparam integer SIM_FRAMES=8,SIM_MAX_CYCLES={cycles},SIM_FAULT_PHASE={1 if args.mode=='small' else 0};\n"
        "localparam integer SIM_OUTPUT_PHASE_PS=1733;\n").encode("ascii")
    report = {"Marker": "FPGA-1031-BOARD1080-INTEGRATION-ONE", "Mode": args.mode,
              "Passed": False, "FunctionalPassed": False, "Digital30fpsBudgetMet": False,
              "SyntheticInput": True, "DevelopmentOnly": True, "HardwareAccessed": False, "PDSAccessed": False,
              "GateState": {key: False for key in ("HardwareReleaseAllowed", "CalibrationAccepted",
                                                   "NewLensCorrectionVerified", "PreBitGateExecutionProven")},
              "StartedUtc": datetime.now(timezone.utc).isoformat(), "MaximumSeconds": maximum,
              "MaximumSystemCycles": cycles, "SourceSHA256": sources, "InputSHA256": inputs,
              "SequenceMetadata": str(Path(args.sequence_dir).resolve()/"sequence.json"),
              "FrameIDs": list(range(1, 9)), "TextureIndices": [i % 3 for i in range(8)],
              "SourceBankExpected": [i % 2 for i in range(8)], "WarmupIDs": [1, 2], "SteadyIDs": [3, 4, 5, 6], "TailIDs": [7, 8],
              "Width": sequence["Width"], "Height": sequence["Height"], "InputPixelClockHz": 74250000,
              "OutputPixelClockHz": 74250000, "OutputPhaseOffsetPs": 1733, "SystemClockHz": 125000000,
              "PixelClockHalfPeriodPs": "2000000/297; separate remainder accumulators, independently phased",
              "InputNativeRaster": {"HTotal": ht, "VTotal": vt, "X0": x0, "Y0": y0, "HS": hs, "VS": vs},
              "InputDDRPreloaded": False, "RealOutputAsyncFIFO": True, "ActualDERGBScanAssertionsEnabled": True,
              "ActualDERGBScanned": False, "LongTermSteadyStateProven": False,
              "SmallOnlyForcedSelectedAddressCoverage": args.mode == "small",
              "SmallPerformanceComparableToNaturalSmall": False,
              "NativeReadyStallStimulusChanged": False,
              "DisplayDDRReadbackOnly": False, "SmallGate": None if small_path is None else {"Path": str(small_path), "SHA256": sha(small_path)},
              "BudgetBasis": "Native provisional bound: prior three-frame DDR-readback run ~1473s; eight/three scaling ~3928s before real scan/FIFO overhead, so explicit 7200s ceiling and 80M system cycles. Small timing is not a native FPS test.",
              "Commands": []}
    deadline = time.monotonic() + maximum
    try:
        for name, data in copied.items():
            with (work/name).open("xb") as stream:
                stream.write(data)
        report["FixtureSHA256"] = {name: sha(work/name) for name in copied}
        bin_dir = Path("E:/Vivado/Vivado/2017.4/bin")
        for executable, argv, stage in (
                ("xvlog.bat", ["--sv", *[str(ROOT/name) for name in COMPILE]], "compile"),
                ("xelab.bat", [TOP, "-s", SNAPSHOT], "elaborate"),
                ("xsim.bat", [SNAPSHOT, "-runall", "-log", "simulation.log"], "simulate")):
            command = {"Stage": stage, "NativeArgv": [str(bin_dir/executable), *argv], "ReturnCode": None}
            report["Commands"].append(command)
            try:
                fixtures.previous.base.tool(bin_dir, executable, argv, work, deadline, stage)
                command["ReturnCode"] = 0
            except (Exception, KeyboardInterrupt) as error:
                match = re.search(r"failed, exit=(-?\d+)", str(error))
                if match:
                    command["ReturnCode"] = int(match.group(1))
                command["Error"] = str(error)
                raise
        log = (work/"simulation.log").read_text(encoding="utf-8", errors="replace")
        if MARKER not in log or re.search(r"(?im)^\s*(?:fatal|error):", log):
            raise ValueError("real-scan system completion marker absent or RTL fatal/error")
        summary = load(work/"summary.json")
        report["Summary"] = summary
        n = sequence["Width"]*sequence["Height"]
        expected = {"passed": True, "frames_input": 8, "frames_committed": 8, "frames_processed": 8,
                    "frames_published": 8, "frames_unique_scanned": 8, "unique_scanned_pixels": 8*n,
                    "source_beats": 8*n//16, "result_beats": 8*n//16,
                    "dropped_frames": 0, "overflow_frames": 0, "no_free_frames": 0,
                    "output_underflows": 0, "output_crc_mismatches": 0, "final_drain": True}
        if any(type(summary.get(key)) is not type(value) or summary[key] != value for key, value in expected.items()):
            raise ValueError("all-eight input/real-scan/CRC/drop/final-drain contract failed")
        if args.mode == "small" and (summary.get("fault_isolation_passed") is not True or summary.get("release_edge_fault_isolated") is not True or summary.get("common_reset_recovered") is not True):
            raise ValueError("small system must isolate a mid-frame fault and recover by common reset")
        missing = [name for name in ("aw_stall", "w_stall", "physical_ar_stall", "cache_output_stall", "core_output_stall",
                                    "tone_stall", "write_contention", "read_contention") if not _positive(summary.get(name))]
        if args.mode == "small":
            missing.extend(name for name in ("forced_result_aw_hold_cycles", "forced_display_ar_hold_cycles", "forced_write_dual_clients_seen", "forced_read_dual_clients_seen") if not _positive(summary.get(name)))
        elif any(summary.get(name) != 0 for name in ("forced_result_aw_hold_cycles", "forced_display_ar_hold_cycles", "forced_write_dual_clients_seen", "forced_read_dual_clients_seen")):
            raise ValueError("native ready/valid stimulus must not use the small-only forced holds")
        rows = _rows(work/"frames.csv")
        if len(rows) != 8 or [int(row["frame_id"]) for row in rows] != list(range(1, 9)):
            raise ValueError("all eight input IDs must remain in the result; no dropped/warmup rows may be removed")
        parsed = []
        for index, row in enumerate(rows):
            values = {key: value if "crc" in key else int(value) for key, value in row.items()}
            expected_frame = sequence["Frames"][index % 3]
            if values["source_crc32"].upper() != expected_frame["SourcePixelCRC32"] or values["scan_crc32"].upper() != expected_frame["ExpectedPixelCRC32"]:
                raise ValueError("per-ID source or actual-pixel-scan CRC differs from CPU golden")
            if not (values["input_first_ps"] < values["input_last_ps"] < values["commit_ps"] < values["source_release_ps"] <= values["publish_ps"] <= values["scan_start_ps"] < values["scan_last_pixel_ps"] <= values["scan_done_ps"]):
                raise ValueError("DMA/core/publication/actual-scan event order differs")
            values["commit_to_release_cycles"] = (values["source_release_ps"]-values["commit_ps"])/8000
            values["input_to_last_scanned_pixel_ms"] = (values["scan_last_pixel_ps"]-values["input_first_ps"])/1e9
            values["processing_lag_ps"] = values["source_release_ps"]-values["input_last_ps"]
            values["output_lag_ps"] = values["scan_last_pixel_ps"]-values["input_last_ps"]
            if index:
                values["scan_last_interval_ps"] = values["scan_last_pixel_ps"]-parsed[-1]["scan_last_pixel_ps"]
                values["output_lag_change_ps"] = values["output_lag_ps"]-parsed[-1]["output_lag_ps"]
            if index in (2, 3, 4, 5):
                if values.get("future_capture_write_overlap_cycles", 0) <= 0 or values["publish_ps"] >= int(rows[-1]["input_last_ps"]) or values["scan_start_ps"] >= int(rows[-1]["input_last_ps"]):
                    missing.append("steady ID"+str(index+1)+" must publish/scan with later actual capture load")
            parsed.append(values)
        report.update(FunctionalPassed=True, ActualDERGBScanned=True, Frames=parsed, CoverageFailures=missing,
                      PassLines=[line for line in log.splitlines() if line.startswith("PASS")])
        if args.mode == "native":
            period = 1e12/30
            if any(abs(parsed[i]["input_first_ps"]-parsed[i-1]["input_first_ps"]-period) > 2 for i in range(1, 8)):
                raise ValueError("native input cadence was throttled or differs from exact 30fps")
            steady = parsed[2:6]
            intervals = [steady[i]["scan_last_pixel_ps"]-steady[i-1]["scan_last_pixel_ps"] for i in range(1, 4)]
            report["SteadyActualScanIntervalsPs"] = intervals
            report["SteadyScanIntervalJitterPs"] = max(intervals)-min(intervals)
            report["SteadyUniqueScanFps"] = 3e12/(steady[-1]["scan_last_pixel_ps"]-steady[0]["scan_last_pixel_ps"])
            report["Digital30fpsBudgetMet"] = all(row["commit_to_release_cycles"] <= 125000000/30 for row in steady) and all(d <= period+2 for d in intervals)
        report["Passed"] = not missing and (args.mode == "small" or report["Digital30fpsBudgetMet"])
        if not report["Passed"]:
            report["Error"] = "required contention/steady later-load coverage or active-system 30fps digital budget failed"
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = type(error).__name__+": "+str(error)
    finally:
        report["SourceSHA256After"] = {name: sha(ROOT/name) for name in sources}
        report["InputSHA256After"] = {name: sha(name) for name in inputs}
        report["FixtureSHA256After"] = {name: sha(work/name) if (work/name).is_file() else None for name in copied}
        if (report["SourceSHA256After"] != sources or report["InputSHA256After"] != inputs or
                report.get("FixtureSHA256") != report["FixtureSHA256After"]):
            report.update(Passed=False, FunctionalPassed=False, SourceOrFixtureDrift=True)
        report["LogSHA256"] = {path.name: sha(path) for path in work.glob("*.log")}
        report["ResultFiles"] = _hash_result_files(work)
        for name in ("frames.csv", "scans.csv", "events.csv"):
            if (work/name).is_file():
                try:
                    report["Observed_"+name.replace(".", "_")] = _rows(work/name)
                except (OSError, csv.Error) as error:
                    report["PartialRowsReadError_"+name] = str(error)
        # Keep all eight planned IDs even on an early failure. Missing rows are
        # explicitly unobserved, never removed to manufacture a passing window.
        frame_rows = {int(row["frame_id"]): row for row in report.get("Observed_frames_csv", []) if row.get("frame_id", "").isdigit()}
        event_rows = report.get("Observed_events_csv", [])
        report["AllEightInputDispositions"] = [
            {"FrameID": frame, "Window": "warmup" if frame <= 2 else "steady" if frame <= 6 else "tail",
             "Status": "COMPLETE_ROW_RECORDED" if frame in frame_rows else "NO_COMPLETE_ROW_RECORDED",
             "FrameRow": frame_rows.get(frame),
             "ObservedNormalPhaseEvents": [row for row in event_rows if row.get("phase") == "0" and row.get("frame_id") == str(frame)]}
            for frame in range(1, 9)]
        report["EndedUtc"] = datetime.now(timezone.utc).isoformat()
        report["Limits"] = "Offline normalized pixel clocks and DDR UI behavior model only; actual DE/RGB scanned through real async FIFO, not reader.done acceptance. No physical PHY, MS7200/MS7210 lock/support, I2C, DDR bandwidth, pin/timing/resource/bitstream, optical or hardware-FPS acceptance. All eight IDs and partial failed-run records are retained."
        with (work/REPORT).open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False); stream.write("\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("small", "native"), required=True)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--sequence-dir", type=Path, required=True)
    parser.add_argument("--small-report", type=Path)
    parser.add_argument("--maximum-seconds", type=int)
    args = parser.parse_args(argv)
    try:
        report = run(args)
    except (ValueError, KeyError, OSError) as error:
        parser.exit(1, str(error)+"\n")
    print(json.dumps({"Report": str(args.workdir.resolve()/REPORT), "Passed": report["Passed"],
                      "FunctionalPassed": report["FunctionalPassed"], "Digital30fpsBudgetMet": report["Digital30fpsBudgetMet"],
                      "Commands": report["Commands"], "Error": report.get("Error")}, indent=2))
    return 0 if report["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
