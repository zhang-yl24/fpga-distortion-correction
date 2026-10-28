"""Heartbeat-only planning/execution boundaries. All processes are mocked."""
from pathlib import Path
import hashlib
import json
import sys
import types
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import program_idle_heartbeat as idle

SCAN = 'PG2L100H\nThe ID value is: 0x00602899\n'
PRE = ('Executing : cfg_scan_chain\nPG2L100H\nThis device configure situation (done bit): 1\n'
       'Executing : cfg_scan_chain successfully.\n')
PROGRAM = 'Executing : cfg_program -device_index 0 successfully.\n'
DONE = PRE+PROGRAM+PRE


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


@pytest.fixture
def files(tmp_path, monkeypatch):
    # tmp_path must be configured below the approved offline scratch in local runs.
    sources = {}
    for name in idle.SOURCE_SHA256:
        path = tmp_path/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT/name).read_bytes())
        sources[name] = digest(path)
    build = tmp_path/'build/heartbeat'
    (build/'generate_bitstream').mkdir(parents=True)
    (build/'place_route').mkdir()
    bit = build/'generate_bitstream/heartbeat.sbit'
    bit.write_bytes(b'SYNTHETIC TEST FIXTURE - NEVER A REAL BITSTREAM')
    manifest = {'Device': 'PG2L100H', 'Package': 'FBG676', 'SCBV': 'High Voltage', 'UnusedIO': 'UNUSED',
                'Bitstream': str(bit), 'SHA256': digest(bit)}
    manifest_path = build/'validated-build.json'
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    (build/'build.log').write_text('Executing : gen_bit_stream -scbv {High Voltage} -unused_io_status UNUSED successfully.\n')
    timing = build/'place_route/heartbeat_timing_summary_after_hold_fix.txt'
    timing.write_text('Design Summary : All Constraints Met.\n')
    pinreport = build/'place_route/heartbeat_prr.prt'
    pinreport.write_text(''.join(f'{ball}|IOBD|BANK|NET|{port}|'+('input' if port=='clk_27m' else 'output')+'|YES\n'
                                 for port, ball in idle.PINS.items()))
    artifacts = {name: digest(tmp_path/name) for name in idle.ARTIFACT_SHA256}
    monkeypatch.setattr(idle, 'ROOT', tmp_path)
    monkeypatch.setattr(idle, 'APPROVED', tmp_path)
    monkeypatch.setattr(idle, 'GOLDEN_BIT_SHA256', digest(bit))
    monkeypatch.setattr(idle, 'SOURCE_SHA256', sources)
    monkeypatch.setattr(idle, 'ARTIFACT_SHA256', artifacts)
    pds = tmp_path/'fake-pds'
    pds.mkdir()
    for name in ('cdt_js.exe', 'cdt_cfg_shell.exe'):
        (pds/name).write_bytes(b'SYNTHETIC PLACEHOLDER - POPEN MUST BE MOCKED')
    return {'work': tmp_path, 'pds': pds, 'bit': bit, 'manifest_path': manifest_path,
            'manifest': manifest, 'timing': timing, 'pinreport': pinreport}


@pytest.fixture
def processes(monkeypatch):
    state = {'processes': [], 'scan': SCAN, 'program': DONE, 'conflict': False,
             'server_exit_after_scan': False, 'conflict_after_scan': False,
             'elapsed':0.,'durations':{},'waits':[]}
    class Process:
        def __init__(self, stage):
            self.pid = 9300+len(state['processes'])
            self.stage = stage
            self.ended = False
            self.terminated = False
        def poll(self): return 0 if self.ended else None
        def wait(self, timeout=None):
            state['waits'].append((self.stage,timeout))
            duration=state['durations'].get(self.stage,0.) if not self.ended else 0.
            if duration>timeout:
                state['elapsed']+=timeout
                raise idle.hw.subprocess.TimeoutExpired(self.stage,timeout)
            state['elapsed']+=duration
            self.ended=True
            if self.stage=='scan' and state['server_exit_after_scan']: state['processes'][0].ended=True
            return 0
        def terminate(self): self.ended=True; self.terminated=True
        def kill(self): self.ended=True
    def popen(command, **kwargs):
        assert Path(command[0]).name in ('cdt_js.exe', 'cdt_cfg_shell.exe')
        stage = ('server-program' if Path(kwargs['stdout'].name).name.startswith('server-program.') else 'server') if Path(command[0]).name=='cdt_js.exe' else Path(command[command.index('-file')+1]).stem
        assert stage in ('server', 'server-program', 'scan', 'program')
        p = Process(stage)
        state['processes'].append(p)
        kwargs['stdout'].write(('SYNTHETIC SERVER' if stage.startswith('server') else state[stage]).encode())
        return p
    def listeners(port):
        if state['conflict']: return {88222}
        if state['conflict_after_scan'] and any(p.stage=='scan' and p.ended for p in state['processes']): return {88223}
        return {p.pid for p in state['processes'] if p.stage.startswith('server') and not p.ended}
    monkeypatch.setattr(idle.hw.subprocess, 'Popen', popen)
    monkeypatch.setattr(idle.hw, 'listening_pids', listeners)
    monkeypatch.setitem(sys.modules, 'serial', types.SimpleNamespace(Serial=lambda *a, **k: pytest.fail('idle helper must not open COM')))
    return state


