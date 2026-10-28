"""All hardware/process/serial execution is mocked; only approved scratch files."""
from pathlib import Path
import copy
import json
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import bounded_native_bringup as bringup


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    state = {'events': [], 'raw_mode': 'success', 'receive_error': None,
             'capture_passed': True, 'idle_passed': True, 'idle_error': None, 'close_error': None}
    monkeypatch.setattr(bringup.raw, 'APPROVED', tmp_path)
    binding_path = tmp_path/'binding.json'
    binding_path.write_text(json.dumps({'synthetic': True}), encoding='utf-8')
    session = tmp_path/'session-binding.json'
    session.write_text(json.dumps({'synthetic': 'SESSION'}), encoding='utf-8')
    raw_validation = {'binding_path': str(binding_path), 'bitstream_path': str(tmp_path/'raw.sbit'), 'synthetic': True}
    idle_validation = {'bitstream_path': str(tmp_path/'heartbeat.sbit'), 'synthetic': True}
    monkeypatch.setattr(bringup.raw, 'validate_program_binding', lambda path: copy.deepcopy(raw_validation))
    monkeypatch.setattr(bringup.idle, 'validate_heartbeat', lambda: copy.deepcopy(idle_validation))
    monkeypatch.setattr(bringup.raw, 'resolve_pds_bin', lambda value=None: tmp_path)

    def nested_plan(work, kind, validation, frequency):
        folder = Path(work)/(kind+'-plan')
        folder.mkdir()
        scripts = bringup.idle._scripts(validation, frequency)
        for stage, text in scripts.items():
            (folder/(stage+'.tcl')).write_text(text, encoding='utf-8')
        return {'target': 'heartbeat' if kind == 'idle' else bringup.raw.TARGET,
            'operation': 'volatile_sram_only', 'frequency': frequency, 'workdir': str(folder),
            'pds_bin': str(tmp_path), 'validation': copy.deepcopy(validation),
            'tcl': {stage: {'path': str(folder/(stage+'.tcl')), 'sha256': bringup.raw.sha(folder/(stage+'.tcl'))} for stage in scripts}}
    monkeypatch.setattr(bringup.raw, 'prepare_plan', lambda path, work, frequency: nested_plan(work, 'raw', raw_validation, frequency))
    monkeypatch.setattr(bringup.idle, 'prepare_plan', lambda work, frequency: nested_plan(work, 'idle', idle_validation, frequency))

    def raw_execute(plan, timeout_seconds):
        state['events'].append('raw')
        mode = state['raw_mode']
        result = {'passed': mode == 'success', 'done_confirmed': mode == 'success',
                  'hardware_accessed': True, 'programming_attempted': mode != 'scan_failed',
                  'session_binding_path': str(session)}
        receipt = Path(plan['workdir'])/'receipt.json'
        if mode == 'corrupt_receipt':
            receipt.write_text('{BROKEN', encoding='utf-8')
            raise RuntimeError('synthetic exception after possible programming')
        receipt.write_text(json.dumps(result), encoding='utf-8')
        if mode == 'keyboard_interrupt':
            raise KeyboardInterrupt('synthetic raw programming interrupt')
        return result
    monkeypatch.setattr(bringup.raw, 'execute_plan', raw_execute)

    def idle_execute(plan, timeout_seconds):
        state['events'].append('idle')
        if state['idle_error']:
            raise state['idle_error']
        return {'passed': state['idle_passed'], 'done_confirmed': state['idle_passed'], 'hardware_accessed': True}
    monkeypatch.setattr(bringup.idle, 'execute_plan', idle_execute)
    monkeypatch.setattr(bringup.capture, 'validate_live_binding', lambda binding, base_dir: {'synthetic': True})

    class SerialChunks:
        def __init__(self):
            self.count = 0
        def __iter__(self):
            return self
        def __next__(self):
            if self.count:
                raise StopIteration
            self.count += 1
            return b'SYNTHETIC WIRE FIXTURE'
        def close(self):
            state['events'].append('close_com')
            if state['close_error']:
                raise state['close_error']
    def serial_chunks(port, baud, seconds):
        state['events'].append('open_com')
        assert baud == 921600 and 10 <= seconds <= 45
        return SerialChunks()
    monkeypatch.setattr(bringup.capture, 'serial_chunks', serial_chunks)

    def receive(chunks, binding, work, session_id, *, frames, source_kind, build_record):
        assert 1 <= frames <= 3
        state['events'].append('capture')
        for data in chunks:
            assert data == b'SYNTHETIC WIRE FIXTURE'
            if state['receive_error']:
                raise state['receive_error']
        return {'passed': state['capture_passed'], 'saved_frames': frames if state['capture_passed'] else 0,
                'frames': [], 'rejected_packets': 0 if state['capture_passed'] else 1}
    monkeypatch.setattr(bringup.capture, 'receive_chunks', receive)
    # Any accidental direct process or real serial use fails even in plan tests.
    monkeypatch.setattr(bringup.raw.subprocess, 'Popen', lambda *a, **k: pytest.fail('real process is forbidden'))
    monkeypatch.setitem(sys.modules, 'serial', types.SimpleNamespace(Serial=lambda *a, **k: pytest.fail('real COM is forbidden')))
    state.update(binding_path=binding_path, work=tmp_path, raw_validation=raw_validation,
                 idle_validation=idle_validation)
    return state


