from pathlib import Path
import re,json,itertools,hashlib
root=Path('D:/f60/delivery/20261103-hdmi-camera-fisheye-60');work=Path('D:/f60-work/cdc')
cells=json.loads((work/'g-cells.json').read_text());byq={c['ports']['Q']:c for c in cells if c['type'].startswith('V_FF') and 'Q'in c['ports']}
byname={c['name'].split('/opit_')[0]:c for c in byq.values()}
drivers={}
for c in cells:
 for p in ['Z','Z5','O']:
  if c['ports'].get(p):drivers[c['ports'][p]]=(c,p)
def const(n):
 if n in ("1'b1","1'b0"):return int(n[-1])
 if n.startswith('_VCC'):return 1
 if n.startswith('_GND'):return 0
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
alias={
'system/bank_core/engine/lanes[1].worker/core/reset_sync':'system/bank_core/engine/lanes[0].worker/core/reset_sync',
'system/core_reset_sync':'core_reset',
'system/output_video/reset_sync':'system/display_fifo/rd_reset_sync',
'system/input_link/input_dma/sys_reset':'system/input_link/input_dma/capture/sys_reset'}
rows=[];inv=json.loads((root/'evidence/cdc-user-audit/synchronizer-chains-g.json').read_text())
for r0 in inv['chains']:
 if r0['source'].endswith('video_async_fifo.v'):continue
 r=dict(r0);name=(r['instance']+'/' if r['instance'] else '')+r['name']
 if r['kind']=='gray_statistic' or r['name']=='processed_ref':
  assert not any(x in byq or x in byname for x in r['logical_stages'])
  r.update(status='PRUNED_UNOBSERVABLE',reason='no_free_frames has no consumer in system' if r['kind']=='gray_statistic' else 'processed_ref has no consumer in top');rows.append(r);continue
 mapped=[alias.get(name,name)+f'[{i}]' for i in range(2)] if name in alias else r['logical_stages']
 ff=[byq[x] if x in byq else byname[x] for x in mapped]
 assert ff[0]['name']!=ff[1]['name'];assert ff[0]['ports']['CK']==ff[1]['ports']['CK']
 assert all('_srl' not in f['name'] for f in ff)
 q=ff[0]['ports']['Q'];d=ff[1]['ports']['D'];ls=leaves(d)
 # Legal reset-release operating state: every local release FF leaf is high.
 resets={x:1 for x in ls if 'reset' in x and x!=q}
 free=sorted(ls-set(resets));assert q in free,(name,ls)
 assert len(free)<=8,(name,free)
 for v in itertools.product([0,1],repeat=len(free)):
  vals=dict(zip(free,v));vals.update(resets);assert ev(d,vals)==vals[q],(name,vals)
 r.update(status='MAPPED_TWO_DISTINCT_FF',owner_alias=alias.get(name),mapped_stages=[{k:v for k,v in f.items() if k!='raw'}for f in ff],stage1_to_stage2=dict(direct=(q==d),leaf_signals=sorted(ls),active_reset_assumptions=resets,truth_table_cases=2**len(free),active_identity=True))
 rows.append(r)
paths=[Path('D:/f60-run/physical-g/prj_tasks/pnr_1/place_route/hdmi_camera_fisheye_top_pnr.adf'),Path('D:/f60-work/cdc/g-netlist/prj_tasks/pnr_1/generate_netlist/hdmi_camera_fisheye_top_sim.v'),Path('D:/f60-run/physical-g/prj_tasks/syn_1/synthesize/hdmi_camera_fisheye_top_syn.vm')]
result=dict(schema='nonfifo-mapped-synchronizer-audit-v1',build='physical-g',source_hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},logical_chains=len(rows),pruned_chains=sum(r['status'].startswith('PRUNED') for r in rows),mapped_logical_chains=sum(r['status'].startswith('MAPPED')for r in rows),shared_reset_chains=len(alias),rows=rows,additional_unprotected_reset_chains=['hdmi_configuration/'+x for x in ['cfg_reset_pipe','seq_reset_pipe','tx_reset_pipe']],scope='This verifies the listed FF structure and active-state stage1-to-stage2 identity. It does not sign off CDC, reset timing, metastability MTBF, source glitches or held-bundle delay windows. The 3 additional three-stage configuration reset chains need H remapping after the attribute addendum.')
(root/'evidence/cdc-user-audit/physical-g-nonfifo-mapping.json').write_text(json.dumps(result,indent=2)+'\n')
print({k:v for k,v in result.items()if k not in ['rows','source_hashes']})
