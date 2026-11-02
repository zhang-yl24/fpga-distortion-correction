"""This direct candidate's own native Boolean/CDC/reset proposal, CPU only.

All logical roles are recovered from actual Q/Boolean connectivity. Unknown
sources and incomplete reset contracts block application. No old target, pin
count, crossing count or blanket hierarchy exception is inherited.
"""
import argparse
import ast
from collections import Counter,defaultdict
import itertools
import json
from pathlib import Path
import re
import tempfile

import hdmi_camera_direct_build as build
import hdmi_camera_direct_native as native
import hdmi_camera_raw_audit as raw
import hdmi_camera_raw_reset_audit as boolean
import audit_camera720_io_cdc as syntax
import camera720_stats_native_mux as mux
import camera720_cdc_clm as clm
import camera720_calibrated_cdc as calibrated
import audit_camera720_monitor as monitor

SELF=Path(__file__).resolve();TARGET=build.TARGET
SCHEMA='hdmi-camera-direct-native-audit-v1'
PYTHON=Path('D:/anaconda3/python.exe')
require,sha,read,write=build.require,build.sha,build.read,build.write
canon=raw.canon;parent=raw.parent
PADS=('vs_in','hs_in','de_in',*[f'{c}_in[{i}]'for c in 'rgb'for i in range(8)])
PERIODS={'board27':37.037037,'cfg_clk':100.0,'input_pixel':6.6667}
MODELS={
 'V_FFSYN':'ae4094a9a478a8ae9e5c67a0fcf982ff1e61a6e1e66588d849dd815d713c1f8c',
 'V_FFASYN':'e2fcf0de9085fd056c4daa14b2f73bd9235cdb52c90e68a2b58114024e048b24',
 'V_LUT6CARRY':'aa7ca57e8ce35845b0d61b02358d4a546facc52be65ec1ca5e68fe37a8bdcf98',
 'V_BUF':'774fb1a08820223eef6c66217e510d3a5eb328edebffb488a25467fe3e623836',
 'V_INV':'b1242601ab1cc80fbc152a149eaf3d73b140e541392d8af727260cadc7b378ef',
 'V_MUX2':'77540b86085dc742e5a5102578cb3f0a8753989b3b800d6a75f23e6d46515b95',
 'V_IBUF':'18814ef6d6f140b763c88871640498cacfaa420f4e5038b4fc751beedf69d4f4',
 'V_OBUFT':'cfc024e819351fe3dd04cabd22f2860c5eac6d528f413c78ab56b1b0f2dd8017',
 'V_GPLL':'1cbab1c034d8129f9164edeff911deb36a0201fb67cd8f336512e4ddc21d9ed0',
 'V_USCM':'3f35757740a6498560e3531ae7bfe44147b05016d6a80e504fc3f27934f486fc',
 'V_GRS':'42302a081bc28e3d89b99997abd11c3411b2d5afd71aa48d2444bc779c384762'}
MODELS['V_DRM18K_E1']='c7c271c7c372ccd9f7e3701db5a79a94e106ac28b7b735c60f3a8f43d78429da'
MODEL_ROOT=Path('D:/pango/PDS_2023.2/arch/vendor/pango/verilog/bsim')


def static_helpers(root=SELF):
    pending=[Path(root).resolve()];seen=set()
    while pending:
        path=pending.pop()
        if path in seen:continue
        seen.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            names=[]
            if isinstance(node,ast.Import):names=[n.name for n in node.names]
            elif isinstance(node,ast.ImportFrom):
                if node.module:names.append(node.module)
                if node.module=='tools':names.extend(n.name for n in node.names)
            for name in names:
                p=SELF.parent/(name.split('.')[-1]+'.py')
                if p.is_file()and p not in seen:pending.append(p)
    return sorted(seen)


