"""Current-lens parameter binding, closure isolation, and executor rejection tests."""
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import prepare_camera_vga_calibrated as prep
import run_camera_vga_calibrated_diagnostic as runner


def test_current_calibration_closure_and_data_delay():
    r=prep.validate_sources(); old=prep.upright.validate_sources()
    assert len(r['Sources'])==109 and len(r['ExplicitDesigns'])==29
    assert set(old['Sources'])-set(r['Sources'])==set(prep.REPLACE)
    assert set(r['Sources'])-set(old['Sources'])==set(prep.REPLACE.values())|{prep.DELAY}
    assert r['ConstraintSHA256']==old['ConstraintSHA256']
    assert r['UnchangedSourceSHA256']=={n:h for n,h in old['SourceSHA256'].items() if n not in prep.REPLACE}
    text=(prep.PROJECT/prep.TOP).read_text()
    assert 'SYNTHETIC_GEOMETRY' not in text and 'parameter WIDTH' not in text
    assert '.cam_data(delayed_cam_data)' in text and '.pad_data(cam_data)' in text
    assert '.MAX_RADIUS_Q22(CAL_RADIUS_Q22)' in text
    assert 'ov5640_cadence_upright_init' in text


def test_recipe_isolated_and_no_inherited_exceptions():
    plan,payloads,tcl=prep.recipe(prep.WORK/'cpu-never-run')
    assert plan['Target']==prep.TARGET and len(payloads)==110
    assert plan['InputSHA256'][prep.MAPPING]==prep.MAPPING_SHA
    assert plan['InputSHA256'][prep.PROFILE]==prep.PROFILE_SHA
    assert plan['InputSHA256'][prep.DELAY]==prep.DELAY_SHA
    assert not plan['HardwareAccessed'] and not plan['TimingAccepted']
    assert ('compile -top_module '+prep.TARGET).encode() in tcl
    for word in [b'manual_route',b'set_false_path',b'generate_bitstream',b'cfg_program']:
        assert word not in tcl
    assert all(Path(x).suffix!='.vh' for x in plan['ExplicitDesigns'])


@pytest.mark.parametrize('name',[prep.PROFILE,prep.MAPPING])
def test_changed_calibration_evidence_rejected(monkeypatch,name):
    real=prep.sha
    monkeypatch.setattr(prep,'sha',lambda path:'0'*64 if path==prep.PROJECT/name else real(path))
    with pytest.raises(ValueError,match='evidence changed'):prep.calibration()


@pytest.mark.parametrize('name',[prep.TOP,prep.HEADER,prep.DELAY])
def test_top_parameter_or_delay_drift_rejected(monkeypatch,name):
    if name==prep.DELAY:
        real=prep.sha
        monkeypatch.setattr(prep,'sha',lambda path:'0'*64 if path==prep.PROJECT/name else real(path))
    else:
        original=Path.read_text
        def changed(path,*args,**kwargs):
            result=original(path,*args,**kwargs)
            if path==prep.PROJECT/name:
                return result.replace('CAL_K1','CAL_K2') if name==prep.TOP else result.replace('674237','674236')
            return result
        monkeypatch.setattr(Path,'read_text',changed)
    with pytest.raises(ValueError):prep.roles()


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
