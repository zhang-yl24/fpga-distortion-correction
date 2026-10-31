"""Read-only final-netlist Boolean audit; no EDA or hardware operation."""
from pathlib import Path
from itertools import product
import hashlib,json,re,sys
ROOT=Path(r'D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction\distortion')
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tools'))
import audit_checked_io_netlist as n
NET=ROOT/'build/hdmi-uart-diagnostic/trained-review-1030-a/final-functional-export/generate_netlist/hdmi_uart_trained_diag_sim.v'
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
raw=NET.read_text(encoding='utf-8');cells,ports,drivers,libs=n.parse(raw.replace('module hdmi_uart_trained_diag','module board1080_top',1),n.LIBRARY)
def getff(prefix):
 found=[(name,c) for name,c in cells.items() if name.lstrip('\\').startswith(prefix+'/') and c['Type'] in n.FFS]
 assert len(found)==1,(prefix,found)
 return found[0]
def netname(text):return n.scalar(text)
FF={key:getff(prefix) for key,prefix in (
 ('outer_reset','input_status/p_reset[1]'),('geometry_reset','input_status/geometry/p_reset[1]'),
 ('polarity_known','input_status/polarity_known'),('vs_inactive','input_status/vs_inactive'),
 ('geometry_enable0','input_status/geometry/p_enable[0]'),('geometry_enable1','input_status/geometry/p_enable[1]'),
 ('geometry_vs_previous','input_status/geometry/vs_previous'),('geometry_frame_started','input_status/geometry/frame_started'))}
observed=set()
def constant(net):return n.constant(net)
def lut(c,port,values):
 init=int(c['Parameters']['INIT'].split("'h")[1],16)
 low=sum(values['I'+str(i)]<<i for i in range(5))
 z5a=(init>>low)&1;z5b=(init>>(low+32))&1
 fifth=values['I5'] if c['Parameters']['I5_TO_LUT']=='"TRUE"' else values['CIN']
 if port=='Z':return z5b if fifth else z5a
 if port=='Z5':return z5a
 if port=='COUT':
  c0=values['I5'] if c['Parameters']['I5_TO_CARRY']=='"TRUE"' else z5b
  return values['CIN'] if z5a else c0
 raise ValueError(port)
def lut_inputs(c,port):
 allpins=['CIN']+['I'+str(i) for i in range(6)]
 fixed={p:constant(netname(c['Ports'][p])) for p in allpins if constant(netname(c['Ports'][p])) is not None}
 free=[p for p in allpins if p not in fixed]
 support=[]
 for pin in free:
  other=[p for p in free if p!=pin]
  if any(lut(c,port,fixed|dict(zip(other,values))|{pin:0})!=lut(c,port,fixed|dict(zip(other,values))|{pin:1}) for values in product((0,1),repeat=len(other))):support.append(pin)
 return support,fixed
def value(net,variables):
 net=netname(net)
 if net in variables:return variables[net]
 if constant(net) is not None:return constant(net)
 assert len(drivers.get(net,[]))==1,net
 name,port=drivers[net][0];c=cells[name];observed.add(name)
 if c['Type'] in n.FFS:raise ValueError('unbound FF '+name+' Q='+net)
 if c['Type'] in ('V_BUF','V_IBUF'):return value(c['Ports']['I'],variables)
 if c['Type']=='V_USCM' and c['Parameters']['USCM_MODE']=='"BUF_A"':return value(c['Ports']['CLK0'],variables)
 if c['Type']=='V_INV':return 1-value(c['Ports']['I'],variables)
 if c['Type']=='V_LUT6CARRY':
  pins,fixed=lut_inputs(c,port);v={p:0 for p in ['CIN']+['I'+str(i) for i in range(6)]};v.update(fixed)
  for p in pins:v[p]=value(c['Ports'][p],variables)
  return lut(c,port,v)
 raise ValueError('unsupported cell '+str(c))
