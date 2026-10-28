"""Fixed CAM2 native720 candidate: prepare/plan/build offline only; no device API."""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, math, os, re, subprocess

ROOT=Path(__file__).resolve().parents[1]
APPROVED=ROOT/'build/offline-20261024'
BASE='raw_camera_capture_cam2_guarded'
TARGET=BASE+'_720p15'
BUILD_TAG=0x52373201
RAW_CONTRACT={'protocol':'PGFRAME1','payload_role':'native_raw','geometry_applied':False,'image_size':[1280,720]}
MODE_CONTRACT={'mode':'conditional-rgb565-1280x720-nominal15','pixel_format':'RGB565_LE',
    'nominal_xvclk_hz':24000000,'nominal_pclk_hz':42000000,'modeled_pclk_upper_hz_at27mhz':47250000,
    'hts':1892,'vts':740,'measured_fps':None,'calibration_accepted':False,
    'bank_base_units4':0,'bank_reserved_bytes':2097152,'frame_end_units4':460800,
    'payload_bytes':1843200,'ddr_beats32':57600,'minimum_good_frames':2,
    'startup_observation_ref_cycles':27000000,'uart_baud':921600,'initial_grant_frames':1,'lease_ms':24000,
    'configured_is_not_ready':True,'input_polarities':'same CAM2 logical inversions as reviewed VGA; final4740=23',
    'monitor_interlock':'admission only; never reset accepted DDR/UART transactions',
    'viewer_or_vga_calibration_inherited':False,'physical_pll_lock_proven':False,
    'hdmi_output_role':'independent720p_diagnostic_pattern_not_camera_image',
    'monitor_failed_address':65535,'mode_fault_clears_armed_immediately':False}
REFERENCES={
 'board/raw_camera_capture_cam2_guarded.v':'c4941b2dd62b771fdc71b6019b0cb738d78790cb3092b76b86b879279e7ee9cf',
 'board/raw_camera_capture_cam2_guarded.fdc':'016c5f4b44bfa6edd2ee0490632c8572e2165abdb9ec8a0c18960b08cd04a52b',
 'board/raw_camera_capture_cam2_guarded-pins.json':'7d4d158411d319fc7a5b6b4e9262deef414ad353a441608c08eae5bd9798bd98',
 'board/raw_camera_capture_cam2_guarded-sources.json':'538f357c33503eaf777d1780a11e04c8e455d1612ee172934ed134cd14afc823',
 'board/build-raw_camera_capture_cam2_guarded.tcl':'94ee8c17f24c4cd87b8d4c41a9da93a9c4932ad446cd735c1a023521cd59a7ee'}
MODE_SOURCES={
 'rtl/experimental/ov5640_rgb565_720_init.v':'403214d854a068e0b087fb0c2b00242cf36b2b2a326c9cde6803f6aa22ccabb5',
 'rtl/experimental/dvp_mode_admission_monitor.v':'2895bad17ecc74c0cceefce4a53de525a2516462e1bc082481d2d34de2ec8b55',
 'board/ov5640_rgb565_720_commands.vh':'05ce241ce37286b6820eeeaad28eeff0821f12d1319bdc6747c4fd04a72ff22c',
 'board/ov5640_rgb565_720_sequence.json':'88cd19153f7f5fda5c80b86a4112f6e689ca52f094642cd1e2ce967261ee2c5d'}
OWN=(f'board/{TARGET}.v',f'board/{TARGET}.fdc',f'board/{TARGET}-pins.json',f'board/build-{TARGET}.tcl')
OLD_INIT='rtl/experimental/ov5640_cadence_trial_init.v'
OLD_ROM='board/ov5640_cadence_trial_commands.vh'
LIMITS='Complete native720 transport candidate. Nominal15fps is a conditional register model, not measured FPS/PLL lock. No lens calibration, geometric/Gamma processing, stereo, physical HDMI or long-run thermal acceptance. HDMI outputs independent diagnostic bars, never a camera preview. Clock/geometry fault revokes admission; in-flight DDR/UART drains; existing armed lease is not immediately cleared solely by camera mode loss. SRAM-file build only; no device/Flash access.'

