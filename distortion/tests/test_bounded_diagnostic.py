"""Mocked bounded UART/JTAG diagnostics plus synthetic artifact rejections."""
from pathlib import Path
import copy
import json
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import bounded_diagnostic as diagnostic

REAL_PROGRAM = diagnostic._execute_program


@pytest.fixture
def control(tmp_path, monkeypatch):
    state = {'events': [], 'program_mode': 'success', 'serial_error': None, 'close_error': None,
             'idle_passed': True, 'idle_error': None, 'wire': b'SYNTHETIC STATUS\r\n'}
    monkeypatch.setattr(diagnostic.hw, 'APPROVED', tmp_path)
    validation = {'target': 'thermal_idle', 'build_dir': str(tmp_path),
                  'bitstream_path': str(tmp_path/'thermal_idle.sbit'), 'synthetic': True}
    exit_validation = {'bitstream_path': str(tmp_path/'heartbeat.sbit'), 'synthetic': True}
    monkeypatch.setattr(diagnostic, 'validate_target', lambda *a, **k: copy.deepcopy(validation))
    monkeypatch.setattr(diagnostic.idle, 'validate_heartbeat', lambda: copy.deepcopy(exit_validation))
    monkeypatch.setattr(diagnostic.hw, 'resolve_pds_bin', lambda value=None: tmp_path)
    def idle_plan(work, frequency):
        folder = Path(work)/'idle-program'
        folder.mkdir()
        scripts = diagnostic.hw._scripts(exit_validation, frequency)
        for stage, text in scripts.items():
            (folder/(stage+'.tcl')).write_text(text, encoding='utf-8')
        return {'target': 'heartbeat', 'operation': 'volatile_sram_only', 'frequency': frequency,
            'workdir': str(folder), 'pds_bin': str(tmp_path), 'validation': copy.deepcopy(exit_validation),
            'tcl': {stage: {'path': str(folder/(stage+'.tcl')), 'sha256': diagnostic.hw.sha(folder/(stage+'.tcl'))} for stage in scripts}}
    monkeypatch.setattr(diagnostic.idle, 'prepare_plan', idle_plan)
    def program(plan):
        state['events'].append('diagnostic_program')
        mode = state['program_mode']
        result = {'passed': mode == 'success', 'done_confirmed': mode == 'success',
                  'programming_attempted': mode != 'scan_failed', 'hardware_accessed': True}
        receipt = Path(plan['workdir'])/'receipt.json'
        if mode == 'corrupt_receipt':
            receipt.write_text('null', encoding='utf-8')
            raise KeyboardInterrupt('synthetic interrupted program')
        receipt.write_text(json.dumps(result), encoding='utf-8')
        if mode == 'interrupt':
            raise KeyboardInterrupt('synthetic interrupted program')
        return result
    monkeypatch.setattr(diagnostic, '_execute_program', program)
    def idle_execute(plan, timeout_seconds):
        state['events'].append('idle')
        if state['idle_error']:
            raise state['idle_error']
        return {'passed': state['idle_passed'], 'done_confirmed': state['idle_passed'], 'hardware_accessed': True}
    monkeypatch.setattr(diagnostic.idle, 'execute_plan', idle_execute)
    class Chunks:
        def __init__(self):
            self.sent = False
        def __iter__(self):
            return self
        def __next__(self):
            if state['serial_error']:
                raise state['serial_error']
            if self.sent:
                raise StopIteration
            self.sent = True
            return state['wire']
        def close(self):
            state['events'].append('close_com')
            if state['close_error']:
                raise state['close_error']
    def serial_chunks(port, baud, seconds):
        state['events'].append('open_com')
        assert port == 'COM5' and baud == 921600 and 10 <= seconds <= 20
        return Chunks()
    monkeypatch.setattr(diagnostic.receiver, 'serial_chunks', serial_chunks)
    monkeypatch.setattr(diagnostic.hw.subprocess, 'Popen', lambda *a, **k: pytest.fail('real process forbidden'))
    monkeypatch.setitem(sys.modules, 'serial', types.SimpleNamespace(Serial=lambda *a, **k: pytest.fail('real COM forbidden')))
    state.update(work=tmp_path, validation=validation)
    return state


def make_plan(control):
    return diagnostic.prepare_plan('thermal_idle', control['work'], port='COM5', seconds=12., thermal_build_dir=control['work'])


