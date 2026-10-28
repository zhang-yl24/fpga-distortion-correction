"""Finite, fixed Gamma/parity SRAM session. Default plan only; no optical acceptance."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import binascii
import json
import math
import re
import struct
import time
import uuid

import program_native_raw as hw
import program_idle_heartbeat as idle
import build_gamma_pipeline_d5 as builder

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'corrected_gamma_pipeline_d5'
BAUD = 115200  # Both inherited TX/RX instances use this verified RTL default.
FIELD_WIDTHS = [('CAM',4),('E',2),('I',1),('H',1),('D',1),('V',1),('WF',8),('CF',8),('PF',8),
    ('UF',8),('MF',8),('OW',8),('X',2),('CS',8),('RC',8),('RS',8),('PS',8),('CY',8),
    ('HT',8),('MS',8),('RA',8),('AU',1),('TV',1),('TR',4),('TF',2),('TA',8),('AL',2),
    ('OC',8),('CC',8),('BW',8),('SP',8),('HV',2),('HQ',4),('HR',8),('HC',8),('HX',8),
    ('HD',8),('HE',8),('GM',1),('GF',8)]
LINE_PATTERN = re.compile(' '.join(k+'=([0-9A-F]{'+str(n)+'})' for k,n in FIELD_WIDTHS))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def helpers():
    names = ['gamma_pipeline_session.py', 'program_native_raw.py', 'program_idle_heartbeat.py',
        'build_gamma_pipeline_d5.py', 'prepare_gamma_pipeline_d5.py', 'native_camera_capture.py',
        'camera_eye_pin_audit.py', 'frame_protocol.py', 'pds_gate_log_audit.py']
    return {'tools/'+n: hw.sha(ROOT/'tools'/n) for n in names}


def limits(port, seconds, frequency, angles):
    if not isinstance(port,str) or not re.fullmatch(r'COM[1-9][0-9]*',port):
        raise ValueError('explicit Windows COM port required')
    if type(seconds) not in (int,float) or not math.isfinite(seconds) or not 12 <= seconds <= 30:
        raise ValueError('UART duration must be finite12..30seconds including final auto-off attempt')
    if frequency not in ('1MHz','5MHz'):
        raise ValueError('only1MHz/5MHz JTAG is allowed')
    if type(angles) not in (list,tuple) or not 1 <= len(angles) <= 3:
        raise ValueError('one to three explicit bounded phase tests required')
    for angle in angles:
        if type(angle) not in (int,float) or not math.isfinite(angle) or not -360 <= angle <= 360:
            raise ValueError('angle must be finite within -360..360degrees')
    if len({phase(a) for a in angles}) != len(angles):
        raise ValueError('phase requests must be distinct modulo one turn')


def phase(angle):
    return round((angle % 360)*(1 << 32)/360) & 0xffffffff


def command(opcode, sequence, argument):
    if opcode not in (1,2) or not 1 <= sequence <= 0xffff or not 0 <= argument <= 0xffffffff:
        raise ValueError('fixed version1 rotation/auto command only')
    if opcode == 2 and argument not in (0,1):
        raise ValueError('auto flag must be zero or one')
    body = struct.pack('<BBHI',1,opcode,sequence,argument)
    return b'\xa5\x5a'+body+struct.pack('<H',binascii.crc_hqx(body,0xffff))


def validate_native_build_result(work, manifest, manifest_path):
    role = manifest.get('PDSLogAudit', {}).get('CADScriptRole')
    names = {builder.gate_log.CANONICAL_MAIN: 'gamma-pipeline-build-result.json',
             builder.gate_log.RESEEDED_MAIN: 'reseed-result.json'}
    if role not in names:
        raise ValueError('explicit main CAD script role required')
    path = work/names[role]
    result = hw.load_json(path)
    if (not isinstance(result, dict) or result.get('Target') != TARGET or result.get('Passed') is not True
            or result.get('HardwareAccessed') is not False or result.get('TimedOut') is not False
            or type(result.get('ProcessExitCode')) is not int or result['ProcessExitCode'] != 0
            or result.get('CleanupError') or result.get('SourceDrift') or result.get('InputOrSourceDrift')
            or Path(result.get('OutputDirectory', '')).resolve() != work
            or result.get('SourceSHA256') != manifest.get('SourceSHA256')
            or result.get('SourceSHA256After') != manifest.get('SourceSHA256After')
            or Path(result.get('ValidatedBuild', '')).resolve() != manifest_path
            or str(result.get('ValidatedBuildSHA256', '')).lower() != hw.sha(manifest_path).lower()):
        raise ValueError('sealed native0/current-source/build-result proof differs')
    return {'path': str(path), 'sha256': hw.sha(path)}


def validate_target(build_dir, profile_binding=None):
    work = Path(build_dir).resolve()
    if not work.is_dir() or not work.is_relative_to(hw.APPROVED.resolve()):
        raise ValueError('existing Gamma build inside approved scratch required')
    manifest_path = work/'validated-build.json'; m = hw.load_json(manifest_path)
    expected = {'Target':TARGET,'Device':'PG2L100H','Package':'FBG676','SCBV':'High Voltage','UnusedIO':'UNUSED'}
    if any(m.get(k) != v for k,v in expected.items()) or type(m.get('ProcessExitCode')) is not int or m['ProcessExitCode'] != 0:
        raise ValueError('fixed Gamma/parity target and successful native build required')
    if m.get('HardwareAccessed') is not False or m.get('NewLensCorrectionVerified') is not False:
        raise ValueError('offline artifact must retain explicit unverified new-lens status')
    if bool(m.get('ProfileBinding')) != bool(profile_binding):
        raise ValueError('a profile-bound build needs its explicit original profile binding')
    before = builder.verify_prepared(profile_binding)
    names = hw.load_json(ROOT/f'board/{TARGET}-sources.json')
    if (type(names) is not list or len(names) != 123 or len(set(names)) != 123
            or set(names) != set(before['SourceSHA256']) or m.get('SourceSHA256') != before['SourceSHA256']
            or m.get('SourceSHA256After') != before['SourceSHA256']):
        raise ValueError('current/final exact123 source closure differs')
    for name,digest in before['SourceSHA256'].items():
        path = (ROOT/name).resolve()
        if not path.is_relative_to(ROOT) or hw.sha(path).lower() != digest.lower():
            raise ValueError('source escaped/missing/changed: '+name)
    sim = builder.validate_simulation(m['SimulationEvidence']['Path'],profile_binding)
    role = m.get('PDSLogAudit', {}).get('CADScriptRole')
    actual = builder.validate_artifacts(work,before,sim,profile_binding,role)
    if canonical(actual) != canonical(m):
        raise ValueError('final build/bit/pins/timing/simulation/builder proof changed')
    native_result = validate_native_build_result(work, m, manifest_path)
    pins = builder.validate_pins(work/'place_route'/f'{TARGET}_prr.prt')
    if len(pins) != 130 or pins['cam_data[5]'] != 'AA23' or pins['uart_rxd'] != 'B24':
        raise ValueError('130routed pins/AA23/B24 required')
    if Path(m['Bitstream']).resolve() != work/'generate_bitstream'/f'{TARGET}.sbit':
        raise ValueError('only named candidate SRAM artifact permitted')
    # Pin the UART capability actually present in this candidate, never infer
    # it from the unrelated newer guarded raw host/protocol.
    top = (ROOT/f'board/{TARGET}.v').read_text()
    if (top.count('uart_tx uart(') != 1 or top.count('uart_rx_control host_receiver(') != 1
            or 'parameter BAUD=115200' not in (ROOT/'rtl/uart_tx.v').read_text()
            or 'BAUD=115200' not in (ROOT/'rtl/experimental/uart_rx_control.v').read_text()):
        raise ValueError('reviewed UART115200 instance/default changed')
    return {'target':TARGET,'build_dir':str(work),'manifest_path':str(manifest_path),
        'manifest_sha256':hw.sha(manifest_path),'bitstream_path':m['Bitstream'],
        'bitstream_sha256':m['SHA256'].lower(),'source_sha256':before['SourceSHA256'],
        'simulation':sim,'profile_binding_path':str(Path(profile_binding).resolve()) if profile_binding else None,
        'profile_binding_sha256':hw.sha(profile_binding) if profile_binding else None,
            'pin_count':130,'baud':BAUD,'helper_source_sha256':helpers(),'native_build_result':native_result,
        'parameter_scope':m['IntegrationContract']['calibration_scope'],
        'new_lens_optical_pass':False,'mask_crc_available':False,'gamma_mode_host_selectable':False}


def session_budget(program, recovery, seconds, outer_wait_seconds=None):
    candidate = idle.validate_program_budget(program)
    restore = idle.validate_program_budget(recovery)
    minimum = (candidate['operation_wait_bound_seconds']+seconds
               +restore['operation_wait_bound_seconds']+30.)
    if outer_wait_seconds is None:
        outer_wait_seconds = max(600.,minimum)
    if (type(outer_wait_seconds) not in (int,float) or not math.isfinite(outer_wait_seconds)
            or not minimum <= outer_wait_seconds <= 900.):
        raise ValueError(f'outer wait budget must be finite in [{minimum},900] seconds')
    return {'uart_observation_seconds':seconds,
        'candidate_client_seconds':candidate['client_timeout_seconds'],
        'candidate_operation_wait_bound_seconds':candidate['operation_wait_bound_seconds'],
        'recovery_client_seconds':restore['client_timeout_seconds'],
        'recovery_operation_wait_bound_seconds':restore['operation_wait_bound_seconds'],
        'host_checks_close_write_allowance_seconds':30.,
        'minimum_outer_wait_seconds':minimum,'outer_wait_seconds':outer_wait_seconds}


def validate_session_budget(plan):
    bound = plan.get('time_budget')
    if not isinstance(bound,dict) or 'outer_wait_seconds' not in bound:
        raise ValueError('explicit sealed session budgets required; no legacy-plan migration')
    if bound != session_budget(plan['program_plan'],plan['idle_plan'],plan['seconds'],bound['outer_wait_seconds']):
        raise ValueError('sealed session budgets differ from candidate/UART/recovery budgets')
    return bound


def prepare_plan(build_dir, workdir, *, port, seconds=30., frequency='5MHz',
                 angles=(0,13.25,181.125), profile_binding=None, pds_bin=None,
                 candidate_timeout_seconds=idle.DEFAULT_CLIENT_TIMEOUT,
                 recovery_timeout_seconds=idle.DEFAULT_CLIENT_TIMEOUT, outer_wait_seconds=None):
    limits(port,seconds,frequency,angles)
    base = Path(workdir).resolve()
    if not base.is_dir() or not base.is_relative_to(hw.APPROVED.resolve()):
        raise ValueError('existing approved work directory required')
    valid = validate_target(build_dir,profile_binding); heartbeat = idle.validate_heartbeat()
    candidate_budget = idle.program_budget(valid,frequency,candidate_timeout_seconds)
    recovery_budget = idle.program_budget(heartbeat,frequency,recovery_timeout_seconds)
    budgets = session_budget({'validation':valid,'frequency':frequency,'program_budget':candidate_budget},
        {'validation':heartbeat,'frequency':frequency,'program_budget':recovery_budget},seconds,outer_wait_seconds)
    pds = hw.resolve_pds_bin(pds_bin)
    work = base/('gamma-pipeline-session-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:8])
    work.mkdir(); program = work/'candidate-program'; program.mkdir()
    scripts = hw._scripts(valid,frequency)
    for stage,text in scripts.items():
        with (program/(stage+'.tcl')).open('x',encoding='utf-8') as out:
            out.write(text)
    nested = {'target':TARGET,'operation':'volatile_sram_only','workdir':str(program),'frequency':frequency,
        'pds_bin':str(pds),'validation':valid,'program_budget':candidate_budget,
        'tcl':{s:{'path':str(program/(s+'.tcl')),'sha256':hw.sha(program/(s+'.tcl'))} for s in scripts}}
    plan = {'schema':1,'target':TARGET,'operation':'finite_gamma_pipeline_then_fixed_heartbeat',
        'executed':False,'hardware_accessed':False,'requires_explicit_execute_flag':True,'workdir':str(work),
        'port':port,'baud':BAUD,'seconds':seconds,'angles_deg':list(angles),'frequency':frequency,
        'program_plan':nested,'idle_plan':idle.prepare_plan(work,pds_bin=pds,frequency=frequency,
            timeout_seconds=recovery_timeout_seconds),'time_budget':budgets,
        'source_sha256':helpers(),'limits':'Function/performance test only. Historical or development K/D '
        'never establishes new-lens optical calibration. ASCII telemetry has no packet CRC. GM/GF are '
        'adaptive observations, not host Gamma selection. No mask-only CRC or PGSTOP exists. Auto-off '
        'does not stop video; only finally heartbeat stops this configuration. No host-death watchdog.'}
    hw._new_json(work/'plan.json',plan)
    return plan


def check_program(plan):
    work = Path(plan['workdir']).resolve()
    if (plan.get('target') != TARGET or plan.get('operation') != 'volatile_sram_only'
            or not work.is_dir() or not work.is_relative_to(hw.APPROVED.resolve())):
        raise ValueError('fixed fresh candidate SRAM plan required')
    idle.validate_program_budget(plan)
    valid = plan['validation']
    if validate_target(valid['build_dir'],valid['profile_binding_path']) != valid:
        raise ValueError('candidate build/source binding changed')
    hw.resolve_pds_bin(plan['pds_bin'])
    check_scripts(plan,hw._scripts)


def check_scripts(plan,factory):
    work = Path(plan['workdir']).resolve()
    for stage,text in factory(plan['validation'],plan['frequency']).items():
        p = Path(plan['tcl'][stage]['path']).resolve()
        if p != work/(stage+'.tcl') or p.read_text(encoding='utf-8') != text or hw.sha(p) != plan['tcl'][stage]['sha256']:
            raise ValueError('fixed volatile SRAM Tcl changed')


def execute_program(plan):
    owned = []; work = Path(plan['workdir'])
    result = {'schema':1,'target':TARGET,'operation':'volatile_sram_only','passed':False,
        'hardware_accessed':False,'programming_attempted':False,'done_confirmed':False,'workdir':str(work)}
    try:
        check_program(plan)
        timeout = idle.validate_program_budget(plan)['client_timeout_seconds']
        if hw.listening_pids(hw.PORT):
            raise RuntimeError('JTAG listener occupied; no foreign owner used or stopped')
        pds = Path(plan['pds_bin'])
        server = hw._start_owned([str(pds/'cdt_js.exe'),'-port',str(hw.PORT),'-work_dir',str(work)],work,owned,'server')
        result['hardware_accessed'] = True; hw._await_owned_server(server); hw._owned_server_check(server)
        hw._check_scan(hw._client(plan,'scan',owned,timeout)); check_program(plan)
        previous = server; server = hw._program_server_after_scan(server,plan,owned)
        result['server_restarted_after_scan'] = server is not previous
        result['programming_attempted'] = True
        hw._check_program(hw._client(plan,'program',owned,timeout)); check_program(plan)
        result.update(passed=True,done_confirmed=True,bitstream_sha256=plan['validation']['bitstream_sha256'])
    except (Exception,KeyboardInterrupt) as exc:
        result['error'] = type(exc).__name__+': '+str(exc)
    finally:
        result['owned_pids'] = [p.pid for p in owned]
        result['terminated_owned_pids'],result['cleanup_errors'] = hw._stop_owned(owned)
        result['passed'] &= not result['cleanup_errors']
        result['logs'] = {str(p):hw.sha(p) for p in work.glob('*.log')}
        result['checked_at_utc'] = datetime.now(timezone.utc).isoformat()
        hw._new_json(work/'receipt.json',result)
    return result


def parse_line(line):
    if type(line) is not bytes or len(line) != 385 or not line.endswith(b'\r\n'):
        raise ValueError('complete385byte CRLF telemetry line required')
    match = LINE_PATTERN.fullmatch(line[:-2].decode('ascii'))
    if match is None:
        raise ValueError('telemetry field order/width/value differs')
    values = {key:int(text,16) for (key,_),text in zip(FIELD_WIDTHS,match.groups())}
    if values['HV'] != 1 or any(values[k] not in (0,1) for k in ('I','H','D','V','AU','TV')) or values['GM'] > 2:
        raise ValueError('invalid telemetry control/mode flags')
    return values


def healthy(row):
    code = row['TR'] >> 4
    return (row['CAM'] == 0x5640 and all(row[k] == 1 for k in ('I','D','V','TV'))
        and not any(row[k] for k in ('E','X','UF','MF','OW','TF','HX','HD','HE'))
        and row['AL'] == 0x80 and row['TA'] < 54000000 and 1913 <= code <= 2732
        and row['CY'] > 0)


def run_uart(link,plan,work,*,clock=time.monotonic):
    started = clock(); normal_end = started+plan['seconds']-3; deadline = started+plan['seconds']
    buf = bytearray(); samples = []; commands = []; requested = [phase(a) for a in plan['angles_deg']]
    completed = []; stable = []; pending = None; sequence = 0; last = None; stage = 'boot'; failure = None
    final_auto_ack = False; leading_partial = False; rawpath = Path(work)/'telemetry-wire.bin'
    logpath = Path(work)/'telemetry-samples.jsonl'
    with rawpath.open('xb') as wire, logpath.open('x',encoding='utf-8') as log:
        def send(op,arg,kind):
            nonlocal sequence,pending
            sequence += 1; packet = command(op,sequence,arg)
            c = {'kind':kind,'sequence':sequence,'opcode':op,'argument':arg,'wire_hex':packet.hex(),
                'sent_elapsed_seconds':clock()-started,'before_CF':last['CF'] if last else None,
                'before_HC':last['HC'] if last else None,'control_ACK_verified':False,'result_phase_verified':False}
            commands.append(c); pending = c
            if link.write(packet) != 12:
                raise RuntimeError('incomplete rotation command write')
            link.flush()

        def receive(stopping=False):
            nonlocal buf,last,pending,stage,final_auto_ack,leading_partial,stable
            chunk = link.read(4096)
            if not chunk:
                return
            wire.write(chunk); wire.flush(); buf.extend(chunk)
            if len(buf) > 8192:
                raise RuntimeError('unbounded/unframed UART data')
            while b'\n' in buf:
                end = buf.index(10)+1; line = bytes(buf[:end]); del buf[:end]
                if not samples and not line.startswith(b'CAM=') and not leading_partial:
                    if len(line) >= 385:
                        raise ValueError('invalid initial partial line')
                    leading_partial = True; continue
                row = parse_line(line)
                if last:
                    for key in ('WF','CF','PF','GF','HC','HX','HD','HE'):
                        if row[key] < last[key]:
                            raise RuntimeError('counter reset/regression: '+key)
                # Real telemetry only; PDS status over_temp is never interpreted as temperature.
                faults = {k:row[k] for k in ('E','X','UF','MF','OW','TF','HX','HD','HE') if row[k]}
                if faults or row['AL'] & 0x7f:
                    raise RuntimeError('camera/video/thermal/command fault '+str({**faults,'AL':row['AL']}))
                if row['TV'] and (not row['AL'] & 0x80 or row['TA'] >= 54000000 or not 1913 <= row['TR']>>4 <= 2732):
                    raise RuntimeError('invalid/stale/out-of-bound internal ADC telemetry')
                if stage != 'boot' and not healthy(row):
                    raise RuntimeError('readiness/ADC telemetry lost')
                record = {'ReceivedUtc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':clock()-started,
                    'Line':line.decode('ascii').rstrip(),'fields':row}
                samples.append(record); log.write(json.dumps(record)+'\n'); log.flush()
                previous = last; last = row
                if stopping:
                    if (pending and row['HQ'] == pending['sequence'] and row['HC'] == pending['before_HC']+1
                            and row['AU'] == 0):
                        pending['control_ACK_verified'] = True; final_auto_ack = True
                    continue
                if pending and pending['control_ACK_verified'] and row['HQ'] != pending['sequence']:
                    raise RuntimeError('accepted control sequence changed during the same phase')
                if stage == 'boot':
                    if clock()-started > 8:
                        raise TimeoutError('no sustained healthy camera/DDR/video/ADC telemetry')
                    if previous and healthy(previous) and healthy(row) and row['CF'] > previous['CF']:
                        if row['HC'] or row['HQ']:
                            raise RuntimeError('fresh candidate has previous host command state')
                        send(2,0,'initial_auto_off'); stage = 'auto_ack'
                elif pending and row['HQ'] == pending['sequence']:
                    if row['HC'] != pending['before_HC']+1 or row['AU'] != 0:
                        raise RuntimeError('control ACK counters/automatic mode differ')
                    if pending['opcode'] == 1 and row['HR'] != pending['argument']:
                        raise RuntimeError('requested phase ACK differs')
                    if not pending['control_ACK_verified']:
                        pending.update(control_ACK_verified=True,ack_elapsed_seconds=clock()-started,
                            ack_CF=row['CF'],ack_RA=row['RA'],ack_HQ=row['HQ'],ack_HR=row['HR'])
                    if stage == 'auto_ack':
                        send(1,requested[0],'phase'); stage = 'phase'
                    elif stage == 'phase' and row['RA'] == pending['argument'] and row['CF'] > pending['ack_CF']:
                        pending.update(result_phase_verified=True,result_elapsed_seconds=clock()-started,
                            result_CF=row['CF'],result_RA=row['RA'],
                            result_telemetry={k:row[k] for k in ('WF','CF','PF','CY','HT','MS','RC','PS','GM','GF','OC','CC','BW','SP')})
                        stable = [record]; stage = 'hold'
                    elif stage == 'hold':
                        if row['RA'] != pending['argument']:
                            raise RuntimeError('result phase changed during its measurement window')
                        stable.append(record)
                        span = record['elapsed_seconds']-stable[0]['elapsed_seconds']
                        if span >= 2 and len(stable) >= 3:
                            delta = {k:row[k]-stable[0]['fields'][k] for k in ('WF','CF','PF','GF')}
                            if any(delta[k] <= 0 for k in ('WF','CF','PF')):
                                raise RuntimeError('no input/process/output progress in same-phase window')
                            pending['stable_performance'] = {'healthy_samples':len(stable),'elapsed_seconds':span,
                                'start_elapsed_seconds':stable[0]['elapsed_seconds'],'end_elapsed_seconds':record['elapsed_seconds'],
                                'phase':row['RA'],'delta':delta,
                                'approx_rates_per_host_second':{k:v/span for k,v in delta.items()},
                                'CY_range':[min(s['fields']['CY'] for s in stable),max(s['fields']['CY'] for s in stable)],
                                'HT_range':[min(s['fields']['HT'] for s in stable),max(s['fields']['HT'] for s in stable)],
                                'MS_range':[min(s['fields']['MS'] for s in stable),max(s['fields']['MS'] for s in stable)],
                                'GM_observed':sorted({s['fields']['GM'] for s in stable}),
                                'result_CRC_observed':sorted({f"{s['fields']['RC']:08X}" for s in stable}),
                                'pixel_CRC_observed':sorted({f"{s['fields']['PS']:08X}" for s in stable})}
                            completed.append(dict(pending))
                            if len(completed) == len(requested):
                                stage = 'done'
                            else:
                                send(1,requested[len(completed)],'phase'); stage = 'phase'
        try:
            while clock() < normal_end and stage != 'done':
                receive()
                if pending and stage in ('auto_ack','phase') and clock()-started-pending['sent_elapsed_seconds'] > 6:
                    raise TimeoutError('control/result phase acknowledgement timed out')
                if clock()-started > 3 and (not samples or clock()-started-samples[-1]['elapsed_seconds'] > 2.5):
                    raise TimeoutError('UART telemetry silence')
            if stage != 'done':
                raise TimeoutError('finite UART budget ended before all phase tests')
        except (Exception,KeyboardInterrupt) as exc:
            failure = type(exc).__name__+': '+str(exc)
        finally:
            if last is not None:
                try:
                    send(2,0,'final_auto_off')
                    while clock() < deadline and not final_auto_ack:
                        receive(stopping=True)
                except (Exception,KeyboardInterrupt) as exc:
                    if failure is None:
                        failure = 'final auto-off '+type(exc).__name__+': '+str(exc)
    good = [s for s in samples if healthy(s['fields'])]
    delta = {k:good[-1]['fields'][k]-good[0]['fields'][k] for k in ('WF','CF','PF','GF')} if len(good) > 1 else {}
    passed = (failure is None and len(completed) == len(requested) and final_auto_ack and bool(delta)
        and all(delta[k] > 0 for k in ('WF','CF','PF')) and clock()-started <= plan['seconds']+.1)
    return {'schema':1,'passed':passed,'error':failure,'baud':BAUD,'sample_count':len(samples),
        'healthy_samples':len(good),'delta':delta,
        'counter_delta_span_seconds':good[-1]['elapsed_seconds']-good[0]['elapsed_seconds'] if len(good)>1 else None,
        'completed_phase_tests':completed,'commands':commands,
        'final_auto_off_ACK':final_auto_ack,'elapsed_UART_seconds':clock()-started,
        'CY_range':[min(s['fields']['CY'] for s in good),max(s['fields']['CY'] for s in good)] if good else None,
        'GM_observed':sorted({s['fields']['GM'] for s in good}),
        'cache_hit_range':[min(s['fields']['HT'] for s in good),max(s['fields']['HT'] for s in good)] if good else None,
        'cache_miss_range':[min(s['fields']['MS'] for s in good),max(s['fields']['MS'] for s in good)] if good else None,
        'result_CRC_observed':sorted({f"{s['fields']['RC']:08X}" for s in good}),
        'pixel_CRC_observed':sorted({f"{s['fields']['PS']:08X}" for s in good}),
        'last_fields':last,'wire_path':str(rawpath),'wire_sha256':hw.sha(rawpath),
        'sample_log_path':str(logpath),'sample_log_sha256':hw.sha(logpath),
        'mask_crc_available':False,'gamma_mode_host_selectable':False,'new_lens_optical_pass':False,
        'limits':'WF=captured input; CF=new completed remaps; PF=HDMI-side refresh including repeats. '
        'RC/PS snapshots can describe different frames and are not a mask-only CRC. No sink/optical '
        'verification. ASCII UART has no packet CRC. Auto-off is not pipeline stop; finally heartbeat is required.'}


def serial_open(port):
    import serial
    link = serial.Serial(port=None,baudrate=BAUD,timeout=.05,write_timeout=1,rtscts=False,dsrdtr=False)
    try:
        link.dtr = False; link.rts = False; link.port = port; link.open()
    except BaseException:
        link.close(); raise
    return link


def check_idle_plan(plan, work):
    """Read-only recovery preflight; never start a process or consume the plan."""
    program = plan['program_plan']
    exit_plan = plan['idle_plan']
    budget = idle.validate_program_budget(exit_plan)
    outer = plan.get('time_budget')
    if (not isinstance(outer,dict) or outer.get('recovery_client_seconds') != budget['client_timeout_seconds']
            or outer.get('recovery_operation_wait_bound_seconds') != budget['operation_wait_bound_seconds']):
        raise ValueError('explicit matching sealed recovery budget required')
    exit_work = Path(exit_plan['workdir']).resolve()
    if (exit_plan.get('target') != 'heartbeat' or exit_plan.get('operation') != 'volatile_sram_only'
            or exit_plan['frequency'] != plan['frequency'] or idle.validate_heartbeat() != exit_plan['validation']
            or not exit_work.is_dir() or exit_work.parent != work
            or exit_work == Path(program['workdir']).resolve()
            or (exit_work/'receipt.json').exists()
            or exit_plan.get('executed') is not False or exit_plan.get('hardware_accessed') is not False
            or exit_plan.get('done_confirmed') is not False
            or exit_plan.get('requires_explicit_execute_flag') is not True
            or hw.load_json(exit_work/'plan.json') != exit_plan
            or Path(exit_plan['pds_bin']).resolve() != Path(program['pds_bin']).resolve()):
        # Reject an unusable recovery plan before even the candidate programmer
        # is entered. The idle executor checks freshness again at restoration.
        raise ValueError('fixed source-bound heartbeat exit required')
    check_scripts(exit_plan,idle._scripts)


def verify_plan(plan):
    limits(plan['port'],plan['seconds'],plan['frequency'],plan['angles_deg'])
    work = Path(plan['workdir']).resolve()
    if (not work.is_dir() or not work.is_relative_to(hw.APPROVED.resolve()) or (work/'result.json').exists()
            or plan.get('target') != TARGET or plan.get('operation') != 'finite_gamma_pipeline_then_fixed_heartbeat'
            or type(plan.get('baud')) is not int or plan['baud'] != BAUD
            or hw.load_json(work/'plan.json') != plan or helpers() != plan['source_sha256']):
        raise ValueError('fresh fixed source-bound Gamma plan required')
    program = plan['program_plan']
    if (Path(program['workdir']).resolve() != work/'candidate-program'
            or program['frequency'] != plan['frequency']
            or (Path(program['workdir'])/'receipt.json').exists()):
        raise ValueError('fresh own candidate-program directory and matching frequency required')
    validate_session_budget(plan)
    check_program(program)
    check_idle_plan(plan, work)
    return work


def execute_plan(plan, *, programmer=None, serial_factory=None, restorer=None):
    work = verify_plan(plan); programmer = programmer or execute_program
    serial_factory = serial_factory or serial_open; restorer = restorer or idle.execute_plan
    started = time.monotonic(); link = None; entered = False
    result = {'schema':1,'target':TARGET,'passed':False,'executed':True,'hardware_accessed':False,
        'program':None,'summary':None,'idle_program':None,'idle_restoration_attempted':False,'idle_done_confirmed':False,
        'new_lens_optical_pass':False,'workdir':str(work),'time_budget':plan['time_budget']}
    try:
        entered = True; result['program'] = programmer(plan['program_plan']); active = result['program']
        if (not isinstance(active,dict) or active.get('programming_attempted') is not True
                or active.get('passed') is not True or active.get('done_confirmed') is not True):
            raise RuntimeError('candidate SRAM/DONE unconfirmed; COM remains closed')
        check_program(plan['program_plan'])
        if helpers() != plan['source_sha256']:
            raise ValueError('helpers changed before UART')
        link = serial_factory(plan['port']); result['summary'] = run_uart(link,plan,work)
        check_program(plan['program_plan'])
        if helpers() != plan['source_sha256']:
            raise ValueError('helpers changed during UART')
        hw._new_json(work/'telemetry-summary.json',result['summary'])
    except (Exception,KeyboardInterrupt) as exc:
        result['error'] = type(exc).__name__+': '+str(exc)
    finally:
        if link is not None:
            try:
                link.close()
            except (Exception,KeyboardInterrupt) as exc:
                result['serial_close_error'] = str(exc)
        if entered and result['program'] is None:
            try:
                result['program'] = hw.load_json(Path(plan['program_plan']['workdir'])/'receipt.json')
            except (Exception,KeyboardInterrupt):
                result['programming_state_unknown'] = True
        active = result['program']
        if entered and not isinstance(active,dict):
            result['programming_state_unknown'] = True; active = {}
        if isinstance(active,dict):
            result['hardware_accessed'] |= bool(active.get('hardware_accessed'))
        attempted = (result.get('programming_state_unknown') or not isinstance(active,dict)
            or type(active.get('programming_attempted')) is not bool or active.get('programming_attempted')
            or active.get('passed') or active.get('done_confirmed'))
        if attempted:
            result['idle_restoration_attempted'] = True
            try:
                check_idle_plan(plan, work)
                result['idle_program'] = restorer(plan['idle_plan'],
                    timeout_seconds=plan['time_budget']['recovery_client_seconds'])
                result['idle_done_confirmed'] = bool(result['idle_program'].get('passed') and result['idle_program'].get('done_confirmed'))
                result['hardware_accessed'] |= bool(result['idle_program'].get('hardware_accessed'))
            except (Exception,KeyboardInterrupt) as exc:
                result['idle_error'] = str(exc)
        result['passed'] = bool(isinstance(active,dict) and active.get('passed') and result['summary']
            and result['summary']['passed'] and result['idle_done_confirmed']
            and not any(k in result for k in ('error','serial_close_error','idle_error')))
        result['elapsed_total_seconds'] = time.monotonic()-started
        result['checked_at_utc'] = datetime.now(timezone.utc).isoformat()
        result['limits'] = 'Finite function/performance SRAM event only; historical/development K/D is not '
        'new-lens optical acceptance. COM close/auto-off does not stop the pipeline. Fixed heartbeat DONE '
        'confirms only the recovery event, not continuous thermal safety or a host-death watchdog.'
        hw._new_json(work/'result.json',result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-dir'); p.add_argument('--workdir'); p.add_argument('--port')
    p.add_argument('--seconds',type=float,default=30); p.add_argument('--frequency',choices=('1MHz','5MHz'),default='5MHz')
    p.add_argument('--angles',default='0,13.25,181.125'); p.add_argument('--profile-binding')
    p.add_argument('--candidate-timeout-seconds',type=float)
    p.add_argument('--recovery-timeout-seconds',type=float)
    p.add_argument('--outer-wait-seconds',type=float)
    p.add_argument('--execute',action='store_true'); p.add_argument('--execute-plan')
    a = p.parse_args()
    if a.execute_plan:
        if a.execute:
            p.error('--execute-plan is the explicit execution boundary')
        if any(v is not None for v in (a.candidate_timeout_seconds,a.recovery_timeout_seconds,a.outer_wait_seconds)):
            p.error('execution uses sealed budgets; command-line budget overrides are rejected')
        result = execute_plan(hw.load_json(a.execute_plan)); print(json.dumps(result,indent=2)); return 0 if result['passed'] else 1
    if any(v is None for v in (a.build_dir,a.workdir,a.port)):
        p.error('planning requires --build-dir/--workdir/--port')
    budgets = {k:v for k,v in {'candidate_timeout_seconds':a.candidate_timeout_seconds,
        'recovery_timeout_seconds':a.recovery_timeout_seconds,'outer_wait_seconds':a.outer_wait_seconds}.items() if v is not None}
    plan = prepare_plan(a.build_dir,a.workdir,port=a.port,seconds=a.seconds,frequency=a.frequency,
        angles=[float(s) for s in a.angles.split(',')],profile_binding=a.profile_binding,**budgets)
    print(json.dumps({'plan':str(Path(plan['workdir'])/'plan.json'),'executing':a.execute}),flush=True)
    result = execute_plan(plan) if a.execute else plan; print(json.dumps(result,indent=2)); return 0 if not a.execute or result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
