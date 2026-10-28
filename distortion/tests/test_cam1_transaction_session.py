from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import cam1_transaction_session as s


@pytest.fixture
def setup(tmp_path, monkeypatch):
    work = tmp_path/'session'
    work.mkdir()
    program = work/'diagnostic-program'
    program.mkdir()
    monkeypatch.setattr(s.hw, 'APPROVED', tmp_path)
    monkeypatch.setattr(s, 'helpers', lambda: {})
    monkeypatch.setattr(s, '_check_program_plan', lambda *args: None)
    validation = {'build_dir': str(tmp_path), 'seal': True}
    monkeypatch.setattr(s, 'validate_target', lambda *_: validation)
    monkeypatch.setattr(s.bounded, '_check_tcl', lambda *args: None)
    monkeypatch.setattr(s.idle, 'validate_heartbeat', lambda: {'idle': True})
    plan = {'schema': 1, 'target': s.TARGET, 'operation': 'bounded_cam1_transaction_then_heartbeat',
        'workdir': str(work), 'port': 'COM5', 'baud': 921600, 'seconds': 12., 'frequency': '5MHz',
        'diagnostic_plan': {'workdir': str(program), 'validation': validation}, 'idle_plan': {'target': 'heartbeat',
        'operation': 'volatile_sram_only', 'validation': {'idle': True}}, 'source_sha256': {}}
    s.hw._new_json(work/'plan.json', plan)
    events = []
    monkeypatch.setattr(s.idle, 'execute_plan', lambda *args, **kwargs: events.append('idle') or
        {'passed': True, 'done_confirmed': True, 'hardware_accessed': True})
    monkeypatch.setattr(s, 'execute_program', lambda *_: {'passed': True, 'done_confirmed': True,
        'programming_attempted': True, 'hardware_accessed': True})

    class Chunks:
        def __iter__(self):
            events.append('receive')
            yield b'sealed bytes'
        def close(self):
            events.append('close')

    monkeypatch.setattr(s.receiver, 'serial_chunks', lambda *_: Chunks())
    return plan, events, work


def test_close_precedes_heartbeat_and_received_bytes_are_retained(setup):
    plan, events, work = setup
    result = s.execute_plan(plan)
    assert result['passed'] and result['idle_done_confirmed'] and not result['raw_frame_certified']
    assert events == ['receive', 'close', 'idle']
    assert (work/'received-diagnostic-wire.bin').read_bytes() == b'sealed bytes'


def test_scan_failure_never_opens_com_or_claims_heartbeat(setup, monkeypatch):
    plan, events, _ = setup
    monkeypatch.setattr(s, 'execute_program', lambda *_: {'passed': False, 'done_confirmed': False,
        'programming_attempted': False, 'hardware_accessed': True})
    result = s.execute_plan(plan)
    assert events == [] and not result['passed'] and not result['idle_restoration_attempted']


@pytest.mark.parametrize('failure', [OSError('disconnected'), KeyboardInterrupt()])
def test_receive_failure_closes_then_restores(setup, monkeypatch, failure):
    plan, events, _ = setup
    class Broken:
        def __iter__(self):
            raise failure
        def close(self):
            events.append('close')
    monkeypatch.setattr(s.receiver, 'serial_chunks', lambda *_: Broken())
    result = s.execute_plan(plan)
    assert not result['passed'] and result['idle_done_confirmed'] and events == ['close', 'idle']


def test_unknown_programming_state_attempts_fixed_restoration(setup, monkeypatch):
    plan, events, _ = setup
    def interrupted(_):
        raise KeyboardInterrupt()
    monkeypatch.setattr(s, 'execute_program', interrupted)
    result = s.execute_plan(plan)
    assert not result['passed'] and result['programming_state_unknown'] and events == ['idle']


def test_untyped_attempt_receipt_does_not_skip_restoration(setup, monkeypatch):
    plan, events, _ = setup
    monkeypatch.setattr(s, 'execute_program', lambda *_: {'passed': False})
    result = s.execute_plan(plan)
    assert not result['passed'] and result['idle_restoration_attempted'] and events == ['idle']


def test_malformed_program_receipt_is_unknown_and_still_restores(setup, monkeypatch):
    plan, events, _ = setup
    monkeypatch.setattr(s, 'execute_program', lambda *_: ['not-a-receipt'])
    result = s.execute_plan(plan)
    assert not result['passed'] and result['programming_state_unknown'] and events == ['idle']


def test_close_failure_is_retained_and_restoration_is_still_attempted(setup, monkeypatch):
    plan, events, _ = setup
    class BrokenClose:
        def __iter__(self): return iter([b'wire'])
        def close(self):
            events.append('close-error')
            raise OSError('close failed')
    monkeypatch.setattr(s.receiver, 'serial_chunks', lambda *_: BrokenClose())
    result = s.execute_plan(plan)
    assert not result['passed'] and result['serial_close_error'] and events == ['close-error', 'idle']


def test_failed_heartbeat_cannot_be_reported_as_pass(setup, monkeypatch):
    plan, events, _ = setup
    monkeypatch.setattr(s.idle, 'execute_plan', lambda *args, **kwargs: {'passed': False, 'done_confirmed': False})
    result = s.execute_plan(plan)
    assert not result['passed'] and not result['idle_done_confirmed'] and events == ['receive', 'close']


@pytest.mark.parametrize('port,seconds,freq', [('COM*',12,'5MHz'),('COM0',12,'5MHz'),
    ('COM5',True,'5MHz'),('COM5',float('nan'),'5MHz'),('COM5',float('inf'),'5MHz'),
    ('COM5',9,'5MHz'),('COM5',21,'5MHz'),('COM5',12,'10MHz')])
def test_unbounded_or_ambiguous_sessions_rejected(port, seconds, freq):
    with pytest.raises(ValueError): s.limits(port, seconds, freq)


@pytest.mark.parametrize('field,value', [('target','thermal_idle'),('baud',115200),('source_sha256',{'changed':'1'})])
def test_plan_mutations_fail_before_programming(setup, monkeypatch, field, value):
    plan, events, _ = setup
    plan[field] = value
    with pytest.raises(ValueError): s.execute_plan(plan)
    assert events == []


@pytest.mark.parametrize('nested,outer', [('100KHz',None),('1MHz','5MHz'),('10MHz','5MHz')])
def test_nested_frequency_gate_applies_even_before_any_tcl_or_artifact_access(nested, outer):
    with pytest.raises(ValueError):
        s._check_program_plan({'target':s.TARGET,'operation':'volatile_sram_only','frequency':nested},Path('.'),outer)


def test_reception_source_drift_is_failure_but_still_closes_then_restores(setup, monkeypatch):
    plan, events, _ = setup
    monkeypatch.setattr(s, 'validate_target', lambda *_: {'changed': True})
    result = s.execute_plan(plan)
    assert not result['passed'] and result['idle_done_confirmed'] and events == ['receive','close','idle']
