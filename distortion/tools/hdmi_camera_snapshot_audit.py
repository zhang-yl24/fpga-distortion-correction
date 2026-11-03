"""Source-bound native inventory of this HDMI snapshot candidate, CPU only.

Reuse frozen Boolean/CLM algorithms, never an old target's counts, roles or
exceptions. Hard RAMs are typed clocked memories, not unknown primary inputs.
"""
import argparse
from collections import Counter,defaultdict
import hashlib
import importlib
import json
from pathlib import Path
import re
import tempfile

import hdmi_camera_snapshot_build_b as build
import hdmi_camera_snapshot_native_b as native
import hdmi_camera_direct_audit as base

SELF=Path(__file__).resolve();TARGET=build.TARGET
SCHEMA='hdmi-camera-snapshot-native-audit-v1'
require,sha,read,write=build.require,build.sha,build.read,build.write
canon,parent=base.canon,base.parent
MODELS={**base.MODELS,
    'V_DRM36K_E1':'224ad428a209ba704b58c24a505b9290648a95e4ae585494b80296bc9e0f1c96',
    'V_RAM32X2':'7cee56e7385cc148c6ea6168736b47ae149d0ecb0c06a4542706c7ac8bf7b7d8',
    'V_RAM64X1':'9db9dff12cad2f7b36faf95fd36cb41cb2c959c4108b033d0dcf69ee729ae8ed'}
MEMORY={'V_DRM18K_E1','V_DRM36K_E1','V_RAM32X2','V_RAM64X1'}


def atoms(value):
    result=[]
    for item in canon(value).strip('{}').split(','):
        if not item:continue
        m=re.fullmatch(r'(.+)\[(\d+):(\d+)\]',item)
        if m:
            hi,lo=map(int,m.groups()[1:]);step=-1 if hi>=lo else 1
            result += [m[1]+f'[{i}]'for i in range(hi,lo+step,step)]
        else:result.append(item)
    return result


class Graph(base.Graph):
    def __init__(self,parsed,ports):
        # Do not mutate the old module's global primitive registry. Native
        # observations belong only to this new graph and target.
        base.raw.Graph.__init__(self,parsed)
        self.ports=ports;self.expr_cache={};self.support_cache={};self.canonical_outputs=defaultdict(list)
        outputs={'V_LUT6CARRY':('Z','Z5','COUT'),'V_BUF':('Z',),'V_INV':('Z',),'V_MUX2':('Z',),
            'V_IBUF':('O',),'V_OBUFT':('O',),'V_GPLL':('CLKOUT0','CLKOUT1','CLKOUT2','CLKOUT3','CLKOUT4','CLKOUT5','LOCK'),
            'V_USCM':('CLKOUT',),'V_GRS':(),'V_DRM18K_E1':('DOA','DOB'),'V_DRM36K_E1':('DOA','DOB'),
            'V_RAM32X2':('RDO',),'V_RAM64X1':('RDO',)}
        for n,c in self.cells.items():
            kind=c['Primitive'];require(kind in MODELS,'unknown snapshot native primitive: '+kind)
            for pin in ('Q',)if n in self.ff else outputs[kind]:
                for net in atoms(c['Ports'].get(pin,'')):self.canonical_outputs[net].append((n,pin))
    def expression(self,net,active=()):
        key=canon(net);drivers=self.canonical_outputs.get(key,[])
        if len(drivers)==1:
            n,p=drivers[0]
            if self.cells[n]['Primitive']in MEMORY:return ('variable','memory:'+n+'/'+p)
        return super().expression(net,active)
    def support(self,net):
        key=canon(net)
        if key in self.support_cache:return self.support_cache[key]
        drivers=self.canonical_outputs.get(key,[])
        if len(drivers)==1:
            n,p=drivers[0];c=self.cells[n]
            if c['Primitive']in MEMORY:
                result={'memory:'+n+'/'+p}
                if c['Primitive']in ('V_RAM32X2','V_RAM64X1'):
                    for value in atoms(c['Ports']['RADDR']):result |= self.support(value)
                self.support_cache[key]=result;return result
        return super().support(net)


def graph(text,build_dir=None,ports=None):
    if isinstance(build_dir,dict):ports=build_dir
    elif build_dir is not None:ports=build.top_ports((Path(build_dir)/'compiled'/build.TOP).read_text(encoding='utf-8-sig'))
    require(ports is not None,'bound snapshot port declarations required')
    require(re.findall(r'(?m)^module\s+(\w+)',text)==[TARGET],'one actual flat snapshot module required')
    adapted=re.sub(r'(?m)^(module\s+)'+TARGET+r'\b',r'\g<1>'+base.syntax.prep.TARGET,text,count=1)
    return Graph(base.syntax.functional(adapted),ports)