Q={key:netname(c['Ports']['Q']) for key,(name,c) in FF.items()}
def enumerated(target,keys,expected):
 count=0
 for states in product((0,1),repeat=len(keys)):
  params=dict(zip(keys,states));variables={(Q.get(k) or k):v for k,v in params.items()}
  actual=value(target,variables);wanted=int(bool(expected(params)))
  assert actual==wanted,(target,params,actual,wanted)
  count+=1
 return count
checks=[]
def check(name,target,keys,fn,expr):checks.append(dict(Name=name,TargetNet=target,EnumeratedRows=enumerated(target,keys,fn),ExpectedExpression=expr,Passed=True))
check('geometry normalized VS D',FF['geometry_vs_previous'][1]['Ports']['D'],['outer_reset','polarity_known','vs_inactive','vs_in'],lambda v:v['outer_reset'] and v['polarity_known'] and (v['vs_in']^v['vs_inactive']),'outer p_reset[1] AND polarity_known AND (vs_in XOR vs_inactive)')
check('geometry frame start CE',FF['geometry_frame_started'][1]['Ports']['CE'],['outer_reset','polarity_known','vs_inactive','vs_in','geometry_vs_previous'],lambda v:v['outer_reset'] and v['polarity_known'] and (v['vs_in']^v['vs_inactive']) and not v['geometry_vs_previous'],'normalized VS AND NOT geometry.vs_previous')
check('geometry source reset',FF['geometry_vs_previous'][1]['Ports']['SR'],['geometry_reset','geometry_enable1'],lambda v:not(v['geometry_reset'] and v['geometry_enable1']),'NOT (geometry.p_reset[1] AND geometry.p_enable[1])')
check('geometry enable D',FF['geometry_enable0'][1]['Ports']['D'],['outer_reset','polarity_known'],lambda v:v['outer_reset'] and v['polarity_known'],'outer p_reset[1] AND polarity_known')
check('geometry enable reset',FF['geometry_enable0'][1]['Ports']['SR'],['geometry_reset'],lambda v:not v['geometry_reset'],'NOT geometry.p_reset[1]')
for key in ('geometry_reset','geometry_enable0','geometry_enable1','geometry_vs_previous','geometry_frame_started'):
 assert value(FF[key][1]['Ports']['CK'],{'pixclk_in':0})==0
 assert value(FF[key][1]['Ports']['CK'],{'pixclk_in':1})==1
checks.append(dict(Name='geometry source FF clocks',ExpectedExpression='Buffered pixclk_in',Passed=True,FFCount=5))
assert FF['geometry_frame_started'][1]['Parameters']['SET_RESET']=='"RESET"'
assert value(FF['geometry_frame_started'][1]['Ports']['D'],{})==1
assert FF['geometry_vs_previous'][1]['Parameters']['SET_RESET']=='"RESET"'
inputs={str(path):sha(path) for path in (NET,Path(__file__),ROOT/'board/hdmi_uart_trained_diag.v',ROOT/'rtl/experimental/hdmi1080_input_status_trained.v',ROOT/'rtl/experimental/dvp_mode_admission_monitor_cdc.v',ROOT/'results/hdmi-trained-live-20261030/live-status-a.json')}
report=dict(Schema='trained-final-netlist-vs-geometry-static-review-v1',Passed=True,InputSHA256=inputs,LibrarySHA256=libs,Checks=checks,SelectedFFs={k:dict(Instance=name,Cell=c) for k,(name,c) in FF.items()},ObservedCombinationalCells={name:cells[name] for name in sorted(observed)},HardwareAccessed=False,EDAExecuted=False,InputVideoPassed=False,Limits='Static final-netlist Boolean connectivity only. C5 means reference-domain good-frame progress was not observed before startup timeout; packet fields cannot distinguish missing source VS/frame boundaries from missing fresh frame snapshots. No observed input waveform is reconstructed by this audit.')
with (OUT/'vs-geometry-static-review.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(dict(Passed=True,Checks=checks,ReviewSHA256=sha(OUT/'vs-geometry-static-review.json'))))
