"""Current HDMI fisheye native partitions and exact CDC proposals, CPU only.

The unchanged DDR source partition is provenance, never a blanket exception.
Every native clock and primitive remains typed. Single-domain arithmetic is
bounded at actual FF/macro terminals and remains subject to ordinary STA.
"""
import argparse
from collections import Counter,defaultdict
import hashlib
import itertools
import json
from pathlib import Path
import re
import tempfile

import hdmi_camera_fisheye_fill8r3s3_build as build
import hdmi_camera_fisheye_fill8r3s3_native as native
import hdmi_camera_pixel_audit as typed
import hdmi_camera_direct_audit as boolean
import hdmi_camera_snapshot_audit as exact
import prepare_camera_vga_reset_scope as vendor_reset
import audit_camera_vga_reset_netlist as vendor_graph
import hdmi_camera_fisheye_macro_modes as macro_modes
import hdmi_camera_fisheye_fill8r3s3_protocol as protocol
import hdmi_camera_fisheye_fill8r3s3_startup as startup

SELF=Path(__file__).resolve();TARGET=build.TARGET
SCHEMA='hdmi-camera-fisheye-fill8r3s3-native-audit-v1'
require,sha,read,write=build.require,build.sha,build.read,build.write
canon,parent=boolean.canon,boolean.parent
CAP='system/input_link/input_dma/capture/'
DMA='system/input_link/input_dma/'
OUT='system/output_video/'
DDR='u_ddr3_test_h/'
native_route=typed.native_route


def atoms(value):
    """Scalar native nets with disjoint tokens and complete whitespace removal.

    The old nested repeated identifier pattern could backtrack exponentially
    on a long otherwise-valid bus item followed by a line break. Every scalar
    character here has one tokenization: identifier character or [index].
    """
    value=re.sub(r'\s+','',canon(value));result=[]
    for item in value.replace('{','').replace('}','').split(','):
        if not item:continue
        if re.fullmatch(r"(?:\d+)?'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]+|\d+",item):
            if re.search(r'[xXzZ?]',item):result.append('@unknown_constant:'+item)
            continue
        span=re.fullmatch(r'(.+)\[(\d+):(\d+)\]',item)
        if span:
            hi,lo=int(span[2]),int(span[3]);step=-1 if hi>=lo else 1
            result.extend(span[1]+f'[{i}]'for i in range(hi,lo+step,step));continue
        require(re.fullmatch(r'[A-Za-z_$](?:[\w$./-]|\[\d+(?::\d+)?\])*',item)is not None,
            'unsupported scalar native net expression: '+item)
        result.append(item)
    return result


def source_inventory(build_plan):
    """Keep the current explicit/IDF/header roles without inferring CDC safety."""
    build_plan=Path(build_plan).resolve();plan=build.validate(build_plan);watched={}
    native.add(watched,build_plan)
    bysource={r['Source']:r for r in plan['CompiledInputs']}
    roles=plan['SourceRoles'];rows=[];seen=set()
    groups=[('vendor_DDR_IDF_body',roles['IDFExpandedSources']),
        ('explicit_design',roles['ExplicitDesigns']),('bound_header',roles['Headers']),
        ('board_constraint',[build.FDC])]
    for role,names in groups:
        for name in names:
            require(name not in seen,'source has multiple compilation roles: '+name);seen.add(name)
            item=bysource[name];path=Path(item['CompiledPath']);native.add(watched,path,item['CompiledSHA256'])
            original=build.ROOT/name;native.add(watched,original,item['OriginalSHA256'])
            rows.append({'Source':name,'Role':role,'Original':native.ref(original),
                'Compiled':native.ref(path),'DeclaredTransformations':item['Changes']})
    require(seen==set(bysource)==set(plan['SourceFiles']),'complete current source partition required')
    profile,inputs=build.fisheye_profile_binding();native.merge(watched,inputs)
    return {'SourceRoles':roles,'Sources':rows,'ExactSourceRoleCoverage':True,
        'FisheyeProfile':profile,'NativeEvidenceComplete':False,
        'SourceBytesAloneClaimNativeSafety':False,'Missing':['current native clock/primitive/CDC evidence'],
        'Violations':[]},watched


def functional(text):
    require(re.findall(r'(?m)^module\s+(\w+)',text)==[TARGET],'one actual flat fisheye top required')
    adapted=re.sub(r'(?m)^(module\s+)'+TARGET+r'\b',r'\g<1>'+boolean.syntax.prep.TARGET,text,count=1)
    return boolean.syntax.functional(adapted)


class Graph(typed.PixelGraph):
    """Exact combinational FF support, with explicit non-FF macro cuts.

    An APM or synchronous RAM output is never expanded through every internal
    stage into user CDC. Its complete input/clock locality is reviewed in a
    separate typed partition, including bypass modes and resets.
    """
    def __init__(self,parsed,ports,clocks,models):
        # Reuse the functional FF/LUT model, but never the old scalar lexer.
        typed.mux.Graph.__init__(self,parsed)
        self.ports,self.clocks,self.models=ports,clocks,models
        self.findings=typed.Findings();self.scalar_outputs=defaultdict(list);self.scalar_refs=defaultdict(list)
        self.support_cache={};self.macro_rows={};self.clock_cache={};self.input_cache={}
        for name,c in self.cells.items():
            kind=c['Primitive'];directions=models.get(kind,{}).get('Ports',{})
            require(directions and not(set(c['Ports'])-set(directions)),'unknown primitive/interface: '+kind)
            for pin,value in c['Ports'].items():
                for net in atoms(value):
                    self.scalar_refs[net].append((name,pin))
                    if directions.get(pin)=='OUTPUT':self.scalar_outputs[net].append((name,pin))
        self.canonical_outputs=self.scalar_outputs;self.expr_cache={};self.support_cache={}

    def support(self,value,active=()):
        result=set()
        for net in atoms(value):
            if net in self.support_cache:result|=self.support_cache[net];continue
            if net.startswith('@unknown_constant:'):
                result.add('unknown_constant:'+net[len('@unknown_constant:'):]);continue
            require(net not in active,'cyclic native combinational cone: '+net)
            drivers=self.scalar_outputs.get(net,[])
            if not drivers:
                require(self.ports.get(net)in ('INPUT','INOUT'),'undriven internal native net: '+net)
                result.add('primary:'+net);continue
            require(len(drivers)==1,'ambiguous native driver: '+net)
            n,pin=drivers[0];c=self.cells[n];kind=c['Primitive'];p=c['Ports']
            if n in self.ff:tokens={'ff:'+n}
            elif kind=='V_USCM':
                clock=self.clock(net);tokens={'clock:'+clock['Domain']}
            elif kind in typed.MACRO_CLOCKS or kind in ('V_GPLL','V_PPLL','V_IOCLKDIV_E3'):
                tokens={'macro:'+n+'/'+pin}
                if kind in ('V_RAM32X2','V_RAM64X1'):
                    tokens|=self.support(p['RADDR'],active+(net,))
            elif self.ports.get(net)=='INOUT'and kind in ('V_OBUFT','V_OBUF','V_OBUFDS','V_OBUFTDS'):tokens={'primary:'+net}
            elif kind=='V_OBUFT':
                require(boolean.possible(self.expression(p['T']),{})=={0},'output buffer is dynamically tri-stated: '+n)
                tokens=self.support(p['I'],active+(net,))
            else:
                if kind in ('V_BUF','V_INV','V_IBUF','V_IBUFDS'):inputs=[p['I']]
                elif kind in ('V_LUT6CARRY','V_MUX2'):inputs=typed.mux.inputs(c,pin)
                elif kind=='V_IODELAY_E2':inputs=[v for key,v in p.items()if self.models[kind]['Ports'].get(key)=='INPUT']
                else:raise ValueError('unsupported typed native cone primitive: '+n+'/'+pin)
                tokens=set.union(set(),*(self.support(x,active+(net,))for x in inputs))
            self.support_cache[net]=tokens;result|=tokens
        return result

    def expression(self,value,active=()):
        net=canon(value)
        if net in ("1'b0","1'b1"):return ('constant',int(net[-1]))
        if net in self.expr_cache:return self.expr_cache[net]
        require(net not in active,'native Boolean expression cycle at '+net)
        drivers=self.scalar_outputs.get(net,[])
        if not drivers:
            require(self.ports.get(net)in ('INPUT','INOUT'),'unknown Boolean leaf: '+net)
            return ('variable','primary:'+net)
        require(len(drivers)==1,'ambiguous Boolean driver: '+net)
        n,op=drivers[0];c=self.cells[n];p=c['Ports'];kind=c['Primitive']
        child=lambda x:self.expression(x,active+(net,))
        if n in self.ff:expr=('variable','ff:'+n)
        elif kind in typed.MACRO_CLOCKS or kind in ('V_GPLL','V_PPLL','V_IOCLKDIV_E3'):expr=('variable','macro:'+n+'/'+op)
        elif kind in ('V_BUF','V_IBUF','V_IBUFDS'):expr=child(p['I'])
        elif kind=='V_INV':expr=('not',child(p['I']))
        elif kind=='V_OBUFT':
            require(boolean.possible(child(p['T']),{})=={0},'Boolean output is dynamically tri-stated: '+n)
            expr=child(p['I'])
        elif kind=='V_MUX2':
            expr=child(p['I0'])if p['I0']==p['I1']or p['SEL']=="1'b0"else child(p['I1'])if p['SEL']=="1'b1"else('mux',child(p['I0']),child(p['I1']),child(p['SEL']))
        elif kind=='V_LUT6CARRY':
            init=int(c['Parameters']['INIT'][4:].replace('_',''),16)
            def lut(number):
                inputs=[]
                for i in range(5):
                    mask=sum(1<<j for j in range(32)if not(j>>i)&1)
                    relevant=bool((number^(number>>(1<<i)))&mask)
                    inputs.append(child(p['I'+str(i)])if relevant else('constant',0))
                return ('lut',number,tuple(inputs))
            low_init=init&0xffffffff;high_init=init>>32
            if op=='Z5':expr=lut(low_init)
            elif op=='Z':
                if low_init==high_init:expr=lut(low_init)
                else:
                    selector=child(p['I5']if c['Parameters'].get('I5_TO_LUT')=='"TRUE"'else p['CIN'])
                    values=boolean.possible(selector,{})
                    if values=={0}:expr=lut(low_init)
                    elif values=={1}:expr=lut(high_init)
                    else:expr=('mux',lut(low_init),lut(high_init),selector)
            else:
                require(op=='COUT','unknown LUT output')
                low=lut(low_init)
                select=boolean.possible(low,{})
                if select=={0}:expr=child(p['I5'])if c['Parameters'].get('I5_TO_CARRY','"TRUE"')=='"TRUE"'else lut(high_init)
                elif select=={1}:expr=child(p['CIN'])
                else:expr=('mux',child(p['I5'])if c['Parameters'].get('I5_TO_CARRY','"TRUE"')=='"TRUE"'else lut(high_init),child(p['CIN']),low)
        else:raise ValueError('unknown native Boolean primitive: '+n+'/'+op)
        self.expr_cache[net]=expr;return expr

    def clock(self,net,visited=()):
        key=canon(net)
        if key in self.clock_cache:return self.clock_cache[key]
        drivers=self.scalar_outputs.get(key,[])
        if len(drivers)==1:
            n,pin=drivers[0];c=self.cells[n]
            if c['Primitive']=='V_DDC_E2'and pin in ('WCLK','WCLK_DELAY'):
                require(key not in visited,'PHY clock cycle')
                upstream=self.clock(c['Ports']['CLKA'],visited+(key,))
                value={**upstream,'Trace':[{'Cell':n,'Primitive':'V_DDC_E2','Pin':pin,'Net':key,
                    'Model':self.models['V_DDC_E2']['Reference'],
                    'ClockRelation':'CLKA-derived gated DDR strobe; no frequency division',
                    'PhaseAndTrainingRemainTypedPHY':True,'PhaseEquivalenceToCLKAClaimed':False}]+upstream['Trace']}
                self.clock_cache[key]=value;return value
        return super().clock(net,visited)


def graph(text,build_dir,watched=None):
    watched={}if watched is None else watched
    build_dir=Path(build_dir);parsed=functional(text)
    models=typed.load_models({c['Primitive']for c in parsed['Cells'].values()},watched)
    if any(c['Primitive']=='V_RAM32X2'for c in parsed['Cells'].values()):
        native.add(watched,typed.MODEL_ROOT/'V_RAM32X1.v','eea8354dee48000fce0ef171120b2b0dd04ef5901cefe0198da050aa8ad07842')
    require(all(m['Reference']for m in models.values()),'unknown current vendor primitive')
    top=build_dir/'compiled'/build.TOP;fdc=build_dir/'compiled'/build.FDC
    native.add(watched,top);native.add(watched,fdc)
    ports=build.top_ports(top.read_text(encoding='utf-8-sig'))
    clocks=typed.clock_definitions(fdc.read_text(encoding='ascii'))
    return Graph(parsed,ports,clocks,models)


def native_graph(scope):
    watched={}
    for key in ('BuildPlan','ExportReceipt','RouteReceipt','NativeNetlist','RouteDump'):
        native.add(watched,scope[key]['Path'],scope[key]['SHA256'])
    text=Path(scope['NativeNetlist']['Path']).read_text(encoding='utf-8-sig')
    g=graph(text,Path(scope['BuildPlan']['Path']).parent,watched)
    placements=boolean.clm.placed_luts(text,g)
    wanted={parent(n)for n in g.ff}|{n.rsplit('/',2)[0]for n in placements}|{
        n.rsplit('/',2)[0]for n,c in g.cells.items()if c['Primitive']in ('V_RAM32X2','V_RAM64X1')}
    with tempfile.TemporaryDirectory(prefix='fisheye-native-route-')as temporary:
        normalized=Path(temporary)/'route.adif'
        boolean.calibrated.normalize_source_locations(scope['RouteDump']['Path'],normalized)
        # Select constants by their actual referenced primitive, never their
        # net/instance spelling. Some constants only exist in the route dump.
        with normalized.open(encoding='utf-8-sig')as stream:
            for line in stream:
                match=re.search(r'\(INSTANCE\s+(\S+)\s+\(VIEWREF\s+OPER\s+\(CELLREF\s+(gopVCC|gopGND)\b',line)
                if match:wanted.add(canon(match[1]))
        route=native_route(normalized,wanted)
    report=scope.get('BaselineTimingReport')
    if report is None:
        receipt=read(scope['ExportReceipt']['Path'])
        report=native.ref(native.artifact(scope['ExportReceipt']['Path'],receipt,TARGET+'.rtr'))
    native.add(watched,report['Path'],report['SHA256'])
    timing_controls=current_timing_control_endpoints(report['Path'])
    mapper=Mapper(g,route,placements,timing_controls);g.native_route=route;g.native_mapper=mapper
    return g,route,mapper,watched