def test_default_cli_plans_without_hardware(control, capsys):
    assert diagnostic.main(['--target', 'thermal_idle', '--workdir', str(control['work']),
        '--thermal-build-dir', str(control['work']), '--port', 'COM5']) == 0
    assert control['events'] == []
    assert '"hardware_accessed": false' in capsys.readouterr().out


def test_scan_failure_does_not_open_com_or_program_idle(control):
    control['program_mode'] = 'scan_failed'
    result = diagnostic.execute_plan(make_plan(control))
    assert control['events'] == ['diagnostic_program']
    assert not result['passed'] and not result['idle_restoration_attempted']


@pytest.mark.parametrize('mode', ['program_failed', 'interrupt', 'corrupt_receipt'])
def test_any_program_attempt_or_unknown_receipt_attempts_idle(control, mode):
    control['program_mode'] = mode
    result = diagnostic.execute_plan(make_plan(control))
    assert control['events'] == ['diagnostic_program', 'idle']
    assert not result['passed'] and result['idle_done_confirmed']


@pytest.mark.parametrize('error', [RuntimeError('synthetic serial failure'), KeyboardInterrupt('synthetic interrupt')])
def test_program_then_serial_error_closes_com_before_idle(control, error):
    control['serial_error'] = error
    result = diagnostic.execute_plan(make_plan(control))
    assert control['events'] == ['diagnostic_program', 'open_com', 'close_com', 'idle']
    assert not result['passed'] and result['idle_done_confirmed']


def test_com_close_interrupt_still_attempts_idle(control):
    control['close_error'] = KeyboardInterrupt('synthetic close interrupt')
    result = diagnostic.execute_plan(make_plan(control))
    assert control['events'][-2:] == ['close_com', 'idle']
    assert not result['passed'] and result['idle_done_confirmed']


@pytest.mark.parametrize('case', ['done_false', 'exception'])
def test_idle_failure_never_passes(control, case):
    if case == 'done_false':
        control['idle_passed'] = False
    else:
        control['idle_error'] = RuntimeError('synthetic idle error')
    result = diagnostic.execute_plan(make_plan(control))
    assert not result['passed'] and not result['idle_done_confirmed']


def test_empty_wire_is_not_a_successful_status_read(control):
    control['wire'] = b''
    result = diagnostic.execute_plan(make_plan(control))
    assert result['idle_done_confirmed'] and not result['passed']


@pytest.mark.parametrize('field,value', [('target', 'camera_isp_probe'), ('seconds', 999), ('baud', 9600), ('port', 'COM6'), ('frequency', '100KHz')])
def test_configuration_tampering_fails_before_hardware(control, field, value):
    plan = make_plan(control)
    plan[field] = value
    with pytest.raises(ValueError):
        diagnostic.execute_plan(plan)
    assert control['events'] == []


def test_scan_only_100khz_rejected_before_preparing_sram_diagnostic(control):
    with pytest.raises(ValueError, match='100KHz is scan-only'):
        diagnostic.prepare_plan('thermal_idle', control['work'], port='COM5', frequency='100KHz',
                                thermal_build_dir=control['work'])
    assert control['events'] == []


def test_idle_tcl_tampering_blocks_active_program(control):
    plan = make_plan(control)
    Path(plan['idle_plan']['tcl']['program']['path']).write_text('TAMPERED', encoding='utf-8')
    with pytest.raises(ValueError, match='Tcl changed'):
        diagnostic.execute_plan(plan)
    assert control['events'] == []


def test_success_retains_full_wire_but_does_not_certify_temperature_or_raw(control):
    result = diagnostic.execute_plan(make_plan(control))
    assert result['passed'] and result['idle_done_confirmed']
    assert Path(result['wire_record']['path']).read_bytes() == control['wire']
    assert not result['temperature_measured'] and not result['raw_frame_role_certified']
    assert control['events'] == ['diagnostic_program', 'open_com', 'close_com', 'idle']


