"""Current native RAM shared-WE timing aliases; no constraints or hardware.

The caller first binds the complete audit. Each functional RAM endpoint and
its complete support matrix remain separate obligations. This provider only
proves which additional *observed STA* names refer to that same physical WE.
It does not merge roles/budgets or invent a functional RAM for a reserved BLE.
"""
import ast
from collections import defaultdict
import json
from pathlib import Path
import re
import tempfile

import hdmi_camera_fisheye_tile8df8_native as native
import hdmi_camera_pixel_audit as typed

build=native.build
SELF=Path(__file__).resolve()
SCHEMA='hdmi-camera-fisheye-tile8df8-macro-we-aliases-v1'
require=build.require
canon=typed.canon
CHILD_SHA='eea8354dee48000fce0ef171120b2b0dd04ef5901cefe0198da050aa8ad07842'


def helper_closure():
    pending=[SELF];seen=set()
    while pending:
        path=pending.pop()
        if path in seen:continue
        seen.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            names=[]
            if isinstance(node,ast.Import):names=[v.name for v in node.names]
            elif isinstance(node,ast.ImportFrom)and node.module:names=[node.module]
            for name in names:
                child=SELF.parent/(name.split('.')[0]+'.py')
                if child.is_file()and child not in seen:pending.append(child)
    return sorted(seen)


def native_ram_placements(path):
    """Select by actual CELLREF type, place by actual INSTANNOTATE evidence."""
    wanted=set();placements={};pending=None
    with Path(path).open(encoding='utf-8-sig')as stream:
        for number,line in enumerate(stream,1):
            match=re.search(r'\(INSTANCE\s+(\S+)\s+\(VIEWREF\s+OPER\s+\(CELLREF\s+\S+\s+\(OPERAREF\s+gopRAM32X2S\s',line)
            if match:wanted.add(canon(match[1]))
            match=re.search(r'\(INSTANNOTATE\s+\(INSTREF\s+(\S+)\s*\)',line)
            if match:pending=canon(match[1]);continue
            if pending:
                match=re.search(r'\(PLACE\s+(\S+)\s+\(DEVINSTREF\s+(\S+)\s+\(SITEREF\s+(\d+)\s+(\d+)\)',line)
                if match:
                    require(pending not in placements,'native instance is placed twice')
                    placements[pending]={'Implementation':match[1],'Site':match[2]+'_'+match[3]+'_'+match[4],
                        'LocationLine':number};pending=None
    require(wanted and wanted<=set(placements),'native RAM placement inventory incomplete')
    return wanted,{p:placements[p]for p in sorted(wanted)}


def timing_we_endpoints(path):
    rows={};endpoint=None;head=None;typ=None;domain=None;designs=[]
    with Path(path).open(encoding='gb18030',errors='strict')as stream:
        for number,line in enumerate(stream,1):
            match=re.fullmatch(r'\| Design\s*:\s*(\S+)\s*',line)
            if match:designs.append(match[1]);continue
            match=re.match(r'^Endpoint\s*:\s*(\S+)\s*$',line)
            if match:endpoint=match[1];head=number;typ=None;domain=None;continue
            match=re.match(r'^Path Type\s*:\s*(.+?)\s*$',line)
            if match:typ=match[1];continue
            match=re.match(r'^Path Group\s*:\s*(\S+)\s*$',line)
            if match:domain=match[1];continue
            if endpoint is None or not endpoint.endswith('/WE'):continue
            match=re.match(r'^\s*(CLM[A-Z]*_\d+_\d+)/WE\s+[rf]\s+(\S+)\s*$',line)
            if not match or match[2]!=endpoint:continue
            row=rows.setdefault(match[1],{}).setdefault(endpoint,{'Endpoint':endpoint,
                'PhysicalTimingPin':match[1]+'/WE','Contexts':{}})
            row['Contexts'].setdefault(typ,{'HeaderLine':head,'PhysicalLine':number,'PathType':typ,
                'DestinationClockDomain':domain})
    require(designs==[build.TARGET],'RAM timing endpoint evidence targets another actual design')
    return rows


