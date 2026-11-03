"""Fresh150MHz raw HDMI activity diagnostic build, without bitstream/hardware.

RX/TX/PLL/pattern source bytes stay the exact rearm configuration. New raw
activity and UART replace the trained observer. No old mapping/count/STA or
timing exceptions are inherited; this target needs its own physical audit.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

import prepare_hdmi_uart_diagnostic as electrical
import run_camera_vga_output_diagnostic as cleanup

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'work/hdmi-camera1080-raw-20261102-a'
SELF=Path(__file__).resolve()
TARGET='hdmi_camera_raw_diag'
TOP='board/'+TARGET+'.v'
UART='rtl/experimental/hdmi_camera_raw_uart.v'
RAW='rtl/experimental/hdmi_raw_activity.v'
FDC='hdmi-camera-raw.fdc'
BASE=ROOT/'build/hdmi-uart-diagnostic/trained-pds-rearm-1031-a'
BASE_SHA='7d6dd6776887a93c328faabc149ddccbd924cef2f23b5ddc1bcc73d141ba8f18'
UNCHANGED=('rtl/uart_tx.v','rtl/experimental/ms72xx_rearm_observed_ctl.v',
    'rtl/experimental/ms7200_1080p30_rearm_ctl.v','rtl/experimental/ms7210_checked_ctl.v',
    'rtl/experimental/iic_dri_checked.v','platform/video_base/ipcore/cfg_pll/cfg_pll.v',
    'board/bringup_pll.v','rtl/video_pattern.v')
SOURCES=(TOP,UART,RAW,*UNCHANGED)
STAGES=['Compile','Synthesize','Device Map','Place','Route','Route Optimize','Report Timing']
SCHEMA='hdmi-camera-raw-build-v1'


def require(value,message):
    if not value:raise ValueError(message)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def utc():return datetime.now(timezone.utc).isoformat()


def write(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as f:
        json.dump(value,f,indent=2,allow_nan=False);f.write('\n')


def work_path(value):
    path=Path(value).absolute()
    require(path==path.resolve() and path.parent==WORK.resolve()
            and re.fullmatch('[A-Za-z0-9_-]+',path.name),'canonical direct raw diagnostic work directory required')
    return path


def render_constraints(text):
    clock=r'(?m)^create_clock -name input_pixel -period [0-9.]+ \[get_ports pixclk_in\]$'
    require(len(re.findall(clock,text))==1,'exact one source input clock required')
    require(not any(re.match(r'\s*(?:set_false_path|set_clock_groups|set_max_delay|set_min_delay|set_multicycle_path)\b',line)
                    for line in text.splitlines()),'initial diagnostic constraints must have no timing exceptions')
    return ('# Fresh raw-activity diagnostic.150MHz internal STA envelope only.\n'
        '# External input/output AC and analog CDC/MTBF are not accepted.\n'
        +re.sub(clock,'create_clock -name input_pixel -period 6.6667 [get_ports pixclk_in]',text)+'\n')


def recipe(work):
    work=work_path(work)
    require(sha(BASE/'build-plan.json')==BASE_SHA,'frozen rearm source plan changed')
    baseline=read(BASE/'build-plan.json')
    bindings={str(BASE/'build-plan.json'):BASE_SHA}
    payloads={}
    for name in SOURCES:
        source=ROOT/name
        require(source.is_file(),'raw diagnostic source is not ready: '+name)
        if name in UNCHANGED:
            frozen=BASE/'frozen-inputs'/name
            require(sha(source)==sha(frozen)==baseline['FrozenInputSHA256']['frozen-inputs/'+name],
                    'retained RX/TX/clock source differs: '+name)
            bindings[str(frozen)]=sha(frozen)
        data=source.read_bytes()
        require(b'`include' not in data,'unexpected unbound include in raw diagnostic source: '+name)
        payloads[work/'frozen-inputs'/name]=data
        bindings[str(source)]=sha(source)
    constraints,pins=electrical.constraints()
    payloads[work/FDC]=render_constraints(constraints).encode('ascii')
    tcl='\n'.join('add_design {'+p.as_posix()+'}' for p in payloads if p.suffix=='.v')+'\n'
    tcl+=('add_constraint {'+(work/FDC).as_posix()+'}\n'
        'set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
        'compile -top_module '+TARGET+'\nsynthesize -ads -selected_syn_tool_opt 2\ndev_map\n'
        'pnr -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 '
        '-fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE\n'
        'report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n')
    payloads[work/'build.tcl']=tcl.encode('ascii')
    config=ROOT.parent/'team-config.local.json'
    pds=Path(read(config)['pds_bin'])/'pds_shell.exe'
    require(pds.is_file(),'configured PDS executable missing')
    for path in (SELF,Path(electrical.__file__).resolve(),Path(cleanup.__file__).resolve(),
                 ROOT/electrical.FDC_SOURCE,config,pds):bindings[str(path)]=sha(path)
    plan={'Schema':SCHEMA,'Target':TARGET,'ProjectRoot':str(ROOT),'WorkDirectory':str(work),
        'InputSHA256':bindings,'PreparedSHA256':{str(p):hashlib.sha256(d).hexdigest() for p,d in payloads.items()},
        'SourceFiles':list(SOURCES),'RetainedExactRearmSources':list(UNCHANGED),'Pins':pins,
        'InputPixelPeriodNS':6.6667,'MaximumInputHzNominal':150000000,'BaselineTimingInherited':False,
        'InitialSTAADFBeforeAfterVerified':False,
        'InitialTimingExceptionsApplied':False,'ExpectedStages':STAGES,'MaximumSeconds':1800,
        'Command':[str(pds),'-file',(work/'build.tcl').as_posix(),'-work_dir',work.as_posix(),'-project_name',TARGET],
        'SyntheticColorBarsOnly':True,'PixelPayloadCaptured':False,'DDRIncluded':False,
        'HardwareAccessed':False,'BitstreamRequested':False,'HardwareReleaseAllowed':False,
        'Limits':'New raw timing measurements only. Own mapped reset/CDC/pins/full STA required before a separate diagnostic bitstream. Output bars do not display HDMI input pixels.'}
    return plan,payloads


def prepare(work):
    work=work_path(work);require(not work.exists(),'fresh build directory required')
    plan,payloads=recipe(work)
    work.mkdir(parents=True)
    for path,data in payloads.items():path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    plan['PreparedUTC']=utc();write(work/'plan.json',plan)
    return plan


def validate(path):
    path=Path(path).absolute();work=work_path(path.parent);plan=read(path)
    require(path.name=='plan.json','exact build plan filename required')
    expected,payloads=recipe(work)
    require(set(plan)==set(expected)|{'PreparedUTC'} and
            {k:v for k,v in plan.items() if k!='PreparedUTC'}==expected,'raw build plan differs from complete recipe')
    require({p for p in (work/'frozen-inputs').rglob('*') if p.is_file()}==
            {p for p in payloads if p.is_relative_to(work/'frozen-inputs')},'compiled source inventory differs')
    for p,data in payloads.items():require(p.is_file() and p.read_bytes()==data,'prepared raw source/Tcl/FDC differs: '+str(p))
    for p,h in plan['InputSHA256'].items():require(sha(p)==h,'raw build input drift: '+p)
    return plan


def diagnostics(work):
    return [p.relative_to(work).as_posix()+': '+line.strip() for p in sorted(Path(work).rglob('*.log'))
        for line in p.read_text(encoding='gb18030',errors='replace').splitlines()
        if re.match(r'\s*(C:|E:|F:|CRITICAL:|ERROR:|FATAL:|Traceback)',line)]


def events(text):return [list(x) for x in re.findall(r'^Process "([^"]+)" (started|done)\.',text,re.M)]


def execute(path):
    path=Path(path).absolute();plan=validate(path);work=path.parent
    require(os.name=='nt' and not (work/'execution-start.json').exists(),'fresh Windows native build required')
    watched={**plan['InputSHA256'],**plan['PreparedSHA256'],str(path):sha(path)}
    result={'Schema':'hdmi-camera-raw-build-execution-v1','Target':TARGET,'PlanSHA256':sha(path),
        'StartedUTC':utc(),'Command':plan['Command'],'HardwareAccessed':False,'BitstreamRequested':False,
        'EDAExecuted':False,'TimedOut':False,'StoppedForUnexpectedStage':False,'ExitCode':None}
    write(work/'execution-start.json',result);process=None;start=time.monotonic()
    expected=[[stage,event] for stage in STAGES for event in ('started','done')]
    try:
        with (work/'stdout.log').open('xb') as out,(work/'stderr.log').open('xb') as err:
            process=subprocess.Popen(plan['Command'],cwd=work,stdout=out,stderr=err,shell=False,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));result.update(EDAExecuted=True,OwnedPID=process.pid)
            while process.poll() is None:
                left=plan['MaximumSeconds']-(time.monotonic()-start)
                if left<=0:result['TimedOut']=True;break
                try:process.wait(timeout=min(3,left))
                except subprocess.TimeoutExpired:pass
                current=events((work/'stdout.log').read_text(encoding='gb18030',errors='replace'))
                if current!=expected[:len(current)]:result['StoppedForUnexpectedStage']=True;break
    except BaseException as error:result['Error']=type(error).__name__+': '+str(error)
    finally:
        if process is not None and process.poll() is None:
            result['Cleanup']=cleanup.stop_owned_tree(process,work,'bounded raw diagnostic build')
        else:result['Cleanup']={'Complete':True,'ParentExited':True}
        if process is not None:result['ExitCode']=process.poll()
        adf=work/'place_route'/(TARGET+'_pnr.adf')
        result.update(ElapsedSeconds=round(time.monotonic()-start,3),FinishedUTC=utc(),
            InputDrift=[p for p,h in watched.items() if not Path(p).is_file() or sha(p)!=h],
            ActualEvents=events((work/'stdout.log').read_text(encoding='gb18030',errors='replace')),
            Diagnostics=diagnostics(work),ADF=str(adf),ADFSHA256=sha(adf) if adf.is_file() else None,
            InitialSTAADFBeforeAfterVerified=False,
            LogSHA256={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*.log')})
        result['NativeErrors']=[row for row in result['Diagnostics'] if not re.search(r': C: Sdm-3003: ',row)]
        result['BuildCompleted']=(result['ExitCode']==0 and not result['TimedOut'] and not result.get('Error')
            and not result['StoppedForUnexpectedStage'] and result['ActualEvents']==expected
            and result['InputDrift']==[] and adf.is_file() and result['NativeErrors']==[] and result['Cleanup']['Complete'])
        result['DiagnosticsCleared']=result['Diagnostics']==[]
        result['TimingAccepted']=False
        write(work/'execution-result.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare',type=Path);mode.add_argument('--validate',type=Path);mode.add_argument('--execute',type=Path)
    a=p.parse_args()
    if a.prepare:v=prepare(a.prepare);print(json.dumps({'Prepared':True,'Plan':str(Path(v['WorkDirectory'])/'plan.json')}));return 0
    if a.validate:validate(a.validate);print('{"Validated":true,"HardwareAccessed":false}');return 0
    v=execute(a.execute);print(json.dumps({k:v.get(k) for k in ('BuildCompleted','ExitCode','ElapsedSeconds','Diagnostics','Error')}));return 0 if v['BuildCompleted'] else 1


if __name__=='__main__':raise SystemExit(main())
