from pathlib import Path
import re,json,itertools,hashlib
import argparse
ap=argparse.ArgumentParser(description='Audit mapped user synchronizers excluding FIFO, including reset aliases.')
ap.add_argument('--project',type=Path,required=True)
ap.add_argument('--mapped-netlist',type=Path,required=True)
ap.add_argument('--inventory',type=Path,required=True)
ap.add_argument('--output',type=Path,required=True)
a=ap.parse_args();root=Path(__file__).resolve().parents[1]
project=a.project.resolve();sim=a.mapped_netlist.resolve();synlog=project/'prj_tasks/syn_1/synthesize/run.log'
def norm(x):return re.sub(r'\s+','',x.strip().lstrip('\\'))
rx=re.compile(r'\b(V_\w+)\s*(?:/\*.*?\*/\s*)?(?:#\(.*?\)\s*)?(\\[^\s]+|\w+)\s*\((.*?)\);',re.S)
cells=[]
for m in rx.finditer(sim.read_text(encoding='utf-8')):
 typ,name,body=m.groups();ports={x:norm(y)for x,y in re.findall(r'\.(\w+)\s*\(([^()]*)\)',body)}
 cells.append(dict(type=typ,name=norm(name),ports=ports,raw=m.group()))
byq={c['ports']['Q']:c for c in cells if c['type'].startswith('V_FF') and 'Q'in c['ports']}
byname={c['name'].split('/opit_')[0]:c for c in byq.values()}
drivers={}
for c in cells:
 for p in ['Z','Z5','O']:
  if c['ports'].get(p):drivers[c['ports'][p]]=(c,p)
def const(n):
 if n in ("1'b1","1'b0"):return int(n[-1])
 if n.startswith('_VCC') or n.startswith('_GND'):
  assert n in drivers,('Unbound named constant',n)
  c,pin=drivers[n]
  assert c['type'].startswith('V_LUT'),('Named constant is not a LUT constant',n,c['type'])
  z=re.search(r"\.INIT\(\d+\x27h([0-9a-fA-F]+)\)",c['raw']);assert z,n
  width=5 if pin=='Z5' else 6;mask=(1<<(1<<width))-1;init=int(z[1],16)&mask
  assert init in (0,mask),('Named constant LUT is not constant',n,hex(init))
  return int(init==mask)
 return None
def lut_inputs(c,p):
 z=re.search(r"\.INIT\(\d+\x27h([0-9a-fA-F]+)\)",c['raw']);assert z,c['name']
 init=int(z[1],16);width=5 if p=='Z5' else 6
 pins=[c['ports'].get('I'+str(i),"1'b0")for i in range(width)]
 fixed={i:const(n)for i,n in enumerate(pins)if const(n)!=None}
 allowed=[i for i in range(1<<width)if all(((i>>k)&1)==v for k,v in fixed.items())]
 return [pins[k]for k in range(width)if k not in fixed and any(((init>>i)&1)!=((init>>(i^(1<<k)))&1)for i in allowed)]
def leaves(n,depth=0):
 if const(n)!=None:return set()
 if n in byq:return {n}
 if n not in drivers or depth>6:return {n}
 c,p=drivers[n]
 if c['type'] in ('V_BUF','V_INV'):return leaves(c['ports']['I'],depth+1)
 if c['type'].startswith('V_LUT'):
  return set().union(*(leaves(x,depth+1)for x in lut_inputs(c,p)))
 return {n}
def ev(n,vals,depth=0):
 if n in vals:return vals[n]
 v=const(n)
 if v!=None:return v
 if depth>8 or n not in drivers:raise RuntimeError(n)
 c,p=drivers[n]
 if c['type']=='V_BUF':return ev(c['ports']['I'],vals,depth+1)
 if c['type']=='V_INV':return 1-ev(c['ports']['I'],vals,depth+1)
 if c['type'].startswith('V_LUT'):
  z=re.search(r'\.INIT\(\d+\x27h([0-9a-fA-F]+)\)',c['raw']);assert z,c['name']
  relevant=lut_inputs(c,p)
  idx=sum((ev(c['ports'].get('I'+str(i),"1'b0"),vals,depth+1) if c['ports'].get('I'+str(i),"1'b0") in relevant or const(c['ports'].get('I'+str(i),"1'b0"))!=None else 0)<<i for i in range(5 if p=='Z5' else 6))
  return (int(z[1],16)>>idx)&1
 raise RuntimeError(c['name'])
