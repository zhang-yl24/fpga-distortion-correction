"""Cloud POSIX-only bounded runner; explicit --rtl and admitted budget required.
No installed-tool mutation, network, PDS or device action. Does not generate vectors.
"""
from pathlib import Path
import argparse,json,hashlib,os,sys,time,re,subprocess,signal,shutil
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent
GIB=1024**3
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def check_inputs(vectors):
 m=json.loads((R/'manifest.json').read_text())
 for e in m['files']:
  p=R/e['path'];assert p.is_file() and p.stat().st_size==e['bytes'] and sha(p)==e['sha256'],e['path']
 vm=json.loads((vectors/'vector_manifest.json').read_text())
 for name,e in vm['files'].items():
  assert Path(name).name==name
  p=vectors/name;assert p.stat().st_size==e['bytes'] and sha(p)==e['sha256'],name
 f=json.loads((vectors/'fixture.json').read_text())
 assert f['native'] and f['width']==1920 and f['height']==1080 and f['pixels_per_frame']==2073600 and f['frames']==3
 assert f['crc565']==[0xc3a70a0b,0x5777c301,0xc3a70a0b] and f['guard_q22']==885911
 for name,h in f['script_sha256'].items():assert sha(R/name)==h,('generator drift',name)
 return {'package_manifest_sha256':sha(R/'manifest.json'),'vector_manifest_sha256':sha(vectors/'vector_manifest.json'),'source_files':37,'files_verified':len(m['files']),'HDL':'NOT_RUN'}
def available_bytes():
 try:
  for line in Path('/proc/meminfo').read_text().splitlines():
   if line.startswith('MemAvailable:'):return int(line.split()[1])*1024
 except OSError:pass
 return None
def group_members(pgid):
 members=[]
 for d in Path('/proc').iterdir():
  if not d.name.isdigit():continue
  try:
   stat=(d/'stat').read_text();rest=stat[stat.rfind(')')+2:].split()
   if int(rest[2])!=pgid:continue
   rss=int(rest[21])*os.sysconf('SC_PAGE_SIZE')
   members.append({'pid':int(d.name),'starttime_ticks':int(rest[19]),'state':rest[0],'rss_bytes':rss})
  except (OSError,ValueError,IndexError):continue
 return members
def process_identity(pid):
 # Missing means gone; unreadable/invalid is uncertainty, never proof of exit.
 try:stat=Path('/proc',str(pid),'stat').read_text()
 except FileNotFoundError:return None
 rest=stat[stat.rfind(')')+2:].split()
 return {'pid':pid,'starttime_ticks':int(rest[19]),'state':rest[0],'pgid':int(rest[2])}

def remember_members(known,members,pgid):
 # A known birth identity in this group anchors adoption of newly seen children.
 if not members:return
 if any(m['pid'] in known and known[m['pid']]!=m['starttime_ticks'] for m in members):
  raise RuntimeError('PID_BIRTH_CHANGED_NO_SIGNAL')
 if not any(known.get(m['pid'])==m['starttime_ticks'] for m in members):
  raise RuntimeError('UNANCHORED_PROCESS_GROUP_NO_SIGNAL')
 for m in members:known[m['pid']]=m['starttime_ticks']

def cleanup_owned_group(proc,known,*,members_fn=None,identity_fn=None,signal_fn=None,clock=None,pause=None,total_seconds=10.0,term_grace_seconds=2.0):
 # Poll the GROUP after KILL, not merely the already-exited direct parent.
 # Dependency injection is only for deterministic CPU tests; production defaults
 # are /proc and ordinary-user POSIX signals, never privilege escalation.
 members_fn=members_fn or group_members;identity_fn=identity_fn or process_identity
 signal_fn=signal_fn or os.killpg;clock=clock or time.monotonic;pause=pause or time.sleep
 start=clock();deadline=start+total_seconds;term_at=None;kill_sent=False
 result={'known_birth_identities':dict(known),'signals':[],'polls':0,'owned_running_members_exited':False}
 def finish(reason,members):
  result.update(reason=reason,remaining_members=members,wall_seconds=clock()-start,known_birth_identities=dict(known),parent_returncode=proc.poll())
  return result
 while True:
  try:
   members=members_fn(proc.pid);remember_members(known,members,proc.pid)
   live=[];states=[]
   for pid,birth in list(known.items()):
    ident=identity_fn(pid)
    if ident is None:states.append({'pid':pid,'birth':birth,'status':'gone'});continue
    if ident['starttime_ticks']!=birth:
     states.append({'pid':pid,'birth':birth,'status':'original_gone_pid_reused_not_signaled'});continue
    if ident['pgid']!=proc.pid and ident['state']!='Z':
     result['identity_states']=states+[ident];return finish('OWNED_MEMBER_LEFT_GROUP_NO_SIGNAL',members)
    states.append(ident)
    if ident['state']!='Z':live.append(ident)
   result.update(polls=result['polls']+1,identity_states=states)
   parent_exit=proc.poll()
   if not live and parent_exit is not None and not any(m['state']!='Z' for m in members):
    result['owned_running_members_exited']=True
    return finish('EXIT_CONFIRMED',members)
   now=clock()
   if now>=deadline:return finish('CLEANUP_DEADLINE_EXCEEDED',members)
   sig=None
   if term_at is None:sig=signal.SIGTERM;term_at=now
   elif not kill_sent and now-term_at>=term_grace_seconds:sig=getattr(signal,'SIGKILL',9);kill_sent=True
   if sig is not None:
    # Re-read and validate birth identities immediately before group signaling.
    current=members_fn(proc.pid);remember_members(known,current,proc.pid)
    if any(m['state']!='Z' for m in current):
     signal_fn(proc.pid,sig);result['signals'].append({'signal':int(sig),'elapsed_seconds':clock()-start,'identities':[{'pid':m['pid'],'starttime_ticks':m['starttime_ticks']} for m in current]})
   pause(min(.05,max(0,deadline-clock())))
  except ProcessLookupError:
   # Signal raced with natural exit. Re-read identities on the next bounded poll.
   if clock()>=deadline:return finish('CLEANUP_DEADLINE_AT_EXIT_RACE',[])
   pause(min(.05,max(0,deadline-clock())))
  except (OSError,ValueError,IndexError,RuntimeError) as exc:
   result['error']=type(exc).__name__+': '+str(exc)
   return finish('CLEANUP_IDENTITY_OR_PERMISSION_UNCERTAIN',members if 'members' in locals() else [])

