"""Exact C common-reset startup isolation, never a blanket vendor exception.

The reset clock and the stopped core clock come from different GPLLs. Four
actual reset-clock FFs keep core GPLL.RST asserted through three clock edges.
Routed SR propagation/recovery/uncertainty must fit that finite window. Only
the explicitly enumerated raw-reset FFs qualify; ordinary runtime timing,
analog PLL behavior/MTBF and unrelated vendor paths remain independent.
"""
import hashlib
import importlib
import itertools
import json
import math
from pathlib import Path
import re
import sys

import hdmi_camera_fisheye_fill8r3s3_protocol as protocol

build,native,base=protocol.build,protocol.native,protocol.base
SELF=Path(__file__).resolve()
SCHEMA='hdmi-camera-fisheye-fill8r3s3-vendor-startup-isolation-v2-bounded-b'
GPLL_MODEL=Path('D:/pango/PDS_2023.2/arch/vendor/pango/verilog/bsim/V_GPLL.v')
GPLL_SHA='1cbab1c034d8129f9164edeff911deb36a0201fb67cd8f336512e4ddc21d9ed0'
ROOT='u_ddr3_test_h/u_ddrphy_top/'
PHASE=ROOT+'u_ips2l_ddrphy_rst_clk_phase_adj/'
DDRC='u_ddr3_test_h/u_ddrc_rstn_sync/'
SEQUENCE_SIGNALS={
 'Second':ROOT+'rst_seq_rstn',
 'State0':ROOT+'ddrphy_reset_ctrl/state_reg[0]',
 'CorePLLRST':ROOT+'phy_pll_rst'}
RST_PLL=ROOT+'rst_clk_gpll/u_gpll/gpll_inst/GPLL'
CORE_PLL=ROOT+'ddrphy_gpll/u_gpll/gpll_inst/GPLL'
require=build.require


class Graph(base.Graph):
    """Small independent, output-sensitive scalar graph; macros stop at ports."""
    def __init__(self,text,ports):
        parsed=protocol.mode_graph(text,ports)
        self.cells,self.ff,self.ports=parsed.cells,parsed.ff,parsed.ports
        self.canonical_outputs=parsed.canonical_outputs;self.expr_cache={};self.support_cache={}
        self.placements=base.syntax.functional(re.sub(r'(?m)^(module\s+)'+build.TARGET+r'\b',
            r'\g<1>'+base.syntax.prep.TARGET,text,count=1))['FFPlacement']
        self.clock_outputs={n:list(v)for n,v in self.canonical_outputs.items()}
        for n,c in self.cells.items():
            pins=('CLKOUT',)if c['Primitive']=='V_USCM'else tuple('CLKOUT'+str(i)for i in range(6))if c['Primitive']=='V_GPLL'else()
            for pin in pins:
                if c['Ports'].get(pin):self.clock_outputs.setdefault(base.canon(c['Ports'][pin]),[]).append((n,pin))

    def expression(self,value,active=()):
        net=base.canon(value)
        if net in ("1'b0","1'b1"):return ('constant',int(net[-1]))
        if net in self.expr_cache:return self.expr_cache[net]
        require(net not in active,'actual used startup Boolean cycle')
        drivers=self.canonical_outputs.get(net,[])
        if not drivers:
            macros=[(n,p)for n,c in self.cells.items()if c['Primitive']=='V_GPLL'
                    for p in ('LOCK','DPS_DONE')if base.canon(c['Ports'].get(p,''))==net]
            if len(macros)==1:return ('variable','macro:'+macros[0][0]+'/'+macros[0][1])
            require(self.ports.get(net)=='INPUT','unknown used startup leaf: '+net)
            return ('variable','primary:'+net)
        require(len(drivers)==1,'ambiguous startup driver')
        n,op=drivers[0];c=self.cells[n];p=c['Ports'];child=lambda x:self.expression(x,active+(net,))
        if n in self.ff:e=('variable','ff:'+n)
        elif c['Primitive']in ('V_BUF','V_IBUF'):e=child(p['I'])
        elif c['Primitive']=='V_INV':e=('not',child(p['I']))
        elif c['Primitive']=='V_MUX2':
            e=child(p['I0'])if p['SEL']=="1'b0"or p['I0']==p['I1']else child(p['I1'])if p['SEL']=="1'b1"else('mux',child(p['I0']),child(p['I1']),child(p['SEL']))
        else:
            require(c['Primitive']=='V_LUT6CARRY','unsupported used startup primitive')
            init=int(c['Parameters']['INIT'][4:].replace('_',''),16)
            def half(number):
                inputs=[]
                for i in range(5):
                    relevant=any(((number>>b)^(number>>(b^(1<<i))))&1 for b in range(32))
                    inputs.append(child(p['I'+str(i)])if relevant else('constant',0))
                return ('lut',number,tuple(inputs))
            low,high=init&0xffffffff,init>>32
            if op=='Z5':e=half(low)
            elif op=='Z':
                if low==high:e=half(low)
                else:
                    sel=child(p['I5']if c['Parameters'].get('I5_TO_LUT')=='"TRUE"'else p['CIN'])
                    choices=protocol.possible(sel,{})
                    e=half(low)if choices=={0}else half(high)if choices=={1}else('mux',half(low),half(high),sel)
            else:
                require(op=='COUT','unknown startup LUT output');select=half(low);choices=protocol.possible(select,{})
                zero=lambda:child(p['I5'])if c['Parameters'].get('I5_TO_CARRY','"TRUE"')=='"TRUE"'else half(high)
                e=zero()if choices=={0}else child(p['CIN'])if choices=={1}else('mux',zero(),child(p['CIN']),select)
        self.expr_cache[net]=e;return e


