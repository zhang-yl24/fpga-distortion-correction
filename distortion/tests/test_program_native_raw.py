"""All execution boundaries are mocked; no process, UART, JTAG or board is used."""
from pathlib import Path
import copy
import hashlib
import json
import struct
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import program_native_raw as program


SCAN = 'PG2L100H\nThe ID value is: 0x00602899\n'
PRE_SCAN = ('Executing : cfg_scan_chain\nPG2L100H\n'
            'This device configure situation (done bit): 1\n'
            'Executing : cfg_scan_chain successfully.\n')
PROGRAM_SUCCESS = 'Executing : cfg_program -device_index 0 successfully.\n'
POST_SCAN = ('Executing : cfg_scan_chain\nPG2L100H\n'
             'This device configure situation (done bit): 1\n'
             'Executing : cfg_scan_chain successfully.\n')
DONE = PRE_SCAN+PROGRAM_SUCCESS+POST_SCAN


def write_json(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def files(tmp_path, monkeypatch):
    # Isolated tests use their own approved scratch root on Windows and CI.
    # Production code still fixes APPROVED to the user's explicit workspace.
    monkeypatch.setattr(program, 'APPROVED', tmp_path)
    prepared = json.loads((ROOT/f'board/{program.TARGET}-sources.json').read_text(encoding='utf-8'))
    bit = tmp_path/(program.TARGET+'.sbit')
    timing, manifest_path, binding_path = [tmp_path/name for name in ('timing.rtr', 'validated-build.json', 'binding.json')]
    bit.write_bytes(b'SYNTHETIC TEST FIXTURE; NEVER A REAL BITSTREAM')
    timing.write_text('SYNTHETIC TEST FIXTURE\nAll Constraints Met\n', encoding='utf-8')
    pins = ROOT/f'board/{program.TARGET}-pins.json'
    manifest = {'Target': program.TARGET, 'Device': 'PG2L100H', 'SCBV': 'High Voltage',
        'SHA256': digest(bit), 'TimingSHA256': digest(timing),
        'RawCaptureContract': prepared['RawCaptureContract'], 'SourceSHA256': prepared['SourceSHA256']}
    write_json(manifest_path, manifest)
    binding = {'schema': 1, 'camera_id': 'SYNTHETIC-CAMERA', 'lens_id': 'SYNTHETIC-LENS',
        'profile_id': 'SYNTHETIC-PROFILE', 'capture_mode_id': 'SYNTHETIC-MODE', 'eye': 'CAM2',
        'image_size': [640, 480], 'pixel_format': 'RGB565_LE',
        'connection_review': {'new_module_pinout_verified': True, 'power_and_io_verified': True,
                              'selected_eye_verified': True, 'programmed_bound_bitstream': False},
        'build_binding': {name: {'path': str(path), 'sha256': digest(path)} for name, path in
            (('validated_build', manifest_path), ('bitstream', bit), ('pinout', pins), ('timing_report', timing))}}
    write_json(binding_path, binding)
    pds = tmp_path/'fake-pds-bin'
    pds.mkdir()
    for name in ('cdt_js.exe', 'cdt_cfg_shell.exe'):
        (pds/name).write_bytes(b'SYNTHETIC PLACEHOLDER; TESTS MUST MOCK POPEN')
    return {'work': tmp_path, 'bit': bit, 'timing': timing, 'manifest': manifest,
            'manifest_path': manifest_path, 'binding': binding, 'binding_path': binding_path, 'pds': pds}


def update_manifest(files):
    write_json(files['manifest_path'], files['manifest'])
    files['binding']['build_binding']['validated_build']['sha256'] = digest(files['manifest_path'])
    write_json(files['binding_path'], files['binding'])


@pytest.fixture
def fake_processes(monkeypatch):
    state = {'processes': [], 'scan': SCAN, 'program': DONE, 'scan_code': 0, 'program_code': 0,
             'stderr': b'', 'conflict': None, 'server_exit_after_scan': False,
             'conflict_after_scan': None, 'second_server_conflict': None}

    class Process:
        def __init__(self, stage, code):
            self.stage, self.code = stage, code
            self.pid = 8100+len(state['processes'])
            self.ended = False
            self.terminated = False
            self.killed = False
        def poll(self):
            return self.code if self.ended else None
        def wait(self, timeout=None):
            self.ended = True
            if self.stage == 'scan' and state['server_exit_after_scan']:
                state['processes'][0].ended = True
            return self.code
        def terminate(self):
            self.terminated = True
            self.ended = True
        def kill(self):
            self.killed = True
            self.ended = True

    def popen(command, **kwargs):
        assert Path(command[0]).name in ('cdt_js.exe', 'cdt_cfg_shell.exe')
        stage = ('server-program' if Path(kwargs['stdout'].name).name.startswith('server-program.') else 'server') if Path(command[0]).name == 'cdt_js.exe' else Path(command[command.index('-file')+1]).stem
        assert stage in ('server', 'server-program', 'scan', 'program')
        process = Process(stage, state.get(stage+'_code', 0))
        state['processes'].append(process)
        kwargs['stdout'].write(('SYNTHETIC OWNED SERVER' if stage.startswith('server') else state[stage]).encode())
        if not stage.startswith('server'):
            kwargs['stderr'].write(state['stderr'])
        return process

    def listeners(port):
        assert port == program.PORT
        if state['conflict'] is not None:
            return set(state['conflict'])
        if state['conflict_after_scan'] is not None and any(p.stage=='scan' and p.ended for p in state['processes']):
            return set(state['conflict_after_scan'])
        if state['second_server_conflict'] is not None and any(p.stage=='server-program' for p in state['processes']):
            return set(state['second_server_conflict'])
        return {p.pid for p in state['processes'] if p.stage.startswith('server') and p.poll() is None}

    monkeypatch.setattr(program.subprocess, 'Popen', popen)
    monkeypatch.setattr(program, 'listening_pids', listeners)
    # If any code tried to create a serial connection this assertion would fail.
    monkeypatch.setitem(sys.modules, 'serial', types.SimpleNamespace(Serial=lambda *a, **k: pytest.fail('no serial access is permitted')))
    return state


def plan(files):
    return program.prepare_plan(files['binding_path'], files['work'], pds_bin=files['pds'])


def test_default_main_validates_and_plans_without_starting_any_process(files, fake_processes, capsys):
    code = program.main(['--binding', str(files['binding_path']), '--workdir', str(files['work']), '--pds-bin', str(files['pds'])])
    result = json.loads(capsys.readouterr().out)
    assert code == 0 and not result['executed'] and not result['hardware_accessed']
    assert fake_processes['processes'] == []
    assert not result['validation']['binding']['connection_review']['programmed_bound_bitstream']
    work = Path(result['workdir'])
    assert work.is_relative_to(program.APPROVED.resolve())
    assert {p.name for p in work.iterdir()} == {'plan.json', 'scan.tcl', 'program.tcl'}
    script = (work/'program.tcl').read_text()
    assert program.TARGET+'.sbit' in script and 'cfg_program -device_index 0' in script
    assert 'cfg_program' not in (work/'scan.tcl').read_text()
    assert 'cfg_erase' not in script and 'cfg_flash' not in script


@pytest.mark.parametrize('case', ['bit', 'source', 'timing', 'timing_content', 'target', 'review', 'wrong_eye'])
def test_bad_bound_files_or_reviews_reject_before_process_start(files, fake_processes, case):
    if case == 'bit':
        files['bit'].write_bytes(b'CHANGED SYNTHETIC FIXTURE')
    elif case == 'source':
        first = next(iter(files['manifest']['SourceSHA256']))
        files['manifest']['SourceSHA256'][first] = '0'*64
        update_manifest(files)
    elif case == 'timing':
        files['timing'].write_text('not a valid timing report', encoding='utf-8')
    elif case == 'timing_content':
        files['timing'].write_text('Not All Constraints Met\n', encoding='utf-8')
        files['manifest']['TimingSHA256'] = digest(files['timing'])
        files['binding']['build_binding']['timing_report']['sha256'] = digest(files['timing'])
        update_manifest(files)
    elif case == 'target':
        files['manifest']['Target'] = 'heartbeat'
        update_manifest(files)
    else:
        if case == 'review':
            files['binding']['connection_review']['selected_eye_verified'] = False
        else:
            files['binding']['eye'] = 'CAM1'
        write_json(files['binding_path'], files['binding'])
    with pytest.raises(ValueError):
        plan(files)
    assert not fake_processes['processes']


@pytest.mark.parametrize('scan', ['PG2L50H\nThe ID value is: 0x00602899\n',
                                  'PG2L100H\nThe ID value is: 0x00000000\n',
                                  SCAN+'PG2L100H\n'])
def test_wrong_or_multiple_devices_never_reach_program(files, fake_processes, scan):
    prepared = plan(files)
    fake_processes['scan'] = scan
    result = program.execute_plan(prepared)
    assert not result['passed'] and not result['done_confirmed'] and not result['programming_attempted']
    assert [p.stage for p in fake_processes['processes']] == ['server', 'scan']
    assert not (Path(prepared['workdir'])/'session-binding.json').exists()
    assert fake_processes['processes'][0].terminated


def test_server_conflict_does_not_start_or_stop_any_process(files, fake_processes):
    prepared = plan(files)
    fake_processes['conflict'] = {99123}
    result = program.execute_plan(prepared)
    assert not result['passed'] and not result['hardware_accessed']
    assert result['owned_pids'] == result['terminated_owned_pids'] == []
    assert fake_processes['processes'] == []
    assert 'occupied' in result['error']


def test_server_startup_race_stops_only_its_own_process(files, fake_processes, monkeypatch):
    prepared = plan(files)
    calls = []
    def changed_listener(port):
        calls.append(port)
        return set() if len(calls) == 1 else {99887}
    monkeypatch.setattr(program, 'listening_pids', changed_listener)
    result = program.execute_plan(prepared)
    assert not result['passed'] and not result['done_confirmed']
    assert [p.stage for p in fake_processes['processes']] == ['server']
    assert result['terminated_owned_pids'] == [fake_processes['processes'][0].pid]
    assert 99887 not in result['owned_pids']


def test_tcl_tampering_cannot_add_another_configuration_operation(files, fake_processes):
    prepared = plan(files)
    script = Path(prepared['tcl']['program']['path'])
    script.write_text(script.read_text()+'cfg_program_other_target\n', encoding='utf-8')
    prepared['tcl']['program']['sha256'] = digest(script)
    result = program.execute_plan(prepared)
    assert not result['passed'] and not result['hardware_accessed']
    assert not fake_processes['processes']


@pytest.mark.parametrize('text,code', [(DONE, 1), ('cfg_program failed\n', 0),
                                      (PRE_SCAN+PROGRAM_SUCCESS+POST_SCAN.replace('done bit): 1', 'done bit): 0'), 0)])
def test_failed_program_never_claims_done_or_writes_ready_binding(files, fake_processes, text, code):
    prepared = plan(files)
    fake_processes['program'], fake_processes['program_code'] = text, code
    result = program.execute_plan(prepared)
    assert not result['passed'] and not result['done_confirmed'] and result['programming_attempted']
    receipt = json.loads((Path(prepared['workdir'])/'receipt.json').read_text())
    assert not receipt['passed'] and not receipt['done_confirmed']
    assert not (Path(prepared['workdir'])/'session-binding.json').exists()


def test_preexisting_done_cannot_replace_a_post_program_scan():
    with pytest.raises(RuntimeError, match='post-program scan'):
        program._check_program(PRE_SCAN+PROGRAM_SUCCESS)


def test_correct_device_in_both_scans_is_accepted_as_format_only():
    program._check_program(DONE)


def test_wrong_pre_program_device_is_not_ignored():
    with pytest.raises(RuntimeError):
        program._check_program(PRE_SCAN.replace('PG2L100H', 'PG2L50H')+PROGRAM_SUCCESS+POST_SCAN)


def test_mock_done_creates_only_new_session_binding_and_owned_cleanup(files, fake_processes):
    original = files['binding_path'].read_bytes()
    prepared = plan(files)
    result = program.execute_plan(prepared)
    assert result['passed'] and result['done_confirmed'] and result['programming_attempted']
    session = json.loads(Path(result['session_binding_path']).read_text())
    assert session['connection_review']['programmed_bound_bitstream']
    assert session['programming_receipt']['sha256'] == digest(Path(prepared['workdir'])/'receipt.json')
    assert files['binding_path'].read_bytes() == original
    assert result['terminated_owned_pids'] == [fake_processes['processes'][0].pid]
    assert all(p.pid in result['owned_pids'] for p in fake_processes['processes'] if p.terminated or p.killed)
    with pytest.raises(ValueError, match='already has an execution receipt'):
        program.execute_plan(prepared)


def test_scan_cfg_close_exit_starts_one_fresh_owned_program_server(files, fake_processes):
    prepared=plan(files);fake_processes['server_exit_after_scan']=True
    result=program.execute_plan(prepared)
    assert result['passed'] and result['done_confirmed'] and result['programming_attempted']
    assert result['server_restarted_after_scan']
    assert [p.stage for p in fake_processes['processes']]==['server','scan','server-program','program']
    assert result['terminated_owned_pids']==[fake_processes['processes'][2].pid]
    assert (Path(prepared['workdir'])/'server-program.out.log').is_file()


def test_foreign_listener_after_scan_prevents_replacement_and_program(files, fake_processes):
    prepared=plan(files);fake_processes['server_exit_after_scan']=True
    fake_processes['conflict_after_scan']={99881}
    result=program.execute_plan(prepared)
    assert not result['passed'] and not result['programming_attempted']
    assert [p.stage for p in fake_processes['processes']]==['server','scan']
    assert 99881 not in result['owned_pids'] and not result['terminated_owned_pids']


def test_replacement_startup_conflict_only_stops_owned_second_server(files, fake_processes):
    prepared=plan(files);fake_processes['server_exit_after_scan']=True
    fake_processes['second_server_conflict']={99882}
    result=program.execute_plan(prepared)
    assert not result['passed'] and not result['programming_attempted']
    assert [p.stage for p in fake_processes['processes']]==['server','scan','server-program']
    assert result['terminated_owned_pids']==[fake_processes['processes'][2].pid]
    assert 99882 not in result['owned_pids']


def test_binding_changes_after_plan_are_rejected_before_start(files, fake_processes):
    prepared = plan(files)
    files['binding']['camera_id'] = 'CHANGED-SYNTHETIC-ID'
    write_json(files['binding_path'], files['binding'])
    result = program.execute_plan(prepared)
    assert not result['passed'] and not result['hardware_accessed']
    assert fake_processes['processes'] == []


@pytest.mark.parametrize('family', [4, 6])
def test_windows_owner_table_parser_filters_port_without_process_commands(family):
    size, offset, pid_offset = (24, 8, 20) if family == 4 else (56, 20, 52)
    row = bytearray(size)
    row[offset:offset+2] = program.PORT.to_bytes(2, 'big')
    struct.pack_into('<I', row, pid_offset, 12345)
    data = struct.pack('<I', 1)+row
    assert program._table_listener_pids(data, family, program.PORT) == {12345}
    assert program._table_listener_pids(data, family, 1) == set()


def test_workdir_and_output_cannot_escape_approved_tree(files, fake_processes):
    with pytest.raises(ValueError, match='approved'):
        program.prepare_plan(files['binding_path'], ROOT/'output/project', pds_bin=files['pds'])
    assert fake_processes['processes'] == []
