from pathlib import Path
import subprocess,json,hashlib,time,sys
work=Path('D:/fpga-stable/scheduler')/(sys.argv[sys.argv.index('--run-dir')+1] if '--run-dir' in sys.argv else ('system-three' if '--third' in sys.argv else 'system-small')); viv=Path('D:/Vicado/Vivado/2017.4/bin')
assert not (work/'verification.json').exists(),'Completed verification is immutable; choose --run-dir with a new directory'
sources=(work/'compile-paths.txt').read_text().splitlines()
bindings=json.loads((work/'compile-sources.json').read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def verify():
 for item in bindings['sources']:assert sha(item['path'])==item['sha256'],item['path']
 assert sha(work/'tb_board1080_system.sv')==bindings['bench_sha256']
verify()
commands=[('compile',[viv/'xvlog.bat','--sv','-i','D:/fpga-stable/build/stable-a/native/b4/rtl',*sources,work/'tb_board1080_system.sv']),('elaborate',[viv/'xelab.bat','tb_board1080_system','-s','systemsmall']),('simulate',[viv/'xsim.bat','systemsmall','-runall'])]
for stage,cmd in commands:
 start=time.monotonic();r=subprocess.run([str(x) for x in cmd],cwd=work,capture_output=True,text=True)
 log=r.stdout+r.stderr;(work/(stage+'.log')).write_text(log)
 print(stage,r.returncode,round(time.monotonic()-start,2),log[-4000:],flush=True)
 assert r.returncode==0 and 'Fatal:' not in log and 'ERROR:' not in log,stage
 if stage=='simulate':assert 'PASS board1080 system:' in log
verify()
report={'passed':True,'hardware_accessed':False,'native_1080p_fps_proven':False,'engine_stub':False,'ddr_ui_model':True,'width':32,'height':16,'source_bank_mask':7 if '--third' in sys.argv else 3,'rtl_sources_unchanged':True,'bench_unchanged':True,'source_binding_sha256':sha(work/'compile-sources.json')}
report['evidence_sha256']={p.name:sha(p) for p in work.iterdir() if p.suffix in ('.mem','.vh','.csv') or p.name in ('compile.log','elaborate.log','simulate.log','summary.json','tb_board1080_system.sv')}
(work/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
