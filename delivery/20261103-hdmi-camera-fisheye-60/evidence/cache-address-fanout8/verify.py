from pathlib import Path
import re,json,hashlib,itertools
root=Path('D:/f60-work/cache-addr-probe')
rx=re.compile(r'\b(GTP_\w+)\s*(?:/\*.*?\*/\s*)?(?:#\((.*?)\)\s*)?(\\[^\s]+|\w+)\s*\((.*?)\);',re.S)
def norm(s):return re.sub(r'\s+','',s.strip().lstrip('\\'))
def parse(variant):
 p=root/variant/'prj_tasks/syn_1/synthesize/cache_address_probe_syn.vm';s=p.read_text();s=s[s.index('module ddr_compact_'):s.index('endmodule')]
 cells=[];drivers={};loads={}
 for m in rx.finditer(s):
  typ,params,name,body=m.groups();ports={x:norm(y)for x,y in re.findall(r'\.(\w+)\s*\(([^()]*)\)',body)};c=dict(type=typ,name=norm(name),params=params or '',ports=ports)
  cells.append(c)
  for pin,net in ports.items():
   if pin in ['Z','Q','Z5']:
    drivers[net]=dict(c,output_pin=pin);continue
   if pin in ['DOA','DOB','ECC_PARITY','ECC_RDADDR']:continue
   for n in net.strip('{}').split(','):
    if re.fullmatch(r'(even|odd)_[ab](?:\[\d+\]|_\d+_(?:_\d+)?)',n):loads.setdefault(n,[]).append((c['name'],pin,typ))
 return cells,drivers,loads
def canonical(c):
 assert c['type'].startswith('GTP_LUT'),c
 width=5 if c['output_pin']=='Z5' else int(re.search(r'LUT(\d+)',c['type'])[1])
 init=int(re.search(r"\.INIT\(\d+'h([0-9a-fA-F]+)\)",c['params'])[1],16)
 pins=[c['ports']['I'+str(i)]for i in range(width)];variables=sorted(set(n for n in pins if n not in ["1'b0","1'b1"]))
 truth=0
 for idx,vals in enumerate(itertools.product([0,1],repeat=len(variables))):
  assign=dict(zip(variables,vals));assign.update({"1'b0":0,"1'b1":1});lut_idx=sum(assign[n]<<i for i,n in enumerate(pins));truth|=((init>>lut_idx)&1)<<idx
 support=[n for k,n in enumerate(variables)if any(((truth>>i)&1)!=((truth>>(i^(1<<(len(variables)-1-k))))&1)for i in range(1<<len(variables)))]
 reduced=0
 for idx,vals in enumerate(itertools.product([0,1],repeat=len(support))):
  assign={n:0 for n in variables};assign.update(dict(zip(support,vals)));assign.update({"1'b0":0,"1'b1":1});lut_idx=sum(assign[n]<<i for i,n in enumerate(pins));reduced|=((init>>lut_idx)&1)<<idx
 return dict(variables=support,truth_table_hex=hex(reduced),assignments=2**len(support))
bs,bd,bl=parse('baseline');cs,cd,cl=parse('maxfan8');rows=[]
for name in ['even_a','odd_a','even_b','odd_b']:
 for bit in range(14):
  base=f'{name}[{bit}]';assert base in bd and base in bl,base
  nets=[n for n in cl if n==base or re.fullmatch(name+'_'+str(bit)+r'_(?:_\d+)?',n)]
  assert len(nets)==4,(base,nets)
  old=bd[base]
  oldsig=canonical(old)
  copies=[]
  for n in sorted(nets):
   new=cd[n];sig=canonical(new)
   assert sig==oldsig,(base,n,oldsig,sig)
   assert len(cl[n])==8,(n,len(cl[n]));assert all(t[2].startswith('GTP_DRM')and t[1]in('ADDRA','ADDRB')for t in cl[n])
   copies.append(dict(net=n,driver=new['name'],fanout=len(cl[n]),loads=cl[n],type=new['type'],output_pin=new['output_pin'],params=norm(new['params']),inputs={k:v for k,v in new['ports'].items()if k.startswith('I')},canonical_function=sig))
  assert len(bl[base])==32
  assert sorted((x,y)for x,y,z in bl[base])==sorted((x,y)for n in nets for x,y,z in cl[n])
  rows.append(dict(address_bit=base,baseline_fanout=len(bl[base]),clones=copies,driver_projected_INIT_function_identical=True,baseline_driver=old,exact_DRM_load_partition=True))
def usage(v):
 t=(root/v/'prj_tasks/pnr_1/device_map/cache_address_probe.dmr').read_text();a=t.split('Device Utilization Summary:')[-1];return {m[0]:int(m[1])for m in re.findall(r'^\|\s+(FF|LUT|DRM|APM|IO)\s+\|\s+(\d+)\s+\|',a,re.M)}
paths=[root/v/q for v in ['baseline','maxfan8']for q in ['cache.v','top.v','clock.fdc','build.tcl','prj_tasks/syn_1/synthesize/cache_address_probe_syn.vm','prj_tasks/pnr_1/device_map/cache_address_probe.dmr','prj_tasks/pnr_1/device_map/cache_address_probe_map.adf']]
r=dict(status='PASS',index_bits=10,address_bits=14,address_net_bits=len(rows),baseline_net_count=56,candidate_net_count=224,baseline_max_fanout=32,candidate_max_fanout=8,preserved_DRM_address_loads=sum(len(x)for x in bl.values()),source_sha256=json.loads((root/'source-manifest.json').read_text())['sha256'],resources={v:usage(v)for v in ['baseline','maxfan8']},rows=rows,sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in paths},scope='Actual cache synthesized and device mapped. Cloned LUT projected INIT truth function over identical named inputs matches baseline (including shared LUT6D Z5/Z splitting); all original DRM address loads partition into four groups of eight. No route timing/placement claim; full candidate must audit final mapped and routed fanout again.')
(root/'verification.json').write_text(json.dumps(r,indent=2)+'\n');print({k:v for k,v in r.items()if k not in ['rows','sha256']})