def current_timing_control_endpoints(report):
    """Actual baseline STA endpoint headers plus matching physical pin rows.

    An existing get_pins object is insufficient: a canonical name here must
    have occurred as the endpoint of a real baseline timing path at that
    exact physical CLM CE/RS. No failed scoped report or source prefix is used.
    """
    rows={};endpoint=None;header=None;path_type=None;designs=[]
    with Path(report).open(encoding='gb18030',errors='strict')as stream:
        for number,line in enumerate(stream,1):
            design=re.fullmatch(r'\| Design\s*:\s*(\S+)\s*',line)
            if design:designs.append(design[1])
            match=re.match(r'^Endpoint\s*:\s*(\S+)\s*$',line)
            if match:
                endpoint=match[1];header=number;path_type=None;continue
            match=re.match(r'^Path Type\s*:\s*(.+?)\s*$',line)
            if match:path_type=match[1];continue
            if endpoint is None or not endpoint.endswith(('/CE','/RS')):continue
            match=re.match(r'^\s*(CLM[A-Z]*_\d+_\d+)/(CE|RS)\s+[rf]\s+(\S+)\s*$',line)
            if match is None or match[3]!=endpoint:continue
            key=match[1],match[2]
            item=rows.setdefault(key,{}).setdefault(endpoint,{'Endpoint':endpoint,
                'PhysicalTimingPin':match[1]+'/'+match[2],'ObservedPaths':0,'Contexts':{}})
            item['ObservedPaths']+=1
            context=path_type or'unknown_path_type'
            item['Contexts'].setdefault(context,{'EndpointHeaderLine':header,'PhysicalPinLine':number,
                'EndpointHeader':endpoint,'PhysicalLocation':match[1]+'/'+match[2],'PathType':path_type})
    require(designs==[TARGET],'timing endpoint evidence is not the current actual design report')
    return {'Report':native.ref(report),'ByPhysicalPin':rows,
        'TimingEndpointIdentityFromActualPath':True,'GetPinsExistenceAloneAccepted':False}


class Mapper(exact.Mapper):
    """Bind synthesis-internal nets to the current native output topology.

    A net rename is never inferred from a prefix or an equal support set.
    The emitting native instance/output must identify one actual functional
    output, using output-slot conventions witnessed by exact bindings in this
    same graph. Boolean equivalence is reported separately from topology.
    """
    def __init__(self,g,route,placements,timing_controls=None):
        super().__init__(g,route,placements)
        self.native_outputs=defaultdict(list);self.local_outputs=defaultdict(list)
        self.output_kinds=defaultdict(set);self.output_witnesses=defaultdict(list)
        self.alias_cache={};self.alias_proofs={};self.alias_inversions={};self.signal_alias_cache={};self.witness_digests={}
        self.timing_controls=timing_controls;self.control_cache={};self.control_proofs={}
        self.ff_by_site=defaultdict(list)
        for ff,placement in g.g['FFPlacement'].items():self.ff_by_site[placement['Site']].append(ff)
        for n,c in g.cells.items():
            p=parent(n)if n in g.ff else n.rsplit('/',2)[0]
            if n in g.ff:
                match=re.search(r'/(FFAPP|FF)[0-3]/FF$',n)
                self.local_outputs[p].append((n,'Q',match[1],canon(c['Ports']['Q'])))
            elif c['Primitive']=='V_LUT6CARRY':
                for pin in ('Z','Z5','COUT'):
                    if c['Ports'].get(pin):self.local_outputs[p].append((n,pin,'LUT:'+pin,canon(c['Ports'][pin])))
            elif c['Primitive']=='V_MUX2':
                self.local_outputs[p].append((n,'Z','MUX:Z',canon(c['Ports']['Z'])))
        for (p,pin),net in route['Pins'].items():
            cell=route['Cells'][route['Instances'][p]['Cell']]
            if cell['Ports'][pin]!='OUTPUT':continue
            self.native_outputs[net].append((p,pin))
            matches=[r for r in self.local_outputs[p]if r[3]==net]
            if len(matches)==1:
                key=cell['Operator'],pin
                self.output_kinds[key].add(matches[0][2]);self.output_witnesses[key].append(matches[0][0])

    def native_functional_net(self,net,active=()):
        net=canon(net)
        if net in self.g.scalar_outputs or net in self.g.ports or net in ("1'b0","1'b1"):return net
        if net in self.alias_cache:return self.alias_cache[net]
        require(net not in active,'cyclic native output alias')
        owners=self.native_outputs.get(net,[])
        require(len(owners)==1,'native alias lacks one actual output owner: '+net)
        p,pin=owners[0];nativecell=self.route['Cells'][self.route['Instances'][p]['Cell']]
        if nativecell['Operator']in ('gopVCC','gopGND'):
            require(pin=='Z'and nativecell['Ports']=={'Z':'OUTPUT'},'native constant primitive interface differs')
            params={r[1]:r[3]for r in nativecell['Parameters']};value=params.get('INIT')
            require(value is not None and value[0]=='BITVEC'and value[1][:2]==['B','64'],'native constant INIT shape')
            bit=int(nativecell['Operator']=='gopVCC');bits=value[1][2].strip('"')
            require(bits==str(bit)*64,'native constant operator and complete INIT disagree')
            functional="1'b"+str(bit);self.alias_cache[net]=functional;self.alias_inversions[net]=False
            self.alias_proofs[net]={'Kind':'actual_native_constant_driver','NativeDriver':p+'/'+pin,
                'NativeOperator':nativecell['Operator'],'NativeINIT':bits,'Value':bit,
                'NetNameUsedToInferValue':False}
            return functional
        key=nativecell['Operator'],pin;kinds=self.output_kinds.get(key,set())
        candidates=[r for r in self.local_outputs[p]if r[2]in kinds]
        # A plain LUT output has one model-defined combinational Z even when
        # every emitted net of this instance was renamed by synthesis.
        if not kinds and nativecell['Operator']=='gopLUT6'and pin=='L6':
            candidates=[r for r in self.local_outputs[p]if r[2]=='LUT:Z']
        require(len(candidates)==1,'native output alias has ambiguous/unproved functional slot: '+p+'/'+pin)
        n,op,kind,functional=candidates[0]
        native_inversion=False;native_init_evidence=None
        if kind.startswith('LUT:'):
            params={r[1]:r[3]for r in nativecell['Parameters']}
            inversions={};local_bindings=[]
            pins=set(boolean.clm.endpoints.input_pins(self.g.cells[n],op))|{
                'I'+str(i)for i in range(6 if op=='Z'else 5)if self.g.cells[n]['Ports']['I'+str(i)]in("1'b0","1'b1")}
            for ip in sorted(pins):
                if (p,ip)not in self.route['Pins']:continue
                binding=self.signal_alias(self.g.cells[n]['Ports'][ip],self.route['Pins'][p,ip],active+(net,))
                inversions[ip]=bool(binding and binding.get('Inverted'));local_bindings.append({'Pin':ip,'Proof':binding})
            if 'INIT'in params:
                value=params['INIT'];require(value[0]=='BITVEC'and value[1][:2]==['B','64'],'native alias LUT INIT shape')
                ni=int(value[1][2].strip('"'),2);fi=int(self.g.cells[n]['Parameters']['INIT'][4:],16)
                constants={i:int(self.g.cells[n]['Ports']['I'+str(i)][-1])for i in range(6)
                    if self.g.cells[n]['Ports']['I'+str(i)]in("1'b0","1'b1")}
                differences=set()
                for address in range(64 if op=='Z'else 32):
                    if any((address>>i)&1!=v for i,v in constants.items()if i<(6 if op=='Z'else 5)):continue
                    native_address=address
                    for ip,inverted in inversions.items():
                        if inverted and re.fullmatch(r'I[0-5]',ip):native_address^=1<<int(ip[1])
                    differences.add(((ni>>native_address)^(fi>>address))&1)
                require(op in ('Z','Z5')and len(differences)==1,
                    'native alias LUT INIT/input polarity does not bind functional operator')
                native_inversion=bool(next(iter(differences)))
                native_init_evidence={'NativeINIT':ni,'FunctionalINIT':fi,'InputPolarityBindings':local_bindings,
                    'LocalTruthTableCofactorVerified':True,'OutputInverted':native_inversion}
        elif kind in ('FF','FFAPP'):
            params={r[1]:r[3]for r in nativecell['Parameters']};init=params.get('FF_INIT'if kind=='FF'else'FFAPP_INIT')
            require(init is not None and init[0]=='BIT'and init[1][:2]==['B','1'],'native FF alias has no explicit initialized slot')
            actual=int(init[1][2].strip('"'));functional_init=int(self.g.ff[n]['Parameters']['INIT'][-1])
            native_inversion=bool(actual^functional_init)
            native_init_evidence={'NativeSlotINIT':actual,'FunctionalFFINIT':functional_init,
                'SameActualFFOutputSlot':True,'Inverted':native_inversion}
        self.alias_cache[net]=functional
        self.alias_inversions[net]=native_inversion
        if key not in self.witness_digests:self.witness_digests[key]=hashlib.sha256(json.dumps(sorted(self.output_witnesses.get(key,[])),separators=(',',':')).encode()).hexdigest()
        self.alias_proofs[net]={'Kind':'current_native_output_slot_binding','NativeDriver':p+'/'+pin,
            'FunctionalDriver':n+'/'+op,'FunctionalNet':functional,'NativeNet':net,
            'ActualPhysicalSite':self.g.g['FFPlacement'][n]['Site']if n in self.g.ff else self.placements[n]['Site'],
            'NativeOperator':nativecell['Operator'],'OutputSlotKind':kind,
            'CurrentExactSlotWitnessKey':'/'.join(key),
            'CurrentExactSlotWitnessCount':len(self.output_witnesses.get(key,[])),
            'CurrentExactSlotWitnessesSHA256':self.witness_digests[key],
            'NativeOutputInvertsFunctionalSignal':native_inversion,'NativeSlotInitializationEvidence':native_init_evidence,
            'ActualFFOrCombinationalOutputIdentityVerified':True}
        return functional

    def signal_alias(self,functional,native,active=()):
        functional=canon(functional);native=canon(native)
        if functional==native:return None
        pair=functional,native
        if pair in self.signal_alias_cache:return self.signal_alias_cache[pair]
        resolved=self.native_functional_net(native,active)
        a=self.g.expression(functional);b=self.g.expression(resolved)
        if self.alias_inversions.get(native):b=('not',b)
        same=exact.boolean_equal(a,b);inverse=False if same else exact.boolean_equal(a,('not',b))
        require(same or inverse,'functional/native nets are not the same Boolean signal or its complement')
        result={'Kind':'actual_driver_bound_boolean_alias','FunctionalNet':functional,'NativeNet':native,
            'ResolvedFunctionalNet':resolved,'Inverted':inverse,'BooleanCofactorVerified':True,
            'NativeOutputBinding':self.alias_proofs.get(native),'SupportPreserved':True}
        self.signal_alias_cache[pair]=result;return result

    def native_expression(self,net):
        resolved=self.native_functional_net(net);expr=self.g.expression(resolved)
        return ('not',expr)if self.alias_inversions.get(canon(net))else expr

    def connection(self,name,pin):
        p=name.rsplit('/',2)[0];net=self.g.cells[name]['Ports'][pin]
        require((p,pin)in self.route['Pins'],'local LUT native input missing')
        native=self.route['Pins'][p,pin]
        if native==canon(net):return p,net,native,None
        if pin=='CIN':return super().connection(name,pin)
        return p,net,native,self.signal_alias(net,native)

    def boundaries(self,target,pin):
        rows=self.functional_boundaries(target,pin)
        if pin not in ('CE','SR')or self.timing_controls is None:return rows
        key=target,pin
        if key in self.control_cache:return self.control_cache[key]
        result=[self.qualified_control_boundary(target,pin,row)for row in rows]
        self.control_cache[key]=result;return result

    def qualified_control_boundary(self,target,pin,row):
        np='CE'if pin=='CE'else'RS';site=self.g.g['FFPlacement'][target]['Site']
        original=row['Endpoint'];op,opn=original.rsplit('/',1)
        require(opn==np and parent(target)==op,'functional control boundary is not the target actual native control input')
        evidence=self.timing_controls['ByPhysicalPin'].get((site,np),{})
        if not evidence:return row
        original_net=self.route['Pins'].get((op,np))
        require(original_net is not None,'original packed control is unconnected')
        actual_clock=self.g.clock(self.g.ff[target]['Ports']['CK'])
        polarity='LCE_POL'if pin=='CE'else'LRS_POL';enabled='LCE_EN'if pin=='CE'else'LRS_EN'
        mux='CEMUX_SEL'if pin=='CE'else'RSMUX_SEL'
        def signature(p):
            cell=self.route['Cells'][self.route['Instances'][p]['Cell']]
            require(cell['Ports'].get(np)=='INPUT','physical control alias is not an input')
            params={r[1]:r[3]for r in cell['Parameters']}
            require(all(k in params for k in(polarity,enabled,mux)),'native control mode parameters missing')
            require(params[enabled]==['STRING','"TRUE"'],'a timing-control input is disabled for its actual FF')
            return {k:params[k]for k in(polarity,enabled,mux)+(('RS_MODE',)if pin=='SR'else())}
        source_signature=signature(op);qualified=[]
        for endpoint,record in sorted(evidence.items()):
            candidate,cp=endpoint.rsplit('/',1)
            require(cp==np and(candidate,np)in self.route['Pins'],'reported control endpoint is absent from current native route')
            targets=[ff for ff in self.ff_by_site[site]if parent(ff)==candidate]
            require(targets and all(self.g.g['FFPlacement'][ff]['Site']==site for ff in targets),
                'reported control endpoint does not own a FF at its actual physical site')
            require(self.route['Pins'][candidate,np]==original_net,'reported physical control has another actual net')
            require(signature(candidate)==source_signature,'reported physical control aliases have different polarity/mux/mode')
            require(all(same_clock(actual_clock,self.g.clock(self.g.ff[ff]['Ports']['CK']))for ff in targets),
                'reported physical control alias has another actual clock root')
            qualified.append((endpoint,record,targets))
        require(qualified,'no actual STA endpoint qualifies for this shared physical control')
        endpoint,record,canonical_targets=qualified[0]
        canonical_target=sorted(canonical_targets)[0];canonical_net=self.g.ff[canonical_target]['Ports'][pin]
        canonical_support=self.g.support(canonical_net);canonical_expr=self.g.expression(canonical_net)
        canonical_alias=self.signal_alias(canonical_net,original_net)
        controlled=[]
        for ff in sorted(self.ff_by_site[site]):
            p=parent(ff)
            if self.route['Pins'].get((p,np))!=original_net:continue
            cell=self.route['Cells'][self.route['Instances'][p]['Cell']]
            params={r[1]:r[3]for r in cell['Parameters']}
            if params.get(enabled)==['STRING','"FALSE"']:continue
            require(signature(p)==source_signature,'one shared physical control footprint has an incompatible native FF mode')
            require(same_clock(actual_clock,self.g.clock(self.g.ff[ff]['Ports']['CK'])),
                'one shared physical control footprint has mixed clock roots')
            functional=self.g.ff[ff]['Ports'][pin]
            require(self.g.support(functional)==canonical_support,
                'shared control pin consumers have different complete functional source support')
            require(exact.boolean_equal(self.g.expression(functional),canonical_expr),
                'shared control pin consumers do not have the same actual functional control polarity')
            alias=self.signal_alias(functional,original_net)
            require(bool(alias and alias.get('Inverted'))==bool(canonical_alias and canonical_alias.get('Inverted')),
                'shared control native/functional active polarity differs')
            controlled.append({'FF':ff,'ActualLogicalQ':canon(self.g.ff[ff]['Ports']['Q']),
                'Placement':self.g.g['FFPlacement'][ff],'NativeParent':p,'NativeControlNet':original_net,
                'NativeControlSignature':signature(p),'FunctionalControlNet':canon(functional),
                'NativeFunctionalAlias':alias,'Clock':self.g.clock(self.g.ff[ff]['Ports']['CK'])})
        require(target in {r['FF']for r in controlled},'original logical target is outside the proved physical control footprint')
        proofkey=site+'/'+np
        proof={'Verified':True,'PhysicalTimingPin':proofkey,'CanonicalTimingEndpoint':endpoint,
            'NativeControlNet':original_net,'NativeControlSignature':source_signature,
            'CurrentBaselineReport':self.timing_controls['Report'],'ActualTimingPathEvidence':record,
            'OtherObservedCanonicalNames':[p[0]for p in qualified],
            'ControlledFFs':controlled,'CompleteControlledFFInventoryVerified':True,
            'CompleteFunctionalSourceSupport':sorted(canonical_support),'SourceSupportEqualityVerified':True,
            'ClockRootAndPolarityAndMuxVerified':True,'GetPinsExistenceAloneAccepted':False,
            'ArbitrarySameClockOrHierarchyPrefixAliasAccepted':False}
        if proofkey in self.control_proofs:require(self.control_proofs[proofkey]==proof,
            'one physical timing control has inconsistent canonical proof')
        else:self.control_proofs[proofkey]=proof
        return {**row,'Endpoint':endpoint,'OriginalLogicalEndpoint':original,
            'OriginalPhysicalAlias':site+'/'+np,'OriginalFunctionalBoundaryNet':row['FunctionalBoundaryNet'],
            'FunctionalBoundaryNet':canonical_net,'BoundaryNet':canon(canonical_net),
            'NativeBoundaryNet':original_net,'QualifiedTimingEndpointProofKey':proofkey,
            'NetAliasProof':canonical_alias,'PhysicalCLMSite':site}

    def functional_boundaries(self,target,pin):
        try:return super().boundaries(target,pin)
        except (ValueError,KeyError)as original:
            p=parent(target);functional=self.g.ff[target]['Ports'][pin]
            if pin in ('CE','SR'):
                np='CE'if pin=='CE'else'RS';actual=self.route['Pins'].get((p,np))
                require(actual is not None,'native control endpoint missing')
                proof=self.signal_alias(functional,actual)
                row={'Endpoint':p+'/'+np,'BoundaryNet':canon(functional),'FunctionalBoundaryNet':functional,
                    'NativeBoundaryNet':actual,'NetAliasProof':proof,'BoundaryToLogicalFF':[],
                    'PhysicalCLMSite':self.g.g['FFPlacement'][target]['Site']}
                self.boundary_cache[target,pin]=[row];return[row]
            # Packed LUT7 contains a model-level MUX2 and two local LUTs. Its
            # physical A/B/M inputs are the exact boundary; no MUX is a FF.
            site=self.g.g['FFPlacement'][target]['Site'];rows={}
            def visit(net,trail,active):
                if not self.support(net):return
                require(net not in active,'packed MUX boundary cycle')
                candidates=[]
                for nativepin in self.route['Cells'][self.route['Instances'][p]['Cell']]['Ports']:
                    actual=self.route['Pins'].get((p,nativepin))
                    if actual is None or nativepin in ('CLK','CE','RS'):continue
                    if self.route['Cells'][self.route['Instances'][p]['Cell']]['Ports'][nativepin]!='INPUT':continue
                    try:proof=self.signal_alias(net,actual)
                    except(ValueError,KeyError):continue
                    candidates.append((nativepin,actual,proof))
                if candidates:
                    for np,actual,proof in candidates:
                        rows[p+'/'+np]={'Endpoint':p+'/'+np,'BoundaryNet':canon(net),'FunctionalBoundaryNet':net,
                            'NativeBoundaryNet':actual,'NetAliasProof':proof,'BoundaryToLogicalFF':[trail],
                            'PhysicalCLMSite':site,'BoundaryKind':'current native packed MUX external input'}
                    return
                n,op=self.g.driver(net);c=self.g.cells[n]
                require(n not in self.g.ff,'unbound sequential source inside native packed MUX')
                require(c['Primitive']in ('V_LUT6CARRY','V_MUX2','V_BUF','V_INV'),'unreviewed packed MUX primitive')
                if n in self.placements:require(self.placements[n]['Site']==site,'MUX cone escaped physical CLM')
                else:require(n.startswith(p+'/')or c['Primitive']in ('V_BUF','V_INV'),'MUX cone escaped native owner')
                if c['Primitive']=='V_MUX2':
                    ips=['I0']if c['Ports']['I0']==c['Ports']['I1']or c['Ports']['SEL']=="1'b0"else['I1']if c['Ports']['SEL']=="1'b1"else['I0','I1','SEL']
                else:ips=boolean.clm.endpoints.input_pins(c,op)
                for ip in ips:
                    visit(c['Ports'][ip],trail+[{'Cell':n,'Primitive':c['Primitive'],'Output':op,'Input':ip,'Parameters':c['Parameters']}],active+(net,))
            visit(functional,[],())
            require(rows,'no exact native packed MUX boundary: '+str(original))
            self.boundary_cache[target,pin]=[rows[k]for k in sorted(rows)];return self.boundary_cache[target,pin]