SENSOR_MODULE=r'''
// Shared by this board and its integration TB. Delays are simulation-scalable;
// I2C quarter68/full7FF0/action ROM and geometry/freshness policy stay fixed.
module raw720_cam2_sensor #(
    parameter RESET_CYCLES=270000,WAIT_CYCLES=1350000,MS_CYCLES=27000
)(input clk_27m,cam_pclk,rst_n,vsync,href,inout cam_rst_n,cam_scl,cam_sda,
    output camera_ready,camera_failed,configured,
    output [15:0] sensor_id,camera_failed_address,
    output [8:0] camera_writes,camera_noacks,
    output [7:0] camera_observed,camera_expected,cam_errors,
    output [31:0] good_frames,bad_frames,pclk_edges_per_window,
    output [15:0] last_frame_lines,last_line_bytes);
    wire init_failed,monitor_failed,monitor_authorize;
    wire [7:0] init_error,monitor_fault;wire [15:0] init_failed_address;
    wire [9:0] writes_completed,verified_noacks;
    ov5640_rgb565_720_init #(.RESET_CYCLES(RESET_CYCLES),.WAIT_CYCLES(WAIT_CYCLES),.MS_CYCLES(MS_CYCLES)) initializer(
        .clk(clk_27m),.rst_n(rst_n),.cam_rst_n(cam_rst_n),.cam_scl(cam_scl),.cam_sda(cam_sda),
        .sensor_id(sensor_id),.configured(configured),.failed(init_failed),.error_code(init_error),
        .failed_address(init_failed_address),.observed_value(camera_observed),.expected_value(camera_expected),
        .observed_valid(),.last_bus_error(),.action_index(),.failed_action(),
        .writes_completed(writes_completed),.verified_write_noacks(verified_noacks),.final_wake_verified());
    // 1s is a digital observation deadline, NOT a fabricated PLL-lock wait.
    // At15fps and arbitrary starting phase, two complete good frames need up
    // to about200ms. Default100ms in the generic observer would be too short.
    dvp_mode_admission_monitor #(.BYTES_PER_LINE(2560),.LINES_PER_FRAME(720),
        .STARTUP_REF_CYCLES(27000000)) monitor(.ref_clk(clk_27m),.pclk(cam_pclk),.rst_n(rst_n),
        .enable(configured && !init_failed),.vsync_active(vsync),.href_active(href),
        .raw_authorize(monitor_authorize),.failed(monitor_failed),.fault(monitor_fault),
        .good_frames(good_frames),.bad_frames(bad_frames),.pclk_edges_per_window(pclk_edges_per_window),
        .last_frame_lines(last_frame_lines),.last_line_bytes(last_line_bytes),
        .pclk_fresh(),.vsync_fresh(),.href_fresh(),.frame_fresh(),.snapshot_fresh());
    assign camera_ready=configured && !init_failed && !monitor_failed && monitor_authorize && good_frames>=2;
    assign camera_failed=init_failed || monitor_failed;
    assign cam_errors=init_failed ? init_error:monitor_fault;
    assign camera_failed_address=init_failed ? init_failed_address:monitor_failed ? 16'hffff:16'd0;
    //403 total actions include read checks; neither counter can reach512.
    assign camera_writes=writes_completed[8:0];assign camera_noacks=verified_noacks[8:0];
endmodule
'''

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):
    def unique(rows):
        out={}
        for key,value in rows:
            if key in out:raise ValueError('duplicate JSON key: '+key)
            out[key]=value
        return out
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),object_pairs_hook=unique,
                      parse_constant=lambda v: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