class Graph(raw.Graph):
    def __init__(self,parsed,ports):
        super().__init__(parsed);self.ports=ports;self.expr_cache={};self.support_cache={};self.canonical_outputs=defaultdict(list)
        for n,c in self.cells.items():
            k=c['Primitive'];require(k in MODELS,'unknown direct native primitive: '+k)
            outputs=('Q',)if n in self.ff else {'V_LUT6CARRY':('Z','Z5','COUT'),'V_BUF':('Z',),'V_INV':('Z',),
                'V_MUX2':('Z',),'V_IBUF':('O',),'V_OBUFT':('O',),'V_GPLL':('CLKOUT0','CLKOUT1','CLKOUT2','CLKOUT3','CLKOUT4','CLKOUT5','LOCK'),
                'V_USCM':('CLKOUT',),'V_GRS':(),'V_DRM18K_E1':('DOA','DOB')}[k]
            for op in outputs:
                if c['Ports'].get(op):
                    for net in canon(c['Ports'][op]).strip('{}').split(','):self.canonical_outputs[net].append((n,op))
    def driver(self,net):
        ds=self.canonical_outputs.get(canon(net),[]);require(len(ds)==1,'unique direct native driver required: '+canon(net));return ds[0]
    def expression(self,net,active=()):
        net=canon(net)
        if net in ("1'b0","1'b1"):return ('constant',int(net[-1]))
        if net in self.expr_cache:return self.expr_cache[net]
        require(net not in active,'cycle in direct Boolean cone')
        if self.ports.get(net)=='INOUT':return ('variable','primary:'+net)
        ds=self.canonical_outputs.get(net,[])
        if not ds:
            require(self.ports.get(net)=='INPUT','undriven internal direct net: '+net)
            return ('variable','primary:'+net)
        require(len(ds)==1,'ambiguous direct Boolean driver');n,op=ds[0];c=self.cells[n];p=c['Ports'];k=c['Primitive']
        child=lambda value:self.expression(value,active+(net,))
        if n in self.ff:value=('variable','ff:'+n)
        elif k=='V_DRM18K_E1':value=('variable','rom:'+n+'/'+op)
        elif k=='V_GPLL'and op=='LOCK':value=('variable','pll_lock:'+n)
        elif k in ('V_BUF','V_IBUF'):value=child(p['I'])
        elif k=='V_INV':value=('not',child(p['I']))
        elif k=='V_MUX2':value=('mux',child(p['I0']),child(p['I1']),child(p['SEL']))
        elif k=='V_LUT6CARRY':
            init=c['Parameters']['INIT'];require(re.fullmatch(r"64'h[0-9a-fA-F_]+",init),'direct LUT initializer differs')
            number=int(init[4:].replace('_',''),16);inputs=tuple(child(p['I'+str(i)])for i in range(5))
            low=('lut',number&0xffffffff,inputs);high=('lut',number>>32,inputs)
            if op=='Z5':value=low
            elif op=='Z':value=('mux',low,high,child(p['I5']if c['Parameters'].get('I5_TO_LUT')=='"TRUE"'else p['CIN']))
            else:
                require(op=='COUT','unknown direct LUT output')
                value=('mux',child(p['I5'])if c['Parameters'].get('I5_TO_CARRY','"TRUE"')=='"TRUE"'else high,child(p['CIN']),low)
        else:raise ValueError('unreviewed direct Boolean primitive: '+n+'/'+op)
        self.expr_cache[net]=value;return value
    def support(self,net):
        net=canon(net)
        if net in self.support_cache:return self.support_cache[net]
        if net in ("1'b0","1'b1"):return set()
        if self.ports.get(net)=='INOUT':return {'primary:'+net}
        ds=self.canonical_outputs.get(net,[])
        if not ds:
            require(self.ports.get(net)=='INPUT','undriven internal direct support: '+net);return {'primary:'+net}
        require(len(ds)==1,'ambiguous direct support');n,op=ds[0];c=self.cells[n];k=c['Primitive'];p=c['Ports']
        if n in self.ff:value={'ff:'+n}
        elif k=='V_DRM18K_E1':value={'rom:'+n+'/'+op}
        elif k=='V_GPLL'and op=='LOCK':value={'pll_lock:'+n}
        else:
            dependencies=[p['I']]if k in ('V_BUF','V_INV','V_IBUF')else mux.inputs(c,op)
            value=set.union(set(),*(self.support(x)for x in dependencies))
        self.support_cache[net]=value
        return self.support_cache[net]


def graph(text,build_dir=None,ports=None):
    if isinstance(build_dir,dict):ports=build_dir
    elif build_dir is not None:ports=build.top_ports((Path(build_dir)/'compiled'/build.TOP).read_text(encoding='utf-8-sig'))
    require(ports is not None,'direct native graph needs its bound actual port declarations')
    require(re.findall(r'(?m)^module\s+(\w+)',text)==[TARGET],'one flat actual direct top required')
    adapted=re.sub(r'(?m)^(module\s+)'+TARGET+r'\b',r'\g<1>'+syntax.prep.TARGET,text,count=1)
    return Graph(syntax.functional(adapted),ports)


def expressions(g,name):return {pin:g.expression(value)for pin,value in g.ff[name]['Ports'].items()if pin in ('D','CE','SR')}


def next_q(g,name,values):
    c=g.ff[name];p=c['Parameters'];e=expressions(g,name)
    require(c['Primitive']in ('V_FFSYN','V_FFASYN')and p.get('LRS_EN')in ('"TRUE"','"FALSE"')and
        p.get('SET_RESET')in ('"SET"','"RESET"'),'unknown native FF transition priority')
    if p['LRS_EN']=='"TRUE"'and boolean.evaluate(e['SR'],values):return int(p['SET_RESET']=='"SET"')
    return boolean.evaluate(e['D'],values)if boolean.evaluate(e['CE'],values)else values['ff:'+name]


def truth(g,name,fixed=None,maximum=14):
    fixed=fixed or {};e=expressions(g,name)
    variables=set.union({'ff:'+name},*(boolean.leaves(v)for v in e.values()))-set(fixed)
    require(len(variables)<=maximum,'native next-Q truth table exceeds bounded review size: '+name)
    variables=sorted(variables)
    return [({'Inputs':dict(zip(variables,bits))|fixed,'NextQ':next_q(g,name,dict(zip(variables,bits))|fixed)})
        for bits in itertools.product((0,1),repeat=len(variables))]


def output_net(g,pad):
    n,p=g.driver(pad);c=g.cells[n];require(c['Primitive']=='V_OBUFT'and p=='O','direct output has no OBUFT: '+pad)
    t=g.expression(c['Ports']['T']);require(not boolean.leaves(t)and boolean.evaluate(t,{})==0,'output is not constantly enabled: '+pad)
    return c['Ports']['I'],{'Pad':pad,'Buffer':n,'TExpression':t,'InputNet':canon(c['Ports']['I'])}


