"""CPU-only reset-save boundaries; no PDS process is started."""
from copy import deepcopy
import json
from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import run_camera_vga_upright_physical as tool


def queries():
    source = 'current_reset/q_reg[0]/CLK'
    targets = ['current_reset/sync[0]/RS', 'current_reset/sync[1]/RS']
    return [{'Source':source, 'Targets':targets, 'Family':'entry_rdc', 'EntryRDC':True,
             'FromRegex':'^('+re.escape(source)+')$',
             'ToRegex':'^('+'|'.join(re.escape(n) for n in targets)+')$',
             'ExpectedFromCount':1, 'ExpectedTargetCount':2,
             'ExpectedNativeFromNames':['t:'+source], 'ExpectedNativeToNames':['t:'+n for n in targets]}]


def proof():
    return {'Schema':tool.audit.PROOF_SCHEMA, 'Target':tool.prep.TARGET, 'Status':'pass',
            **{k:True for k in tool.PROOF_TRUE}, **{k:False for k in tool.PROOF_FALSE}}


def test_proof_accepts_audited_unapproved_diagnostic_only():
    tool.proof_flags(proof())


def test_graph_adapter_descriptions_differ_but_semantics_must_match():
    actual = {'HeaderOnlyAdapter':'camera_vga_output_top to board1080_top for reused strict V_* parser',
              'Status':'pass', 'InternalFunctionalTargetsVerified':17}
    claimed = {**actual, 'HeaderOnlyAdapter':'upright top declaration token to camera parser top, then board parser top; no primitive/net/pin rewrite'}
    tool.graph_semantics(actual, claimed)
    with pytest.raises(ValueError, match='graph differs'):
        tool.graph_semantics(actual, {**claimed, 'InternalFunctionalTargetsVerified':18})
    with pytest.raises(ValueError, match='adapter'):
        tool.graph_semantics(actual, {**claimed, 'HeaderOnlyAdapter':'unverified rewrite'})


@pytest.mark.parametrize('key', tool.PROOF_TRUE+tool.PROOF_FALSE)
def test_proof_rejects_missing_scope_and_overclaimed_approval(key):
    p = proof(); p[key] = not p[key]
    with pytest.raises(ValueError):
        tool.proof_flags(p)


def test_no_historical_endpoint_count_or_names_are_required():
    commands = tool.exact_commands(queries())
    assert len(commands) == 1 and 'current_reset' in commands[0]
    assert 'set_clock_groups' not in commands[0]


@pytest.mark.parametrize('mutation', ('regex', 'count', 'native_name', 'duplicate', 'unsafe', 'unsorted'))
def test_exact_scope_rejects_broadened_or_ambiguous_names(mutation):
    q = queries(); row = q[0]
    if mutation == 'regex':row['ToRegex'] = '.*'
    if mutation == 'count':row['ExpectedTargetCount'] = 3
    if mutation == 'native_name':row['ExpectedNativeToNames'][0] = 't:other/RS'
    if mutation == 'duplicate':q.append(deepcopy(row))
    if mutation == 'unsafe':row['Source'] = 'unsafe};exec injected'
    if mutation == 'unsorted':row['Targets'].reverse()
    with pytest.raises(ValueError):
        tool.exact_commands(q)


