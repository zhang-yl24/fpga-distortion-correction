"""Independent local source/identity probes; no final/provider/EDA/hardware run."""
from pathlib import Path
import hashlib
import json
import shutil

import pytest

import assemble_stage_d_c as a


@pytest.fixture
def program_fragment(tmp_path):
    work = tmp_path / 'synthetic-own-work'
    directory = work / 'program-v3-a'
    directory.mkdir(parents=True)
    bit = work / 'bit-v3-a/generate_bitstream/hdmi_camera_fisheye_top.sbit'
    plan = {'Schema': 'hdmi-camera-fisheye-tile8df8v3-sram-plan-v1', 'Target': a.TARGET,
        'WorkDirectory': str(directory), 'BitstreamWorkDirectory': str(work / 'bit-v3-a'),
        'CableIndex': 0, 'Frequency': '1MHz', 'ServerPort': 65420,
        'RequiresExplicitExecute': True, 'RequiresCurrentSessionBoardPower': True,
        'UserMustBeNotifiedBeforeExecution': True, 'Tcl': {}}
    program = {'Target': a.TARGET, 'WorkDirectory': str(directory), 'ExecutorSHA256': 'a' * 64,
        'UserConfirmedBoardPowered': True, 'UserNotifiedBeforeExecution': True, 'Logs': {}}
    for name, lines in a.expected_program_scripts(bit).items():
        path = directory / (name + '.tcl')
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        plan['Tcl'][name] = a.reference(path)
    for name in ('scan.out.log', 'program.out.log'):
        path = directory / name
        path.write_text('SYNTHETIC LOCAL FIXTURE ONLY\n', encoding='utf-8')
        program['Logs'][name] = a.sha(path)
    watched = {}
    def bound(ref, reason=None):
        assert type(ref) is dict and set(ref) == {'Path', 'SHA256'}
        path = Path(ref['Path']).resolve()
        if not path.is_file() or a.sha(path) != ref['SHA256']:
            raise ValueError('local fixture reference drift')
        watched[str(path)] = ref['SHA256']
        return path
    return plan, program, work, bit, bound, watched


def test_both_required_log_bytes_enter_the_shared_helper_watch(program_fragment):
    plan, program, work, bit, bound, watched = program_fragment
    a.check_program_identity(plan, program, work, bit, 'a' * 64, bound)
    for name in ('scan.out.log', 'program.out.log'):
        assert watched[str(work / 'program-v3-a' / name)] == program['Logs'][name]


@pytest.mark.parametrize('name', ['scan.out.log', 'program.out.log'])
@pytest.mark.parametrize('mutation', ['missing', 'bad_sha', 'bool_sha', 'actual_drift', 'missing_file'])
def test_each_required_log_is_hash_bound_before_success(program_fragment, name, mutation):
    plan, program, work, bit, bound, _ = program_fragment
    path = work / 'program-v3-a' / name
    if mutation == 'missing':
        del program['Logs'][name]
    elif mutation == 'bad_sha':
        program['Logs'][name] = 'not-a-sha'
    elif mutation == 'bool_sha':
        program['Logs'][name] = True
    elif mutation == 'actual_drift':
        path.write_bytes(b'changed local fixture bytes')
    else:
        path.unlink()
    with pytest.raises(ValueError):
        a.check_program_identity(plan, program, work, bit, 'a' * 64, bound)


@pytest.mark.parametrize('mutation', ['another_bit', 'extra_program', 'flash_command', 'script_alias', 'wrong_executor'])
def test_self_consistent_script_rehash_cannot_change_exact_program_recipe(program_fragment, mutation):
    plan, program, work, bit, bound, _ = program_fragment
    path = Path(plan['Tcl']['program']['Path'])
    if mutation == 'wrong_executor':
        program['ExecutorSHA256'] = 'b' * 64
    else:
        text = path.read_text(encoding='utf-8')
        if mutation == 'another_bit':
            path.write_text(text.replace('hdmi_camera_fisheye_top.sbit', 'another.sbit'), encoding='utf-8')
        elif mutation == 'extra_program':
            path.write_text(text + 'cfg_program -device_index 1\n', encoding='utf-8')
        elif mutation == 'flash_command':
            path.write_text(text + 'cfg_program_flash\n', encoding='utf-8')
        else:
            path = path.with_name('program-alias.tcl')
            path.write_text(text, encoding='utf-8')
        plan['Tcl']['program'] = a.reference(path)
    with pytest.raises(ValueError):
        a.check_program_identity(plan, program, work, bit, 'a' * 64, bound)