def scoped_aliases(g,build_dir,watched):
    """Recover literal aliases from this source hierarchy, never parent bit names."""
    specs=[('',build.TOP),('system/','rtl/experimental/hdmi_camera_fisheye_system_c.v'),
        ('system/input_link/','rtl/experimental/hdmi_camera_fisheye_input_link.v'),
        ('system/input_link/shared_writes/','rtl/ddr_write_arbiter.v'),
        (DMA,'rtl/experimental/hdmi1080_input_dma.v'),(CAP,'rtl/experimental/hdmi1080_capture_cdc.v'),
        (OUT,'rtl/experimental/ddr_video_output_1080_board.v'),
        ('system/display_fifo/','rtl/video_async_fifo.v'),(CAP+'pixels/','rtl/video_async_fifo.v'),
        ('input_sampler/',build.SAMPLER),('input_quantizer/',build.QUANTIZER),('view_control/',build.VIEW_CONTROL)]
    texts={};bounds={};uf={};proof=[]
    def find(n):
        uf.setdefault(n,n)
        if uf[n]!=n:uf[n]=find(uf[n])
        return uf[n]
    def join(a,b,why):
        x,y=find(a),find(b)
        if x!=y:uf[y]=x
        proof.append({'Left':a,'Right':b,**why})
    for scope,name in specs:
        path=Path(build_dir)/'compiled'/name;native.add(watched,path)
        text=build.pins.clean_verilog(path.read_text(encoding='utf-8-sig'));texts[scope]=text;bounds[scope]={}
        for hi,lo,names in re.findall(r'\b(?:input|output|wire|reg)\s+(?:(?:wire|reg|signed)\s+)*\[(\d+):(\d+)\]\s+([^;\n]+)',text):
            for value in names.split(','):
                m=re.match(r'\s*(\w+)',value)
                if m:bounds[scope][m[1]]=(int(hi),int(lo))
    def scalar(value,scope,width=None):
        value=re.sub(r'\s+','',canon(value))
        if value.startswith('{')and value.endswith('}'):return [x for item in value[1:-1].split(',')for x in scalar(item,scope)]
        if re.fullmatch(r'[A-Za-z_]\w*',value)and(value in bounds[scope]or width and width>1):
            hi,lo=bounds[scope][value]if value in bounds[scope]else(width-1,0)
            return [scope+value+f'[{i}]'for i in range(hi,lo-1,-1)]
        if not re.fullmatch(r'[A-Za-z_]\w*(?:\[\d+(?::\d+)?\])?',value):
            # A single Boolean expression in a concatenation occupies one
            # bit but provides no literal alias. Preserve other bit slots.
            return [None]if re.search(r'\|\||&&|==|!=',value)else[]
        return [scope+x for x in exact.atoms(value)]
    for scope,text in texts.items():
        for lhs,rhs in re.findall(r'\bassign\s+([^;=]+?)\s*=\s*([^;]+);',text):
            a,b=scalar(lhs,scope),scalar(rhs,scope)
            if a and len(a)==len(b):
                for x,y in zip(a,b):
                    if x is not None and y is not None:join(x,y,{'Kind':'literal_assign','Scope':scope})
    for child,name in specs[1:]:
        scope,instance=child.rstrip('/').rsplit('/',1)if'/'in child.rstrip('/')else('',child.rstrip('/'))
        scope=scope+'/'if scope else''
        if scope not in texts:continue
        module=re.search(r'\bmodule\s+(\w+)',texts[child])[1]
        matches=re.findall(r'\b'+module+r'\s*(?:#\s*\(.*?\)\s*)?'+re.escape(instance)+r'\s*\((.*?)\)\s*;',texts[scope],re.S)
        require(len(matches)==1,'literal instance port binding absent: '+child)
        for formal,actual in re.findall(r'\.(\w+)\s*\(([^()]*)\)',matches[0]):
            hi,lo=bounds[child].get(formal,(0,0));a,b=scalar(formal,child,hi-lo+1),scalar(actual,scope,hi-lo+1)
            if a and len(a)==len(b):
                for x,y in zip(a,b):
                    if x is not None and y is not None:join(x,y,{'Kind':'literal_port','Instance':child,'Formal':formal,'Actual':actual})
    for pad,direction in g.ports.items():
        if direction!='OUTPUT':continue
        drivers=g.scalar_outputs.get(pad,[])
        if len(drivers)==1:
            n,p=drivers[0];c=g.cells[n]
            if c['Primitive']=='V_OBUFT'and boolean.possible(g.expression(c['Ports']['T']),{})=={0}:
                join(pad,canon(c['Ports']['I']),{'Kind':'native_output_buffer','Cell':n})
    groups=defaultdict(set)
    for n in list(uf):groups[find(n)].add(n)
    aliases={n:sorted(v)for v in groups.values()for n in v}
    g.registered_roles=defaultdict(set)
    for values in groups.values():
        choices=[]
        for net in sorted(values):
            if net not in g.scalar_outputs:continue
            sources=g.support(net)
            if len(sources)!=1 or not next(iter(sources)).startswith('ff:'):continue
            ff=next(iter(sources))[3:];expr=g.expression(net)
            if boolean.boolean.leaves(expr)!={'ff:'+ff}:continue
            result=[boolean.boolean.evaluate(expr,{'ff:'+ff:bit})for bit in (0,1)]
            require(result in ([0,1],[1,0]),'registered alias is not exact identity/complement')
            choices.append((ff,result[0],net))
        if choices:
            require(len({ff for ff,_,_ in choices})==1,'literal role group reaches different actual FFs')
            ff=choices[0][0];g.registered_roles[ff]|=values
            proof.append({'Kind':'registered_role_cofactor','ActualFF':ff,'LogicalNames':sorted(values),
                'DriverEvidence':[{'Net':n,'NativeQInverted':bool(inv)}for _,inv,n in choices],
                'ActualFunctionalQ':canon(g.ff[ff]['Ports']['Q']),
                'LiteralNetAliasClaimedAcrossInversion':False})
    return aliases,proof


def identities(g,ff,aliases):
    return sorted(set(exact.identities(g,ff,aliases))|getattr(g,'registered_roles',{}).get(ff,set()))


def resolve_ff(g,logical,aliases):
    candidates=[n for n in g.ff if logical in getattr(g,'registered_roles',{}).get(n,set())]
    if candidates:
        require(len(candidates)==1,'registered role reaches multiple actual FFs: '+logical)
        return candidates[0]
    return exact.resolve_ff(g,logical,aliases)


def same_clock(first,second):
    return all(first.get(key)==second.get(key)for key in ('Domain','Root','PeriodNS','Master'))


def consumer_index(g):
    consumers=defaultdict(set)
    for n,c in g.ff.items():
        for pin in ('D','CE','SR'):
            for token in g.support(c['Ports'][pin]):consumers[token].add((n,pin))
    return consumers


def next_q_possibilities(g,ff,fixed):
    """Conservative cofactor, preserving native SR-before-CE priority."""
    c=g.ff[ff];p=c['Parameters'];ports=c['Ports'];result=set()
    sr=boolean.possible(g.expression(ports['SR']),fixed)if p['LRS_EN']=='"TRUE"'else{0}
    if 1 in sr:result.add(int(p['SET_RESET']=='"SET"'))
    if 0 in sr:
        ce=boolean.possible(g.expression(ports['CE']),fixed)
        if 1 in ce:result|=boolean.possible(g.expression(ports['D']),fixed)
        if 0 in ce:result|={fixed['ff:'+ff]}if'ff:'+ff in fixed else{0,1}
    return result


def scalar_chain(g,first,second,release,label,consumers):
    a,b=g.ff[first],g.ff[second];rt,ri=release
    require(same_clock(g.clock(a['Ports']['CK']),g.clock(b['Ports']['CK'])),'different scalar-stage clock roots')
    ia=int(a['Parameters']['SET_RESET']=='"SET"');ib=int(b['Parameters']['SET_RESET']=='"SET"')
    require(a['Parameters']['INIT']=="1'b"+str(ia)and b['Parameters']['INIT']=="1'b"+str(ib),
        'scalar native INIT/reset encoding differs')
    second_table=boolean.truth(g,second)
    for row in second_table:
        v=row['Inputs'];sr=boolean.boolean.evaluate(g.expression(b['Ports']['SR']),v)if b['Parameters']['LRS_EN']=='"TRUE"'else 0
        expected=0 if sr else(v['ff:'+first]^ia)&(v['ff:'+rt]^ri)
        require((row['NextQ']^ib)==expected,'scalar second is not first AND actual local release: '+label)
    fixed={'ff:'+rt:ri};forced=next_q_possibilities(g,first,fixed)
    require(forced=={ia},'inactive local release does not force native scalar first-stage reset value')
    require(consumers['ff:'+first]=={(second,'D')},'scalar first stage has an extra native FF consumer')
    try:ordinary=g.chain(first,second,label,g.ff[rt]['Ports']['Q'])
    except ValueError:
        ordinary={'First':first,'Second':second,'FirstPlacement':g.g['FFPlacement'][first],
            'SecondPlacement':g.g['FFPlacement'][second],'SameSite':g.g['FFPlacement'][first]['Site']==g.g['FFPlacement'][second]['Site'],
            'SameBLE':g.g['FFPlacement'][first]==g.g['FFPlacement'][second],'NativeQueries':[],
            'ExactNativeInterstageQueryRequired':True}
    return {**ordinary,'Family':label,'DestinationClock':g.clock(a['Ports']['CK'])['Domain'],
        'ClockRootsIdentical':True,'FirstStageOnlyFeedsSecondStage':True,'NativeTruthVerified':True,
        'FirstInactiveCofactor':{'Fixed':fixed,'NextQPossibilities':sorted(forced),
            'ConservativeUnknownsCannotWeakenProof':True},'SecondTruthTable':second_table,
        'LocalReleaseFF':rt,'LocalReleaseInactivePhysicalQ':ri,'NativeStageInactiveQ':[ia,ib],
        'InterstageTimingAccepted':False,'AnalogMetastabilityAccepted':False}