def test_render_initializes_once_then_saves_without_second_sta():
    text = tool.render(tool.exact_commands(queries()), Path('D:/diagnostic/fresh-copy'))
    assert text.count('mpnr_report_timing ') == 1
    assert text.index('mpnr -input') < text.index(tool.INIT) < text.index('post-init.adf')
    assert text.index('post-init.adf') < text.index('set_false_path ') < text.index('save_adif')
    assert text.index('save_adif') < text.index('saved-reset.adf') < text.index(tool.MARKER)
    for forbidden in ('manual_route', 'unroute ', 'compile ', 'gen_netlist ', 'generate_bitstream', 'cfg_program', 'exec '):
        assert forbidden not in text


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    project = tmp_path/'distortion'; workroot = project/'work'; workroot.mkdir(parents=True)
    monkeypatch.setattr(tool.prep, 'PROJECT', project)
    monkeypatch.setattr(tool.prep, 'WORK', workroot)
    evidence = workroot/'evidence'; evidence.mkdir()
    source = evidence/'original.adf'; source.write_bytes(b'original native ADF bytes')
    build = evidence/'plan.json'; build.write_text('{}')
    proofpath = evidence/'proof.json'; proofpath.write_text('{}')
    fdc = evidence/'proposed-scope.fdc'; fdc.write_text('\n'.join(tool.exact_commands(queries()))+'\n')
    executable = evidence/'pds_shell.exe'; executable.write_bytes(b'not executable; never run')
    watched = {p:tool.sha(p) for p in (source, build, proofpath, fdc, executable)}
    def bound(*args):
        assert not tool.inspect.drift(watched)
        return ({'PDS':{'Executable':str(executable)}}, source,
                {'SourceADFSHA256':tool.sha(source), 'NativeQueries':queries()}, fdc, tool.exact_commands(queries()), dict(watched))
    monkeypatch.setattr(tool, 'bind_proof', bound)
    stage = tool.prepare(build, proofpath, tool.sha(proofpath), workroot/'reset-save-test', 120)
    return stage, source


def test_prepare_preserves_original_and_validate_is_cpu_only(prepared, monkeypatch):
    stage, source = prepared
    def forbidden(*args, **kwargs):raise AssertionError('Native process must never start')
    monkeypatch.setattr(tool.subprocess, 'Popen', forbidden)
    value, watched = tool.validate_prepared(stage)
    assert source.read_bytes() == b'original native ADF bytes'
    assert (stage.parent/'input.adf').read_bytes() == source.read_bytes()
    assert stage.parent/'input.adf' not in watched
    assert source in watched and value['TimingAccepted'] is False
    assert value['HardwareReleaseAllowed'] is False and value['TimingExceptionApproved'] is False


@pytest.mark.parametrize('file', ('stage.tcl', 'input.adf', 'applied-scope.fdc', 'executor-snapshot.py', 'dummy.v'))
def test_prepared_artifact_tampering_is_rejected(prepared, file):
    stage, _ = prepared
    with (stage.parent/file).open('ab') as stream:stream.write(b'TAMPER')
    with pytest.raises(ValueError):tool.validate_prepared(stage)


def test_used_stage_is_never_reexecuted(prepared):
    stage, _ = prepared
    (stage.parent/'result.json').write_text('{}')
    with pytest.raises(ValueError, match='reused or contaminated'):tool.validate_prepared(stage)


def test_native_zero_without_saved_copy_is_not_success():
    good = {'ExitCode':0, 'EDAExecuted':True, 'TimedOut':False, 'StoppedForUnexpectedStage':False,
            'InputDrift':[], 'Diagnostics':[], 'ActualEvents':[], 'CompletionMarker':True,
            'InitializationPreservedADF':True, 'SavedADFReadbackMatches':True, 'ResultADFChanged':True,
            'ApplicationNativeNamesVerified':True,
            'Cleanup':{'Complete':True}}
    assert tool.execution_ok(good)
    for key in ('InitializationPreservedADF', 'SavedADFReadbackMatches', 'ResultADFChanged', 'CompletionMarker', 'ApplicationNativeNamesVerified'):
        altered = dict(good); altered[key] = False
        assert not tool.execution_ok(altered)
    assert not tool.execution_ok({'ExitCode':0})
    altered = dict(good); altered['ActualEvents'] = [('Place and Route', 'started')]
    assert not tool.execution_ok(altered)


def test_explicit_proof_hash_is_required(tmp_path, monkeypatch):
    monkeypatch.setattr(tool.prep, 'WORK', tmp_path)
    parent = tmp_path/'proof-dir'; parent.mkdir()
    p = parent/'proof.json'; p.write_text(json.dumps(proof()))
    with pytest.raises(ValueError, match='proof SHA'):
        tool.bind_proof(tmp_path/'plan.json', p, '0'*64)
