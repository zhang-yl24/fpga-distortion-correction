"""Directed three-source DMA/link tests; uses actual RTL, no FPGA access."""
from pathlib import Path
import argparse, hashlib, json, subprocess, time

PACKAGE=Path(__file__).resolve().parents[1]

def run(args):
    work=args.work.resolve()
    if work.exists():raise ValueError('work directory must be new')
    work.mkdir(parents=True)
    native=args.source_root.resolve(); rtl=PACKAGE/'rtl'; tests=PACKAGE/'tests'
    configs={
        'dma':('tb_hdmi1080_input_dma',[native/'rtl/video_async_fifo.v',rtl/'hdmi1080_capture_cdc.v',rtl/'hdmi1080_input_dma.v',tests/'tb_dma_three.sv'],'PASS hdmi1080_input_dma directed'),
        'link':('tb_hdmi1080_input_write_link',[native/'rtl/video_async_fifo.v',rtl/'hdmi1080_capture_cdc.v',rtl/'hdmi1080_input_dma.v',rtl/'hdmi_camera_fisheye_input_link.v',native/'rtl/ddr_write_arbiter.v',tests/'tb_link_three.sv'],'PASS hdmi1080 input write link:'),
    }
    result={'passed':False,'hardware_accessed':False,'scope':'Directed small-frame DMA, descriptor queue and shared-write tests; not a full 1080p60 throughput claim.','cases':[]}
    for name,(top,files,marker) in configs.items():
        cwd=work/name;cwd.mkdir()
        commands=[['xvlog.bat','--sv',*map(str,files)],['xelab.bat',top,'--snapshot',name],['xsim.bat',name,'-runall']]
        for i,cmd in enumerate(commands):
            start=time.monotonic();p=subprocess.run([str(args.vivado_bin/cmd[0]),*cmd[1:]],cwd=cwd,capture_output=True,text=True)
            log=p.stdout+p.stderr;(cwd/f'{i}.log').write_text(log,encoding='utf-8')
            if p.returncode or 'Fatal:' in log or 'ERROR:' in log:raise RuntimeError(log[-6000:])
            if i==2 and marker not in log:raise RuntimeError('PASS marker missing: '+log[-3000:])
            print(name,i,'OK',round(time.monotonic()-start,2),flush=True)
        result['cases'].append({'name':name,'passed':True,'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}})
    result['passed']=True
    (work/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True)
    p.add_argument('--source-root',type=Path,default=PACKAGE.parents[1]/'distortion')
    p.add_argument('--vivado-bin',type=Path,required=True)
    a=p.parse_args();print(json.dumps(run(a),indent=2))
