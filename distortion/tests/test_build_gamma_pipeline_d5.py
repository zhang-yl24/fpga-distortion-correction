"""Only mocked subprocess/artifacts; never execute PDS or access a board."""
from pathlib import Path
import copy
import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"tools"))
import build_gamma_pipeline_d5 as build

REAL_PINS = json.loads((ROOT/f"board/{build.TARGET}-pins.json").read_text())
REAL_HELPER = build.prepared.__file__


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "ROOT", tmp_path)
    monkeypatch.setattr(build, "APPROVED", tmp_path)
    monkeypatch.setattr(build.gate_log, "APPROVED", tmp_path)
    (tmp_path/"rtl").mkdir(); (tmp_path/"board").mkdir()
    (tmp_path/"rtl/shared.v").write_text("// synthetic fixture only\n")
    (tmp_path/f"board/{build.TARGET}-pins.json").write_text(json.dumps(REAL_PINS))
    moves = {"old/cal.vh": "board/private-cal.vh", "old/domain.vh": "board/private-domain.vh"}
    for name in moves.values():
        (tmp_path/name).write_text("// synthetic historical parameter stand-in\n")
    def verify():
        return {"SourceSHA256": {"rtl/shared.v": build.sha(tmp_path/"rtl/shared.v")},
                "IntegrationContract": {"calibration_scope": "historical synthetic fixture only"}}
    monkeypatch.setattr(build, "prepared", SimpleNamespace(verify_clone=verify, PARAMETER_MOVES=moves, __file__=REAL_HELPER))
    simulation = {"Path": "synthetic-simulation", "SHA256": "a"*64,
                  "SourceBinding": "synthetic", "HistoricalParametersOnly": True,
                  "NewLensCorrectionVerified": False}
    monkeypatch.setattr(build, "validate_simulation", lambda _: copy.deepcopy(simulation))
    pds = tmp_path/"pds"; pds.mkdir(); (pds/"pds_shell.exe").write_bytes(b"mock only - never execute")
    return tmp_path, pds


def artifacts(work, fault=None):
    for name in ("place_route", "report_timing", "generate_bitstream"):
        (work/name).mkdir()
    target = build.TARGET
    routed = work/"place_route"/f"{target}_pnr.adf"; routed.write_bytes(b"mock DB")
    hold = work/"place_route"/f"{target}_timing_summary_after_hold_fix.txt"
    final = work/"report_timing"/f"{target}.rtr"
    passed = "Design Summary : All Constraints Met.\n"
    hold.write_text("" if fault=="hold" else "Design Summary : Some Constraints Violated.\n" if fault=="earlier-summary" else passed)
    summary = "Design Summary : Failed.\n" if fault=="timing" else passed
    final.write_text(summary+(passed if fault=="duplicate-timing" else '')+str(routed).replace("\\","/")+"\n")
    bit = work/"generate_bitstream"/f"{target}.sbit"; bit.write_bytes(b"" if fault=="empty-bit" else b"mock SRAM bits")
    os.utime(routed, ns=(1000,1000)); os.utime(final, ns=(2000,2000)); os.utime(bit, ns=(3000,3000))
    if fault=="stale-timing": os.utime(final, ns=(999,999))
    if fault=="stale-bit": os.utime(bit, ns=(1999,1999))
    pins = dict(REAL_PINS)
    if fault=="AA22": pins["cam_data[5]"]="AA22"
    rows=[f"{pad}|IO|BANK|PIN|{port}|{build.port_direction(port)}|YES" for port,pad in pins.items()]
    if fault=="direction": rows=[line.replace("|key0_n|input|", "|key0_n|output|") for line in rows]
    if fault=="duplicate": rows.append(rows[0])
    (work/"place_route"/f"{target}_prr.prt").write_text("\n".join(rows)+"\n")


def fake_popen(monkeypatch, *, fault=None, code=0):
    called=[]
    class Fake:
        pid=43210
        def __init__(self, command, **kwargs):
            self.code=code; called.append(self)
            assert command[0].endswith("pds_shell.exe") and "-project_name" in command
            work=Path(kwargs["cwd"])
            _, errors, commands = build.gate_log.script_context(work, build.TARGET, build.gate_log.CANONICAL_MAIN)
            lines = ['License checkout: fabric_shell from mock-only.lic', *errors,
                f"Analyzing project file '{work.as_posix()}/{build.TARGET}.pds'."]
            for stage in build.gate_log.STAGES:
                lines.extend(('Executing : '+commands[stage], 'Executing : '+commands[stage]+' successfully.'))
            if fault=='runtime-error': lines.append('E: real runtime failure')
            if fault=='unknown-prefix': lines.insert(0,'E: unknown source or license failure')
            kwargs["stdout"].write(('\n'.join(lines)+'\n').encode())
            kwargs["stdout"].flush()
            artifacts(work, fault)
            if fault=="source": (work.parent/"rtl/shared.v").write_text("changed synthetic source")
        def wait(self, timeout): return self.code
        def poll(self): return self.code
    monkeypatch.setattr(build.subprocess, "Popen", Fake)
    return called


