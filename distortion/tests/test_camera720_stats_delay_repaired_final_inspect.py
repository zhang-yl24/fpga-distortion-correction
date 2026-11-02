"""CPU-only source seal integrity and fresh-query checks; no PDS or hardware."""
from pathlib import Path
import json
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_delay_repaired_final_inspect as final


def shape():
    return {'Schema':final.AUTHORITY_SCHEMA,'Target':final.prep.TARGET,'FullVerificationCompleted':True,
        'ValidationMethod':{'Function':'camera720_stats_delay_repaired_reset_apply.bind_completed',
            'Path':str(final.physical.SELF),'SHA256':final.sha(final.physical.SELF)},
        'Producer':final.reference(final.SELF),'EDAExecuted':False,'HardwareAccessed':False,
        'HardwareReleaseAllowed':False,'TimingAccepted':False}


@pytest.mark.parametrize('field,bad',[
    ('Schema','old'),('Target','raw_camera_capture_cam2_current720'),('FullVerificationCompleted',False),
    ('EDAExecuted',True),('HardwareAccessed',True),('HardwareReleaseAllowed',True),('TimingAccepted',True),
])
def test_final_source_identity_and_scope_are_exact(field,bad):
    value=shape();final.authority_shape(value);value[field]=bad
    with pytest.raises(ValueError):final.authority_shape(value)


@pytest.mark.parametrize('field,bad',[('SHA256','0'*64),('Function','old.bind_completed'),('Path','other.py')])
def test_source_validator_is_exact(field,bad):
    value=shape();value['ValidationMethod'][field]=bad
    with pytest.raises(ValueError):final.authority_shape(value)


def test_report_is_fresh_readonly_native_context():
    text=final.render('report','',final.prep.WORK,final.prep.WORK/'fixture')
    assert text.count(final.INIT)==1
    assert '.switch_db -route' in text
    for forbidden in ('save_adif','set_false_path','manual_route','unroute','gen_bit_stream'):
        assert forbidden not in text


def test_completion_marker_cannot_be_injected():
    with pytest.raises(ValueError,match='reserved'):
        final.render('query','',final.prep.WORK,final.prep.WORK,'puts {'+final.MARKER+'}')


@pytest.mark.parametrize('digest',[None,'','bad','a'*63])
def test_seal_requires_explicit_receipt_hash_before_any_full_bind(monkeypatch,digest):
    monkeypatch.setattr(final.physical,'bind_completed',lambda *a:pytest.fail('invalid hash must reject before full binding'))
    with pytest.raises(ValueError,match='explicit'):final.seal_source('none',digest,'none')


@pytest.fixture
def sealed(tmp_path,monkeypatch):
    def write(path,data):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(data) if isinstance(data,dict) else data,encoding='utf-8')
        return path
    monkeypatch.setattr(final,'SELF',write(tmp_path/'final.py','final inspector'))
    monkeypatch.setattr(final.physical,'SELF',write(tmp_path/'apply.py','exact apply'))
    work=tmp_path/'apply-a';work.mkdir()
    build=write(tmp_path/'build.json',{'Target':final.prep.TARGET})
    request=write(tmp_path/'request.json',{'Target':final.prep.TARGET})
    original=write(tmp_path/'source.adf','before reset')
    leaf=write(tmp_path/'source.v','bound HDL')
    candidate=write(work/'input.adf','after reset')
    write(work/'saved-reset.adf','after reset');write(work/'post-init.adf','before reset')
    write(work/'stdout.log',final.physical.MARKER+'\n');write(work/'stderr.log','')
    write(work/'stage.tcl','exact reset Tcl');write(work/'executor-snapshot.py','exact apply')
    stage={'Mode':'save-reset','WorkDirectory':str(work),'BuildPlan':str(build),'Request':final.reference(request),
        'SourceADF':str(original),'SourceADFSHA256':final.sha(original),'NativeQueries':[],
        'ExpectedNativeNameProof':[],'InputSHA256':{str(p):final.sha(p) for p in (original,leaf,build,request)}}
    stage_path=write(work/'stage-plan.json',stage)
    application={**stage,'Schema':final.physical.SCHEMA,'Target':final.prep.TARGET,'ExitCode':0,
        'EDAExecuted':True,'TimedOut':False,'StoppedForUnexpectedStage':False,'InputDrift':[],'Diagnostics':[],
        'ActualEvents':[],'CompletionMarker':True,'InitializationPreservedADF':True,'SavedADFReadbackMatches':True,
        'ResultADFChanged':True,'NativeApplicationNamesVerified':True,'RoutesAndPlacementUnchanged':True,
        'Cleanup':{'Complete':True},'ExecutionPassed':True,'ApplicationNativeNameProof':[],
        'ResultADF':{'Path':str(candidate),'SHA256':final.sha(candidate),'Bytes':candidate.stat().st_size},
        'ResultADFSHA256':final.sha(candidate),'StagePlanSHA256':final.sha(stage_path),
        'Artifacts':final.physical.artifact_hashes(work)}
    receipt=write(work/'result.json',application)
    inputs={str(p):final.sha(p) for p in (original,leaf,build,request,receipt,final.SELF,final.physical.SELF)}
    inputs.update({str(work/n):h for n,h in application['Artifacts'].items()})
    seed={**shape(),'SourceReceipt':final.reference(receipt),'CandidateADF':final.reference(candidate),
        'StagePlan':final.reference(stage_path),'BuildPlan':final.reference(build),'Request':final.reference(request),
        'InputSHA256':inputs,'ToolSHA256':{p:h for p,h in inputs.items() if Path(p).suffix in ('.py','.exe')}}
    authority=tmp_path/'authority.json'
    def seal():write(authority,seed);return final.sha(authority)
    return {'path':authority,'seed':seed,'seal':seal,'leaf':leaf,'receipt':receipt,'application':application,'write':write}


def test_sealed_bind_rehashes_without_repeating_graph_parser(monkeypatch,sealed):
    a=sealed;monkeypatch.setattr(final.physical,'bind_completed',lambda *a:pytest.fail('must not repeat expensive semantic parser'))
    value,watched=final.bind_authority(a['path'],a['seal']())
    assert value['ExecutionPassed'] is True
    assert a['leaf'] in watched


def test_any_bound_source_drift_rejects_sealed_reuse(sealed):
    a=sealed;digest=a['seal']();a['leaf'].write_text('changed source')
    with pytest.raises(ValueError,match='sealed source input drift'):final.bind_authority(a['path'],digest)


def test_original_input_cannot_be_omitted_from_seed(sealed):
    a=sealed;a['seed']['InputSHA256'].pop(str(a['leaf']))
    with pytest.raises(ValueError,match='omitted original source input'):final.bind_authority(a['path'],a['seal']())


def test_source_artifact_cannot_be_omitted_from_seed(sealed):
    a=sealed;path=a['receipt'].parent/'stderr.log';a['seed']['InputSHA256'].pop(str(path))
    with pytest.raises(ValueError,match='omitted actual source artifact'):final.bind_authority(a['path'],a['seal']())


def test_tool_closure_shape_cannot_be_narrowed(sealed):
    a=sealed;a['seed']['ToolSHA256']={}
    with pytest.raises(ValueError,match='tool closure'):final.bind_authority(a['path'],a['seal']())


def test_explicit_seed_hash_is_rechecked(sealed):
    a=sealed;a['seal']()
    with pytest.raises(ValueError):final.bind_authority(a['path'],'0'*64)
