"""One guarded CAM2 program, one OPEN, explicit finite one-frame pose grants, heartbeat finally."""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import json
import math
import time
import threading

import guarded_native_session as gn

ROOT=gn.ROOT
PROGRAM_BOUND=240
RESTORE_BOUND=120
STOP_BOUND=10
HOUSEKEEPING_BOUND=30
UART_MAX=200
LEASE_MAX=24000


def number(value,low,high,name):
    if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:
        raise ValueError(name+' must be finite within '+str(low)+'..'+str(high))
    return value


def validate_limits(poses,frame_budget,uart_seconds,total_seconds,interval_seconds,lease_ms):
    if type(frame_budget) is not int or not 1<=frame_budget<=30:
        raise ValueError('explicit total frame budget must be integer1..30')
    if type(poses) is not list or len(poses)!=frame_budget:raise ValueError('one explicit pose_id/split per budgeted frame required')
    seen=set()
    for pose in poses:
        if type(pose) is not dict or not {'pose_id','split'}.issubset(pose) or not set(pose).issubset({'pose_id','split','description'}):
            raise ValueError('pose schema is pose_id/split and optional description')
        label=gn.capture.safe_label(pose['pose_id'],'pose_id')
        if len(label)>40 or label in seen or pose['split'] not in ('train','held_out','unassigned'):
            raise ValueError('unique pose IDs<=40 chars and explicit train/held_out/unassigned split required')
        if 'description' in pose and (type(pose['description']) is not str or len(pose['description'])>500):raise ValueError('pose description must be text<=500 chars')
        seen.add(label)
    number(uart_seconds,15,UART_MAX,'UART seconds');number(total_seconds,1,600,'total session seconds')
    number(interval_seconds,0,30,'interpose minimum seconds')
    if type(lease_ms) is not int or not 1<=lease_ms<=LEASE_MAX:raise ValueError('each GRANT1 lease must be integer1..24000ms')
    if PROGRAM_BOUND+uart_seconds+STOP_BOUND+RESTORE_BOUND+HOUSEKEEPING_BOUND>total_seconds:
        raise ValueError('total budget must include program240/UART/STOP10/heartbeat120/housekeeping30 within600s')


def load_poses(path,skip_ids=()):
    value=gn.capture.load_json(path)
    if type(value) is dict and value.get('kind')=='explicit_capture_plan_not_a_ready_calibration_manifest':
        value=[{'pose_id':row['pose_id'],'split':row['split'],'description':row['instruction']} for row in value['pose_order']]
    if type(value) is not list:raise ValueError('pose input must be an explicit list or the fixed capture-plan pose_order')
    available={row.get('pose_id') for row in value}
    if any(label not in available for label in skip_ids):raise ValueError('unknown explicit skipped pose ID')
    return [row for row in value if row.get('pose_id') not in skip_ids]


def helpers():
    return {**gn._helpers(), 'tools/guarded_pose_batch.py':gn.hw.sha(__file__)}


