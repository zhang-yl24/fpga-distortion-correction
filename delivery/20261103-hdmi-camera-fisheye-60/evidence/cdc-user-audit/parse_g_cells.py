from pathlib import Path
import re,json,hashlib
ROOT=Path('D:/f60/delivery/20261103-hdmi-camera-fisheye-60')
p=Path('D:/f60-work/cdc/g-netlist/prj_tasks/pnr_1/generate_netlist/hdmi_camera_fisheye_top_sim.v')
def norm(x):return re.sub(r'\s+','',x.strip().lstrip('\\'))
rx=re.compile(r'\b(V_\w+)\s*(?:/\*.*?\*/\s*)?(?:#\(.*?\)\s*)?(\\[^\s]+|\w+)\s*\((.*?)\);',re.S)
cells=[]
s=p.read_text()
for m in rx.finditer(s):
 typ,name,body=m.groups();ports={x:norm(y) for x,y in re.findall(r'\.(\w+)\s*\(([^()]*)\)',body)}
 cells.append(dict(type=typ,name=norm(name),ports=ports,raw=m.group()))
ff=[c for c in cells if c['type'].startswith('V_FF')]
byq={c['ports'].get('Q'):c for c in ff}
inv=json.loads((ROOT/'evidence/cdc-user-audit/synchronizer-chains-g.json').read_text())
rows=[]
for c in inv['chains']:
 if c['source'].endswith('video_async_fifo.v'):continue
 row=dict(c)
 row['stages']=[{k:v for k,v in byq[x].items() if k!='raw'} if x in byq else None for x in c['logical_stages']]
 rows.append(row)
Path('D:/f60-work/cdc/g-cells.json').write_text(json.dumps(cells))
Path('D:/f60-work/cdc/g-nonfifo-first-pass.json').write_text(json.dumps(rows,indent=2))
print('cells',len(cells),'ff',len(ff))
for r in rows:
 if r['kind']=='gray_statistic':continue
 print(r['logical_stages'],[(x['type'],x['ports']['D']) if x else None for x in r['stages']])