def clock(g,net):
    net=base.canon(net);trace=[];seen=set()
    while net not in seen:
        seen.add(net);ds=g.clock_outputs.get(net,[]);require(len(ds)==1,'unbound startup clock')
        n,pin=ds[0];c=g.cells[n];trace.append({'Cell':n,'Pin':pin,'Primitive':c['Primitive'],'Net':net})
        if c['Primitive']in ('V_BUF','V_IBUF'):net=base.canon(c['Ports']['I'])
        elif c['Primitive']=='V_USCM':
            require(c['Parameters'].get('USCM_MODE')=='"BUF_A"','startup clock has a dynamic switch')
            net=base.canon(c['Ports']['CLK0'])
        elif c['Primitive']=='V_GPLL':return {'Root':n+'/'+pin,'Trace':trace}
        else:raise ValueError('unreviewed startup clock driver')
    raise ValueError('startup clock cycle')


def next_q(g,ff,fixed):
    c=g.ff[ff];p=c['Parameters'];e=base.expressions(g,ff)
    require(p.get('LRS_EN')in ('"TRUE"','"FALSE"')and p.get('SET_RESET')in ('"SET"','"RESET"'),'unknown FF semantics')
    sr=protocol.possible(e['SR'],fixed)if p['LRS_EN']=='"TRUE"'else{0}
    ce=protocol.possible(e['CE'],fixed);data=protocol.possible(e['D'],fixed)
    old={fixed['ff:'+ff]}if'ff:'+ff in fixed else{0,1}
    return {int(p['SET_RESET']=='"SET"')if s else d if en else q for s,en,d,q in itertools.product(sr,ce,data,old)}


def warm_clear(g,targets):
    pending=list(targets);nodes=set();expr={}
    while pending:
        n=pending.pop()
        if n in nodes:continue
        nodes.add(n);require(len(nodes)<=16,'startup asynchronous ancestor scope expanded')
        expr[n]=g.expression(g.ff[n]['Ports']['SR'])
        pending.extend(x[3:]for x in base.boolean.leaves(expr[n])if x.startswith('ff:'))
    fixed={'primary:reset_n':0};proof=[]
    while True:
        changed=False
        for n in sorted(nodes):
            c=g.ff[n];p=c['Parameters']
            if'ff:'+n in fixed or c['Primitive']!='V_FFASYN'or p.get('LRS_EN')!='"TRUE"':continue
            if protocol.possible(expr[n],fixed)!={1}:continue
            q=int(p['SET_RESET']=='"SET"');proof.append({'FF':n,'KnownInputs':dict(fixed),
                'Parameters':p,'SRExpression':expr[n],'SRForced':1,'QForced':q})
            fixed['ff:'+n]=q;changed=True
        if not changed:break
    require(all('ff:'+n in fixed for n in targets),'warm common reset did not establish every startup state')
    return fixed,proof