def plan(fixture):
    return bringup.prepare_plan(fixture['binding_path'], fixture['work'], port='COM5', frames=1, seconds=35., frequency='100KHz')


def test_default_plan_does_not_program_open_com_or_idle(fixture, monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['bounded_native_bringup.py', '--binding', str(fixture['binding_path']),
                        '--workdir', str(fixture['work']), '--port', 'COM5'])
    assert bringup.main() == 0
    assert fixture['events'] == []
    assert '"executed": false' in capsys.readouterr().out


def test_raw_scan_failure_opens_no_com_and_does_not_program_idle(fixture):
    fixture['raw_mode'] = 'scan_failed'
    result = bringup.execute_plan(plan(fixture))
    assert fixture['events'] == ['raw']
    assert not result['passed'] and not result['idle_restoration_attempted']


def test_raw_program_attempt_failure_still_programs_fixed_idle(fixture):
    fixture['raw_mode'] = 'program_failed'
    result = bringup.execute_plan(plan(fixture))
    assert fixture['events'] == ['raw', 'idle']
    assert not result['passed'] and result['idle_done_confirmed']


@pytest.mark.parametrize('error', [RuntimeError('synthetic capture error'), KeyboardInterrupt('synthetic capture interrupt')])
def test_capture_failure_closes_com_before_idle(fixture, error):
    fixture['receive_error'] = error
    result = bringup.execute_plan(plan(fixture))
    assert fixture['events'] == ['raw', 'open_com', 'capture', 'close_com', 'idle']
    assert result['idle_done_confirmed'] and not result['passed']
    assert type(error).__name__ in result['error']


def test_capture_crc_failure_is_not_passed_but_com_closes_and_idle_runs(fixture):
    fixture['capture_passed'] = False
    result = bringup.execute_plan(plan(fixture))
    assert not result['passed'] and not result['capture_summary']['passed']
    assert fixture['events'][-2:] == ['close_com', 'idle']


@pytest.mark.parametrize('error', [RuntimeError('synthetic close error'), KeyboardInterrupt('synthetic close interrupt')])
def test_serial_close_error_or_interrupt_cannot_bypass_idle(fixture, error):
    fixture['close_error'] = error
    result = bringup.execute_plan(plan(fixture))
    assert not result['passed'] and 'serial_close_error' in result
    assert result['idle_done_confirmed'] and fixture['events'][-1] == 'idle'


def test_keyboard_interrupt_during_raw_program_recovers_attempt_receipt_and_idles(fixture):
    fixture['raw_mode'] = 'keyboard_interrupt'
    result = bringup.execute_plan(plan(fixture))
    assert fixture['events'] == ['raw', 'idle']
    assert result['raw_program']['programming_attempted']
    assert result['idle_done_confirmed'] and not result['passed']


def test_corrupt_raw_receipt_does_not_bypass_conservative_idle_exit(fixture):
    fixture['raw_mode'] = 'corrupt_receipt'
    result = bringup.execute_plan(plan(fixture))
    assert fixture['events'] == ['raw', 'idle']
    assert result['programming_state_unknown'] and result['idle_done_confirmed']
    assert not result['passed'] and 'raw_receipt_error' in result


@pytest.mark.parametrize('case', ['failed_done', 'exception', 'interrupt'])
def test_idle_failure_never_passes_the_bounded_test(fixture, case):
    if case == 'failed_done':
        fixture['idle_passed'] = False
    else:
        fixture['idle_error'] = RuntimeError('synthetic idle error') if case == 'exception' else KeyboardInterrupt('synthetic idle interrupt')
    result = bringup.execute_plan(plan(fixture))
    assert not result['passed'] and not result['idle_done_confirmed']
    assert fixture['events'][-2:] == ['close_com', 'idle']


@pytest.mark.parametrize('field,value', [('frames', 4), ('seconds', 3600), ('port', 'COM6'), ('baud', 9600)])
def test_modified_capture_configuration_fails_before_hardware(fixture, field, value):
    prepared = plan(fixture)
    prepared[field] = value
    with pytest.raises(ValueError):
        bringup.execute_plan(prepared)
    assert fixture['events'] == []


def test_changed_idle_tcl_is_rejected_before_raw_programming(fixture):
    prepared = plan(fixture)
    Path(prepared['idle_plan']['tcl']['program']['path']).write_text('SYNTHETIC TAMPER', encoding='utf-8')
    with pytest.raises(ValueError, match='idle exit Tcl changed'):
        bringup.execute_plan(prepared)
    assert fixture['events'] == []


def test_changed_raw_binding_validation_fails_before_hardware(fixture):
    prepared = plan(fixture)
    fixture['raw_validation']['synthetic'] = 'CHANGED'
    with pytest.raises(ValueError, match='raw binding or helpers changed'):
        bringup.execute_plan(prepared)
    assert fixture['events'] == []


def test_success_requires_capture_then_com_close_and_confirmed_idle(fixture):
    prepared = plan(fixture)
    result = bringup.execute_plan(prepared)
    assert result['passed'] and result['idle_done_confirmed'] and result['hardware_accessed']
    assert fixture['events'] == ['raw', 'open_com', 'capture', 'close_com', 'idle']
    assert Path(result['capture_summary']['path']).is_file()
    assert result['wire_record']['bytes'] == len(b'SYNTHETIC WIRE FIXTURE')
    with pytest.raises(ValueError, match='fresh bounded-native plan'):
        bringup.execute_plan(prepared)