def same(a,b): return json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False)
def write_new(path,value):
    with Path(path).open('x',encoding='utf-8') as out:json.dump(value,out,indent=2,allow_nan=False);out.write('\n')
def replace_one(text,old,new):
    if text.count(old)!=1:raise ValueError('expected unique clone anchor: '+old[:80])
    return text.replace(old,new,1)
def control_contract():
    import guarded_protocol as gp
    result=dict(gp.GUARDED_CONTROL_CONTRACT);result['build_tag']=BUILD_TAG
    return result

def reference():
    for n,h in {**REFERENCES,**MODE_SOURCES}.items():
        if sha(ROOT/n)!=h:raise ValueError('frozen reference changed: '+n)
    original=load(ROOT/f'board/{BASE}-sources.json')
    if len(original['source_files'])!=107 or set(original['source_files'])!=set(original['SourceSHA256']):raise ValueError('reference107 closure differs')
    for n,h in original['SourceSHA256'].items():
        if sha(ROOT/n).lower()!=h.lower():raise ValueError('frozen VGA source changed: '+n)
    return original

def expected_files():
    old=reference();text=(ROOT/f'board/{BASE}.v').read_text(encoding='utf-8')
    text=replace_one(text,'module '+BASE+'(','module '+TARGET+'(')
    text=replace_one(text,"GUARDED_BUILD_TAG=32'h52473201","GUARDED_BUILD_TAG=32'h52373201")
    text=replace_one(text,'guarded_capture_controller #(.BUILD_TAG(GUARDED_BUILD_TAG)',
                     'guarded_capture_controller #(.WIDTH(1280),.HEIGHT(720),.BUILD_TAG(GUARDED_BUILD_TAG)')
    text=replace_one(text,'// OV5640 DVP/VGA/RGB565 setup + critical register readback + HDMI pattern.',
        '// OV5640 conditional720p15 model + full critical readback + live geometry/freshness.\n// Physical input clock/fps/PLL remain unmeasured; HDMI is diagnostic bars only.')
    start=text.index('    ov5640_cadence_trial_init #(');end=text.index('    assign cam_complete=',start)
    text=text[:start]+'''    raw720_cam2_sensor camera(.clk_27m(clk_27m),.cam_pclk(cam_pclk),.rst_n(rst_n),
        .vsync(!cam_vsync),.href(!cam_href),.cam_rst_n(cam_rst_n),.cam_scl(cam_scl),.cam_sda(cam_sda),
        .sensor_id(sensor_id),.camera_ready(camera_ready),.camera_failed(camera_failed),.configured(),
        .cam_errors(cam_errors),.camera_failed_address(camera_failed_address),.camera_writes(camera_writes),
        .camera_noacks(camera_noacks),.camera_observed(camera_observed),.camera_expected(camera_expected),
        .good_frames(),.bad_frames(),.pclk_edges_per_window(),.last_frame_lines(),.last_line_bytes());
'''+text[end:]
    start=text.index('    wire preview_ready;');end=text.index('    assign led=',start)
    text=text[:start]+'''    // Independent pattern only: no misleading VGA-scaled camera preview.
    video_pattern #(.MODE_720P(1)) picture(.clk(pix_clk),.rst_n(pixel_reset_sync[1]),
        .hs(hs_out),.vs(vs_out),.de(de_out),.r(r_out),.g(g_out),.b(b_out));
'''+text[end:]
    text='// Independent conditional720p15 native raw: no measured FPS/optical acceptance.\n'+text+SENSOR_MODULE
    fdc=(ROOT/f'board/{BASE}.fdc').read_text(encoding='utf-8')
    fdc=replace_one(fdc,'-group [get_clocks {clk_27m pixel_clk}]','-group [get_clocks {pixel_clk}]')
    fdc+='''
# New monitor: PCLK Gray edge/VSYNC/HREF counters ->27MHz two-flop first stage;
# held_snapshot plus request/ack travel both directions. No false clock group
# excludes these crossings.8ns bounds every Gray bit and held data path below
# the shortest48MHz source period, hence also bounds inter-bit Gray skew.
# Shared asynchronous reset with each domain's synchronized release is kept.
set_max_delay -datapath_only -from [get_clocks camera_pclk] -to [get_clocks clk_27m] 8.0
set_max_delay -datapath_only -from [get_clocks clk_27m] -to [get_clocks camera_pclk] 8.0
set_min_delay -from [get_clocks camera_pclk] -to [get_clocks clk_27m] 0.0
set_min_delay -from [get_clocks clk_27m] -to [get_clocks camera_pclk] 0.0
'''
    tcl=(ROOT/f'board/build-{BASE}.tcl').read_text(encoding='utf-8').replace(BASE,TARGET)
    tcl=replace_one(tcl,'add_design {'+str(ROOT/OLD_INIT).replace('\\','/')+'}',
        '\n'.join('add_design {'+str(ROOT/n).replace('\\','/')+'}' for n in MODE_SOURCES if n.endswith('.v')))
    gate=r'''# Final saved-DB timing is required BEFORE SRAM file generation.
set final_timing_path [file join [pwd] report_timing TARGET.rtr]
if {![file isfile $final_timing_path]} {error "Missing final timing report"}
set final_timing_handle [open $final_timing_path r]
set final_timing_text [read $final_timing_handle]
close $final_timing_handle
set summaries 0
set passes 0
foreach line [split $final_timing_text "\n"] {
    if {[regexp {^[ \t]*Design Summary[ \t]*:} $line]} {
        incr summaries
        if {[regexp {^[ \t]*Design Summary[ \t]*:[ \t]*All Constraints Met\.[ \t]*\r?$} $line]} {incr passes}
    }
}
if {$summaries != 1 || $passes != 1} {error "Final timing failed; no bitstream"}
'''.replace('TARGET',TARGET)
    tcl=replace_one(tcl,'gen_bit_stream -scbv',gate+'gen_bit_stream -scbv')
    names=[n.replace(BASE,TARGET) if n in [f'board/{BASE}.v',f'board/{BASE}.fdc',f'board/{BASE}-pins.json',f'board/build-{BASE}.tcl'] else n
           for n in old['source_files'] if n not in (OLD_INIT,OLD_ROM)]+list(MODE_SOURCES)
    if len(names)!=109 or len(set(names))!=109:raise ValueError('candidate109 closure differs')
    return {OWN[0]:text.encode(),OWN[1]:fdc.encode(),OWN[2]:(ROOT/f'board/{BASE}-pins.json').read_bytes(),OWN[3]:tcl.encode()},names