def plan(files):
    return idle.prepare_plan(files['work'], pds_bin=files['pds'],timeout_seconds=90.)


def test_plan_default_never_touches_hardware(files, processes, capsys):
    assert idle.main(['--workdir', str(files['work']), '--pds-bin', str(files['pds'])]) == 0
    p = json.loads(capsys.readouterr().out)
    assert p['target']=='heartbeat' and not p['hardware_accessed'] and not p['executed']
    assert not processes['processes']
    text = Path(p['tcl']['program']['path']).read_text()
    assert 'heartbeat.sbit' in text and 'cfg_program -device_index 0' in text
    assert not any(name in text.lower() for name in ('flash', 'erase', 'raw_camera'))


@pytest.mark.parametrize('case', ['bit', 'source', 'timing', 'pins', 'manifest'])
def test_tampering_is_rejected_before_process_start(files, processes, case):
    path = {'bit':files['bit'], 'source':files['work']/'board/heartbeat.v', 'timing':files['timing'],
            'pins':files['pinreport'], 'manifest':files['manifest_path']}[case]
    path.write_bytes(path.read_bytes()+b' TAMPER')
    with pytest.raises(ValueError): plan(files)
    assert not processes['processes']


@pytest.mark.parametrize('field,value', [('Device','PG2L50H'), ('SCBV','Low Voltage'), ('UnusedIO','DRIVE'), ('Package','WRONG')])
def test_wrong_manifest_identity_rejected_even_after_fixture_hash_refresh(files, field, value):
    files['manifest'][field]=value
    files['manifest_path'].write_text(json.dumps(files['manifest']))
    idle.ARTIFACT_SHA256['build/heartbeat/validated-build.json']=digest(files['manifest_path'])
    with pytest.raises(ValueError): plan(files)


def test_pin_report_cannot_add_or_swap_active_pins(files):
    files['pinreport'].write_text(files['pinreport'].read_text().replace('A20|','A21|'))
    idle.ARTIFACT_SHA256['build/heartbeat/place_route/heartbeat_prr.prt']=digest(files['pinreport'])
    with pytest.raises(ValueError, match='nine'): plan(files)


def test_occupied_server_is_never_used_or_stopped(files, processes):
    p=plan(files);processes['conflict']=True
    result=idle.execute_plan(p)
    assert not result['passed'] and not result['hardware_accessed'] and not result['programming_attempted']
    assert processes['processes']==[] and result['terminated_owned_pids']==[]


@pytest.mark.parametrize('scan', ['No JTAG device\n', 'PG2L50H\nThe ID value is: 0x00602899\n',
                                  'PG2L100H\nThe ID value is: 0x00000000\n'])
def test_bad_scan_never_reaches_program(files, processes, scan):
    p=plan(files);processes['scan']=scan
    result=idle.execute_plan(p)
    assert not result['passed'] and not result['done_confirmed'] and not result['programming_attempted']
    assert [x.stage for x in processes['processes']]==['server','scan']
    assert processes['processes'][0].terminated


@pytest.mark.parametrize('text', [PRE+PROGRAM, PRE+PROGRAM+PRE.replace('done bit): 1','done bit): 0'), 'cfg_program failed\n'])
def test_missing_fresh_post_done_is_not_success(files, processes, text):
    p=plan(files);processes['program']=text
    result=idle.execute_plan(p)
    assert not result['passed'] and not result['done_confirmed'] and result['programming_attempted']


def test_only_heartbeat_target_and_exact_tcl_may_execute(files, processes):
    p=plan(files);p['target']='raw_camera_capture_cam2_ref'
    with pytest.raises(ValueError,match='disk plan'):idle.execute_plan(p)
    assert not processes['processes']
    p=plan(files)
    script=Path(p['tcl']['program']['path']);script.write_text(script.read_text()+'cfg_flash\n')
    p['tcl']['program']['sha256']=digest(script)
    with pytest.raises(ValueError,match='disk plan'):idle.execute_plan(p)
    assert not processes['processes']