class Mapper(base.Mapper):
    def boundaries(self,target,pin):
        if pin not in ('CE','SR'):return super().boundaries(target,pin)
        key=target,pin
        if key in self.boundary_cache:return self.boundary_cache[key]
        p=parent(target);np='CE'if pin=='CE'else'RS';net=self.g.ff[target]['Ports'][pin]
        actual=self.route['Pins'].get((p,np))
        if actual is not None and actual!=canon(net):
            try:
                driver,output=self.g.driver(net);c=self.g.cells[driver];dp=driver.rsplit('/',2)[0]
                require(c['Primitive']=='V_LUT6CARRY'and output in ('Z','Z5'),'control alias is not a placed LUT')
                require(not any(parent(n)==dp for n in self.g.ff),'control alias source has packed sequential outputs')
                require(sum(bool(c['Ports'].get(x))for x in ('Z','Z5','COUT'))==1,'control alias source has multiple functional outputs')
                native_cell=self.route['Cells'][self.route['Instances'][dp]['Cell']]
                outputs=[op for op,direction in native_cell['Ports'].items()if direction=='OUTPUT'and(dp,op)in self.route['Pins']]
                require(len(outputs)==1,'control LUT native output is not unique')
                require(self.route['Pins'][dp,outputs[0]]==actual,'actual native LUT output does not feed target control')
                for ip in base.clm.endpoints.input_pins(c,output):
                    require(self.route['Pins'].get((dp,ip))==canon(c['Ports'][ip]),'native control LUT input net differs')
                parameters={row[1]:row[3]for row in native_cell['Parameters']}
                value=parameters['INIT'];require(value[0]=='BITVEC'and value[1][:2]==['B','64'],'control native INIT shape differs')
                ni=int(value[1][2].strip('"'),2);fi=int(c['Parameters']['INIT'][4:],16)
                require(ni in (fi,fi^((1<<64)-1)),'functional/native control LUT functions are neither equal nor complementary')
                inverted=ni!=fi
                target_params={row[1]:row[3]for row in self.route['Cells'][self.route['Instances'][p]['Cell']]['Parameters']}
                polarity=target_params['LCE_POL'if pin=='CE'else'LRS_POL']
                require(polarity==['STRING','"TRUE"'if inverted else'"FALSE"'],'native control inversion flag does not explain functional alias')
                proof={'Kind':'placed_combinational_control_output_and_target_polarity',
                    'FunctionalDriver':driver+'/'+output,'NativeDriver':dp+'/'+outputs[0],
                    'FunctionalNet':canon(net),'NativeNet':actual,'Inverted':inverted,
                    'NativeControlPolarity':polarity,'NativeINIT':ni,'FunctionalINIT':fi,
                    'InputsExactlyBound':True,'NoPackedSequentialSource':True}
                row={'Endpoint':p+'/'+np,'BoundaryNet':canon(net),'FunctionalBoundaryNet':net,
                    'NativeBoundaryNet':actual,'NetAliasProof':proof,'BoundaryToLogicalFF':[],
                    'PhysicalCLMSite':self.g.g['FFPlacement'][target]['Site']}
                self.boundary_cache[key]=[row];return [row]
            except (ValueError,KeyError):pass
        return super().boundaries(target,pin)


def native_graph(scope):
    watched={};build_dir=Path(scope['BuildPlan']['Path']).parent
    for key in ('BuildPlan','ExportReceipt','RouteReceipt','NativeNetlist','RouteDump'):
        native.add(watched,scope[key]['Path'],scope[key]['SHA256'])
    text=Path(scope['NativeNetlist']['Path']).read_text(encoding='utf-8-sig');g=graph(text,build_dir)
    placements=base.clm.placed_luts(text,g)
    wanted={parent(n)for n in g.ff}|{n.rsplit('/',2)[0]for n in placements}
    with tempfile.TemporaryDirectory(prefix='snapshot-native-route-')as temporary:
        normalized=Path(temporary)/'route.adif';base.calibrated.normalize_source_locations(scope['RouteDump']['Path'],normalized)
        route=base.clm.endpoints.route_objects(normalized,wanted)
    return g,route,Mapper(g,route,placements),watched


def digital_constant(g,value):
    expr=g.expression(value);poss=base.possible(expr,{})
    require(len(poss)==1,'constant native control required: '+canon(value));return next(iter(poss))


def memory_inventory(g):
    rows=[];violations=[]
    for name,c in sorted(g.cells.items()):
        kind=c['Primitive']
        if kind not in MEMORY:continue
        p=c['Ports'];v=c['Parameters'];issues=[]
        if kind in ('V_RAM32X2','V_RAM64X1'):
            clock=g.clock(p['WCLK']);role='same_PCLK_asynchronous_read_line_cache'
            if clock['Domain']!='input_pixel':issues.append('LUTRAM write clock is not source PCLK')
            clocks={'WCLK':clock};mode='asynchronous_RADDR_read_with_clocked_memory_write'
        else:
            clocks={pin:g.clock(p[pin])for pin in ('CLKA','CLKB')};domains=[clocks[x]['Domain']for x in ('CLKA','CLKB')]
            mode=v.get('RAM_MODE');width_a=int(v['DATA_WIDTH_A']);width_b=int(v['DATA_WIDTH_B'])
            try:web=digital_constant(g,p['WEB'])
            except ValueError:web=None
            try:wea=digital_constant(g,p['WEA'])
            except ValueError:wea=None
            if domains==['cfg_clk','cfg_clk']and wea==0 and web==0:
                role='immutable_configuration_ROM'
                if mode!='"SIMPLE_DUAL_PORT"'or width_b!=32:issues.append('unreviewed configuration ROM mode')
            elif domains==['input_pixel','input_pixel']:
                role='same_PCLK_line_pair_cache'
                if web!=0 or width_a!=9 or width_b!=9 or mode not in ('"SIMPLE_DUAL_PORT"','"TRUE_DUAL_PORT"'):issues.append('unreviewed line cache shape')
            elif domains==['input_pixel','board27']:
                role='frozen_snapshot_byte_bank'
                expected={'RAM_MODE':'"TRUE_DUAL_PORT"','DATA_WIDTH_A':'8','DATA_WIDTH_B':'8',
                    'DOB_REG':'1','DOB_REG_CLKINV':'0','DOA_REG':'0','GRS_EN':'"FALSE"','RST_TYPE':'"SYNC"'}
                if any(v.get(k)!=value for k,value in expected.items()):issues.append('snapshot byte-bank primitive mode differs')
                if web!=0:issues.append('reference port B can write')
            else:role='unclassified_memory';issues.append('unreviewed memory clock pair')
            for side in ('A','B'):
                domain=clocks['CLK'+side]['Domain']
                for pin in ('ADDR'+side,'CE'+side,'WE'+side):
                    for value in atoms(p[pin]):
                        if re.fullmatch(r"\d+'b[01]+",value):continue
                        for source in g.support(value):
                            if source.startswith('ff:')and g.clock(g.ff[source[3:]]['Ports']['CK'])['Domain']!=domain:
                                issues.append('memory '+pin+' has foreign FF '+source[3:])
                            elif not source.startswith('ff:'):issues.append('memory '+pin+' has unreviewed input '+source)
        row={'Cell':name,'Primitive':kind,'Role':role,'Mode':mode,'ClockBindings':clocks,
            'OrdinaryFFClaimed':False,'Violations':sorted(set(issues)),
            'ParametersSHA256':hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest(),
            'Parameters':{k:value for k,value in v.items()if not k.startswith('INIT')},
            'VendorModel':{'Path':str(base.MODEL_ROOT/(kind+'.v')),'SHA256':MODELS[kind]},'TimingAccepted':False}
        rows.append(row);violations += [{'Cell':name,'Detail':x}for x in row['Violations']]
    return {'Memories':rows,'CountsByRole':dict(Counter(r['Role']for r in rows)),'Violations':violations,
        'AllMemoryModesAndPortDomainsVerified':not violations}