def sequence(g):
    """Resolve actual FFs from functional signals and D connectivity, not slots."""
    found={}
    for role,signal in SEQUENCE_SIGNALS.items():
        ff,polarity=protocol.logical(g,signal)
        require(polarity==[0,1],'startup logical signal is not an active-high FF: '+role)
        found[role]=ff
    sync_root=ROOT+'u_ddrphy_rst_seq_rstn_sync/'
    first,polarity=protocol.logical(g,g.ff[found['Second']]['Ports']['D'])
    require(polarity==[0,1] and first.startswith(sync_root) and found['Second'].startswith(sync_root),
            'startup reset synchronizer is not two actual identity-connected FFs')
    found={'First':first,**found}
    require(len(set(found.values()))==4,'startup logical roles do not resolve to four distinct FFs')
    require(found['State0'].startswith(ROOT+'ddrphy_reset_ctrl/') and
            found['CorePLLRST'].startswith(ROOT+'ddrphy_reset_ctrl/'),
            'startup FSM and PLL-reset roles left the actual reset controller')
    state,polarity=protocol.logical(g,g.ff[found['CorePLLRST']]['Ports']['D'])
    require(state==found['State0'] and polarity==[0,1],
            'core PLL reset no longer registers the actual startup FSM state')
    pll=g.cells.get(CORE_PLL)
    require(pll is not None and pll['Primitive']=='V_GPLL','stopped clock is not the official GPLL')
    reset,polarity=protocol.logical(g,pll['Ports']['RST'])
    require(reset==found['CorePLLRST'] and polarity==[0,1],
            'core PLL RST is not the proved active-high startup FF')
    return found


def finite_sequence(g):
    selected=sequence(g)
    targets=list(selected.values());fixed,warm=warm_clear(g,targets)
    roots={clock(g,g.ff[n]['Ports']['CK'])['Root']for n in targets}
    require(roots=={RST_PLL+'/CLKOUT0'},'four startup FFs do not share the actual reset-clock GPLL')
    state={k:{fixed['ff:'+n]}for k,n in selected.items()}
    require(state=={'First':{0},'Second':{0},'State0':{1},'CorePLLRST':{1}},'startup physical encoding differs')
    rows=[];power,_=protocol.logical(g,'power_ready')
    for edge in range(1,5):
        out={k:set()for k in selected};keys=list(selected)
        for bits in itertools.product(*(state[k]for k in keys)):
            context={'primary:reset_n':1,'ff:'+power:1,**{'ff:'+selected[k]:b for k,b in zip(keys,bits)}}
            for k,n in selected.items():out[k]|=next_q(g,n,context)
        rows.append({'Edge':edge,'Before':{k:sorted(v)for k,v in state.items()},
                     'After':{k:sorted(v)for k,v in out.items()}});state=out
    require(all(r['After']['CorePLLRST']==[1]for r in rows[:3]),'core PLL may start before three full reset-clock periods')
    return {'Passed':True,'WarmAsyncProofs':warm,'SequenceFFs':selected,'Rows':rows,
        'SequenceIdentityBasis':'actual logical signal expressions and reset synchronizer D connectivity; no packed FF slot or query alias',
        'ResetClock':clock(g,g.ff[selected['First']]['Ports']['CK']),
        'ResetClockPeriodNS':8.0,'CompletedIntervalsBeforePossiblePLLResetRelease':3,
        'NominalMinimumStartupWindowNS':24.0,'OtherLockCounterOrFSMStatesFixed':False,
        'NoAnalogPLLStartLatencyUsed':True}


