"""Compare registered-return mode to default timing with an explicit lane bundle."""
from pathlib import Path
import argparse,hashlib,json,subprocess
PACKAGE=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--vivado-bin',type=Path,default=Path('D:/Vicado/Vivado/2017.4/bin'))
    args=parser.parse_args();work=args.work.resolve();work.mkdir(parents=True,exist_ok=False)
    files=[PACKAGE/'rtl/ddr_neighbour_cache_scatter4_rowpipe.v',PACKAGE/'tests/cache_registered_return.sv']
    hashes={}
    for p in files:
        data=p.read_bytes();(work/p.name).write_bytes(data);hashes[str(p.relative_to(PACKAGE))]=hashlib.sha256(data).hexdigest()
    report={'passed':False,'source_sha256':hashes,'commands':[],
            'scope':'Explicit whole-bundle registered return; digital exact-cycle and independent pixel/protocol checks. No native timing or board claim.'}
    commands=[['xvlog','--sv',*[p.name for p in files]],['xelab','tb_cache_registered_return','-mt','2','-s','registered_return'],['xsim','registered_return','-runall']]
    try:
        for name,*arguments in commands:
            argv=[str(args.vivado_bin/(name+'.bat')),*arguments]
            result=subprocess.run(argv,cwd=work,capture_output=True,text=True,timeout=300)
            output=result.stdout+result.stderr;(work/(name+'.log')).write_text(output,encoding='utf-8')
            passed=result.returncode==0 and 'Fatal:' not in output and 'ERROR:' not in output
            if name=='xsim':passed&='PASS REGISTERED_RETURN exact-cycle' in output
            report['commands'].append({'command':argv,'returncode':result.returncode,'passed':passed})
            if not passed:raise RuntimeError(name+' failed: '+output[-3000:])
        report['metrics']=[line for line in output.splitlines() if line.startswith(('METRIC','PASS'))]
        report['passed']=True
    finally:
        (work/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