def literal_led_aliases(g,source):
    clean=re.sub(r'/\*.*?\*/|//[^\n]*','',source,flags=re.S)
    matches=re.findall(r'assign\s+led\s*=\s*\{([^{}]+)\}\s*;',clean)
    require(len(matches)==1,'one direct literal LED assignment required');parts=matches[0].split(',');require(len(parts)==8,'eight direct LED bits required')
    aliases={};rows=[]
    for i,expr in enumerate(reversed(parts)):
        logical=canon(expr.strip())
        if not re.fullmatch(r'[A-Za-z_]\w*(?:\[\d+\])?',logical):continue
        net,proof=output_net(g,f'led[{i}]');leaves=g.support(net)
        if len(leaves)==1 and next(iter(leaves)).startswith('ff:'):
            name=next(iter(leaves))[3:];aliases[logical]=name
            rows.append({'Logical':logical,'FF':name,'ActualQ':canon(g.ff[name]['Ports']['Q']),'LiteralAssignment':expr.strip(),**proof})
    return aliases,rows


def unique_q(g,logical,aliases=None):
    if aliases and logical in aliases:return aliases[logical]
    values=[n for n,c in g.ff.items()if canon(c['Ports']['Q'])==logical]
    require(len(values)==1,'one actual Q for logical role required: '+logical);return values[0]


def sampler_inventory(g):
    direct={pad:[]for pad in PADS};cones={}
    for n,c in sorted(g.ff.items()):
        for pin in ('D','CE','SR'):
            support=g.support(c['Ports'][pin]);cones[n,pin]=support
            for pad in PADS:
                if 'primary:'+pad in support:direct[pad].append({'FF':n,'Pin':pin})
    rows=[];releases=set()
    for pad in PADS:
        targets=direct[pad];require(len(targets)==1 and targets[0]['Pin']=='D','pad bypasses a unique D-only native sampler: '+pad)
        n=targets[0]['FF'];require(g.ff[n]['Primitive']=='V_FFSYN'and g.clock(g.ff[n]['Ports']['CK'])['Domain']=='input_pixel','sampler primitive/clock differs')
        variables=set.union(set(),*(g.support(g.ff[n]['Ports'][pin])for pin in ('D','CE','SR')))
        candidates={v[3:]for v in variables if v.startswith('ff:')and v!='ff:'+n};require(len(candidates)==1,'sampler release is not one FF: '+pad)
        release=next(iter(candidates));table=truth(g,n);choices=[]
        for inactive,inverted in itertools.product((0,1),repeat=2):
            if all(r['NextQ']==((r['Inputs']['primary:'+pad]if r['Inputs']['ff:'+release]!=inactive else 0)^inverted)for r in table):choices.append((inactive,inverted))
        require(len(choices)==1,'sampler native truth does not capture exactly one pad with local reset: '+pad)
        inactive,inverted=choices[0];releases.add((release,inactive))
        rows.append({'Pad':pad,'SamplerFF':n,'ActualQ':canon(g.ff[n]['Ports']['Q']),'Placement':g.g['FFPlacement'][n],
            'LocalReleaseFF':release,'InactiveReleasePhysicalQ':inactive,'NativeQInvertsSample':bool(inverted),
            'TruthTable':table,'DirectPrimaryConsumers':targets,'EveryReleasedPCLKCapturesPad':True,'LocalSynchronousResetVerified':True})
    require(len(releases)==1 and len({r['SamplerFF']for r in rows})==len(PADS),'common source sampling stage is not unique')
    return {'SourceSamplingIsolatedVerified':True,'ActualSamplerCount':len(rows),'DeclaredRawBundleBits':len(PADS),
        'Pads':rows,'NonSamplerDirectPrimaryConsumers':[],'ExternalACAccepted':False,'OpticalRGBVerified':False},next(iter(releases))


def release_chain(g,last,inactive):
    c=g.ff[last];require(c['Primitive']=='V_FFASYN','local release is not asynchronously asserted')
    support={v[3:]for v in g.support(c['Ports']['D'])if v.startswith('ff:')and v!='ff:'+last}
    require(len(support)==1,'local release second stage lacks one actual predecessor');first=next(iter(support));a=g.ff[first]
    require(a['Primitive']=='V_FFASYN'and g.clock(a['Ports']['CK'])==g.clock(c['Ports']['CK']),'release stages use different actual clocks')
    first_inactive=int(a['Parameters']['SET_RESET']=='"SET"')
    require(c['Parameters']['LRS_EN']==a['Parameters']['LRS_EN']=='"TRUE"'and
        int(c['Parameters']['SET_RESET']=='"SET"')==inactive and
        a['Parameters']['INIT']=="1'b"+str(first_inactive)and c['Parameters']['INIT']=="1'b"+str(inactive),
        'release chain native INIT/reset encoding differs')
    sr0=g.expression(a['Ports']['SR']);sr1=g.expression(c['Ports']['SR']);variables=sorted(boolean.leaves(sr0)|boolean.leaves(sr1))
    require(len(variables)<=8 and all(boolean.evaluate(sr0,dict(zip(variables,b)))==boolean.evaluate(sr1,dict(zip(variables,b)))
        for b in itertools.product((0,1),repeat=len(variables))),'release-stage reset functions differ')
    def operational_table(n):
        expr=expressions(g,n);v=set.union({'ff:'+n},*(boolean.leaves(x)for x in expr.values()))
        require(len(v)<=12,'release truth table exceeds native review bound');result=[]
        for bits in itertools.product((0,1),repeat=len(v)):
            assignment=dict(zip(sorted(v),bits))
            if boolean.evaluate(expr['SR'],assignment):continue
            result.append({'Inputs':assignment,'NextQ':next_q(g,n,assignment)})
        return result
    ft,lt=operational_table(first),operational_table(last)
    require(ft and all(r['NextQ']==1-first_inactive for r in ft),'release first stage does not advance unconditionally')
    require(lt and all((r['NextQ']^inactive)==(r['Inputs']['ff:'+first]^first_inactive)for r in lt),'release second stage does not follow actual first Q')
    fanout={(n,pin)for n,c in g.ff.items()for pin in ('D','CE','SR')if 'ff:'+first in g.support(c['Ports'][pin])}
    require(fanout=={(last,'D')},'release first stage feeds a consumer before the second stage')
    return {'First':first,'Second':last,'InactivePhysicalQ':[first_inactive,inactive],
        'NativeParameters':[a['Parameters'],c['Parameters']],'FirstTruthTable':ft,'SecondTruthTable':lt,
        'SameClockRoot':True,'CommonResetFunctionVerified':True,'NativeINITMatchesInactive':True,
        'FirstStageOnlyFeedsSecondStage':True,
        'FirstToSecondInterstageTimingAccepted':False,'AnalogMetastabilityAccepted':False}