def primitive_contract(g,watched):
    native.add(watched,GPLL_MODEL,GPLL_SHA);text=GPLL_MODEL.read_text(encoding='utf-8-sig');flat=protocol.compact(text)
    clauses=['assign rst_n = ~(PLL_PWD | RST) & inner_rstn;',
       'always @(negedge odiv0_out_delay or negedge rst_n)',
       "if(!rst_n)clk_out0_gate <= 3'b000;",'assign CLKOUT0 = odiv0_out_delay & clk_out0_gate[2];']
    for s in clauses:require(protocol.compact(s)in flat,'official GPLL reset-clock contract changed')
    pll=g.cells[CORE_PLL];require(pll['Primitive']=='V_GPLL','stopped clock is not the official GPLL')
    rst=g.expression(pll['Ports']['RST']);n=sequence(g)['CorePLLRST']
    require(base.boolean.leaves(rst)=={'ff:'+n}and[base.boolean.evaluate(rst,{'ff:'+n:b})for b in (0,1)]==[0,1],
            'core PLL RST is not the proved active-high startup FF')
    require(protocol.possible(g.expression(pll['Ports']['PLL_PWD']),{})=={0},'core PLL powerdown is dynamic')
    return {'Passed':True,'Primitive':'V_GPLL','ActualCorePLL':CORE_PLL,'ActualRST':pll['Ports']['RST'],
        'Model':native.ref(GPLL_MODEL),'ResetAssertedForcesCLKOUT0Low':True,
        'Basis':'official known GPLL primitive reset/output-gating functional contract',
        'ModelClauses':clauses,'SimulationInternalThreeGateCyclesUsedAsSiliconDelay':False,
        'AnalogLockTimeOrMinimumResetReleaseLatencyClaimed':False}


def native_route_cell(route,parent):
    # Every native instance ends in a semicolon. Excluding that delimiter from
    # the header and both groups prevents cross-cell capture. A zero-width
    # statement boundary also enumerates adjacent same-line declarations.
    pattern=re.compile(r'(?:^|(?<=;))\s*(?:\(\*[^;]*?\*\)\s*)*(gop\w+)\s*(?:/\*[^;]*?\*/\s*)?#\(([^;]*?)\)\s*\\'+re.escape(parent)+r'\s*\(([^;]*?)\);',re.M|re.S)
    found=list(pattern.finditer(route))
    require(len(found)==1,'one exact startup native parent required: '+parent)
    match=found[0]
    def fields(text,kind):
        pairs=re.compile(r'\.(\w+)\s*\(([^()]*)\)')
        rows=list(pairs.finditer(text))
        require(re.fullmatch(r'[\s,]*',pairs.sub('',text))is not None,'unsupported single-cell '+kind+' syntax')
        names=[m[1]for m in rows]
        require(len(names)==len(set(names)),'duplicate single-cell '+kind)
        return {m[1]:m[2].strip()for m in rows}
    return {'Primitive':match[1],'Parameters':fields(match[2],'parameter'),
            'Ports':fields(match[3],'port')}


