"""Offline CAM1 variant boundaries; no serial/JTAG/PDS process is opened."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import prepare_guarded_cam1 as prep
import build_guarded_cam1 as builder
import guarded_protocol as gp


def test_real_exact_clone_and_inherited_closure():
    result = prep.verify_clone()
    assert result['target'] == prep.TARGET
    assert len(result['source_files']) == 107
    assert len(result['CloneVerification']['SharedSourceSHA256']) == 103
    assert result['physical_eye'] is None
    assert result['GuardedControlContract'] == {**gp.GUARDED_CONTROL_CONTRACT, 'build_tag': gp.CAM1_BUILD_TAG}
    assert result['RawCaptureContract'] == prep.load(prep.ROOT/f'board/{prep.ORIGINAL}-sources.json')['RawCaptureContract']
    old_pins = prep.load(prep.ROOT/f'board/{prep.ORIGINAL}-pins.json')
    new_pins = prep.load(prep.ROOT/f'board/{prep.TARGET}-pins.json')
    assert len(new_pins) == len(set(new_pins.values())) == 129
    assert {key for key in old_pins if old_pins[key] != new_pins[key]} == {key for key in old_pins if key.startswith('cam_')}
    assert new_pins['cam_data[5]'] == 'Y21' and new_pins['uart_rxd'] == 'B24'


def test_top_only_identity_comments_and_module_change():
    old = (prep.ROOT/f'board/{prep.ORIGINAL}.v').read_bytes()
    new = prep.clone_top(old)
    assert new == (prep.ROOT/f'board/{prep.TARGET}.v').read_bytes()
    # Strip comments and reverse exactly the three data identities/module.
    without_comments = lambda value: b'\n'.join(line for line in value.splitlines() if not line.lstrip().startswith(b'//'))
    reversed_new = new.replace(prep.TARGET.encode(), prep.ORIGINAL.encode()).replace(b"52473101", b"52473201").replace(b"43414d31", b"43414d32").replace(b"CAMERA_SLOT=2'b01", b"CAMERA_SLOT=2'b10")
    assert without_comments(reversed_new) == without_comments(old)


def test_top_missing_identity_anchor_rejected():
    with pytest.raises(ValueError, match='anchor'):
        prep.clone_top((prep.ROOT/f'board/{prep.ORIGINAL}.v').read_bytes().replace(b'52473201', b'52473202'))


def test_fdc_missing_pad_rejected():
    with pytest.raises(ValueError, match='FDC'):
        prep.clone_fdc(b'', {'cam_data[5]': 'AA23'}, {'cam_data[5]': 'Y21'})


def test_factory_conflict_prechecked_before_any_write(tmp_path, monkeypatch):
    (tmp_path/'second').write_bytes(b'other candidate')
    monkeypatch.setattr(prep, 'ROOT', tmp_path)
    monkeypatch.setattr(prep, 'expected_files', lambda: ({'first': b'new', 'second': b'expected'}, {}))
    with pytest.raises(ValueError, match='refusing to overwrite'):
        prep.prepare()
    assert not (tmp_path/'first').exists()
    assert (tmp_path/'second').read_bytes() == b'other candidate'


def test_builder_default_plan_never_starts_process(tmp_path, monkeypatch):
    monkeypatch.setattr(builder.subprocess, 'Popen', lambda *a, **k: pytest.fail('default plan accessed PDS'))
    report = builder.run_build(tmp_path/'plan')
    assert report['ExecuteBuild'] is False and report['HardwareAccessed'] is False
    assert not (tmp_path/'plan'/'validated-build.json').exists()


def test_builder_execute_requires_cam1_sim_before_output(tmp_path):
    work = tmp_path/'missing-sim'
    with pytest.raises(ValueError, match='CAM1 parameterized simulation'):
        builder.run_build(work, execute=True)
    assert not work.exists()


@pytest.mark.parametrize('bound', [True, 0, 59, 1801, float('nan'), float('inf')])
def test_builder_finite_bound_rejected_before_process(tmp_path, bound):
    with pytest.raises(ValueError, match='bound'):
        builder.run_build(tmp_path/'bound', timeout_seconds=bound)
    assert not (tmp_path/'bound').exists()


def test_cam2_sim_cannot_replace_cam1_parameterized_evidence():
    with pytest.raises(ValueError, match='CAM1 parameterized simulation'):
        prep.validate_simulation(prep.ROOT/prep.INHERITED_SIMULATION)


def _pin_report(path, pins, *, wrong_direction=False):
    rows = []
    import re
    for port, pad in pins.items():
        direction = ('input' if re.fullmatch(r'clk_27m|clk_p|clk_n|cam_pclk|cam_vsync|cam_href|cam_data\[\d+\]|uart_rxd', port)
                     else 'inout' if re.fullmatch(r'cam_rst_n|cam_scl|cam_sda|hd_scl|hd_sda|mem_dq\[\d+\]|mem_dqs(_n)?\[\d+\]', port)
                     else 'output')
        if wrong_direction and port == 'cam_data[5]':
            direction = 'output'
        rows.append('|'.join([pad, '', '', '', port, direction, 'YES']))
    path.write_text('\n'.join(rows))


def test_final_all129_pin_directions_and_cam1_d5(tmp_path):
    pins = prep.load(prep.ROOT/f'board/{prep.TARGET}-pins.json')
    path = tmp_path/'pins.prt'
    _pin_report(path, pins)
    assert builder.validate_pins(path) == pins
    pins['cam_data[5]'] = 'AA23'
    _pin_report(path, pins)
    with pytest.raises(ValueError, match='CAM1 exact129'):
        builder.validate_pins(path)


def test_wrong_camera_input_direction_rejected(tmp_path):
    path = tmp_path/'pins.prt'
    _pin_report(path, prep.load(prep.ROOT/f'board/{prep.TARGET}-pins.json'), wrong_direction=True)
    with pytest.raises(ValueError, match='direction'):
        builder.validate_pins(path)


def test_no_output_overwrite(tmp_path):
    with pytest.raises(ValueError, match='no overwrite'):
        builder.run_build(tmp_path)


def test_tb_covers_cam1_status_and_held_raw_identity():
    tb = prep.cam1_testbench()
    assert b".BUILD_TAG(32'h52473101),.CAMERA_ID(32'h43414d31),.CAMERA_SLOT(2'b01)" in tb
    assert b"u32(12)!=32'h52473101" in tb
    assert b"dut.held_camera_id!==32'h43414d31 || dut.held_eye!==2'b01" in tb


@pytest.mark.parametrize('failure', ['nonzero', 'timeout', 'interrupt'])
def test_owned_offline_pds_failure_never_validates_and_stops_if_running(tmp_path, monkeypatch, failure):
    pds = tmp_path/'existing-pds'
    pds.mkdir()
    (pds/'pds_shell.exe').write_bytes(b'mock existing tool')
    sim = tmp_path/'synthetic-sim.json'
    sim.write_text('{}')
    monkeypatch.setattr(prep, 'validate_simulation', lambda path: {})
    class Child:
        pid = 4242
        returncode = None
        def poll(self):
            return self.returncode
        def wait(self, timeout):
            if failure == 'timeout':
                raise builder.subprocess.TimeoutExpired('offline-pds', timeout)
            if failure == 'interrupt':
                raise KeyboardInterrupt()
            self.returncode = 9
            return 9
    child = Child()
    starts, stops = [], []
    def start(command, **kwargs):
        starts.append(command)
        assert Path(command[0]).name == 'pds_shell.exe'
        assert command[1] == '-file' and command[-1] == prep.TARGET
        assert all('cfg_program' not in arg for arg in command)
        return child
    def stop(owned, work):
        assert owned is child
        stops.append(owned.pid)
        child.returncode = -1
    monkeypatch.setattr(builder.subprocess, 'Popen', start)
    monkeypatch.setattr(builder, 'stop_owned', stop)
    work = tmp_path/'failed-build'
    result = builder.run_build(work, execute=True, simulation_evidence=sim, pds_bin=pds)
    assert result['Passed'] is False and len(starts) == 1
    assert result['TimedOut'] is (failure == 'timeout')
    assert stops == ([] if failure == 'nonzero' else [4242])
    assert not (work/'validated-build.json').exists()
    assert (work/'cam1-guarded-build-result.json').is_file()
