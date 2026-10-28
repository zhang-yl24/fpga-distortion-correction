"""Focused synthetic lifecycle/ASCII/control checks; no PDS, UART or real artifact dependency."""
from pathlib import Path
import binascii
import json
import struct
import sys
import copy

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import gamma_pipeline_session as session


@pytest.mark.parametrize('role,result_name', [('canonical_main','gamma-pipeline-build-result.json'),
                                            ('main_reseed','reseed-result.json')])
def test_sealed_native_build_result_required_before_download(tmp_path,role,result_name):
    manifest_path=tmp_path/'validated-build.json';manifest_path.write_text('{"mock":"manifest"}')
    sources={'rtl/mock.v':'a'*64}
    manifest={'PDSLogAudit':{'CADScriptRole':role},'SourceSHA256':sources,'SourceSHA256After':sources}
    result={'Target':session.TARGET,'Passed':True,'HardwareAccessed':False,'TimedOut':False,'ProcessExitCode':0,
        'OutputDirectory':str(tmp_path),'SourceSHA256':sources,'SourceSHA256After':sources,
        'ValidatedBuild':str(manifest_path),'ValidatedBuildSHA256':session.hw.sha(manifest_path)}
    path=tmp_path/result_name
    with pytest.raises(FileNotFoundError):session.validate_native_build_result(tmp_path,manifest,manifest_path)
    path.write_text(json.dumps(result))
    assert session.validate_native_build_result(tmp_path,manifest,manifest_path)['path']==str(path)
    for key,value in [('Passed',False),('ProcessExitCode',1),('ProcessExitCode',None),('ProcessExitCode',False),
                      ('TimedOut',True),('CleanupError','unknown process cleanup'),('SourceSHA256After',{}),
                      ('ValidatedBuildSHA256','0'*64),('OutputDirectory',str(tmp_path/'different'))]:
        bad=copy.deepcopy(result);bad[key]=value;path.write_text(json.dumps(bad))
        with pytest.raises(ValueError,match='native0'):session.validate_native_build_result(tmp_path,manifest,manifest_path)


def test_native_result_cannot_choose_an_unlisted_script_role(tmp_path):
    with pytest.raises(ValueError,match='CAD script role'):
        session.validate_native_build_result(tmp_path,{'PDSLogAudit':{'CADScriptRole':'unlisted'}},tmp_path/'manifest.json')


class Clock:
    def __init__(self): self.value=0.
    def __call__(self): return self.value


class UART:
    def __init__(self,clock,bad_ack=False):
        self.clock=clock;self.bad_ack=bad_ack;self.sent=[];self.seq=0;self.count=0
        self.requested=0;self.result=0;self.frames=0;self.commit=None
    def write(self,packet):
        assert len(packet)==12 and packet[:2]==b'\xa5\x5a'
        assert binascii.crc_hqx(packet[2:10],0xffff)==struct.unpack_from('<H',packet,10)[0]
        ver,op,seq,arg=struct.unpack_from('<BBHI',packet,2)
        assert ver==1 and op in (1,2) and seq==self.seq+1
        self.seq=seq;self.count+=1;self.sent.append((op,seq,arg))
        if op==1:self.requested=arg;self.commit=arg
        return len(packet)
    def flush(self): pass
    def read(self,count):
        self.clock.value+=.4;self.frames+=1
        values={key:0 for key,_ in session.FIELD_WIDTHS}
        values.update(CAM=0x5640,I=1,D=1,V=1,TV=1,TR=2500<<4,TA=1000,AL=0x80,
            WF=self.frames+1,CF=self.frames,PF=self.frames*2,GF=self.frames,CY=100000,
            HT=1000,MS=200,RA=self.result,HV=1,HQ=self.seq,HR=self.requested,
            HC=self.count,RC=0x12345678,PS=0xabcdef01)
        if self.bad_ack and self.commit is not None:values['HR']^=1
        if self.commit is not None:self.result=self.commit;self.commit=None
        return (' '.join(k+'='+format(values[k],'0'+str(n)+'X') for k,n in session.FIELD_WIDTHS)+'\r\n').encode()


