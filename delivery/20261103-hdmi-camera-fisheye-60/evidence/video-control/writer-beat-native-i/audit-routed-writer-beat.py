from pathlib import Path
import argparse,collections,hashlib,json,re
p=argparse.ArgumentParser();p.add_argument('--netlist',type=Path,required=True);p.add_argument('--project',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
def norm(x):return re.sub(r'\s+','',x.strip().lstrip('\\'))
rx=re.compile(r'\b(V_\w+)\s*(?:/\*.*?\*/\s*)?(?:#\((.*?)\)\s*)?(\\[^\s]+|\w+)\s*\((.*?)\);',re.S)
cells=[];loads=collections.defaultdict(list);transparent={}
outputs={'Q','Z','Z5','O','COUT','CO','DO','DOA','DOB'}
for m in rx.finditer(a.netlist.read_text(encoding='utf-8')):
 typ,params,name,body=m.groups();ports={x:norm(y) for x,y in re.findall(r'\.(\w+)\s*\(([^()]*)\)',body)}
 c={'type':typ,'name':norm(name),'ports':ports,'params':re.sub(r'\s+','',params or '')};cells.append(c)
 for pin,net in ports.items():
  if net and pin not in outputs:loads[net].append({'instance':c['name'],'type':typ,'pin':pin})
 if typ in ['V_BUF','V_INV']:
  z=ports.get('Z',ports.get('O'))
  if z:transparent[c['name']]=z
def buffered_loads(net,seen=None):
 seen=set() if seen is None else set(seen)
 assert net not in seen,'buffer loop';seen.add(net);out=[]
 for d in loads[net]:
  if d['instance'] in transparent:out.extend(buffered_loads(transparent[d['instance']],seen))
  else:out.append(d)
 return out
families={};all_detail=[]
for lane in range(2):
 for bit in range(4):
  name=f'lane{lane}/bit{bit}'
  pat=re.compile(r'lanes\['+str(lane)+r'\]\.worker/writer/raster/beat(?:_copy)?\['+str(bit)+r'\](?:_\d+)?/')
  ff=[c for c in cells if c['type'].startswith('V_FF') and pat.search(c['name'])]
  assert ff,name
  data=[]
  for c in ff:
   q=c['ports']['Q'];actual=loads[q];expanded=buffered_loads(q)
   data.append({'instance':c['name'],'q':q,'cell':c['type'],'parameters':c['params'],
     'input_pins':{k:v for k,v in c['ports'].items() if k!='Q'},
     'direct_connected_pins':len(actual),'direct_cell_types':dict(collections.Counter(d['type'] for d in actual)),
     'buffer_expanded_connected_pins':len(expanded),
     'load_sha256':hashlib.sha256(json.dumps(actual,sort_keys=True).encode()).hexdigest()})
  families[name]={'registers':len(ff),'max_direct_connected_pins':max(d['direct_connected_pins'] for d in data),
    'sum_direct_connected_pins':sum(d['direct_connected_pins'] for d in data),
    'max_buffer_expanded_connected_pins':max(d['buffer_expanded_connected_pins'] for d in data),
    'register_details':data}
plan=a.project/'candidate-plan.json';adf=a.project/'prj_tasks/pnr_1/place_route/hdmi_camera_fisheye_top_pnr.adf'
report={'scope':'Connected primitive input-pin counts in the functional netlist exported from the final PNR ADF. Counts include all connected LUT inputs, even when the LUT truth table ignores an input. BUF/INV expansion is reported separately. This is topology, not delay or whole-device equivalence signoff.',
 'source_identity':json.loads(plan.read_text())['source_identity'],'families':families,
 'hashes':{str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in [a.netlist,plan,adf]},
 'physical_timing_verified':False}
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='families'}|{'families':{k:{x:y for x,y in v.items() if x!='register_details'} for k,v in families.items()}},indent=2))
