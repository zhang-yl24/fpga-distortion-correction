"""Derive and query exact CDC objects from this trained diagnostic mapping."""
from pathlib import Path
from collections import Counter
import importlib.util,json,re,shutil,sys
import native_review as n
ROOT,BASE,SOURCE,TOP=n.ROOT,n.BASE,n.SOURCE,n.TOP
sys.path.insert(0,str(ROOT/'tools'))
import audit_checked_io_netlist as net
sha,write,load=n.sha,n.write,n.load

def connectivity():
 mapping=load(BASE/'mapping-review.json');work=BASE/'functional-export'
 raw=(work/f'generate_netlist/{TOP}_sim.v').read_text(encoding='utf-8')
 assert raw.count('module '+TOP)==1
 cells,ports,drivers,libs=net.parse(raw.replace('module '+TOP,'module board1080_top',1),net.LIBRARY)
 locations={net.canonical(m[4]):dict(site=m[2].strip(),line=raw.count('\n',0,m.start())+1) for m in re.finditer(r'\b(V_FFSYN|V_FFASYN)\s*/\*\s*([^*]+?)\s*\*/\s*#\((.*?)\)\s*(\\[^\s]+)\s*\(',raw,re.S)}
 expected={}
 for entry in mapping['registers']:
  assert entry['route_mapping_status']=='independent_plain_register' and len(entry['route_objects'])==1
  prefix=entry['route_objects'][0]['name']+'/'
  ff=[(name,c) for name,c in cells.items() if c['Type'] in net.FFS and name.lstrip('\\').startswith(prefix)]
  assert len(ff)==1
  name,c=ff[0];assert name in locations
  expected[entry['expected_instance']]=dict(native_instance=name,primitive=c['Type'],parameters=c['Parameters'],ports=c['Ports'],location=locations[name],route_instance=entry['route_objects'][0]['name'])
 assert len(expected)==161
 links=[]
 for pair in mapping['stage_links']:
  a,b=expected[pair['first']],expected[pair['second']]
  q,d=net.scalar(a['ports']['Q']),net.scalar(b['ports']['D']);ck=net.scalar(a['ports']['CK'])
  criteria=dict(direct_q_to_d=q==d,sole_driver=drivers[d]==[(a['native_instance'],'Q')],same_clock=ck==net.scalar(b['ports']['CK']) and net.constant(ck) is None,first_ce=net.constant(net.scalar(a['ports']['CE']))==1,second_ce=net.constant(net.scalar(b['ports']['CE']))==1)
  assert all(criteria.values())
  links.append(dict(first=pair['first'],second=pair['second'],criteria=criteria,same_site=a['location']['site']==b['location']['site'],first_route=a['route_instance'],second_route=b['route_instance'],q_net=q,d_net=d))
 assert len(links)==81
 pins={}
 for line in (SOURCE/f'place_route/{TOP}_prr_route_optimize.prt').read_text().splitlines():
  bits=line.split('|')
  if len(bits)==7 and bits[4]:pins[bits[4]]=dict(Pin=bits[0],Direction=bits[5],Fixed=bits[6])
 plan=load(SOURCE/'build-plan.json');assert len(pins)==len(plan['Pins'])==46
 for name,pin in plan['Pins'].items():
  direction='inout' if name in ('hd_scl','hd_sda') else 'input' if name in ('clk_27m','reset_n','pixclk_in','vs_in','hs_in','de_in') else 'output'
  assert pins[name]==dict(Pin=pin,Direction=direction,Fixed='YES')
 result=dict(Schema='trained-cdc-postroute-connectivity-v1',VerifiedFFCount=len(expected),FFTypes=dict(Counter(e['primitive'] for e in expected.values())),VerifiedStageLinks=len(links),SameSiteStageLinks=sum(x['same_site'] for x in links),All81StageConnectionsVerified=True,Pins46Verified=True,Pins=pins,Registers=expected,StageLinks=links,LibrarySHA256=libs,FunctionalNetlistSHA256=sha(work/f'generate_netlist/{TOP}_sim.v'),SourceADFSHA256=sha(work/'input.adf'),NativeParserInMemoryTopAdapter=True,HardwareAccessed=False,FullCDCSignoff=False,MTBFQuantified=False)
 write(BASE/'connectivity-review.json',result)
 return expected,links