def prepare_sources():
    files,names=expected_files()
    for n,data in files.items():
        if (ROOT/n).exists() and (ROOT/n).read_bytes()!=data:raise ValueError('refusing differing new target: '+n)
    for n,data in files.items():
        if not (ROOT/n).exists():
            with (ROOT/n).open('xb') as out:out.write(data)
    p={'Target':TARGET,'source_files':names,'SourceSHA256':{n:sha(ROOT/n) for n in names},
       'ReferenceSHA256':REFERENCES,'RawCaptureContract':RAW_CONTRACT,'GuardedControlContract':control_contract(),
       'InputModeContract':MODE_CONTRACT,'HardwareAccessed':False,'CalibrationAccepted':False,'Limits':LIMITS}
    path=ROOT/f'board/{TARGET}-sources.json'
    if path.exists() and not same(load(path),p):raise ValueError('prepared candidate differs')
    if not path.exists():write_new(path,p)
    return verify_sources()

def verify_sources():
    files,names=expected_files()
    for n,data in files.items():
        if (ROOT/n).read_bytes()!=data:raise ValueError('strict clone differs: '+n)
    p=load(ROOT/f'board/{TARGET}-sources.json')
    if p.get('Target')!=TARGET or p.get('source_files')!=names or set(p.get('SourceSHA256',{}))!=set(names):raise ValueError('candidate109 source closure differs')
    for key,value in [('RawCaptureContract',RAW_CONTRACT),('GuardedControlContract',control_contract()),('InputModeContract',MODE_CONTRACT),('ReferenceSHA256',REFERENCES)]:
        if not same(p.get(key),value):raise ValueError('contract differs: '+key)
    for n,h in p['SourceSHA256'].items():
        if sha(ROOT/n)!=h:raise ValueError('candidate current source differs: '+n)
    pins=load(ROOT/OWN[2])
    if len(pins)!=129 or len(set(pins.values()))!=129 or pins.get('cam_data[5]')!='AA23' or pins.get('uart_rxd')!='B24':raise ValueError('129 unique reference pins required')
    return p

