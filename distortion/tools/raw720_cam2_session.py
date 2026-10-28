"""One fixed720 CAM2 GRANT1, finite45s UART, then fixed heartbeat SRAM; plan by default."""
from pathlib import Path
from datetime import datetime, timezone
import argparse, json, math, re, secrets, struct, time, uuid, zlib
import build_raw720_cam2 as build
import guarded_protocol as gp
import native_camera_capture as capture
import program_native_raw as hw
import program_idle_heartbeat as idle
from frame_protocol import Frame

ROOT=build.ROOT;APPROVED=build.APPROVED;TARGET=build.TARGET;BUILD_TAG=build.BUILD_TAG
MODE='conditional-720p15-rgb565-cam2-guarded'
HELPERS=('tools/raw720_cam2_session.py','tools/build_raw720_cam2.py','tools/run_raw720_cam2_sim.py',
    'tools/program_native_raw.py','tools/program_idle_heartbeat.py','tools/native_camera_capture.py',
    'tools/camera_eye_pin_audit.py','tools/frame_protocol.py','tools/guarded_protocol.py','tools/finalize_raw720_cam2.py')
sha=build.sha;load=build.load;write_new=build.write_new

def helper_hashes():return {n:sha(ROOT/n) for n in HELPERS}
def decode_status(packet):
    if len(packet)!=128 or packet[:8]!=b'PGSTAT02' or packet[124:]!=b'ST02' or struct.unpack_from('<HHI',packet,8)!=(128,2,BUILD_TAG) or zlib.crc32(packet[:120])!=struct.unpack_from('<I',packet,120)[0]:raise ValueError('fixed720 status tag/CRC/schema differs')
    out={name:struct.unpack_from('<'+fmt,packet,offset)[0] for name,offset,fmt in gp.STATUS_FIELDS}
    out['flags']={name:bool(out['flag_bits']&(1<<bit)) for bit,name in enumerate(gp.FLAG_NAMES)}
    return out

class Stream:
    """Strict packet-boundary parser. Only initial partial status may be discarded."""
    def __init__(self):self.buffer=bytearray();self.started=False;self.initial_discarded=0
    def feed(self,data):
        self.buffer.extend(data);events=[]
        while len(self.buffer)>=8:
            magic=bytes(self.buffer[:8])
            if magic not in (b'PGSTAT02',b'PGFRAME1'):
                if self.started or self.initial_discarded>=127:raise ValueError('720 mixed packet boundary lost')
                del self.buffer[0];self.initial_discarded+=1;continue
            self.started=True
            if magic==b'PGSTAT02':
                if len(self.buffer)<128:break
                packet=bytes(self.buffer[:128]);events.append(('status',decode_status(packet)));del self.buffer[:128]
            else:
                if len(self.buffer)<32:break
                _,w,h,ident,count,crc,fmt,hcrc=struct.unpack_from('<8sHHIIIII',self.buffer)
                if (w,h,count,fmt)!=(1280,720,1843200,0x5651) or zlib.crc32(self.buffer[:28])!=hcrc:raise ValueError('fixed720 raw header/size/CRC differs')
                total=1843244
                if len(self.buffer)<total:break
                payload=bytes(self.buffer[32:32+count]);tail=bytes(self.buffer[32+count:total])
                if tail[:8]!=b'PGEND001' or zlib.crc32(payload)!=crc or struct.unpack_from('<I',tail,8)[0]!=crc:raise ValueError('720 payload/source/tail CRC differs')
                events.append(('frame',Frame(w,h,ident,crc,payload)));del self.buffer[:total]
        if len(self.buffer)>1843244:raise ValueError('unbounded720 packet')
        return events

