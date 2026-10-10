"""Exercise saved-evidence gates with isolated fixtures; no hardware access."""
from pathlib import Path
from datetime import datetime,timedelta,timezone
import copy,importlib.util,json,os,shutil,subprocess
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('analyzer',root/'tools/analyze-rotation-telemetry.py')
analyzer=importlib.util.module_from_spec(spec);spec.loader.exec_module(analyzer)
start=datetime(2026,10,6,tzinfo=timezone.utc)
capture={'StartedUtc':start.isoformat(),'Samples':[]}
for i in range(12):
    fields={'CAM':0x5640,'E':0,'I':1,'H':1,'D':1,'V':1,'WF':i*12,'CF':i*10,'PF':i*60,
        'UF':0,'MF':0,'OW':0,'X':0,'CS':i+17,'RC':i+23,'RS':i+23,'PS':i+23,'CY':3807193,'HT':1213190,'MS':1200,
        'RA':0 if i<6 else 0x15555555,'AU':0,'TV':1,'TR':0xB00F,'TF':0,'TA':13500000,'AL':0x80}
    capture['Samples'].append({'ReceivedUtc':(start+timedelta(seconds=i)).isoformat(),'Line':' '.join(f'{k}={v:X}' for k,v in fields.items())})
result=analyzer.analyze(capture)
assert result['approx_rates_per_second']['CF']==10 and result['approx_rates_per_second']['PF']==60
negative_cases={'TV':'0','TF':'1','TA':f'{54000000:X}','TR':'F','UF':'1','CF':'0','CAM':'1234','AL':'A0'}
for key,bad in negative_cases.items():
    changed=copy.deepcopy(capture)
    last=changed['Samples'][-1]
    import re
    last['Line']=re.sub(r'\b'+key+r'=[0-9A-F]+\b',key+'='+bad,last['Line'])
    try:analyzer.analyze(changed)
    except ValueError:pass
    else:raise AssertionError(f'Acceptance failed to reject {key}')
work=root/'build/offline_guard_fixture';work.mkdir(parents=True,exist_ok=True)
target='corrected_fast';build=work/'build'/target;build.mkdir(parents=True,exist_ok=True)
manifest=json.loads((root/'build'/target/'validated-build.json').read_text(encoding='utf-8-sig'))
assert manifest['SourceSHA256']
files=set(manifest['SourceSHA256'])
files.update(('tools/build-pds.ps1','tools/program-heartbeat.ps1','board/'+target+'-sources.json'))
files.update(('board/bringup.v','board/bringup.fdc','board/build-bringup.tcl','rtl/camera_id_probe.v',
    'board/camera_init.v','board/camera_init.fdc','board/build-camera_init.tcl',
    'board/camera_capture.v','board/camera_capture.fdc','board/build-camera_capture.tcl','rtl/dvp_monitor.v'))
for rel in files:
    dst=work/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/rel,dst)
for rel in ('build.log','generate_bitstream/'+target+'.sbit','report_timing/'+target+'.rtr','place_route/'+target+'_prr.prt'):
    dst=build/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/'build'/target/rel,dst)
db=build/'place_route'/ (target+'_pnr.adf');db.write_bytes(b'ISOLATED GUARD FIXTURE; NOT A ROUTED DB')
mtime=(root/'build'/target/'place_route'/(target+'_pnr.adf')).stat().st_mtime;os.utime(db,(mtime,mtime))
manifest['Bitstream']=str(build/'generate_bitstream'/(target+'.sbit'))
manifest['TimingReport']=str(build/'report_timing'/(target+'.rtr'))
(build/'validated-build.json').write_text(json.dumps(manifest),encoding='utf-8')
cmd=['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(work/'tools/program-heartbeat.ps1'),'-Target',target,'-ValidateOnly']
task_env=os.environ.copy()
# The parent shell can be PowerShell7; let Windows PowerShell5 restore its
# own standard module search path instead of inheriting incompatible modules.
for key in list(task_env):
    if key.upper()=='PSMODULEPATH':task_env.pop(key)
def run():return subprocess.run(cmd,capture_output=True,text=True,env=task_env)
ok=run();assert ok.returncode==0,ok.stdout+ok.stderr
assert '"HardwareAccessed":  false' in ok.stdout
guard_cases=[('source',work/'board'/ (target+'.v')),('bitstream',Path(manifest['Bitstream'])),('timing',Path(manifest['TimingReport'])),('pins',work/'board'/(target+'-pins.json'))]
for name,path in guard_cases:
    original=path.read_bytes();stat=path.stat()
    try:
        path.write_bytes(original+b'\nTAMPERED FIXTURE');os.utime(path,(stat.st_atime,stat.st_mtime))
        rejected=run();assert rejected.returncode!=0,(name,rejected.stdout)
    finally:path.write_bytes(original);os.utime(path,(stat.st_atime,stat.st_mtime))
assert run().returncode==0
out={'passed':True,'hardware_accessed':False,'synthetic_uart_fixture':True,'uart_negative_cases':list(negative_cases),
    'guard_tamper_cases':[p[0] for p in guard_cases],'original_project_files_modified':False,'fixture':str(work)}
(root/'results/offline-acceptance-gates-20261006.json').write_text(json.dumps(out,indent=2)+'\n')
print('PASS isolated acceptance gates: valid serial fixture, 8 invalid/stale/fault/reset/alarm cases, and preserved-timestamp source/bit/timing/pin tampering; no hardware accessed.')
