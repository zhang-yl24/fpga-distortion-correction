"""Four narrow synthetic/mock checks; never launch PDS or access hardware."""
from pathlib import Path
import json
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import reseed_gamma_pipeline_d5 as reseed


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(reseed, "APPROVED", tmp_path)
    old = tmp_path / "F"
    old.mkdir()
    mapping, pcf = old / "map.adf", old / "pins.pcf"
    mapping.write_bytes(b"synthetic sealed map")
    pcf.write_bytes(b"synthetic sealed constraints")
    plan, result = old / "plan.json", old / "result.json"
    plan.write_text("{}")
    result.write_text(json.dumps({"Passed": False, "ProcessExitCode": 1}))
    context = {"PreviousPlan": str(plan), "PreviousPlanSHA256": reseed.sha(plan),
               "PreviousResult": str(result), "PreviousResultSHA256": reseed.sha(result),
               "PreviousPassed": False, "PreviousTimedOut": False, "PreviousProcessExitCode": 1,
               "MapDatabase": str(mapping), "PreviousDatabaseSHA256": {str(p): reseed.sha(p) for p in (mapping, pcf)}}
    name = "rtl/cordic_sincos.v"
    before = {"SourceSHA256": {name: reseed.sha(reseed.ROOT / name)}, "ProfileBinding": {"DevelopmentOnly": True}}
    monkeypatch.setattr(reseed, "source_context", lambda *a: (before, {"Path": "synthetic-sim"}, context))
    monkeypatch.setattr(reseed.core, "verify_prepared", lambda *a: before)
    pds = tmp_path / "pds"
    pds.mkdir()
    (pds / "pds_shell.exe").write_bytes(b"never execute")
    return tmp_path, old, pds, mapping


def test_default_complete_seed3_plan_is_nonexecuting(source, monkeypatch):
    root, old, pds, _ = source
    original = {p.name: p.read_bytes() for p in old.iterdir()}
    monkeypatch.setattr(reseed.subprocess, "Popen", lambda *a, **k: pytest.fail("plan launched PDS"))
    result = reseed.run_reseed(old, root / "plan", profile_binding="mock", pds_bin=pds)
    text = (root / "plan/reseed.tcl").read_text()
    assert result["ExecuteReseed"] is False and result["Seed"] == 3
    main = (reseed.ROOT / f"board/build-{reseed.TARGET}.tcl").read_text()
    assert text == main.replace("-gplace_seed 2", "-gplace_seed 3")
    assert "-input_db_file" not in text and "-gplace_seed 3" in text and "-input_place_db_file" not in text
    assert all("\n" + command + " " in text for command in ("compile", "synthesize", "dev_map"))
    assert reseed.core.prepared.pre_bit_timing_gate() in text
    assert {p.name: p.read_bytes() for p in old.iterdir()} == original


def test_active_or_source_drift_is_refused_before_output(tmp_path, monkeypatch):
    monkeypatch.setattr(reseed, "APPROVED", tmp_path)
    old = tmp_path / "active"
    old.mkdir()
    with pytest.raises(ValueError, match="active/unknown"):
        reseed.source_context(old, "mock")
    sources = {f"synthetic-{i}": "a" * 64 for i in range(123)}
    before = {"SourceSHA256": sources, "ProfileBinding": {"Path": "mock"}}
    monkeypatch.setattr(reseed.core, "verify_prepared", lambda *a: before)
    plan = {"Target": reseed.TARGET, **before}
    result = {"Target": reseed.TARGET, "Passed": False, "TimedOut": False, "EndedUtc": "2026-10-26T00:00:00Z",
              "ProcessExitCode": 1, "Error": "synthetic failed attempt", "OutputDirectory": str(old),
              "SourceSHA256": sources, "SourceSHA256After": {**sources, "synthetic-0": "b" * 64}}
    (old / "plan.json").write_text(json.dumps(plan))
    (old / "gamma-pipeline-build-result.json").write_text(json.dumps(result))
    with pytest.raises(ValueError, match="source123/profile"):
        reseed.source_context(old, "mock")
    result.update(SourceSHA256After=sources, TimedOut=True, ProcessExitCode=None,
                  CleanupError="synthetic child cleanup/termination unknown")
    (old / "gamma-pipeline-build-result.json").write_text(json.dumps(result))
    with pytest.raises(ValueError, match="source123/profile"):
        reseed.source_context(old, "mock")


def test_timeout_stops_only_own_native_child(source, monkeypatch):
    root, old, pds, _ = source
    stopped = []
    class Hung:
        pid = 65432
        status = None
        def __init__(self, *a, **k):
            pass
        def wait(self, timeout):
            raise subprocess.TimeoutExpired("synthetic owned PDS", timeout)
        def poll(self):
            return self.status
    monkeypatch.setattr(reseed.subprocess, "Popen", Hung)
    def stop(child, work):
        stopped.append(child.pid)
        child.status = -1
    monkeypatch.setattr(reseed, "stop_owned", stop)
    result = reseed.run_reseed(old, root / "timeout", profile_binding="mock", execute=True, pds_bin=pds)
    assert result["Passed"] is False and result["TimedOut"] is True and stopped == [65432]
    assert not (root / "timeout/validated-build.json").exists()


def test_input_map_change_after_native_zero_cannot_validate(source, monkeypatch):
    root, old, pds, mapping = source
    class Changed:
        pid = 65433
        def __init__(self, *a, **k):
            mapping.write_bytes(b"changed synthetic map")
        def wait(self, timeout):
            return 0
        def poll(self):
            return 0
    monkeypatch.setattr(reseed.subprocess, "Popen", Changed)
    monkeypatch.setattr(reseed.core, "validate_artifacts", lambda *a: pytest.fail("drift reached validator"))
    result = reseed.run_reseed(old, root / "changed", profile_binding="mock", execute=True, pds_bin=pds)
    assert result["Passed"] is False and result["ProcessExitCode"] == 0 and "DB SHA changed" in result["Error"]
    assert not (root / "changed/validated-build.json").exists()
