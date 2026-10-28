"""Prepare/validate/build the fixed six-pin register-only CAM1 diagnostic; never hardware."""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import struct
import zlib

ROOT=Path(__file__).resolve().parents[1]
APPROVED=ROOT/'build/offline-20261024'
TARGET='cam1_transaction_probe'
DIAGNOSTIC_CONTRACT={'protocol':'PGCAMD01','packet_bytes':64,'crc32_cover_bytes':56,
    'baud':921600,'clock_hz':27000000,'quarter_cycles':68,'pad_mask':32752,
    'readonly_failed_probe_addresses':[12298,12299,12312],
    'raw_frames':False,'ddr_outputs':False,'hdmi_outputs':False}
REFERENCES={'board/raw_camera_capture_cam1_guarded.fdc':'E910693AC8ADC725D717AF97A3E4CFA0388777B64E5F6E5863246FED3BCAA44C',
    'board/raw_camera_capture_cam1_guarded-pins.json':'3D1AFC93D302B79A4B5F9757F26E1CCE752E8E416A928DAD72A720E587E4C8FA'}
PIN_MAP={'clk_27m':'D18','uart_txd':'C24','cam_rst_n':'T20','cam_scl':'W21','cam_sda':'U14','led0':'A20'}
DEPENDENCIES={'rtl/experimental/ov5640_cadence_diagnostic_init.v':'E6740C69DE616BD27478E39BC206D1A8891BD8FFD6AF0A92D9805E8B9BF7F3D2',
    'rtl/reg16_i2c.v':'7DB5335DEE7D64EDDF3905008A1CD64262889D0A9EBEF63C74D4612D70A5A580',
    'rtl/uart_tx.v':'0A691C35B88D4305D9C74C4ACD8676DEFA09C8C5AAE7D7EE653C561F40B49D2B',
    'board/ov5640_cadence_trial_commands.vh':'53428872AA14E6120EED93D876C889EF5155B3C196C014DB77C4578B2BD50674'}
INIT_SIM=APPROVED/'cadence-diagnostic-sim-20261026T003834260374Z-f19892/cadence-diagnostic-init-simulation.json'
INIT_SIM_SHA='A346EB916BAD51FB5E0F017C773D89F72F8D37151B02FFE9C4CABEF4BCEE9B27'
SOURCE_FILES=list(DEPENDENCIES)+[f'board/{TARGET}.v',f'board/{TARGET}.fdc',f'board/{TARGET}-pins.json',f'board/build-{TARGET}.tcl']
SIM_SOURCE_FILES=SOURCE_FILES+['tests/tb_cam1_transaction_probe_uart.sv','tools/run-cam1-transaction-probe-sim.ps1',
    'tools/build_cam1_transaction_probe.py']+list(REFERENCES)
REQUIRED_LOGS={'compile-stdout.log','elab-stdout.log','transaction-probe-simulation.log'}
LIMITS='Register-only CAM1 diagnostic. Fixed3 failed-state reads never clear original FAILED status. No RAW/DDR/HDMI, input-mode/optics/synchronization or temperature-safety acceptance. Digital2FF pad levels are not measured voltages/waveforms. Offline SRAM file only; no Flash or hardware operation.'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest().upper()
def same(a,b):return json.dumps(a,sort_keys=True)==json.dumps(b,sort_keys=True)
def load(path):
    def unique(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate JSON key: '+key)
            result[key]=value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=unique)
