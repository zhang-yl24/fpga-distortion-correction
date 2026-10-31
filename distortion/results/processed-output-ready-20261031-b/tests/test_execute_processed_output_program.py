"""Exercise processed-output hardware boundaries with mocked processes only."""
from pathlib import Path
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import execute_processed_output_program as tool
import prepare_processed_output_program as prepare
# Share the existing Windows/JTAG process simulator, not its observer target.
from test_execute_hdmi_input_program import fake_processes, SCAN, PRE_SCAN, PROGRAM_SUCCESS, DONE


@pytest.fixture
def files(tmp_path, monkeypatch):
    build = tmp_path/'processed-output'
    build.mkdir()
    bit_work = build/'bit-fixture'
    (bit_work/'generate_bitstream').mkdir(parents=True)
    source = tmp_path/'source.v'
    source.write_bytes(b'SYNTHETIC SOURCE')
    source_bit = bit_work/'generate_bitstream/processed_output_top.sbit'
    source_bit.write_bytes(b'SYNTHETIC BIT; NEVER PROGRAM')
    evidence = bit_work/'evidence.json'
    evidence.write_text('{}', encoding='utf-8')
    plan = {'ProjectInputSHA256': {str(source): tool.bit.sha(source)}, 'WorkInputSHA256': {}}
    (bit_work/'bitstream-plan.json').write_text(json.dumps(plan), encoding='utf-8')
    verified = {'Verified': True, 'FinalADFSHA256': tool.bit.ADF_SHA,
                'Bitstream': {'Path': str(source_bit), 'SHA256': tool.bit.sha(source_bit),
                              'Bytes': source_bit.stat().st_size, 'Header': {'Design': tool.bit.TARGET}},
                'EvidenceSHA256': {'evidence.json': tool.bit.sha(evidence)}}
    monkeypatch.setattr(tool.bit, 'BUILD', build)
    monkeypatch.setattr(tool.bit, 'verify', lambda work: verified)
    pds = tmp_path/'pds'
    pds.mkdir()
    for name in ('cdt_js.exe', 'cdt_cfg_shell.exe'):
        (pds/name).write_bytes(b'SYNTHETIC EXE; NEVER RUN')
    monkeypatch.setattr(tool.bit.export, 'PDS', pds/'pds_shell.exe')
    work = build/'program-fixture'
    prepare.prepare(bit_work, work)
    return dict(source=source, bit=source_bit, evidence=evidence, work=work,
                plan=work/'plan.json', pds=pds)


def test_default_cli_is_offline(files, fake_processes, capsys):
    assert tool.main(['--plan', str(files['plan'])]) == 0
    assert json.loads(capsys.readouterr().out)['HardwareAccessed'] is False
    assert fake_processes['processes'] == []
    assert not (files['work']/'receipt.json').exists()


def test_power_confirmation_required_before_any_hardware(files, fake_processes):
    with pytest.raises(ValueError, match='user-confirmed board power'):
        tool.execute(files['plan'])
    assert fake_processes['processes'] == []


@pytest.mark.parametrize('name', ['source', 'bit', 'evidence'])
def test_drift_stops_before_hardware(files, fake_processes, name):
    files[name].write_bytes(b'ALTERED FIXTURE')
    with pytest.raises(ValueError):
        tool.execute(files['plan'], board_powered=True)
    assert fake_processes['processes'] == []


def test_changed_command_with_updated_hash_is_rejected(files, fake_processes):
    script = files['work']/'program.tcl'
    script.write_text(script.read_text()+'cfg_program_another_target\n', encoding='utf-8')
    plan = json.loads(files['plan'].read_text())
    plan['Tcl']['program']['SHA256'] = tool.bit.sha(script)
    files['plan'].write_text(json.dumps(plan), encoding='utf-8')
    with pytest.raises(ValueError, match='fixed SRAM-only Tcl'):
        tool.execute(files['plan'], board_powered=True)
    assert fake_processes['processes'] == []