@pytest.mark.parametrize('bad_ack',[False,True])
def test_real12byte_commands_and_independent_delayed_result_phase(tmp_path,bad_ack):
    clock=Clock();uart=UART(clock,bad_ack)
    plan={'seconds':30.,'angles_deg':[0,13.25,181.125]}
    result=session.run_uart(uart,plan,tmp_path,clock=clock)
    assert result['passed'] is (not bad_ack)
    assert uart.sent[0][0:3]==(2,1,0) and uart.sent[-1][0]==2 and uart.sent[-1][2]==0
    assert all(op in (1,2) for op,_,_ in uart.sent)  # No invented PGSTOP/Gamma opcode.
    if not bad_ack:
        assert len(result['completed_phase_tests'])==3 and result['final_auto_off_ACK']
        for row in result['completed_phase_tests']:
            assert row['control_ACK_verified'] and row['result_phase_verified']
            if row['argument']!=0:assert row['ack_RA']!=row['argument']
            assert row['result_RA']==row['argument'] and row['result_CF']>row['ack_CF']
            assert row['result_elapsed_seconds']>row['ack_elapsed_seconds']
            assert row['result_telemetry']['CY']==100000
            window=row['stable_performance']
            assert window['elapsed_seconds']>=2 and window['healthy_samples']>=3
            assert all(window['delta'][k]>0 for k in ('WF','CF','PF','GF'))
        assert all(result['delta'][k]>0 for k in ('WF','CF','PF'))
    else:assert 'requested phase ACK' in result['error']
    assert result['new_lens_optical_pass'] is False and result['mask_crc_available'] is False
    line=UART(Clock()).read(4096);assert len(line)==385 and session.parse_line(line)['H']==0
    with pytest.raises(ValueError):session.parse_line(line.replace(b'HV=01',b'HV=02'))
    with pytest.raises(ValueError):session.parse_line(line+b' ')


def test_ACK_and_result_without_complete_hold_are_not_performance_acceptance(tmp_path):
    clock=Clock()
    class InterruptedUART(UART):
        interrupted=False
        def read(self,count):
            if self.clock.value>=2.8 and not self.interrupted:
                self.interrupted=True;raise KeyboardInterrupt()
            return super().read(count)
    uart=InterruptedUART(clock)
    result=session.run_uart(uart,{'seconds':30.,'angles_deg':[13.25]},tmp_path,clock=clock)
    tested=[c for c in result['commands'] if c['kind']=='phase']
    assert tested[0]['control_ACK_verified'] and tested[0]['result_phase_verified']
    assert 'stable_performance' not in tested[0] and result['completed_phase_tests']==[]
    assert not result['passed'] and result['final_auto_off_ACK']


def test_default_prepare_is_offline_and_requires_completed_candidate(monkeypatch,tmp_path):
    (tmp_path/'fixed.sbit').write_bytes(b'SYNTHETIC NEVER PROGRAM')
    (tmp_path/'idle.sbit').write_bytes(b'SYNTHETIC NEVER PROGRAM')
    monkeypatch.setattr(session.hw,'APPROVED',tmp_path)
    monkeypatch.setattr(session,'validate_target',lambda *a:{'bitstream_path':str(tmp_path/'fixed.sbit')})
    monkeypatch.setattr(session,'helpers',lambda:{'synthetic':'only'})
    monkeypatch.setattr(session.idle,'validate_heartbeat',lambda:{'bitstream_path':str(tmp_path/'idle.sbit')})
    monkeypatch.setattr(session.idle,'prepare_plan',lambda *a,**k:{'target':'heartbeat'})
    monkeypatch.setattr(session.hw,'resolve_pds_bin',lambda *a:tmp_path)
    monkeypatch.setattr(session.hw,'listening_pids',lambda *a:pytest.fail('plan touched JTAG'))
    monkeypatch.setattr(session.hw,'_start_owned',lambda *a,**k:pytest.fail('plan started native process'))
    monkeypatch.setattr(session,'serial_open',lambda *a:pytest.fail('plan opened COM'))
    p=session.prepare_plan(tmp_path,tmp_path,port='COM5')
    assert p['hardware_accessed'] is False and p['executed'] is False and p['baud']==115200
    assert (Path(p['workdir'])/'plan.json').is_file()
    monkeypatch.setattr(session,'validate_target',lambda *a:(_ for _ in ()).throw(ValueError('missing validated-build')))
    with pytest.raises(ValueError,match='missing validated-build'):session.prepare_plan(tmp_path,tmp_path,port='COM5')