def port_inventory(g,build_dir,watched):
    paths=[build_dir/'compiled'/build.TOP,build_dir/'compiled'/build.FDC,build_dir/'device_map'/(TARGET+'.pcf'),
        build_dir/'place_route'/(TARGET+'_prr_route_optimize.prt')]
    for p in paths:native.add(watched,p)
    declared=build.top_ports(paths[0].read_text(encoding='utf-8-sig'));fdc=build.pins.fdc_pins(paths[1].read_text())
    pcf=build.pins.pcf_pins(paths[2].read_text());_,routed=build.pins.routed_pads(paths[3].read_text())
    require(set(declared)==set(fdc)==set(pcf)==set(routed),'complete current snapshot declared/FDC/PCF/routed pins differ')
    rows=[]
    for port,direction in sorted(declared.items()):
        require(fdc[port]['DIRECTION']==direction==routed[port]['Direction']and fdc[port]['LOC']==routed[port]['Pad']and
            pcf[port]=={k:v for k,v in fdc[port].items()if k!='DIRECTION'},'snapshot actual pin direction/location/electrical differs: '+port)
        connections=[{'Cell':n,'Pin':pin,'Primitive':c['Primitive']}for n,c in g.cells.items()for pin,value in c['Ports'].items()if canon(value)==port]
        require(connections,'snapshot declared pad is disconnected: '+port)
        rows.append({'Port':port,'Direction':direction,'Attributes':pcf[port],'Route':routed[port],'FunctionalConnections':connections})
    return {'Declared':len(rows),'Routed':len(rows),'Active':len(rows),'UnusedRGBPorts':[],
        'Inventory':rows,'NativeElectricalParametersVerified':False}


def literal_aliases(g,build_dir,watched):
    """Only literal module-port and wire assignments; no state equivalence."""
    names=[('',build.TOP),('capture/',build.CAPTURE),('packetizer/',build.REF),
        ('snapshot_memory/',build.RAM),('snapshot_uart/',build.UART),('input_sampler/',build.SAMPLER)]
    texts={};bounds={};parents={};proof=[]
    def find(n):
        parents.setdefault(n,n)
        if parents[n]!=n:parents[n]=find(parents[n])
        return parents[n]
    def join(a,b,why):
        if a==b:return
        x,y=find(a),find(b)
        if x!=y:parents[y]=x
        proof.append({'Left':a,'Right':b,**why})
    def expand(value,scope,width=None):
        value=re.sub(r'\s+','',value)
        if value.startswith('{')and value.endswith('}'):
            return [x for part in value[1:-1].split(',')for x in expand(part,scope)]
        if re.fullmatch(r'[A-Za-z_]\w*',value)and(value in bounds[scope]or width and width>1):
            hi,lo=bounds[scope][value]if value in bounds[scope]else(width-1,0)
            return [scope+value+f'[{i}]'for i in range(hi,lo-1,-1)]
        if not re.fullmatch(r'[A-Za-z_]\w*(?:\[\d+(?::\d+)?\])?',value):return []
        return [scope+n for n in atoms(value)]
    for scope,name in names:
        p=build_dir/'compiled'/name;native.add(watched,p)
        text=re.sub(r'/\*.*?\*/|//[^\n]*','',p.read_text(encoding='utf-8-sig'),flags=re.S);texts[scope]=text;bounds[scope]={}
        for hi,lo,decl in re.findall(r'\b(?:input|output|wire|reg)\s+(?:(?:wire|reg|signed)\s+)*\[(\d+):(\d+)\]\s+([^;\n]+)',text):
            for item in decl.split(','):
                m=re.match(r'\s*([A-Za-z_]\w*)\b',item)
                if m:bounds[scope][m[1]]=(int(hi),int(lo))
        for lhs,rhs in re.findall(r'\bassign\s+([^;=]+?)\s*=\s*([^;]+);',text):
            left,right=expand(lhs,scope),expand(rhs,scope)
            if left and len(left)==len(right):
                for a,b in zip(left,right):join(a,b,{'Kind':'literal_assign','Scope':scope,'Statement':lhs.strip()+'='+rhs.strip()})
    for scope,name in names[1:]:
        instance=scope[:-1];module={build.CAPTURE:'hdmi_camera_snapshot_capture',build.REF:'hdmi_camera_snapshot_ref',
            build.RAM:'hdmi_camera_snapshot_ram',build.UART:'uart_tx',build.SAMPLER:'hdmi_camera_pixel_sampler'}[name]
        matches=re.findall(r'\b'+module+r'\s*(?:#\s*\(.*?\)\s*)?'+instance+r'\s*\((.*?)\)\s*;',texts[''],re.S)
        require(len(matches)==1,'one snapshot top instance required: '+instance)
        for formal,actual in re.findall(r'\.(\w+)\s*\(([^()]*)\)',matches[0]):
            hi,lo=bounds[scope].get(formal,(0,0));width=hi-lo+1
            left,right=expand(formal,scope,width),expand(actual,'',width)
            if left and len(left)==len(right):
                for a,b in zip(left,right):join(a,b,{'Kind':'literal_instance_port','Instance':instance,'Formal':formal,'Actual':actual.strip()})
    # Native buffers and constantly enabled output buffers are literal
    # connectivity. This recovers top-output aliases without borrowing any
    # packed parent's register index or changing the functional graph.
    for n,c in g.cells.items():
        if c['Primitive']=='V_BUF':
            a,b=canon(c['Ports']['I']),canon(c['Ports']['Z'])
            if not re.fullmatch(r"\d+'b[01]+",a):join(a,b,{'Kind':'native_buffer','Cell':n})
        elif c['Primitive']=='V_OBUFT'and g.ports.get(canon(c['Ports']['O']))=='OUTPUT':
            if digital_constant(g,c['Ports']['T'])==0:
                join(canon(c['Ports']['O']),canon(c['Ports']['I']),{'Kind':'native_output_buffer','Cell':n})
    groups=defaultdict(set)
    for name in list(parents):groups[find(name)].add(name)
    aliases={n:sorted(v)for v in groups.values()for n in v}
    return aliases,proof


