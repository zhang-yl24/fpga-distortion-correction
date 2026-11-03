"""Verify direct DDR fill against independent pixel, metadata and protocol oracles."""
from pathlib import Path
import argparse, hashlib, json, re, subprocess, time

PACKAGE = Path(__file__).resolve().parents[1]

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--vivado-bin',type=Path,default=Path('D:/Vicado/Vivado/2017.4/bin'))
    parser.add_argument('--predecode',type=int,choices=(0,1),default=1)
    parser.add_argument('--index-bits',type=int,choices=(7,9,10),default=7)
    parser.add_argument('--row-padded-index',action='store_true')
    args=parser.parse_args()
    work=args.work.resolve();work.mkdir(parents=True,exist_ok=False)
    sources=[PACKAGE/'rtl/ddr_neighbour_cache_scatter4_rowpipe.v',PACKAGE/'tests/cache_direct64.sv']
    source_hashes={str(p.relative_to(PACKAGE)):digest(p) for p in sources}
    report={'passed':False,'hardware_accessed':False,'predecode':args.predecode,'index_bits':args.index_bits,'row_padded_index':args.row_padded_index,'source_sha256':source_hashes,'commands':[]}
    defines=(['-d','CACHE_PREDECODE_OFF'] if not args.predecode else [])+(['-d',f'CACHE_INDEX{args.index_bits}'] if args.index_bits!=7 else [])+(['-d','CACHE_ROW_PADDED'] if args.row_padded_index else [])
    commands=[['xvlog.bat','--sv',*defines,*[str(p) for p in sources]],['xelab.bat','tb_rowpipe_cache','-s','cache_direct64'],['xsim.bat','cache_direct64','-runall']]
    try:
        for command in commands:
            argv=[str(args.vivado_bin/command[0]),*command[1:]]
            start=time.monotonic()
            proc=subprocess.run(argv,cwd=work,capture_output=True,text=True,errors='replace',timeout=300)
            output=proc.stdout+proc.stderr
            log=work/(command[0]+'.log');log.write_text(output,encoding='utf-8')
            report['commands'].append({'argv':argv,'returncode':proc.returncode,'seconds':time.monotonic()-start,'log_sha256':digest(log)})
            if proc.returncode or re.search(r'(?im)^\s*(fatal|error)(?:\s|:|\[)',output):
                raise RuntimeError(command[0]+': '+output[-4500:])
        if 'PASS DIRECT64 candidate unit:' not in output:
            raise RuntimeError('Required completion marker missing')
        assert source_hashes=={str(p.relative_to(PACKAGE)):digest(p) for p in sources}
        report['passed']=True
        report['pass_lines']=[line for line in output.splitlines() if line.startswith(('PASS','DIRECT64 coverage','DIRECT64 strengthened'))]
        report['summaries']={p.name:json.loads(p.read_text()) for p in work.glob('cache-direct64-*-summary.json')}
    except Exception as exc:
        report['error']=str(exc)
        raise
    finally:
        (work/'cache-direct64-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