@pytest.mark.parametrize('scenario',['success','unknown','list_receipt','scan_failed','close_interrupt'])
def test_close_then_fixed_heartbeat_even_when_programming_state_unknown(tmp_path,monkeypatch,scenario):
    plan={'port':'COM5','seconds':30.,'angles_deg':[13.25],'source_sha256':{'f':'f'},
        'program_plan':{'workdir':str(tmp_path)},'idle_plan':{'target':'heartbeat'},
        'time_budget':{'recovery_client_seconds':90.}}
    monkeypatch.setattr(session,'verify_plan',lambda p:tmp_path)
    monkeypatch.setattr(session,'check_idle_plan',lambda *a:None)
    monkeypatch.setattr(session,'check_program',lambda p:None)
    monkeypatch.setattr(session,'helpers',lambda:{'f':'f'})
    monkeypatch.setattr(session,'run_uart',lambda *a,**k:{'passed':True})
    events=[]
    def program(p):
        events.append('program')
        if scenario=='unknown':return None
        if scenario=='list_receipt':
            (tmp_path/'receipt.json').write_text('[]');raise KeyboardInterrupt()
        if scenario=='scan_failed':return {'passed':False,'done_confirmed':False,'programming_attempted':False}
        return {'passed':True,'done_confirmed':True,'programming_attempted':True,'hardware_accessed':False}
    class Link:
        def close(self):
            events.append('close')
            if scenario=='close_interrupt':raise KeyboardInterrupt()
    def open_serial(port):
        assert scenario in ('success','close_interrupt');events.append('open');return Link()
    def restore(p,*,timeout_seconds):
        assert p==plan['idle_plan'] and timeout_seconds==90.;events.append('heartbeat')
        return {'passed':True,'done_confirmed':True}
    result=session.execute_plan(plan,programmer=program,serial_factory=open_serial,restorer=restore)
    assert result['passed'] is (scenario=='success')
    if scenario=='scan_failed':assert events==['program'] and not result['idle_restoration_attempted']
    else:
        assert events[-1]=='heartbeat' and result['idle_done_confirmed']
        if 'close' in events:assert events.index('close')<events.index('heartbeat')


@pytest.fixture
def fresh_plan(tmp_path,monkeypatch):
    """Real plan/script preflight with synthetic artifacts and no device APIs."""
    monkeypatch.setattr(session.hw,'APPROVED',tmp_path)
    monkeypatch.setattr(session.idle,'APPROVED',tmp_path)
    (tmp_path/'candidate.sbit').write_bytes(b'SYNTHETIC NEVER PROGRAM')
    (tmp_path/'heartbeat.sbit').write_bytes(b'SYNTHETIC NEVER PROGRAM')
    candidate={'bitstream_path':str(tmp_path/'candidate.sbit'),
        'build_dir':str(tmp_path),'profile_binding_path':None}
    heartbeat={'bitstream_path':str(tmp_path/'heartbeat.sbit')}
    monkeypatch.setattr(session,'validate_target',lambda *a:candidate)
    monkeypatch.setattr(session,'helpers',lambda:{'synthetic':'host-binding'})
    monkeypatch.setattr(session.idle,'validate_heartbeat',lambda:heartbeat)
    monkeypatch.setattr(session.hw,'resolve_pds_bin',lambda *a:tmp_path)
    monkeypatch.setattr(session.hw,'_start_owned',lambda *a,**k:pytest.fail('device process forbidden'))
    monkeypatch.setattr(session.hw,'listening_pids',lambda *a:pytest.fail('device query forbidden'))
    monkeypatch.setattr(session,'serial_open',lambda *a:pytest.fail('COM forbidden'))
    return session.prepare_plan(tmp_path,tmp_path,port='COM5',seconds=30.,frequency='1MHz',angles=[0])