def identities(g,name,aliases):
    q=canon(g.ff[name]['Ports']['Q']);return aliases.get(q,[q])


def resolve_ff(g,logical,aliases):
    names=aliases.get(logical,[logical]);candidates=[n for n,c in g.ff.items()if canon(c['Ports']['Q'])in names]
    if not candidates:
        for name in names:
            if name not in g.canonical_outputs:continue
            sources=g.support(name)
            if len(sources)==1 and next(iter(sources)).startswith('ff:'):candidates.append(next(iter(sources))[3:])
        candidates=sorted(set(candidates))
    require(len(candidates)==1,'one actual functional Q for role required: '+logical+': '+str(candidates));return candidates[0]


def synchronizers(g,aliases,source_release,ref_release):
    rows=[]
    for family,release in [('ready_pix',source_release),('capture/request_sync',source_release),
        ('packetizer/boot_sync',ref_release),('packetizer/done_sync',ref_release),
        *[(x,ref_release)for x in ('cfg_lock_ref','rx_done_ref','tx_done_ref','cfg_failed_ref')]]:
        second=resolve_ff(g,family+'[1]',aliases)
        try:first=resolve_ff(g,family+'[0]',aliases)
        except ValueError:
            candidates={x[3:]for x in g.support(g.ff[second]['Ports']['D'])if x.startswith('ff:')and x[3:]!=second and
                g.clock(g.ff[x[3:]]['Ports']['CK'])['Domain']==g.clock(g.ff[second]['Ports']['CK'])['Domain']}
            isolated=[]
            for candidate in candidates:
                consumers={(n,p)for n,c in g.ff.items()for p in ('D','CE','SR')if 'ff:'+candidate in g.support(c['Ports'][p])}
                if consumers=={(second,'D')}:isolated.append(candidate)
            require(len(isolated)==1,'cannot recover unique actual isolated first synchronizer Q: '+family)
            first=isolated[0]
        extra={x[3:]for p in ('D','CE','SR')for x in g.support(g.ff[second]['Ports'][p])if x.startswith('ff:')and x[3:]not in (first,second)and
            g.clock(g.ff[x[3:]]['Ports']['CK'])['Domain']==g.clock(g.ff[second]['Ports']['CK'])['Domain']}
        proved=[]
        for local in extra:
            inactive=int(g.ff[local]['Parameters']['SET_RESET']=='"SET"')
            try:base.release_chain(g,local,inactive);proved.append((local,inactive))
            except(ValueError,KeyError):pass
        require(len(proved)==1,'one proved local release in scalar D/CE/SR required: '+family)
        release=proved[0]
        rows.append(base.scalar_chain(g,first,second,release,family))
    return rows


def role_for(g,s,d,pin,aliases,sync,source_release,ref_ready,power):
    sc=g.clock(g.ff[s]['Ports']['CK'])['Domain'];dc=g.clock(g.ff[d]['Ports']['CK'])['Domain']
    if {sc,dc}=={'cfg_clk','board27'}:return 'related_cfg_board_remains_timed'
    firsts={r['First']:r['Family']for r in sync};sq=identities(g,s,aliases);dq=identities(g,d,aliases)
    if pin=='D'and d in firsts:
        family=firsts[d]
        expected={'ready_pix':{'ref_ready'},'capture/request_sync':{'packetizer/request_toggle'},
            'packetizer/boot_sync':{'capture/history_seen'},'packetizer/done_sync':{'capture/done_hold'}}
        if s==source_release[0]and family in ('packetizer/boot_sync','packetizer/done_sync'):return 'source_release_qualified_'+family
        if set(sq)&expected.get(family,set()):return 'scalar_first_'+family
    if pin=='SR'and sc=='board27'and dc=='input_pixel'and s==power and g.ff[d]['Primitive']=='V_FFASYN':
        return 'common_epoch_input_reset'
    request=lambda q:bool(re.fullmatch(r'packetizer/request_id\[\d+\]',q))
    descriptor=lambda q:bool(re.fullmatch(r'capture/(?:done_id\[\d+\]|source_crc\[\d+\]|native_pixels\[\d+\]|stored_bytes\[\d+\]|fault_hold\[\d+\]|good_hold)',q))
    shadow=lambda q:bool(re.fullmatch(r'packetizer/desc_(?:good|id\[\d+\]|crc\[\d+\]|native_pixels\[\d+\]|stored_bytes\[\d+\]|fault\[\d+\])',q))
    request_dest=lambda q:bool(re.fullmatch(r'capture/(?:done_id\[\d+\]|drain_count\[\d+\]|fault_hold\[\d+\]|good_hold|state\[\d+\])',q))
    if sc=='board27'and dc=='input_pixel'and any(request(q)for q in sq)and any(request_dest(q)for q in dq):
        source_bits={int(m[1])for q in sq if(m:=re.fullmatch(r'packetizer/request_id\[(\d+)\]',q))}
        target_bits={int(m[1])for q in dq if(m:=re.fullmatch(r'capture/done_id\[(\d+)\]',q))}
        if target_bits and(source_bits!=target_bits or pin!='D'):return 'unclassified'
        return 'held_request_ID_after_2FF_and_2_settle'
    if sc=='input_pixel'and dc=='board27'and any(shadow(q)for q in dq)and(any(descriptor(q)for q in sq)or s==source_release[0]):
        return 'held_descriptor_to_unconditional_local_shadow'
    return 'unclassified'