@pytest.mark.parametrize('scan', [SCAN.replace('100H', '50H'), SCAN.replace('00602899', '00000000'),
                                 SCAN+'PG2L100H\n'])
def test_wrong_device_cannot_program(files, fake_processes, scan):
    fake_processes['scan'] = scan
    result = tool.execute(files['plan'], board_powered=True)
    assert not result['Passed'] and not result['ProgrammingAttempted']
    assert [p.stage for p in fake_processes['processes']] == ['server', 'scan']


def test_foreign_server_starts_and_stops_nothing(files, fake_processes):
    fake_processes['conflict'] = {99999}
    result = tool.execute(files['plan'], board_powered=True)
    assert not result['Passed'] and not result['HardwareAccessed']
    assert fake_processes['processes'] == []


def test_drift_after_scan_prevents_program(files, fake_processes):
    fake_processes['on_scan'] = lambda: files['source'].write_bytes(b'CHANGED AFTER SCAN')
    result = tool.execute(files['plan'], board_powered=True)
    assert not result['Passed'] and not result['ProgrammingAttempted']
    assert [p.stage for p in fake_processes['processes']] == ['server', 'scan']


@pytest.mark.parametrize('output', [PRE_SCAN+PROGRAM_SUCCESS,
    PRE_SCAN+PROGRAM_SUCCESS+PRE_SCAN.replace('done bit): 1', 'done bit): 0')])
def test_preexisting_done_is_not_new_done(files, fake_processes, output):
    fake_processes['program'] = output
    result = tool.execute(files['plan'], board_powered=True)
    assert result['ProgrammingAttempted'] and not result['DoneConfirmed'] and not result['Passed']


def test_success_preserves_plan_and_cleans_only_owned_processes(files, fake_processes):
    before = files['plan'].read_bytes()
    result = tool.execute(files['plan'], board_powered=True)
    assert result['Passed'] and result['DoneConfirmed'] and not result['FlashWritten']
    assert files['plan'].read_bytes() == before
    assert [p.stage for p in fake_processes['processes']] == ['server', 'scan', 'program']
    assert fake_processes['processes'][0].terminated
    assert all(p.pid in result['OwnedPIDs'] for p in fake_processes['processes'] if p.terminated or p.killed)


def test_owned_scan_server_can_exit_before_program(files, fake_processes):
    fake_processes['server_exit_after_scan'] = True
    result = tool.execute(files['plan'], board_powered=True)
    assert result['Passed'] and result['ServerRestartedAfterScan']
    assert [p.stage for p in fake_processes['processes']] == ['server', 'scan', 'server-program', 'program']


def test_foreign_replacement_server_prevents_program(files, fake_processes):
    fake_processes['server_exit_after_scan'] = True
    fake_processes['conflict_after_scan'] = {99998}
    result = tool.execute(files['plan'], board_powered=True)
    assert not result['Passed'] and not result['ProgrammingAttempted']
    assert [p.stage for p in fake_processes['processes']] == ['server', 'scan']


def test_timeout_cleans_owned_processes(files, fake_processes):
    fake_processes['timeout_stage'] = 'scan'
    result = tool.execute(files['plan'], board_powered=True, timeout_seconds=.01)
    assert not result['Passed'] and not result['ProgrammingAttempted']
    assert all(p.terminated for p in fake_processes['processes'])


def test_cleanup_failure_cannot_pass(files, fake_processes):
    fake_processes['cleanup_failure'] = True
    result = tool.execute(files['plan'], board_powered=True)
    assert not result['Passed'] and result['CleanupErrors']


@pytest.mark.parametrize('seconds', [True, 0, -1, float('nan'), float('inf'), 301])
def test_invalid_timeout_never_starts_process(files, fake_processes, seconds):
    with pytest.raises(ValueError):
        tool.execute(files['plan'], board_powered=True, timeout_seconds=seconds)
    assert fake_processes['processes'] == []
