"""Exercise isolated DVP/System integration with a modeled DDR UI.

Real byte capture, ownership, nonlinear processing, CRC, FIFO and scan execute.
Small geometry, modeled sensor/DDR/clock stimuli are not physical input proof.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile
import time

import run_processed_output_sim as baseline
from run_gamma_pipeline_d5_sim import tool
from simulation_tools import prepare_compile_sources, resolve_vivado_bin, verify_compile_sources

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'build/camera-vga-integration'
TEMP_BASE = Path(tempfile.gettempdir()).resolve()/'codex-camera-vga-integration'
REMOVED = {
    'rtl/experimental/hdmi1080_capture_cdc.v', 'rtl/experimental/hdmi1080_input_dma.v',
    'rtl/experimental/hdmi1080_input_write_link.v', 'rtl/experimental/hdmi1080_video_system_cdc_reset.v',
    'rtl/experimental/processed_output_pattern.v', 'board/processed_output_top.v',
    'tests/tb_processed_output.sv',
}
ADDED = (
    'rtl/experimental/dvp_rgb565_capture_cdc.v', 'rtl/experimental/camera_vga_input_dma.v',
    'rtl/experimental/camera_vga_input_write_link.v', 'rtl/experimental/camera_vga_video_system.v',
    'tests/tb_camera_vga_system.sv',
)
COMPILE = tuple(p for p in baseline.COMPILE if p not in REMOVED)+ADDED
HEADERS = baseline.HEADERS
HELPERS = tuple(dict.fromkeys((*baseline.HELPERS, 'tools/run_camera_vga_system_sim.py')))

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def run(workdir, maximum_seconds):
    supplied=Path(workdir).absolute()
    work=supplied.resolve()
    if supplied!=work or work.parent not in (BASE.resolve(),TEMP_BASE) or work.exists():
        raise ValueError('fresh canonical direct child of build/camera-vga-integration or '
                         'the local temporary codex-camera-vga-integration directory required')
    if not 30<=maximum_seconds<=600:
        raise ValueError('whole native deadline must be 30..600 seconds')
    work.mkdir(parents=True,exist_ok=False)
    source_hashes={name:sha(ROOT/name) for name in (*COMPILE,*HEADERS,*HELPERS)}
    report={'Schema':'camera-vga-dvp-system-simulation-v1','Passed':False,
            'StartedUTC':datetime.now(timezone.utc).isoformat(),'SourceSHA256':source_hashes,
            'Commands':[],'HardwareAccessed':False,'PhysicalIPExecuted':False,
            'PhysicalCameraValidated':False,'SourceGeometry':[32,16],'OutputActiveArea':[64,32],
            'CameraPolarity':{'VSYNC_ACTIVE_HIGH':0,'HREF_ACTIVE_HIGH':0,'HIGH_BYTE_FIRST':0},
            'RealDVPCaptureExecuted':True,'RealOutputFIFOExecuted':True,
            'ProductionBankAndMapperExecuted':True,'RTLResultUsedForGolden':False,
            'Limits':'Small DVP byte-level simulation with nonlinear synthetic geometry and modeled DDR UI. '
                     'Checks one malformed first row, valid recovery, source/result bank reuse, full output DE '
                     'and centered picture/black borders. No SCCB, sensor electrical timing, real camera data, '
                     'native VGA throughput, independent reset/clock-stop or board top startup claim.'}
    fixture_hashes={}
    started=time.monotonic();deadline=started+maximum_seconds
    try:
        # Existing independent scalar/vector Brown and pixel oracle, not RTL output.
        expected,model=baseline.fixtures(work)
        if model['IntegerConfig']!=[3968,1920,3968,1920,4096,3686,67108864,74573496,
                                   0x51eb8,-0xf5c3,0x20c5,0x1062,-0xb78]:
            raise ValueError('testbench nonlinear model no longer matches independent oracle')
        report['Model']=model
        fixture_hashes={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()}
        report['FixtureSHA256']=fixture_hashes
        compiled,relocated=prepare_compile_sources(ROOT,COMPILE,HEADERS,work)
        report['CompileBindings']=relocated
        bin_dir=resolve_vivado_bin(ROOT.parent)
        for executable,argv,stage in (
            ('xvlog.bat',['--sv',*map(str,compiled)],'compile'),
            ('xelab.bat',['tb_camera_vga_system','-s','camera_vga_system','--timescale','1ps/1ps'],'elaborate'),
            ('xsim.bat',['camera_vga_system','-runall','-log','simulation.log'],'simulate')):
            item={'Stage':stage,'NativeArgv':[str(bin_dir/executable),*argv],'ReturnCode':None}
            report['Commands'].append(item)
            tool(bin_dir,executable,argv,work,deadline,stage)
            item['ReturnCode']=0
        log=(work/'simulation.log').read_text(encoding='utf-8',errors='replace')
        if 'PASS camera VGA system:' not in log or '$finish called' not in log or re.search(r'(?im)^\s*(?:fatal|error):',log):
            raise ValueError('complete camera system native pass marker missing')
        summary=json.loads((work/'summary.json').read_text(encoding='ascii'))
        exact={'passed':True,'malformed_frames_dropped':1,'full_output_de_verified':True,
               'centered_picture_verified':True,'directed_final_drain':True}
        if any(type(summary.get(k)) is not type(v) or summary[k]!=v for k,v in exact.items()):
            raise ValueError('required malformed/recovery/window/drain coverage missing')
        if summary['frames_committed']!=summary['frames_processed'] or summary['unique_frames_scanned']<4:
            raise ValueError('complete frame progress missing')
        if any(summary.get(k,0)<=0 for k in ('repeat_scans','source_bank_reuses','result_bank_reuses','black_border_pixels')):
            raise ValueError('bank reuse/repeat/border coverage missing')
        with (work/'scanned-pixels.csv').open(encoding='ascii',newline='') as stream:
            rows=list(csv.DictReader(stream))
        if len(rows)!=summary['scanned_pixels'] or len(rows)%512:
            raise ValueError('incomplete actual scan dump')
        for i,row in enumerate(rows):
            if int(row['pixel'])!=i%512 or int(row['rgb565'],16)!=int(expected.ravel()[i%512]):
                raise ValueError('actual scanned RGB differs from independent CPU oracle')
        verify_compile_sources(ROOT,COMPILE,HEADERS,work,relocated)
        report.update(Passed=True,Summary=summary,ActualScanPixelsCompared=len(rows))
    except (Exception,KeyboardInterrupt) as error:
        report['Error']=type(error).__name__+': '+str(error)
    finally:
        report['SourceSHA256After']={n:sha(ROOT/n) for n in source_hashes}
        report['FixtureSHA256After']={n:sha(work/n) for n in fixture_hashes}
        if report['SourceSHA256After']!=source_hashes or report['FixtureSHA256After']!=fixture_hashes:
            report.update(Passed=False,SourceOrFixtureDrift=True)
        report['ElapsedSeconds']=round(time.monotonic()-started,3)
        report['LogSHA256']={p.name:sha(p) for p in work.glob('*.log')}
        report['ResultSHA256']={p.name:sha(p) for p in work.iterdir() if p.name in ('summary.json','events.csv','scanned-pixels.csv')}
        (work/'camera-vga-system-simulation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'Passed':report['Passed'],'Error':report.get('Error'),'Report':str(work/'camera-vga-system-simulation.json')}))
    return 0 if report['Passed'] else 1

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir',type=Path,required=True)
    parser.add_argument('--maximum-seconds',type=int,default=240)
    args=parser.parse_args()
    return run(args.workdir,args.maximum_seconds)

if __name__=='__main__':
    raise SystemExit(main())
