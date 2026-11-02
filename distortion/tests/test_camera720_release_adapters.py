"""New producer adapters must preserve every original authority boundary."""
from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_bitstream as bit
import camera720_cdc_grouped as grouped
import camera720_io_fast as io_fast


def test_producer_dispatch_is_explicit_and_known():
    assert bit.audit_module({},'cdc') is bit.cdc
    assert bit.audit_module({},'io') is io_fast.source
    assert bit.audit_module({'Producer':bit.binding(grouped.SELF)},'cdc') is grouped
    assert bit.audit_module({'Producer':bit.binding(io_fast.SELF)},'io') is io_fast
    for value in ({'InspectionSeed':{}},{'OriginalBatchPlan':{}},
                  {'Producer':bit.binding(io_fast.SELF)},
                  {'Producer':{'Path':str(grouped.SELF),'SHA256':'0'*64}}):
        with pytest.raises(ValueError):bit.audit_module(value,'cdc')


@pytest.fixture
def grouped_proof(tmp_path,monkeypatch):
    export=tmp_path/'export.json';export.write_text('{}')
    plan={'OriginalBatchPlan':{'Path':'original.json','SHA256':'a'*64},
        'InspectionSeed':{'Path':'seed.json','SHA256':'b'*64},
        'Producer':bit.binding(grouped.SELF),'ExportReceipt':bit.binding(export)}
    value={'Producer':plan['Producer'],'OriginalBatchPlan':plan['OriginalBatchPlan'],
        'InspectionSeed':plan['InspectionSeed'],'BatchPlan':{'Path':'grouped.json','SHA256':'c'*64}}
    expected_context=('actual seed','actual original','actual bound')
    calls=[]
    def bind(path,digest,watched):
        assert watched=={}
        calls.append((path,digest));return plan,['planned body'],expected_context
    monkeypatch.setattr(grouped,'bind_plan',bind)
    monkeypatch.setattr(bit,'read',lambda path:{'Command':['unused-pds']})
    monkeypatch.setattr(bit,'merge',lambda *args:None)
    return value,plan,export,expected_context,calls


def test_grouped_adapter_uses_explicit_plan_hash_and_fresh_binder_context(grouped_proof):
    value,plan,export,context,calls=grouped_proof
    module,actual,texts,bound=bit.grouped_context(value,export,{'other':'already watched'})
    assert module is grouped and actual is plan and texts==['planned body'] and bound is context
    assert calls==[('grouped.json','c'*64)]


@pytest.mark.parametrize('field',('OriginalBatchPlan','InspectionSeed','Producer','ExportReceipt'))
def test_grouped_adapter_rejects_different_original_seed_producer_or_export(grouped_proof,field):
    value,plan,export,_,_=grouped_proof
    plan[field]={**plan[field],'SHA256':'f'*64}
    with pytest.raises(ValueError):bit.grouped_context(value,export,{})


def test_full_grouped_recompute_rejects_any_remaining_supplements(grouped_proof,monkeypatch):
    value,plan,export,_,_=grouped_proof
    value['NativeReceipts']=[{'Path':'actual query.json','SHA256':'d'*64}]
    called=[]
    def audit(path,digest,receipts):
        called.append((path,digest,receipts));return {},{}, {'supplement-00.tcl':'missing pair'}
    monkeypatch.setattr(grouped,'audit',audit)
    with pytest.raises(ValueError,match='supplemental'):bit.recompute_cdc(value,export,{})
    assert called==[('grouped.json','c'*64,['actual query.json'])]


