"""Independent failure-injection review of the 720p SRAM execution boundary.

All JTAG operations are replaced; these tests never inspect a live server or
access hardware. They exercise a changed artifact after scan, before program.
"""
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import camera720_program as program


@pytest.mark.parametrize('change', ('bitstream', 'program_script', 'scan_timeout'))
def test_post_scan_change_or_timeout_cleans_owned_server_without_programming(tmp_path, monkeypatch, change):
    work = tmp_path / 'program-review'; work.mkdir()
    bitfile = tmp_path / 'verified.sbit'; bitfile.write_bytes(b'original verified bytes')
    plan = work / 'plan.json'; plan.write_text('{}\n')
    scripts = {'scan': 'scan fixture\n', 'program': 'program fixture\n'}
    for name, body in scripts.items():
        (work / (name + '.tcl')).write_text(body, encoding='utf-8', newline='\n')
    value = {
        'PDSBin': str(tmp_path / 'inert-pds'), 'Frequency': '1MHz',
        'Bitstream': {'Path': str(bitfile), 'SHA256': program.sha(bitfile)},
        'CandidateADFSHA256': 'a' * 64,
        'BoundInputSHA256': {str(bitfile): program.sha(bitfile)},
        'Tcl': {name: {'Path': str(work / (name + '.tcl')),
                       'SHA256': program.sha(work / (name + '.tcl'))}
                for name in scripts},
    }
    monkeypatch.setattr(program, 'validate', lambda path: value)
    monkeypatch.setattr(program, 'scripts', lambda path: scripts)
    monkeypatch.setattr(program.hw, 'listening_pids', lambda port: [])
    server = SimpleNamespace(pid=7654321)
    calls, stopped = [], []

    def start(command, directory, owned, label):
        assert label == 'server'
        owned.append(server)
        return server

    def client(adapter, stage, owned, timeout):
        calls.append(stage)
        assert stage == 'scan', 'program command must never run after scan evidence changes'
        if change == 'bitstream':
            bitfile.write_bytes(b'changed during scan')
        elif change == 'program_script':
            (work / 'program.tcl').write_text('changed during scan\n')
        else:
            raise TimeoutError('mock scan deadline')
        return 'mock successful scan'

    def cleanup(owned):
        stopped.extend(p.pid for p in owned)
        return list(stopped), []

    monkeypatch.setattr(program.hw, '_start_owned', start)
    monkeypatch.setattr(program.hw, '_await_owned_server', lambda p: None)
    monkeypatch.setattr(program.hw, '_owned_server_check', lambda p: None)
    monkeypatch.setattr(program.hw, '_client', client)
    monkeypatch.setattr(program.hw, '_check_scan', lambda text: None)
    monkeypatch.setattr(program.hw, '_program_server_after_scan',
                        lambda *args: pytest.fail('must reject before preparing programming server'))
    monkeypatch.setattr(program.hw, '_stop_owned', cleanup)
    result = program.execute(plan, board_powered=True, user_notified=True)
    assert calls == ['scan'] and stopped == [server.pid]
    assert not result['Passed'] and not result['ProgrammingAttempted']
    assert not result['DoneConfirmed'] and not result['FlashWritten']
    assert result['CleanupErrors'] == [] and result['Error']
    assert (work / 'receipt.json').is_file()