def scalar_chain(g,first,second,release,label):
    a,b=g.ff[first],g.ff[second];clock=g.clock(a['Ports']['CK'])
    require(clock==g.clock(b['Ports']['CK']),'scalar stages use different native clock roots')
    ia=int(a['Parameters']['SET_RESET']=='"SET"');ib=int(b['Parameters']['SET_RESET']=='"SET"')
    require(a['Parameters']['INIT']=="1'b"+str(ia)and b['Parameters']['INIT']=="1'b"+str(ib),'scalar INIT differs from inactive reset encoding')
    rt,ri=release;second_table=truth(g,second);first_table=truth(g,first)
    for row in second_table:
        values=row['Inputs'];sr=boolean.evaluate(g.expression(b['Ports']['SR']),values)if b['Parameters']['LRS_EN']=='"TRUE"'else 0
        expected=0 if sr else (values['ff:'+first]^ia)&(values['ff:'+rt]^ri)
        require((row['NextQ']^ib)==expected,'scalar second stage is not first AND local release: '+label)
    for row in first_table:
        if not(row['Inputs']['ff:'+rt]^ri):require(row['NextQ']==ia,'inactive local release does not clear scalar first stage')
    consumers=[]
    for n,c in g.ff.items():
        for pin in ('D','CE','SR'):
            if 'ff:'+first in g.support(c['Ports'][pin]):consumers.append((n,pin))
    require(set(consumers)=={(second,'D')},'scalar first stage escapes unique second D: '+label)
    try:ordinary=g.chain(first,second,label,g.ff[rt]['Ports']['Q'])
    except ValueError:
        ordinary={'First':first,'Second':second,'FirstPlacement':g.g['FFPlacement'][first],
            'SecondPlacement':g.g['FFPlacement'][second],'SameSite':g.g['FFPlacement'][first]['Site']==g.g['FFPlacement'][second]['Site'],
            'SameBLE':g.g['FFPlacement'][first]==g.g['FFPlacement'][second],'NativeQueries':[],
            'ExactNativeInterstageQueryRequired':True}
    return {**ordinary,'Family':label,'DestinationClock':clock['Domain'],'ClockRootsIdentical':True,
        'FirstStageOnlyFeedsSecondStage':True,'NativeTruthVerified':True,'FirstTruthTable':first_table,'SecondTruthTable':second_table,
        'LocalReleaseFF':rt,'LocalReleaseInactivePhysicalQ':ri,'NativeStageInactiveQ':[ia,ib],
        'InterstageTimingAccepted':False,'AnalogMetastabilityAccepted':False}