def prepare_batch(review_binding,build_dir,workdir,poses,*,port,frame_budget,uart_seconds=200.,
                  total_seconds=600.,interval_seconds=2.,lease_ms=12000,frequency='5MHz',pds_bin=None,cues=False):
    validate_limits(poses,frame_budget,uart_seconds,total_seconds,interval_seconds,lease_ms)
    if type(cues) is not bool:raise ValueError('cues must be boolean')
    # Reuse the fixed source-bound program/heartbeat preparation, never its one-GRANT UART runner.
    base=gn.prepare_plan(review_binding,build_dir,workdir,port=port,scenario='capture',frames=1,
        seconds=45.,lease_ms=lease_ms,frequency=frequency,pds_bin=pds_bin,target=gn.TARGET)
    binding=base['program_plan']['validation']['binding']
    plan={'schema':1,'operation':'one_program_finite_pose_batch_then_heartbeat','target':gn.TARGET,
        'base_plan':base,'poses':poses,'frame_budget':frame_budget,'frames_per_pose':1,'uart_seconds':uart_seconds,
        'total_seconds':total_seconds,'interval_seconds':interval_seconds,'lease_ms':lease_ms,'cues':cues,
        'identity':gn.capture.validate_binding(binding),'source_sha256':helpers(),
        'ideal_wire_seconds_for_all_frames':frame_budget*(614444*10/921600),'all_planned_poses_guaranteed':False,
        'timing_budget':{'program_bound_seconds':PROGRAM_BOUND,'stop_bound_seconds':STOP_BOUND,
            'heartbeat_bound_seconds':RESTORE_BOUND,'heartbeat_per_client_timeout_seconds':30,
            'housekeeping_margin_seconds':HOUSEKEEPING_BOUND},
        'pose_novelty_verified':False,'automatic_dataset_split':False,
        'limits':'Default plan only. Each declared pose gets at most one new GRANT1; labels and lens identity are operator declarations. Intervals do not prove distinct poses. Corner detection, duplicate/coverage checks and train/holdout suitability remain post-capture work. Finite CPU/native-helper budgets are not a hardware wall-clock watchdog.'}
    gn.hw._new_json(Path(base['workdir'])/'batch-plan.json',plan)
    return plan


def verify_plan(plan):
    validate_limits(plan['poses'],plan['frame_budget'],plan['uart_seconds'],plan['total_seconds'],plan['interval_seconds'],plan['lease_ms'])
    base=plan['base_plan'];work=Path(base['workdir']).resolve()
    if (plan.get('schema')!=1 or plan.get('operation')!='one_program_finite_pose_batch_then_heartbeat'
            or plan.get('target')!=gn.TARGET or type(plan.get('frames_per_pose')) is not int or plan['frames_per_pose']!=1 or type(plan.get('cues')) is not bool
            or not work.is_dir() or not work.is_relative_to(gn.hw.APPROVED.resolve())
            or (work/'batch-result.json').exists()):raise ValueError('fresh fixed CAM2 batch plan required')
    if gn.capture.load_json(work/'batch-plan.json')!=plan or gn.capture.load_json(work/'plan.json')!=base or plan['source_sha256']!=helpers():
        raise ValueError('batch/base/helper sources changed after planning')
    expected_budget={'program_bound_seconds':PROGRAM_BOUND,'stop_bound_seconds':STOP_BOUND,
        'heartbeat_bound_seconds':RESTORE_BOUND,'heartbeat_per_client_timeout_seconds':30,
        'housekeeping_margin_seconds':HOUSEKEEPING_BOUND}
    if not gn._same_contract(plan.get('timing_budget'),expected_budget):raise ValueError('fixed program/UART/STOP/heartbeat budget changed')
    gn._validate_exit(base)
    current=gn.validate_program_binding(base['program_plan']['validation']['binding_path'],base['program_plan']['validation']['build']['build_dir'])
    if current!=base['program_plan']['validation'] or plan['identity']!=gn.capture.validate_binding(current['binding']):raise ValueError('build/new lens identity binding changed')
    gn._check_tcl(base['program_plan'],gn.hw._scripts)
    return work


def cue_default(kind,pose):
    labels={'prepare_pose':'准备姿态','freeze_now':'请保持静止，正在采集','pose_received_move_next':'上一张已完整接收，请换下一姿态','batch_complete':'本批已完整接收，正在恢复空闲配置'}
    print(labels.get(kind,kind)+': '+pose['pose_id']+' ['+pose['split']+'] '+pose.get('description',''),flush=True)
    if kind in ('pose_received_move_next','batch_complete'):
        def chirp():
            try:
                import winsound
                winsound.Beep(1000,100);time.sleep(.08);winsound.Beep(1000,100)
            except (ImportError,RuntimeError,OSError):pass
        threading.Thread(target=chirp,daemon=True).start()  # Never block the UART reader.


