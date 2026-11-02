"""CPU faults for exact sealed-source reuse; no native process or hardware."""
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_delay_fast_derived as fast


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    def write(path,value):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value) if isinstance(value,dict) else value,encoding='utf-8')
        return path
    monkeypatch.setattr(fast.prep,'WORK',tmp_path)
    monkeypatch.setattr(fast.prep,'work_path',lambda p:Path(p).resolve())
    monkeypatch.setattr(fast,'SELF',write(tmp_path/'fast.py','sealed executor'))
    monkeypatch.setattr(fast.original,'SELF',write(tmp_path/'original.py','ordinary inspector'))
    monkeypatch.setattr(fast.hold,'SELF',write(tmp_path/'hold.py','hold provider'))
    original=write(tmp_path/'before.adf','original');leaf=write(tmp_path/'source.v','source')
    build=write(tmp_path/'build/plan.json',{'PDS':{'Executable':'pds.exe'}})
    timing=write(build.parent/'timing.tcl','timing')
    request=write(tmp_path/'request.json',{})
    work=tmp_path/'route';candidate=write(work/'input.adf','routed')
    write(work/'post-init.adf','original');write(work/'saved-route.adf','routed')
    write(work/'stage.tcl','exact');write(work/'executor-snapshot.py','hold provider')
    write(work/'stdout.log','marker');write(work/'stderr.log','')
    inputs={str(p):fast.sha(p) for p in (original,leaf,build,timing,request,fast.hold.SELF)}
    stage={'Schema':fast.hold.SCHEMA,'Target':fast.prep.TARGET,'Mode':'save-route-only',
        'SourceADF':str(original),'SourceADFSHA256':fast.sha(original),'BuildPlan':str(build),
        'BuildPlanSHA256':fast.sha(build),'BuildDiagnosticsReview':fast.ref(request),
        'Request':fast.ref(request),'InputSHA256':inputs}
    stage_path=write(work/'stage-plan.json',stage)
    result={**stage,'ExecutionPassed':True,'EDAExecuted':True,'ExitCode':0,'TimedOut':False,
        'StoppedForUnexpectedStage':False,'InputDrift':[],'Diagnostics':[],'ActualEvents':[],
        'CompletionMarker':True,'InitializationPreservedADF':True,'SavedADFReadbackMatches':True,
        'ResultADFChanged':True,'Cleanup':{'Complete':True},'RouteComparison':{'Passed':True},
        'ResultADF':{'Path':str(candidate),'SHA256':fast.sha(candidate),'Bytes':candidate.stat().st_size},
        'ResultADFSHA256':fast.sha(candidate),'StagePlanSHA256':fast.sha(stage_path),
        'Artifacts':fast.hold.artifact_hashes(work)}
    receipt=write(work/'result.json',result)
    base={Path(p):h for p,h in inputs.items()}
    base.update({work/n:h for n,h in result['Artifacts'].items()})
    for p in (receipt,fast.original.SELF):base[p]=fast.sha(p)
    calls=[]
    def source(path,watched):
        assert Path(path)==receipt;calls.append(path);watched.update(base);return result
    monkeypatch.setattr(fast.original,'bind_source',source)
    monkeypatch.setattr(fast.original,'render',lambda mode,*a:'exact '+mode+' Tcl\n')
    return {'write':write,'receipt':receipt,'result':result,'leaf':leaf,'base':base,
        'calls':calls,'authority':tmp_path/'seal.json','work':tmp_path/'export','root':tmp_path}


def seal(f):
    fast.seal_source(f['receipt'],fast.sha(f['receipt']),f['authority'])
    return fast.sha(f['authority'])


def change(f,fn):
    v=fast.read(f['authority']);fn(v);f['write'](f['authority'],v)
    return fast.sha(f['authority'])