def output_review(g,sampling,ready_second,input_release,sampler_release):
    bypad={r['Pad']:r for r in sampling['Pads']};rows=[]
    for pad in PADS:
        if pad=='de_in':continue
        out={'vs_in':'vs_out','hs_in':'hs_out'}.get(pad,pad.replace('_in','_out'))
        net,buffer=output_net(g,out);expr=g.expression(net);row=bypad[pad]
        require(g.support(net)=={'ff:'+row['SamplerFF']},'raw output bypasses or mixes common sampled bits: '+pad)
        require(all(boolean.evaluate(expr,{'ff:'+row['SamplerFF']:q})==(q^int(row['NativeQInvertsSample']))for q in (0,1)),
            'output physical polarity differs from sampled raw bit: '+pad)
        rows.append({'InputPad':pad,'OutputPad':out,'SamplerFF':row['SamplerFF'],'NativeLogicalPolarityVerified':True,**buffer})
    de_net,de_buffer=output_net(g,'de_out');de_expr=g.expression(de_net);de_ff=bypad['de_in']['SamplerFF']
    rf,ri=input_release;sf,si=sampler_release
    known={de_ff,ready_second,rf,sf};sources={v[3:]for v in g.support(de_net)if v.startswith('ff:')}
    remaining=sources-known;require(len(remaining)==1,'DE valid-hold source not uniquely recovered');valid=next(iter(remaining))
    valid_table=truth(g,valid);encodings=[inverted for inverted in (0,1)if all(
        r['NextQ']==((r['Inputs']['ff:'+sf]^si)^inverted)for r in valid_table)]
    require(len(encodings)==1,'sample valid hold is not the actual local sampler release');vi=encodings[0]
    variables=sorted(boolean.leaves(de_expr));require(set(variables)=={'ff:'+n for n in sources}and len(variables)<=6,'DE has unrelated source/control')
    ready_inactive=int(g.ff[ready_second]['Parameters']['SET_RESET']=='"SET"');de_i=int(bypad['de_in']['NativeQInvertsSample'])
    count=0
    for bits in itertools.product((0,1),repeat=len(variables)):
        v=dict(zip(variables,bits));expected=(v['ff:'+de_ff]^de_i)&(v['ff:'+valid]^vi)&(v['ff:'+ready_second]^ready_inactive)&(v['ff:'+rf]^ri)&(v['ff:'+sf]^si)
        require(boolean.evaluate(de_expr,v)==expected,'native DE lacks exact valid/ready/release common sample qualification');count+=1
    clock_net,clock_buffer=output_net(g,'pix_clk');clock=g.clock(clock_net)
    require(clock['Domain']=='input_pixel'and clock['Root']=='pixclk_in'and all(
        r['Primitive']in ('V_BUF','V_IBUF','V_USCM')for r in clock['Trace']),'forwarded output clock is not the continuous input clock')
    return {'AllRGB24AndHSVSShareSameSample':True,'OutputBits':rows,'DEQualificationVerified':True,
        'DETruthAssignments':count,'DEBuffer':de_buffer,'SampleValidFF':valid,'SampleValidNativeInversion':vi,
        'SampleValidTruth':valid_table,'ForwardedClockContinuousVerified':True,'ForwardedClock':clock,
        'ForwardedClockBuffer':clock_buffer,'ExternalACAccepted':False}


def rom_inventory(g):
    rows=[]
    for n,c in g.cells.items():
        if c['Primitive']!='V_DRM18K_E1':continue
        p=c['Ports'];v=c['Parameters']
        require(v['RAM_MODE']=='"SIMPLE_DUAL_PORT"'and v['DATA_WIDTH_B']=='32'and
            v['DOA_REG']==v['DOB_REG']=='0'and v['RST_TYPE']=='"SYNC"','unreviewed direct table ROM mode')
        for pin in ('WEA','WEB'):
            e=g.expression(p[pin]);require(not boolean.leaves(e)and boolean.evaluate(e,{})==0,'direct command table memory is writable')
        ca,cb=g.clock(p['CLKA']),g.clock(p['CLKB']);require(ca==cb and cb['Domain']=='cfg_clk','direct command table clock differs')
        for pin in ('ADDRA','ADDRB'):
            for net in canon(p[pin]).strip('{}').split(','):
                if net in ("1'b0","1'b1"):continue
                require(all(s.startswith('ff:')and g.clock(g.ff[s[3:]]['Ports']['CK'])['Domain']=='cfg_clk'for s in g.support(net)),
                    'ROM address crosses an unreviewed clock')
        rows.append({'Cell':n,'Primitive':c['Primitive'],'Nature':'immutable_initialization_ROM_synchronous_read',
            'OutputClock':'cfg_clk','WideSDPBothOutputsUseCLKB':True,'BothWriteEnablesConstantZero':True,
            'NativeModelBound':True,'AllAddressSourcesSameCfgClock':True,'Parameters':v})
    return rows


def pin_inventory(plan,g,build_dir,watched):
    paths=[build_dir/'compiled'/build.TOP,build_dir/'compiled'/build.FDC,
        build_dir/'device_map'/(TARGET+'.pcf'),build_dir/'place_route'/(TARGET+'_prr_route_optimize.prt')]
    for p in paths:native.add(watched,p)
    declared=build.top_ports(paths[0].read_text(encoding='utf-8-sig'));fdc=build.pins.fdc_pins(paths[1].read_text())
    pcf=build.pins.pcf_pins(paths[2].read_text());_,routed=build.pins.routed_pads(paths[3].read_text())
    require(set(declared)==set(fdc)==set(pcf)==set(routed),'complete actual direct declared/FDC/PCF/route pins differ')
    rows=[]
    for port,direction in sorted(declared.items()):
        require(fdc[port]['DIRECTION']==direction==routed[port]['Direction']and fdc[port]['LOC']==routed[port]['Pad'],'direct pin mapping differs: '+port)
        require(pcf[port]=={k:v for k,v in fdc[port].items()if k!='DIRECTION'},'native direct pin attributes differ: '+port)
        connections=[{'Cell':n,'Pin':p,'Primitive':c['Primitive']}for n,c in g.cells.items()for p,v in c['Ports'].items()if canon(v)==port]
        require(connections,'declared direct pad has no actual consumer/driver: '+port)
        rows.append({'Port':port,'Direction':direction,'Attributes':pcf[port],'Route':routed[port],'FunctionalConnections':connections})
    return {'Declared':len(declared),'Routed':len(routed),'Active':len(routed),'DeclaredPortCount':len(declared),
        'ActivePortCount':len(routed),'UnusedRGBPorts':[],'Inventory':rows,'NativeElectricalParametersVerified':False}


class Mapper(clm.Mapper):
    def support(self,net,active=()):return {v[3:]for v in self.g.support(net)if v.startswith('ff:')}