def healthy(s):
    f=s['flags'];code=s['temperature_code']
    return (all(f[k] for k in ('camera_ready','ddr_ready','warmup_ready','safety_ok','temp_valid')) and
        not any(f[k] for k in ('raw_failed','requires_reset','temp_failed','temp_over_temp','temp_stale','camera_failed')) and
        all(s[k]==0 for k in ('camera_error','raw_fault','adc_fault','adc_alarm','rx_errors','duplicate_commands','rejected_commands')) and
        s['sensor_id']==0x5640 and s['temperature_raw']>>4==code and 1913<=code<=2732 and
        s['temperature_age_27mhz']<54000000 and s['safety_snapshot_age_core']<125000000 and
        2<=s['temperature_samples']<=s['temperature_conversions']-2)
def is_idle(s):return s['flags']['core_idle'] and not any(s['flags'][k] for k in ('armed','inflight','bank_locked','draining','raw_failed','requires_reset'))
def _approved(path):
    path=Path(path).resolve()
    if not path.is_relative_to(APPROVED.resolve()):raise ValueError('approved scratch output required')
    return path
def _tcl(plan,provider,*,fresh=True):
    work=_approved(plan['workdir'])
    if not work.is_dir() or (fresh and (work/'receipt.json').exists()):raise ValueError('fresh owned programming operation required')
    for stage,text in provider(plan['validation'],plan['frequency']).items():
        record=plan['tcl'][stage];p=Path(record['path']).resolve()
        if p!=work/(stage+'.tcl') or p.read_text(encoding='utf-8')!=text or sha(p)!=record['sha256']:raise ValueError('fixed SRAM Tcl changed')
    hw.resolve_pds_bin(plan['pds_bin'])

def _derive_binding(review_path,manifest,build_dir):
    review=load(review_path);capture.validate_binding(review)
    if review['eye']!='CAM2' or any(review.get('connection_review',{}).get(k) is not True for k in capture.CONNECTION_FIELDS[:-1]):raise ValueError('explicit CAM2 pin/power/connector reviews required')
    binding={k:review[k] for k in ('camera_id','lens_id','eye')}
    binding.update(schema=1,profile_id='cam2-720p15-uncalibrated',capture_mode_id=MODE,image_size=[1280,720],pixel_format='RGB565_LE',
        connection_review={**{k:True for k in capture.CONNECTION_FIELDS[:-1]},'programmed_bound_bitstream':False},
        input_mode_contract=build.MODE_CONTRACT,calibration_accepted=False,intrinsics=None,distortion=None,
        review_source={'path':str(Path(review_path).resolve()),'sha256':sha(review_path)},
        notes='Reuse reviewed camera/lens/connector declarations only. New720 mode has no accepted K/D, actual FPS or PLL-lock measurement; VGA profile is not inherited.')
    binding['build_binding']={name:{'path':str(path),'sha256':sha(path)} for name,path in {
        'validated_build':Path(build_dir).resolve()/'validated-build.json','bitstream':manifest['Bitstream'],
        'pinout':ROOT/f'board/{TARGET}-pins.json','timing_report':manifest['TimingReport']}.items()}
    return binding