def chain_inventory(g,aliases,consumers):
    families=[(x+'_ref',2,'scalar')for x in ('cfg_lock','video_lock','rx_done','tx_done','cfg_failed',
        'ddr_init','ddr_pll','system_failed','processed','pclk_activity','hs_activity','corrected_requested')]
    families += [(x,2,'scalar')for x in ('board_failed_core','input_vs_core','output_vs_core',
        'system/request_sync','system/grant_ack_sync','system/done_sync','system/scan_abort_sync',
        'system/scan_enable_sync','system/scan_failed_sync',CAP+'enable_pix',CAP+'grant_sync',
        CAP+'done_sync',CAP+'ack_sync',OUT+'grant_sync',OUT+'done_ack_sync')]
    families += [('view_control/key_sync',2,'scalar')]
    pairs=[(f+'[0]',f+'[1]',f,role,None)for f,_,role in families]
    for prefix,width in ((CAP+'pixels/',7),('system/display_fifo/',10)):
        for source,first,second in (('wr_gray','wr_gray_r1','wr_gray_r2'),('rd_gray','rd_gray_w1','rd_gray_w2')):
            pairs += [(prefix+first+f'[{i}]',prefix+second+f'[{i}]',prefix+source+f'[{i}]','gray',i)for i in range(width)]
    pairs += [(CAP+f'no_grant_s1[{i}]',CAP+f'no_grant_s2[{i}]',CAP+f'no_grant_gray[{i}]','gray',i)for i in range(32)]
    rows=[];missing=[]
    for firstq,secondq,family,role,bit in pairs:
        try:
            second=resolve_ff(g,secondq,aliases)
        except ValueError as e:
            # An unused diagnostic Gray counter may be eliminated completely.
            if role=='gray'and not any(name in g.scalar_refs for logical in (firstq,secondq)
                for name in aliases.get(logical,[logical])):continue
            if role=='scalar'and not any(name in g.scalar_refs for logical in (firstq,secondq)
                for name in aliases.get(logical,[logical])):continue
            missing.append({'Code':'SynchronizerSecondMissing','Logical':secondq,'Detail':str(e)});continue
        try:
            same=g.clock(g.ff[second]['Ports']['CK'])
            candidates={x[3:]for x in g.support(g.ff[second]['Ports']['D'])if x.startswith('ff:')and x[3:]!=second
                and same_clock(g.clock(g.ff[x[3:]]['Ports']['CK']),same)
                and consumers['ff:'+x[3:]]=={(second,'D')}}
            try:
                declared_first=resolve_ff(g,firstq,aliases)
                if declared_first in candidates:candidates={declared_first}
            except ValueError:pass
            require(len(candidates)==1,'second D lacks one exclusively isolated actual first-stage Q')
            first=next(iter(candidates));releases=[]
            extra={x[3:]for n in (first,second)for pin in ('D','CE','SR')for x in g.support(g.ff[n]['Ports'][pin])
                if x.startswith('ff:')and x[3:]not in (first,second)
                and same_clock(g.clock(g.ff[x[3:]]['Ports']['CK']),same)}
            for local in extra:
                inactive=int(g.ff[local]['Parameters']['SET_RESET']=='"SET"')
                try:proof=boolean.release_chain(g,local,inactive);releases.append((local,inactive,proof))
                except(ValueError,KeyError):pass
            require(len(releases)<=1,'synchronizer has ambiguous native local-release chains')
            if releases:
                local,inactive,release_proof=releases[0]
            else:
                local=None;inactive=None
                a,b=g.ff[first],g.ff[second]
                require(a['Primitive']==b['Primitive']and a['Primitive']in ('V_FFASYN','V_FFSYN')and
                    a['Parameters']==b['Parameters']and a['Ports']['CE']==b['Ports']['CE']=="1'b1"and
                    g.support(b['Ports']['D'])=={'ff:'+first},
                    'synchronizer without local release is not an exact async-clear direct pair')
                require(exact.boolean_equal(g.expression(a['Ports']['SR']),g.expression(b['Ports']['SR'])),
                    'direct synchronizer async clear functions differ')
                release_proof={'CommonAsyncClearPair':True,'LocalReleaseGuardPresent':False,
                    'NativeParameters':[a['Parameters'],b['Parameters']]}
            if role=='scalar'and releases:proof=scalar_chain(g,first,second,(local,inactive),family,consumers)
            elif role=='scalar':
                proof=g.chain(first,second,family)
                proof.update(NativeTruthVerified=True,LocalReleaseFF=None,LocalReleaseInactivePhysicalQ=None,
                    FirstStageOnlyFeedsSecondStage=True)
            else:
                # Same first-to-second truth used for scalar bits; a separate
                # source-role check below proves one registered Gray bit.
                proof=scalar_chain(g,first,second,(local,inactive),family,consumers)if releases else g.chain(first,second,family)
                representation='registered_Gray_Q'
                try:source=resolve_ff(g,family,aliases)
                except ValueError:
                    maximum=6 if family.startswith(CAP+'pixels/')else 9 if family.startswith('system/display_fifo/')else None
                    require(bit==maximum and re.search(r'/(?:wr|rd)_gray\[\d+\]$',family),
                        'only the exact FIFO pointer MSB can share registered binary/Gray identity')
                    binary=family.replace('_gray[','_binary[');source=resolve_ff(g,binary,aliases)
                    representation='registered_binary_MSB_equals_Gray_MSB_by_xor_definition_and_common_reset'
                leaves=g.support(g.ff[first]['Ports']['D'])-({'ff:'+local}if local else set())
                require(leaves<={'ff:'+source,'ff:'+first}and'ff:'+source in leaves,
                    'Gray first stage mixes bits or bypasses registered source')
                proof.update(GraySourceFF=source,GraySourceLogical=family,GrayBit=bit,
                    GraySourceNativeRepresentation=representation,
                    SourcePeriodNS=g.clock(g.ff[source]['Ports']['CK'])['PeriodNS'])
            proof.update(Role=role,Family=family,FirstLogical=firstq,SecondLogical=secondq,
                NativeLocalReleaseProof=release_proof)
            rows.append(proof)
        except(ValueError,KeyError)as e:missing.append({'Code':'SynchronizerNativeProofIncomplete','Logical':firstq,'Detail':str(e)})
    return rows,missing


def typed_macro_inventory(g):
    """Retain current macro inputs/clock roots; no FF clock is invented."""
    rows=[];mode_rows,missing=macro_modes.review_macros(g)
    mode_by={r['Cell']:r for r in mode_rows}
    for n,c in sorted(g.cells.items()):
        kind=c['Primitive']
        if kind not in typed.MACRO_CLOCKS and kind not in ('V_GPLL','V_PPLL','V_IOCLKDIV_E3','V_IODELAY_E2'):continue
        p=c['Ports'];parameters=c['Parameters'];clockpins=typed.MACRO_CLOCKS.get(kind,())
        clocks=[]
        active={r['Pin']:r['SelectedValue']for r in mode_by.get(n,{}).get('ActiveInputs',[])}
        selected_clockpins=[pin for pin in clockpins if n not in mode_by or pin in active]
        for pin in selected_clockpins:
            if not atoms(p.get(pin,"1'b0")):continue
            try:
                if not g.support(p[pin]):
                    values=boolean.possible(g.expression(p[pin]),{})
                    require(len(values)==1,'macro clock constant truth is not unique')
                    clocks.append({'Pin':pin,'Nature':'constant_clock_tie','Value':next(iter(values))})
                else:
                    try:clocks.append({'Pin':pin,**g.clock(p[pin])})
                    except ValueError:
                        require(kind in typed.PHY,'only a typed PHY can consume an external DDR strobe')
                        clocks.append({'Pin':pin,**external_ddr_strobe(g,p[pin])})
            except(ValueError,KeyError)as e:missing.append({'Code':'MacroClockUnresolved','Cell':n,'Pin':pin,'Detail':str(e)})
        inputs=[];lutram_wdi_selection=None
        for pin,value in p.items():
            if pin in clockpins or g.models[kind]['Ports'].get(pin)!='INPUT':continue
            if n in mode_by:
                if pin not in active:continue
                value=active[pin]
            elif kind=='V_RAM32X2'and pin=='WDI':
                outputs=macro_modes.bits(p['RDO'],2);data_bits=macro_modes.bits(value,2)
                selected=[v for out,v in zip(outputs,data_bits)if any(nn!=n and
                    g.models[g.cells[nn]['Primitive']]['Ports'].get(pp)=='INPUT'for nn,pp in g.scalar_refs.get(out,[]))]
                value=selected[0]if len(selected)==1 else'{'+','.join(selected)+'}'
                lutram_wdi_selection={'OriginalWDI':p['WDI'],'SelectedWDI':value,
                    'RDOActualConsumerBindings':[{'Net':out,'Consumers':g.scalar_refs.get(out,[])}for out in outputs],
                    'IndependentOneBitMemoryChildrenVerifiedByBoundModel':True}
            try:support=sorted(g.support(value))
            except(ValueError,KeyError)as e:
                missing.append({'Code':'MacroInputSupportUnresolved','Cell':n,'Pin':pin,'Detail':str(e)})
                support=['unresolved:'+canon(value)]
            domains=set()
            for token in support:
                if token.startswith('ff:'):domains.add(g.clock(g.ff[token[3:]]['Ports']['CK'])['Domain'])
            inputs.append({'Pin':pin,'Support':support,'FFDomains':sorted(domains)})
            if any(x.startswith('unknown_constant:')for x in support):
                missing.append({'Code':'MacroUnusedPortModeReviewRequired','Cell':n,'Pin':pin,'Support':support})
        row={'Cell':n,'Primitive':kind,'Parameters':parameters,'ClockBindings':clocks,'InputBindings':inputs,
            'VendorModel':g.models[kind]['Reference'],'OrdinaryFFClaimed':False,'ExceptionsGenerated':False}
        if n in mode_by:row['ActiveBitModeProof']=mode_by[n]
        if lutram_wdi_selection is not None:row['LUTRAMWDISelection']=lutram_wdi_selection
        if not n.startswith(DDR):
            allowed={x['Domain']for x in clocks if'Domain'in x}
            if not allowed and kind=='V_APM_E2':
                # A constant-clock DSP can still be a combinational operator.
                # Aggregate actual input domains; exact register/bypass mode
                # acceptance remains an explicit primitive-mode obligation.
                allowed={d for item in inputs for d in item['FFDomains']}
            fifo=next((prefix for prefix in (CAP+'pixels/','system/display_fifo/')if n.startswith(prefix)),None)
            if len(allowed)>1 and not fifo:
                missing.append({'Code':'ProcessingMacroMultipleClocks','Cell':n,'ClockDomains':sorted(allowed)})
            for item in inputs:
                domains=allowed
                if kind in ('V_RAM32X2','V_RAM64X1')and item['Pin']=='RADDR':
                    domains=set(item['FFDomains'])
                    if len(domains)!=1:missing.append({'Code':'AsynchronousRAMReadAddressMixedDomains','Cell':n,**item})
                    row['ReadAddressClockDomains']=sorted(domains)
                    row['AsynchronousReadAddressIsNotWCLKFlipFlop']=True
                if fifo and kind.startswith('V_DRM'):
                    # Narrow TDP port ownership is not inferred from all-clock
                    # union: each address/data/enable uses its own port clock.
                    side='A'if item['Pin']in ('DIA','ADDRA','CEA','WEA','OCEA','RSTA')else'B'if item['Pin']in ('DIB','ADDRB','CEB','WEB','OCEB','RSTB')else None
                    if item['Pin']=='DIB'and parameters.get('RAM_MODE')=='"SIMPLE_DUAL_PORT"'and int(parameters['DATA_WIDTH_A'])>36:
                        side='A';row['WideSDPDIBIsPortAWriteData']=True
                    domains={x['Domain']for x in clocks if x['Pin']=='CLK'+side}if side else allowed
                if set(item['FFDomains'])-domains:
                    if kind in ('V_RAM32X2','V_RAM64X1')and item['Pin']=='WE':
                        row['ForeignWriteEnableRequiresExactScope']=True
                    else:missing.append({'Code':'ProcessingMacroForeignInput','Cell':n,**item})
            if kind=='V_APM_E2':
                row['ModeReview']='All input/CE/reset/MODE operands and register/bypass outputs stay in the same actual core domain; internal timing remains ordinary.'
            elif kind.startswith('V_DRM'):
                require(parameters.get('RAM_CASCADE','"NONE"')=='"NONE"'and
                    parameters.get('ECC_READ_EN','"FALSE"')=='"FALSE"'and
                    parameters.get('ECC_WRITE_EN','"FALSE"')=='"FALSE"','unreviewed new RAM cascade/ECC mode')
        rows.append(row)
    g.current_macro_inventory={r['Cell']:r for r in rows}
    return rows,missing


def external_ddr_strobe(g,net):
    """Trace the model's gated/delayed DQSI to actual differential pads.

    No PLL frequency, clock phase or ordinary FF timing root is invented.
    """
    n,pin=g.driver(net);c=g.cells[n]
    require(g.models['V_DDC_E2']['Reference']['SHA256']=='c027722638f7db1d08da558b75b15096b38c2d6051dc3b4fc701ad70c6c861b7',
        'external strobe model changed')
    trace=[];pending=[net]
    if c['Primitive']=='V_DDC_E2':
        require(pin in ('DQSI_DELAY','DQSIB_DELAY'),'unreviewed DDC strobe output')
        trace=[{'Cell':n,'Primitive':c['Primitive'],'Output':pin,'Parameters':c['Parameters'],
        'Model':g.models['V_DDC_E2']['Reference'],'SourcePin':'DQSI',
        'Gate':'dqs_ena','InputFunction':'dqs_ena && DQSI'if pin=='DQSI_DELAY'else'~(dqs_ena && DQSI)',
        'TrainableDelayCodeInputs':{k:v for k,v in c['Ports'].items()if k.startswith(('DQS','DLY','DIRECTION','MOVE','RST','TRAIN'))}}]
        pending=[c['Ports']['DQSI']]
    pads=set();seen=set()
    while pending:
        value=canon(pending.pop());require(value not in seen,'external strobe input cycle');seen.add(value)
        if value in g.ports:
            require(g.ports[value]in ('INPUT','INOUT'),'strobe ends at an output pad');pads.add(value);continue
        driver,op=g.driver(value);d=g.cells[driver];kind=d['Primitive']
        require(kind in ('V_BUF','V_IBUF','V_IBUFDS'),'unreviewed strobe pad/buffer path: '+kind)
        inputs=['I','IB']if kind=='V_IBUFDS'else['I']
        trace.append({'Cell':driver,'Primitive':kind,'Output':op,'Parameters':d['Parameters'],
            'ActualInputNets':{ip:d['Ports'][ip]for ip in inputs}})
        pending.extend(d['Ports'][ip]for ip in inputs)
    require(len(pads)==2 and any(re.fullmatch(r'mem_dqs\[\d+\]',p)for p in pads)and
        any(re.fullmatch(r'mem_dqs_n\[\d+\]',p)for p in pads),'external strobe does not bind one actual DDR differential pair')
    return {'Nature':'SourceSynchronousDDRStrobe','SourceSynchronousDDRStrobe':True,'NativeRoot':n+'/'+pin,
        'SourcePads':sorted(pads),'Trace':trace,'FrequencyHz':None,'PeriodNS':None,
        'FrequencyOrPhaseInferredFromPLL':False,'TrainingAndResetRemainTypedVendorBoundary':True,
        'TimingAccepted':False}


