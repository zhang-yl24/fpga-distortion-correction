"""CPU checks for the isolated upright closure and fail-closed executor."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import prepare_camera_vga_upright as prep
import run_camera_vga_upright_diagnostic as runner


def test_real_closure_replaces_only_two_sources():
    r = prep.validate_sources()
    old = prep.baseline.validate(prep.PROJECT)
    assert set(old['Sources']) - set(r['Sources']) == set(prep.REPLACE)
    assert set(r['Sources']) - set(old['Sources']) == set(prep.REPLACE.values())
    assert len(r['Sources']) == 108
    assert len(r['Sources']) + 1 == 109
    assert r['UnchangedSourceSHA256'] == {
        name: digest for name, digest in old['SourceSHA256'].items()
        if name not in prep.REPLACE}
    assert r['ConstraintSHA256'] == old['ConstraintSHA256']
    assert prep.OLD_INIT not in r['ExplicitDesigns']
    assert prep.INIT in r['ExplicitDesigns']


def test_real_recipe_is_upright_without_inherited_physical_repairs():
    work = prep.WORK / 'cpu-recipe-never-executed'
    plan, files, tcl = prep.recipe(work)
    assert len(files) == 109
    assert len(plan['CompiledInputs']) == 109
    assert plan['Target'] == 'camera_vga_upright_top'
    assert set(plan['InputSHA256']) >= {
        prep.MANIFEST, prep.RUNNER, 'tools/prepare_camera_vga_upright.py',
        prep.TOP, prep.INIT, prep.baseline.TOP, prep.OLD_INIT}
    assert plan['EDAExecuted'] is False and plan['HardwareAccessed'] is False
    assert plan['TimingAccepted'] is False
    text = tcl.decode('ascii')
    assert 'compile -top_module camera_vga_upright_top\n' in text
    assert '-max_path 1000 -nworst 4 -report_exception TRUE' in text
    for forbidden in ('manual_route', 'unroute', 'set_false_path', 'generate_bitstream',
                      '_N101', '_N188', '_N78', 'cfg_program'):
        assert forbidden not in text
    assert all(Path(name).suffix != '.vh' for name in plan['ExplicitDesigns'])
    for expanded in plan['IDFExpandedSourcesNotAdded']:
        assert str(work / 'compiled' / expanded).replace('\\', '/') not in plan['ExplicitDesigns']


@pytest.mark.parametrize('change', [
    lambda s: s.replace('640', '800', 1),
    lambda s: s.replace('ov5640_cadence_upright_init', 'ov5640_cadence_trial_init'),
    lambda s: s.replace('camera_vga_upright_top', 'another_top', 1),
])
def test_top_semantic_change_rejected(change):
    old = (prep.PROJECT / prep.baseline.TOP).read_text()
    new = (prep.PROJECT / prep.TOP).read_text()
    assert change(new) != new
    with pytest.raises(ValueError, match='upright top differs'):
        prep.validate_top(old, change(new))


@pytest.mark.parametrize('path', [
    lambda: prep.PROJECT / 'work/camera-vga-output/new',
    lambda: prep.WORK / 'nested' / 'stage',
    lambda: prep.WORK / 'bad;command',
])
def test_only_exact_upright_root(path):
    with pytest.raises(ValueError, match='direct upright'):
        prep.work_path(path())


@pytest.fixture
def stage(tmp_path, monkeypatch):
    # Tiny deterministic recipe isolates validator branches; real recipe checked above.
    monkeypatch.setattr(prep, 'WORK', tmp_path.parent)
    monkeypatch.setattr(prep, 'PROJECT', tmp_path)
    source = tmp_path / 'source.txt'
    source.write_bytes(b'bound source')
    pds = tmp_path / 'pds_shell.exe'
    pds.write_bytes(b'CPU fixture; never launched')
    compiled = tmp_path / 'compiled' / 'design.v'
    compiled.parent.mkdir()
    compiled.write_bytes(b'module design; endmodule\n')
    tcl = b'compile -top_module fixture\n'
    (tmp_path / 'timing.tcl').write_bytes(tcl)
    expected = {
        'Schema': prep.SCHEMA, 'Target': prep.TARGET,
        'MaximumSecondsForExternalExecutor': 1800,
        'PDS': {'Executable': str(pds), 'ExecutableSHA256': prep.sha(pds)},
        'InputSHA256': {}, 'Tcl': {'SHA256': prep.sha(tmp_path / 'timing.tcl')},
        'TimingAccepted': False, 'CommandToRunSeparately': ['bound-command'],
    }
    # Sources/executable live outside the fresh stage's exact three-entry inventory.
    outside = tmp_path.parent / (tmp_path.name + '-inputs')
    outside.mkdir()
    moved_source, moved_pds = outside / source.name, outside / pds.name
    source.replace(moved_source)
    pds.replace(moved_pds)
    expected['PDS']['Executable'] = str(moved_pds)
    expected['InputSHA256'] = {str(moved_source): prep.sha(moved_source)}
    path = tmp_path / 'plan.json'
    path.write_text(json.dumps({**expected, 'PreparedUTC': '2026-10-31T00:00:00Z'}))
    monkeypatch.setattr(prep, 'recipe', lambda *a: (expected, {compiled: compiled_payload}, tcl))
    compiled_payload = compiled.read_bytes()
    return path, compiled, expected


def test_validator_accepts_bound_recipe_without_execution(stage):
    path, _, _ = stage
    context = runner.validate_plan(path, 30)
    assert context['MaximumSeconds'] == 30
    assert not (path.parent / 'execution-start.json').exists()


@pytest.mark.parametrize('mutation', [
    lambda p: p.update(Target='camera_vga_output_top'),
    lambda p: p.update(Schema='independent-camera-vga-output-diagnostic-preparation-v1'),
    lambda p: p.update(TimingAccepted=True),
    lambda p: p.update(CommandToRunSeparately=['other-command']),
    lambda p: p.update(InputSHA256={}),
    lambda p: p.update(UnexpectedAcceptance=True),
])
def test_validator_rejects_plan_mutations(stage, mutation):
    path, _, _ = stage
    plan = json.loads(path.read_text())
    mutation(plan)
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError):
        runner.validate_plan(path)


@pytest.mark.parametrize('mutation', ['tcl', 'compiled', 'injected', 'reused'])
def test_validator_rejects_artifact_mutations(stage, mutation):
    path, compiled, _ = stage
    if mutation == 'tcl':
        (path.parent / 'timing.tcl').write_bytes(b'generate_bitstream\n')
    elif mutation == 'compiled':
        compiled.write_bytes(b'changed source')
    elif mutation == 'injected':
        (compiled.parent / 'injected.v').write_bytes(b'module injected; endmodule')
    else:
        (path.parent / 'execution-start.json').write_text('{}')
    with pytest.raises(ValueError):
        runner.validate_plan(path)


@pytest.mark.parametrize('maximum', [29, 1801, True])
def test_validator_rejects_invalid_deadline(stage, maximum):
    with pytest.raises(ValueError, match='deadline'):
        runner.validate_plan(stage[0], maximum)


def test_event_parser_exposes_unexpected_native_stage():
    text = 'Process "Compile" started.\nProcess "Compile" done.\nProcess "Generate Bitstream" started.\n'
    assert runner.stage_events(text) == [
        ('Compile', 'started'), ('Compile', 'done'), ('Generate Bitstream', 'started')]


def test_snapshot_checks_database_bytes_without_timing_acceptance(tmp_path):
    assert runner.snapshot(tmp_path)['UnchangedAcrossSTA'] is False
    before = tmp_path / 'pre-sta-final.adf'
    after = tmp_path / 'place_route' / (prep.TARGET + '_pnr.adf')
    after.parent.mkdir()
    before.write_bytes(b'bound routed database')
    after.write_bytes(before.read_bytes())
    audit = runner.snapshot(tmp_path)
    assert audit['UnchangedAcrossSTA'] is True and audit['TimingAccepted'] is False
    after.write_bytes(b'modified database')
    assert runner.snapshot(tmp_path)['UnchangedAcrossSTA'] is False