def sync_plan(plan, *, idle=True):
    if idle:
        (Path(plan['idle_plan']['workdir'])/'plan.json').write_text(json.dumps(plan['idle_plan']),encoding='utf-8')
    (Path(plan['workdir'])/'plan.json').write_text(json.dumps(plan),encoding='utf-8')


def test_fresh_recovery_preflight_is_read_only_and_repeatable(fresh_plan):
    work=Path(fresh_plan['workdir'])
    for _ in range(2):assert session.verify_plan(fresh_plan)==work
    assert not (work/'result.json').exists()
    assert not (Path(fresh_plan['idle_plan']['workdir'])/'receipt.json').exists()


@pytest.mark.parametrize('case',[
    'idle_receipt','candidate_receipt','main_result','disk_mismatch','missing_disk_plan',
    'executed','hardware_accessed','done_confirmed','explicit_flag','pds','frequency','target','operation',
    'parent','candidate_alias','outside_session','missing_directory','script_text','script_hash','script_path',
    'validation','stale_host_binding',
])
def test_unusable_recovery_is_rejected_before_candidate_or_com(fresh_plan,case):
    p=fresh_plan;idle=p['idle_plan'];work=Path(p['workdir']);iw=Path(idle['workdir'])
    if case=='idle_receipt':(iw/'receipt.json').write_text('{}')
    elif case=='candidate_receipt':(Path(p['program_plan']['workdir'])/'receipt.json').write_text('{}')
    elif case=='main_result':(work/'result.json').write_text('{}')
    elif case=='disk_mismatch':(iw/'plan.json').write_text('{}')
    elif case=='missing_disk_plan':(iw/'plan.json').unlink()
    elif case in ('executed','hardware_accessed','done_confirmed'):
        idle[case]=True;sync_plan(p)
    elif case=='explicit_flag':idle['requires_explicit_execute_flag']=False;sync_plan(p)
    elif case=='pds':idle['pds_bin']=str(iw/'other-pds');sync_plan(p)
    elif case=='frequency':idle['frequency']='5MHz';sync_plan(p)
    elif case=='target':idle['target']=session.TARGET;sync_plan(p)
    elif case=='operation':idle['operation']='flash';sync_plan(p)
    elif case in ('parent','candidate_alias','outside_session','missing_directory'):
        idle['workdir']=str({'parent':work,'candidate_alias':work/'candidate-program',
            'outside_session':work.parent,'missing_directory':work/'missing'}[case]);sync_plan(p,idle=False)
    elif case=='script_text':
        f=Path(idle['tcl']['program']['path']);f.write_text(f.read_text()+'cfg_flash\n')
        idle['tcl']['program']['sha256']=session.hw.sha(f);sync_plan(p)
    elif case=='script_hash':idle['tcl']['program']['sha256']='0'*64;sync_plan(p)
    elif case=='script_path':idle['tcl']['program']['path']=p['program_plan']['tcl']['program']['path'];sync_plan(p)
    elif case=='validation':idle['validation']['bitstream_path']=str(iw/'wrong.sbit');sync_plan(p)
    elif case=='stale_host_binding':p['source_sha256']={'old':'host'};sync_plan(p)
    called=[]
    with pytest.raises((ValueError,FileNotFoundError)):
        session.execute_plan(p,programmer=lambda *a:called.append('program'),
            serial_factory=lambda *a:called.append('COM'),restorer=lambda *a,**k:called.append('restore'))
    assert called==[]
    if case!='main_result':assert not (work/'result.json').exists()