def test_actual_full_recipe_runs_once_then_no_semantic_reparse(fixture,monkeypatch):
    f=fixture;digest=seal(f);assert len(f['calls'])==1
    monkeypatch.setattr(fast.original,'bind_source',lambda *a:pytest.fail('repeat full bind'))
    result,base,watched=fast.bind_authority(f['authority'],digest)
    assert result==f['result'] and base==f['base'] and f['leaf'] in watched


@pytest.mark.parametrize('digest',[None,'','a'*63,'g'*64])
def test_seal_and_reuse_require_explicit_sha(fixture,digest):
    f=fixture
    with pytest.raises(ValueError,match='explicit'):fast.seal_source(f['receipt'],digest,f['authority'])
    with pytest.raises(ValueError,match='explicit'):fast.bind_authority(f['authority'],digest)
    assert not f['calls']


def test_any_bound_byte_drift_rejects(fixture):
    f=fixture;digest=seal(f);f['leaf'].write_text('changed')
    with pytest.raises(ValueError):fast.bind_authority(f['authority'],digest)


def test_omitted_original_input_rejects_even_rehashed_authority(fixture):
    f=fixture;seal(f)
    def omit(v):
        for k in ('InputSHA256','BaseInputSHA256'):v[k].pop(str(f['leaf']))
    with pytest.raises(ValueError,match='original input omitted'):
        fast.bind_authority(f['authority'],change(f,omit))


def test_omitted_native_artifact_rejects(fixture):
    f=fixture;seal(f);p=str(f['receipt'].parent/'stderr.log')
    def omit(v):
        for k in ('InputSHA256','BaseInputSHA256'):v[k].pop(p)
    with pytest.raises(ValueError,match='actual artifact omitted'):
        fast.bind_authority(f['authority'],change(f,omit))


@pytest.mark.parametrize('field',['Producer','Validator','HoldProvider'])
def test_wrong_executor_or_validator_rejects(fixture,field):
    f=fixture;seal(f)
    with pytest.raises(ValueError,match='identity'):
        fast.bind_authority(f['authority'],change(f,lambda v:v[field].update(SHA256='0'*64)))


@pytest.mark.parametrize('field',['FullVerificationCompleted','HardwareAccessed','TimingAccepted'])
def test_acceptance_flags_cannot_be_relabeled(fixture,field):
    f=fixture;seal(f)
    with pytest.raises(ValueError):fast.bind_authority(f['authority'],change(f,lambda v:v.update({field:field!='FullVerificationCompleted'})))


@pytest.mark.parametrize('mode',['report','export','query'])
def test_fast_recipe_and_stage_are_exact_frozen_recipe(fixture,mode):
    f=fixture;digest=seal(f);body=None
    if mode=='query':body=f['write'](f['root']/'query.txt','read-only body')
    expected,tcl,_=fast.original.recipe(f['receipt'],fast.sha(f['receipt']),f['work'],mode,body)
    value,actual,_=fast.recipe(f['authority'],digest,f['work'],mode,body)
    assert value==expected and actual==tcl
    stage=fast.prepare(f['authority'],digest,f['work'],mode,body)
    got,_=fast.validate_prepared(stage,f['authority'],digest)
    assert {k:v for k,v in got.items() if k!='PreparedUTC'}==expected


def test_prepared_command_tampering_is_rejected(fixture):
    f=fixture;digest=seal(f);stage=fast.prepare(f['authority'],digest,f['work'],'report')
    value=fast.read(stage);value['Command'].append('extra');f['write'](stage,value)
    with pytest.raises(ValueError,match='exact recipe'):fast.validate_prepared(stage,f['authority'],digest)


def test_prepared_native_snapshot_is_exact_frozen_inspector(fixture):
    f=fixture;digest=seal(f);stage=fast.prepare(f['authority'],digest,f['work'],'report')
    (stage.parent/'executor-snapshot.py').write_text('different executor')
    with pytest.raises(ValueError,match='bytes differ'):fast.validate_prepared(stage,f['authority'],digest)