def relationship_role(g,s,d,pin,aliases,chains):
    sc=g.clock(g.ff[s]['Ports']['CK'])['Domain'];dc=g.clock(g.ff[d]['Ports']['CK'])['Domain']
    if s.startswith(DDR)and d.startswith(DDR):return 'vendor_DDR_timed_native_boundary'
    if {sc,dc}=={'cfg_clk','board27'}:return 'related_cfg_board_remains_timed'
    first=next((r for r in chains if r['First']==d),None)
    if pin=='D'and first:
        if first['Role']=='gray':return 'gray_first_stage'if first['GraySourceFF']==s else'unclassified'
        return 'scalar_first_stage'
    sq=identities(g,s,aliases);dq=identities(g,d,aliases)
    if d.startswith(DDR)and pin=='SR'and 'power_ready'in sq:
        require(exact.boolean_equal(g.expression(g.ff[d]['Ports']['SR']),
            ('not',exact.and_expression([g.expression('nt_reset_n'),g.expression('power_ready')]))),
            'vendor ordinary global reset has another actual Boolean source')
        return 'vendor_global_common_reset_remains_timed'
    # SR is functional data when synthesis encodes logic there. Only reset
    # dependence on the actual board's epoch registers receives reset review.
    if pin=='SR'and any(x in ('power_ready','pipeline_release')for x in sq):
        return 'coordinated_common_reset_requires_guard'
    if pin in ('D','CE')and any(x in ('power_ready','pipeline_release')for x in sq)and any(
        x=='system/input_link/shared_writes/last_owner'for x in dq):return 'user_synchronous_reset_requires_guard'
    roles=[(CAP+r'grant_(?:bank_hold|id_hold\[\d+\])',CAP+r'pending_(?:bank|id\[\d+\])','capture_grant_held'),
        (DMA+r'active_(?:bank|id\[\d+\])',CAP+r'pending_(?:bank|id\[\d+\])','capture_grant_held'),
        (CAP+r'end_(?:good|bank|id\[\d+\]|pixels\[\d+\]|crc\[\d+\]|fault\[\d+\])',
            DMA+r'(?:end_(?:good|bank|id\[\d+\]|pixels\[\d+\]|crc\[\d+\]|fault\[\d+\])|aborting|state(?:_reg)?\[\d+\]|write_index\[\d+\]|last_drop_fault\[\d+\])','capture_end_held'),
        (OUT+r'request_epoch\[\d+\]',r'system/(?:request_epoch_hold|grant_epoch)\[\d+\]','scan_request_epoch_held'),
        (r'system/grant_(?:valid|epoch\[\d+\]|checksum\[\d+\]|id\[\d+\]|bank)',OUT+r'.+','scan_grant_held'),
        (OUT+r'(?:done_(?:good|bank|epoch\[\d+\]|id\[\d+\]|crc\[\d+\])|consumed_pixels\[\d+\])',
            r'system/(?:pixel_done_(?:good|bank|id\[\d+\]|crc\[\d+\]|epoch\[\d+\]|count\[\d+\])|controller_failed|controller_fault\[\d+\])','scan_done_held'),
        (r'board_fault\[\d+\]',r'system/(?:system_fault\[\d+\]|system_failed)','board_fault_sticky_held'),
        (r'board_failed',r'system/system_fault\[(?:5|7)\]','board_fault_sticky_held'),
        (r'board_fault\[\d+\]',r'status_uart/snapshot\[\d+\]','diagnostic_board_fault_sticky_held'),
        (r'board_failed',r'status_uart/snapshot\[\d+\]','diagnostic_board_fault_sticky_held'),
        (r'system/system_fault\[\d+\]',OUT+r'.+','system_fault_sticky_held')]
    if any(re.search(r'(?:reset|_sync|_ref|enable_pix|no_grant_s)[^/]*\[',x)for x in dq):return 'unclassified'
    for source,target,role in roles:
        if any(re.fullmatch(source,x)for x in sq)and any(re.fullmatch(target,x)for x in dq):return role
    if d.startswith(OUT)and dc=='pixel_clk':
        # PDS may expose a local RAM write-address FF as a site-local Q
        # instead of the source tail[] name. The compiled output instance
        # owns this actual native consumer; protocol role still comes only
        # from the exact registered held source bundle, never its prefix.
        if any(re.fullmatch(r'system/grant_(?:valid|epoch\[\d+\]|checksum\[\d+\]|id\[\d+\]|bank)',x)for x in sq):
            require(not any(n==d for row in chains for n in (row['First'],row['Second'])),
                'held grant bypasses an unrelated synchronizer')
            return 'scan_grant_held'
        if any(re.fullmatch(r'system/system_fault\[\d+\]',x)for x in sq):return 'system_fault_sticky_held'
    return 'unclassified'


def foreign_inventory(g,aliases,chains):
    rows=[];other=[];missing=[];counts=Counter()
    clocks={n:g.clock(c['Ports']['CK'])for n,c in g.ff.items()}
    for clock in clocks.values():counts[clock['Domain']]+=1
    for d,c in sorted(g.ff.items()):
        for pin in ('D','CE','SR'):
            for token in sorted(g.support(c['Ports'][pin])):
                if not token.startswith('ff:'):
                    other.append({'DestinationFF':d,'Pin':pin,'Source':token,'DestinationClock':clocks[d]['Domain']});continue
                s=token[3:]
                if clocks[s]['Domain']==clocks[d]['Domain']:continue
                role=relationship_role(g,s,d,pin,aliases,chains)
                rows.append({'SourceFF':s,'DestinationFF':d,'DestinationPin':pin,'SourceClock':clocks[s]['Domain'],
                    'DestinationClock':clocks[d]['Domain'],'SourceLogicalQ':canon(g.ff[s]['Ports']['Q']),
                    'DestinationLogicalQ':canon(c['Ports']['Q']),'SourceAliases':identities(g,s,aliases),
                    'DestinationAliases':identities(g,d,aliases),'Role':role,
                    'ExceptionProposed':role not in ('unclassified','related_cfg_board_remains_timed','vendor_DDR_timed_native_boundary','vendor_global_common_reset_remains_timed'),
                    'TimedWithoutException':role in ('related_cfg_board_remains_timed','vendor_DDR_timed_native_boundary','vendor_global_common_reset_remains_timed')})
                if role=='unclassified':missing.append({'Code':'UnknownUserCrossing','Index':len(rows)-1,'SourceFF':s,'DestinationFF':d,'Pin':pin})
    return rows,other,dict(counts),missing


def current_vendor_reset_report(report):
    """Adapt only one Design token; retain original path lines and encoding."""
    digest=hashlib.sha256();replacements=0
    with tempfile.TemporaryDirectory(prefix='fisheye-vendor-reset-')as temporary:
        path=Path(temporary)/'report.rtr'
        with Path(report).open(encoding='gb18030')as source,path.open('w',encoding='utf-8',newline='\n')as out:
            for line in source:
                m=re.fullmatch(r'\| Design\s*:\s*(\S+)\s*',line)
                if m:
                    require(m[1]==TARGET,'current native timing report targets another design')
                    line=line[:m.start(1)]+'camera_vga_output_top'+line[m.end(1):];replacements+=1
                digest.update(line.encode('utf-8'));out.write(line)
        require(replacements==1,'one actual report Design header required')
        paths,summaries=vendor_reset.parse_report(path)
    # User reset failures remain separately inventoried; the vendor parser's
    # strict complete arithmetic applies only to its exact five clock families.
    other={str(k):v for k,v in summaries.items()if not vendor_reset.targeted_pair(k[1],k[2])}
    inventory=vendor_reset.audit_inventory(paths,{k:v for k,v in summaries.items()
        if vendor_reset.targeted_pair(k[1],k[2])},require_complete=True)
    return inventory,{'OriginalEncoding':'gb18030_strict','DesignTokenReplacements':replacements,
        'NormalizedSHA256':digest.hexdigest(),'NativeNamesAndLineNumbersUnchanged':True,
        'OtherRecoverySummariesRemainTimedAndSeparatelyReviewed':other}


def launch_identity(g,route,mapper,ff):
    p=parent(ff);q=canon(g.ff[ff]['Ports']['Q']);outputs=mapper.outputs[p].get(q,[])
    require(len(outputs)==1 and(p,'CLK')in route['Pins'],'actual launch lacks exact native Q/CLK binding: '+ff)
    match=re.search(r'/(FFAPP|FF)([0-3])/FF$',ff);require(match is not None,'unknown actual FF slot')
    site=g.g['FFPlacement'][ff]['Site']
    return p+'/CLK',p+'/'+outputs[0],site+('/CR'if match[1]=='FFAPP'else'/Q')+match[2],route['Pins'][p,'CLK']


def compact_clock_proof(g,scope,variants,proof):
    key='clk-'+hashlib.sha256((scope['FromCLK']+'|'+scope['LaunchQ']).encode()).hexdigest()[:24]
    if not hasattr(g,'native_source_clock_proofs'):g.native_source_clock_proofs={}
    if key not in g.native_source_clock_proofs:
        g.native_source_clock_proofs[key]={k:v for k,v in proof.items()if k!='EndpointUnchanged'}
    else:require(g.native_source_clock_proofs[key]=={k:v for k,v in proof.items()if k!='EndpointUnchanged'},
        'one shared clock-source identity has inconsistent actual proof')
    return {k:proof[k]for k in ('Verified','PhysicalCLK','CLKNet','CompanionQLaunchesAdmitted','LaunchQUnchanged')}|{
        'SharedSourceClockProofKey':key}


def current_vendor_reset_graph(g,queries):
    """Current typed DDR graph, including a reset shared with LUT.Z5.

    The legacy graph required the same expression specifically on Z. This
    checks the actual output expression and actual complete reset fanout.
    """
    prefix=DDR+'u_ddrphy_top/';sync=prefix+'u_ddrphy_rst_seq_rstn_sync/'
    chain=[n for n in g.ff if n.startswith(sync)]
    require(len(chain)==2,'two actual DDR entry asynchronous FFs required')
    firsts=[n for n in chain if any(x.startswith('macro:')and x.endswith('/LOCK')for x in g.support(g.ff[n]['Ports']['D']))]
    require(len(firsts)==1,'DDR entry first stage must sample actual startup PLL LOCK')
    first=firsts[0];second=next(n for n in chain if n!=first)
    params={'GRS_EN':'"TRUE"','SET_RESET':'"RESET"','LRS_EN':'"TRUE"','INIT':"1'b0"}
    for ff in chain:
        require(g.ff[ff]['Primitive']=='V_FFASYN'and g.ff[ff]['Parameters']==params and
            g.ff[ff]['Ports']['CE']=="1'b1",'DDR entry FF parameters changed')
    require(g.support(g.ff[second]['Ports']['D'])=={'ff:'+first},'DDR entry is not a direct two-stage chain')
    require(g.clock(g.ff[first]['Ports']['CK'])['Domain']==g.clock(g.ff[second]['Ports']['CK'])['Domain']=='rst_clk',
        'DDR entry clock roots differ')
    require({(n,p)for n,c in g.ff.items()for p in ('D','CE','SR')if'ff:'+first in g.support(c['Ports'][p])}=={(second,'D')},
        'DDR entry first stage has extra FF consumers')
    locknet=g.ff[first]['Ports']['D'];pll,pin=g.driver(locknet)
    require(g.cells[pll]['Primitive']=='V_GPLL'and pin=='LOCK','startup LOCK driver changed')
    require(set(g.scalar_refs[canon(locknet)])=={(pll,'LOCK'),(first,'D')},
        'DDR startup LOCK has an extra actual bypass consumer')
    trace=g.clock(g.ff[first]['Ports']['CK'])['Trace']
    require(any(r['Cell']==pll and r['Primitive']=='V_GPLL'for r in trace),
        'DDR entry clock and sampled LOCK come from different actual PLLs')
    clear_expr=('not',exact.and_expression([g.expression('nt_reset_n'),g.expression('power_ready')]))
    clears=[]
    for value in sorted({canon(g.ff[first]['Ports']['SR']),canon(g.ff[second]['Ports']['SR']),canon(g.cells[pll]['Ports']['RST'])}):
        require(exact.boolean_equal(g.expression(value),clear_expr),'actual DDR startup clear is not common reset')
        n,op=g.driver(value);require(g.cells[n]['Primitive']in ('V_LUT6CARRY','V_BUF','V_INV'),
            'startup clear has an unknown actual driver')
        clears.append({'Net':value,'ActualDriver':n+'/'+op,'Expression':g.expression(value),
            'CommonResetBooleanCofactorVerified':True,'Z5SharingExplicitlyAllowedByTruthNotName':op=='Z5'})
    groups=[]
    for query in queries:
        if query['EntryRDC']:continue
        targets=[]
        for endpoint in query['Targets']:
            p,pin=endpoint.rsplit('/',1)
            primitive,port={'ISR_IOLHR':('V_ISERDES_E2','RST'),'OSR_IOLHR':('V_OSERDES_E2','RST'),
                'TSR':('V_OSERDES_E2','RST'),'RST_TRAINING_N':('V_DDC_E2','RST_TRAINING_N'),
                'RST':('V_CLKPD'if'cpd_inst'in p else'V_DDC_E2','RST')}[pin]
            matches=[n for n,c in g.cells.items()if n.startswith(p+'/')and c['Primitive']==primitive]
            require(len(matches)==1,'reported DDR primitive target has no unique actual typed instance')
            n=matches[0];targets.append({'NativeTarget':endpoint,'FunctionalCell':n,'Primitive':primitive,
                'Pin':port,'Net':canon(g.cells[n]['Ports'][port])})
        nets={t['Net']for t in targets};require(len(nets)==1,'one DDR reset family has more than one actual direct reset net')
        net=next(iter(nets));source,op=g.driver(net)
        require(source in g.ff and op=='Q'and g.ff[source]['Primitive']=='V_FFASYN','DDR reset is not a direct asynchronous FF output')
        clock=g.clock(g.ff[source]['Ports']['CK'])
        require(clock['Domain']==('ddrphy_sysclk'if query['Family']=='training_reset'else'rst_clk'),
            'actual DDR reset source domain differs')
        groups.append({'NativeSource':query['Source'],'FunctionalSource':{'Name':source,**g.ff[source]},
            'Clock':clock,'Targets':targets,'TargetCount':len(targets),'ActualDirectResetNet':net})
    return {'Status':'pass','Stages':[{'Name':n,**g.ff[n]}for n in (first,second)],
        'CommonResetFunctions':clears,'StartupPLL':{'Name':pll,**g.cells[pll]},'InternalDriverGroups':groups,
        'CurrentTypedTargetsVerified':True,'HistoricalEndpointCountsInherited':False,
        'AnalogMTBFProven':False,'TimingAccepted':False}