def test_program_uses_owned_scan_then_program_server_and_fresh_done(control, monkeypatch):
    prepared = make_plan(control)['diagnostic_plan']
    events = []
    server = types.SimpleNamespace(pid=123)
    monkeypatch.setattr(diagnostic.hw, 'listening_pids', lambda port: set())
    monkeypatch.setattr(diagnostic.hw, '_start_owned', lambda *a: (a[2].append(server) or server))
    monkeypatch.setattr(diagnostic.hw, '_await_owned_server', lambda server: events.append('await_owned'))
    monkeypatch.setattr(diagnostic.hw, '_owned_server_check', lambda server: events.append('check_owned'))
    monkeypatch.setattr(diagnostic.hw, '_client', lambda plan, stage, owned, timeout: (events.append(stage) or stage))
    monkeypatch.setattr(diagnostic.hw, '_check_scan', lambda text: events.append('check_id'))
    monkeypatch.setattr(diagnostic.hw, '_check_program', lambda text: events.append('check_fresh_done'))
    monkeypatch.setattr(diagnostic.hw, '_program_server_after_scan', lambda *a: (events.append('owned_program_server') or server))
    monkeypatch.setattr(diagnostic.hw, '_stop_owned', lambda owned: ([], []))
    result = REAL_PROGRAM(prepared)
    assert result['passed'] and result['programming_attempted'] and result['done_confirmed']
    assert events.index('check_id') < events.index('owned_program_server') < events.index('program') < events.index('check_fresh_done')


@pytest.fixture
def thermal_artifact(tmp_path, monkeypatch):
    project, artifact = tmp_path/'project', tmp_path/'thermal-artifact'
    project.mkdir(); artifact.mkdir()
    monkeypatch.setattr(diagnostic, 'ROOT', project)
    monkeypatch.setattr(diagnostic.hw, 'APPROVED', tmp_path)
    for name in diagnostic.THERMAL_FILES:
        path = project/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('// SYNTHETIC SOURCE FIXTURE', encoding='utf-8')
    pins = project/'board/thermal_idle-pins.json'
    pins.write_text(json.dumps(diagnostic.THERMAL_PINS), encoding='utf-8')
    source_hashes = {name: diagnostic.hw.sha(project/name) for name in diagnostic.THERMAL_FILES}
    prepared_path = project/'board/thermal_idle-sources.json'
    prepared_path.write_text(json.dumps({'target': 'thermal_idle', 'source_files': list(diagnostic.THERMAL_FILES),
        'SourceSHA256': source_hashes, 'ThermalIdleContract': diagnostic.THERMAL_CONTRACT}), encoding='utf-8')
    (artifact/'generate_bitstream').mkdir(); (artifact/'place_route').mkdir()
    bit = artifact/'generate_bitstream/thermal_idle.sbit'
    bit.write_bytes(b'SYNTHETIC THERMAL BITSTREAM, NEVER PROGRAM')
    timing = artifact/'place_route/thermal_idle_timing_summary_after_hold_fix.txt'
    timing.write_text('Design Summary : All Constraints Met.\n', encoding='utf-8')
    routed = artifact/'place_route/thermal_idle_prr.prt'
    routed.write_text(''.join(f'{pin}|tile|bank|site|{port}|'+('input' if port=='clk_27m' else 'output')+'|YES\n'
                               for port,pin in diagnostic.THERMAL_PINS.items()), encoding='utf-8')
    manifest = {'Target': 'thermal_idle', 'Device': 'PG2L100H', 'Package': 'FBG676', 'SCBV': 'High Voltage',
        'UnusedIO': 'UNUSED', 'Bitstream': str(bit), 'SHA256': diagnostic.hw.sha(bit),
        'TimingReport': str(timing), 'TimingSHA256': diagnostic.hw.sha(timing),
        'SourceSHA256': {**source_hashes, 'board/thermal_idle-sources.json': diagnostic.hw.sha(prepared_path)},
        'ThermalIdleContract': diagnostic.THERMAL_CONTRACT}
    (artifact/'validated-build.json').write_text(json.dumps(manifest), encoding='utf-8')
    return {'project': project, 'artifact': artifact, 'manifest': manifest, 'bit': bit, 'timing': timing, 'routed': routed}


def test_thermal_validation_requires_exact_eight_sources_and_ten_routed_pins(thermal_artifact):
    value = diagnostic.validate_target('thermal_idle', thermal_build_dir=thermal_artifact['artifact'])
    assert len(value['source_sha256']) == 9 and len(value['verified_pins']) == 10
    assert not value['camera_initialization_writes_registers']


