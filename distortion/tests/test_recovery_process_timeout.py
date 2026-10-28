"""Actual Python test children only; no PDS executable, device or port is used."""
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import program_native_raw as hw


def fake_client_plan(tmp_path):
    script=tmp_path/'program.tcl'
    script.write_text('# SYNTHETIC TEST; NEVER A DEVICE PLAN\n',encoding='utf-8')
    return {'workdir':str(tmp_path),'pds_bin':str(tmp_path/'NO_PDS_INSTALLED'),
        'tcl':{'program':{'path':str(script),'sha256':hw.sha(script)}}}


def test_real_fake_child_timeout_cleans_only_owned_process(tmp_path,monkeypatch):
    plan=fake_client_plan(tmp_path);owned=[];original=hw._start_owned
    code="import time; print('SYNTHETIC_NO_HARDWARE',flush=True); time.sleep(60)"
    # This separate test-owned sentinel is deliberately absent from owned.
    sentinel=subprocess.Popen([sys.executable,'-c',code],stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    def start(command,work,processes,stage):
        assert Path(command[0]).name=='cdt_cfg_shell.exe' and stage=='program'
        return original([sys.executable,'-c',code],work,processes,stage)
    monkeypatch.setattr(hw,'_start_owned',start)
    try:
        with pytest.raises(subprocess.TimeoutExpired):hw._client(plan,'program',owned,.2)
        assert len(owned)==1 and owned[0].poll() is None
        terminated,errors=hw._stop_owned(owned)
        assert terminated==[owned[0].pid] and errors==[] and owned[0].poll() is not None
        assert sentinel.poll() is None and sentinel.pid not in terminated
    finally:
        hw._stop_owned(owned)
        if sentinel.poll() is None:sentinel.terminate()
        sentinel.wait(timeout=5)


def test_cleanup_terminate_timeout_escalates_only_owned_with_bounded_waits():
    class Child:
        pid=77123
        def __init__(self):self.events=[];self.killed=False
        def poll(self):return None
        def terminate(self):self.events.append('terminate')
        def wait(self,timeout):
            self.events.append(('wait',timeout))
            if not self.killed:raise subprocess.TimeoutExpired('synthetic',timeout)
            return 0
        def kill(self):self.events.append('kill');self.killed=True
    child=Child();unlisted=Child()
    assert hw._stop_owned([child])==([child.pid],[])
    assert child.events==['terminate',('wait',5),'kill',('wait',5)]
    assert unlisted.events==[]


def test_real_fake_child_native0_without_fresh_postscan_DONE_still_fails(tmp_path,monkeypatch):
    plan=fake_client_plan(tmp_path);owned=[];original=hw._start_owned
    text=('Executing : cfg_scan_chain\nPG2L100H\nThis device configure situation (done bit): 1\n'
          'Executing : cfg_scan_chain successfully.\n'
          'Executing : cfg_program -device_index 0 successfully.\n')
    def start(command,work,processes,stage):
        assert Path(command[0]).name=='cdt_cfg_shell.exe'
        return original([sys.executable,'-c','print('+repr(text)+',end="")'],work,processes,stage)
    monkeypatch.setattr(hw,'_start_owned',start)
    try:
        output=hw._client(plan,'program',owned,5.)
        assert owned[0].returncode==0
        with pytest.raises(RuntimeError,match='post-program scan'):hw._check_program(output)
    finally:hw._stop_owned(owned)