def run_batch_uart(io,plan,binding,work,*,build_record=None,source_kind='offline_uart_replay',
                   clock=time.monotonic,deadline=None,cue=None):
    """Capture-only persistent OPEN/sequence controller; no COM/JTAG is opened here."""
    validate_limits(plan['poses'],plan['frame_budget'],plan['uart_seconds'],plan['total_seconds'],plan['interval_seconds'],plan['lease_ms'])
    if source_kind not in ('physical_native_camera','offline_uart_replay') or source_kind=='physical_native_camera' and not build_record:
        raise ValueError('physical capture requires its live source-bound build record')
    variant=gn.variant_for(gn.TARGET);gn._validate_mode_binding(binding,variant)
    work=Path(work)
    if not work.is_dir():raise ValueError('existing output directory required')
    gp=gn.protocol();parser=gp.GuardedStreamParser(expected_build_tag=gn.BUILD_TAG)
    started=clock();deadline=min(started+plan['uart_seconds'],deadline if deadline is not None else started+plan['uart_seconds'])
    session=plan['base_plan']['host_session']
    if type(session) is not int or not 1<=session<=0xffffffff:raise ValueError('fresh nonzero session required')
    saved=[];pose_results=[];commands=[];last=None;last_at=None;pending=None;seq=0
    phase='boot';pose_index=0;baseline=0;last_frame_id=0;frame_for_pose=None;grant_ack=None
    ready_at=started;frozen_at=None;header_seen=False;quiet=[];leading=None;error=None;stop_ack=False
    callback=cue or (cue_default if plan.get('cues') else lambda kind,pose:None)
    files={name:work/name for name in ('batch-received-wire.bin','batch-tx-commands.jsonl','batch-status-events.jsonl','batch-frames.jsonl')}
    def stamp():return {'host_elapsed_seconds':clock()-started,'host_utc':datetime.now(timezone.utc).isoformat()}
    with files['batch-received-wire.bin'].open('xb') as rx,files['batch-tx-commands.jsonl'].open('x',encoding='utf-8') as tx,files['batch-status-events.jsonl'].open('x',encoding='utf-8') as sl,files['batch-frames.jsonl'].open('x',encoding='utf-8') as fl:
        def send(opcode,arg=0):
            nonlocal seq,pending
            seq+=1;packet=gp.encode_command(opcode,seq,session,arg)
            record={**stamp(),**gp.decode_command(packet),'wire_hex':packet.hex(),'execution_acknowledged':False}
            commands.append(record);tx.write(json.dumps(record)+'\n');tx.flush()
            before={k:last[k] for k in ('accepted_commands','rejected_commands','duplicate_commands','rx_errors')} if last else None
            pending={'record':record,'before':before,'sent_at':clock()}
            if io.write(packet)!=16:raise RuntimeError('incomplete command write')
            io.flush()
        def freeze_notice():
            nonlocal header_seen,frozen_at
            if not header_seen:
                header_seen=True;frozen_at=clock()  # Evidence timestamp only; no blocking/sound during RAW.
        def consume(chunk,stopping=False):
            nonlocal last,last_at,leading,pending,phase,baseline,grant_ack,frame_for_pose,last_frame_id,pose_index,ready_at,header_seen,frozen_at,quiet,stop_ack
            if not chunk:return
            rx.write(chunk);rx.flush();events=parser.feed(chunk)
            if parser.rejected:raise RuntimeError('mixed-stream CRC/framing failure')
            if leading is None and events:
                leading=parser.discarded
                if leading>127:raise RuntimeError('more than one leading partial status')
            if leading is not None and parser.discarded!=leading:raise RuntimeError('corrupt/interleaved mixed-stream bytes')
            for event in events:
                if event['kind']=='frame':
                    if grant_ack is None or frame_for_pose is not None or pose_index>=len(plan['poses']):raise RuntimeError('frame without this pose GRANT ACK')
                    frame=event['frame']
                    if [frame.width,frame.height]!=[640,480] or frame.frame_id!=last_frame_id+1 or len(saved)>=plan['frame_budget']:raise RuntimeError('frame geometry/global ID/total budget differs')
                    freeze_notice();pose=plan['poses'][pose_index]
                    item=gn._save_guarded_frame(frame,binding,work,'posebatch-'+str(session)+'-'+pose['pose_id'],
                        variant=variant,source_kind=source_kind,build_record=build_record)
                    sidecar={'schema':1,'pose_id':pose['pose_id'],'split':pose['split'],'description':pose.get('description',''),
                        'pose_label_source':'explicit_operator_plan','pose_novelty_verified':False,'automatic_dataset_split':False,
                        'identity_binding':item['identity_binding'],'metadata_path':item['metadata_path'],'metadata_sha256':item['metadata_sha256'],
                        'raw_sha256':item['raw_sha256'],'image_sha256':item['image_sha256'],'source_crc32':item['source_crc32'],
                        'frame_id':frame.frame_id,'grant_seq':grant_ack['last_accepted_seq'],'grant_ack_snapshot_seq':grant_ack['snapshot_seq'],
                        'frozen_header_host_elapsed_seconds':frozen_at-started,'exposure_time_verified':False,
                        'limits':'One transaction for the declared pose label. Scene novelty/corners/coverage/duplicates and split suitability are not established by this collector.'}
                    sidepath=work/('pose-'+pose['pose_id']+'-frame'+str(frame.frame_id)+'.json');gn.hw._new_json(sidepath,sidecar)
                    item.update(pose_id=pose['pose_id'],split=pose['split'],pose_sidecar_path=str(sidepath),pose_sidecar_sha256=gn.hw.sha(sidepath))
                    saved.append(item);frame_for_pose=item;last_frame_id=frame.frame_id
                    fl.write(json.dumps(item,allow_nan=False)+'\n');fl.flush();continue
                s=event['status']
                if last is not None:
                    delta=(s['snapshot_seq']-last['snapshot_seq'])&0xffffffff
                    if not 0<delta<0x80000000 or s['uptime_ms']<last['uptime_ms'] or s['completed_frames']<last['completed_frames']:raise RuntimeError('status/global completion replay or regression')
                    if s['temperature_samples']<last['temperature_samples'] or s['temperature_conversions']<last['temperature_conversions'] or s['temperature_samples']-last['temperature_samples']>s['temperature_conversions']-last['temperature_conversions']:raise RuntimeError('ADC epoch regression')
                if s['admitted_frames']>1 or s['completed_frames']>plan['frame_budget']:raise RuntimeError('hardware one-frame/global budget exceeded')
                sl.write(json.dumps({**s,**stamp()})+'\n');sl.flush();previous=last;last=s;last_at=clock()
                if stopping:
                    if pending and s['session_id']==session and s['last_received_seq']==pending['record']['seq'] and s['last_opcode']==int(gp.Opcode.STOP) and s['last_result']==int(gp.Result.ACCEPTED) and s['last_accepted_seq']==pending['record']['seq']:
                        before=pending['before']
                        exact=before is not None and s['accepted_commands']==before['accepted_commands']+1 and all(s[k]==before[k] for k in ('rejected_commands','duplicate_commands','rx_errors'))
                        pending['record']['execution_acknowledged']=exact;stop_ack=exact and gn._idle_status(s)
                    continue
                if phase not in ('boot','open') and s['session_id']!=session:raise RuntimeError('persistent host session changed unexpectedly')
                if phase!='boot' and not gn.healthy_status(s):raise RuntimeError('camera/ADC/safety became unhealthy; no further GRANT')
                if phase=='boot':
                    if any(s[k] for k in ('session_id','accepted_commands','rejected_commands','duplicate_commands','rx_errors','completed_frames','admitted_frames')):raise RuntimeError('fresh program has prior session/frame state')
                    if s['camera_error'] or s['raw_fault'] or s['flags']['camera_failed'] or s['flags']['temp_failed']:raise RuntimeError('boot camera/core/ADC failure')
                    if previous and gn._idle_status(s) and gn.healthy_status(s) and gn.healthy_status(previous) and s['temperature_samples']>previous['temperature_samples']:
                        send(gp.Opcode.OPEN);phase='open'
                elif pending and s['session_id']==session and s['last_received_seq']==pending['record']['seq']:
                    command=pending['record'];before=pending['before']
                    if (s['last_opcode']!=command['opcode'] or s['last_result']!=int(gp.Result.ACCEPTED) or s['last_accepted_seq']!=command['seq']
                        or s['accepted_commands']!=before['accepted_commands']+1 or any(s[k]!=before[k] for k in ('rejected_commands','duplicate_commands','rx_errors'))):raise RuntimeError('ACK/counters do not prove exact command execution')
                    command.update(execution_acknowledged=True,ack_snapshot_seq=s['snapshot_seq']);pending=None
                    if phase=='open':phase='waiting';ready_at=clock()+plan['interval_seconds'];callback('prepare_pose',plan['poses'][pose_index])
                    elif phase=='query':
                        if not gn._idle_status(s) or s['completed_frames']!=len(saved):raise RuntimeError('fresh QUERY is not healthy idle at the global completion baseline')
                        baseline=s['completed_frames'];send(gp.Opcode.GRANT,gp.grant_argument(1,plan['lease_ms']));phase='grant'
                    elif phase=='grant':grant_ack=dict(s);phase='active'
                if phase=='active':
                    if not baseline<=s['completed_frames']<=baseline+1 or s['completed_frames']-baseline>s['admitted_frames']:raise RuntimeError('per-GRANT admission/global completion mismatch')
                    complete=(frame_for_pose is not None and gn._idle_status(s) and s['admitted_frames']==1
                        and s['completed_frames']==baseline+1 and s['remaining_frames']==0 and s['stop_reason']==int(gp.StopReason.FRAME_BUDGET))
                    if complete:
                        quiet.append(s)
                        if len(quiet)>=2 and quiet[-1]['uptime_ms']-quiet[0]['uptime_ms']>=500:
                            pose_results.append({'pose_id':plan['poses'][pose_index]['pose_id'],'frame_id':last_frame_id,'completed_baseline':baseline,'completed_after':s['completed_frames'],'admitted_per_grant':1})
                            pose_index+=1
                            if pose_index==len(plan['poses']):
                                phase='finished';callback('batch_complete',plan['poses'][pose_index-1])
                            else:
                                phase='waiting';ready_at=clock()+plan['interval_seconds'];grant_ack=None;frame_for_pose=None;header_seen=False;frozen_at=None;quiet=[]
                                callback('pose_received_move_next',plan['poses'][pose_index])
                    else:quiet=[]
            if (not stopping and phase=='active' and grant_ack is not None and gn._frame_header_pending(parser)
                    and int.from_bytes(parser.buffer[12:16],'little')==last_frame_id+1):freeze_notice()
        try:
            while clock()<deadline and phase!='finished':
                consume(io.read(8192))
                if pending and clock()-pending['sent_at']>5:raise TimeoutError('command ACK timed out')
                if phase=='waiting' and clock()>=ready_at and last_at is not None and clock()-last_at<2.5 and gn.healthy_status(last) and gn._idle_status(last):
                    callback('freeze_now',plan['poses'][pose_index]);send(gp.Opcode.QUERY);phase='query'
            if phase!='finished':raise TimeoutError('finite UART batch budget expired; valid partial captures retained')
        except (Exception,KeyboardInterrupt) as exc:error=type(exc).__name__+': '+str(exc)
        finally:
            try:
                send(gp.Opcode.STOP);stop_until=clock()+STOP_BOUND
                while clock()<stop_until and not stop_ack:consume(io.read(8192),stopping=True)
            except (Exception,KeyboardInterrupt) as exc:
                if error is None:error='STOP '+type(exc).__name__+': '+str(exc)
    return {'schema':1,'passed':error is None and stop_ack and len(pose_results)==len(plan['poses']),
        'partial':len(pose_results)<len(plan['poses']),'error':error,'host_session':session,'saved_frames':len(saved),
        'frames':saved,'completed_poses':pose_results,'tx_commands':commands,'last_status':last,'stop_attempted':True,
        'stop_acknowledged_idle':stop_ack,'parser_rejected':parser.rejected,'pose_novelty_verified':False,
        'identity':gn.capture.validate_binding(binding),'wire_path':str(files['batch-received-wire.bin']),
        'wire_sha256':gn.hw.sha(files['batch-received-wire.bin']),'elapsed_seconds':clock()-started}


