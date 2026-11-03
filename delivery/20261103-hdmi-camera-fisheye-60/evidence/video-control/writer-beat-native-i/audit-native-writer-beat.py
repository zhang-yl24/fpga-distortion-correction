from pathlib import Path
import argparse,collections,hashlib,json,re,xml.etree.ElementTree as ET

p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def tokens(path):
 s=re.sub(r'`include "[^"]*video_crc32.vh"','',path.read_text())
 s=re.sub(r'/\*.*?\*/|//[^\n]*|\(\*.*?\*\)','',s,flags=re.S)
 return re.findall(r'[A-Za-z_$][\w$]*|\d+|[^\s]',s)
def rows(path):
 t=ET.parse(path).getroot().find('table');h=[x.text for x in t.find('column_headers')]
 return [dict(zip(h,[x.text or '' for x in r])) for r in t.findall('row')]
pattern=re.compile(r'(?P<type>GTP_\w+)\s*(?:#\((?P<params>.*?)\))?\s+(?P<name>\\\S+|\w+)\s*\((?P<pins>.*?)\);',re.S)
def parse(path):
 text=path.read_text();out={}
 for mod in re.finditer(r'(?m)^module (ddr_raster_result_writer_pingpong\w*)\s',text):
  body=text[mod.end():text.index('endmodule',mod.end())]
  cells=[];loads=collections.Counter()
  for m in pattern.finditer(body):
   pins={k:re.sub(r'\s+','',v) for k,v in re.findall(r'\.(\w+)\s*\(\s*(.*?)\s*\)',m['pins'],re.S)}
   c={'type':m['type'],'name':m['name'].lstrip('\\'),'params':re.sub(r'\s+','',m['params'] or ''),'pins':pins}
   cells.append(c)
   for pin,net in pins.items():
    if pin not in ['Q','Z','O','CO','F','G']:loads[net]+=1
  families={}
  for bit in range(4):
   ff=[c for c in cells if c['type'].startswith('GTP_DFF') and re.fullmatch(r'beat(?:_copy)?\['+str(bit)+r'\](?:_\d+)?',c['name'])]
   base=next(c for c in ff if c['name']==f'beat[{bit}]')
   sig=lambda c:{'cell':c['type'],'parameters':c['params'],'input_pins':{k:v for k,v in c['pins'].items() if k!='Q'}}
   detail=[{'instance':c['name'],'q':c['pins']['Q'],'loads':loads[c['pins']['Q']]} for c in ff]
   families[str(bit)]={'registers':len(ff),'max_fanout':max(c['loads'] for c in detail),'sum_loads':sum(c['loads'] for c in detail),
       'identical_clone_control_and_init':all(sig(c)==sig(base) for c in ff),'signature':sig(base),'register_detail':detail}
  out[mod[1]]=families
 return out

proj=a.project;ref=a.reference
vmpath=proj/'prj_tasks/syn_1/synthesize/hdmi_camera_fisheye_top_syn.vm'
refvm=ref/'prj_tasks/syn_1/synthesize/hdmi_camera_fisheye_top_syn.vm'
writers=parse(vmpath);old=parse(refvm)
for mod,fams in writers.items():
 for bit,f in fams.items():
  f['baseline_signature_exact_match']=f['signature']==old[mod][bit]['signature']
  f['baseline_max_fanout']=old[mod][bit]['max_fanout']
  f['baseline_sum_loads']=old[mod][bit]['sum_loads']
src=proj/'compiled/rtl/experimental/ddr_adaptive_result_writer.v'
oldsrc=ref/'compiled/rtl/experimental/ddr_adaptive_result_writer.v'
mapfile=proj/'prj_tasks/pnr_1/device_map/report_db/device_map_high_fanout_singnal.db'
mapped=rows(mapfile)
beatrows=[r for r in mapped if '/writer/raster/beat' in r['Net_Name']]
ordered=all(int(mapped[i]['Fanout'])>=int(mapped[i+1]['Fanout']) for i in range(len(mapped)-1))
report={'scope':'Read-only complete native candidate synthesis/device-map verification. Routed fanout is audited separately when the parent-exported functional PNR netlist becomes available.',
 'project':str(proj),'reference':str(ref),'source_identity':json.loads((proj/'candidate-plan.json').read_text())['source_identity'],
 'source_count':len(json.loads((proj/'candidate-plan.json').read_text())['source_files']),
 'writer_functional_tokens_equal':tokens(src)==tokens(oldsrc),'writers':writers,
 'map_report_ordered':ordered,'map_report_entries':len(mapped),'map_report_cutoff_fanout':int(mapped[-1]['Fanout']),
 'map_beat_rows':beatrows,'map_scope':'Bounded high-fanout report; complete per-register fanout comes from the synthesis VM, not omitted mapped rows.',
 'hashes':{str(f):sha(f) for f in [src,oldsrc,vmpath,refvm,mapfile,proj/'candidate-plan.json']},
 'routed_verified':False,'physical_timing_verified':False}
report['passed']=report['writer_functional_tokens_equal'] and len(writers)==2 and all(f['max_fanout']<=32 and f['identical_clone_control_and_init'] for fams in writers.values() for f in fams.values())
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'passed':report['passed'],'source_identity':report['source_identity'],'source_count':report['source_count'],'writer_functional_tokens_equal':report['writer_functional_tokens_equal'],
 'writers':{m:{b:{k:f[k] for k in ['registers','max_fanout','sum_loads','baseline_max_fanout','identical_clone_control_and_init','baseline_signature_exact_match']} for b,f in v.items()} for m,v in writers.items()},
 'map_report_entries':len(mapped),'map_cutoff':report['map_report_cutoff_fanout'],'map_beat_rows':beatrows},indent=2))
assert report['passed']
