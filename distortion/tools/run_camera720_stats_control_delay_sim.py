"""Actual vendor-model 10-lane control/data timing simulation; no PDS/hardware."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

from run_gamma_pipeline_d5_sim import tool
from simulation_tools import resolve_vivado_bin

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'work/camera720-stats-delay'
TARGET='camera720_calibrated_stats_delay_top'
VENDOR=Path('D:/pango/PDS_2023.2/arch/vendor/pango/verilog/simulation')
MODELS=('GTP_INBUF.v','GTP_ZEROHOLDDELAY.v')
SOURCES=('rtl/experimental/raw_camera_input_delay.v','rtl/experimental/raw_camera_control_input_delay.v',
         'tests/tb_camera720_stats_control_delay.sv')
HELPERS=('tools/run_camera720_stats_control_delay_sim.py','tools/run_gamma_pipeline_d5_sim.py','tools/simulation_tools.py')
CONTROL_SHA='78c3b56145f6531b4fd8605b0ec2dc6a7d79466b9f3c5d48594448b1bb4f4fc9'
PASS='CAMERA720_STATS_CONTROL_DELAY_PASS lanes=10 tuples=1024 checks=3072 sampling=32 nominal_delay_ps=1500'
REPORT='control-data-delay-simulation.json'


def need(value,message):
    if not value:raise ValueError(message)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def top_wiring(top):
    text=Path(top).read_text(encoding='utf-8-sig')
    text=re.sub(r'/\*.*?\*/|//[^\n]*','',text,flags=re.S)
    need(re.findall(r'(?m)^module\s+(\w+)\b',text)==[TARGET],'exact new delay target required')
    def connections(instance):
        matches=re.findall(r'\b'+re.escape(instance)+r'\s*\((.*?)\);',text,re.S)
        need(len(matches)==1,'one exact instance required: '+instance)
        pins=re.findall(r'\.(\w+)\s*\(\s*([^()]*)\s*\)',matches[0])
        need(len({p for p,_ in pins})==len(pins),'duplicate instance connection')
        return {p:re.sub(r'\s+','',n) for p,n in pins}
    need(connections('camera_data_delay')=={'pad_data':'cam_data','capture_data':'delayed_cam_data'},'data delay wiring differs')
    need(connections('camera_control_delay')=={'pad_href':'cam_href','pad_vsync':'cam_vsync',
        'capture_href':'delayed_cam_href','capture_vsync':'delayed_cam_vsync'},'control delay wiring differs')
    video=connections('system');monitor=connections('camera_configuration')
    need(all(video.get(p)==v for p,v in {'cam_clk':'cam_pclk','cam_data':'delayed_cam_data',
        'cam_href':'delayed_cam_href','cam_vsync':'delayed_cam_vsync'}.items()),'capture does not use aligned ten delayed lanes/raw PCLK')
    need(all(monitor.get(p)==v for p,v in {'pclk':'cam_pclk','vsync_active':'!cam_vsync',
        'href_active':'!cam_href'}.items()),'frame admission monitor no longer uses original raw controls/clock')
    return {'CaptureDataLanes':8,'CaptureControlLanes':2,'CaptureClockUnchanged':True,
        'RawControlMonitorUnchanged':True,'MonitorHasPixelDataInput':False,
        'Observation':'Static actual generated-top connection check; functional simulation below instantiates both real delay wrappers.'}


def inspect_observations(work):
    with (work/'transitions.csv').open(encoding='ascii',newline='') as f:rows=list(csv.DictReader(f))
    need(len(rows)==1024,'complete 10-bit tuple coverage required')
    previous=0;rises=[0]*10;falls=[0]*10
    for index,row in enumerate(rows):
        need(set(row)=={'index','previous','driven','before1500ps','after1500ps','stable'},'transition observation fields differ')
        driven=index^0x2a5
        expected={'index':index,'previous':previous,'driven':driven,'before1500ps':previous,'after1500ps':driven,'stable':driven}
        actual={k:int(v,10 if k=='index' else 16) for k,v in row.items()}
        need(actual==expected,'actual lane delay/skew/tuple observation differs')
        for lane in range(10):
            rises[lane]+=int(not(previous>>lane&1) and driven>>lane&1)
            falls[lane]+=int(previous>>lane&1 and not(driven>>lane&1))
        previous=driven
    need(all(rises) and all(falls),'both polarities required on every lane')
    with (work/'sampling.csv').open(encoding='ascii',newline='') as f:rows=list(csv.DictReader(f))
    need(len(rows)==32,'all sampling phases required')
    offsets=[1,100,1000,1499,1501,2000,8000,15000]
    for index,row in enumerate(rows):
        need(set(row)=={'index','offset_ps','previous','driven','sampled_capture','sampled_raw_monitor'},'sampling fields differ')
        driven=(~previous)&1023;offset=offsets[index%8]
        expected={'index':index,'offset_ps':offset,'previous':previous,'driven':driven,
            'sampled_capture':previous if offset<1500 else driven,'sampled_raw_monitor':driven>>8}
        actual={k:int(v,10 if k in ('index','offset_ps') else 16) for k,v in row.items()}
        need(actual==expected,'sample boundary or raw control monitor observation differs')
        previous=driven
    return {'ObservedTuples':1024,'TupleChecks':3072,'SamplingChecks':32,'SamplingOffsetsPS':offsets,
        'LaneRisingTransitions':rises,'LaneFallingTransitions':falls,'RelativeControlDataDelayUnchangedInModel':True,
        'ExtraPixelClockCycleObserved':False,'RawControlMonitorUnchangedInModel':True}


def run(work,top,execute=False):
    work=Path(work).absolute();top=Path(top).absolute()
    need(work==work.resolve() and work.parent==WORK and not work.exists(),'fresh direct delay-candidate work directory required')
    need(top==top.resolve() and top.is_relative_to(WORK) and top.is_file(),'actual isolated generated top required')
    need(sha(ROOT/SOURCES[1])==CONTROL_SHA,'reviewed control delay RTL changed')
    wiring=top_wiring(top)
    paths=[VENDOR/n for n in MODELS]+[ROOT/n for n in SOURCES]
    watched={str(p.resolve()):sha(p) for p in paths+[ROOT/n for n in HELPERS]+[top]}
    binary=resolve_vivado_bin(ROOT.parent).resolve()
    stages=[('xvlog.bat',['--sv',*map(str,paths)],'compile'),
        ('xelab.bat',['tb_camera720_stats_control_delay','-s','camera720_stats_control_delay_tb','--timescale','1ps/1ps'],'elaborate'),
        ('xsim.bat',['camera720_stats_control_delay_tb','-runall','-log','simulation.log'],'simulate')]
    need(all((binary/n).is_file() for n,_,_ in stages),'simulation tools unavailable')
    record={'Schema':'camera720-stats-control-data-delay-simulation-v1','Target':TARGET,'Passed':False,
        'InputSHA256':watched,'GeneratedTop':{'Path':str(top),'SHA256':sha(top)},'TopWiring':wiring,
        'MaximumSeconds':120,'NominalDelayPS':1500,'Lanes':10,
        'Commands':[{'Stage':stage,'Argv':[str(binary/name),*args]} for name,args,stage in stages],
        'SimulationExecuted':False,'PDSAccessed':False,'HardwareAccessed':False,'ExternalACTimingAccepted':False,
        'Limits':'Actual vendor functional delay models only, nominal 1500ps. Tuple/edge/boundary checks do not prove routed PVT delay, external sensor AC, metastability or board operation.'}
    if not execute:return record
    work.mkdir(parents=True);started=time.monotonic();record['StartedUTC']=datetime.now(timezone.utc).isoformat()
    try:
        record['SimulationExecuted']=True
        for name,args,stage in stages:tool(binary,name,args,work,started+120,stage)
        log=(work/'simulation.log').read_text(encoding='utf-8',errors='replace')
        need([x.strip() for x in log.splitlines() if x.startswith('CAMERA720_STATS_CONTROL_DELAY_')]==[PASS], 'complete real model simulation marker missing')
        need(not re.search(r'(?im)^\s*(?:fatal|error):',log),'simulation fatal/error present')
        summary=json.loads((work/'summary.json').read_text())
        need(summary=={'Passed':True,'Lanes':10,'NominalDelayPS':1500,'AllTupleValues':1024,'Checks':3072,
            'SampleBoundaryChecks':32,'BothPolaritiesEveryLane':True},'incomplete simulation summary')
        record.update(Passed=True,Summary=summary,Observed=inspect_observations(work))
    except (Exception,KeyboardInterrupt) as error:record['Error']=type(error).__name__+': '+str(error)
    finally:
        record['InputDrift']=[p for p,h in watched.items() if sha(p)!=h]
        record['Passed']=record['Passed'] and not record['InputDrift']
        record['ElapsedSeconds']=round(time.monotonic()-started,3)
        record['EvidenceSHA256']={p.name:sha(p) for p in work.iterdir() if p.is_file() and p.suffix in ('.log','.csv','.json')}
        (work/REPORT).write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    return record


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work-dir',type=Path,required=True)
    p.add_argument('--top',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
    value=run(a.work_dir,a.top,a.execute)
    print(json.dumps({k:value[k] for k in ('Passed','SimulationExecuted','ElapsedSeconds','InputDrift','Error') if k in value}))
    return 0 if not a.execute or value['Passed'] else 1


if __name__=='__main__':raise SystemExit(main())