def foreign_inventory(g,aliases,sync,source_release,ref_ready,power):
    rows=[];nonff=[];errors=[];counts=Counter()
    for n,c in g.ff.items():counts[g.clock(c['Ports']['CK'])['Domain']]+=1
    for d,c in sorted(g.ff.items()):
        dc=g.clock(c['Ports']['CK'])['Domain']
        for pin in ('D','CE','SR'):
            for item in sorted(g.support(c['Ports'][pin])):
                if not item.startswith('ff:'):
                    nonff.append({'Source':item,'DestinationFF':d,'DestinationPin':pin,'DestinationClock':dc});continue
                s=item[3:];sc=g.clock(g.ff[s]['Ports']['CK'])['Domain']
                if sc==dc:continue
                role=role_for(g,s,d,pin,aliases,sync,source_release,ref_ready,power)
                row={'SourceFF':s,'DestinationFF':d,'DestinationPin':pin,'SourceClock':sc,'DestinationClock':dc,
                    'SourceLogicalQ':canon(g.ff[s]['Ports']['Q']),'DestinationLogicalQ':canon(c['Ports']['Q']),
                    'SourceAliases':identities(g,s,aliases),'DestinationAliases':identities(g,d,aliases),
                    'Role':role,'ExceptionProposed':role not in ('related_cfg_board_remains_timed','unclassified'),
                    'TimedWithoutException':role=='related_cfg_board_remains_timed'}
                rows.append(row)
                if role=='unclassified':errors.append({'Code':'UnclassifiedForeignRelationship','RelationshipIndex':len(rows)-1,'Source':s,'Destination':d,'Pin':pin})
    return rows,nonff,dict(counts),errors


def clock_variant_groups(g,route):
    """Index concrete CLK aliases, retaining every functional FF identity.

    A physical CLM clock may be printed using any of its packed parents.
    These are clock selectors only: no companion Q becomes a launch source.
    """
    groups=defaultdict(list)
    for ff,c in sorted(g.ff.items()):
        instance=parent(ff);site=g.g['FFPlacement'][ff]['Site']
        net=route['Pins'].get((instance,'CLK'))
        require(net is not None,'placed snapshot FF lacks native CLK connectivity: '+ff)
        groups[site,net].append(ff)
    return groups


def source_clock_variants(g,route,scope,groups=None):
    """Prove the complete same-site, same-native-net CLK selector union.

    The original source Q, physical FF slot and endpoint remain unchanged.
    Same domain alone is insufficient; each admitted parent is tied to this
    exact physical CLK net and a posedge native FF at the same CLM site.
    """
    if groups is None:groups=clock_variant_groups(g,route)
    sources=scope['NativeObjects']['SourceFFs'];require(sources,'clock alias proof has no actual source FF')
    sites={g.g['FFPlacement'][ff]['Site']for ff in sources}
    nets={route['Pins'][parent(ff),'CLK']for ff in sources}
    require(len(sites)==len(nets)==1,'one exact physical source clock required')
    site=next(iter(sites));net=next(iter(nets))
    require(scope['NativeObjects']['SourceCLKNet']==[net],'source CLK net differs from mapped relationship')
    source_clock=g.clock(g.ff[sources[0]]['Ports']['CK'])
    parents={};source_support=[]
    for ff in groups[site,net]:
        c=g.ff[ff];instance=parent(ff);clock=g.clock(c['Ports']['CK'])
        require(canon(c['Ports']['CK'])==net,'functional/native clock net differs in shared CLK proof: '+ff)
        require(clock==source_clock,'shared native CLK alias has different clock root/trace: '+ff)
        cell=route['Cells'][route['Instances'][instance]['Cell']]
        require(cell['Ports'].get('CLK')=='INPUT','shared native CLK selector is not an input: '+instance)
        params={row[1]:row[3]for row in cell['Parameters']}
        require(params.get('CLK_POL')==['STRING','"FALSE"'],
            'shared CLK proof requires actual posedge native clock polarity: '+instance)
        slot=re.search(r'/(FFAPP|FF)([0-3])/FF$',ff)
        require(slot is not None,'shared CLK proof has unknown physical FF slot: '+ff)
        physical=site+('/CR'if slot[1]=='FFAPP'else'/Q')+slot[2]
        support={'FF':ff,'ActualLogicalQ':canon(c['Ports']['Q']),
            'PhysicalQ':physical,'Placement':g.g['FFPlacement'][ff]}
        row=parents.setdefault(instance,{'Instance':instance,'CLKPin':instance+'/CLK',
            'Site':site,'CLKNet':net,'NativeCLKPolarity':params['CLK_POL'],
            'Clock':clock,'FunctionalFFs':[]})
        row['FunctionalFFs'].append(support)
        if ff in sources:source_support.append(support)
    variants=sorted(row['CLKPin']for row in parents.values())
    require(1<=len(variants)<=8 and scope['FromCLK']in variants,
        'shared CLK selector inventory is incomplete or exceeds one physical CLM')
    require(sorted(row['FF']for row in source_support)==sorted(sources),
        'shared CLK proof dropped an original functional launch FF')
    require(sorted({row['PhysicalQ']for row in source_support})==scope['NativeObjects']['SourcePhysicalQ'],
        'shared CLK proof changes the original physical launch slot')
    return variants,{'Verified':True,'PhysicalCLK':site+'/CLK','CLKNet':net,
        'Parents':[parents[p]for p in sorted(parents)],'TimingEvidence':[],
        'SourceFFs':source_support,'LaunchQUnchanged':scope['LaunchQ'],
        'EndpointUnchanged':scope['Endpoint'],'CompanionQLaunchesAdmitted':False,
        'Basis':'All actual packed FF parents on this same CLM site and native CLK net; exact original through-Q and endpoint are retained.'}