def native_graph(scope):
    watched={};plan_path=Path(scope['BuildPlan']['Path']);build_dir=plan_path.parent
    for key in ('BuildPlan','ExportReceipt','RouteReceipt','NativeNetlist','RouteDump'):
        native.add(watched,scope[key]['Path'],scope[key]['SHA256'])
    g=graph(Path(scope['NativeNetlist']['Path']).read_text(encoding='utf-8-sig'),build_dir)
    placements=clm.placed_luts(Path(scope['NativeNetlist']['Path']).read_text(encoding='utf-8-sig'),g)
    parents={parent(n)for n in g.ff}|{n.rsplit('/',2)[0]for n in placements}
    with tempfile.TemporaryDirectory(prefix='direct-native-route-')as temporary:
        normalized=Path(temporary)/'route.adif';calibrated.normalize_source_locations(scope['RouteDump']['Path'],normalized)
        route=clm.endpoints.route_objects(normalized,parents)
    return g,route,Mapper(g,route,placements),watched


def possible(expr,fixed):
    kind=expr[0]
    if kind=='constant':return {expr[1]}
    if kind=='variable':return {fixed[expr[1]]}if expr[1]in fixed else {0,1}
    if kind=='not':return {1-v for v in possible(expr[1],fixed)}
    if kind=='mux':return set.union(set(),*(possible(expr[1+s],fixed)for s in possible(expr[3],fixed)))
    return {(expr[1]>>sum(v<<i for i,v in enumerate(bits)))&1
        for bits in itertools.product(*(possible(n,fixed)for n in expr[2]))}


def pll_review(g):
    cells=[(n,c)for n,c in g.cells.items()if c['Primitive']=='V_GPLL'];require(len(cells)==1,'one native configuration PLL required')
    n,c=cells[0];p=c['Ports'];v=c['Parameters']
    require(g.clock(p['CLKIN1'])['Domain']=='board27'and p['CLKIN_SEL']=="1'b0"and
        v['INTERNAL_FB']=='"CLKOUTF"'and v['EXTERNAL_FB']=='"DISABLE"'and v['SSC_MODE']=='"DISABLE"','unreviewed direct PLL clock source/feedback')
    for key in ('APB_EN','APB_SEL','APB_WRITE','DPS_EN','PLL_PWD','RST'):
        e=g.expression(p[key]);require(possible(e,{})=={0},'configuration PLL has dynamic control: '+key)
    require(all(value=='"FALSE"'for key,value in v.items()if key.startswith('CLK_DPS')or key.endswith('_SYN_EN')),'PLL phase/sync reconfiguration enabled')
    period=PERIODS['board27']*float(v['STATIC_RATIOI'])*float(v['STATIC_RATIO0'])/(float(v['STATIC_RATIOM'])*float(v['STATIC_RATIOF']))
    require(abs(period-PERIODS['cfg_clk'])<0.00001,'native PLL static ratio disagrees with generated FDC clock')
    return {'Cell':n,'InputClock':'board27','OutputClock':'cfg_clk','NativeStaticPeriodNS':period,
        'DynamicReconfigurationDisabled':True,'RelatedClockPathsRemainTimed':True,'Parameters':v}