@pytest.mark.parametrize('which', ['PROVIDER_SHA256', 'ROOT_REVIEW_SHA256', 'WRAPPER_SHA256'])
def test_each_pending_pin_individually_prevents_source_authorization(monkeypatch, which):
    for key in ('PROVIDER_SHA256', 'ROOT_REVIEW_SHA256', 'WRAPPER_SHA256'):
        monkeypatch.setattr(a.authority, key, 'a' * 64)
    monkeypatch.setattr(a.authority, which, None)
    with pytest.raises(ValueError, match='not frozen'):
        a.authority.pins_ready()


@pytest.mark.parametrize('suffix', ['.git/archive', 'distortion/rtl/archive', 'distortion/tools/archive',
    'distortion/work/hdmi-camera-fisheye-tile8df8-20261103-a/archive'])
def test_destination_cannot_be_repointed_to_source_or_frozen_work(tmp_path, suffix):
    with pytest.raises(ValueError, match='only reviewed'):
        a.check_destination(tmp_path, tmp_path / 'base', tmp_path / suffix)


def test_copy_preflight_rejects_later_blocker_without_creating_first_target(tmp_path):
    source = tmp_path / 'source'; source.write_bytes(b'saved local bytes')
    destination = tmp_path / 'archive'; destination.mkdir()
    blocker = destination / 'existing-file'; blocker.write_bytes(b'preserve')
    first = destination / 'would-be-first'
    operations = [(source, first, a.sha(source), source.stat().st_size),
        (source, blocker / 'bad-child', a.sha(source), source.stat().st_size)]
    with pytest.raises(ValueError):
        a.preflight_targets(operations, destination)
    assert not first.exists() and blocker.read_bytes() == b'preserve'


def test_source_contract_map_is_all_seven_df8_roles_and_replays_only_saved_small_evidence(tmp_path):
    repo = Path(__file__).resolve().parents[3]
    rows = {}
    def add(path, expected=None, reason=None):
        path = Path(path).resolve()
        digest = a.sha(path)
        assert expected is None or digest == expected
        rows[str(path)] = {'Path': str(path), 'SHA256': digest, 'Bytes': path.stat().st_size,
            'Mode': 'copy', 'Destination': 'saved/' + path.relative_to(repo).as_posix()}
        return path
    roles, members = a.portable_closure(repo / 'distortion', add)
    assert set(roles) == a.portable.ROLES and len(roles) == 7
    mapping = a.source_contract_map(roles, members, rows.values())
    for row in mapping['Files']:
        target = tmp_path / row['BundlePath']; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(row['OriginalPath'], target)
    path = tmp_path / 'source-contract-map.json'
    path.write_text(json.dumps(mapping), encoding='utf-8')
    facts, _ = a.portable.review(tmp_path, path)
    assert facts['Candidate'] == 'df8' and facts['ProductionSourcesVerified'] == 110
    assert facts['PortableSourceContractVerified'] is True
    for key in ('PublicationComplete', 'NativePhysicalAcceptanceRecomputed', 'BitstreamVerifiedHere',
        'BoardFPSVerifiedHere', 'FullSystemRTLVerifiedHere', 'RTLReexecuted', 'EDAExecuted', 'HardwareAccessed'):
        assert facts[key] is False


def test_loaded_saved_wire_analyzer_is_exact_frozen_d_without_calling_identity_or_hardware():
    repo = Path(__file__).resolve().parents[3]
    paths = []
    def add(path, expected=None, reason=None):
        path = Path(path).resolve()
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
        paths.append(path)
        return path
    reviewer = a.load_fps_reviewer(repo, add)
    assert paths == [repo / 'output/tile8_next15h_20261103/verify_saved_fps_stability_d.py']
    assert reviewer.analyze.__code__.co_filename == str(paths[0])
