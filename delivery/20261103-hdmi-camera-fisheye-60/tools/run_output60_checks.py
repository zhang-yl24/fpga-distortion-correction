"""Check full 1080p60 raster and scaled real-FIFO fault behavior with XSim."""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess,time
PACKAGE=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--work',type=Path,required=True);p.add_argument('--source-root',type=Path,default=PACKAGE.parents[1]/'distortion');p.add_argument('--vivado-bin',type=Path,default=Path('D:/Vicado/Vivado/2017.4/bin'));a=p.parse_args()
 work=a.work.resolve();work.mkdir(parents=True,exist_ok=False);tmp=work/'temp';tmp.mkdir()
 env=dict(os.environ,TEMP=str(tmp),TMP=str(tmp));report=dict(passed=False,hardware_accessed=False,physical_timing_verified=False,cases=[])
 try:
  for name,top,bench,marker in [('raster','tb_output60_raster','tb_output60_raster.sv','PASS OUTPUT60 RASTER'),('faults','tb_board1080_scan','tb_output60_faults.sv','PASS board1080 scan:'),('faults_tight','tb_board1080_scan','tb_output60_faults.sv','PASS board1080 scan:'),('positions','tb_output60_positions','tb_output60_positions.sv','PASS OUTPUT60 POSITIONS')]:
   cwd=work/name;cwd.mkdir();src=PACKAGE/'rtl/ddr_video_output_1080_board.v';crc=a.source_root/'rtl/video_crc32.vh';fifo=a.source_root/'rtl/video_async_fifo.v';test=PACKAGE/'tests'/bench
   source_files=[src,crc,fifo,test];sources={str(f):sha(f) for f in source_files}
   staged=cwd/'ddr_video_output_1080_board.v';text=src.read_text(encoding='utf-8-sig');text=re.sub(r'`include "[^"]*video_crc32.vh"','`include "'+crc.resolve().as_posix()+'"',text);staged.write_text(text,encoding='utf-8')
   files=[staged,fifo,test];case=dict(name=name,passed=False,source_sha256=sources,staged_source_sha256=sha(staged),commands=[]);report['cases'].append(case)
   for tool,args in [('xvlog.bat',['--sv',*(['--define','TIGHT_RASTER'] if name=='faults_tight' else []),*[str(f) for f in files]]),('xelab.bat',[top,'-s','scan_test']),('xsim.bat',['scan_test','-runall'])]:
    command=[str(a.vivado_bin/tool),*args];start=time.monotonic();r=subprocess.run(command,cwd=cwd,env=env,capture_output=True,text=True,errors='replace',timeout=240)
    text=r.stdout+r.stderr;log=cwd/(tool+'.log');log.write_text(text,encoding='utf-8');case['commands'].append(dict(argv=command,returncode=r.returncode,seconds=time.monotonic()-start,log_sha256=sha(log)))
    if r.returncode or re.search(r'(?im)^\s*(?:fatal|error)(?:\s|:|\[)',text):raise RuntimeError(text[-4000:])
   if marker not in text:raise RuntimeError('Expected PASS marker absent')
   if sources!={str(f):sha(f) for f in source_files}:raise RuntimeError('Source drift')
   case['pass_lines']=[s for s in text.splitlines() if s.startswith('PASS')];case['passed']=True;print(name,'PASS',flush=True)
  report['passed']=True
 finally:(work/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
