from pathlib import Path
import hashlib,json,re,sys,copy,argparse
sys.dont_write_bytecode=True
from check_outer import check,REQUIRED
R=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
b=json.loads((R/'evidence/SOURCE_BINDING.json').read_text())
assert sha(R/'rtl/hdmi1080_input_status_cdc.v')==b['original_outer_sha256']
assert sha(R/'rtl/dvp_mode_admission_monitor_cdc.v')==b['original_inner_sha256']
for n in ('hdmi1080_input_status_cdc.v','hdmi1080_input_status_guard_candidate.v','hdmi1080_input_status_permit_candidate.v'):
 s=(R/'rtl'/n).read_text();assert s.count('or negedge rst_n')==2
 assert '.SNAPSHOT_INTERVAL_REF_CYCLES(27000)' in s
 assert 'geometry_failed ? geometry_fault:timing_bad_sync[1] ? 8\'h24:rate_failed ? 8\'h25:8\'h00' in s
for n in ('dvp_mode_admission_monitor_cdc.v','dvp_mode_admission_monitor_epoch_candidate.v','dvp_mode_admission_monitor_permit_candidate.v'):
 s=(R/'rtl'/n).read_text();assert s.count('or negedge rst_n')==2
 assert 'snapshot_request==ack_seen && !settle && !snapshot_apply' in s
 assert 'if(request_sync[1]!=snapshot_ack)' in s
assert not any('Meyesemi' in p.read_text() for p in (R/'rtl').iterdir())
for line in (R/'sources.f').read_text().splitlines():assert (R/line).is_file()
rows=[]
for c,labels in REQUIRED.items():
 for label in labels:rows.append(dict(event='MARK',case=str(c),kind='-1',epoch=str(c),time='1',a=label,b='0',c='0'))
 rows.append(dict(event='QUALIFIED',case=str(c),kind='-1',epoch=str(c),time='2',a='2',b='2',c='2'))
 if c<=4:rows.append(dict(event='READY',case=str(c),kind='-1',epoch=str(c),time='1',a='4',b='1',c='0'))
 for k in (0,1,2):rows.append(dict(event='APPLY',case=str(c),kind=str(k),epoch=str(c),time='1',a='0',b='0',c='0'))
rows.extend([dict(event='SUMMARY',case='0',kind='-1',epoch='9',time='3',a='1000',b='6',c='3'),dict(event='CURRENT_DIFF_COUNT',case='0',kind='1',epoch='9',time='3',a='0',b='0',c='0'),dict(event='PASS',case='0',kind='-1',epoch='9',time='3',a='fixture',b='0',c='0')])
check(rows);mutants=[rows[:-1]]
t=copy.deepcopy(rows);next(z for z in t if z['event']=='APPLY')['epoch']='0';mutants.append(t)
t=copy.deepcopy(rows);next(z for z in t if z['event']=='QUALIFIED')['a']='0';mutants.append(t)
t=[z for z in rows if not(z['event']=='MARK' and z['a']=='TIMING_TERMINAL_SAME_REF')];mutants.append(t)
t=copy.deepcopy(rows);next(z for z in t if z['event']=='SUMMARY')['b']='0';mutants.append(t)
t=[z for z in rows if not(z['event']=='APPLY' and z['kind']=='2')];mutants.append(t)
for t in mutants:
 try:check(t)
 except AssertionError:pass
 else:raise AssertionError('oracle accepted mutant')
out={'status':'PREPARATION_PASS_HDL_PENDING','original_hashes_verified':2,'self_RTL_files':7,'RS_processes_retained_per_module':2,'host_oracle_negative_fixtures':len(mutants),'RX_body_included':False,'production_modified':False,'no_new_recovery_protocol':True}
p=argparse.ArgumentParser();p.add_argument('--out',default='run-preparation.json');a=p.parse_args()
dest=Path(a.out);dest=dest if dest.is_absolute() else R/dest
dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(out))