def prove_site(site,consumers,route,placements,timing,endpoint_support):
    """Pure finite proof; no parent-prefix, same-clock-only or first-wins alias."""
    parents=sorted(p for p in route['Instances']if placements[p]['Site']==site)
    require(parents and consumers,'shared RAM WE has no actual native/functional inventory')
    clk={route['Pins'].get((p,'CLK'))for p in parents};we={route['Pins'].get((p,'WE'))for p in parents}
    require(None not in clk|we and len(clk)==len(we)==1,'native RAM alias has another actual WE/WCLK net')
    params={}
    for p in parents:
        cell=route['Cells'][route['Instances'][p]['Cell']]
        require(cell['Operator']=='gopRAM32X2S'and cell['Ports'].get('WE')=='INPUT'and cell['Ports'].get('CLK')=='INPUT',
            'shared RAM WE owner primitive/interface differs')
        params[p]={r[1]:r[3]for r in cell['Parameters']}
        require(params[p].get('CP_IMPL_LOC')in (['STRING','"NA"'],['STRING','"D"']),
            'unreviewed RAM control implementation placement mode')
    reduced=[{k:v for k,v in params[p].items()if k!='CP_IMPL_LOC'}for p in parents]
    require(all(row==reduced[0]for row in reduced),'RAM alias native modes/INIT/write-clock polarity differ')
    required={'MODE':['STRING','"RAM"'],'CLK_POL':['STRING','"FALSE"'],
        'WCK_SEL':['STRING','"LOCAL"'],'RAM_MODE':['STRING','"LRAM"'],'RAM32_EN':['STRING','"TRUE"']}
    require(all(reduced[0].get(k)==v for k,v in required.items()),'unreviewed native RAM mode/clock selection')
    rows=[];supports=[];cuts=[];clock_bindings=[];polarities=[];functional=set()
    for row in sorted(consumers,key=lambda r:r['Cell']):
        p=row['Cell'].rsplit('/',2)[0];endpoint=p+'/WE';functional.add(p)
        require(p in parents and row['Primitive']=='V_RAM32X2','functional RAM is not in the actual same-site native inventory')
        connection=row['NativeWEConnection']
        require(connection['NativeWE']==next(iter(we))and connection['NativeInstance']==route['Instances'][p],
            'functional RAM WE does not bind native alias common net/instance')
        support=endpoint_support[endpoint]
        require(support['SourceSupportComplete']is True and support['AllActualSourceFFsRetained']is True,
            'shared WE alias requires complete original functional FF support')
        supports.append(set(support['SourceFFs']));cuts.append(set(support.get('TypedBoundaryCuts',[])))
        clocks=[c for c in row['ClockBindings']if c['Pin']=='WCLK']
        require(len(clocks)==1,'functional RAM WCLK is ambiguous')
        functional_clock_net=clocks[0]['Trace'][0]['Net']if clocks[0].get('Trace')else clocks[0]['Root']
        require(functional_clock_net==next(iter(clk)),
            'native RAM clock net does not bind the actual functional WCLK trace')
        clock_bindings.append({k:clocks[0][k]for k in ('Domain','Root','PeriodNS','Master')})
        polarities.append((connection['NativeActiveWriteValue'],connection['NativeInactiveValue']))
        rows.append({'Cell':row['Cell'],'NativeParent':p,'Endpoint':endpoint,'NativeWEConnection':connection,
            'WCLK':clocks[0],'CompleteSourceFFs':support['SourceFFs'],
            'ActualFunctionalWCLKNet':functional_clock_net,'NativeFunctionalWCLKNetIdentical':True,
            'TypedBoundaryCuts':support.get('TypedBoundaryCuts',[]),'OriginalNativeEndpointSupport':endpoint})
    require(all(v==supports[0]for v in supports),'shared RAM WE functional consumers have different complete FF support')
    require(all(v==cuts[0]for v in cuts),'shared RAM WE functional consumers have different typed boundary cuts')
    require(all(v==clock_bindings[0]for v in clock_bindings),'shared RAM WE functional consumers use another clock root')
    require(len(set(polarities))==1 and set(polarities[0])=={0,1},'shared RAM WE functional/native active polarity differs')
    aliases=[]
    for endpoint,evidence in sorted(timing.get(site,{}).items()):
        p=endpoint.rsplit('/',1)[0]
        require(p in parents and evidence['PhysicalTimingPin']==site+'/WE',
            'reported RAM WE alias is outside the actual physical site')
        require(evidence['Contexts']and all(v['DestinationClockDomain']==clock_bindings[0]['Domain']
            for v in evidence['Contexts'].values()),'reported RAM WE timing clock differs from actual functional WCLK')
        ports={pin:net for(nn,pin),net in route['Pins'].items()if nn==p};native_only=p not in functional
        if native_only:
            require(not any(k in ports for k in ('DOH','DOL','DIH','DIL')),
                'native-only RAM control alias has data consumers/inputs outside the functional inventory')
        aliases.append({'Endpoint':endpoint,'NativeParent':p,'Placement':placements[p],
            'NativeInstance':route['Instances'][p],'NativeParameters':params[p],'NativePins':ports,
            'NativeOnlyImplementationAlias':native_only,'FunctionalRAMInvented':False,
            'NativeOnlyHasNoDataInputsOrOutputs':native_only,
            'ActualTimingEvidence':evidence})
    require(aliases,'shared RAM WE has no actual baseline timing endpoint evidence')
    equivalents=sorted(row['Endpoint']for row in rows)
    return {'Passed':True,'PhysicalTimingPin':site+'/WE','NativeCLKNet':next(iter(clk)),
        'NativeWENet':next(iter(we)),'NativeActiveWriteValue':polarities[0][0],
        'NativeInactiveWriteValue':polarities[0][1],'FunctionalConsumers':rows,
        'EquivalentFunctionalEndpoints':equivalents,'EquivalentCanonicalEndpoints':equivalents,
        'AllNativeSameSiteRAMParents':parents,'NativeTimingAliases':[r['Endpoint']for r in aliases],
        'NativeTimingAliasEvidence':aliases,'CompleteFunctionalSupportIdentical':True,
        'NativeModeClockAndPolarityIdentical':True,'AllOriginalFunctionalEndpointMatrixObligationsRetained':True,
        'RoleBudgetAndDomainEquivalenceStillRequiredForMatrixCanonicalization':True,
        'NoHierarchyPrefixUsedToInventAlias':True,'EncryptedNativeOperatorDecoded':False}


