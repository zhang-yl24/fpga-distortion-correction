"""Focused finished native evidence faults; only temporary files are mutated."""
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_delay_sealed_receipts as s


@pytest.fixture
def done(tmp_path,monkeypatch):
    def write(p,v):
        p.write_text(json.dumps(v) if isinstance(v,dict) else v,encoding='utf-8',newline='\n')
        return p
    monkeypatch.setattr(s.prep,'WORK',tmp_path)
    monkeypatch.setattr(s.prep,'work_path',lambda p:Path(p))
    monkeypatch.setattr(s,'canonical',lambda p,*a:Path(p).resolve())
    work=tmp_path/'native';work.mkdir()
    original=write(tmp_path/'original.py','frozen inspector')
    monkeypatch.setattr(s.original,'SELF',original)
    authority=write(tmp_path/'authority.json','actual full seal')
    watched={authority:s.sha(authority),original:s.sha(original)}
    write(work/'input.adf','candidate');write(work/'stage.tcl','native Tcl\n')
    write(work/'executor-snapshot.py','frozen inspector')
    write(work/'dummy.v','module physical_dummy(input a, output y); assign y=a; endmodule\n')
    write(work/'stdout.log',s.MARKER+'\n');write(work/'stderr.log','')
    report=write(work/'current.rtr','fresh native report')
    timing={'Path':str(report),'SHA256':s.sha(report),'Bytes':report.stat().st_size}
    expected={'Schema':s.SCHEMA,'Target':s.prep.TARGET,'Mode':'report','WorkDirectory':str(work),
        'SourceReceipt':{'Path':'actual-route.json','SHA256':'a'*64},'QueryBody':None,'MaximumSeconds':300,
        'SourceADFSHA256':s.sha(work/'input.adf'),'ExpectedActualStages':[],
        'HardwareAccessed':False,'BitstreamRequested':False,'TimingAccepted':False,
        'HardwareReleaseAllowed':False,'OpticalCorrectionAccepted':False}
    stage=write(work/'stage-plan.json',{**expected,'PreparedUTC':'recorded'})
    v={**s.physical.read(stage),'StagePlanSHA256':s.sha(stage),'EDAExecuted':True,'ExecutionPassed':True,
        'ExitCode':0,'TimedOut':False,'StoppedForUnexpectedStage':False,'InputDrift':[],'Diagnostics':[],
        'CompletionMarker':True,'InputADFUnchanged':True,'Cleanup':{'Complete':True},'TimingReport':timing,
        'ActualEvents':[],'Artifacts':{p.name:s.sha(p) for p in work.iterdir() if p.suffix in ('.tcl','.log','.rtr','.v','.gnr','.txt','.fdc')}}
    path=write(work/'result.json',v)
    monkeypatch.setattr(s.fast,'recipe',lambda *a:(expected,'native Tcl\n',dict(watched)))
    monkeypatch.setattr(s.inspect,'timing_report',lambda *a:timing)
    monkeypatch.setattr(s.diagnostic,'stage_events',lambda *a:[])
    monkeypatch.setattr(s,'scan_diagnostics',lambda *a:[])
    return {'value':v,'path':path,'authority':authority,'write':write,'watched':watched}


def bind(f):return s.bind_receipt(f['path'],f['authority'],s.sha(f['authority']))


def test_regular_finished_receipt_remains_compatible(done):
    v,w=bind(done);assert v==done['value'] and done['path'] in w


@pytest.mark.parametrize('field,bad',[('SourceReceipt',{}),('ExecutionPassed',False),('InputDrift',['changed']),
    ('Diagnostics',['C: changed']),('CompletionMarker',False),('InputADFUnchanged',False),('TimingReport',{})])
def test_native_receipt_cannot_relabel_actual_evidence(done,field,bad):
    done['value'][field]=bad;done['write'](done['path'],done['value'])
    with pytest.raises(ValueError):bind(done)


def test_actual_native_artifact_omission_rejects(done):
    done['value']['Artifacts'].pop('current.rtr');done['write'](done['path'],done['value'])
    with pytest.raises(ValueError,match='inventory differs'):bind(done)


def test_new_critical_diagnostic_rejects(done,monkeypatch):
    monkeypatch.setattr(s,'scan_diagnostics',lambda *a:['C: actual critical'])
    with pytest.raises(ValueError,match='critical'):bind(done)


def test_fast_runtime_provenance_requires_complete_exact_closure(done):
    f=done;w=dict(f['watched']);work=f['path'].parent
    for n in ('input.adf','stage.tcl','executor-snapshot.py','stage-plan.json','dummy.v'):w[work/n]=s.sha(work/n)
    f['value'].update(ExecutionProvider=s.fast.ref(s.fast.SELF),SourceAuthority=s.fast.ref(f['authority']),
        SealedValidationClosure={str(p):h for p,h in w.items()})
    f['write'](f['path'],f['value']);bind(f)
    f['value']['SealedValidationClosure'].pop(str(work/'input.adf'));f['write'](f['path'],f['value'])
    with pytest.raises(ValueError,match='runtime closure'):bind(f)