def map_scopes(g,rows,mapper):
    mapped=[];data={};resets={};errors=[]
    for i,row in enumerate(rows):
        if not row['ExceptionProposed']:mapped.append(row);continue
        try:
            m=mapper.map(row);s=row['SourceFF'];slot=re.search(r'/(FFAPP|FF)([0-3])/FF$',s);require(slot is not None,'unknown snapshot source FF slot')
            m.update(SourceNativeCLKNet=mapper.route['Pins'][parent(s),'CLK'],SourcePhysicalQ=m['SourcePlacement']['Site']+('/CR'if slot[1]=='FFAPP'else'/Q')+slot[2])
            mapped.append(m);table=resets if row['Role']=='common_epoch_input_reset'else data
            for boundary in m['NativeBoundaries']:
                key=m['SourceNativeClockPin'],m['SourceNativeOutputPin'],boundary['Endpoint']
                scope=table.setdefault(key,{'FromCLK':key[0],'LaunchQ':key[1],'Endpoint':key[2],'Role':row['Role'],'Roles':[],
                    'RelationshipIndexes':[],'NativeObjects':{k:[]for k in ('SourceFFs','DestinationFFs','SourcePhysicalQ','SourceCLKNet')}})
                scope['Roles'].append(row['Role']);scope['RelationshipIndexes'].append(i)
                for k,value in [('SourceFFs',s),('DestinationFFs',row['DestinationFF']),('SourcePhysicalQ',m['SourcePhysicalQ']),('SourceCLKNet',m['SourceNativeCLKNet'])]:scope['NativeObjects'][k].append(value)
                if table is data:
                    period=base.PERIODS[row['DestinationClock']];budget=period*(2 if row['Role'].startswith('held_')else 1)
                    scope['MaximumNS']=min(scope.get('MaximumNS',budget),budget)
                    scope['BoundBasis']='Held bus: two source-toggle synchronizers, detection, then two complete settling states before unconditional capture; at most two destination periods. Scalar first-D: one destination period. Interstage timing remains ordinary.'
                else:scope.update(GuardAccepted=False,GuardProof={'Missing':['native local release/epoch guard acceptance pending']})
        except(ValueError,KeyError)as error:
            mapped.append({**row,'NativeMappingError':str(error)});errors.append({'Code':'NativeMappingIncomplete','RelationshipIndex':i,'Detail':str(error)})
    groups=clock_variant_groups(g,mapper.route)
    for scope in list(data.values())+list(resets.values()):
        scope['NativeObjects']={k:sorted(set(v))for k,v in scope['NativeObjects'].items()};scope['Roles']=sorted(set(scope['Roles']))
        scope['FromCLKVariants'],scope['FromCLKVariantProof']=source_clock_variants(g,mapper.route,scope,groups)
    return mapped,[data[k]for k in sorted(data)],[resets[k]for k in sorted(resets)],errors


def signal_expression(g,logical,aliases):
    for name in aliases.get(logical,[logical]):
        if name in g.canonical_outputs:return g.expression(name)
    # PDS may inline this exact two-input source output into all 256 bank
    # decoders. Recover its registered controls from the already proved local
    # release chain, never by inventing a primary input for the missing wire.
    if logical=='snapshot_we':
        sync_last=resolve_ff(g,'capture/request_sync[1]',aliases)
        candidates={s[3:]for p in ('D','CE','SR')for s in g.support(g.ff[sync_last]['Ports'][p])if s.startswith('ff:')and s[3:]!=sync_last and
            g.clock(g.ff[s[3:]]['Ports']['CK'])['Domain']=='input_pixel'}
        releases=[]
        for n in candidates:
            inactive=int(g.ff[n]['Parameters']['SET_RESET']=='"SET"')
            try:base.release_chain(g,n,inactive);releases.append((n,inactive))
            except(ValueError,KeyError):pass
        require(len(releases)==1,'inlined bank write enable has no unique actual capture release')
        n,inv=releases[0];valid=resolve_ff(g,'capture/wr_valid',aliases)
        vr=int(g.ff[valid]['Parameters']['SET_RESET']=='"SET"')
        bit=lambda name,inverted:('not',('variable','ff:'+name))if inverted else('variable','ff:'+name)
        return and_expression([bit(n,inv),bit(valid,vr)])
    raise ValueError('actual driven signal alias absent: '+logical)


def boolean_equal(a,b,maximum=12):
    if a==b:return True
    variables=sorted(base.boolean.leaves(a)|base.boolean.leaves(b))
    require(len(variables)<=maximum,'bounded native alias truth table exceeded')
    import itertools
    return all(base.boolean.evaluate(a,dict(zip(variables,bits)))==base.boolean.evaluate(b,dict(zip(variables,bits)))
        for bits in itertools.product((0,1),repeat=len(variables)))


def and_expression(values):
    result=('constant',1)
    for value in values:result=('mux',('constant',0),result,value)
    return result


def memory_native_bindings(g,aliases,memory):
    bank_indices=[];proofs=[];issues=[]
    write_enable=signal_expression(g,'snapshot_we',aliases);read_enable=signal_expression(g,'snapshot_re',aliases)
    waddr=[signal_expression(g,f'snapshot_waddr[{i}]',aliases)for i in range(19)]
    raddr=[signal_expression(g,f'snapshot_raddr[{i}]',aliases)for i in range(19)]
    wdata=[signal_expression(g,f'snapshot_wdata[{i}]',aliases)for i in range(8)]
    for row in memory['Memories']:
        if row['Role']!='frozen_snapshot_byte_bank':continue
        name=row['Cell'];p=g.cells[name]['Ports'];m=re.fullmatch(r'snapshot_memory/banks\[(\d+)\]\.memory/.+',name)
        require(m is not None,'native bank index is not explicitly generated from this snapshot RAM')
        index=int(m[1]);bank_indices.append(index)
        checks=[]
        for side,addr in (('A',waddr),('B',raddr)):
            actual=atoms(p['ADDR'+side]);require(len(actual)==14,'native byte RAM address width differs')
            require(all(digital_constant(g,n)==0 for n in actual[-3:]),'byte RAM address lacks three aligned low bits')
            require(all(boolean_equal(g.expression(actual[-4-i]),addr[i])for i in range(11)),
                'actual native RAM byte address mapping differs: '+name+'/'+side)
            selector=[expr if (index>>i)&1 else('not',expr)for i,expr in enumerate(addr[11:19])]
            expected=and_expression([write_enable if side=='A'else read_enable,*selector])
            require(boolean_equal(g.expression(p['WEA'if side=='A'else'CEB']),expected),
                'actual native RAM bank select/enable function differs: '+name+'/'+side)
            checks.append({'Port':side,'ByteAddressUsesADDR13to3':True,'AlignedLowBitsZero':True,
                'BankSelectComparedToExactHighEightAddressBits':True})
        actual_data=atoms(p['DIA']);require(len(actual_data)==18,'native data bus width differs')
        require(all(boolean_equal(g.expression(actual_data[-1-i]),wdata[i])for i in range(8)),
            'native RAM byte data bit order differs: '+name)
        require(digital_constant(g,p['WEB'])==0,'native read port can overwrite snapshot')
        proofs.append({'Cell':name,'LogicalBankIndex':index,'PortChecks':checks,
            'LowEightWriteDataBitsExactlyMatchRegisteredSnapshotByte':True,'PortBWriteConstantZero':True})
    require(sorted(bank_indices)==list(range(256)),'actual snapshot bank set does not exactly cover 2^19 bytes')
    halves=sum(2 if r['Primitive']=='V_DRM36K_E1'else 1 if r['Primitive']=='V_DRM18K_E1'else 0 for r in memory['Memories'])
    require(halves<=310,'actual native block memory exceeds device resources')
    return {'Used18KBlocks':halves,'Available18KBlocks':310,'Used36KBlocks':halves/2,'Available36KBlocks':155,
        'SourceBytes':524288,'NativeByteWidth':8,'WriteClock':'input_pixel','ReadClock':'board27',
        'ReadWritePhasesExclusive':False,'Inventory':memory['Memories'],'NativeByteAddressAndDataBindings':proofs,
        'Missing':[],'Violations':memory['Violations'],'AllNativeModesAndByteConnectionsVerified':not memory['Violations']}