def _validated_build(build_dir):
    """A standard manifest alone cannot publish an unfinished post-finalize."""
    import finalize_raw720_cam2 as post
    work=Path(build_dir).resolve();manifest=build.validate_target(work)
    proof=manifest.get('PostValidationProof')
    if not isinstance(proof,dict):raise ValueError('complete720 post-validation proof/receipt required')
    receipt_path=work/'post-validation-receipt.json';plan_path=Path(proof.get('ValidationPlan','')).resolve()
    if proof.get('ReceiptPath')!=str(receipt_path) or plan_path.parent!=work or not re.fullmatch(r'post-validation-plan(?:-[a-zA-Z0-9_-]+)?\.json',plan_path.name):raise ValueError('post-validation paths differ')
    checked=post.inspect_build(work);sealed=load(plan_path);receipt=load(receipt_path)
    if not build.same(sealed,checked):raise ValueError('post-validation plan/source/log evidence changed')
    standard={k:v for k,v in manifest.items() if k!='PostValidationProof'}
    if not build.same(standard,checked['ProposedManifest']):raise ValueError('post-validation standard manifest differs')
    tool_sha=sha(ROOT/'tools/finalize_raw720_cam2.py');plan_sha=sha(plan_path)
    wanted_proof={'Policy':post.POLICY,'ValidationStage':'post_build_final_saved_db','PreBitGateExecutionProven':False,
        'OriginalBuildResultPassed':False,'OriginalBuildResultSHA256':checked['OriginalFileSHA256']['build-result.json'],
        'ValidationPlan':str(plan_path),'ValidationPlanSHA256':plan_sha,'PostValidatorSHA256':tool_sha,'ReceiptPath':str(receipt_path)}
    if not build.same(proof,wanted_proof) or not isinstance(receipt,dict):raise ValueError('complete post-validation proof differs')
    required={'Passed':True,'Target':TARGET,'HardwareAccessed':False,'PDSAccessed':False,
        'ValidationStage':'post_build_final_saved_db','PreBitGateExecutionProven':False,
        'OriginalBuildResultPassed':False,'OriginalBuildResultPreserved':True,
        'OriginalFileSHA256':checked['OriginalFileSHA256'],'ValidationPlan':str(plan_path),'ValidationPlanSHA256':plan_sha,
        'ValidatedBuild':str(work/'validated-build.json'),'ValidatedBuildSHA256':sha(work/'validated-build.json'),
        'PostValidatorSHA256':tool_sha,'FrozenBuilderValidateTargetCalled':True}
    if any(not build.same(receipt.get(k),v) for k,v in required.items()):raise ValueError('complete post-validation receipt/manifest/hash differs')
    return manifest

