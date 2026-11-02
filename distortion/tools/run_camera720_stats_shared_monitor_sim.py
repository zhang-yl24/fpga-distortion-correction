"""Actual full-size frontend regression with shared vendor-delayed controls."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import time

import run_camera720_stats_shared_delay_sim as delay
from run_gamma_pipeline_d5_sim import tool
from simulation_tools import resolve_vivado_bin

ROOT,WORK,TARGET=delay.ROOT,delay.WORK,delay.TARGET
need,sha=delay.need,delay.sha
SOURCES=('rtl/experimental/raw_camera_control_input_delay.v','rtl/reg16_i2c.v',
 'rtl/experimental/ov5640_current720_init.v','rtl/experimental/ov5640_current720_frontend.v',
 'rtl/experimental/dvp_mode_admission_monitor.v','tests/tb_camera720_stats_shared_monitor.sv')
HEADERS=('board/ov5640_rgb565_720_commands.vh','board/ov5640_rgb565_720_sequence.json')
HELPERS=('tools/run_camera720_stats_shared_monitor_sim.py',*delay.HELPERS)
CASES=(('pclk42_good',11905,False,[]),('pclk47_25_good',10582,False,['pclk_upper']),
       ('pclk42_bad_line',11905,True,['bad_line']),('pclk47_25_bad_line',10582,True,['pclk_upper','bad_line']))
GOOD_MARKERS=('PASS frontend configured remains disarmed before live geometry',
 'PASS frontend one complete good frame remains disarmed',
 'PASS frontend full2560x720 lines and PCLK-domain edge accounting; two fresh frames',
 'PASS frontend resumed PCLK cannot clear sticky failure',
 'PASS CURRENT720 frontend: two complete full-size good frames required, diagnostics and sticky clock-stop failure; synthetic only, no hardware acceptance.')
BAD_MARKER='PASS CURRENT720 frontend malformed line blocks admission despite configured registers'
REPORT='shared-monitor-simulation.json'


def observations(log,summary,half,bad):
    need(not re.search(r'(?im)^\s*(?:fatal|error):',log),'monitor simulator fatal/error')
    need(summary.get('Passed') is True and summary.get('PCLKHalfPeriodPS')==half
         and summary.get('BadLineCase')==int(bad) and summary.get('Configured')==1
         and summary.get('RawAuthorize')==0,'incomplete actual monitor result or wrong case')
    if bad:
        need(BAD_MARKER in log and summary.get('GoodFrames')==0 and summary.get('Fault')==0x12,
             'malformed first line was not rejected')
    else:
        need(all(s in log for s in GOOD_MARKERS) and summary.get('GoodFrames')==2
             and summary.get('BadFrames')==0 and summary.get('LastLines')==720
             and summary.get('LastBytes')==2560 and summary.get('Fault')==0xc0,
             'complete two-frame qualification and sticky PCLK halt proof required')
    return summary


def run(work,top,execute=False):
    work=Path(work).absolute();top=Path(top).absolute()
    need(work==work.resolve() and work.parent==WORK and not work.exists(),'fresh direct work directory required')
    need(top==top.resolve() and top.is_relative_to(WORK) and top.is_file(),'actual generated C top required')
    need(sha(ROOT/SOURCES[0])==delay.CONTROL_SHA,'control delay RTL differs')
    wiring=delay.top_wiring(top)
    models=[delay.VENDOR/n for n in delay.MODELS]
    inputs=models+[ROOT/n for n in (*SOURCES,*HEADERS,*HELPERS)]+[top]
    watched={str(p.resolve()):sha(p) for p in inputs}
    sequence=json.loads((ROOT/HEADERS[1]).read_text())
    need((sequence['NominalPCLKModelHz'],sequence['UpperPCLKModelHzAt27MHz'])==(42000000,47250000),
         'retained register-model scenarios changed')
    binary=resolve_vivado_bin(ROOT.parent).resolve()
    need(all((binary/n).is_file() for n in ('xvlog.bat','xelab.bat','xsim.bat')),'simulation tools unavailable')
    value={'Schema':'camera720-stats-shared-control-monitor-simulation-v1','Target':TARGET,'Passed':False,
        'GeneratedTop':{'Path':str(top),'SHA256':sha(top)},'InputSHA256':watched,'TopWiring':wiring,
        'MaximumSeconds':600,'MonitorSamplePhaseShiftPS':1500,'MonitorAfterControlDelay':True,
        'RawMonitorPathPreserved':False,'Geometry':[2560,720],'PCLKModelHz':[42000000,47250000],
        'SimulationExecuted':False,'Cases':[],'PDSAccessed':False,'HardwareAccessed':False,
        'ExternalACTimingAccepted':False,'HardwareReleaseAllowed':False,
        'Limits':'Actual vendor nominal delay models and unchanged real I2C/frontend/monitor with a synthetic sensor register slave. Two full 2560-byte x720-line frames plus bad-line and stopped-clock cases at retained 42/47.25MHz register-model scenarios. This is not measured PCLK/FPS, pixel/DDR transport, physical AC or routed PVT proof. Initializer wait/reset timings and monitor timeout intervals are accelerated explicitly in the testbench.'}
    if not execute:return value
    work.mkdir();start=time.monotonic();deadline=start+600
    value.update(SimulationExecuted=True,StartedUTC=datetime.now(timezone.utc).isoformat())
    try:
        tool(binary,'xvlog.bat',['--sv','-i',str(ROOT),*map(str,models),*[str(ROOT/n) for n in SOURCES]],work,deadline,'compile')
        tool(binary,'xelab.bat',['tb_camera720_stats_shared_monitor','-s','shared_monitor_tb'],work,deadline,'elaborate')
        for name,half,bad,args in CASES:
            argv=['shared_monitor_tb','-runall','-log',name+'.log']
            for arg in args:argv.extend(['-testplusarg',arg])
            tool(binary,'xsim.bat',argv,work,deadline,'simulate-'+name)
            log=(work/(name+'.log')).read_text(encoding='utf-8',errors='replace')
            raw=work/'monitor-summary.json';summary=json.loads(raw.read_text())
            observations(log,summary,half,bad)
            saved=work/(name+'-summary.json');need(not saved.exists(),'case artifact reused');raw.rename(saved)
            value['Cases'].append({'Name':name,'Passed':True,'Summary':summary,'SummaryFile':saved.name,'Log':name+'.log'})
        need(len(value['Cases'])==4,'all four actual cases required');value['Passed']=True
    except (Exception,KeyboardInterrupt) as error:value['Error']=type(error).__name__+': '+str(error)
    finally:
        value['InputDrift']=[p for p,h in watched.items() if sha(p)!=h]
        value['Passed']=value['Passed'] and not value['InputDrift']
        value['ElapsedSeconds']=round(time.monotonic()-start,3)
        value['EvidenceSHA256']={p.name:sha(p) for p in work.iterdir() if p.is_file() and p.suffix in ('.log','.json')}
        (work/REPORT).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
    return value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work-dir',type=Path,required=True)
    p.add_argument('--top',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    v=run(a.work_dir,a.top,a.execute)
    print(json.dumps({k:v[k] for k in ('Passed','SimulationExecuted','ElapsedSeconds','InputDrift','Error') if k in v}))
    return 0 if not a.execute or v['Passed'] else 1


if __name__=='__main__':raise SystemExit(main())