def verify_simulation(path):
    path=Path(path).resolve();sim=load(path)
    if not path.is_relative_to(APPROVED.resolve()) or sim.get('Passed') is not True or sim.get('HardwareAccessed') is not False or sim.get('Target')!=TARGET:raise ValueError('completed offline candidate integration evidence required')
    if sim.get('SourceSHA256')!=sim.get('SourceSHA256After') or sim.get('PreparedSHA256')!=sha(ROOT/f'board/{TARGET}-sources.json'):raise ValueError('integration source binding differs')
    required=set(verify_sources()['source_files'])|{'tools/build_raw720_cam2.py','tools/run_raw720_cam2_sim.py','tests/tb_raw720_cam2.sv'}
    if set(sim.get('SourceSHA256',{}))!=required:raise ValueError('full109+builder/runner/TB simulation binding required')
    for n,h in sim['SourceSHA256'].items():
        if sha(ROOT/n)!=h:raise ValueError('integration source changed: '+n)
    if not {'compile-stdout.log','elaborate-stdout.log','simulation.log'}.issubset(sim.get('LogSHA256',{})):raise ValueError('nonempty compile/elab/sim logs required')
    for n,h in sim['LogSHA256'].items():
        if Path(n).name!=n or sha(path.parent/n)!=h:raise ValueError('integration log differs')
    from run_raw720_cam2_sim import audit_wire
    if not same(audit_wire(path.parent/'raw720-cam2-stream.bin'),sim.get('WireAudit')):raise ValueError('whole720 mixed wire audit differs')
    return sim

def port_direction(port):
    if re.fullmatch(r'clk_27m|clk_p|clk_n|cam_pclk|cam_vsync|cam_href|cam_data\[\d+\]|uart_rxd',port):return 'input'
    if re.fullmatch(r'cam_rst_n|cam_scl|cam_sda|hd_scl|hd_sda|mem_dq\[\d+\]|mem_dqs(_n)?\[\d+\]',port):return 'inout'
    return 'output'
def validate_pins(path):
    active={}
    for line in Path(path).read_text(encoding='utf-8',errors='replace').splitlines():
        f=[x.strip() for x in line.split('|')]
        if len(f)>=7 and f[4]:
            if f[4] in active or f[6]!='YES' or f[5]!=port_direction(f[4]):raise ValueError('routed pin direction/active/uniqueness differs')
            active[f[4]]=f[0]
    if active!=load(ROOT/OWN[2]) or len(active)!=129:raise ValueError('actual129 routed map differs')
    return active