def selected_functional_endpoints(scope):
    """Include both held-data WE paths and separately guarded reset WE paths."""
    data={row['Endpoint']for row in scope['DataScopes']if row.get('TargetKind')=='MacroFunctionalInput'}
    reset={row['Endpoint']for row in scope.get('UserSynchronousResetScopes',[])
        if row.get('TargetKind')=='MacroWriteEnableResetFunction'}
    require(all(name.endswith('/WE')for name in data|reset),'macro alias scope includes another native function')
    return data|reset


def review(scope):
    require(scope.get('Target')==build.TARGET and scope.get('ProposalReady')is True,
        'complete current fisheye audit required before RAM alias review')
    watched={}
    for path in helper_closure():native.add(watched,path)
    native.add(watched,'D:/anaconda3/python.exe')
    for key in ('NativeNetlist','RouteDump','BaselineTimingReport'):
        native.add(watched,scope[key]['Path'],scope[key]['SHA256'])
    native.add(watched,typed.MODEL_ROOT/'V_RAM32X2.v',typed.MODEL_SHA['V_RAM32X2'])
    native.add(watched,typed.MODEL_ROOT/'V_RAM32X1.v',CHILD_SHA)
    wanted,placements=native_ram_placements(scope['RouteDump']['Path'])
    with tempfile.TemporaryDirectory(prefix='bound-ram-we-alias-')as temporary:
        path=Path(temporary)/'route.adif'
        typed.calibrated.normalize_source_locations(scope['RouteDump']['Path'],path)
        route=typed.native_route(path,wanted)
    timing=timing_we_endpoints(scope['BaselineTimingReport']['Path'])
    selected=selected_functional_endpoints(scope)
    sites={placements[row['Cell'].rsplit('/',2)[0]]['Site']for row in scope['PrimitiveBoundaries']
        if row['Primitive']=='V_RAM32X2'and row['Cell'].rsplit('/',2)[0]+'/WE'in selected}
    grouped=defaultdict(list)
    for row in scope['PrimitiveBoundaries']:
        if row['Primitive']!='V_RAM32X2':continue
        p=row['Cell'].rsplit('/',2)[0]
        if p in placements and placements[p]['Site']in sites:grouped[placements[p]['Site']].append(row)
    proofs={};missing=[]
    for site,consumers in sorted(grouped.items()):
        try:proofs[site+'/WE']=prove_site(site,consumers,route,placements,timing,scope['NativeEndpointSupport'])
        except(ValueError,KeyError)as e:missing.append({'Site':site,'Detail':str(e)})
    covered={end for proof in proofs.values()for end in proof['EquivalentFunctionalEndpoints']}
    if selected-covered:missing.append({'Detail':'selected macro WE scopes lack a complete actual native alias model',
        'Endpoints':sorted(selected-covered)})
    value={'Schema':SCHEMA,'Target':build.TARGET,'Passed':not missing,'ByPhysicalPin':proofs,
        'ActualNativeRAMInstanceCount':len(wanted),'Missing':missing,'Violations':[],
        'BaselineTimingReport':scope['BaselineTimingReport'],'RouteDump':scope['RouteDump'],
        'NativeNetlist':scope['NativeNetlist'],'ExistingRoleBudgetAndSourceMatrixNotModified':True,
        'ConstraintsApplied':False,'TimingAccepted':False,'HardwareReleaseAllowed':False}
    require(all(build.sha(path)==h for path,h in watched.items()),'RAM WE alias evidence input drift')
    value['InputSHA256']={str(p):h for p,h in sorted(watched.items(),key=lambda x:str(x[0]))}
    return json.loads(json.dumps(value)),watched