def targets(g,route):
    names=[n for n in g.ff if n.startswith(PHASE)or n.startswith(DDRC)]
    require(sum(n.startswith(PHASE)for n in names)==32 and sum(n.startswith(DDRC)for n in names)==2,
            'exact current phase-adjust and DDR-controller entry FF inventory changed')
    power,polarity=protocol.logical(g,'power_ready');require(polarity==[0,1],'power-ready logical encoding changed')
    source={'ff:'+power,'primary:reset_n'};rows=[]
    for n in sorted(names):
        c=g.ff[n];p=c['Parameters'];parent=n.rsplit('/',2)[0];native_cell=native_route_cell(route,parent)
        require(c['Primitive']=='V_FFASYN'and p.get('LRS_EN')=='"TRUE"'and p.get('GRS_EN')=='"TRUE"',
                'startup target is not an actual asynchronous-clear/set FF')
        sr=g.expression(c['Ports']['SR']);require(base.boolean.leaves(sr)==source,'target reset has a runtime/foreign source')
        for reset,powered in itertools.product((0,1),repeat=2):
            require(base.boolean.evaluate(sr,{'primary:reset_n':reset,'ff:'+power:powered})==int(not(reset and powered)),
                    'startup target SR is not exactly common reset')
        require(clock(g,c['Ports']['CK'])['Root']==CORE_PLL+'/CLKOUT0','startup target is not on stopped core GPLL output')
        qreset=int(p['SET_RESET']=='"SET"');require(p['INIT']=="1'b"+str(qreset),'startup target INIT/reset polarity differs')
        np=native_cell['Parameters'];require(np.get('LRS_EN')=='"TRUE"'and np.get('RS_MODE')=='"ASYNC"'and
            np.get('RSMUX_SEL')=='"LOCAL"'and np.get('LRS_POL')=='"FALSE"'and
            base.canon(native_cell['Ports']['RS'])==base.canon(c['Ports']['SR']),
            'startup target actual route reset mode/net/polarity differs')
        site=g.placements[n]['Site'];rows.append({'FF':n,'LogicalQ':base.canon(c['Ports']['Q']),
            'Placement':g.placements[n],'FunctionalSR':base.canon(c['Ports']['SR']),
            'FunctionalParameters':p,'ActualEnable':c['Ports']['CE'],
            'EnableConstrainedToOne':False,'ClockStoppedDuringResetReleaseRegardlessOfCE':True,
            'NativeParent':parent,'NativeResetParameters':np,
            'LogicalEndpoint':parent+'/RS','PhysicalEndpoint':site+'/RS','ActualClock':clock(g,c['Ports']['CK'])})
    pff=g.ff[power];parent=power.rsplit('/',2)[0];nc=native_route_cell(route,parent)
    outputs=[pin for pin,v in nc['Ports'].items()if pin in ('Q','L6Q','L5Q')and base.canon(v)==base.canon(pff['Ports']['Q'])]
    require(len(outputs)==1,'power-ready actual native Q output is ambiguous')
    slot=re.search(r'/(FFAPP|FF)([0-3])/FF$',power);require(slot is not None,'power-ready native FF slot missing')
    physical=g.placements[power]['Site']+('/CR'if slot[1]=='FFAPP'else'/Q')+slot[2]
    launch={'SourceFF':power,'SourcePhysicalQ':physical,'SourceNativeOutputPin':parent+'/'+outputs[0],
            'LaunchClock':'board27','CaptureClock':'ddrphy_sysclk'}
    return rows,sorted({r['PhysicalEndpoint']for r in rows}),launch


def power_source(plan,watched):
    spec=protocol.CONTRACTS['Top'];item=next(x for x in plan['CompiledInputs']if x['Source']==spec['Source'])
    path=Path(item['CompiledPath']);native.add(watched,path,item['CompiledSHA256']);text=path.read_text(encoding='utf-8-sig')
    protocol.contract('Top',text);flat=protocol.compact(text)
    clauses=['if(!reset_n)begin power_count<=0;power_ready<=0;end',
       'else if(!key_reset_sync[1])begin power_count<=0;power_ready<=0;end',
       "else if(!(&power_count))power_count<=power_count+1'b1;else power_ready<=1;",
       'wire global_reset_n=reset_n && power_ready;']
    for clause in clauses:require(protocol.compact(clause)in flat,'power startup source changed')
    assignments=re.findall(r'\bpower_ready\s*<=\s*([^;]+);',text)
    require([x.strip()for x in assignments]==['0','0','1'],'power ready has an unreviewed assignment')
    return {'Passed':True,'Top':native.ref(path),'Clauses':clauses,'AllPowerReadyAssignments':assignments,
            'PrimaryReleaseCannotReleaseCommonResetBeforeLaterPowerReadyRise':True,
            'RuntimeCommonResetHasNoBusinessOrWREADYSource':True}


def timing_acceptance(bound,window=24.0):
    maximum=bound.get('MaximumRequiredNS')
    finite=type(maximum)in (int,float)and math.isfinite(maximum)and maximum>=0
    accepted=bound.get('Schema')=='hdmi-camera-fisheye-fill8r3s3-vendor-startup-paths-v1'and \
        bound.get('CompleteActualResetPathCoverage')is True and bound.get('Missing')==[]and \
        bound.get('Violations')==[]and finite and maximum<window
    return accepted,maximum,window-maximum if finite else None