def write_new(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def expected_board_files():
    for name,digest in {**REFERENCES,**DEPENDENCIES}.items():
        if sha(ROOT/name)!=digest:raise ValueError('frozen dependency/reference changed: '+name)
    source=(ROOT/'board/raw_camera_capture_cam1_guarded.fdc').read_bytes()
    oldpins=load(ROOT/'board/raw_camera_capture_cam1_guarded-pins.json')
    lines=[b'create_clock -name clk_27m -period 37.037 [get_ports clk_27m]\n',
        b'set_false_path -from [get_ports {cam_rst_n cam_scl cam_sda}] -to [get_clocks clk_27m]\n']
    for port,pad in PIN_MAP.items():
        old='led[0]' if port=='led0' else port
        if oldpins.get(old)!=pad:raise ValueError('reviewed CAM1 reference pad differs')
        attrs=[line for line in source.splitlines() if ('{p:'+old+'}').encode() in line]
        if len(attrs)!=(3 if port=='clk_27m' else 5):raise ValueError('complete original electrical attributes required')
        lines.extend(line.replace(('{p:'+old+'}').encode(),('{p:'+port+'}').encode())+b'\n' for line in attrs)
    tcl=''.join('add_design {'+str(ROOT/name).replace('\\','/')+'}\n' for name in SOURCE_FILES if name.endswith('.v'))
    tcl+='add_constraint {'+str(ROOT/f'board/{TARGET}.fdc').replace('\\','/')+'}\n'
    tcl+='set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
    tcl+='compile -top_module '+TARGET+'\nsynthesize -ads -selected_syn_tool_opt 2\ndev_map\n'
    tcl+='pnr -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE\nreport_timing -max_path 5\ngen_bit_stream -scbv {High Voltage} -unused_io_status UNUSED\n'
    return {f'board/{TARGET}.fdc':b''.join(lines),f'board/{TARGET}-pins.json':(json.dumps(PIN_MAP,indent=2)+'\n').encode(),f'board/build-{TARGET}.tcl':tcl.encode()}


def check_top():
    text=(ROOT/f'board/{TARGET}.v').read_text()
    for literal in ['STATUS_PERIOD_CYCLES=13500000', '.DYNAMIC_PAD_MASK(1),.I2C_QUARTER_CYCLES(68),.DIAGNOSTIC_PROBES(1)',
                    ".trial_pad_mask(16'h7ff0)",'.CLOCK_HZ(27000000),.BAUD(921600)']:
        if text.count(literal)!=1:raise ValueError('fixed diagnostic top specialization differs: '+literal)
    if any(name in text for name in ('ddr3_test','hdmi_tx_init','raw_camera_capture')):raise ValueError('non-diagnostic block in fixed top')


def prepare_sources():
    files=expected_board_files();check_top()
    for name,data in files.items():
        if (ROOT/name).exists() and (ROOT/name).read_bytes()!=data:raise ValueError('refusing to overwrite differing candidate: '+name)
    for name,data in files.items():
        if not (ROOT/name).exists():
            with (ROOT/name).open('xb') as f:f.write(data)
    prepared={'Target':TARGET,'source_files':SOURCE_FILES,'SourceSHA256':{n:sha(ROOT/n) for n in SOURCE_FILES},
        'ReferenceSourceSHA256':REFERENCES,'DiagnosticContract':DIAGNOSTIC_CONTRACT,
        'HardwareAccessed':False,'SourceKind':'camera_transaction_diagnostic','limits':LIMITS}
    path=ROOT/f'board/{TARGET}-sources.json'
    if path.exists() and not same(load(path),prepared):raise ValueError('refusing to overwrite differing prepared source evidence')
    if not path.exists():write_new(path,prepared)
    return verify_sources()


def verify_sources():
    check_top()
    for name,data in expected_board_files().items():
        if (ROOT/name).read_bytes()!=data:raise ValueError('fixed6 electrical/Tcl candidate differs: '+name)
    p=load(ROOT/f'board/{TARGET}-sources.json')
    if p.get('Target')!=TARGET or p.get('source_files')!=SOURCE_FILES or set(p.get('SourceSHA256',{}))!=set(SOURCE_FILES):raise ValueError('fixed8 source closure differs')
    if not same(p.get('DiagnosticContract'),DIAGNOSTIC_CONTRACT) or not same(p.get('ReferenceSourceSHA256'),REFERENCES):raise ValueError('fixed diagnostic contract/references differ')
    for name,digest in p['SourceSHA256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('prepared source changed: '+name)
    return p


def audit_uart_wires(directory):
    work=Path(directory).resolve();result={}
    for filename,kind in [('pgcamd01-success-wire.bin','complete_original_success'),('pgcamd01-read-nack-wire.bin','write4_read1_pending61')]:
        data=(work/filename).read_bytes()
        if not data or len(data)%64:raise ValueError('UART wire is empty/truncated')
        terminal=[];last_uptime=0
        for offset in range(0,len(data),64):
            b=data[offset:offset+64];u16=lambda n:struct.unpack_from('<H',b,n)[0];u32=lambda n:struct.unpack_from('<I',b,n)[0]
            if b[:8]!=b'PGCAMD01' or b[8:12]!=bytes([1,64,1,0]) or b[60:]!=b'CD01' or u32(56)!=zlib.crc32(b[:56]):raise ValueError('UART header/CRC/tail differs')
            if b[50:56]!=bytes(6) or u16(37)!=0x7ff0 or u16(39)!=68 or u32(45)!=offset//64+1 or u32(41)<last_uptime or b[49]>7:raise ValueError('UART reserved/parameter/sequence/uptime/sample mask differs')
            last_uptime=u32(41)
            if kind=='complete_original_success' and b[27]&1:
                if (u16(12),b[14],b[15],u16(18),u16(20),b[24],b[25],b[26],b[27],b[28:34])!=(0x5640,0,0xf3,264,0,0,0,0xf0,9,bytes(6)):raise ValueError('original successful transaction status differs')
                terminal.append(offset//64+1)
            if kind=='write4_read1_pending61' and b[27]&4:
                if (u16(12),b[14],b[15],u16(16),u16(18),u16(20),b[23],b[24],b[25],b[27],b[28:37])!=(0x5640,0x61,0x3f,0x3018,262,0,0xf0,4,1,14,bytes([7,7,7,3,0,0,0x56,0x40,0xf0])):raise ValueError('write4/read1/pending/invalid-read/fixed3 probe status differs')
                terminal.append(offset//64+1)
        if len(terminal)<2:raise ValueError('two complete terminal status snapshots required per actual-top case')
        result[filename]={'Case':kind,'SHA256':sha(work/filename),'Packets':len(data)//64,'TerminalSequences':terminal,'CRCAndFieldsVerified':True}
    return result


def verify_simulation(path):
    path=Path(path).resolve()
    if not path.is_relative_to(APPROVED.resolve()):raise ValueError('simulation must be inside approved scratch')
    sim=load(path)
    if sim.get('Passed') is not True or sim.get('HardwareAccessed') is not False or sim.get('Target')!=TARGET or sim.get('Cases')!=['complete_original_success','write4_read1_pending61']:
        raise ValueError('two actual-top UART cases required')
    if sim.get('PreparedSourceManifestSHA256')!=sha(ROOT/f'board/{TARGET}-sources.json') or sim.get('SourceSHA256')!=sim.get('SourceSHA256After'):raise ValueError('simulation source binding changed')
    if set(sim.get('SourceSHA256',{}))!=set(SIM_SOURCE_FILES):raise ValueError('exact actual-top/initializer/UART/TB/runner/builder source13 binding required')
    for name,digest in sim['SourceSHA256'].items():
        if sha(ROOT/name.replace('\\','/'))!=digest:raise ValueError('simulation source no longer current: '+name)
    if not REQUIRED_LOGS.issubset(sim.get('LogSHA256',{})):raise ValueError('compile/elaborate/actual UART logs required')
    for name,digest in sim['LogSHA256'].items():
        file=path.parent/name
        if file.parent!=path.parent or sha(file)!=digest:raise ValueError('simulation log mismatch')
    wires=audit_uart_wires(path.parent)
    if not same(wires,sim.get('WireAudit')) or sim.get('WireSHA256')!={name:value['SHA256'] for name,value in wires.items()}:raise ValueError('two real UART wire/hash/CRC case evidence changed')
    if sha(INIT_SIM)!=INIT_SIM_SHA:raise ValueError('frozen7-case diagnostic init evidence changed')
    init=load(INIT_SIM)
    if init.get('Passed') is not True or init.get('HardwareAccessed') is not False or init.get('MeasuredConsecutiveBitPeriodCoreCycles')!=274:raise ValueError('successful original-preserving diagnostic init proof required')
    return sim


def validate_pins(path):
    active={}
    for line in Path(path).read_text().splitlines():
        f=line.split('|')
        if len(f)>=7 and f[4]:
            direction='input' if f[4]=='clk_27m' else 'inout' if f[4] in ('cam_rst_n','cam_scl','cam_sda') else 'output'
            if f[4] in active or f[6]!='YES' or f[5]!=direction:raise ValueError('routed port direction/active/uniqueness differs')
            active[f[4]]=f[0]
    if active!=PIN_MAP or len(set(active.values()))!=6:raise ValueError('exact6 routed pins required')
    return active


def validate_target(build_dir):
    work=Path(build_dir).resolve()
    if not work.is_relative_to(APPROVED.resolve()) or work==APPROVED.resolve():raise ValueError('fixed candidate build must be below approved scratch')
    m=load(work/'validated-build.json');p=verify_sources()
    fixed={'Target':TARGET,'Device':'PG2L100H','Package':'FBG676','SCBV':'High Voltage','UnusedIO':'UNUSED','ProcessExitCode':0,'HardwareAccessed':False}
    if any(not same(m.get(k),v) for k,v in fixed.items()):raise ValueError('fixed diagnostic build identity/exit differs')
    if not same(m.get('DiagnosticContract'),DIAGNOSTIC_CONTRACT) or m.get('SourceSHA256')!=p['SourceSHA256'] or m.get('ReferenceSourceSHA256')!=REFERENCES:raise ValueError('current source8/contract/reference binding differs')
    if m.get('PreparedSourceManifestSHA256')!=sha(ROOT/f'board/{TARGET}-sources.json') or m.get('BuilderSHA256')!=sha(__file__):raise ValueError('prepared/helper binding differs')
    for pathkey,hashkey,relative in [('Bitstream','SHA256',f'generate_bitstream/{TARGET}.sbit'),('TimingReport','TimingSHA256',f'place_route/{TARGET}_timing_summary_after_hold_fix.txt'),('PinReport','PinReportSHA256',f'place_route/{TARGET}_prr.prt')]:
        file=(work/relative).resolve()
        if m.get(pathkey)!=str(file) or sha(file)!=m.get(hashkey):raise ValueError('exact named artifact/hash differs: '+pathkey)
    if not Path(m['TimingReport']).read_text().startswith('Design Summary : All Constraints Met.'):raise ValueError('final after-hold timing failed')
    validate_pins(m['PinReport'])
    if sha(m['SimulationEvidence'])!=m.get('SimulationEvidenceSHA256'):raise ValueError('simulation evidence hash changed')
    verify_simulation(m['SimulationEvidence'])
    return m


def run_build(workdir,*,execute=False,simulation_evidence=None,pds_bin=None,timeout_seconds=600):
    if type(execute) is not bool or type(timeout_seconds) not in (int,float) or not math.isfinite(timeout_seconds) or not 60<=timeout_seconds<=1800:raise ValueError('explicit execution flag and finite60..1800s bound required')
    work=Path(workdir).resolve()
    if not work.is_relative_to(APPROVED.resolve()) or work==APPROVED.resolve() or work.exists() or not work.parent.is_dir():raise ValueError('fresh output below existing approved scratch required')
    p=verify_sources();simpath=Path(simulation_evidence).resolve() if simulation_evidence else None
    if simpath:verify_simulation(simpath)
    if execute and simpath is None:raise ValueError('actual-top UART simulation required before PDS')
    work.mkdir()
    plan={'Target':TARGET,'ExecuteBuild':execute,'HardwareAccessed':False,'NoFlashOrProgrammingOperation':True,'DiagnosticContract':DIAGNOSTIC_CONTRACT,'SourceSHA256':p['SourceSHA256'],'BuilderSHA256':sha(__file__),'SimulationEvidence':str(simpath) if simpath else None,'SimulationEvidenceSHA256':sha(simpath) if simpath else None}
    write_new(work/'plan.json',plan)
    if not execute:return plan
    result={'Target':TARGET,'Passed':False,'HardwareAccessed':False,'ProcessExitCode':None,'StartedUtc':datetime.now(timezone.utc).isoformat()};child=None
    try:
        pds=Path(pds_bin or os.environ.get('FPGA_PDS_BIN',r'E:\Pango\PDS_2022.2-SP6.4\bin'))
        command=[str(pds/'pds_shell.exe'),'-file',str(ROOT/f'board/build-{TARGET}.tcl'),'-work_dir',str(work),'-project_name',TARGET]
        flags={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
        with (work/'build-stdout.log').open('xb') as out,(work/'build-stderr.log').open('xb') as err:
            child=subprocess.Popen(command,cwd=work,stdout=out,stderr=err,**flags);result['OwnedPID']=child.pid
            result['ProcessExitCode']=child.wait(timeout=timeout_seconds)
        if result['ProcessExitCode']!=0:raise ValueError('native PDS exit nonzero')
        if verify_sources()!=p or sha(__file__)!=plan['BuilderSHA256'] or sha(simpath)!=plan['SimulationEvidenceSHA256']:raise ValueError('source/evidence changed during build')
        stdout=(work/'build-stdout.log').read_text(errors='replace');stderr=(work/'build-stderr.log').read_text(errors='replace')
        if re.search(r'(?m)^\s*E:',stdout+'\n'+stderr) or 'Executing : gen_bit_stream -scbv {High Voltage} -unused_io_status UNUSED successfully.' not in stdout:raise ValueError('SRAM-file-only generation did not finish')
        timing=work/f'place_route/{TARGET}_timing_summary_after_hold_fix.txt';pins=work/f'place_route/{TARGET}_prr.prt';bit=work/f'generate_bitstream/{TARGET}.sbit'
        if not timing.read_text().startswith('Design Summary : All Constraints Met.') or not bit.stat().st_size:raise ValueError('final timing/nonempty named bitstream required')
        validate_pins(pins)
        m={'Target':TARGET,'Device':'PG2L100H','Package':'FBG676','SCBV':'High Voltage','UnusedIO':'UNUSED','Bitstream':str(bit),'SHA256':sha(bit),'TimingReport':str(timing),'TimingSHA256':sha(timing),'PinReport':str(pins),'PinReportSHA256':sha(pins),'SourceSHA256':p['SourceSHA256'],'ReferenceSourceSHA256':REFERENCES,'PreparedSourceManifest':str(ROOT/f'board/{TARGET}-sources.json'),'PreparedSourceManifestSHA256':sha(ROOT/f'board/{TARGET}-sources.json'),'DiagnosticContract':DIAGNOSTIC_CONTRACT,'BuilderSHA256':sha(__file__),'SimulationEvidence':str(simpath),'SimulationEvidenceSHA256':sha(simpath),'ProcessExitCode':0,'HardwareAccessed':False,'SourceKind':'camera_transaction_diagnostic','Limits':LIMITS}
        write_new(work/'validated-build.json',m);validate_target(work);result.update(Passed=True,ValidatedBuild=str(work/'validated-build.json'),ValidatedBuildSHA256=sha(work/'validated-build.json'))
    except (Exception,KeyboardInterrupt) as error:result['Error']=type(error).__name__+': '+str(error)
    finally:
        if child is not None and child.poll() is None:
            if os.name=='nt':
                with (work/'owned-stop.log').open('xb') as out:subprocess.run([str(Path(os.environ['SystemRoot'])/'System32/taskkill.exe'),'/PID',str(child.pid),'/T','/F'],stdout=out,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            else:child.kill()
            child.wait(timeout=30)
        result['EndedUtc']=datetime.now(timezone.utc).isoformat();write_new(work/'build-result.json',result)
    return result


def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--prepare',action='store_true');a.add_argument('--workdir');a.add_argument('--execute-build',action='store_true');a.add_argument('--simulation-evidence');a.add_argument('--pds-bin');a.add_argument('--audit-uart-dir');args=a.parse_args()
    if args.audit_uart_dir:print(json.dumps(audit_uart_wires(args.audit_uart_dir),indent=2));return 0
    if args.prepare:r=prepare_sources();print(json.dumps({'Target':TARGET,'SourceCount':len(r['source_files']),'Pins':PIN_MAP}));return 0
    if not args.workdir:a.error('--workdir required except --prepare')
    r=run_build(args.workdir,execute=args.execute_build,simulation_evidence=args.simulation_evidence,pds_bin=args.pds_bin);print(json.dumps(r,indent=2));return 0 if not args.execute_build or r.get('Passed') else 1


if __name__=='__main__':raise SystemExit(main())