def read_text(path):
    data=Path(path).read_bytes();return data.decode('utf-16' if data.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8',errors='replace')
def validate_target(build_dir):
    work=Path(build_dir).resolve();m=load(work/'validated-build.json');p=verify_sources()
    if work==APPROVED.resolve() or not work.is_relative_to(APPROVED.resolve()):raise ValueError('approved fresh target build required')
    fixed={'Target':TARGET,'Device':'PG2L100H','Package':'FBG676','SCBV':'High Voltage','UnusedIO':'UNUSED','ProcessExitCode':0,'HardwareAccessed':False,'RawCaptureContract':RAW_CONTRACT,'GuardedControlContract':control_contract(),'InputModeContract':MODE_CONTRACT,'SourceSHA256':p['SourceSHA256'],'PreparedSHA256':sha(ROOT/f'board/{TARGET}-sources.json'),'BuilderSHA256':sha(__file__)}
    for k,v in fixed.items():
        if not same(m.get(k),v):raise ValueError('validated build binding differs: '+k)
    for k,h,rel in [('Bitstream','SHA256',f'generate_bitstream/{TARGET}.sbit'),('TimingReport','TimingSHA256',f'report_timing/{TARGET}.rtr'),('PinReport','PinReportSHA256',f'place_route/{TARGET}_prr.prt'),('FinalRoutedDatabase','FinalRoutedDatabaseSHA256',f'place_route/{TARGET}_pnr.adf'),('AfterHoldTimingReport','AfterHoldTimingSHA256',f'place_route/{TARGET}_timing_summary_after_hold_fix.txt')]:
        f=work/rel
        if m.get(k)!=str(f) or sha(f)!=m.get(h):raise ValueError('named artifact/hash differs: '+k)
    final=read_text(m['TimingReport']);routed=Path(m['FinalRoutedDatabase']);bit=Path(m['Bitstream'])
    if len(re.findall(r'(?m)^Design Summary\s*:',final))!=1 or not re.search(r'(?m)^Design Summary\s*:\s*All Constraints Met\.\s*$',final):raise ValueError('final saved-DB timing failed')
    if str(routed).replace('\\','/').lower() not in final.replace('\\','/').lower() or Path(m['TimingReport']).stat().st_mtime_ns<routed.stat().st_mtime_ns or bit.stat().st_mtime_ns<Path(m['TimingReport']).stat().st_mtime_ns or not bit.stat().st_size:raise ValueError('final DB/timing/bit freshness differs')
    validate_pins(m['PinReport'])
    if sha(m['SimulationEvidence'])!=m['SimulationEvidenceSHA256']:raise ValueError('sim report changed')
    verify_simulation(m['SimulationEvidence'])
    return m

def run_build(workdir,*,execute=False,simulation_evidence=None,pds_bin=None,timeout_seconds=7200):
    if type(execute) is not bool or type(timeout_seconds) not in (int,float) or not math.isfinite(timeout_seconds) or not 60<=timeout_seconds<=7200:raise ValueError('explicit execute/finite60..7200s bound required')
    work=Path(workdir).resolve()
    if work==APPROVED.resolve() or not work.is_relative_to(APPROVED.resolve()) or work.exists() or not work.parent.is_dir():raise ValueError('fresh child of approved scratch required')
    p=verify_sources();simpath=Path(simulation_evidence).resolve() if simulation_evidence else None
    if simpath:verify_simulation(simpath)
    if execute and simpath is None:raise ValueError('actual candidate integration simulation required before PDS')
    work.mkdir();plan={'Target':TARGET,'ExecuteBuild':execute,'HardwareAccessed':False,'Operation':'offline_compile_route_sram_file_only','NoFlashOrProgrammingOperation':True,'SourceSHA256':p['SourceSHA256'],'BuilderSHA256':sha(__file__),'PreparedSHA256':sha(ROOT/f'board/{TARGET}-sources.json'),'RawCaptureContract':RAW_CONTRACT,'InputModeContract':MODE_CONTRACT,'SimulationEvidence':str(simpath) if simpath else None,'SimulationEvidenceSHA256':sha(simpath) if simpath else None}
    write_new(work/'plan.json',plan)
    if not execute:return plan
    child=None;result={'Target':TARGET,'Passed':False,'HardwareAccessed':False,'ProcessExitCode':None,'StartedUtc':datetime.now(timezone.utc).isoformat()}
    try:
        config=load(ROOT.parent/'team-config.local.json') if (ROOT.parent/'team-config.local.json').is_file() else {}
        pds=Path(pds_bin or os.environ.get('FPGA_PDS_BIN') or config.get('pds_bin') or r'E:\Pango\PDS_2022.2-SP6.4\bin')
        command=[str(pds/'pds_shell.exe'),'-file',str(ROOT/OWN[3]),'-work_dir',str(work),'-project_name',TARGET]
        with (work/'build-stdout.log').open('xb') as out,(work/'build-stderr.log').open('xb') as err:
            child=subprocess.Popen(command,cwd=work,stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));result['OwnedPID']=child.pid;result['ProcessExitCode']=child.wait(timeout=timeout_seconds)
        if result['ProcessExitCode']!=0 or sha(__file__)!=plan['BuilderSHA256'] or verify_sources()!=p:raise ValueError('PDS exit/source/helper changed')
        logs=read_text(work/'build-stdout.log')+'\n'+read_text(work/'build-stderr.log')
        if re.search(r'(?m)^\s*E:',logs) or not re.search(r'(?m)^Executing : gen_bit_stream (?:-force_to_run )?-scbv \{High Voltage\} -unused_io_status UNUSED successfully\.\s*$',logs):raise ValueError('PDS SRAM generation not successful')
        m={'Target':TARGET,'Device':'PG2L100H','Package':'FBG676','SCBV':'High Voltage','UnusedIO':'UNUSED','ProcessExitCode':0,'HardwareAccessed':False,'SourceSHA256':p['SourceSHA256'],'PreparedSHA256':plan['PreparedSHA256'],'BuilderSHA256':sha(__file__),'RawCaptureContract':RAW_CONTRACT,'GuardedControlContract':control_contract(),'InputModeContract':MODE_CONTRACT,'SimulationEvidence':str(simpath),'SimulationEvidenceSHA256':sha(simpath),'Limits':LIMITS}
        for k,h,rel in [('Bitstream','SHA256',f'generate_bitstream/{TARGET}.sbit'),('TimingReport','TimingSHA256',f'report_timing/{TARGET}.rtr'),('PinReport','PinReportSHA256',f'place_route/{TARGET}_prr.prt'),('FinalRoutedDatabase','FinalRoutedDatabaseSHA256',f'place_route/{TARGET}_pnr.adf'),('AfterHoldTimingReport','AfterHoldTimingSHA256',f'place_route/{TARGET}_timing_summary_after_hold_fix.txt')]:m[k]=str(work/rel);m[h]=sha(work/rel)
        write_new(work/'validated-build.json',m);validate_target(work);result.update(Passed=True,ValidatedBuild=str(work/'validated-build.json'))
    except (Exception,KeyboardInterrupt) as exc:result['Error']=type(exc).__name__+': '+str(exc)
    finally:
        if child is not None and child.poll() is None:
            if os.name=='nt':subprocess.run([str(Path(os.environ['SystemRoot'])/'System32/taskkill.exe'),'/PID',str(child.pid),'/T','/F'],capture_output=True,timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
            else:child.kill()
            child.wait(timeout=20)
        result['EndedUtc']=datetime.now(timezone.utc).isoformat();write_new(work/'build-result.json',result)
    return result

def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--prepare',action='store_true');a.add_argument('--workdir');a.add_argument('--simulation-evidence');a.add_argument('--execute-build',action='store_true');a.add_argument('--pds-bin');args=a.parse_args()
    if args.prepare:r=prepare_sources();print(json.dumps({'Target':TARGET,'SourceCount':len(r['source_files'])}));return 0
    if not args.workdir:a.error('--workdir required')
    result=run_build(args.workdir,execute=args.execute_build,simulation_evidence=args.simulation_evidence,pds_bin=args.pds_bin);print(json.dumps(result,indent=2));return 0 if not args.execute_build or result.get('Passed') else 1
if __name__=='__main__':raise SystemExit(main())