def review(build_plan,export_receipt,route_receipt):
    build_plan=Path(build_plan).resolve();plan=build.validate(build_plan)
    exported,watched=native.bind_receipt(export_receipt);routed,inputs=native.bind_receipt(route_receipt);native.merge(watched,inputs)
    require(exported['Mode']=='export'and routed['Mode']=='report'and
        exported['BuildPlanSHA256']==routed['BuildPlanSHA256']==build.sha(build_plan),'current same-plan C native evidence required')
    net=native.artifact(export_receipt,exported,build.TARGET+'_sim.v');route=native.artifact(route_receipt,routed,'route-dump.v')
    native.add(watched,net);native.add(watched,route);native.add(watched,SELF);native.add(watched,protocol.SELF);native.add(watched,sys.executable)
    top=(build_plan.parent/'compiled'/build.TOP).read_text(encoding='utf-8-sig')
    g=Graph(net.read_text(encoding='gb18030'),build.top_ports(top));sequence=finite_sequence(g)
    power=power_source(plan,watched);contract=primitive_contract(g,watched)
    ff,pins,source=targets(g,route.read_text(encoding='gb18030'))
    fdc=build_plan.parent/'compiled'/build.FDC;native.add(watched,fdc);text=fdc.read_text()
    require('create_clock -name {ref_clk} [get_ports {clk_p}] -period {8.0}'in text and
            all(s in text for s in ('-name {rst_clk}','-name {ddrphy_sysclk}','-multiply_by {16} -divide_by {16}')),
            'actual reset/core clock period contract changed')
    timing=importlib.import_module('hdmi_camera_fisheye_fill8r3s3_startup_timing')
    require(Path(timing.__file__).resolve()==SELF.with_name('hdmi_camera_fisheye_fill8r3s3_startup_timing.py'),'startup timing provider moved')
    bound,inputs=timing.review(build_plan,export_receipt,route_receipt,pins,source);native.merge(watched,inputs);native.add(watched,timing.__file__)
    require(bound.get('RequiredPhysicalResetPins')==pins and bound.get('Source')==source and
            bound.get('BuildPlan')==native.ref(build_plan),'timing witness identifies another physical reset footprint')
    passed,maximum,margin=timing_acceptance(bound)
    missing=[]if passed else['complete routed reset propagation/recovery/uncertainty coverage inside startup window']
    value={'Schema':SCHEMA,'Target':build.TARGET,'BuildPlan':native.ref(build_plan),'ExportReceipt':native.ref(export_receipt),
        'RouteReceipt':native.ref(route_receipt),'Passed':passed,'Missing':missing,'Violations':[],
        'Family':'typed_vendor_common_reset_core_clock_startup_isolation','Targets':ff,
        'Source':source,'FiniteStartupSequence':sequence,'PowerReadyReleaseContract':power,
        'OfficialGPLLResetClockContract':contract,'RoutedTiming':bound,
        'MinimumStartupWindowNS':24.0,'MaximumRequiredNS':maximum,
        'MarginNS':margin,'OnlyActualCommonResetSRPathsQualified':True,
        'OrdinaryVendorPrefixWaiver':False,'AnalogMTBFOrPLLMinimumLockTimeClaimed':False,
        'ConstraintsApplied':False,'TimingAccepted':False,'HardwareReleaseAllowed':False}
    protocol.add_helper_closure(watched)
    require(all(build.sha(p)==h for p,h in watched.items()),'vendor startup evidence drift')
    value['InputSHA256']={str(p):h for p,h in sorted(watched.items(),key=lambda x:str(x[0]))}
    return protocol.canonical_value(value),watched


def verify(path):
    path=Path(path).resolve();saved=build.read(path)
    require(saved.get('Schema')==SCHEMA and saved.get('Target')==build.TARGET,'typed current vendor startup review required')
    value,watched=review(saved['BuildPlan']['Path'],saved['ExportReceipt']['Path'],saved['RouteReceipt']['Path'])
    require(value==saved,'vendor startup proof changed');native.add(watched,path);return saved,watched