@pytest.fixture
def io_case(tmp_path,monkeypatch):
    project=tmp_path/'distortion';project.mkdir()
    monkeypatch.setattr(io_fast.prep,'PROJECT',project)
    one=project/'input.bin';one.write_bytes(b'unchanged full proof input')
    seed_path=project/'seed.json';seed_path.write_text('{}')
    seed_ref={'Path':str(seed_path),'SHA256':io_fast.sha(seed_path)}
    candidate={'Path':str(project/'candidate.adf'),'SHA256':'a'*64}
    original={'SourceADF':candidate['Path'],'SourceADFSHA256':candidate['SHA256'],'BuildPlanSHA256':'b'*64}
    context=({'SourceADF':candidate},original,{one:io_fast.sha(one)})
    calls=[]
    def bind_seed(path,digest):
        assert path==seed_path and digest==seed_ref['SHA256'];return context
    monkeypatch.setattr(io_fast.fast,'bind_seed',bind_seed)
    monkeypatch.setattr(io_fast.source.structure,'local_helpers',lambda modules:[])
    monkeypatch.setattr(io_fast,'SELF',one)
    export=project/'export.json';export.write_text('{}')
    query=project/'query.json';query.write_text('{}')
    report=project/'report.rtr';report.write_text('native paths')
    log=project/'stdout.log';log.write_text('Site IO_1_2 (1) :\n')
    dump=project/'route-dump.txt';dump.write_text('native IO parameters')
    def bind_native(path,mode,watched,cand,build,seed,seed_context):
        assert seed_context is context and seed==seed_ref and cand==candidate and build=='b'*64
        calls.append((path,mode))
        return {'BuildPlanSHA256':'b'*64,'Artifacts':{'route-dump.txt':io_fast.sha(dump)}}
    monkeypatch.setattr(grouped,'bind_native_fast',bind_native)
    monkeypatch.setattr(io_fast,'derive',lambda *args:({'PinInventory':[]},{'Passed':True}))
    def artifact(path,receipt,name,watched):
        return {'stdout.log':log,'route-dump.txt':dump}.get(name,report)
    monkeypatch.setattr(io_fast.source,'artifact',artifact)
    monkeypatch.setattr(io_fast.source.structure.io,'apply_native_sites',lambda *args:None)
    monkeypatch.setattr(io_fast.source,'io_parameters',lambda *args:{'Passed':True})
    monkeypatch.setattr(io_fast.source.tx,'pad_paths',lambda *args:[{'SlackNS':0.1}])
    monkeypatch.setattr(io_fast.source.tx,'commands',lambda *args:['checked command'])
    for name in ('board/ms7210_commands.vh','platform/video_base/source/hdmi/ms7210_ctl.v'):
        path=project/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('actual command source')
    monkeypatch.setattr(io_fast.source,'dvp_records',lambda *args:[{'native':'record'}])
    monkeypatch.setattr(io_fast.source,'dvp_summary',lambda rows:{'ReportedBudgetCoverageComplete':True})
    return export,query,seed_path,seed_ref,one,calls


def test_fast_io_reuses_seed_but_runs_actual_io_checks_and_records_producer(io_case):
    export,query,seed,ref,_,calls=io_case
    result=io_fast.audit(export,[query],seed,ref['SHA256'])
    assert result['AuditPassed'] and result['ActualIOChecksRecomputed'] and result['NativeSourceProofReused']
    assert result['InspectionSeed']==ref and result['Producer']==io_fast.binding(io_fast.SELF)
    assert calls==[(export,'export'),(query,'query')]
    assert result['ExternalACAccepted'] is False and result['HardwareReleaseAllowed'] is False


def test_fast_io_missing_dvp_evidence_never_passes(io_case,monkeypatch):
    export,query,seed,ref,_,_=io_case
    monkeypatch.setattr(io_fast.source,'dvp_summary',lambda rows:{'ReportedBudgetCoverageComplete':False})
    with pytest.raises(ValueError,match='DVP'):io_fast.audit(export,[query],seed,ref['SHA256'])


def test_fast_io_wrong_pad_parameter_failure_is_not_suppressed(io_case,monkeypatch):
    export,query,seed,ref,_,_=io_case
    def fail(*args):raise ValueError('native VCCIO differs')
    monkeypatch.setattr(io_fast.source,'io_parameters',fail)
    with pytest.raises(ValueError,match='VCCIO'):io_fast.audit(export,[query],seed,ref['SHA256'])


def test_fast_io_parser_time_input_drift_rejected(io_case,monkeypatch):
    export,query,seed,ref,one,_=io_case
    def changed(*args):
        one.write_bytes(b'changed after source proof')
        return {'Passed':True}
    monkeypatch.setattr(io_fast.source,'io_parameters',changed)
    with pytest.raises(ValueError,match='drift'):io_fast.audit(export,[query],seed,ref['SHA256'])


def test_fast_io_duplicate_receipts_rejected_before_binding(io_case):
    export,query,seed,ref,_,calls=io_case
    with pytest.raises(ValueError,match='distinct'):io_fast.audit(export,[query,query],seed,ref['SHA256'])
    assert calls==[]
