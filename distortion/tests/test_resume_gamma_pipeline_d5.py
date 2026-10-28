"""Three narrow mocked checks; no actual PDS, programming or hardware."""
from pathlib import Path
import json
import subprocess
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import resume_gamma_pipeline_d5 as resume


@pytest.fixture
def source(tmp_path,monkeypatch):
    monkeypatch.setattr(resume,"APPROVED",tmp_path)
    old=tmp_path/"A";old.mkdir();mapping=old/"map.adf";mapping.write_bytes(b"synthetic map")
    placed=old/"plc.adf";placed.write_bytes(b"synthetic placed DB")
    result=old/"result.json";result.write_text(json.dumps({"TimedOut":True,"ProcessExitCode":None}))
    plan=old/"plan.json";plan.write_text("{}")
    context={"PreviousPlan":str(plan),"PreviousPlanSHA256":resume.sha(plan),"PreviousResult":str(result),"PreviousResultSHA256":resume.sha(result),
             "PreviousTimedOut":True,"PreviousProcessExitCode":None,"PreviousPassed":False,
             "MapDatabase":str(mapping),"PlacementDatabase":str(placed),
             "InputDatabaseSHA256":{str(mapping):resume.sha(mapping),str(placed):resume.sha(placed)}}
    before={"SourceSHA256":{},"IntegrationContract":{}}
    monkeypatch.setattr(resume,"source_context",lambda _:(before,{"Path":"mock"},context))
    monkeypatch.setattr(resume.core.prepared,"verify_clone",lambda:before)
    pds=tmp_path/"pds";pds.mkdir();(pds/"pds_shell.exe").write_bytes(b"mock only, never execute")
    return old,tmp_path,pds,mapping,result


def test_default_plan_does_not_launch_or_mutate_A(source,monkeypatch):
    old,root,pds,mapping,oldresult=source
    before={str(p):p.read_bytes() for p in old.iterdir()}
    monkeypatch.setattr(resume.subprocess,"Popen",lambda *a,**k:pytest.fail("plan launched PDS"))
    plan=resume.run_resume(old,root/"B-plan",pds_bin=pds)
    assert plan["ExecuteResume"] is False and plan["Context"]["PreviousTimedOut"] is True
    assert plan["Context"]["PreviousProcessExitCode"] is None
    assert {str(p):p.read_bytes() for p in old.iterdir()}==before
    tcl=(root/"B-plan/resume.tcl").read_text()
    assert "-input_db_file" in tcl and "-input_place_db_file" in tcl
    assert "\ncompile " not in tcl and "\nsynthesize " not in tcl and "\ndev_map " not in tcl


def test_timeout_only_stops_owned_child(source,monkeypatch):
    old,root,pds,mapping,oldresult=source;stopped=[]
    class Hung:
        pid=45678
        def __init__(self,*a,**k):self.status=None
        def poll(self):return self.status
        def wait(self,timeout):raise subprocess.TimeoutExpired("synthetic owned PDS",timeout)
    monkeypatch.setattr(resume.subprocess,"Popen",Hung)
    def stop(child,work):stopped.append(child.pid);child.status=-9
    monkeypatch.setattr(resume,"stop_owned",stop)
    result=resume.run_resume(old,root/"B-timeout",execute=True,pds_bin=pds,timeout_seconds=7200)
    assert result["Passed"] is False and result["TimedOut"] is True and result["ProcessExitCode"] is None
    assert stopped==[45678] and not (root/"B-timeout/validated-build.json").exists()


def test_changed_input_db_rejected_even_after_native_zero(source,monkeypatch):
    old,root,pds,mapping,oldresult=source
    class Changed:
        pid=45679
        def __init__(self,*a,**k):mapping.write_bytes(b"changed synthetic DB")
        def wait(self,timeout):return 0
        def poll(self):return 0
    monkeypatch.setattr(resume.subprocess,"Popen",Changed)
    monkeypatch.setattr(resume.core,"validate_artifacts",lambda *a:pytest.fail("DB change reached canonical validator"))
    result=resume.run_resume(old,root/"B-changed",execute=True,pds_bin=pds)
    assert result["Passed"] is False and result["ProcessExitCode"]==0 and "DB SHA changed" in result["Error"]
    assert not (root/"B-changed/validated-build.json").exists()
