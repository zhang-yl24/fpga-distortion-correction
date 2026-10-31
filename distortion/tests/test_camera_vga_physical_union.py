import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import audit_camera_vga_physical_union as adapter


def fixture(tmp_path):
    old=tmp_path/'old.rtr';old.write_text('old report')
    new=tmp_path/'new.rtr';new.write_text('new report')
    adf=tmp_path/'input.adf';adf.write_text('final ADF')
    args=SimpleNamespace(baseline_exceptions=old,candidate_exceptions=new,candidate_adf=adf)
    proof={'Schema':'camera-vga-exception-union-comparison-v1','AuditPassed':True,
           'MembershipCompletedFromBothUnions':True,'RouteChain':{'OnlyChangedNets':sorted(adapter.union.NETS),
           'Verified':True,'CandidateADFSHA256':adapter.sha(adf)},
           'BaselineExceptions':str(old),'CandidateExceptions':str(new),
           'InputSHA256':{str(p):adapter.sha(p) for p in (old,new,adf)},
           'ToolSHA256':{str(Path(adapter.union.__file__).resolve()):adapter.sha(adapter.union.__file__)},
           'Sections':{},'ChangedIdentityCount':1,'ComparedUnionPathCount':1,'PrintedRoundingPathCount':0}
    path=tmp_path/'proof.json';path.write_text(json.dumps(proof))
    return args,path,proof


def test_adapter_binds_and_embeds_all_proof_inputs(tmp_path,monkeypatch):
    args,path,proof=fixture(tmp_path)
    original=adapter.physical.exceptions
    def audited(args):
        assert adapter.physical.exceptions(args.baseline_exceptions,set())==adapter.physical.exceptions(args.candidate_exceptions,set())
        return {'InputSHA256':{},'ToolSHA256':{},'AuditPassed':True}
    monkeypatch.setattr(adapter.physical,'audit',audited)
    result=adapter.audit(args,path)
    assert adapter.physical.exceptions is original
    assert result['ExceptionUnionProof']==proof
    assert set(proof['InputSHA256'])<=set(result['InputSHA256'])


def test_adapter_restores_frozen_function_on_failure(tmp_path,monkeypatch):
    args,path,_=fixture(tmp_path);original=adapter.physical.exceptions
    def failure(args):raise ValueError('strict timing failure')
    monkeypatch.setattr(adapter.physical,'audit',failure)
    with pytest.raises(ValueError,match='strict timing failure'):adapter.audit(args,path)
    assert adapter.physical.exceptions is original


def test_adapter_rejects_report_drift(tmp_path):
    args,path,_=fixture(tmp_path);args.candidate_exceptions.write_text('changed')
    with pytest.raises(ValueError,match='drift'):adapter.load_proof(path,args)


def test_adapter_rejects_different_candidate_adf(tmp_path):
    args,path,proof=fixture(tmp_path)
    other=tmp_path/'other.adf';other.write_text('different');args.candidate_adf=other
    with pytest.raises(ValueError,match='candidate ADF differs'):adapter.load_proof(path,args)


def test_adapter_does_not_skip_either_frozen_exception_call(tmp_path,monkeypatch):
    args,path,_=fixture(tmp_path)
    monkeypatch.setattr(adapter.physical,'audit',lambda args:{'InputSHA256':{},'ToolSHA256':{}})
    with pytest.raises(ValueError,match='did not compare both'):adapter.audit(args,path)


def test_adapter_rejects_duplicate_exception_calls(tmp_path,monkeypatch):
    args,path,_=fixture(tmp_path)
    def duplicate(args):
        adapter.physical.exceptions(args.baseline_exceptions,set())
        adapter.physical.exceptions(args.baseline_exceptions,set())
    monkeypatch.setattr(adapter.physical,'audit',duplicate)
    with pytest.raises(ValueError,match='unexpected exception audit invocation'):adapter.audit(args,path)
