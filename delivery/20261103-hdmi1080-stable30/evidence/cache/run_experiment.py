"""Run four isolated cache cases, including two cycle-exact differential cases."""
from pathlib import Path
import argparse, hashlib, json, os, re, subprocess, time

ROOT=Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--vivado-bin',type=Path,default=Path('D:/Vicado/Vivado/2017.4/bin'))
    parser.add_argument('--workdir',type=Path,required=True)
    args=parser.parse_args()
    work=args.workdir.resolve();work.mkdir(parents=True,exist_ok=False)
    temporary=work/'temp';temporary.mkdir()
    env=dict(os.environ,TEMP=str(temporary),TMP=str(temporary))
    inputs=[p for f in ('sources','tests') for p in (ROOT/f).iterdir()]
    hashes={str(p.relative_to(ROOT)):sha(p) for p in inputs}
    report=dict(passed=False,hardware_accessed=False,eda_implementation_accessed=False,
                source_sha256=hashes,cases=[])
    try:
        for variant in ('current','experiment'):
            for stem in ('tb_cache_directed','tb_cache_stream'):
                stage=work/(variant+'-'+stem);stage.mkdir()
                test=ROOT/'tests'/(stem+('_lockstep' if variant=='experiment' else '')+'.sv')
                files=[ROOT/'sources'/(variant+'.v'),test]
                if variant=='experiment':files.insert(1,ROOT/'sources/reference.v')
                commands=[['xvlog.bat','--sv','-d','PACKED32',*[str(p) for p in files]],
                          ['xelab.bat',stem,'-s','cache_test'],['xsim.bat','cache_test','-runall']]
                case=dict(variant=variant,bench=stem,passed=False,commands=[])
                report['cases'].append(case)
                for command in commands:
                    argv=[str(args.vivado_bin/command[0]),*command[1:]]
                    start=time.monotonic()
                    proc=subprocess.run(argv,cwd=stage,env=env,capture_output=True,text=True,
                                        errors='replace',timeout=600)
                    output=proc.stdout+proc.stderr
                    log=stage/(command[0]+'.log');log.write_text(output,encoding='utf-8')
                    case['commands'].append(dict(argv=argv,returncode=proc.returncode,
                                                 seconds=time.monotonic()-start,log_sha256=sha(log)))
                    if proc.returncode or re.search(r'(?im)^\s*(?:fatal|error)(?:\s|:|\[)',output):
                        raise RuntimeError(f'{stage.name}/{command[0]} failed: {output[-4000:]}')
                marker='PASS SCATTER4 independent directed regression:' if stem.endswith('directed') else 'PASS CACHE STREAM'
                if marker not in output:
                    raise RuntimeError('Oracle completion marker missing: '+stage.name)
                if variant=='experiment' and 'LOCKSTEP cycles=' not in output:
                    raise RuntimeError('Differential monitor completion marker missing')
                case['pass_lines']=[l for l in output.splitlines() if l.startswith(('PASS','CACHE_METRICS','SCATTER4 coverage','SCATTER4 strengthened','LOCKSTEP'))]
                m=re.search(r'CACHE_METRICS cycles=(\d+) queries=(\d+) bursts=(\d+) scatter=(\d+) hits=(\d+) misses=(\d+)',output)
                if m:case['metrics']=dict(zip(('cycles','queries','bursts','scatter','hits','misses'),map(int,m.groups())))
                case['passed']=True
                print(stage.name,'PASS',flush=True)
        stream=[c for c in report['cases'] if 'metrics' in c]
        if len(stream)!=2 or stream[0]['metrics']!=stream[1]['metrics']:
            raise RuntimeError('Cycle/throughput metrics changed')
        if hashes!={str(p.relative_to(ROOT)):sha(p) for p in inputs}:
            raise RuntimeError('Staged sources changed during simulation')
        report['passed']=True
    except Exception as exc:
        report['error']=str(exc)
        raise
    finally:
        (work/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