def prepare_scope():
 expected,links=connectivity();mapping=load(BASE/'mapping-review.json');by={e['expected_instance']:e for e in mapping['registers']}
 def pin(name,suffix):
  rows=by[name]['route_objects'];assert len(rows)==1 and suffix in rows[0]['pins'];return rows[0]['name']+'/'+suffix
 gray=[pin(f'input_status/geometry/{stem}_meta[{i}]','D') for stem,width in (('edge',32),('href',16),('vs',16)) for i in range(width)]
 gray += [pin('input_status/'+stem+'[0]','D') for stem in ('polarity_sync','vs_level_sync','hs_level_sync','timing_good_sync','timing_bad_sync')]
 gray += [pin('input_status/geometry/'+stem+'[0]','D') for stem in ('r_enable','source_running_sync','ack_sync','healthy_sync','failed_sync')]
 assert len(gray)==74
 spec=importlib.util.spec_from_file_location('mapping',ROOT/'results/hdmi-input-observer-20261030/audit-scripts/verify_mapping.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 routed=m.read_index(SOURCE/f'place_route/{TOP}_route.netlist')
 held=[key+'/D' for key,c in routed.items() if re.fullmatch(r'input_status/geometry/ref_snapshot\[\d+\]/[^/]+',key) and c['primitive']=='gopQ' and 'D' in c['pins']]
 assert len(held)==92
 reverse=[pin('input_status/geometry/request_sync[0]','D')]
 resets=[pin(prefix+'p_reset['+str(i)+']','RS') for prefix in ('input_status/','input_status/geometry/') for i in range(2)]
 second={pin(link['second'],'D') for link in mapping['stage_links']}
 assert not second.intersection(gray+held+reverse)
 groups=[dict(Name=name,LaunchClock=clock,Targets=sorted(targets),MaxDelayNS=8.0 if name!='pixel_resets' else None) for name,clock,targets in (('gray_and_scalar','input_pixel',gray),('held_snapshot','input_pixel',held),('reverse_request','board27',reverse),('pixel_resets','board27',resets))]
 work=BASE/'scoped-cdc';work.mkdir();shutil.copyfile(SOURCE/f'place_route/{TOP}_pnr.adf',work/'input.adf')
 (work/'dummy.v').write_text('module dummy; endmodule\n')
 plan=dict(Schema='trained-cdc-scope-plan-v1',SourceADF=str(SOURCE/f'place_route/{TOP}_pnr.adf'),SourceADFSHA256=sha(work/'input.adf'),RouteIndexSHA256=sha(SOURCE/f'place_route/{TOP}_route.netlist'),Groups=groups,NoSecondStageDataPins=True,HardwareAccessed=False,FullCDCSignoff=False)
 write(work/'scope-plan.json',plan)
 commands=[]
 for g in groups:
  expr='^('+'|'.join(re.escape(p) for p in g['Targets'])+')$'
  g['Query']='get_pins -hierarchical -regexp {'+expr+'}'
  commands += ['puts {TRAINED_SCOPE_QUERY_BEGIN '+g['Name']+'}',g['Query'],'puts {TRAINED_SCOPE_QUERY_END '+g['Name']+'}']
 script='set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\nadd_design '+n.lit(work/'dummy.v')+'\nif {[info script] ne {}} {\n mpnr -input '+n.lit(work/'input.adf')+'\n'+'\n'.join(' '+c for c in commands)+'\n puts {TRAINED_SCOPE_QUERY_COMPLETE}\n flush stdout\n}\n'
 (work/'query.tcl').write_text(script,encoding='ascii',newline='\n')
 result=n.run(work/'query.tcl',work,'query','TRAINED_SCOPE_QUERY_COMPLETE')
 assert not result['InputDrift']
 text=(work/'query-stdout.log').read_text(encoding='utf-8')
 records=[]
 for match in re.finditer(r"(?m)^I: Timing-5001: The pattern '(.*)' in command '(.*)' match (\d+) objects below: (.*)$",text):
  pattern,command,count,rendered=match.groups();names=rendered.split()
  assert int(count)==len(set(names))==len(names)
  records.append(dict(Pattern=pattern,Command=command,Count=int(count),NativeNames=names))
 assert len(records)==4
 for g,record in zip(groups,records):
  assert set(record['NativeNames'])=={'t:'+p for p in g['Targets']},(g,record)
 write(work/'scope-match-audit.json',dict(ExactGroupsMatched=True,TargetCounts=[len(g['Targets']) for g in groups],Records=records,InputADFUnchanged=sha(work/'input.adf')==plan['SourceADFSHA256'],HardwareAccessed=False))
 fdc=[]
 for g in groups:
  query=g['Query'];clock=g['LaunchClock']
  if g['Name']=='pixel_resets':fdc.append('set_false_path -from [get_clocks '+clock+'] -to ['+query+']')
  else:
   fdc+=['set_max_delay -datapath_only -from [get_clocks '+clock+'] -to ['+query+'] 8.0','set_false_path -hold -from [get_clocks '+clock+'] -to ['+query+']']
 (work/'scope.fdc').write_text('\n'.join(fdc)+'\n',encoding='ascii',newline='\n')
 print(json.dumps(dict(VerifiedFF=161,Links=81,SameSite=sum(x['same_site'] for x in links),Pins=46,GroupCounts=[len(g['Targets']) for g in groups],QueryPassed=True)))
if __name__=='__main__':prepare_scope()