@pytest.mark.parametrize('scenario',[
    'success','attempted_failure','program_exception','open_error','uart_error','uart_interrupt',
    'close_error','restore_false','restore_no_done','restore_error','idle_used_during_uart','idle_changed_during_uart',
])
def test_real_preflight_lifecycle_always_reports_recovery_outcome(fresh_plan,monkeypatch,scenario):
    p=fresh_plan;events=[]
    def program(plan):
        events.append('program')
        if scenario=='program_exception':raise OSError('program result unknown')
        return {'passed':scenario!='attempted_failure','done_confirmed':scenario!='attempted_failure',
            'programming_attempted':True,'hardware_accessed':False}
    class Link:
        def close(self):
            events.append('close')
            if scenario=='close_error':raise OSError('close failed')
    def open_serial(port):
        events.append('open')
        if scenario=='open_error':raise OSError('open failed')
        return Link()
    def uart(*args,**kwargs):
        events.append('UART')
        if scenario=='uart_error':raise OSError('read failed')
        if scenario=='uart_interrupt':raise KeyboardInterrupt()
        iw=Path(p['idle_plan']['workdir'])
        if scenario=='idle_used_during_uart':(iw/'receipt.json').write_text('{}')
        if scenario=='idle_changed_during_uart':(iw/'plan.json').write_text('{}')
        return {'passed':True}
    def restore(plan,*,timeout_seconds):
        events.append('heartbeat');assert timeout_seconds==90.
        if scenario=='restore_error':raise OSError('heartbeat unavailable')
        return {'passed':scenario!='restore_false','done_confirmed':scenario!='restore_no_done'}
    monkeypatch.setattr(session,'run_uart',uart)
    result=session.execute_plan(p,programmer=program,serial_factory=open_serial,restorer=restore)
    assert result['passed'] is (scenario=='success')
    assert result['idle_restoration_attempted']
    if scenario in ('attempted_failure','program_exception'):assert 'open' not in events
    if scenario.startswith('idle_'):
        assert 'heartbeat' not in events and 'idle_error' in result and not result['idle_done_confirmed']
    else:
        assert events[-1]=='heartbeat'
        if 'close' in events:assert events.index('close')<events.index('heartbeat')
    assert json.loads((Path(p['workdir'])/'result.json').read_text())==result


def test_candidate_receipt_and_source_failure_cannot_block_fixed_recovery(fresh_plan,monkeypatch):
    p=fresh_plan;events=[]
    def program(plan):
        result={'passed':True,'done_confirmed':True,'programming_attempted':True,'hardware_accessed':False}
        (Path(plan['workdir'])/'receipt.json').write_text(json.dumps(result))
        return result
    class Link:
        def close(self):events.append('close')
    def uart(*args,**kwargs):
        def changed(*args):raise ValueError('candidate source changed during UART')
        monkeypatch.setattr(session,'validate_target',changed)
        return {'passed':True}
    def restore(*args,**kwargs):
        events.append('heartbeat');return {'passed':True,'done_confirmed':True}
    monkeypatch.setattr(session,'run_uart',uart)
    result=session.execute_plan(p,programmer=program,serial_factory=lambda *a:Link(),restorer=restore)
    assert not result['passed'] and 'candidate source changed' in result['error']
    assert result['idle_done_confirmed'] and events==['close','heartbeat']


@pytest.mark.parametrize('case',['session_missing','recovery_missing','candidate_missing','recovery_small',
    'recovery_changed','top_mismatch','outer_small','outer_changed','recovery_disk_changed'])