@pytest.mark.parametrize('case', ['device', 'target', 'bit', 'source', 'timing', 'pins', 'contract'])
def test_invalid_artifacts_rejected_without_hardware(thermal_artifact, case):
    fixture = thermal_artifact
    if case == 'device':
        fixture['manifest']['Device'] = 'OTHER'
    elif case == 'target':
        fixture['manifest']['Target'] = 'OTHER'
    elif case == 'bit':
        fixture['bit'].write_bytes(b'TAMPERED')
    elif case == 'source':
        (fixture['project']/'rtl/uart_tx.v').write_text('TAMPERED', encoding='utf-8')
    elif case == 'timing':
        fixture['timing'].write_text('Timing failed', encoding='utf-8')
    elif case == 'pins':
        fixture['routed'].write_text('C24|tile|bank|site|uart_txd|output|YES\n', encoding='utf-8')
    else:
        fixture['manifest']['ThermalIdleContract'] = {**diagnostic.THERMAL_CONTRACT, 'camera_outputs': True}
    (fixture['artifact']/'validated-build.json').write_text(json.dumps(fixture['manifest']), encoding='utf-8')
    with pytest.raises(ValueError):
        diagnostic.validate_target('thermal_idle', thermal_build_dir=fixture['artifact'])


def test_known_legacy_aa22_probe_is_always_forbidden():
    with pytest.raises(ValueError, match='known AA22'):
        diagnostic.validate_target('camera_isp_probe')


@pytest.fixture
def probe_clone(tmp_path, monkeypatch):
    """Bind real clone checks to synthetic sources, never a local PDS build."""
    project = tmp_path/'synthetic-probe-project'
    original = diagnostic.hw.load_json(ROOT/'board/camera_isp_probe-sources.json')
    cloned = [name.replace('camera_isp_probe', 'camera_isp_probe_d5') for name in original]
    assert len(original) == 16
    original_text = {
        'board/camera_isp_probe.v': '// SYNTHETIC SOURCE FIXTURE\nmodule camera_isp_probe(); endmodule\n',
        'board/camera_isp_probe.fdc': 'define_attribute {p:cam_data[5]} {PAP_IO_LOC} {AA22}\n',
        'board/camera_isp_probe-pins.json': json.dumps({'clk_27m': 'D18', 'cam_data[5]': 'AA22'}),
        'board/build-camera_isp_probe.tcl': '# SYNTHETIC SOURCE FIXTURE\nset top camera_isp_probe\n',
        'board/camera_isp_probe-sources.json': json.dumps(original),
    }
    cloned_text = {
        'board/camera_isp_probe_d5.v': '// SYNTHETIC SOURCE FIXTURE\nmodule camera_isp_probe_d5(); endmodule\n',
        'board/camera_isp_probe_d5.fdc': 'define_attribute {p:cam_data[5]} {PAP_IO_LOC} {AA23}\n',
        'board/camera_isp_probe_d5-pins.json': json.dumps({'clk_27m': 'D18', 'cam_data[5]': 'AA23'}),
        'board/build-camera_isp_probe_d5.tcl': '# SYNTHETIC SOURCE FIXTURE\nset top camera_isp_probe_d5\n',
        'board/camera_isp_probe_d5-sources.json': json.dumps(cloned),
    }
    for name in original:
        path = project/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(original_text.get(name, '// SYNTHETIC SOURCE FIXTURE: '+name+'\n'), encoding='utf-8')
    for name, text in cloned_text.items():
        (project/name).write_text(text, encoding='utf-8')
    legacy = project/'build/camera_isp_probe/validated-build.json'
    legacy.parent.mkdir(parents=True)
    legacy.write_text(json.dumps({
        'synthetic': True, 'purpose': 'clone validation unit test only; no PDS build or hardware approval',
        'SourceSHA256': {name: diagnostic.hw.sha(project/name) for name in original},
    }), encoding='utf-8')
    monkeypatch.setattr(diagnostic, 'ROOT', project)
    # Change only the fixture identity; keep the production hash and clone checks real.
    monkeypatch.setitem(diagnostic.CAMERA_ARTIFACT_SHA, 'validated-build.json', diagnostic.hw.sha(legacy).upper())
    return {'project': project, 'cloned': cloned}


def test_probe_clone_rejects_an_extra_dependency(probe_clone):
    names = probe_clone['cloned']
    assert diagnostic._validate_probe_clone(names) == set(names)
    with pytest.raises(ValueError, match='exact legacy 16-file'):
        diagnostic._validate_probe_clone(names+['rtl/another_candidate.v'])


def test_probe_clone_rejects_extra_rtl_changes(probe_clone):
    cloned = probe_clone['cloned']
    assert diagnostic._validate_probe_clone(cloned) == set(cloned)
    top = probe_clone['project']/'board/camera_isp_probe_d5.v'
    top.write_text(top.read_text(encoding='utf-8-sig')+'\n// EXTRA UNREVIEWED CHANGE\n', encoding='utf-8')
    with pytest.raises(ValueError, match='differs from the exact'):
        diagnostic._validate_probe_clone(cloned)