def vendor_reset_inventory(g,route,mapper,report,text):
    inventory,adapter=current_vendor_reset_report(report);queries,_,_=vendor_reset.query_scope(inventory)
    require({q['Family']for q in queries}=={'entry_rdc','cpd_reset','dqs_reset','iol_reset','training_reset'},
        'current DDR reset source families differ')
    structure=current_vendor_reset_graph(g,queries)
    require(structure['Status']=='pass','actual current DDR reset graph failed')
    actualtargets={t['NativeTarget']:t for row in structure['InternalDriverGroups']for t in row['Targets']}
    rows=[];groups=exact.clock_variant_groups(g,route)
    checks=inventory['Corners']['slow']['Checks']
    for item in checks:
        fromclk=item['Source'];p=fromclk.rsplit('/',1)[0]
        sources=[n for n in g.ff if parent(n)==p]
        # The graph proves the reset net's direct source FF; packed siblings
        # cannot replace its actual Q even when sharing the printed CLK.
        target=actualtargets.get(item['Endpoint'])
        if target:
            sources=[n for n in g.ff if canon(g.ff[n]['Ports']['Q'])==canon(target['Net'])]
        else:
            endpoint_parent=item['Endpoint'].rsplit('/',1)[0]
            destinations=[n for n,c in g.ff.items()if parent(n)==endpoint_parent]
            entry=structure['Stages'][0]['Name']
            require(entry in destinations and all(n in {r['Name']for r in structure['Stages']}for n in destinations),
                'entry DDR physical reset pin has an unrelated packed FF')
            require(all(exact.boolean_equal(g.expression(g.ff[n]['Ports']['SR']),g.expression(g.ff[entry]['Ports']['SR']))for n in destinations),
                'packed DDR entry FFs have different actual reset functions')
            support=g.support(g.ff[entry]['Ports']['SR']);destinations=[entry]
            sources=[n for n in sources if'ff:'+n in support]
        require(len(sources)==1,'DDR reset reported CLK does not identify its actual direct launch Q')
        ff=sources[0];original,q,physical,net=launch_identity(g,route,mapper,ff)
        if target:destination={'Cell':target['FunctionalCell'],'Primitive':target['Primitive'],
            'Pin':target['Pin'],'Endpoint':item['Endpoint']}
        else:destination={'Cell':destinations[0],'Primitive':g.ff[destinations[0]]['Primitive'],
            'Pin':'SR','Endpoint':item['Endpoint']}
        row={'FromCLK':original,'LaunchQ':q,'Endpoint':item['Endpoint'],'Family':item['Family'],
            'LaunchClock':item['LaunchClock'],'CaptureClock':item['CaptureClock'],
            'TargetKind':'DDRPrimitiveReset','GuardAccepted':True,
            'GuardProof':{'NativeVendorResetGraphPassed':True,'CurrentReportCoverageVerified':True,
                'HistoricalEndpointCountsInherited':False,'NativeReportCheck':item},
            'NativeObjects':{'SourceFFs':[ff],'SourcePhysicalQ':[physical],'SourceCLKNet':[net],
                'DestinationObjects':[destination]}}
        row['FromCLKVariants'],row['FromCLKVariantProof']=exact.source_clock_variants(g,route,row,groups)
        require(fromclk in row['FromCLKVariants'],'report prints CLK outside same-site/net aliases')
        rows.append(row)
    return rows,{'Passed':True,'CurrentReport':native.ref(report),'Inventory':inventory,'ReportAdapter':adapter,
        'NativeGraph':structure,'HistoricalEndpointCountsInherited':False,'TimingAccepted':False}


def map_scopes(g,route,mapper,rows):
    mapped=[];data={};resets={};syncresets={};missing=[];endpoint_support={};source_launches={};boundary_cache={};launch_cache={};boundary_proofs={}
    for i,row in enumerate(rows):
        if not row['ExceptionProposed']:mapped.append(row);continue
        try:
            m=mapper.map(row);s=row['SourceFF']
            if s not in launch_cache:launch_cache[s]=launch_identity(g,route,mapper,s)
            clock,q,physical,net=launch_cache[s]
            require(s not in source_launches or source_launches[s]==q,'one functional source has conflicting native launch Q')
            source_launches[s]=q
            m.update(SourcePhysicalQ=physical,SourceNativeCLKNet=net)
            table=resets if row['Role']=='coordinated_common_reset_requires_guard'else syncresets if row['Role']=='user_synchronous_reset_requires_guard'else data
            for boundary in m['NativeBoundaries']:
                functional_net=boundary['FunctionalBoundaryNet']
                if functional_net not in boundary_cache:boundary_cache[functional_net]=sorted(mapper.support(functional_net))
                supported=boundary_cache[functional_net]
                endpoint=boundary['Endpoint']
                if endpoint in endpoint_support:
                    require(endpoint_support[endpoint]['SourceFFs']==supported,
                        'one native endpoint has inconsistent complete functional source support')
                else:
                    endpoint_support[endpoint]={'SourceFFs':supported,'LaunchQs':[],
                        'FunctionalBoundaryNet':boundary['FunctionalBoundaryNet'],
                        'NativeBoundaryNet':boundary['NativeBoundaryNet'],'SourceSupportComplete':True,
                        'TypedBoundaryCuts':sorted(x for x in g.support(functional_net)if not x.startswith('ff:'))}
                key=clock,q,boundary['Endpoint']
                scope=table.setdefault(key,{'FromCLK':clock,'LaunchQ':q,'Endpoint':key[2],
                    'Role':row['Role'],'Roles':[],'RelationshipIndexes':[],
                    'SourceDomain':row['SourceClock'],'DestinationDomain':row['DestinationClock'],
                    'NativeObjects':{k:[]for k in ('SourceFFs','DestinationFFs','SourcePhysicalQ','SourceCLKNet')}})
                scope['Roles'].append(row['Role']);scope['RelationshipIndexes'].append(i)
                for k,value in [('SourceFFs',s),('DestinationFFs',row['DestinationFF']),
                    ('SourcePhysicalQ',physical),('SourceCLKNet',net)]:scope['NativeObjects'][k].append(value)
                if table is data:
                    source_period=g.clock(g.ff[s]['Ports']['CK'])['PeriodNS']
                    target_period=g.clock(g.ff[row['DestinationFF']]['Ports']['CK'])['PeriodNS']
                    maximum=source_period if row['Role']=='gray_first_stage'else target_period
                    scope['MaximumNS']=min(scope.get('MaximumNS',maximum),maximum)
                    scope['BoundBasis']='GraySourcePeriod'if row['Role']=='gray_first_stage'else'ScalarHeldDestinationPeriod'
                else:
                    scope.update(GuardAccepted=False,GuardProof={'Missing':['actual destination local-release next-Q guard pending']})
                    if table is syncresets:scope.update(TargetKind='FFSynchronousResetFunction',FunctionalDestinationPin=row['DestinationPin'])
            compact=[]
            for boundary in m['NativeBoundaries']:
                proofkey=row['DestinationFF']+'|'+row['DestinationPin']+'|'+boundary['Endpoint']
                if proofkey not in boundary_proofs:boundary_proofs[proofkey]=boundary
                compact.append({k:boundary[k]for k in ('Endpoint','FunctionalBoundaryNet','NativeBoundaryNet')if k in boundary}|{'NativeBoundaryProofKey':proofkey})
            m['NativeBoundaries']=compact;mapped.append(m)
        except(ValueError,KeyError)as e:
            mapped.append({**row,'NativeMappingError':str(e)})
            missing.append({'Code':'NativeUserMappingIncomplete','RelationshipIndex':i,'Detail':str(e)})
    groups=exact.clock_variant_groups(g,route)
    variants_cache={}
    for scope in list(data.values())+list(resets.values())+list(syncresets.values()):
        scope['NativeObjects']={k:sorted(set(v))for k,v in scope['NativeObjects'].items()}
        scope['Roles']=sorted(set(scope['Roles']))
        scope['Role']='+'.join(scope['Roles'])
        cachekey=scope['FromCLK'],scope['LaunchQ'],tuple(scope['NativeObjects']['SourceFFs'])
        if cachekey not in variants_cache:variants_cache[cachekey]=exact.source_clock_variants(g,route,scope,groups)
        variants,proof=variants_cache[cachekey]
        scope['FromCLKVariants'],scope['FromCLKVariantProof']=variants,compact_clock_proof(g,scope,variants,proof)
    for value in endpoint_support.values():
        value['LaunchQs']=sorted({source_launches[ff]for ff in value['SourceFFs']if ff in source_launches})
        value['QualifiedSourceFFs']={ff:source_launches[ff]for ff in value['SourceFFs']if ff in source_launches}
        value['AllActualSourceFFsRetained']=True
        value['NativeQProjectionLimitedToQualifiedForeignSources']=True
    g.native_endpoint_support=endpoint_support
    g.native_boundary_proofs=boundary_proofs
    g.user_sync_reset_scopes=[syncresets[k]for k in sorted(syncresets)]
    return mapped,[data[k]for k in sorted(data)],[resets[k]for k in sorted(resets)],missing


def macro_crossings(g,route,mapper,aliases,macro_rows,relationship_offset):
    """Actual LUTRAM WE consumers are endpoints, never implicit FF waivers."""
    rows=[];data=[];syncresets=[];missing=[];variants=exact.clock_variant_groups(g,route)
    for item in macro_rows:
        if not item.get('ForeignWriteEnableRequiresExactScope'):continue
        n=item['Cell'];c=g.cells[n];p=n.rsplit('/',2)[0];nativewe=route['Pins'].get((p,'WE'))
        try:
            require(nativewe is not None,'actual LUTRAM WE endpoint missing')
            clocks=[r for r in item['ClockBindings']if r['Pin']=='WCLK'];require(len(clocks)==1,'one real LUTRAM WCLK required')
            clock=clocks[0];net=c['Ports']['WE'];alias=mapper.signal_alias(net,nativewe)
            require(c['Parameters']['WE_POL']in ('"TRUE"','"FALSE"'),'unknown functional RAM write-enable polarity')
            active=int(c['Parameters']['WE_POL']=='"TRUE"');inverted=bool(alias and alias['Inverted'])
            item['NativeWEConnection']={'FunctionalWE':canon(net),'NativeWE':nativewe,'Inverted':inverted,
                'FunctionalActiveWriteValue':active,'FunctionalInactiveValue':1-active,
                'NativeActiveWriteValue':active^int(inverted),'NativeInactiveValue':(1-active)^int(inverted),
                'AliasProof':alias,'Basis':'same-ADF vendor functional export, bound RAM32X2/RAM32X1 behavior and actual route alias',
                'EncryptedNativeOperatorDecoded':False,'NativeInstance':route['Instances'][p]}
            endpoint=p+'/WE';obj={'Cell':n,'Primitive':c['Primitive'],'Pin':'WE','Endpoint':endpoint}
            support=sorted(mapper.support(net));qualified={}
            for source in support:
                source_clock=g.clock(g.ff[source]['Ports']['CK'])
                if source_clock['Domain']==clock['Domain']:continue
                names=identities(g,source,aliases)
                reset=any(x in ('power_ready','pipeline_release')for x in names)
                held=any(re.fullmatch(r'system/grant_(?:valid|epoch\[\d+\]|checksum\[\d+\]|id\[\d+\]|bank)',x)for x in names)
                fault=any(re.fullmatch(r'system/system_fault\[\d+\]',x)for x in names)
                require(reset or held or fault,'LUTRAM write enable has an unclassified foreign actual source: '+source)
                if held or fault:require(n.startswith(OUT),'held scan grant/fault drives a RAM outside actual scan storage')
                role='user_synchronous_reset_requires_guard'if reset else'scan_grant_held'if held else'system_fault_sticky_held'
                fromclk,q,physical,clknet=launch_identity(g,route,mapper,source);qualified[source]=q
                boundary={'Endpoint':endpoint,'FunctionalBoundaryNet':net,'NativeBoundaryNet':nativewe,
                    'BoundaryNet':canon(net),'NetAliasProof':alias,'BoundaryToLogicalFF':[]}
                proofkey=n+'|WE|'+endpoint
                if proofkey not in g.native_boundary_proofs:g.native_boundary_proofs[proofkey]=boundary
                compact_boundary={k:boundary[k]for k in ('Endpoint','FunctionalBoundaryNet','NativeBoundaryNet')}|{'NativeBoundaryProofKey':proofkey}
                row={'SourceFF':source,'SourceLogicalQ':canon(g.ff[source]['Ports']['Q']),
                    'DestinationObject':obj,'TargetKind':'MacroFunctionalInput','DestinationPin':'WE',
                    'SourceClock':source_clock['Domain'],'DestinationClock':clock['Domain'],'Role':role,
                    'ExceptionProposed':True,'TimedWithoutException':False,'NativeBoundaries':[compact_boundary],
                    'SourceNativeClockPin':fromclk,'SourceNativeOutputPin':q,'SourcePhysicalQ':physical,
                    'SourceNativeCLKNet':clknet,'SourcePlacement':g.g['FFPlacement'][source]}
                index=relationship_offset+len(rows);rows.append(row)
                scope={'FromCLK':fromclk,'LaunchQ':q,'Endpoint':endpoint,'Role':role,'Roles':[role],
                    'RelationshipIndexes':[index],'SourceDomain':source_clock['Domain'],'DestinationDomain':clock['Domain'],
                    'TargetKind':'MacroFunctionalInput','NativeObjects':{'SourceFFs':[source],
                        'DestinationFFs':[],'DestinationObjects':[obj],'SourcePhysicalQ':[physical],'SourceCLKNet':[clknet]}}
                if reset:
                    scope.update(TargetKind='MacroWriteEnableResetFunction',FunctionalDestinationPin='WE',
                        GuardAccepted=False,GuardProof={'Missing':['actual local release inactive RAM WE proof pending']})
                    syncresets.append(scope)
                else:
                    scope.update(MaximumNS=clock['PeriodNS'],BoundBasis='HeldMacroWriteClockPeriod')
                    data.append(scope)
                names,clock_proof=exact.source_clock_variants(g,route,scope,variants)
                scope['FromCLKVariants'],scope['FromCLKVariantProof']=names,compact_clock_proof(g,scope,names,clock_proof)
            g.native_endpoint_support[endpoint]={'SourceFFs':support,'LaunchQs':sorted(set(qualified.values())),
                'QualifiedSourceFFs':qualified,'FunctionalBoundaryNet':net,'NativeBoundaryNet':nativewe,
                'SourceSupportComplete':True,'AllActualSourceFFsRetained':True,
                'NativeQProjectionLimitedToQualifiedForeignSources':True,
                'TypedBoundaryCuts':sorted(x for x in g.support(net)if not x.startswith('ff:'))}
        except(ValueError,KeyError)as e:missing.append({'Code':'MacroForeignWriteEnableReviewIncomplete','Cell':n,'Detail':str(e)})
    return rows,data,syncresets,missing


def normalize_relationships(g,aliases,rows):
    """Keep every relationship; intern repeated functional identity evidence."""
    ffset={r[k]for r in rows for k in ('SourceFF','DestinationFF')if k in r}
    identities_table={n:{'FunctionalQ':canon(g.ff[n]['Ports']['Q']),'Placement':g.g['FFPlacement'][n],
        'LogicalRoles':identities(g,n,aliases)}for n in sorted(ffset)}
    omitted={'SourceLogicalQ','DestinationLogicalQ','SourcePlacement','DestinationPlacement','SourceAliases','DestinationAliases'}
    return [{k:v for k,v in r.items()if k not in omitted}for r in rows],identities_table