def set_child_limit():
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(6*GIB,6*GIB))
def command(argv,work,stage,budget):
 assert os.name=='posix' and Path('/proc').is_dir(),'cloud Linux required; no Windows long execution'
 start=time.monotonic();proc=None;offset=0;tail='';reason=None;owned_identities={}
 record={'stage':stage,'argv':argv,'budget_seconds':budget,'state':'LAUNCHING','rlimit_as_bytes':6*GIB,'rss_stop_bytes':5*GIB,'available_stop_bytes':int(1.5*GIB)}
 def save():
  record['wall_seconds']=time.monotonic()-start
  tmp=work/(stage+'-status.tmp');tmp.write_text(json.dumps(record,indent=2));tmp.replace(work/(stage+'-status.json'))
 save()
 assert available_bytes() is not None and available_bytes()>=int(1.5*GIB),'memory visibility/admission failed'
 with (work/(stage+'.log')).open('wb',buffering=0) as log:
  try:
   proc=subprocess.Popen(argv,cwd=work,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,preexec_fn=set_child_limit)
   ident=process_identity(proc.pid)
   assert ident is not None and ident['pgid']==proc.pid,'new child birth/group identity unavailable'
   owned_identities[proc.pid]=ident['starttime_ticks']
   record.update(pid=proc.pid,pgid=proc.pid,parent_birth=ident['starttime_ticks'],state='RUNNING');save()
   while proc.poll() is None:
    elapsed=time.monotonic()-start;members=group_members(proc.pid);rss=sum(x['rss_bytes'] for x in members);avail=available_bytes()
    remember_members(owned_identities,members,proc.pid)
    path=work/(stage+'.log')
    with path.open('rb') as f:f.seek(offset);chunk=f.read();offset=f.tell()
    tail=(tail+chunk.decode('utf-8','replace'))[-65536:]
    match=re.findall(r'NATIVE_PROGRESS t=(\d+) cycles=(\d+) frames=(\d+) bytes=(\d+)',tail)
    sample={'wall_seconds':elapsed,'rss_group_bytes':rss,'available_bytes':avail,'members':members,'log_bytes':offset}
    if match:
     t,cycles,frames,nbytes=map(int,match[-1]);sample.update(sim_time_ps=t,cycles=cycles,frames=frames,uart_bytes=nbytes)
     if t>0:sample['estimated_wall_to_180ms']=elapsed*180000000000/t
    record['latest']=sample
    with (work/(stage+'-progress.jsonl')).open('a',buffering=1) as f:f.write(json.dumps(sample)+'\n');f.flush()
    print(json.dumps({'stage':stage,**{k:v for k,v in sample.items() if k!='members'}}),flush=True);save()
    if elapsed>=budget:reason='WALL_TIMEOUT'
    elif rss>=5*GIB:reason='RSS_LIMIT'
    elif avail is None or avail<int(1.5*GIB):reason='AVAILABLE_MEMORY_LIMIT_OR_UNKNOWN'
    elif 'FATAL:' in tail:reason='HDL_FATAL'
    elif stage=='simulate' and elapsed>=600 and sample.get('sim_time_ps',0)>=33333333333 and sample.get('estimated_wall_to_180ms',0)>14400:reason='PROJECTED_HARD_BUDGET_EXCEEDED'
    if reason:break
    try:proc.wait(timeout=min(5,max(.01,budget-elapsed)))
    except subprocess.TimeoutExpired:pass
  except BaseException as exc:
   reason=type(exc).__name__+': '+str(exc);raise
  finally:
   if proc is not None:
    cleanup=cleanup_owned_group(proc,owned_identities)
    record['cleanup']=cleanup;record['returncode']=proc.returncode
    record['remaining_members']=cleanup['remaining_members']
    record['owned_running_members_exited']=cleanup['owned_running_members_exited']
    if not cleanup['owned_running_members_exited']:
     record['cleanup_failure']=cleanup['reason']
     if reason is None:reason=cleanup['reason']
   record.update(state='STOPPED' if reason else 'EXITED',stop_reason=reason);save()
 assert proc is not None and proc.returncode==0 and reason is None and record['owned_running_members_exited'],record
 text=(work/(stage+'.log')).read_text(errors='replace');assert 'FATAL' not in text,text[-4000:]
 return text