def native_protocol_boundaries(g,rows,sync,aliases,source_release,sampler_release):
    """Exact native FF consumer cut of each declared cross-domain signal."""
    unknown=[r for r in rows if r['Role']=='unclassified']
    require(not unknown,'foreign native consumer has no exact protocol role')
    descriptors=[r for r in rows if r['Role']=='held_descriptor_to_unconditional_local_shadow']
    for r in descriptors:
        require(any(re.fullmatch(r'packetizer/desc_(?:good|id\[\d+\]|crc\[\d+\]|native_pixels\[\d+\]|stored_bytes\[\d+\]|fault\[\d+\])',n)
            for n in identities(g,r['DestinationFF'],aliases)),'descriptor bypasses first local shadow')
    # A direct pad is never a substitute for a registered native source.
    require(all(g.clock(g.ff[r['SourceFF']]['Ports']['CK'])['Domain']=='input_pixel'for r in descriptors),
        'descriptor source is not the source PCLK domain')
    request_chain=next(r for r in sync if r['Family']=='capture/request_sync')
    done_chain=next(r for r in sync if r['Family']=='packetizer/done_sync')
    boot_chain=next(r for r in sync if r['Family']=='packetizer/boot_sync')
    cap_reset=base.release_chain(g,*source_release)
    common=base.boolean.leaves(g.expression(g.ff[source_release[0]]['Ports']['SR']))
    require('primary:reset_n'in common,'source release is not tied to coordinated external reset')
    return {'DescriptorOnlyFeedsExactNativeShadowFFs':True,'DescriptorNativeRelationshipCount':len(descriptors),
        'RequestChain':request_chain,'DoneChain':done_chain,'BootChain':boot_chain,
        'ActualCaptureLocalRelease':cap_reset,'CaptureLocalReleaseWasRecoveredFromActualSyncDCEAndSR':True,
        'SamplerLocalReleaseFF':sampler_release[0],'AllCrossingsClassifiedByActualFunctionalQAndLiteralAliases':True,
        'NoPrimitiveOrClockFallbackToPrimary':True,'NativeFFConsumersVerified':True}