def normalize_non_ff_support(rows):
    grouped=defaultdict(list)
    for r in rows:grouped[r['DestinationFF'],r['Pin'],r['DestinationClock']].append(r['Source'])
    sets={};out=[]
    for (ff,pin,clock),values in sorted(grouped.items()):
        values=sorted(set(values));key=hashlib.sha256(json.dumps(values,separators=(',',':')).encode()).hexdigest()
        require(key not in sets or sets[key]==values,'native support-set digest collision');sets[key]=values
        out.append({'DestinationFF':ff,'Pin':pin,'DestinationClock':clock,'SupportSetKey':key})
    return {'Schema':'complete-non-FF-support-sets-v1','Consumers':out,'SourceSets':sets,
        'AllNonFFSourceTokensRetained':True,'UnknownsNotConvertedToPrimaryInputs':True}


def user_reset_guards(g,reset_scopes,sync_scopes,consumers,chains=(),aliases=None,admission=None):
    """Bounded native local-inactive guards; no whole-FSM induction claim."""
    releases=[];by_last={};missing=[]
    for ff,c in sorted(g.ff.items()):
        if c['Primitive']!='V_FFASYN':continue
        predecessors=mapper_support={x[3:]for x in g.support(c['Ports']['D'])if x.startswith('ff:')and x[3:]!=ff}
        if len(predecessors)!=1:continue
        first=next(iter(predecessors))
        if first not in g.ff or g.ff[first]['Primitive']!='V_FFASYN':continue
        if consumers['ff:'+first]!={(ff,'D')}:continue
        try:proof=boolean.release_chain(g,ff,int(c['Parameters']['SET_RESET']=='"SET"'))
        except(ValueError,KeyError):continue
        proof.update(DestinationClock=g.clock(c['Ports']['CK'])['Domain'],NativeTruthVerified=True,
            FirstPlacement=g.g['FFPlacement'][first],SecondPlacement=g.g['FFPlacement'][ff])
        try:proof.update(g.chain(first,ff,'actual current local-reset release'))
        except ValueError:pass
        releases.append(proof);by_last[ff]=proof
    membership={n:p for p in releases for n in (p['First'],p['Second'])}
    scalar_members={}
    for p in chains:
        if not p.get('NativeLocalReleaseProof',{}).get('CommonAsyncClearPair'):continue
        if g.ff[p['First']]['Primitive']!='V_FFASYN':continue
        for n in (p['First'],p['Second']):scalar_members[n]=p
    targetproof={}
    for scope in reset_scopes+sync_scopes:
        proofs=[]
        try:
            objects=scope['NativeObjects'];targets=objects['DestinationFFs']
            if scope.get('TargetKind')=='MacroWriteEnableResetFunction':
                for obj in objects['DestinationObjects']:
                    c=g.cells[obj['Cell']];expr=g.expression(c['Ports']['WE']);support=boolean.boolean.leaves(expr)
                    connection=g.current_macro_inventory[obj['Cell']]['NativeWEConnection']
                    disabled=connection['FunctionalInactiveValue']
                    choices=[]
                    for ff in sorted(by_last):
                        if'ff:'+ff not in support:continue
                        proof=by_last[ff];inactive=proof['InactivePhysicalQ'][1]
                        if boolean.possible(expr,{'ff:'+ff:inactive})=={disabled}:choices.append((ff,proof,inactive))
                    require(len(choices)==1,'RAM WE has no unique actual local-release inactive-zero proof')
                    ff,proof,inactive=choices[0]
                    actual=g.native_mapper.native_expression(connection['NativeWE'])
                    native_values=boolean.possible(actual,{'ff:'+ff:inactive})
                    require(native_values=={connection['NativeInactiveValue']},'native write-enable alias does not preserve the proved inactive value')
                    proofs.append({'Cell':obj['Cell'],'NativeEndpoint':obj['Endpoint'],'LocalReleaseFF':ff,
                        'InactivePhysicalQ':inactive,'FunctionalWEInactivePossibilities':[disabled],
                        'NativeWEInactivePossibilities':sorted(native_values),'NativeWEConnection':connection,
                        'NativeLocalReleaseProof':proof})
                scope['GuardProof']={'NativeNextQInactiveGuardVerified':True,'NativeWEInactiveGuardVerified':True,
                    'LocalReleaseChainVerified':True,'OnlyResetFunctionProven':True,'BusinessDataPathWaiver':False,
                    'ActualConsumerProofs':proofs,'FullNativeFSMInductionClaimed':False}
            else:
                for target in targets:
                    if target in targetproof:proofs.append(targetproof[target]);continue
                    if target in membership:
                        proof={'DestinationFF':target,'Role':'actual local asynchronous-assert two-stage release FF',
                            'ReleaseChain':membership[target],'NativeNextQInactiveGuardVerified':True,
                            'FirstStageConsumersRestrictedToSecondD':True}
                    elif target in scalar_members:
                        require(admission and admission['Passed'],'scalar common-epoch reset needs reviewed startup admission')
                        proof={'DestinationFF':target,'ProofKind':'isolated_two_stage_async_scalar_common_clear',
                            'NativeNextQInactiveGuardVerified':False,'NativeExactPairIsolationAndCommonClearVerified':True,
                            'FirstStageIsMetastabilityBoundary':True,'ActualSynchronizer':scalar_members[target],
                            'CommonEpochLocalResetSourceContractVerified':admission['LocalCoreResetContract']['Passed'],
                            'AnalogMTBFProven':False,'ArbitrarySelfInactiveConstantClaimed':False}
                    else:
                        expected=next_q_possibilities(g,target,{'primary:reset_n':0})
                        require(len(expected)==1,'global reset assertion does not force one actual consumer Q')
                        support=set.union(*(g.support(g.ff[target]['Ports'][p])for p in ('D','CE','SR')))
                        choices=[]
                        for local in by_last:
                            if'ff:'+local not in support:continue
                            if not same_clock(g.clock(g.ff[target]['Ports']['CK']),g.clock(g.ff[local]['Ports']['CK'])):continue
                            rel=by_last[local];inactive=rel['InactivePhysicalQ'][1]
                            if next_q_possibilities(g,target,{'ff:'+local:inactive})==expected:choices.append((local,rel,inactive))
                        require(choices,'actual consumer next-Q lacks a native local-release inactive guard: '+target)
                        require(all(same_clock(g.clock(g.ff[target]['Ports']['CK']),g.clock(g.ff[local]['Ports']['CK']))for local,_,_ in choices),
                            'inactive consumer guard crosses clock roots')
                        proof={'DestinationFF':target,'NativeResetQ':next(iter(expected)),
                            'NativeNextQInactiveGuardVerified':True,'GuardChoices':[{'LocalReleaseFF':local,
                                'InactivePhysicalQ':inactive,'NextQPossibilities':sorted(expected),'NativeLocalReleaseProof':rel}
                                for local,rel,inactive in choices],'FullNativeFSMInductionClaimed':False}
                    targetproof[target]=proof;proofs.append(proof)
                scope['GuardProof']={'NativeNextQInactiveGuardVerified':all(p.get('NativeNextQInactiveGuardVerified')is True for p in proofs),'LocalReleaseChainVerified':True,
                    'OnlyResetFunctionProven':True,'BusinessDataPathWaiver':False,'ActualConsumerProofs':proofs,
                    'FullNativeFSMInductionClaimed':False}
            scope['GuardAccepted']=True
        except(ValueError,KeyError)as e:
            scope.update(GuardAccepted=False,GuardProof={'Missing':[str(e)]})
            missing.append({'Code':'UserLocalResetGuardIncomplete','FromCLK':scope['FromCLK'],
                'LaunchQ':scope['LaunchQ'],'Endpoint':scope['Endpoint'],'Detail':str(e)})
    return releases,{'Verified':not missing,'GuardProofsByFF':targetproof,
        'KeyReleaseChain':None,'FullNativeFSMInductionClaimed':False},missing


def core_link_reset_inventory(g,aliases,releases,build_dir,watched):
    """C's synchronous consumer reset is proved with arbitrary prior state.

    The forced value is read from the actual next-Q function, and may differ
    from GRS INIT or logical RTL reset polarity. No DDR ready/idle assumption
    and no established-state induction is used.
    """
    rows=[];missing=[];source={}
    for name in ('rtl/experimental/hdmi_camera_fisheye_system_c.v',
            'rtl/experimental/hdmi_camera_fisheye_input_link.v','rtl/ddr_write_arbiter.v'):
        path=Path(build_dir)/'compiled'/name;native.add(watched,path)
        source[name]=build.pins.clean_verilog(path.read_text(encoding='utf-8-sig'))
    arb=source['rtl/ddr_write_arbiter.v'];block=re.search(r'if\s*\(!rst_n\)\s*begin(.*?)end\s*else\s*begin',arb,re.S)
    require(block is not None,'current arbiter reset assignments are not explicit')
    assignments={name:value.strip()for name,value in re.findall(r'\b(\w+)\s*<=\s*([^;]+);',block[1])}
    require(assignments=={'state':'IDLE','owner':'0','last_owner':'1','address':'0','length':'0',
        'beat':'0','watchdog':'0','failed':'0','fault':'0','bursts0':'0','bursts1':'0'},
        'source logical arbiter reset assignments changed')
    targets=sorted(n for n in g.ff if n.startswith('system/input_link/shared_writes/'))
    contract=resolve_ff(g,'system/input_link/contract_failed',aliases)
    targets=sorted(set(targets+[contract]));require(len(targets)>1,'no actual C writer/contract consumers')
    proofs={p['Second']:p for p in releases};nominations=set()
    for n in targets:
        for pin in ('D','CE','SR'):
            nominations|={x[3:]for x in g.support(g.ff[n]['Ports'][pin])if x.startswith('ff:')and x[3:]in proofs}
    choices=[]
    for local in sorted(nominations):
        release=proofs[local];inactive=release['InactivePhysicalQ'][1];fixed={'ff:'+local:inactive};items=[]
        for target in targets:
            if not same_clock(g.clock(g.ff[target]['Ports']['CK']),g.clock(g.ff[local]['Ports']['CK'])):break
            forced=next_q_possibilities(g,target,fixed)
            if len(forced)!=1:break
            items.append({'ActualFF':target,'Placement':g.g['FFPlacement'][target],
                'NativeInactiveQ':next(iter(forced)),'GRSINIT':g.ff[target]['Parameters']['INIT'],
                'IndependentOfArbitraryPriorQAndBusinessInputs':True,
                'NativeSET_RESET':g.ff[target]['Parameters']['SET_RESET'],
                'NativeDCE_SR':boolean.expressions(g,target)})
        else:choices.append((local,release,fixed,items))
    if len(choices)!=1:
        missing.append({'Code':'CWriterLocalResetStrongCofactorIncomplete','ActualConsumers':len(targets),
            'QualifiedLocalReleaseChoices':len(choices),'NominatedLocalReleaseFFs':sorted(nominations)})
    else:
        local,release,fixed,rows=choices[0]
    return {'Passed':not missing,'SourceResetAssignments':assignments,'ActualConsumerCount':len(targets),
        'LocalReleaseFF':choices[0][0]if choices else None,'LocalReleaseProof':choices[0][1]if choices else None,
        'Fixed':choices[0][2]if choices else None,'ActualConsumerCofactors':rows,
        'ArbitraryPriorStateGuardVerified':not missing,'GRSINITNotSubstitutedForOperationalReset':True,
        'DDRReadyValueAssumed':False,'EstablishedIdleStateAssumed':False,'FullNativeFSMInductionClaimed':False,
        'Missing':missing,'Violations':[]}


def constraint_groups(scopes,endpoint_support=None):
    """Lossless grouping of an exact native Q/end support matrix.

    The printed report need not enumerate this whole matrix. Every group
    retains all allowed pairs, and final reported paths must be a subset.
    Grouping never changes the registered sources or constraint budgets.
    """
    groups=defaultdict(list)
    for index,row in enumerate(scopes):
        groups[row['Role'],row['MaximumNS'],row.get('SourceDomain'),row.get('DestinationDomain')].append(index)
    result=[]
    for (role,maximum,source_domain,destination_domain),indexes in sorted(groups.items()):
        pairs=defaultdict(list)
        for index in indexes:pairs[scopes[index]['LaunchQ'],scopes[index]['Endpoint']].append(index)
        group={'Role':role,'MaximumNS':maximum,'SourceDomain':source_domain,'DestinationDomain':destination_domain,'ScopeIndexes':indexes,
            'FromCLKs':sorted({name for i in indexes for name in scopes[i]['FromCLKVariants']}),
            'LaunchQs':sorted({scopes[i]['LaunchQ']for i in indexes}),
            'Endpoints':sorted({scopes[i]['Endpoint']for i in indexes}),
            'AllowedPairs':[{'LaunchQ':q,'Endpoint':end,'ScopeIndexes':members}for(q,end),members in sorted(pairs.items())],
            'ReportedEnumerationComplete':False,'FunctionalNativeSupportMatrixComplete':False,
            'MatrixConstraintCoverageComplete':False,'ConstraintsApplied':False}
        if endpoint_support is not None:
            actual={(q,end)for end in group['Endpoints']for q in endpoint_support[end]['LaunchQs']if q in group['LaunchQs']}
            require(actual==set(pairs),'group axes include a supported Q/end pair outside this exact same-role/budget matrix')
            group['FunctionalNativeSupportMatrixComplete']=True
            group['NativeSupportMatrixProof']={'AllAxisCrossProductsCheckedAgainstCompleteNativeEndpointSupport':True,
                'SourceDomain':source_domain,'DestinationDomain':destination_domain,
                'SupportedAxisPairs':len(actual),'MissingPairs':[],'UnexpectedPairs':[]}
        result.append(group)
    require(sorted(i for row in result for i in row['ScopeIndexes'])==list(range(len(scopes))),
        'constraint grouping drops or repeats a native scope')
    return result


