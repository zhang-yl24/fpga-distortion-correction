"""The cache skips parsing only; changed proof inputs never reach PDS."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stage_fast as fast


def forbid(*args, **kwargs):
    raise AssertionError('repeated full proof is forbidden in a seed consumer')


@pytest.fixture
def proof(monkeypatch):
    root = fast.prep.WORK
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='_fast_', dir=root) as name:
        work = Path(name).resolve()
        assert work.is_relative_to(root.resolve())
        monkeypatch.setattr(fast.prep, 'WORK', work)
        evidence = work/'evidence'; evidence.mkdir()
        source = evidence/'input.adf'; source.write_bytes(b'proved reset bytes')
        ancestor = evidence/'ancestor.adf'; ancestor.write_bytes(b'original bytes')
        receipt = evidence/'result.json'
        receipt.write_text(json.dumps({'Schema':fast.native.physical.SCHEMA, 'Target':fast.prep.TARGET,
            'Mode':'save-reset', 'ExecutionPassed':True, 'EDAExecuted':True, 'ExitCode':0,
            'TimedOut':False, 'StoppedForUnexpectedStage':False, 'InputDrift':[], 'Diagnostics':[],
            'CompletionMarker':True, 'Cleanup':{'Complete':True}, 'ActualEvents':[],
            'InitializationPreservedADF':True, 'ApplicationNativeNamesVerified':True,
            'SavedADFReadbackMatches':True, 'ResultADFChanged':True, 'RoutesAndPlacementUnchanged':True}))
        executable = evidence/'pds_shell.exe'; executable.write_bytes(b'INERT NEVER EXECUTE')
        build = evidence/'plan.json'
        build.write_text(json.dumps({'PDS': {'Executable':str(executable)}}))
        suffix = ('if {[file exists '+fast.prep.literal(evidence/'place_route'/(fast.prep.TARGET+'_pnr.adf'))+']} {\n'
                  '    file copy '+fast.prep.literal(evidence/'place_route'/(fast.prep.TARGET+'_pnr.adf'))+' '+fast.prep.literal(evidence/'pre-sta-final.adf')+'\n}\n'
                  'report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n')
        (evidence/'timing.tcl').write_text('pnr -optimize_multi_corner_timing -fix_hold_violation\n'+suffix, newline='\n')
        def full_source(path, watched):
            assert path == receipt or str(path) == str(receipt)
            for p in (source, ancestor, receipt, executable, build, evidence/'timing.tcl'):
                fast.native.add(watched, p)
            return {'ResultADF': {'Path':str(source)}, 'ResultADFSHA256':fast.sha(source),
                    'BuildPlan':str(build), 'SourceADF':str(ancestor), 'SourceADFSHA256':fast.sha(ancestor),
                    'OriginalSourceADF':str(ancestor), 'OriginalSourceADFSHA256':fast.sha(ancestor)}
        # The expensive source semantic proof alone is mocked. The unchanged
        # original recipe, prepared-byte checks and seed handoff run for real.
        monkeypatch.setattr(fast.native, 'bind_source_receipt', full_source)
        native_recipe = fast.native.recipe
        original = fast.native.prepare(receipt, work/'original', 'export', None, 120)
        seed = work/'seed.json'
        full = fast.native.validate_prepared
        calls = []
        def validate(path):
            calls.append(path)
            return full(path)
        monkeypatch.setattr(fast.native, 'validate_prepared', validate)
        fast.seed_from_full(original, fast.sha(original), seed)
        assert calls == [original]
        seed_sha = fast.sha(seed)
        monkeypatch.setattr(fast.native, 'validate_prepared', forbid)
        monkeypatch.setattr(fast.native, 'recipe', forbid)
        popen = Mock(side_effect=AssertionError('no actual PDS permitted'))
        monkeypatch.setattr(fast.subprocess, 'Popen', popen)
        yield SimpleNamespace(work=work, source=source, ancestor=ancestor, receipt=receipt,
                              executable=executable, original=original, seed=seed, sha=seed_sha, popen=popen,
                              native_recipe=native_recipe)
        assert work.resolve().is_relative_to(root.resolve())


def test_new_query_keeps_exact_native_schema_without_reparsing(proof):
    body = proof.work/'query.tcl'; body.write_bytes(b'puts {TEST_QUERY}\nget_ports -regexp {.*}\n')
    path = fast.prepare(proof.seed, proof.sha, proof.work/'query', 'query', body, 120)
    plan, _ = fast.validate(proof.seed, proof.sha, path)
    assert plan['Schema'] == fast.native.SCHEMA and plan['ExpectedActualStages'] == []
    assert plan['SourceADFSHA256'] == fast.sha(proof.source)
    assert plan['InputSHA256'][str(body)] == fast.sha(body)
    assert b'\r' not in (path.parent/'stage.tcl').read_bytes()
    assert (path.parent/'dummy.v').read_bytes() == fast.native.physical.DUMMY.encode('ascii')
    assert fast.sha(path.parent/'executor-snapshot.py') == fast.sha(fast.native.SELF)
    proof.popen.assert_not_called()


@pytest.mark.parametrize('mode', ['report', 'export'])
def test_other_readonly_modes_preserve_the_frozen_render(proof, mode):
    path = fast.prepare(proof.seed, proof.sha, proof.work/mode, mode, None, 300)
    value, _ = fast.validate(proof.seed, proof.sha, path)
    assert value['ExpectedActualStages'] == fast.native.expected_stages(mode)
    assert all(value[k] is False for k in fast.FALSE_FLAGS)


@pytest.mark.parametrize('which', ['source', 'ancestor', 'executable', 'receipt', 'original'])
def test_changed_proof_byte_cannot_reach_execution(proof, which):
    plan = fast.prepare(proof.seed, proof.sha, proof.work/'fresh', 'report')
    path = getattr(proof, which)
    path.write_bytes(path.read_bytes()+b'changed')
    with pytest.raises(ValueError):
        fast.execute(proof.seed, proof.sha, plan)
    proof.popen.assert_not_called()


def test_wrong_explicit_seed_anchor_is_rejected(proof):
    with pytest.raises(ValueError, match='seed SHA'):
        fast.bind_seed(proof.seed, '0'*64)


@pytest.mark.parametrize('key', ['AuthorityInputSHA256', 'ValidatedInputSHA256', 'ToolSHA256'])
def test_dropped_closure_rejected_even_with_new_manifest_hash(proof, key):
    value = fast.read(proof.seed)
    if key == 'ToolSHA256':
        value[key].pop(str(fast.SELF))
    else:
        value[key].pop(str(proof.source))
    proof.seed.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        fast.bind_seed(proof.seed, fast.sha(proof.seed))


@pytest.mark.parametrize('key,value', [('FullValidationCompleted',False), ('HardwareReleaseAllowed',True),
                                     ('Schema','historical-seed'), ('EDAExecuted',True)])
def test_seed_claims_cannot_replace_completed_validation(proof, key, value):
    seed = fast.read(proof.seed); seed[key] = value
    proof.seed.write_text(json.dumps(seed))
    with pytest.raises(ValueError):
        fast.bind_seed(proof.seed, fast.sha(proof.seed))


@pytest.mark.parametrize('maximum', [119, 301, True, 300.0])
def test_deadline_cannot_expand(proof, maximum):
    with pytest.raises(ValueError, match='deadline'):
        fast.prepare(proof.seed, proof.sha, proof.work/'fresh', 'report', maximum=maximum)
    assert not (proof.work/'fresh').exists()


def test_arbitrary_query_command_is_rejected(proof):
    body = proof.work/'injected.tcl'; body.write_bytes(b'exec injected\n')
    with pytest.raises(ValueError, match='unsupported read-only query'):
        fast.prepare(proof.seed, proof.sha, proof.work/'query', 'query', body)
    assert not (proof.work/'query').exists()


@pytest.mark.parametrize('name', ['input.adf','stage.tcl','dummy.v','executor-snapshot.py'])
def test_prepared_byte_changes_fail_before_pds(proof, name):
    path = fast.prepare(proof.seed, proof.sha, proof.work/'fresh', 'report')
    p = path.parent/name; p.write_bytes(p.read_bytes()+b'changed')
    with pytest.raises(ValueError):fast.execute(proof.seed, proof.sha, path)
    proof.popen.assert_not_called()


def test_reused_stage_is_rejected(proof):
    path = fast.prepare(proof.seed, proof.sha, proof.work/'fresh', 'report')
    (path.parent/'stdout.log').write_bytes(b'previous execution')
    with pytest.raises(ValueError, match='reused'):
        fast.execute(proof.seed, proof.sha, path)
    proof.popen.assert_not_called()


@pytest.mark.parametrize('field,value', [('SourceADFSHA256','0'*64), ('ExpectedActualStages',['Place and Route']),
                                     ('Command',['injected.exe']), ('HardwareAccessed',True)])
def test_mutated_plan_envelope_cannot_execute(proof, field, value):
    path = fast.prepare(proof.seed, proof.sha, proof.work/'fresh', 'report')
    plan = fast.read(path); plan[field] = value; path.write_text(json.dumps(plan))
    with pytest.raises(ValueError, match='plan differs'):
        fast.execute(proof.seed, proof.sha, path)
    proof.popen.assert_not_called()


def test_native_success_still_requires_marker_and_no_errors(proof, monkeypatch):
    monkeypatch.setattr(fast, 'os', SimpleNamespace(name='nt'))
    def process(command, **kwargs):
        kwargs['stdout'].write((fast.native.MARKER+'\n   ERROR: native failed\n').encode())
        return SimpleNamespace(pid=99999, poll=lambda:0)
    monkeypatch.setattr(fast.subprocess, 'Popen', process)
    path = fast.prepare(proof.seed, proof.sha, proof.work/'fresh', 'report')
    value = fast.execute(proof.seed, proof.sha, path)
    assert value['ExitCode'] == 0 and value['ExecutionPassed'] is False
    assert value['Diagnostics']


def test_successful_mock_keeps_original_receipt_contract(proof, monkeypatch):
    monkeypatch.setattr(fast, 'os', SimpleNamespace(name='nt'))
    def process(command, **kwargs):
        kwargs['stdout'].write((fast.native.MARKER+'\n').encode())
        assert kwargs['shell'] is False
        return SimpleNamespace(pid=99999, poll=lambda:0)
    monkeypatch.setattr(fast.subprocess, 'Popen', process)
    path = fast.prepare(proof.seed, proof.sha, proof.work/'fresh', 'report')
    value = fast.execute(proof.seed, proof.sha, path)
    fast.native.receipt_flags(value)
    assert value['FastExecutionSeed'] == fast.binding(proof.seed)
    assert value['InputDrift'] == [] and value['InputADFUnchanged']
    assert value['Cleanup']['DescendantLivenessIndependentlyVerified'] is False


def test_failed_full_validator_writes_no_seed(proof, monkeypatch):
    monkeypatch.setattr(fast.native, 'validate_prepared', Mock(side_effect=ValueError('unproved source')))
    output = proof.work/'bad-seed.json'
    with pytest.raises(ValueError, match='unproved source'):
        fast.seed_from_full(proof.original, fast.sha(proof.original), output)
    assert not output.exists()


def test_bootstrap_calls_actual_full_recipe_once_and_never_revalidates(proof, monkeypatch):
    calls = []
    def full(*args):
        calls.append(args)
        return proof.native_recipe(*args)
    monkeypatch.setattr(fast.native, 'recipe', full)
    output = proof.work/'bootstrap-seed.json'
    result = fast.bootstrap(proof.receipt, fast.sha(proof.receipt), proof.work/'bootstrap', output, 120)
    assert len(calls) == 1 and result['FullValidationCompleted'] and result['Prepared']
    monkeypatch.setattr(fast.native, 'recipe', forbid)
    plan, _ = fast.validate(output, result['Seed']['SHA256'], Path(result['StagePlan']['Path']))
    assert plan['Schema'] == fast.native.SCHEMA and plan['ExpectedActualStages'] == ['Report Timing','Generate Netlist']
    proof.popen.assert_not_called()


def test_bootstrap_source_failure_does_not_create_files(proof, monkeypatch):
    monkeypatch.setattr(fast.native, 'recipe', Mock(side_effect=ValueError('unproved reset chain')))
    output = proof.work/'bootstrap-seed.json'
    with pytest.raises(ValueError, match='unproved reset'):
        fast.bootstrap(proof.receipt, fast.sha(proof.receipt), proof.work/'bootstrap', output)
    assert not output.exists() and not (proof.work/'bootstrap').exists()


def test_bootstrap_copy_corruption_cannot_be_sealed(proof, monkeypatch):
    monkeypatch.setattr(fast.native, 'recipe', proof.native_recipe)
    copyfile = fast.shutil.copyfile
    def corrupt(src,dst):
        copyfile(src,dst)
        if Path(dst).name == 'input.adf':Path(dst).write_bytes(b'bad copy')
    monkeypatch.setattr(fast.shutil,'copyfile',corrupt)
    output = proof.work/'bootstrap-seed.json'
    with pytest.raises(ValueError, match='readback'):
        fast.bootstrap(proof.receipt, fast.sha(proof.receipt), proof.work/'bootstrap', output)
    assert not output.exists()


@pytest.mark.parametrize('reason', ['timeout','unexpected'])
def test_running_process_is_stopped_for_deadline_or_wrong_stage(proof, monkeypatch, reason):
    monkeypatch.setattr(fast, 'os', SimpleNamespace(name='nt'))
    class Process:
        pid = 99999
        code = None
        def poll(self):return self.code
        def wait(self, timeout):return None
    process = Process()
    def launch(command, **kwargs):
        if reason == 'unexpected':
            kwargs['stdout'].write(b'Process "Place and Route" started.\n')
            kwargs['stdout'].flush()
        return process
    monkeypatch.setattr(fast.subprocess, 'Popen', launch)
    def stop(proc, work, reason):
        assert proc is process
        proc.code = -15
        return {'Complete':True, 'OwnedPID':proc.pid}
    cleanup = Mock(side_effect=stop)
    monkeypatch.setattr(fast.diagnostic.cleanup, 'stop_owned_tree', cleanup)
    times = iter([0, 301, 302] if reason == 'timeout' else [0, 1, 2])
    monkeypatch.setattr(fast.time, 'monotonic', lambda:next(times))
    path = fast.prepare(proof.seed, proof.sha, proof.work/'fresh', 'report')
    value = fast.execute(proof.seed, proof.sha, path)
    assert value['ExecutionPassed'] is False
    assert value['TimedOut'] if reason == 'timeout' else value['StoppedForUnexpectedStage']
    cleanup.assert_called_once()
