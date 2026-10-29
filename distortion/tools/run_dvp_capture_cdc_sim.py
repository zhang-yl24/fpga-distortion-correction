"""Simulate the independent DVP capture adapter; no PDS or hardware access."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import time
import zlib

from run_gamma_pipeline_d5_sim import tool
from simulation_tools import resolve_vivado_bin


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "build/dvp-capture-cdc"
TOP = "tb_dvp_rgb565_capture_cdc"
SOURCES = (
    "rtl/video_async_fifo.v",
    "rtl/experimental/dvp_rgb565_capture_cdc.v",
    "tests/tb_dvp_rgb565_capture_cdc.sv",
)
HELPERS = (
    "tools/run_dvp_capture_cdc_sim.py",
    "tools/run_gamma_pipeline_d5_sim.py",
    "tools/simulation_tools.py",
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_pixels(work, log):
    """Check the emitted FIFO words against a separate byte/CRC oracle."""
    lines = (work / "dvp-good-words.hex").read_text(encoding="ascii").splitlines()
    if len(lines) != 8 or any(not re.fullmatch(r"[0-9a-fA-F]{64}", s) for s in lines):
        raise ValueError("expected eight complete 256-bit FIFO words")
    actual = b"".join(int(s, 16).to_bytes(32, "little") for s in lines)
    expected = b"".join(((0x1234 + i * 0x0103 + 0x0711) & 0xFFFF).to_bytes(2, "little")
                        for i in range(128))
    crc = zlib.crc32(expected)
    records = re.findall(r"(?m)^DVP_CDC_GOOD pixels=(\d+) crc=([0-9a-fA-F]{8}) bank=(\d+) id=([0-9a-fA-F]{8})\s*$", log)
    if actual != expected or len(records) != 1:
        raise ValueError("FIFO pixel ordering, bytes, count or completion record differs")
    pixels, crc_text, bank, frame_id = records[0]
    if (int(pixels), int(crc_text, 16), int(bank), int(frame_id, 16)) != (128, crc, 1, 0x10203040):
        raise ValueError("frame count/CRC/bank/ID does not match the independent oracle")
    return {"Pixels": 128, "FIFOBeats": 8, "CRC32": f"{crc:08x}",
            "FrameID": "10203040", "Bank": 1, "BytesSHA256": hashlib.sha256(actual).hexdigest()}


def run(work, maximum_seconds=180):
    work = Path(work).resolve()
    if work.parent != BASE.resolve() or not work.is_dir() or any(work.iterdir()):
        raise ValueError("use a fresh empty directory directly under distortion/build/dvp-capture-cdc")
    if not 1 <= maximum_seconds <= 300:
        raise ValueError("maximum-seconds must be in 1..300")
    inputs = {name: sha(ROOT / name) for name in (*SOURCES, *HELPERS)}
    bin_dir = resolve_vivado_bin(ROOT.parent)
    report = {"Schema": "dvp-capture-cdc-simulation-v1", "Passed": False,
              "StartedUTC": datetime.now(timezone.utc).isoformat(),
              "SourceSHA256": inputs, "VivadoBin": str(bin_dir), "Commands": [],
              "HardwareAccessed": False, "PDSAccessed": False,
              "HardwareReleaseAllowed": False,
              "Limits": "Synthetic DVP bytes, real adapter/FIFO RTL and software CRC oracle only. "
                        "No sensor initialization, DDR DMA integration, lens correction, physical timing, "
                        "camera frame-rate measurement or independent clock-stop recovery is verified."}
    deadline = time.monotonic() + maximum_seconds
    try:
        for executable, arguments, stage in (
            ("xvlog.bat", ["--sv", *[str(ROOT / name) for name in SOURCES]], "compile"),
            ("xelab.bat", [TOP, "-s", "dvp_capture_cdc"], "elaborate"),
            ("xsim.bat", ["dvp_capture_cdc", "-runall", "-log", "simulation.log"], "simulate"),
        ):
            record = {"Stage": stage, "Argv": [str(bin_dir / executable), *arguments], "ReturnCode": None}
            report["Commands"].append(record)
            tool(bin_dir, executable, arguments, work, deadline, stage)
            record["ReturnCode"] = 0
        log = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        if not re.search(r"(?m)^PASS dvp_rgb565_capture_cdc\b", log) or re.search(r"(?im)^\s*(?:fatal|error):", log):
            raise ValueError("testbench did not finish successfully")
        report["IndependentPixelCheck"] = verify_pixels(work, log)
        report["CaseLines"] = [s for s in log.splitlines() if s.startswith("DVP_CDC_CASE ")]
        report["Passed"] = True
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = f"{type(error).__name__}: {error}"
    finally:
        after = {name: sha(ROOT / name) for name in inputs}
        if after != inputs:
            report.update(Passed=False, SourceDrift=True)
        report["SourceSHA256After"] = after
        report["LogSHA256"] = {p.name: sha(p) for p in work.glob("*.log")}
        report["DataSHA256"] = {p.name: sha(p) for p in work.glob("*.hex")}
        report["EndedUTC"] = datetime.now(timezone.utc).isoformat()
        (work / "simulation-result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=int, default=180)
    args = parser.parse_args()
    report = run(args.workdir, args.maximum_seconds)
    print(json.dumps({"Passed": report["Passed"], "Report": str(args.workdir / "simulation-result.json"),
                      "Error": report.get("Error")}, ensure_ascii=False))
    return 0 if report["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
