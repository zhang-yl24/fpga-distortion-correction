"""Full 1280x720 DVP/DMA/arbiter simulation; no PDS or hardware access.

Four complete source frames exercise both banks and reuse, then compare every
DDR word and committed CRC with an independent Python RGB565 oracle. A malformed
short frame and a deliberately stalled overflowing frame must be quarantined.
The sensor and DDR are models; this is not a board throughput measurement.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import zlib

from simulation_tools import resolve_vivado_bin

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "work/camera720-capture-sim"
TOP = "tb_camera720_capture"
SOURCES = (
    "rtl/video_async_fifo.v",
    "rtl/ddr_write_arbiter.v",
    "rtl/experimental/dvp_rgb565_capture_cdc.v",
    "rtl/experimental/camera_vga_input_dma.v",
    "rtl/experimental/camera_vga_input_write_link.v",
    "tests/tb_camera720_capture.sv",
)
HELPERS = ("tools/run_camera720_capture_sim.py", "tools/simulation_tools.py")
WIDTH, HEIGHT, BEATS = 1280, 720, 57600
GOOD_IDS = (1, 2, 5, 6)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_bytes(frame_id: int) -> bytes:
    result = bytearray(WIDTH * HEIGHT * 2)
    for y in range(HEIGHT):
        for x in range(WIDTH):
            index = y * WIDTH + x
            value = ((x * 73 + y * 151 + frame_id * 0x1234)
                     ^ ((x << 7) | (y >> 1)) ^ (frame_id << (index % 7))) & 0xFFFF
            result[2 * index] = value & 255
            result[2 * index + 1] = value >> 8
    return bytes(result)


def verify_results(work: Path) -> dict:
    summary = json.loads((work / "summary.json").read_text(encoding="ascii"))
    exact = {"passed": True, "width": WIDTH, "height": HEIGHT, "pclk_hz": 48000000,
             "core_hz": 125000000, "hts_pixels": 1892, "vts_lines": 740,
             "bank_stride_ui": 1048576, "ui_bytes": 4, "frame_beats": BEATS,
             "frame_bytes": 1843200, "frame_ui": 460800, "good_frames": 4,
             "bad_frames": 2, "overflow_frames": 1, "bank_reuses": 4,
             "final_bursts": 4, "complete_drain": True}
    if any(type(summary.get(k)) is not type(v) or summary[k] != v for k, v in exact.items()):
        raise ValueError("required full-resolution, fault/recovery or address coverage differs")
    for key in ("result_bursts", "contention_cycles", "aw_stall_cycles", "w_stall_cycles",
                "zero_latency_first_beats", "overflow_stall_cycles"):
        if not isinstance(summary.get(key), int) or summary[key] <= 0:
            raise ValueError("required DDR stall/arbitration coverage absent: " + key)
    peaks = summary.get("fifo_peaks")
    if (not isinstance(peaks, list) or len(peaks) != 6 or peaks[3] != 64
            or any(type(v) is not int or not 0 < v <= 64 for v in peaks)
            or any(peaks[i - 1] >= 64 for i in GOOD_IDS)):
        raise ValueError("FIFO normal/overflow high-water coverage differs")
    expected = {frame_id: expected_bytes(frame_id) for frame_id in range(1, 7)}
    observed = {frame_id: bytearray() for frame_id in range(1, 7)}
    with (work / "ddr-source-words.csv").open(encoding="ascii", newline="") as stream:
        for record in csv.DictReader(stream):
            frame_id, bank, index = (int(record[k]) for k in ("frame_id", "bank", "word"))
            if frame_id not in observed or bank != (frame_id - 1) % 2:
                raise ValueError("source bank/id mismatch")
            if index != len(observed[frame_id]) // 32 or index >= BEATS:
                raise ValueError("source address duplicated, skipped or exceeds frame")
            if not re.fullmatch(r"[0-9a-fA-F]{64}", record["data"]):
                raise ValueError("source data is not a complete 256-bit word")
            actual = int(record["data"], 16).to_bytes(32, "little")
            if actual != expected[frame_id][32 * index:32 * (index + 1)]:
                raise ValueError(f"independent pixel/order mismatch: frame {frame_id}, word {index}")
            observed[frame_id].extend(actual)
    with (work / "commits.csv").open(encoding="ascii", newline="") as stream:
        commits = list(csv.DictReader(stream))
    if [int(row["frame_id"]) for row in commits] != list(GOOD_IDS):
        raise ValueError("bad frame committed, recovery missing or complete frame duplicated")
    details = []
    for record in commits:
        frame_id = int(record["frame_id"])
        actual = observed[frame_id]
        crc = zlib.crc32(expected[frame_id])
        if (actual != expected[frame_id] or int(record["bank"]) != (frame_id - 1) % 2
                or int(record["pixels"]) != WIDTH * HEIGHT or int(record["beats"]) != BEATS
                or int(record["crc"], 16) != crc or zlib.crc32(actual) != crc):
            raise ValueError("committed count/CRC or complete DDR frame mismatch")
        details.append({"FrameID": frame_id, "Bank": int(record["bank"]), "Beats": BEATS,
                        "Pixels": WIDTH * HEIGHT, "CRC32": f"{crc:08x}",
                        "BytesSHA256": hashlib.sha256(actual).hexdigest()})
    with (work / "drops.csv").open(encoding="ascii", newline="") as stream:
        drops = list(csv.DictReader(stream))
    if ([int(r["frame_id"]) for r in drops] != [3, 4]
            or int(drops[0]["fault"], 16) & 0x41 != 0x41 or not int(drops[1]["fault"], 16) & 8):
        raise ValueError("malformed/overflow frame quarantine missing")
    for record in drops:
        frame_id = int(record["frame_id"])
        if (len(observed[frame_id]) // 32 != int(record["written_beats"])
                or not 0 < len(observed[frame_id]) < WIDTH * HEIGHT * 2):
            raise ValueError("rejected transaction partial DDR prefix/drain differs")
    return {"Summary": summary, "IndependentFrames": details,
            "IndependentComparedDDRBeats": sum(len(b) // 32 for b in observed.values()),
            "IndependentComparedGoodPixels": len(GOOD_IDS) * WIDTH * HEIGHT}


def native(bin_dir: Path, executable: str, arguments: list[str], work: Path,
           deadline: float, stage: str) -> None:
    tokens = [str(bin_dir / executable), *arguments]
    comspec = os.environ.get("ComSpec", "cmd.exe")
    if not Path(tokens[0]).is_file() or any(re.search(r'["\r\n&|<>^%!]', t) for t in [comspec, *tokens]):
        raise ValueError("invalid simulation tool or fixed arguments")
    command = '"' + comspec + '" /d /s /c "' + " ".join('"' + t + '"' for t in tokens) + '"'
    process = None
    with (work / (stage + "-stdout.log")).open("xb") as out, (work / (stage + "-stderr.log")).open("xb") as err:
        try:
            process = subprocess.Popen(command, cwd=work, stdout=out, stderr=err,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("whole simulation deadline exhausted")
            code = process.wait(timeout=remaining)
            if code:
                raise RuntimeError(f"{executable} failed, exit={code}; inspect {stage}-stdout.log")
        finally:
            if process is not None and process.poll() is None:
                # Terminate only this runner's owned process tree on timeout.
                result = subprocess.run([str(Path(os.environ["SystemRoot"]) / "System32/taskkill.exe"),
                                         "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=15)
                (work / (stage + "-owned-stop.log")).write_bytes(result.stdout + result.stderr)
                process.wait(timeout=15)


def run(work: Path, maximum_seconds: int) -> int:
    supplied = work.absolute()
    work = supplied.resolve()
    if supplied != work or work.parent != BASE.resolve() or work.exists():
        raise ValueError("use a new canonical direct child of distortion/work/camera720-capture-sim")
    if not 30 <= maximum_seconds <= 1800:
        raise ValueError("whole-run deadline must be 30..1800 seconds")
    work.mkdir(parents=True, exist_ok=False)
    hashes = {name: sha(ROOT / name) for name in (*SOURCES, *HELPERS)}
    report = {"Schema": "camera720-ingress-simulation-v1", "Passed": False,
              "StartedUTC": datetime.now(timezone.utc).isoformat(), "SourceSHA256": hashes,
              "Commands": [], "HardwareAccessed": False, "PDSAccessed": False,
              "HardwareReleaseAllowed": False, "RTLResultUsedForGolden": False,
              "PhysicalIPExecuted": False, "PhysicalCameraValidated": False,
              "Limits": "Synthetic full-size 1280x720 DVP at 48 MHz with HTS 1892 pixels (3784 byte clocks), "
                        "VTS 740, 125 MHz core, and modeled DDR arbitration/stalls. Four complete frames "
                        "and two shortened fault frames; deliberate inter-frame reservation pauses. "
                        "Real capture/FIFO/DMA/write arbiter only; background result data is modeled. "
                        "No sensor SCCB, electrical/CDC timing, bank-manager/remapper/scan concurrency, "
                        "720p optical calibration, board throughput or measured frame-rate claim."}
    start = time.monotonic()
    try:
        bin_dir = resolve_vivado_bin(ROOT.parent)
        report["VivadoBin"] = str(bin_dir)
        for executable, arguments, stage in (
            ("xvlog.bat", ["--sv", *[str(ROOT / name) for name in SOURCES]], "compile"),
            ("xelab.bat", [TOP, "-s", "camera720_capture", "--timescale", "1ps/1ps"], "elaborate"),
            ("xsim.bat", ["camera720_capture", "-runall", "-log", "simulation.log"], "simulate"),
        ):
            command = {"Stage": stage, "NativeArgv": [str(bin_dir / executable), *arguments], "ReturnCode": None}
            report["Commands"].append(command)
            native(bin_dir, executable, arguments, work, start + maximum_seconds, stage)
            command["ReturnCode"] = 0
        log = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        if (not re.search(r"(?m)^PASS camera720 capture:", log) or "$finish called" not in log
                or re.search(r"(?im)^\s*(?:fatal|error):", log)):
            raise ValueError("complete native 720p capture pass marker missing")
        report.update(verify_results(work), Passed=True)
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = type(error).__name__ + ": " + str(error)
    finally:
        report["SourceSHA256After"] = {name: sha(ROOT / name) for name in hashes}
        if report["SourceSHA256After"] != hashes:
            report.update(Passed=False, SourceDrift=True)
        report["ElapsedSeconds"] = round(time.monotonic() - start, 3)
        report["LogSHA256"] = {p.name: sha(p) for p in work.glob("*.log")}
        report["ResultSHA256"] = {p.name: sha(p) for p in work.iterdir()
                                  if p.name in ("summary.json", "commits.csv", "drops.csv", "ddr-source-words.csv")}
        (work / "camera720-capture-simulation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"Passed": report["Passed"], "Error": report.get("Error"),
                      "Report": str(work / "camera720-capture-simulation.json")}))
    return 0 if report["Passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=int, default=900)
    arguments = parser.parse_args()
    return run(arguments.workdir, arguments.maximum_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
