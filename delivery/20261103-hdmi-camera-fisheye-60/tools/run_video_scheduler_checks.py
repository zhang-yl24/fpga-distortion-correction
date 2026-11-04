"""Compare C two-source scheduling with the three-source overlay using a controlled engine latency."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
PACKAGE=Path(__file__).resolve().parents[1]

def run(args):
    work=args.work.resolve()
    if work.exists():raise ValueError('work directory must be new')
    work.mkdir(parents=True);results=[];sources={}
    def invoke(command,cwd,name):
        p=subprocess.run(list(map(str,command)),cwd=cwd,capture_output=True,text=True)
        log=p.stdout+p.stderr;(cwd/(name+'.log')).write_text(log,encoding='utf-8')
        if p.returncode or 'Fatal:' in log or 'ERROR:' in log:raise RuntimeError(log[-6000:])
        return log
    for banks in (2,3):
        cwd=work/str(banks);cwd.mkdir()
        bank=(args.source_root/'rtl/experimental/hdmi_camera_fisheye_bank.v') if banks==2 else PACKAGE/'rtl/hdmi_camera_fisheye_bank.v'
        files=[bank,PACKAGE/'tests/fisheye_scheduler_engine_stub.v',PACKAGE/'tests/tb_video_scheduler.sv']
        sources.update({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files})
        cmd=[args.vivado_bin/'xvlog.bat','--sv',*files]
        if banks==3:cmd+=['--define','THREE']
        invoke(cmd,cwd,'compile');invoke([args.vivado_bin/'xelab.bat','tb_scheduler','--snapshot','schedule'],cwd,'elaborate')
        for process in (1800,2500,3100):
            for phase in (0,700,1400,2100,2800):
                name=f'p{process}-phase{phase}';arg=cwd/(name+'.args')
                arg.write_text(f'--runall\n--testplusarg PHASE={phase}\n--testplusarg PROCESS={process}\n')
                log=invoke([args.vivado_bin/'xsim.bat','schedule','-f',arg],cwd,name)
                found=re.search(r'SCHED_RESULT (.*)',log)
                if not found:raise RuntimeError('scheduler result missing')
                row={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',found[1])}
                if banks==3 and (row['shown']!=240 or row['no_bank']!=0):raise RuntimeError('three-source scheduling missed frame: '+str(row))
                results.append(row);print(row,flush=True)
    receipt={'passed':True,'hardware_accessed':False,'sources':sources,'scope':'Controlled latency and scaled frame-period scheduling. Does not prove 1080p60 engine/DDR throughput.','cases':results}
    (work/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--work',type=Path,required=True)
    p.add_argument('--source-root',type=Path,default=PACKAGE.parents[1]/'distortion');p.add_argument('--vivado-bin',type=Path,required=True)
    print(json.dumps(run(p.parse_args()),indent=2))
