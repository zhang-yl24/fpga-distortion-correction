"""Mocked fixed debug builder; no PDS/native executable is ever launched."""
from pathlib import Path
import copy
import json
import os
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_gamma_capture_k320_dev as build

PINS = json.loads((ROOT / f"board/{build.TARGET}-pins.json").read_text())


@pytest.fixture
def files(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "ROOT", tmp_path)
    monkeypatch.setattr(build, "APPROVED", tmp_path)
    source = tmp_path / "synthetic.v"
    source.write_bytes(b"synthetic source stand-in, never synthesized")
    def prepared():
        return {"Target": build.TARGET, "SourceSHA256": {"synthetic.v": build.sha(source)},
                "Pins": PINS, "ProfileBinding": {"DevelopmentOnly": True, "CalibrationAccepted": False}}
    monkeypatch.setattr(build, "verify_prepared", prepared)
    monkeypatch.setattr(build, "validate_simulation", lambda: {"Passed": True, "SyntheticMock": True})
    monkeypatch.setattr(build, "helper_hashes", lambda: {"mock-test": "f" * 64})
    pds = tmp_path / "pds"
    pds.mkdir()
    (pds / "pds_shell.exe").write_bytes(b"never run")
    return tmp_path, pds, source


def artifacts(work, fault=None):
    for name in ("place_route", "report_timing", "generate_bitstream"):
        (work / name).mkdir()
    routed = work / "place_route" / f"{build.TARGET}_pnr.adf"
    routed.write_bytes(b"mock routed DB")
    (work / "place_route" / f"{build.TARGET}_timing_summary_after_hold_fix.txt").write_text("Design Summary : Some Constraints Violated.\n")
    final = work / "report_timing" / f"{build.TARGET}.rtr"
    final.write_text(("Design Summary : Failed.\n" if fault == "timing" else "Design Summary : All Constraints Met.\n") + routed.as_posix())
    bit = work / "generate_bitstream" / f"{build.TARGET}.sbit"
    bit.write_bytes(b"mock SRAM file")
    for path, age in ((routed, 1000), (final, 2000), (bit, 3000)):
        os.utime(path, ns=(age, age))
    if fault == "stale-bit":
        os.utime(bit, ns=(1999, 1999))
    pins = dict(PINS)
    if fault == "AA22":
        pins["cam_data[5]"] = "AA22"
    rows = [f"{pad}|IO|BANK|PIN|{port}|{build.port_direction(port)}|YES" for port, pad in pins.items()]
    (work / "place_route" / f"{build.TARGET}_prr.prt").write_text("\n".join(rows))


def test_default_plan_does_not_launch_pds(files, monkeypatch):
    root, pds, _ = files
    monkeypatch.setattr(build.subprocess, "Popen", lambda *a, **k: pytest.fail("plan launched native code"))
    plan = build.run_build(root / "plan", pds_bin=pds)
    assert plan["ExecuteBuild"] is False and plan["TimeoutSeconds"] == 7200
    assert not (root / "plan/validated-build.json").exists()
    with pytest.raises(ValueError):
        build.run_build(root / "bad-bound", timeout_seconds=7201)


@pytest.mark.parametrize("fault", [None, "timing", "stale-bit", "AA22", "source", "native"])
def test_native_artifact_and_source_gates(files, monkeypatch, fault):
    root, pds, source = files
    class Fake:
        pid = 12345
        def __init__(self, command, **kwargs):
            artifacts(Path(kwargs["cwd"]), fault)
            kwargs["stdout"].write(b"Executing : gen_bit_stream -scbv {High Voltage} -unused_io_status UNUSED successfully.\n")
            if fault == "source":
                source.write_bytes(b"drift")
        def wait(self, timeout):
            return 1 if fault == "native" else 0
        def poll(self):
            return 0
    monkeypatch.setattr(build.subprocess, "Popen", Fake)
    result = build.run_build(root / "built", execute=True, pds_bin=pds)
    assert result["Passed"] is (fault is None)
    assert (root / "built/validated-build.json").exists() is (fault is None)
    if fault is None:
        m = build.load(root / "built/validated-build.json")
        assert m["RoutedPinCount"] == 128 and m["AfterHoldSummaryAllMet"] is False
        assert m["DevelopmentOnly"] is True and m["CalibrationAccepted"] is False


def test_timeout_stops_only_owned_process(files, monkeypatch):
    root, pds, _ = files
    stopped = []
    class Hung:
        pid = 54321
        code = None
        def __init__(self, *a, **k):
            pass
        def wait(self, timeout):
            raise subprocess.TimeoutExpired("mock-owned-PDS", timeout)
        def poll(self):
            return self.code
    monkeypatch.setattr(build.subprocess, "Popen", Hung)
    def stop(process, work):
        stopped.append(process.pid)
        process.code = -1
    monkeypatch.setattr(build, "stop_owned", stop)
    result = build.run_build(root / "timeout", execute=True, pds_bin=pds, timeout_seconds=60)
    assert result["Passed"] is False and result["TimedOut"] is True and stopped == [54321]