def verify_after(plan,binding_path,binding_sha,binding,build):
    if gn.hw.sha(binding_path)!=binding_sha or helpers()!=plan['source_sha256']:raise ValueError('binding/helper source changed during batch')
    base=plan['base_plan'];program=base['program_plan']
    if gn.validate_program_binding(program['validation']['binding_path'],program['validation']['build']['build_dir'])!=program['validation']:
        raise ValueError('build/preprogram/source closure changed during batch')
    if gn.capture.validate_live_binding(binding,base_dir=binding_path.parent)!=build:raise ValueError('live receipt/build/source closure changed during batch')


def execute_batch(plan,*,clock=time.monotonic,programmer=None,serial_factory=None,restorer=None,cue=None):
    work=verify_plan(plan);base=plan['base_plan'];programmer=programmer or gn.execute_program
    serial_factory=serial_factory or gn._serial;restorer=restorer or gn.idle.execute_plan
    result={'schema':1,'operation':plan['operation'],'passed':False,'hardware_accessed':False,
        'program':None,'summary':None,'idle_program':None,'idle_done_confirmed':False,'idle_restoration_attempted':False}
    link=None;entered=False;attempted=False;started=clock()
    try:
        entered=True;result['program']=programmer(base['program_plan']);active=result['program']
        if not isinstance(active,dict) or type(active.get('programming_attempted')) is not bool:
            attempted=True;raise RuntimeError('unknown programming outcome')
        attempted=active['programming_attempted'];result['hardware_accessed']|=bool(active.get('hardware_accessed'))
        if active.get('passed') is not True or active.get('done_confirmed') is not True:raise RuntimeError('guarded SRAM/DONE unconfirmed; COM remains closed')
        if not attempted:
            attempted=True;result['programming_state_unknown']=True;raise RuntimeError('contradictory successful program receipt without attempt')
        if clock()-started>PROGRAM_BOUND:raise TimeoutError('guarded programming exceeded reserved program budget')
        binding_path=Path(active['session_binding_path']);binding_sha=gn.hw.sha(binding_path)
        binding=gn.capture.load_json(binding_path);build=gn.capture.validate_live_binding(binding,base_dir=binding_path.parent)
        if gn.capture.validate_binding(binding)!=plan['identity']:raise ValueError('new camera/lens identity changed')
        deadline=min(clock()+plan['uart_seconds'],started+plan['total_seconds']-STOP_BOUND-RESTORE_BOUND-HOUSEKEEPING_BOUND)
        if deadline<=clock():raise TimeoutError('no UART budget remains after program/exit reservation')
        link=serial_factory(base['port'])
        result['summary']=run_batch_uart(link,plan,binding,work,build_record=build,source_kind='physical_native_camera',clock=clock,deadline=deadline,cue=cue)
        verify_after(plan,binding_path,binding_sha,binding,build)
        gn.hw._new_json(work/'batch-summary.json',result['summary'])
    except (Exception,KeyboardInterrupt) as exc:result['error']=type(exc).__name__+': '+str(exc)
    finally:
        if link is not None:
            try:link.close()
            except (Exception,KeyboardInterrupt) as exc:result['serial_close_error']=str(exc)
        if entered and result['program'] is None:
            try:result['program']=gn.capture.load_json(Path(base['program_plan']['workdir'])/'receipt.json')
            except (Exception,KeyboardInterrupt):attempted=True;result['programming_state_unknown']=True
        active=result['program']
        if entered and not isinstance(active,dict):
            attempted=True;result['programming_state_unknown']=True
        elif isinstance(active,dict):
            if type(active.get('programming_attempted')) is not bool:result['programming_state_unknown']=True
            attempted|=type(active.get('programming_attempted')) is not bool or bool(active.get('programming_attempted') or active.get('passed') or active.get('done_confirmed'))
            result['hardware_accessed']|=bool(active.get('hardware_accessed'))
        if attempted:
            result['idle_restoration_attempted']=True
            try:
                result['idle_program']=restorer(base['idle_plan'],timeout_seconds=30.)
                result['idle_done_confirmed']=bool(result['idle_program'].get('passed') and result['idle_program'].get('done_confirmed'))
                result['hardware_accessed']|=bool(result['idle_program'].get('hardware_accessed'))
            except (Exception,KeyboardInterrupt) as exc:result['idle_error']=str(exc)
        result['elapsed_total_seconds']=clock()-started
        result['total_budget_seconds']=plan['total_seconds'];result['within_total_budget']=result['elapsed_total_seconds']<=plan['total_seconds']
        result['passed']=bool(isinstance(active,dict) and active.get('passed') and result['summary'] and result['summary']['passed']
            and result['idle_done_confirmed'] and result['within_total_budget'] and not any(k in result for k in ('error','serial_close_error','idle_error')))
        result['limits']='Finite one-program batch only. Host finally is not a hardware watchdog; process/OS/power failure can prevent recovery. Pose labels/identity are declarations; calibration novelty/corners/holdout suitability are not accepted by time intervals or CRC.'
        gn.hw._new_json(work/'batch-result.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--binding');p.add_argument('--build-dir');p.add_argument('--workdir');p.add_argument('--port')
    p.add_argument('--poses',help='explicit list or fixed capture-plan JSON');p.add_argument('--skip-pose-id',action='append',default=[]);p.add_argument('--frame-budget',type=int)
    p.add_argument('--uart-seconds',type=float,default=200);p.add_argument('--total-seconds',type=float,default=600);p.add_argument('--interval-seconds',type=float,default=2)
    p.add_argument('--lease-ms',type=int,default=12000);p.add_argument('--frequency',choices=('1MHz','5MHz','10MHz'),default='5MHz');p.add_argument('--cues',action='store_true');p.add_argument('--execute',action='store_true');p.add_argument('--execute-plan');a=p.parse_args()
    if a.execute_plan:
        if a.execute:p.error('--execute-plan is already the explicit execution boundary')
        result=execute_batch(gn.capture.load_json(a.execute_plan));print(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False));return 0 if result['passed'] else 1
    if any(v is None for v in (a.binding,a.build_dir,a.workdir,a.port,a.poses,a.frame_budget)):p.error('planning requires binding/build-dir/workdir/port/poses/frame-budget')
    poses=load_poses(a.poses,a.skip_pose_id);plan=prepare_batch(a.binding,a.build_dir,a.workdir,poses,port=a.port,frame_budget=a.frame_budget,
        uart_seconds=a.uart_seconds,total_seconds=a.total_seconds,interval_seconds=a.interval_seconds,lease_ms=a.lease_ms,frequency=a.frequency,cues=a.cues)
    result=execute_batch(plan) if a.execute else plan;print(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False));return 0 if not a.execute or result['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
