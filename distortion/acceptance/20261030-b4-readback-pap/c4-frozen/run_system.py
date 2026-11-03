#!/usr/bin/env python3
from pathlib import Path
import argparse,json,hashlib,shutil,struct,subprocess,zlib,sys
sys.dont_write_bytecode=True
from check_telemetry import verify,rgb,signature
R=Path(__file__).resolve().parent
def prepare_check():
 m=json.loads((R/'manifest.json').read_text())
 for e in m['files']:
  p=R/e['path'];assert p.stat().st_size==e['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==e['sha256'],e['path']
 vals=lambda n:[int(x,16) for x in (R/'vectors'/n).read_text().split()]
 src=vals('source0.mem');assert src==vals('source1.mem')==vals('expected0.mem') and len(src)==1024
 corrected=vals('expected1.mem');assert len(corrected)==1024
 assert sum(a!=b for a,b in zip(src,corrected))==926
 for n,data in [('sourcecrc0.mem',src),('sourcecrc1.mem',src),('crc0.mem',src),('crc1.mem',corrected)]:
  assert zlib.crc32(struct.pack('<1024H',*data))==vals(n)[0]
 for f in (1,2,3):
  packet=signature(R,f,f+10);assert len(packet)==128
  assert zlib.crc32(packet[:120])==struct.unpack_from('<I',packet,120)[0]
 return {'input_hashes_checked':len(m['files']),'oracle_raw_corrected_different_pixels':926,
         'oracle_crc565':['b7611bbb','21a0be41','b7611bbb'],'new_hdl':'NOT_RUN'}
def command(args,work,stage,timeout):
 # Stream both stdout/stderr directly to a durable stage log. No PIPE contents
 # are discarded when wait raises TimeoutExpired. Direct child only; no shell.
 logpath=work/(stage+'.log');statepath=work/(stage+'-status.json')
 import time,re
 began=time.monotonic()
 status={'stage':stage,'state':'LAUNCHING','budget_seconds':timeout,'argv':args,
         'stdout_stderr':'merged in '+logpath.name,'pid':None,'returncode':None}
 def persist():
  status['wall_seconds']=time.monotonic()-began
  statepath.write_text(json.dumps(status,indent=2),encoding='utf-8')
 persist()
 with logpath.open('wb',buffering=0) as output:
  try:
   proc=subprocess.Popen(args,cwd=work,stdout=output,stderr=subprocess.STDOUT)
  except Exception as exc:
   status.update(state='LAUNCH_FAILED',error=str(exc));persist();raise
  status.update(state='RUNNING',pid=proc.pid);persist()
  try:
   while True:
    remaining=timeout-(time.monotonic()-began)
    if remaining<=0:raise subprocess.TimeoutExpired(args,timeout)
    try:
     code=proc.wait(timeout=min(1.0,remaining));break
    except subprocess.TimeoutExpired:
     # This does not change the admitted wall budget. It makes progress/rate
     # evidence durable so a future budget decision need not guess from buffers.
     text=logpath.read_text(encoding='utf-8',errors='replace')
     matches=re.findall(r'TELEMETRY_(?:DRAIN_BEGIN|DRAIN_PROGRESS|HOST_PACKET) t=(\d+).*?bytes=(\d+)',text)
     sample={'wall_seconds':time.monotonic()-began,'log_bytes':logpath.stat().st_size}
     if matches:sample.update(sim_time_ps=int(matches[-1][0]),decoded_wire_bytes=int(matches[-1][1]))
     with (work/(stage+'-wall-timeline.jsonl')).open('a',encoding='utf-8') as f:f.write(json.dumps(sample)+'\n')
     status['latest_progress']=sample;persist()
  except subprocess.TimeoutExpired as exc:
   status.update(state='TIMEOUT_STOPPING');persist()
   # Own direct compiler/vvp child; retain its actual exit status after cleanup.
   proc.kill()
   try:status['returncode']=proc.wait(timeout=10)
   except subprocess.TimeoutExpired:
    status.update(state='TIMEOUT_CLEANUP_UNCERTAIN');persist();raise
   status.update(state='TIMEOUT',owned_child_exited=True);persist()
   raise TimeoutError(f'{stage} budget {timeout}s exhausted; partial output in {logpath.name}; status in {statepath.name}') from exc
  status.update(state='EXITED',returncode=code,owned_child_exited=True);persist()
 text=logpath.read_text(encoding='utf-8',errors='replace')
 assert code==0 and 'FATAL' not in text,f'{stage} exit {code}; see {logpath.name}'
 return text
def main():
 p=argparse.ArgumentParser();p.add_argument('--rtl',action='store_true');p.add_argument('--out',default='work-real-system')
 p.add_argument('--simulate-timeout',type=float,default=300,help='Explicit admitted wall seconds; does not change clocks, UART, or simulation watchdog')
 a=p.parse_args();assert a.simulate_timeout>0;result=prepare_check()
 if a.rtl:
  work=(R/a.out).resolve();work.mkdir(exist_ok=False)
  for f in (R/'vectors').iterdir():shutil.copyfile(f,work/f.name)
  sources=[str(R/n.strip()) for n in (R/'sources.f').read_text().splitlines() if n.strip()]
  result['new_hdl']='RUNNING';(work/'result.json').write_text(json.dumps(result,indent=2))
  try:
   command(['iverilog','-g2012','-s','tb_b4_real_system','-I',str(work),'-I',str(R/'ce'),
     '-I',str(R/'b4/rtl'),'-I',str(R/'tests'),'-o',str(work/'system.vvp'),*sources,
     str(R/'tests/tb_b4_real_system.sv')],work,'compile',90)
   log=command(['vvp',str(work/'system.vvp')],work,'simulate',a.simulate_timeout)
   assert 'COMPLETE_REAL_SYSTEM_TELEMETRY' in log and 'PASS GEOMETRY_SYSTEM' in log
   result['integration']=verify(R,work);result['new_hdl']='PASS'
  except Exception as e:
   result['new_hdl']='FAIL_OR_INCOMPLETE';result['error']=str(e)
   (work/'result.json').write_text(json.dumps(result,indent=2));raise
  (work/'result.json').write_text(json.dumps(result,indent=2))
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