alias={};alias_lines=[]
for line in synlog.read_text(encoding='utf-8').splitlines():
 m=re.search(r'Removed .*? inst (.*?) that is redundant to (.*?)$',line)
 if m:alias[m[1]]=m[2];alias_lines.append(line)
def owner(n):
 seen=set()
 while n in alias:
  assert n not in seen,'Alias cycle';seen.add(n);n=alias[n]
 return n
route=project/'prj_tasks/pnr_1/place_route/hdmi_camera_fisheye_top_route_optimize.netlist'
primitives=dict(line.split(';')[:2]for line in route.read_text(encoding='utf-8').splitlines()if ';gop' in line)
dmr=project/'prj_tasks/pnr_1/device_map/hdmi_camera_fisheye_top.dmr';dmr_text=dmr.read_text(encoding='utf-8')
rows=[];inv=json.loads(a.inventory.read_text(encoding='utf-8'))
plan=json.loads((project/'candidate-plan.json').read_text(encoding='utf-8'))
source_hashes={r['source']:r['source_sha256']for r in plan['overlays']}
for name,expected in inv['source_sha256'].items():
 assert source_hashes.get(name)==expected,('Inventory is not bound to this prepared source',name)

for r0 in inv['chains']:
 if r0['source'].endswith('video_async_fifo.v'):continue
 r=dict(r0);name=(r['instance']+'/' if r['instance'] else '')+r['name']
 if r['kind']=='gray_statistic' or r['name']=='processed_ref':
  assert not any(x in byq or x in byname for x in r['logical_stages'])
  r.update(status='PRUNED_UNOBSERVABLE',reason='no_free_frames has no consumer in system' if r['kind']=='gray_statistic' else 'processed_ref has no consumer in top');rows.append(r);continue
 mapped=[owner(x)for x in r['logical_stages']]
 ff=[byq[x] if x in byq else byname[x] for x in mapped]
 assert len({f['name']for f in ff})==len(ff)
 assert len({f['ports']['CK']for f in ff})==1
 assert all('_srl' not in f['name']for f in ff)
 checks=[]
 for f in ff:
  primitive=f['name'].rsplit('/',2)[0];assert primitives.get(primitive)=='gopQ',(name,primitive,primitives.get(primitive))
  logical_owner=f['name'].split('/opit_')[0]
  attrs=[l.strip()for l in dmr_text.splitlines()if ('| i:'+logical_owner+' ')in l and ('PAP_ASYNC_REG'in l or 'PAP_SRL_STYLE'in l)]
  assert any('PAP_ASYNC_REG'in l and 'TRUE'in l for l in attrs),(name,logical_owner)
  f['device_map_attributes']=attrs
 for prev,nxt in zip(ff,ff[1:]):
  q=prev['ports']['Q'];d=nxt['ports']['D'];ls=leaves(d)
  resets={x:1 for x in ls if 'reset'in x and x!=q};free=sorted(ls-set(resets));assert q in free,(name,ls)
  assert len(free)<=8,(name,free)
  for v in itertools.product([0,1],repeat=len(free)):
   vals=dict(zip(free,v));vals.update(resets);assert ev(d,vals)==vals[q],(name,vals)
  checks.append(dict(direct=(q==d),leaf_signals=sorted(ls),active_reset_assumptions=resets,truth_table_cases=2**len(free),active_identity=True))
 r.update(status='MAPPED_DISTINCT_FF',resolved_logical_stages=mapped,mapped_stages=[{k:v for k,v in f.items()if k!='raw'}for f in ff],stage_connections=checks)
 rows.append(r)
paths=[project/'prj_tasks/pnr_1/place_route/hdmi_camera_fisheye_top_pnr.adf',sim,synlog,route,dmr,a.inventory,project/'candidate-plan.json']
result=dict(schema='nonfifo-mapped-synchronizer-audit-v2',status='PASS',build=project.name,source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths},logical_chains=len(rows),pruned_chains=sum(r['status'].startswith('PRUNED')for r in rows),mapped_logical_chains=sum(r['status'].startswith('MAPPED')for r in rows),mapped_logical_stages=sum(len(r.get('mapped_stages',[]))for r in rows),unique_mapped_FF=len({f['name']for r in rows for f in r.get('mapped_stages',[])}),rows=rows,reset_aliases=[l for l in alias_lines if 'reset'in l],scope='Verifies listed FF structure, attributes and active-state stage-to-stage identity. CDC/reset timing/MTBF, source glitches and held-bundle delay windows need separate review.')
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print({k:v for k,v in result.items()if k not in ['rows','source_hashes','reset_aliases']})
