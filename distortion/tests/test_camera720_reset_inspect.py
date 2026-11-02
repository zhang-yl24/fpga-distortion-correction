"""CPU checks for isolated derived-report/export stages and receipt identity."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_reset_inspect as tool

BASE = tool.prep.WORK/'cpu-build-never-executed'
WORK = tool.prep.WORK/'derived-inspection-never-executed'


def test_report_initializes_once_and_emits_only_a_readonly_route_dump():
    text = tool.render('report', '', BASE, WORK)
    assert text.count('mpnr_report_timing ') == 1
    assert text.index(tool.inspect.INIT) < text.index('.switch_db -route') < text.index(tool.MARKER)
    for forbidden in ('save_adif', 'set_false_path', 'manual_route', 'gen_netlist', 'generate_bitstream'):
        assert forbidden not in text


def test_export_has_one_report_and_native_final_netlist_only():
    payload = tool.prep.make_tcl([], BASE/'fixture.fdc', BASE/'fixture.rcf', BASE).encode('ascii')
    text = tool.render('export', payload.decode('ascii'), BASE, WORK)
    assert text.count('report_timing -force_to_run') == 1
    assert text.count('gen_netlist -force_to_run') == 1
    assert tool.inspect.MARKER not in text and tool.MARKER in text
    assert 'save_adif' not in text


@pytest.mark.parametrize('body', ['save_adif', 'set_false_path -from {a} -to {b}',
                                 'manual_route -net {_N127}', tool.inspect.INIT, 'puts {'+tool.MARKER+'}'])
def test_derived_query_reuses_strict_readonly_grammar(body):
    with pytest.raises(ValueError):tool.render('query', '', BASE, WORK, body)


def clean_receipt(mode='report'):
    stages = tool.expected_stages(mode)
    return {'Schema':tool.SCHEMA, 'Target':tool.prep.TARGET, 'Mode':mode, 'ExecutionPassed':True,
        'ExitCode':0, 'TimedOut':False, 'StoppedForUnexpectedStage':False, 'InputDrift':[], 'Diagnostics':[],
        'CompletionMarker':True, 'InputADFUnchanged':True, 'Cleanup':{'Complete':True}, 'EDAExecuted':True,
        'ExpectedActualStages':stages, 'ActualEvents':[[s,e] for s in stages for e in ('started','done')],
        'HardwareAccessed':False, 'BitstreamRequested':False, 'TimingAccepted':False, 'HardwareReleaseAllowed':False,
        'NativeNetlistWithFFloc':True if mode=='export' else None,
        'OpticalCorrectionAccepted':False,'ExceptionEffectsAccepted':False}


@pytest.mark.parametrize('mode', ['query','report','export'])
def test_clean_mode_receipt_schema_is_explicit(mode):tool.receipt_flags(clean_receipt(mode))


@pytest.mark.parametrize('field,bad', [('Source','irrelevant'), ('InputDrift',['changed']), ('Cleanup',{}),
    ('InputADFUnchanged',False), ('HardwareReleaseAllowed',True), ('ActualEvents',[['Place and Route','done']]),
    ('Schema',tool.inspect.SCHEMA)])
def test_zero_exit_cannot_replace_clean_receipt(field,bad):
    value = clean_receipt()
    if field=='Source':value={'ExitCode':0}
    else:value[field]=bad
    with pytest.raises(ValueError):tool.receipt_flags(value)


def test_unsupported_mutation_schema_is_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr(tool.prep,'WORK',tmp_path)
    p=tmp_path/'result.json';p.write_text('{"Schema":"old-camera-authority"}')
    with pytest.raises(ValueError,match='unsupported'):tool.bind_source_receipt(p,{})


def test_prepare_and_validate_use_exact_lf_bytes(tmp_path,monkeypatch):
    project=tmp_path/'distortion';root=project/'work';root.mkdir(parents=True)
    monkeypatch.setattr(tool.prep,'PROJECT',project);monkeypatch.setattr(tool.prep,'WORK',root)
    evidence=root/'evidence';evidence.mkdir()
    source=evidence/'result.adf';source.write_bytes(b'derived bytes')
    receipt=evidence/'result.json';receipt.write_text('{}')
    plan=evidence/'plan.json';plan.write_text(json.dumps({'PDS':{'Executable':str(evidence/'pds_shell.exe')}}))
    (evidence/'timing.tcl').write_bytes(b'not used in report mode')
    original=evidence/'original.adf';original.write_bytes(b'original bytes')
    def bound(path,watched):
        for p in (source,receipt,plan,original):watched[p]=tool.sha(p)
        return {'ResultADF':{'Path':str(source)},'ResultADFSHA256':tool.sha(source),'BuildPlan':str(plan),
                'SourceADF':str(original),'SourceADFSHA256':tool.sha(original),
                'OriginalSourceADF':str(original),'OriginalSourceADFSHA256':tool.sha(original)}
    monkeypatch.setattr(tool,'bind_source_receipt',bound)
    monkeypatch.setattr(tool,'add',lambda w,p,expected=None,pds=None:w.setdefault(Path(p),tool.sha(p)) or Path(p))
    path=tool.prepare(receipt,root/'fresh','report',None,120)
    assert (path.parent/'dummy.v').read_bytes()==tool.physical.DUMMY.encode('ascii')
    assert b'\r' not in (path.parent/'stage.tcl').read_bytes()
    value,_=tool.validate_prepared(path)
    assert value['Schema']==tool.SCHEMA and value['SourceADFSHA256']==tool.sha(source)
    with (path.parent/'input.adf').open('ab') as f:f.write(b'drift')
    with pytest.raises(ValueError,match='artifact drift'):tool.validate_prepared(path)


@pytest.mark.parametrize('schema', ['camera-vga-upright-route-reset-application-v1',
                                  'camera-vga-calibrated-route-reset-application-v1',
                                  'camera-vga-upright-diagnostic-reset-application-v1'])
def test_route_and_old_candidate_receipts_never_dispatch(tmp_path, monkeypatch, schema):
    monkeypatch.setattr(tool.prep, 'WORK', tmp_path)
    p = tmp_path/'result.json'; p.write_text(json.dumps({'Schema':schema}))
    with pytest.raises(ValueError, match='unsupported'):
        tool.bind_source_receipt(p,{})