def test_success_is_fresh_receipt_only_and_never_updates_legacy_status(files, processes):
    status=files['work']/'status.json';status.write_text('UNCHANGED')
    p=plan(files);result=idle.execute_plan(p)
    assert result['passed'] and result['done_confirmed'] and result['programming_attempted']
    assert [x.stage for x in processes['processes']]==['server','scan','program']
    assert status.read_text()=='UNCHANGED'
    receipt=Path(p['workdir'])/'receipt.json'
    assert receipt.is_file()
    with pytest.raises(ValueError, match='fresh'): idle.execute_plan(p)


def test_idle_scan_server_exit_restarts_owned_program_stage(files, processes):
    p=plan(files);processes['server_exit_after_scan']=True
    result=idle.execute_plan(p)
    assert result['passed'] and result['done_confirmed'] and result['programming_attempted']
    assert result['server_restarted_after_scan']
    assert [x.stage for x in processes['processes']]==['server','scan','server-program','program']
    assert result['terminated_owned_pids']==[processes['processes'][2].pid]


def test_idle_foreign_listener_after_scan_blocks_program_without_touching_it(files, processes):
    p=plan(files);processes['server_exit_after_scan']=True;processes['conflict_after_scan']=True
    result=idle.execute_plan(p)
    assert not result['passed'] and not result['programming_attempted']
    assert [x.stage for x in processes['processes']]==['server','scan']
    assert 88223 not in result['owned_pids'] and not result['terminated_owned_pids']


@pytest.mark.parametrize('timeout', [0, -1, True, float('nan'), float('inf'), 121])
def test_invalid_timeout_never_starts_process(files, processes, timeout):
    with pytest.raises(ValueError): idle.execute_plan(plan(files), timeout_seconds=timeout)
    assert not processes['processes']


@pytest.mark.parametrize('explicit',[False,True])
def test_program_over30_seconds_uses_sealed_budget_without_default_override(files,processes,explicit):
    seconds=80. if explicit else 90.
    p=idle.prepare_plan(files['work'],pds_bin=files['pds'],timeout_seconds=seconds)
    processes['durations']={'scan':5.,'program':43.}
    result=idle.execute_plan(p,**({'timeout_seconds':80.} if explicit else {}))
    assert result['passed'] and result['done_confirmed']
    assert processes['elapsed']==48. and processes['elapsed']>30.
    assert [(s,t) for s,t in processes['waits'] if s in ('scan','program')]==[('scan',seconds),('program',seconds)]
    assert result['program_budget']==p['program_budget']


def test_explicit_timeout_cannot_override_or_be_overridden_by_sealed_default(files,processes):
    p=idle.prepare_plan(files['work'],pds_bin=files['pds'],timeout_seconds=80.)
    with pytest.raises(ValueError,match='differs'):idle.execute_plan(p,timeout_seconds=90.)
    assert not processes['processes']


@pytest.mark.parametrize('case',['missing','small','changed','wrong_size','disk','receipt'])
def test_bad_or_used_budget_plan_is_rejected_before_native_process(files,processes,case):
    p=plan(files);work=Path(p['workdir'])
    if case=='missing':p.pop('program_budget')
    elif case=='small':p['program_budget']['client_timeout_seconds']=30.
    elif case=='changed':p['program_budget']=idle.program_budget(p['validation'],p['frequency'],100.)
    elif case=='wrong_size':p['program_budget']['bitstream_bytes']+=1
    elif case=='disk':(work/'plan.json').write_text('{}')
    elif case=='receipt':(work/'receipt.json').write_text('{}')
    with pytest.raises(ValueError):idle.execute_plan(p)
    assert not processes['processes']


def test_timeout_budget_uses_file_scale_and_frequency_not_UART(files):
    bit=files['work']/'SYNTHETIC-scale-only.sbit'
    with bit.open('wb') as f:
        f.write(b'SYNTHETIC NEVER PROGRAM');f.truncate(3791112)
    validation={'bitstream_path':str(bit)}
    bound=idle.program_budget(validation,'1MHz',90.)
    assert bound['minimum_client_seconds']==76
    assert bound['wire_seconds']==pytest.approx(30.328896)
    assert bound['operation_wait_bound_seconds']==240.
    for small in (30.,60.,75.):
        with pytest.raises(ValueError):idle.program_budget(validation,'1MHz',small)
    assert idle.program_budget(validation,'1MHz',80.)['client_timeout_seconds']==80.
    assert idle.program_budget(validation,'5MHz',90.)['minimum_client_seconds']==40


def test_legacy_caller_without_explicit_recovery_budget_fails_during_prepare(files,processes):
    with pytest.raises(ValueError,match='explicitly bind'):
        idle.prepare_plan(files['work'],pds_bin=files['pds'])
    assert not processes['processes']
