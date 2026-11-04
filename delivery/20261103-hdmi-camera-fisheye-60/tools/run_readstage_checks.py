"""Run registered-return and raw-ownership tests against the frozen arbiter."""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess,time
ROOT=Path(__file__).resolve().parents[1]
CASES=[('legacy','tb_ddr_read_arbiter','tb_legacy_registered.sv','PASS DDR read arbitration'),
       ('integration','tb_ddr_readstage_integration','tb_readstage_integration.sv','PASS READSTAGE INTEGRATION'),
       ('guard','tb_readstage_guard','tb_readstage_guard.sv','PASS READSTAGE GUARD checks=11'),
       ('system','tb_system_readstage_guard','tb_system_readstage_guard.sv','PASS SYSTEM READSTAGE'),
       ('completion','tb_system_completion_guard','tb_system_completion_guard.sv','PASS SYSTEM COMPLETION')]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--case',action='append',choices=[v[0] for v in CASES]);p.add_argument('--source-root',type=Path,default=ROOT.parents[1]/'distortion');p.add_argument('--work',type=Path,required=True);p.add_argument('--vivado-bin',type=Path,default=Path('D:/Vicado/Vivado/2017.4/bin'));a=p.parse_args()
 work=a.work.resolve();work.mkdir(parents=True,exist_ok=False);tmp=work/'temp';tmp.mkdir()
 env=dict(os.environ,TEMP=str(tmp),TMP=str(tmp));report=dict(passed=False,hardware_accessed=False,physical_implementation_accessed=False,cases=[])
 try:
  for name,top,bench,marker in CASES:
   if a.case and name not in a.case:continue
   stage=work/name;stage.mkdir();files=[ROOT/'rtl/ddr_read_return_register.v',a.source_root/'rtl/ddr_read_arbiter.v',ROOT/'tests'/bench]
   if name in ('system','completion'):
    files += [ROOT/'rtl'/v for v in ['hdmi_camera_fisheye_system_c.v','hdmi_camera_fisheye_bank.v','hdmi_camera_fisheye_input_link.v','hdmi1080_input_dma.v','hdmi1080_capture_cdc.v']]
    files += [a.source_root/'rtl'/v for v in ['ddr_video_reader.v','video_async_fifo.v','ddr_write_arbiter.v']]
    files += [ROOT/'tests/fisheye_scheduler_engine_stub.v',ROOT/'rtl/ddr_video_output_1080_board.v']
   sources={str(p):sha(p) for p in files};compile_files=[]
   for src in files:
    content=src.read_text(encoding='utf-8-sig')
    if '`include' in content:
     content=re.sub(r'`include "[^"]*video_crc32.vh"','`include "'+(a.source_root/'rtl/video_crc32.vh').resolve().as_posix()+'"',content)
     staged=stage/src.name;staged.write_text(content,encoding='utf-8');compile_files.append(staged)
     sources[str(a.source_root/'rtl/video_crc32.vh')]=sha(a.source_root/'rtl/video_crc32.vh')
    else:compile_files.append(src)
   case=dict(name=name,passed=False,source_sha256=sources,commands=[]);report['cases'].append(case)
   for tool,args in [('xvlog.bat',['--sv',*[str(p) for p in compile_files]]),('xelab.bat',[top,'-s','read_test']),('xsim.bat',['read_test','-runall'])]:
    command=[str(a.vivado_bin/tool),*args];start=time.monotonic();r=subprocess.run(command,cwd=stage,env=env,capture_output=True,text=True,errors='replace',timeout=180)
    text=r.stdout+r.stderr;log=stage/(tool+'.log');log.write_text(text,encoding='utf-8');case['commands'].append(dict(argv=command,returncode=r.returncode,seconds=time.monotonic()-start,log_sha256=sha(log)))
    if r.returncode or re.search(r'(?im)^\s*(?:fatal|error)(?:\s|:|\[)',text):raise RuntimeError(text[-4000:])
   if marker not in text:raise RuntimeError('Expected PASS marker absent')
   if sources!={p:sha(Path(p)) for p in sources}:raise RuntimeError('Source drift')
   case['pass_lines']=[s for s in text.splitlines() if s.startswith('PASS')];case['passed']=True;print(name,'PASS',flush=True)
  report['passed']=True
 finally:(work/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