def test_default_plan_never_starts_process(fixture, monkeypatch):
    root,pds=fixture
    def forbidden(*_,**__): raise AssertionError("default plan started PDS")
    monkeypatch.setattr(build.subprocess, "Popen", forbidden)
    result=build.run_build(root/"plan", simulation_evidence="mock", pds_bin=pds)
    assert result["ExecuteBuild"] is False and result["NoFlashOrProgrammingOperation"] is True
    assert (root/"plan/plan.json").is_file()
    assert not (root/"plan/validated-build.json").exists()


@pytest.mark.parametrize("bad", [True, float("nan"), 0, 7201])
def test_invalid_bound_rejected(fixture,bad):
    root,pds=fixture
    with pytest.raises(ValueError): build.run_build(root/"bad", simulation_evidence="mock", timeout_seconds=bad)
    assert not (root/"bad").exists()


def test_workdir_must_be_fresh(fixture):
    root,pds=fixture
    with pytest.raises(ValueError): build.run_build(root, simulation_evidence="mock")
    with pytest.raises(ValueError): build.run_build(root.parent/"outside-candidate-build", simulation_evidence="mock")


def test_explicit_7200_second_offline_plan_is_allowed(fixture, monkeypatch):
    root,pds=fixture
    monkeypatch.setattr(build.subprocess,"Popen",lambda *a,**kw: pytest.fail("plan started PDS"))
    result=build.run_build(root/"long-offline-plan",simulation_evidence="mock",pds_bin=pds,timeout_seconds=7200)
    assert result["ExecuteBuild"] is False


def test_mock_success_requires_full_artifact_gates(fixture,monkeypatch):
    root,pds=fixture; calls=fake_popen(monkeypatch)
    result=build.run_build(root/"built", execute=True, simulation_evidence="mock", pds_bin=pds)
    assert result["Passed"] is True and result["ProcessExitCode"]==0 and len(calls)==1
    manifest=json.loads((root/"built/validated-build.json").read_text())
    assert manifest["RoutedPinCount"]==130 and manifest["NewLensCorrectionVerified"] is False
    assert manifest["SourceSHA256"]==manifest["SourceSHA256After"]
    assert manifest['PDSLogAudit']['CADScriptRole']=='canonical_main'
    assert manifest['PreBitGateExecutionProven'] is False
    assert manifest['PDSLogAuditHelperSHA256']==build.sha(Path(build.gate_log.__file__))


def test_final_saved_db_report_wins_over_earlier_pnr_summary(fixture,monkeypatch):
    root,pds=fixture; fake_popen(monkeypatch,fault="earlier-summary")
    result=build.run_build(root/"final-route",execute=True,simulation_evidence="mock",pds_bin=pds)
    assert result["Passed"] is True
    manifest=json.loads((root/"final-route/validated-build.json").read_text())
    assert manifest["AfterHoldSummaryAllMet"] is False
    assert "final saved routed-DB" in manifest["BuildValidation"]


@pytest.mark.parametrize("fault", ["hold","timing","duplicate-timing","stale-timing","stale-bit","empty-bit","AA22","direction","duplicate","source","runtime-error","unknown-prefix"])
def test_mock_bad_artifact_or_source_cannot_pass(fixture,monkeypatch,fault):
    root,pds=fixture; fake_popen(monkeypatch,fault=fault)
    result=build.run_build(root/"rejected", execute=True, simulation_evidence="mock", pds_bin=pds)
    assert result["Passed"] is False
    assert not (root/"rejected/validated-build.json").exists()


@pytest.mark.parametrize("code", [1,None])
def test_native_failed_or_missing_exit_cannot_pass(fixture,monkeypatch,code):
    root,pds=fixture; fake_popen(monkeypatch,code=code)
    # None represents an unavailable native exit; mock cleanup must not invoke OS tools.
    monkeypatch.setattr(build, "stop_owned", lambda child,work: setattr(child,"code",-9))
    result=build.run_build(root/"failed", execute=True, simulation_evidence="mock", pds_bin=pds)
    assert result["Passed"] is False and not (root/"failed/validated-build.json").exists()


def test_timeout_stops_only_the_owned_child(fixture,monkeypatch):
    root,pds=fixture; stopped=[]
    class Hung:
        pid=56789
        def __init__(self,*_,**__): self.status=None
        def wait(self,timeout): raise subprocess.TimeoutExpired("mock-owned-pds",timeout)
        def poll(self): return self.status
    monkeypatch.setattr(build.subprocess,"Popen",Hung)
    def stop(child,work): stopped.append(child.pid);child.status=-9
    monkeypatch.setattr(build,"stop_owned",stop)
    result=build.run_build(root/"timeout",execute=True,simulation_evidence="mock",pds_bin=pds)
    assert result["Passed"] is False and result["TimedOut"] is True and stopped==[56789]
