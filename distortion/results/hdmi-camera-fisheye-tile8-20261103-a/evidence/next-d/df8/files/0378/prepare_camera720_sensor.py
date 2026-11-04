"""Verify a portable 720p sensor port against retained, byte-frozen sources.

This is a retained-source port, not a replay of the historical generator. Its
proposal under build/offline-20261024 is no longer present. The 403-action ROM
and manifest are reused verbatim; no register values are regenerated or changed.
No PDS, serial, JTAG, or hardware access is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BASE_INIT = "rtl/experimental/ov5640_rgb565_720_init.v"
INIT = "rtl/experimental/ov5640_current720_init.v"
FRONTEND = "rtl/experimental/ov5640_current720_frontend.v"
ROM = "board/ov5640_rgb565_720_commands.vh"
SEQUENCE = "board/ov5640_rgb565_720_sequence.json"
MONITOR = "rtl/experimental/dvp_mode_admission_monitor.v"
RETAINED = {
    BASE_INIT: "403214d854a068e0b087fb0c2b00242cf36b2b2a326c9cde6803f6aa22ccabb5",
    ROM: "05ce241ce37286b6820eeeaad28eeff0821f12d1319bdc6747c4fd04a72ff22c",
    SEQUENCE: "88cd19153f7f5fda5c80b86a4112f6e689ca52f094642cd1e2ce967261ee2c5d",
    MONITOR: "2895bad17ecc74c0cceefce4a53de525a2516462e1bc082481d2d34de2ec8b55",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_retained(root: Path = ROOT) -> dict:
    for name, expected in RETAINED.items():
        if sha(root / name) != expected:
            raise ValueError("Retained sensor source hash changed: " + name)
    mode = json.loads((root / SEQUENCE).read_text(encoding="utf-8"))
    actions = mode["Actions"]
    if mode["ImageSize"] != [1280, 720] or len(actions) != 403:
        raise ValueError("Retained 720p dimensions/action count changed")
    entries = re.findall(r"10'd(\d+):mode_action=48'h([0-9a-f]{12});",
                         (root / ROM).read_text(encoding="utf-8"))
    encoded = [(int(index), int(word, 16)) for index, word in entries]
    expected = []
    for index, action in enumerate(actions):
        if action["index"] != index:
            raise ValueError("Non-contiguous action sequence")
        word = ((action["op"] << 44) | (action["address"] << 28) |
                (action["mask"] << 20) | (action["value"] << 12) | action["delay_ms"])
        expected.append((index, word))
    if encoded != expected:
        raise ValueError("ROM and retained action manifest differ")
    return mode


def expected_initializer(root: Path = ROOT) -> bytes:
    verify_retained(root)
    payload = (root / BASE_INIT).read_bytes()
    edits = (
        (b"module ov5640_rgb565_720_init #(", b"module ov5640_current720_init #("),
        (b'`include "D:/English/FPGA/distortion/board/ov5640_rgb565_720_commands.vh"',
         b'`include "board/ov5640_rgb565_720_commands.vh"'),
    )
    for old, new in edits:
        if payload.count(old) != 1:
            raise ValueError("Expected exactly one portable initializer edit")
        payload = payload.replace(old, new)
    return payload


def verify(root: Path = ROOT) -> dict:
    mode = verify_retained(root)
    if (root / INIT).read_bytes() != expected_initializer(root):
        raise ValueError("Portable initializer changed beyond module name/include path")
    return {
        "Passed": True,
        "Target": "ov5640_current720_sensor_retained_source_port",
        "HistoricalGeneratorReproduced": False,
        "RetainedSourceSHA256": RETAINED,
        "PortSourceSHA256": {name: sha(root / name) for name in (INIT, FRONTEND)},
        "InitializerEdits": ["module name", "repository-relative include path"],
        "IncludeDirectoriesRelativeToDistortion": ["."],
        "RegisterActionCount": len(mode["Actions"]),
        "ImageSize": [1280, 720],
        "VSYNCHREFInputConvention": "already logical active-high; caller binds physical inversions",
        "PixelByteConvention": "RGB565 low-byte-first; frontend observes timing only, caller packs pixels",
        "StartupGraceRefCycles": 27000000,
        "StartupGraceMeaning": "1 second at 27 MHz to first complete good frame; two complete good frames required for admission",
        "RequiredCompleteGoodFrames": 2,
        "NominalPCLKModelHzAt24MHzXVCLK": mode["NominalPCLKModelHz"],
        "UpperPCLKModelHzAt27MHzXVCLK": mode["UpperPCLKModelHzAt27MHz"],
        "NominalFPSModelAt24MHzXVCLK": mode["NominalFPSModel"],
        "MeasuredFPS": None,
        "HardwareAccessed": False,
        "PDSAccessed": False,
        "HardwareReleaseAllowed": False,
        "Limits": "Retained-source integrity and portable binding only. Frontend digital behavior needs its separate RTL tests. No regenerated historical proposal, measured clock/fps, sensor/optical calibration, physical CDC/timing or board acceptance. raw_authorize must not reset accepted downstream transactions.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-initializer", action="store_true",
                        help="create only the new portable initializer; never overwrite")
    parser.add_argument("--report", type=Path, help="write a new JSON report; never overwrite")
    args = parser.parse_args()
    if args.stage_initializer:
        payload = expected_initializer()
        with (ROOT / INIT).open("xb") as stream:
            stream.write(payload)
    result = verify()
    payload = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if args.report:
        with args.report.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
