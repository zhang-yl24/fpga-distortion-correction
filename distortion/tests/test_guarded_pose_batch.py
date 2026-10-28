"""Synthetic mixed-wire/lifecycle tests only; never open COM or PDS."""
from pathlib import Path
from dataclasses import asdict
import copy
import json
import sys

import pytest

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'tools'));sys.path.insert(0,str(HERE))
import guarded_pose_batch as batch
import guarded_protocol as gp
from test_guarded_native_session import Clock,SyntheticUART


def poses(count=3):
    return [{'pose_id':'p'+str(i+1),'split':'held_out' if i==count-1 else 'train'} for i in range(count)]


def plan(count=3):
    return {'schema':1,'operation':'one_program_finite_pose_batch_then_heartbeat','target':batch.gn.TARGET,
        'poses':poses(count),'frame_budget':count,'frames_per_pose':1,'uart_seconds':200.,'total_seconds':600.,
        'interval_seconds':2.,'lease_ms':12000,'cues':False,
        'base_plan':{'host_session':345678,'port':'COM5'}}


@pytest.fixture
def binding():
    return {'schema':1,'camera_id':'new-replacement-camera','lens_id':'new-replacement-lens',
        'profile_id':'new-replacement-uncalibrated','capture_mode_id':batch.gn.variant_for().capture_mode_id,
        'eye':'CAM2','image_size':[640,480],'pixel_format':'RGB565_LE',
        'guarded_variant':asdict(batch.gn.variant_for()),'guarded_control_contract':copy.deepcopy(gp.GUARDED_CONTROL_CONTRACT)}


class BatchUART(SyntheticUART):
    def __init__(self,clock,*,reset_admission=True,corrupt_frame=False,**kwargs):
        super().__init__(clock,**kwargs);self.reset_admission=reset_admission;self.corrupt_frame=corrupt_frame
    def write(self,packet):
        if gp.decode_command(packet)['opcode']==gp.Opcode.GRANT and self.reset_admission:self.admitted=0
        return super().write(packet)
    def admit(self):
        super().admit()
        if self.corrupt_frame and self.current_frame is not None:
            kind,data=self.out[-1];data=data[:200]+bytes([data[200]^1])+data[201:];self.out[-1]=(kind,data)


def test_one_open_multiple_new_grants_and_real_raw_png_pose_sidecars(tmp_path,binding):
    clock=Clock();io=BatchUART(clock);events=[]
    result=batch.run_batch_uart(io,plan(),binding,tmp_path,clock=clock,cue=lambda kind,pose:events.append((kind,pose['pose_id'])))
    assert result['passed'] and result['saved_frames']==3 and result['stop_acknowledged_idle']
    commands=[gp.decode_command(p) for p in io.sent]
    assert sum(c['opcode']==gp.Opcode.OPEN for c in commands)==1
    assert [c['requested_frames'] for c in commands if c['opcode']==gp.Opcode.GRANT]==[1,1,1]
    assert [c['seq'] for c in commands]==list(range(1,len(commands)+1))
    assert len({c['session'] for c in commands})==1
    assert [p['completed_baseline'] for p in result['completed_poses']]==[0,1,2]
    assert [p['admitted_per_grant'] for p in result['completed_poses']]==[1,1,1]
    assert [f['frame_id'] for f in result['frames']]==[1,2,3]
    assert len({f['raw_sha256'] for f in result['frames']})==1  # Repeated scene deliberately retained, never certified novel.
    for frame,pose in zip(result['frames'],poses()):
        assert Path(frame['raw_path']).stat().st_size==614400 and Path(frame['image_path']).read_bytes().startswith(b'\x89PNG')
        assert frame['identity_binding']['lens_id']=='new-replacement-lens'
        side=json.loads(Path(frame['pose_sidecar_path']).read_text())
        assert (side['pose_id'],side['split'])==(pose['pose_id'],pose['split'])
        assert side['pose_novelty_verified'] is False and side['automatic_dataset_split'] is False
        assert batch.gn.hw.sha(frame['metadata_path'])==side['metadata_sha256']
    assert sum(kind=='pose_received_move_next' for kind,_ in events)==2
    assert sum(kind=='batch_complete' for kind,_ in events)==1
    assert sum(kind=='freeze_now' for kind,_ in events)==3


@pytest.mark.parametrize('fault',['no-pergrant-reset','stale-query','bad-grant-ack','bad-crc','silent'])
def test_faults_stop_without_unlimited_new_grants(tmp_path,binding,fault):
    clock=Clock();io=BatchUART(clock,reset_admission=fault!='no-pergrant-reset',
        corrupt_frame=fault=='bad-crc',stale_query=fault=='stale-query',bad_ack=fault=='bad-grant-ack',silent=fault=='silent')
    result=batch.run_batch_uart(io,plan(),binding,tmp_path,clock=clock)
    assert not result['passed'] and result['error']
    commands=[gp.decode_command(p) for p in io.sent]
    assert commands[-1]['opcode']==gp.Opcode.STOP
    assert sum(c['opcode']==gp.Opcode.GRANT for c in commands)<=2
    assert clock()<=plan()['uart_seconds']+batch.STOP_BOUND+.3


def test_operator_cue_interrupt_still_attempts_stop(tmp_path,binding):
    clock=Clock();io=BatchUART(clock)
    def cancel(kind,pose):raise KeyboardInterrupt()
    r=batch.run_batch_uart(io,plan(),binding,tmp_path,clock=clock,cue=cancel)
    assert not r['passed'] and r['stop_attempted'] and r['saved_frames']==0
    assert gp.decode_command(io.sent[-1])['opcode']==gp.Opcode.STOP