def derive(build_plan,export_receipt,route_receipt):
    build_plan=Path(build_plan).resolve();export_receipt=Path(export_receipt).resolve();route_receipt=Path(route_receipt).resolve()
    watched={}
    for p in base.static_helpers(SELF):native.add(watched,p)
    native.add(watched,base.PYTHON);initial=dict(watched);build.validate(build_plan)
    exported,inputs=native.bind_receipt(export_receipt);native.merge(watched,inputs)
    routed,inputs=native.bind_receipt(route_receipt);native.merge(watched,inputs)
    require(exported['Mode']=='export'and routed['Mode']in ('report','query')and
        all(exported[k]==routed[k]for k in ('BuildPlanSHA256','SourceADFSHA256','SourceADF'))and
        exported['BuildPlanSHA256']==sha(build_plan),'snapshot export/route belongs to another source ADF')
    refs={'BuildPlan':native.ref(build_plan),'ExportReceipt':native.ref(export_receipt),'RouteReceipt':native.ref(route_receipt),
        'SourceADF':native.ref(exported['SourceADF']),
        'NativeNetlist':native.ref(native.artifact(export_receipt,exported,TARGET+'_sim.v')),
        'RouteDump':native.ref(native.artifact(route_receipt,routed,'route-dump.txt'))}
    g,route,mapper,inputs=native_graph(refs);native.merge(watched,inputs)
    for kind in sorted({c['Primitive']for c in g.cells.values()}):native.add(watched,base.MODEL_ROOT/(kind+'.v'),MODELS[kind])
    aliases,alias_proofs=literal_aliases(g,build_plan.parent,watched)
    pins=port_inventory(g,build_plan.parent,watched);sampling,sampler_release=base.sampler_inventory(g)
    input_release=(resolve_ff(g,'input_reset[1]',aliases),0);ref_release=(resolve_ff(g,'ref_reset[1]',aliases),0)
    sync=synchronizers(g,aliases,input_release,ref_release)
    request=next(r for r in sync if r['Family']=='capture/request_sync')
    source_release=(request['LocalReleaseFF'],request['LocalReleaseInactivePhysicalQ'])
    ready=next(r for r in sync if r['Family']=='ready_pix')
    output=base.output_review(g,sampling,ready['Second'],input_release,sampler_release)
    rows,other,clock_counts,blockers=foreign_inventory(g,aliases,sync,source_release,resolve_ff(g,'ref_ready',aliases),resolve_ff(g,'power_ready',aliases))
    mapped,data,resets,mapping_errors=map_scopes(g,rows,mapper);blockers+=mapping_errors
    memories=memory_inventory(g);memory=memory_native_bindings(g,aliases,memories)
    require(not memory['Violations'],'native snapshot memory mode/domain violations')
    boundaries=native_protocol_boundaries(g,rows,sync,aliases,source_release,sampler_release)
    provider=importlib.import_module('hdmi_camera_snapshot_protocol')
    require(Path(provider.__file__).resolve()==SELF.with_name('hdmi_camera_snapshot_protocol.py'),'protocol provider location differs')
    source,inputs=provider.source_review(build_plan);native.merge(watched,inputs);native.add(watched,provider.__file__)
    require(source['SourceProtocolReviewPassed']is True,'source protocol review did not pass')
    release_pairs={}
    for last,inactive in (sampler_release,input_release,ref_release,source_release,
        (resolve_ff(g,'packetizer/r_reset[1]',aliases),0)):
        proof=base.release_chain(g,last,inactive);release_pairs[proof['First'],proof['Second']]=proof
    key=base.release_chain(g,resolve_ff(g,'key_reset_sync[1]',aliases),0)
    reset_value=None
    reset_module=SELF.with_name('hdmi_camera_snapshot_reset_review.py')
    if reset_module.is_file():
        reset_provider=importlib.import_module('hdmi_camera_snapshot_reset_review')
        require(Path(reset_provider.__file__).resolve()==reset_module,'reset provider location differs')
        reset_value,inputs=reset_provider.native_reset_review(build_plan,export_receipt)
        native.merge(watched,inputs);native.add(watched,reset_module)
        if reset_value.get('Passed')is not True:blockers.append({'Code':'NativeResetReviewIncomplete','Detail':reset_value.get('Violations')})
    else:blockers.append({'Code':'NativeResetReviewPending'})
    if reset_value and reset_value.get('Passed')is True:
        for scope in resets:
            proofs={n:reset_value['GuardProofByFF'][n]for n in scope['NativeObjects']['DestinationFFs']}
            scope.update(GuardAccepted=True,GuardProof={'Destinations':proofs,'NativeResetReviewPassed':True})
    ownership={**source['SnapshotOwnership'],'SourceOnly':False,
        'NativeFFConsumersVerified':boundaries['NativeFFConsumersVerified'],
        'NativeMemoryModesVerified':memory['AllNativeModesAndByteConnectionsVerified'],
        'NativeEvidence':boundaries,'SourceReview':source['SnapshotOwnership']}
    epoch={**source['SnapshotEpoch'],'SourceOnly':False,'NativeFFConsumersVerified':boundaries['NativeFFConsumersVerified'],
        'NativeMemoryModesVerified':memory['AllNativeModesAndByteConnectionsVerified'],
        'SourceReview':source['SnapshotEpoch'],'NativeResetReview':reset_value}
    reset_passed=bool(reset_value and reset_value.get('Passed')is True)
    ownership['Passed']=ownership.get('Passed')is True and not blockers
    epoch['Passed']=epoch.get('Passed')is True and reset_passed and not blockers
    memory['ReadWritePhasesExclusive']=ownership['Passed']
    for p,h in initial.items():require(sha(p)==h,'snapshot audit helper changed during derivation: '+str(p))
    return {'Schema':SCHEMA,'Target':TARGET,**refs,'Pins':pins,'ActualCells':len(g.cells),'ActualFFs':len(g.ff),
        'PrimitiveCounts':dict(Counter(c['Primitive']for c in g.cells.values())),
        'ClockDefinitions':{'PeriodsNS':base.PERIODS,'ConfigurationPLL':base.pll_review(g)},
        'ClockTopology':{'FFCountsByClock':clock_counts},'SourceSampling':sampling,
        'OutputPathReview':output,'LogicalAliasRecovery':alias_proofs,'Synchronizers':sync,
        'ReleaseChains':list(release_pairs.values()),'LocalResetGuards':{'KeyReleaseChain':key,
            'Verified':reset_passed,'ResetScopeVerified':reset_passed,'NativeReview':reset_value},
        'ForeignRelationships':mapped,'NonFFSequentialSupport':other,'DataScopes':data,'ResetScopes':resets,
        'Memory':memory,'SnapshotOwnership':ownership,'SnapshotEpoch':epoch,'SourceProtocol':source,
        'NativeAcceptance':{'ResetAccepted':reset_passed,'ProtocolSafetyAccepted':ownership['Passed']and epoch['Passed'],
            'SourceSamplingIsolatedVerified':sampling['SourceSamplingIsolatedVerified'],
            'RAMModesAccepted':memory['AllNativeModesAndByteConnectionsVerified'],'SnapshotOwnershipAccepted':ownership['Passed'],
            'SnapshotEpochAccepted':epoch['Passed'],'Missing':blockers,'Violations':[]},
        'Blockers':blockers,'ProposalReady':not blockers,'ConstraintsApplied':False,'TimingAccepted':False,
        'ExternalACAccepted':False,'HardwareReleaseAllowed':False,'HardwareAccessed':False,'BitstreamRequested':False,
        'InputSHA256':{str(p):h for p,h in sorted(watched.items(),key=lambda x:str(x[0]))},
        'Limits':'Current snapshot candidate only. Exact registered sampling, typed byte-bank connectivity and source/native protocol/reset guards. '
            'All ordinary/interstage/native IO and final unchanged-graph all-ten-table timing still required. No external AC or optical calibration acceptance.'},watched


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('build-plan','export-receipt','route-receipt','output-dir'):p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args(argv);out=build.work_path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    value,_=derive(args.build_plan,args.export_receipt,args.route_receipt);write(out/'scope.json',value)
    print(json.dumps({'ProposalReady':value['ProposalReady'],'DataScopes':len(value['DataScopes']),
        'ResetScopes':len(value['ResetScopes']),'Blockers':value['Blockers'],'Scope':str(out/'scope.json')}));return 0


if __name__=='__main__':raise SystemExit(main())