def prepare_plan(review_binding,build_dir,workdir,*,port,seconds=45.,frequency='1MHz',pds_bin=None):
    if not isinstance(port,str) or not re.fullmatch(r'COM[1-9][0-9]*',port):raise ValueError('explicit COM port required')
    if type(seconds) not in (int,float) or not math.isfinite(seconds) or not 35<=seconds<=45 or frequency not in ('1MHz','5MHz'):raise ValueError('finite35..45s single-frame UART and1/5MHz SRAM only')
    base=_approved(workdir)
    if not base.is_dir():raise ValueError('existing approved scratch required')
    manifest=_validated_build(build_dir);binding=_derive_binding(review_binding,manifest,build_dir)
    idle.validate_heartbeat();pds=hw.resolve_pds_bin(pds_bin)
    work=base/('raw720-cam2-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:8]);work.mkdir()
    binding_path=work/'preprogram-binding.json';write_new(binding_path,binding)
    capture.validate_live_binding(binding,base_dir=work,require_programmed=False)
    prog=work/'program';prog.mkdir()
    program={'target':TARGET,'operation':'volatile_sram_only','workdir':str(prog),'pds_bin':str(pds),'frequency':frequency,
        'validation':{'bitstream_path':manifest['Bitstream']},'tcl':{}}
    for stage,text in hw._scripts(program['validation'],frequency).items():
        path=prog/(stage+'.tcl');path.write_text(text,encoding='utf-8');program['tcl'][stage]={'path':str(path),'sha256':sha(path)}
    write_new(prog/'plan.json',program)
    exit_plan=idle.prepare_plan(work,frequency=frequency,pds_bin=pds)
    plan={'schema':1,'operation':'single_native720_then_fixed_heartbeat','target':TARGET,'build_tag':BUILD_TAG,
        'hardware_accessed':False,'executed':False,'requires_explicit_execute_flag':True,'workdir':str(work),'port':port,'seconds':seconds,
        'baud':921600,'frames':1,'lease_ms':24000,'frequency':frequency,'host_session':secrets.randbelow(0xffffffff)+1,
        'build_dir':str(Path(build_dir).resolve()),'manifest_sha256':sha(Path(build_dir)/'validated-build.json'),
        'binding_path':str(binding_path),'binding_sha256':sha(binding_path),'helpers':helper_hashes(),'program_plan':program,'idle_plan':exit_plan,
        'limits':'Plan only; one complete720 frame. Nominal15fps register model is not measured FPS or optical calibration. UART<=45s; program scan/client<=90s each and bounded owned cleanup; fixed-heartbeat client<=60s each. COM closes before recovery. No Flash/other target/automatic retry.'}
    _tcl(program,hw._scripts);_tcl(exit_plan,idle._scripts);write_new(work/'plan.json',plan)
    return plan

def verify_plan(plan,*,fresh=True):
    work=_approved(plan['workdir'])
    if load(work/'plan.json')!=plan or plan.get('target')!=TARGET or plan.get('operation')!='single_native720_then_fixed_heartbeat' or plan.get('build_tag')!=BUILD_TAG or plan.get('frames')!=1 or plan.get('lease_ms')!=24000 or plan.get('baud')!=921600:raise ValueError('sealed fixed720 plan differs')
    if type(plan.get('seconds')) not in (int,float) or not 35<=plan['seconds']<=45 or not re.fullmatch(r'COM[1-9][0-9]*',plan.get('port','')) or plan.get('frequency') not in ('1MHz','5MHz') or type(plan.get('host_session')) is not int or not 0<plan['host_session']<=0xffffffff:raise ValueError('bounded720 parameters differ')
    if plan.get('helpers')!=helper_hashes() or sha(Path(plan['build_dir'])/'validated-build.json')!=plan['manifest_sha256']:raise ValueError('720 helper/manifest changed')
    manifest=_validated_build(plan['build_dir']);bp=Path(plan['binding_path']).resolve()
    if bp!=work/'preprogram-binding.json' or sha(bp)!=plan['binding_sha256']:raise ValueError('720 identity binding changed')
    binding=load(bp);review=binding['review_source']
    if sha(review['path'])!=review['sha256'] or binding!=_derive_binding(review['path'],manifest,plan['build_dir']):raise ValueError('review or separate720 mode identity changed')
    record=capture.validate_live_binding(binding,base_dir=work,require_programmed=False)
    p=plan['program_plan'];e=plan['idle_plan']
    if p.get('target')!=TARGET or p.get('operation')!='volatile_sram_only' or Path(p['workdir']).resolve()!=work/'program' or p.get('frequency')!=plan['frequency'] or p.get('validation')!={'bitstream_path':manifest['Bitstream']} or load(Path(p['workdir'])/'plan.json')!=p:raise ValueError('nested raw720 program operation differs')
    if e.get('target')!='heartbeat' or e.get('operation')!='volatile_sram_only' or e.get('frequency')!=plan['frequency'] or e.get('pds_bin')!=p.get('pds_bin') or e.get('validation')!=idle.validate_heartbeat() or Path(e['workdir']).resolve().parent!=work or load(Path(e['workdir'])/'plan.json')!=e:raise ValueError('fixed recovery plan differs')
    _tcl(p,hw._scripts,fresh=fresh)
    _tcl(e,idle._scripts)
    return manifest,binding,record

def execute_program(plan):
    verify_plan(plan);p=plan['program_plan'];work=Path(p['workdir']);owned=[]
    result={'target':TARGET,'operation':'volatile_sram_only','hardware_accessed':False,'programming_attempted':False,'done_confirmed':False,'passed':False,'workdir':str(work)}
    try:
        if hw.listening_pids(hw.PORT):raise RuntimeError('foreign JTAG listener occupied; no attachment/termination')
        pds=hw.resolve_pds_bin(p['pds_bin']);server=hw._start_owned([str(pds/'cdt_js.exe'),'-port',str(hw.PORT),'-work_dir',str(work)],work,owned,'server');result['hardware_accessed']=True
        hw._await_owned_server(server);hw._owned_server_check(server);hw._check_scan(hw._client(p,'scan',owned,90.))
        verify_plan(plan);prior=server;server=hw._program_server_after_scan(server,p,owned);result['server_restarted_after_scan']=server is not prior
        result['programming_attempted']=True;hw._check_program(hw._client(p,'program',owned,90.));verify_plan(plan)
        result.update(passed=True,done_confirmed=True,bitstream_sha256=sha(p['validation']['bitstream_path']))
    except (Exception,KeyboardInterrupt) as exc:result['error']=type(exc).__name__+': '+str(exc)
    finally:
        result['owned_pids']=[q.pid for q in owned];result['terminated_owned_pids'],result['cleanup_errors']=hw._stop_owned(owned)
        if result['cleanup_errors']:result['passed']=False
        result['logs']={str(p):sha(p) for p in work.glob('*.log')};result['checked_at_utc']=datetime.now(timezone.utc).isoformat();write_new(work/'receipt.json',result)
    return result

def _confirm_receipt(result,operation,target,bit_sha):
    path=Path(operation['workdir'])/'receipt.json'
    if (not isinstance(result,dict) or result.get('target')!=target or result.get('operation')!='volatile_sram_only'
        or result.get('workdir')!=operation['workdir'] or result.get('passed') is not True
        or result.get('done_confirmed') is not True or result.get('programming_attempted') is not True
        or str(result.get('bitstream_sha256','')).lower()!=bit_sha.lower() or load(path)!=result):
        raise RuntimeError('fresh named SRAM receipt/DONE/bit hash differs')
    return {'path':str(path),'sha256':sha(path)}

def run_uart(io,plan,binding,record,*,clock=time.monotonic):
    start=clock();deadline=start+plan['seconds'];parser=Stream();state='boot';last=None;healthy_start=None;expected_seq=0;expected_opcode=0;before_count=0;saved=[];statuses=[];tx=[];last_write=b''
    work=Path(plan['workdir']);session=plan['host_session']
    def send(op,seq,arg=0):
        nonlocal expected_seq,expected_opcode,before_count,last_write
        last_write=gp.encode_command(op,seq,session,arg)
        if io.write(last_write)!=16:raise RuntimeError('partial720 command write')
        tx.append({'seq':seq,'opcode':int(op),'hex':last_write.hex(),'elapsed':clock()-start});expected_seq=seq;expected_opcode=int(op);before_count=last['accepted_commands']
    with (work/'uart-wire.bin').open('xb') as wire,(work/'status.jsonl').open('x',encoding='utf-8') as rows:
        while clock()<deadline and state!='done':
            chunk=io.read(65536)
            if not chunk:continue
            wire.write(chunk);wire.flush()
            for kind,value in parser.feed(chunk):
                if kind=='frame':
                    if state!='frame' or saved or value.frame_id!=1:raise RuntimeError('unexpected/duplicate720 raw or missing grant ACK')
                    item=capture.save_frame(value,binding,work,f'raw720-{session}',source_kind='physical_native_camera',build_record=record)
                    metadata=Path(item['metadata_path'])
                    if metadata.parent!=work or sha(metadata)!=item['metadata_sha256']:raise ValueError('fresh720 metadata changed')
                    item.update(input_mode_contract=build.MODE_CONTRACT,capture_mode=MODE,calibration_accepted=False,measured_input_fps=None)
                    item.pop('metadata_sha256');item.pop('metadata_path')
                    metadata.write_text(json.dumps(item,indent=2)+'\n',encoding='utf-8')
                    saved.append({**item,'metadata_path':str(metadata),'metadata_sha256':sha(metadata)});state='completion';continue
                s=value;stamp=clock()-start
                if last and (s['snapshot_seq']<=last['snapshot_seq'] or any(s[k]<last[k] for k in ('uptime_ms','accepted_commands','completed_frames','admitted_frames'))):raise RuntimeError('720 status counter/snapshot reset')
                if any(s[k] for k in ('camera_error','raw_fault','adc_fault','adc_alarm','rejected_commands','duplicate_commands','rx_errors')):raise RuntimeError('720 camera/core/ADC/command fault')
                if s['session_id'] not in (0,session):raise RuntimeError('foreign720 command session')
                if s['flags']['raw_failed'] or s['flags']['requires_reset']:raise RuntimeError('720 core ownership fault')
                statuses.append({'elapsed':stamp,'fields':s});rows.write(json.dumps(statuses[-1])+'\n');rows.flush();last=s
                if state=='boot':
                    if healthy(s) and is_idle(s) and s['accepted_commands']==s['completed_frames']==s['held_frame_id']==0 and s['last_received_seq']==s['last_accepted_seq']==s['last_opcode']==s['session_id']==0:
                        if healthy_start is None:healthy_start=stamp
                        elif stamp-healthy_start>=.5:send(gp.Opcode.OPEN,1);state='open'
                    else:healthy_start=None
                    continue
                # A queued boot snapshot may arrive before OPEN is accepted.
                # It must never serve as the matching OPEN ACK; after that ACK
                # every control/completion snapshot belongs to this session.
                if s['session_id']!=session and not (state=='open' and s['last_received_seq']!=expected_seq):raise RuntimeError('720 ACK/completion session differs')
                if not healthy(s):raise RuntimeError('720 ready/ADC state lost outside pixel packet')
                if state in ('frame','completion') and (s['last_received_seq'],s['last_accepted_seq'],s['last_opcode'],s['last_result'],s['accepted_commands'])!=(3,3,16,1,3):raise RuntimeError('accepted command changed during one720 grant')
                if state in ('open','query','grant','stop'):
                    if s['last_received_seq']!=expected_seq:continue
                    if (s['last_accepted_seq'],s['last_opcode'],s['last_result'],s['accepted_commands'])!=(expected_seq,expected_opcode,1,before_count+1):raise RuntimeError('720 actual command ACK/counters differ')
                    if state=='open':send(gp.Opcode.QUERY,2);state='query'
                    elif state=='query':
                        if not is_idle(s) or s['completed_frames'] or s['held_frame_id']:raise RuntimeError('nonfresh720 baseline')
                        send(gp.Opcode.GRANT,3,gp.grant_argument(1,24000));state='grant'
                    elif state=='grant':state='frame'
                    else:
                        if not is_idle(s):raise RuntimeError('STOP acknowledged with ownership active')
                        state='done'
                elif state=='completion':
                    if not is_idle(s):continue
                    frame=saved[0]
                    if (s['admitted_frames'],s['completed_frames'],s['held_frame_id'],s['written_beats'],s['source_crc32'],s['remaining_frames'],s['stop_reason'])!=(1,1,1,57600,int(frame['source_crc32'],16),0,1):raise RuntimeError('720 final DDR/CRC/frame-budget/global completion differs')
                    send(gp.Opcode.STOP,4);state='stop'
    write_new(work/'tx.json',tx)
    if state!='done' or len(saved)!=1 or parser.buffer:raise TimeoutError('complete720 frame/STOP-idle not reached within bounded UART window')
    return {'passed':True,'frames':saved,'status_count':len(statuses),'tx':tx,'final_status':last,'uart_seconds':clock()-start,'wire_sha256':sha(work/'uart-wire.bin'),'initial_discarded_bytes':parser.initial_discarded,
        'limits':'One CRC-protected full native720 frame; not measured15fps, optical/calibration, stereo, display or long-run safety evidence.'}

def _serial(port):
    import serial
    link=serial.Serial(port=None,baudrate=921600,timeout=.05,write_timeout=1,dsrdtr=False,rtscts=False)
    try:
        link.dtr=False;link.rts=False;link.port=port;link.open();link.reset_input_buffer();return link
    except BaseException:
        # execute_plan cannot yet own this object if open/reset raises.
        try:link.close()
        except BaseException:pass
        raise

def execute_plan(plan):
    manifest,binding,record=verify_plan(plan);work=Path(plan['workdir'])
    if (work/'result.json').exists():raise ValueError('fresh once-only720 execution required')
    result={'target':TARGET,'passed':False,'executed':True,'hardware_accessed':False,'programming_state_unknown':False,'com_closed':False};attempted=False;link=None
    try:
        result['program']=execute_program(plan);attempted=result['program'].get('programming_attempted') is True;result['hardware_accessed']=result['program'].get('hardware_accessed') is True
        if not result['program'].get('passed') or not result['program'].get('done_confirmed'):raise RuntimeError('fixed720 SRAM program/freshDONE failed')
        result['program_receipt']=_confirm_receipt(result['program'],plan['program_plan'],TARGET,sha(manifest['Bitstream']))
        verify_plan(plan,fresh=False);binding=dict(binding);binding['connection_review']={**binding['connection_review'],'programmed_bound_bitstream':True}
        binding['programming_receipt']={'path':str(work/'program/receipt.json'),'sha256':sha(work/'program/receipt.json')};write_new(work/'session-binding.json',binding)
        record=capture.validate_live_binding(binding,base_dir=work,require_programmed=True)
        link=_serial(plan['port']);result['hardware_accessed']=True;result['capture']=run_uart(link,plan,binding,record)
        verify_plan(plan,fresh=False);result['passed']=result['capture']['passed']
    except (Exception,KeyboardInterrupt) as exc:
        result['error']=type(exc).__name__+': '+str(exc)
        try:
            receipt=load(work/'program/receipt.json')
            if not isinstance(receipt,dict) or type(receipt.get('programming_attempted')) is not bool:raise ValueError('unknown receipt')
            attempted|=receipt['programming_attempted']
        except (Exception,KeyboardInterrupt):attempted=True;result['programming_state_unknown']=True
    finally:
        if link is not None:
            try:
                if not result['passed']:link.write(gp.encode_stop(0x7fff,plan['host_session']))
            except (Exception,KeyboardInterrupt) as exc:result['stop_attempt_error']=str(exc)
            finally:
                try:link.close();result['com_closed']=True
                except (Exception,KeyboardInterrupt) as exc:result['close_error']=str(exc);result['passed']=False
        if attempted:
            try:
                _tcl(plan['idle_plan'],idle._scripts);result['idle_program']=idle.execute_plan(plan['idle_plan'],timeout_seconds=60.)
                if not result['idle_program'].get('passed') or not result['idle_program'].get('done_confirmed'):result['passed']=False
                else:result['idle_receipt']=_confirm_receipt(result['idle_program'],plan['idle_plan'],'heartbeat',idle.GOLDEN_BIT_SHA256)
            except (Exception,KeyboardInterrupt) as exc:result['idle_error']=type(exc).__name__+': '+str(exc);result['passed']=False
        result['ended_at_utc']=datetime.now(timezone.utc).isoformat();write_new(work/'result.json',result)
    return result

def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--identity-binding',required=True);a.add_argument('--build-dir',required=True);a.add_argument('--workdir',required=True);a.add_argument('--port',required=True);a.add_argument('--frequency',choices=('1MHz','5MHz'),default='1MHz');a.add_argument('--seconds',type=float,default=45.);a.add_argument('--pds-bin');a.add_argument('--execute',action='store_true');args=a.parse_args()
    plan=prepare_plan(args.identity_binding,args.build_dir,args.workdir,port=args.port,seconds=args.seconds,frequency=args.frequency,pds_bin=args.pds_bin)
    result=execute_plan(plan) if args.execute else plan;print(json.dumps(result,indent=2));return 0 if not args.execute or result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