@pytest.mark.parametrize('change',[{'frame_budget':True},{'frame_budget':31},{'uart_seconds':201},
    {'total_seconds':601},{'total_seconds':599},{'interval_seconds':float('nan')},{'lease_ms':24001}])
def test_budget_bounds_are_strict_before_any_prepare(change):
    values=dict(poses=poses(),frame_budget=3,uart_seconds=200.,total_seconds=600.,interval_seconds=2.,lease_ms=12000);values.update(change)
    with pytest.raises(ValueError):batch.validate_limits(**values)


def test_cross_split_duplicate_pose_id_is_rejected():
    p=poses();p[2]['pose_id']=p[0]['pose_id']
    with pytest.raises(ValueError):batch.validate_limits(p,3,200,600,2,12000)


def test_prepare_budget_rejection_never_reaches_old_hardware_helpers(monkeypatch):
    monkeypatch.setattr(batch.gn,'prepare_plan',lambda *a,**k:pytest.fail('bad budget reached preparation'))
    with pytest.raises(ValueError):batch.prepare_batch('x','x','x',poses(),port='COM5',frame_budget=3,total_seconds=599)


def lifecycle(tmp_path,binding,monkeypatch):
    p=plan(1);p['identity']=batch.gn.capture.validate_binding(binding)
    p['base_plan'].update(workdir=str(tmp_path),program_plan={'workdir':str(tmp_path/'program')},idle_plan={'target':'heartbeat'})
    path=tmp_path/'binding.json';path.write_text(json.dumps(binding))
    active={'passed':True,'done_confirmed':True,'programming_attempted':True,'hardware_accessed':False,'session_binding_path':str(path)}
    monkeypatch.setattr(batch,'verify_plan',lambda value:tmp_path)
    monkeypatch.setattr(batch.gn.capture,'validate_live_binding',lambda *a,**k:{'synthetic':True})
    monkeypatch.setattr(batch,'run_batch_uart',lambda *a,**k:{'passed':True,'saved_frames':1})
    monkeypatch.setattr(batch,'verify_after',lambda *a,**k:None)
    return p,active


def test_lifecycle_program_once_close_before_single_fixed_restore(tmp_path,binding,monkeypatch):
    p,active=lifecycle(tmp_path,binding,monkeypatch);events=[]
    class Link:
        def close(self):events.append('close')
    def program(value):events.append('program');return active
    def restore(value,*,timeout_seconds):
        assert value==p['base_plan']['idle_plan'] and timeout_seconds==30
        events.append('idle');return {'passed':True,'done_confirmed':True,'hardware_accessed':False}
    r=batch.execute_batch(p,programmer=program,serial_factory=lambda port:Link(),restorer=restore)
    assert r['passed'] and events==['program','close','idle']


@pytest.mark.parametrize('failure',['none-result','interrupt','bad-receipt','list-receipt'])
def test_unknown_programming_outcome_restores_without_opening_com(tmp_path,binding,monkeypatch,failure):
    p,_=lifecycle(tmp_path,binding,monkeypatch);calls=[]
    def program(value):
        if failure=='interrupt':raise KeyboardInterrupt()
        if failure in ('bad-receipt','list-receipt'):
            (tmp_path/'program').mkdir();(tmp_path/'program/receipt.json').write_text('{bad json' if failure=='bad-receipt' else '[]')
            raise RuntimeError('receipt lost')
        return None
    def restore(*a,**k):calls.append('idle');return {'passed':True,'done_confirmed':True}
    r=batch.execute_batch(p,programmer=program,serial_factory=lambda port:pytest.fail('unknown program opened COM'),restorer=restore)
    assert not r['passed'] and r['idle_done_confirmed'] and calls==['idle']


def test_confirmed_no_program_attempt_skips_com_and_restore(tmp_path,binding,monkeypatch):
    p,_=lifecycle(tmp_path,binding,monkeypatch)
    r=batch.execute_batch(p,programmer=lambda value:{'passed':False,'done_confirmed':False,'programming_attempted':False},
        serial_factory=lambda port:pytest.fail('COM opened'),restorer=lambda *a,**k:pytest.fail('unneeded restore'))
    assert not r['passed'] and not r['idle_restoration_attempted']


def test_com_close_interrupt_does_not_bypass_fixed_heartbeat(tmp_path,binding,monkeypatch):
    p,active=lifecycle(tmp_path,binding,monkeypatch);events=[]
    class Link:
        def close(self):events.append('close');raise KeyboardInterrupt()
    def restore(*a,**k):events.append('idle');return {'passed':True,'done_confirmed':True}
    r=batch.execute_batch(p,programmer=lambda value:active,serial_factory=lambda port:Link(),restorer=restore)
    assert not r['passed'] and r['idle_done_confirmed'] and events==['close','idle']


def test_program_budget_exhaustion_cannot_open_com(tmp_path,binding,monkeypatch):
    p,active=lifecycle(tmp_path,binding,monkeypatch);clock=Clock();restored=[]
    def program(value):clock.value=241;return active
    r=batch.execute_batch(p,clock=clock,programmer=program,serial_factory=lambda port:pytest.fail('late program opened COM'),
        restorer=lambda *a,**k:restored.append(True) or {'passed':True,'done_confirmed':True})
    assert not r['passed'] and restored and 'program budget' in r['error']