def test_budget_failures_reject_before_candidate_and_recovery(fresh_plan,case):
    p=fresh_plan
    if case=='session_missing':p.pop('time_budget')
    elif case=='recovery_missing':p['idle_plan'].pop('program_budget')
    elif case=='candidate_missing':p['program_plan'].pop('program_budget')
    elif case=='recovery_small':p['idle_plan']['program_budget']['client_timeout_seconds']=30.
    elif case=='recovery_changed':
        p['idle_plan']['program_budget']=session.idle.program_budget(p['idle_plan']['validation'],p['frequency'],100.)
    elif case=='top_mismatch':p['time_budget']['recovery_client_seconds']=80.
    elif case=='outer_small':p['time_budget']['outer_wait_seconds']=30.
    elif case=='outer_changed':p['time_budget']['outer_wait_seconds']=700.
    elif case=='recovery_disk_changed':(Path(p['idle_plan']['workdir'])/'plan.json').write_text('{}')
    if case!='outer_changed':sync_plan(p,idle=case!='recovery_disk_changed')
    calls=[]
    with pytest.raises(ValueError):
        session.execute_plan(p,programmer=lambda *a:calls.append('program'),
            serial_factory=lambda *a:calls.append('COM'),restorer=lambda *a,**k:calls.append('restore'))
    assert calls==[]


def test_session_wait_covers_both_clients_startup_cleanup_and_explicit_outer(fresh_plan):
    p=fresh_plan;b=p['time_budget']
    assert b['candidate_client_seconds']==b['recovery_client_seconds']==90.
    assert b['candidate_operation_wait_bound_seconds']==b['recovery_operation_wait_bound_seconds']==240.
    assert b['uart_observation_seconds']==30. and b['minimum_outer_wait_seconds']==540.
    assert b['outer_wait_seconds']==600.
    assert session.session_budget(p['program_plan'],p['idle_plan'],30.,550.)['outer_wait_seconds']==550.
    with pytest.raises(ValueError):session.session_budget(p['program_plan'],p['idle_plan'],30.,539.)


def test_UART_expiry_does_not_cancel_legal_recovery_or_cleanup(fresh_plan,monkeypatch):
    p=fresh_plan;clock=[0.];events=[]
    monkeypatch.setattr(session.time,'monotonic',lambda:clock[0])
    def program(plan):
        clock[0]+=43.
        return {'passed':True,'done_confirmed':True,'programming_attempted':True,'hardware_accessed':False}
    class Link:
        def close(self):events.append('close')
    def UART(*args,**kwargs):
        clock[0]+=30.;return {'passed':False,'error':'UART budget expired'}
    def restore(plan,*,timeout_seconds):
        assert timeout_seconds==90.
        events.append('restore_start');clock[0]+=48.;events.append('restore_cleanup')
        return {'passed':True,'done_confirmed':True}
    monkeypatch.setattr(session,'run_uart',UART)
    r=session.execute_plan(p,programmer=program,serial_factory=lambda *a:Link(),restorer=restore)
    assert not r['passed'] and r['idle_done_confirmed']
    assert events==['close','restore_start','restore_cleanup']
    assert r['elapsed_total_seconds']==121.>p['seconds']
    assert r['elapsed_total_seconds']<p['time_budget']['outer_wait_seconds']


@pytest.mark.parametrize('flag',['--candidate-timeout-seconds','--recovery-timeout-seconds','--outer-wait-seconds'])
def test_execute_plan_CLI_rejects_budget_override_before_loading_plan(monkeypatch,flag):
    monkeypatch.setattr(sys,'argv',['gamma_pipeline_session.py','--execute-plan','NEVER_LOAD.json',flag,'90'])
    monkeypatch.setattr(session.hw,'load_json',lambda *a:pytest.fail('override loaded a plan'))
    monkeypatch.setattr(session,'execute_plan',lambda *a:pytest.fail('override executed a plan'))
    with pytest.raises(SystemExit) as exc:session.main()
    assert exc.value.code==2