def review_typed_matrix_cuts(g,groups):
    """A filtered FF cut is complete only if every omitted leaf is typed.

    Clocked memory state is a boundary; asynchronous RAM read addresses were
    already expanded by Graph.support. A combinational DSP cannot hide a
    foreign launch when its complete selected-input partition is local.
    """
    rows=[];missing=[];seen=set();shared={};endpoints={}
    for group in groups:
        for endpoint in group['Endpoints']:
            key=endpoint,group['DestinationDomain']
            if key in seen:continue
            seen.add(key);support=g.native_endpoint_support[endpoint]
            tokens=support.get('TypedBoundaryCuts',[])
            endpoints[endpoint]={'DestinationDomain':group['DestinationDomain'],'TypedCuts':tokens}
            for token in tokens:
                proofkey=token+'|'+group['DestinationDomain']
                if proofkey in shared:continue
                try:
                    if token=='primary:reset_n':
                        shared[proofkey]={'Token':token,'Nature':'common board reset input',
                            'ResetGraphAcceptanceRequired':True,'ForeignLaunchFFHidden':False};continue
                    require(token.startswith('macro:'),'unreviewed non-FF boundary in grouped matrix: '+token)
                    name,pin=token[6:].rsplit('/',1);c=g.cells[name];kind=c['Primitive'];p=c['Ports']
                    if kind in ('V_RAM32X2','V_RAM64X1'):
                        clock=g.clock(p['WCLK']);nature='clocked memory state plus completely expanded asynchronous RADDR'
                    elif kind.startswith('V_DRM'):
                        wide=int(c['Parameters']['DATA_WIDTH_B'])>(36 if kind=='V_DRM36K_E1'else 31)
                        side='B'if c['Parameters']['RAM_MODE']=='"SIMPLE_DUAL_PORT"'and wide or pin=='DOB'else'A'
                        clock=g.clock(p['CLK'+side]);nature='actual synchronous memory read-state boundary'
                    elif kind=='V_APM_E2':
                        record=g.current_macro_inventory[name]
                        require(record['ActiveBitModeProof']['Passed'],'unreviewed processing DSP selected mode')
                        domains={d for item in record['InputBindings']for d in item['FFDomains']}
                        clock={'Domain':next(iter(domains))}if len(domains)==1 else next(
                            (v for v in record['ClockBindings']if'Domain'in v),{})
                        require(domains<={group['DestinationDomain']},'DSP cut hides selected foreign FF input')
                        nature='selected DSP inputs local in fully reviewed processing partition'
                    else:raise ValueError('matrix contains an unsupported typed output boundary: '+kind)
                    require(clock.get('Domain')==group['DestinationDomain'],'typed matrix cut is not local to its destination')
                    shared[proofkey]={'Token':token,'Nature':nature,'Clock':clock,
                        'ForeignLaunchFFHidden':False,'ActualModel':g.models[kind]['Reference']}
                except(ValueError,KeyError)as e:missing.append({'Code':'NativeMatrixTypedCutIncomplete','Endpoint':endpoint,'Token':token,'Detail':str(e)})
    return {'Passed':not missing,'EndpointCuts':endpoints,'SharedCutProofs':shared,'Missing':missing,'Violations':[],
        'AllActualSourceFFsRetained':True,'OnlyQualifiedGroupSourceFFsProjectedToNativeQ':True,
        'MacroLeavesNotSilentlyDiscarded':True}


def native_clock_review(g,report):
    cores=[n for n in g.ff if n.startswith('system/bank_core/engine/core/mapper/')]
    require(cores,'current mapper has no actual core-domain FF')
    clock=g.clock(g.ff[cores[0]]['Ports']['CK'])
    require(clock['Domain']=='ddrphy_sysclk'and abs(clock['PeriodNS']-8.)<1e-9,
        'current native processing clock is not constrained8ns')
    cells=[row for row in clock['Trace']if row['Primitive']=='V_GPLL']
    require(len(cells)==1,'processing clock does not trace to one actual vendor GPLL')
    n=cells[0]['Cell'];c=g.cells[n];p=c['Ports'];params=c['Parameters']
    require(params['INTERNAL_FB']=='"CLKOUTF"'and params['EXTERNAL_FB']=='"DISABLE"'and
        params['SSC_MODE']=='"DISABLE"','unreviewed core PLL feedback/spread mode')
    numerator=int(params['STATIC_RATIOM'])*int(params['STATIC_RATIOF'])
    denominator=int(params['STATIC_RATIOI'])*int(params['STATIC_RATIO0'])
    require(numerator==denominator and numerator>0,'core native ratio is not1:1')
    for pin in ('APB_EN','APB_SEL','APB_WRITE','CLKIN_SEL','PLL_PWD'):
        require(boolean.possible(g.expression(p[pin]),{})=={0},'core PLL frequency controls are dynamic: '+pin)
    upstream=g.clock(p['CLKIN1']);require(upstream['Domain']=='ref_clk'and upstream['PeriodNS']==8.,
        'core PLL input is not current8ns differential reference clock')
    actual=[]
    with Path(report).open(encoding='gb18030')as stream:
        for line_no,line in enumerate(stream,1):
            if line_no>300:break
            if re.match(r'^\s+ddrphy_sysclk\s+8\.0000\s+\{0\.0000 4\.0000\}\s+Generated \(ref_clk\)',line):
                actual.append({'Line':line_no,'Text':line.rstrip()})
    require(len(actual)==1 and '/ddrphy_gpll/'in actual[0]['Text'],'current native clock table differs from actual GPLL root')
    return {'CoreClock':{'Domain':'ddrphy_sysclk','FrequencyHz':125000000,'PeriodNS':8.,
        'NativeRoot':clock['Root'],'Trace':clock['Trace'],'CurrentGeneratedClockVerified':True,
        'PLLParametersVerified':True,'FrequencyBasis':'current_constraint_and_native_1_to_1_clock_trace',
        'ConstrainedCoreMHz':125,'InputParameterMetadataMHz':float(params['CLKIN_FREQ']),
        'PhysicalFrequencyMeasured':False,'NativeRatioNumerator':numerator,'NativeRatioDenominator':denominator,
        'PLLCell':n,'PLLParameters':params,'UpstreamClock':upstream,'CurrentReportClockTable':actual,
        'DynamicPhaseControlChangesFrequency':False,
        'Limits':'Native/FDC clock relationship and timing basis; absolute hardware frequency must be cross-checked by host arrival/core tick measurements.'}}


def pin_inventory(g,build_dir,watched):
    paths=[Path(build_dir)/'compiled'/build.FDC,Path(build_dir)/'device_map'/(TARGET+'.pcf'),
        Path(build_dir)/'place_route'/(TARGET+'_prr_route_optimize.prt')]
    for path in paths:native.add(watched,path)
    fdc=build.pins.fdc_pins(paths[0].read_text());pcf=build.pins.pcf_pins(paths[1].read_text())
    _,routed=build.pins.routed_pads(paths[2].read_text())
    require(set(g.ports)==set(fdc)==set(pcf)==set(routed),'current declared/FDC/PCF/routed port sets differ')
    rows=[]
    for pad,direction in sorted(g.ports.items()):
        require(direction==fdc[pad]['DIRECTION']==routed[pad]['Direction']and
            fdc[pad]['LOC']==routed[pad]['Pad']and pcf[pad]=={k:v for k,v in fdc[pad].items()if k!='DIRECTION'},
            'actual pin direction/location/electrical differs: '+pad)
        refs=[{'Cell':n,'Pin':pin,'Primitive':g.cells[n]['Primitive']}for n,pin in g.scalar_refs.get(pad,[])]
        rows.append({'Port':pad,'Direction':direction,'Attributes':pcf[pad],'Route':routed[pad],
            'FunctionalConnections':refs,'NativeDisposition':'active'if refs else'native_disconnected_requires_review'})
    return {'Declared':len(rows),'Routed':len(rows),'Active':sum(bool(r['FunctionalConnections'])for r in rows),
        'UnusedPads':[r['Port']for r in rows if not r['FunctionalConnections']],
        'Inventory':rows,'NativeElectricalParametersVerified':False}


def derive(build_plan,export_receipt,route_receipt):
    build_plan=Path(build_plan).resolve();export_receipt=Path(export_receipt).resolve();route_receipt=Path(route_receipt).resolve()
    partitions,watched=source_inventory(build_plan)
    for path in boolean.static_helpers(SELF):native.add(watched,path)
    native.add(watched,boolean.PYTHON);initial=dict(watched)
    exported,inputs=native.bind_receipt(export_receipt);native.merge(watched,inputs)
    routed,inputs=native.bind_receipt(route_receipt);native.merge(watched,inputs)
    require(exported['Mode']=='export'and routed['Mode']in ('query','report')and
        all(exported[k]==routed[k]for k in ('BuildPlanSHA256','SourceADF','SourceADFSHA256'))and
        exported['BuildPlanSHA256']==sha(build_plan),'native fisheye export/route lineage differs')
    report=native.artifact(export_receipt,exported,TARGET+'.rtr');native.add(watched,report)
    refs={'BuildPlan':native.ref(build_plan),'ExportReceipt':native.ref(export_receipt),'RouteReceipt':native.ref(route_receipt),
        'SourceADF':native.ref(exported['SourceADF']),
        'NativeNetlist':native.ref(native.artifact(export_receipt,exported,TARGET+'_sim.v')),
        'RouteDump':native.ref(native.artifact(route_receipt,routed,'route-dump.txt')),
        'BaselineTimingReport':native.ref(report)}
    g,route,mapper,inputs=native_graph(refs);native.merge(watched,inputs)
    aliases,alias_proof=scoped_aliases(g,build_plan.parent,watched)
    consumers=consumer_index(g);chains,missing=chain_inventory(g,aliases,consumers)
    macro,issues=typed_macro_inventory(g);missing+=issues
    rows,other,clock_counts,issues=foreign_inventory(g,aliases,chains);missing+=issues
    mapped,data,resets,issues=map_scopes(g,route,mapper,rows);missing+=issues
    macro_rows,macro_data,macro_resets,issues=macro_crossings(g,route,mapper,aliases,macro,len(mapped));missing+=issues
    mapped+=macro_rows;data+=macro_data
    mapped,ff_identities=normalize_relationships(g,aliases,mapped)
    sync_resets=g.user_sync_reset_scopes+macro_resets
    source_admission,inputs=startup.review(build_plan,export_receipt);native.merge(watched,inputs)
    release_chains,local_guards,issues=user_reset_guards(g,resets,sync_resets,consumers,chains,aliases,source_admission);missing+=issues
    core_link_reset=core_link_reset_inventory(g,aliases,release_chains,build_plan.parent,watched)
    missing+=core_link_reset['Missing']
    try:
        key=resolve_ff(g,'key_reset_sync[1]',aliases)
        local_guards['KeyReleaseChain']=boolean.release_chain(g,key,int(g.ff[key]['Parameters']['SET_RESET']=='"SET"'))
    except(ValueError,KeyError)as e:missing.append({'Code':'KeyReleaseNativeProofIncomplete','Detail':str(e)})
    pins=pin_inventory(g,build_plan.parent,watched)
    sampling,sampler_release=boolean.sampler_inventory(g)
    vendor_scopes=[];vendor_proof=None
    try:vendor_scopes,vendor_proof=vendor_reset_inventory(g,route,mapper,report,Path(refs['NativeNetlist']['Path']).read_text(encoding='utf-8-sig'))
    except(ValueError,KeyError)as e:missing.append({'Code':'NativeVendorResetReviewIncomplete','Detail':str(e)})
    source_protocol,inputs=protocol.review(build_plan,export_receipt);native.merge(watched,inputs)
    groups=constraint_groups(data,g.native_endpoint_support)
    matrix_review=review_typed_matrix_cuts(g,groups)
    missing+=matrix_review['Missing']
    for path,h in initial.items():require(sha(path)==h,'audit helper changed during derivation: '+str(path))
    vendor_passed=bool(vendor_proof and vendor_proof['Passed'])
    user_passed=not any(x['Code']not in ('NativeVendorResetReviewIncomplete','MacroClockUnresolved')for x in missing)
    protocol_passed=source_protocol['Passed']and user_passed
    if not missing:
        partitions.update(NativeEvidenceComplete=True,Missing=[],Violations=[])
    partitions['CurrentNativeEvidence']={'TypedMacrosVerified':not any(x['Code'].startswith(('Macro','ProcessingMacro'))for x in missing),
        'ActualForeignSupportMatrixVerified':user_passed,'VendorResetGraphVerified':vendor_passed,
        'OrdinaryProcessingAndVendorTimingAcceptanceDeferredToFreshSTA':True}
    result={'Schema':SCHEMA,'Target':TARGET,**refs,'SourcePartitions':partitions,'Pins':pins,
        'ActualCells':len(g.cells),'ActualFFs':len(g.ff),'PrimitiveCounts':dict(Counter(c['Primitive']for c in g.cells.values())),
        'ClockDefinitions':g.clocks,'ClockTopology':{'FFCountsByClock':clock_counts},'PrimitiveBoundaries':macro,
        'LogicalAliasRecovery':alias_proof,'Synchronizers':chains,'ReleaseChains':release_chains,
        'LocalResetGuards':local_guards,'SourceSampling':sampling,
        'ForeignRelationships':mapped,'FunctionalFFIdentities':ff_identities,
        'NonFFSequentialSupport':normalize_non_ff_support(other),'DataScopes':data,
        'BoundBasisDefinitions':{'GraySourcePeriod':'Registered single-bit Gray source period, with the interstage path ordinarily timed.',
            'ScalarHeldDestinationPeriod':'One actual destination period bounded by the two-stage token and reviewed held-data protocol; no interstage exception.',
            'HeldMacroWriteClockPeriod':'One actual destination WCLK period; scan grant is stable through the complete display lease, and sticky fault is stable until the common reset epoch.'},
        'NativeEndpointSupport':g.native_endpoint_support,
        'SharedNativeBoundaryProofs':g.native_boundary_proofs,'SharedSourceClockProofs':g.native_source_clock_proofs,
        'QualifiedTimingControlEndpointProofs':mapper.control_proofs,
        'NativeOutputSlotWitnesses':{'/'.join(key):sorted(v)for key,v in sorted(mapper.output_witnesses.items())},
        'ConstraintGroups':groups,'ResetScopes':resets,'UserSynchronousResetScopes':sync_resets,
        'NativeSupportTypedCutReview':matrix_review,'UserProtocolReview':source_protocol,
        'StartupAdmissionReview':source_admission,'CoreLinkLocalResetReview':core_link_reset,
        'VendorResetScopes':vendor_scopes,'VendorResetProof':vendor_proof,
        'NativeClockReview':native_clock_review(g,report),
        'NativeAcceptance':{'ResetAccepted':local_guards['Verified']and vendor_passed,'ProtocolSafetyAccepted':protocol_passed,
            'SourceSamplingIsolatedVerified':sampling['SourceSamplingIsolatedVerified'],
            'VendorDDRClockResetAccepted':vendor_passed and not any(x['Code']=='MacroClockUnresolved'for x in missing),
            'FrameBoundaryViewSelectionAccepted':source_protocol['NativeFrameModeReview']['Passed'],
            'FisheyeProfileAccepted':True,'UserCDCAccepted':user_passed,'Missing':missing,'Violations':[]},
        'Blockers':missing,'ProposalReady':not missing,'ConstraintsApplied':False,'TimingAccepted':False,
        'ExternalACAccepted':False,'HardwareReleaseAllowed':False,'HardwareAccessed':False,'BitstreamRequested':False,
        'InputSHA256':{str(p):h for p,h in sorted(watched.items(),key=lambda item:str(item[0]))}}
    return result,watched


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('build-plan','export-receipt','route-receipt','output-dir'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args(argv);out=build.work_path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    value,_=derive(args.build_plan,args.export_receipt,args.route_receipt);write(out/'scope.json',value)
    print(json.dumps({'Scope':str(out/'scope.json'),'DataScopes':len(value['DataScopes']),
        'ResetScopes':len(value['ResetScopes']),'VendorResetScopes':len(value['VendorResetScopes']),
        'ProposalReady':value['ProposalReady'],'Blockers':value['Blockers'][:10]}));return 0


if __name__=='__main__':raise SystemExit(main())