def derive(build_plan,export_receipt,route_receipt):
    build_plan=Path(build_plan).resolve();export_receipt=Path(export_receipt).resolve();route_receipt=Path(route_receipt).resolve()
    watched={}
    for p in static_helpers():native.add(watched,p)
    native.add(watched,PYTHON);initial=dict(watched);plan=build.validate(build_plan)
    exported,inputs=native.bind_receipt(export_receipt);native.merge(watched,inputs)
    routed,inputs=native.bind_receipt(route_receipt);native.merge(watched,inputs)
    require(exported['Mode']=='export'and routed['Mode']in ('report','query')and
        all(exported[k]==routed[k]for k in ('BuildPlanSHA256','SourceADFSHA256','SourceADF'))and
        exported['BuildPlanSHA256']==sha(build_plan),'direct native export/route lineage differs')
    net=native.artifact(export_receipt,exported,TARGET+'_sim.v');dump=native.artifact(route_receipt,routed,'route-dump.txt')
    refs={'BuildPlan':native.ref(build_plan),'ExportReceipt':native.ref(export_receipt),'RouteReceipt':native.ref(route_receipt),
        'SourceADF':native.ref(exported['SourceADF']),'NativeNetlist':native.ref(net),'RouteDump':native.ref(dump)}
    g,route,mapper,inputs=native_graph(refs);native.merge(watched,inputs)
    for kind in sorted({c['Primitive']for c in g.cells.values()}):native.add(watched,MODEL_ROOT/(kind+'.v'),MODELS[kind])
    source=build_plan.parent/'compiled'/build.TOP;native.add(watched,source);source_text=source.read_text(encoding='utf-8-sig')
    aliases,alias_rows=literal_led_aliases(g,source_text)
    pins=pin_inventory(plan,g,build_plan.parent,watched);pll=pll_review(g);roms=rom_inventory(g)
    sampling,sampler_release=sampler_inventory(g);sampler_chain=release_chain(g,*sampler_release)
    input_release=(unique_q(g,'input_reset[1]'),0);input_chain=release_chain(g,*input_release)
    ref_release=(unique_q(g,'ref_reset[1]'),0);ref_chain=release_chain(g,*ref_release)
    chains=[]
    for family in ('cfg_lock_ref','rx_done_ref','tx_done_ref','cfg_failed_ref','ready_pix'):
        first=unique_q(g,family+'[0]',aliases);second=unique_q(g,family+'[1]',aliases)
        chains.append(scalar_chain(g,first,second,input_release if family=='ready_pix'else ref_release,family))
    # The IIC pad synchronizers stay in cfg_clk. This classification is of
    # actual external-pad support, never a wildcard over controller FFs.
    iic=[]
    for pad in ('hd_scl','hd_sda'):
        targets=[(n,pin)for n,c in g.ff.items()for pin in ('D','CE','SR')if 'primary:'+pad in g.support(c['Ports'][pin])]
        require(len(targets)==1 and targets[0][1]=='D','IIC async pad does not terminate only at one first D')
        first=targets[0][0];seconds=[n for n,c in g.ff.items()if n!=first and 'ff:'+first in g.support(c['Ports']['D'])]
        require(len(seconds)==1,'IIC pad lacks unique second sampled FF')
        second=seconds[0];chain=g.chain(first,second,pad+' async input')
        require(chain['DestinationClock']=='cfg_clk','IIC sampled chain is not configuration-domain')
        chain.update(Family=pad,NativeTruthVerified=True,InterstageTimingAccepted=False,AsynchronousPad=pad);iic.append(chain)
    chains+=iic
    ready=next(c for c in chains if c['Family']=='ready_pix');ref_ready=unique_q(g,'ref_ready',aliases)
    output=output_review(g,sampling,ready['Second'],input_release,sampler_release)
    power=unique_q(g,'power_ready');power_q='ff:'+power
    power_native=g.ff[power];require(power_native['Parameters']['INIT']=="1'b0"and power_native['Parameters']['SET_RESET']=='"RESET"','power-ready inactive native encoding differs')
    # Cofactor is stronger than merely observing a source-name match.
    key_release=unique_q(g,'key_reset_sync[1]');key_chain=release_chain(g,key_release,0)
    require(all(possible(g.expression(g.ff[n]['Ports']['SR']),{'primary:reset_n':1})=={0}for n in (key_chain['First'],key_chain['Second'])),
        'key release can asynchronously reassert without common reset_n')
    fixed={power_q:1,'primary:reset_n':1,'ff:'+key_release:1};pe=expressions(g,power)
    states={d if ce else 1 for d,ce in itertools.product(possible(pe['D'],fixed),possible(pe['CE'],fixed))}
    require(possible(pe['SR'],fixed)=={0}and states=={1},'native power_ready may deassert in a live common epoch')
    common_reset={'PowerReadyFF':power,'NativePowerReadyMonotonicWhenResetNHigh':True,
        'ResetNAssertsWholeEpoch':True,'SourceRTL':native.ref(source),'AsynchronousAssertion':True,
        'KeyReleaseChain':key_chain,'KeyReleaseStaysActiveUntilCommonReset':True,
        'NoIndependentInputResetOrRuntimeReset':True,'ReleaseChains':[input_chain,sampler_chain],
        'ReadyChain':ready,'ExternalClockStopRecoveryClaimed':False}
    reset_targets={input_chain['First'],input_chain['Second'],sampler_chain['First'],sampler_chain['Second'],ready['First'],ready['Second']}
    guard_proofs={}
    for n in reset_targets:
        sr=g.expression(g.ff[n]['Ports']['SR']);vars=sorted(boolean.leaves(sr))
        require(set(vars)=={power_q,'primary:reset_n'},'input reset has unrelated sources')
        require(all(boolean.evaluate(sr,dict(zip(vars,b)))==int(not(dict(zip(vars,b))[power_q]and dict(zip(vars,b))['primary:reset_n']))
            for b in itertools.product((0,1),repeat=len(vars))),'input reset is not the exact common assertion')
        proof={'CommonResetFunctionVerified':True,'PowerReadyMonotonicVerified':True,'NativeInactiveGuardVerified':True}
        if n in (ready['First'],ready['Second']):
            table=truth(g,n,{'ff:'+input_release[0]:input_release[1]});inactive=int(g.ff[n]['Parameters']['SET_RESET']=='"SET"')
            require(all(r['NextQ']==inactive for r in table),'business ready stage lacks unconditional local inactive reset')
            proof.update(NativeForcedQ=inactive,LocalReleaseFF=input_release[0],LocalReleaseInactiveQ=input_release[1],NativeTruthTable=table)
        else:proof['Role']='proved two-stage asynchronous-assert/synchronous-release chain'
        guard_proofs[n]=proof
    firsts={c['First']:c for c in chains};rows=[];nonff=[];clock_counts=Counter()
    for n,c in g.ff.items():clock_counts[g.clock(c['Ports']['CK'])['Domain']]+=1
    for d,c in sorted(g.ff.items()):
        dc=g.clock(c['Ports']['CK'])['Domain'];require(dc in PERIODS,'unknown direct FF clock')
        for pin in ('D','CE','SR'):
            for item in sorted(g.support(c['Ports'][pin])):
                if not item.startswith('ff:'):
                    nonff.append({'Source':item,'DestinationFF':d,'DestinationPin':pin,'DestinationClock':dc});continue
                s=item[3:];sc=g.clock(g.ff[s]['Ports']['CK'])['Domain']
                if sc==dc:continue
                excepted=False;role='related_cfg_board_path_remains_timed'
                if dc=='input_pixel':
                    if pin=='D'and d==ready['First']and s==ref_ready:role='ready_scalar_first_stage';excepted=True
                    elif pin=='SR'and d in reset_targets and s==power:role='common_epoch_input_reset';excepted=True
                    else:raise ValueError('unclassified direct input-domain relationship: '+s+' -> '+d+'/'+pin)
                else:require({sc,dc}=={'board27','cfg_clk'},'unknown foreign direct domain pair')
                row={'SourceFF':s,'DestinationFF':d,'DestinationPin':pin,'SourceClock':sc,'DestinationClock':dc,
                    'SourceLogicalQ':canon(g.ff[s]['Ports']['Q']),'DestinationLogicalQ':canon(c['Ports']['Q']),
                    'Role':role,'ExceptionProposed':excepted,'TimedWithoutException':not excepted,'ProtocolProved':True}
                if excepted:
                    row=mapper.map(row);slot=re.search(r'/(FFAPP|FF)([0-3])/FF$',s);require(slot is not None,'unknown native source FF slot')
                    row.update(SourceNativeCLKNet=route['Pins'][parent(s),'CLK'],SourcePhysicalQ=row['SourcePlacement']['Site']+
                        ('/CR'if slot[1]=='FFAPP'else'/Q')+slot[2])
                rows.append(row)
    data={};resets={}
    for i,row in enumerate(rows):
        if not row['ExceptionProposed']:continue
        table=resets if row['Role']=='common_epoch_input_reset'else data
        for boundary in row['NativeBoundaries']:
            key=row['SourceNativeClockPin'],row['SourceNativeOutputPin'],boundary['Endpoint']
            scope=table.setdefault(key,{'FromCLK':key[0],'LaunchQ':key[1],'Endpoint':key[2],'Role':row['Role'],
                'RelationshipIndexes':[],'NativeObjects':{k:[]for k in ('SourceFFs','DestinationFFs','SourcePhysicalQ','SourceCLKNet')}})
            scope['RelationshipIndexes'].append(i)
            for k,value in [('SourceFFs',row['SourceFF']),('DestinationFFs',row['DestinationFF']),('SourcePhysicalQ',row['SourcePhysicalQ']),('SourceCLKNet',row['SourceNativeCLKNet'])]:scope['NativeObjects'][k].append(value)
            if table is resets:
                scope['GuardAccepted']=True
                scope.setdefault('GuardProof',{'Destinations':{},'CommonEpoch':common_reset})['Destinations'][row['DestinationFF']]=guard_proofs[row['DestinationFF']]
            else:scope.update(MaximumNS=PERIODS['input_pixel'],BoundBasis='One destination PCLK period to scalar first D; proved two-stage level synchronization; stage1->2 remains ordinarily timed')
    for scope in list(data.values())+list(resets.values()):scope['NativeObjects']={k:sorted(set(v))for k,v in scope['NativeObjects'].items()}
    for row in sampling['Pads']:
        row.update(SamplerClock='input_pixel',SamplerClockRoot=g.clock(g.ff[row['SamplerFF']]['Ports']['CK'])['Root'],
            SamplerEdge='posedge',LogicalD=g.ff[row['SamplerFF']]['Ports']['D'],ActualPhysicalSite=row['Placement']['Site'])
    for p,h in initial.items():require(sha(p)==h,'direct audit helper changed while deriving')
    value={'Schema':SCHEMA,'Target':TARGET,**refs,'Pins':pins,'ClockDefinitions':{'PeriodsNS':PERIODS,'ConfigurationPLL':pll},
        'ClockTopology':{'FFCountsByClock':dict(sorted(clock_counts.items()))},'ActualFFs':len(g.ff),'ActualCells':len(g.cells),
        'PrimitiveCounts':dict(Counter(c['Primitive']for c in g.cells.values())),'PrimitiveBoundaries':roms,
        'SourceSampling':sampling,'LogicalAliasRecovery':alias_rows,'Synchronizers':chains,'ReleaseChains':[ref_chain,input_chain,sampler_chain],
        'OutputPathReview':output,'ForeignRelationships':rows,'NonFFSequentialSupport':nonff,'LocalResetGuards':common_reset,
        'DataScopes':[data[k]for k in sorted(data)],'ResetScopes':[resets[k]for k in sorted(resets)],
        'NativeAcceptance':{'ResetAccepted':True,'ProtocolSafetyAccepted':True,'SourceSamplingIsolatedVerified':True,'Missing':[],'Violations':[]},
        'Blockers':[],'ProposalReady':True,'ConstraintsApplied':False,'TimingAccepted':False,'HardwareReleaseAllowed':False,
        'ExternalACAccepted':False,'HardwareAccessed':False,'BitstreamRequested':False,
        'InputSHA256':{str(p):h for p,h in sorted(watched.items(),key=lambda item:str(item[0]))},
        'Limits':'Native Boolean source/protocol/reset exception proposal. Only unrelated board27-to-input scalar/reset scopes. '
            'Related cfg/board paths remain timed; all native queries, ordinary interstage timing, electrical checks and final unchanged-graph full STA remain required. No analog or optical acceptance.'}
    return value,watched


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('build-plan','export-receipt','route-receipt','output-dir'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args(argv);out=build.work_path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    value,_=derive(args.build_plan,args.export_receipt,args.route_receipt);write(out/'scope.json',value)
    print(json.dumps({'ProposalReady':value['ProposalReady'],'DataScopes':len(value['DataScopes']),
        'ResetScopes':len(value['ResetScopes']),'SamplerBits':value['SourceSampling']['ActualSamplerCount'],'Scope':str(out/'scope.json')}));return 0


if __name__=='__main__':raise SystemExit(main())
