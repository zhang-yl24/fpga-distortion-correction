"""Independent reset/ACK-guard review of the actual raw HDMI native candidate.

Derives only unapplied exact source-CLK to local release-chain async RS pairs.
All business data pins and other async-reset consumers remain timed. No EDA,
timing exceptions, hardware or old candidate endpoint inventory is executed.
"""
import argparse
from collections import defaultdict
import itertools
import json
from pathlib import Path
import re

import hdmi_camera_raw_audit as physical
import hdmi_camera_raw_native as native
import hdmi_camera_raw_build as build
import camera720_stats_native_mux as boolean

SELF=Path(__file__).resolve()
SCHEMA='hdmi-camera-raw-reset-review-v1'
TARGET,require,sha,read,write=build.TARGET,build.require,build.sha,build.read,build.write
canon,parent=physical.canon,physical.parent
SAMPLER_FF_MODEL=Path('D:/pango/PDS_2023.2/arch/vendor/pango/verilog/bsim/V_FFSYN.v')
SAMPLER_FF_MODEL_SHA='ae4094a9a478a8ae9e5c67a0fcf982ff1e61a6e1e66588d849dd815d713c1f8c'


def ref(path):return native.ref(path)


def expression(g,net,active=()):
    require(net not in active,'reset Boolean cycle')
    if net in ("1'b0","1'b1"):return ('constant',int(net[-1]))
    ds=g.outputs.get(net,[])
    if not ds:return ('variable','primary:'+canon(net))
    require(len(ds)==1,'ambiguous reset/guard driver')
    name,pin=ds[0];c=g.cells[name];p=c['Ports'];kind=c['Primitive']
    if name in g.ff:return ('variable','ff:'+name)
    if kind=='V_GPLL' and pin=='LOCK':return ('variable','pll_lock:'+name)
    child=lambda n:expression(g,n,active+(net,))
    if kind in ('V_BUF','V_IBUF','V_INBUFG'):return child(p['I'])
    if kind=='V_INV':return ('not',child(p['I']))
    if kind=='V_MUX2':return ('mux',child(p['I0']),child(p['I1']),child(p['SEL']))
    require(kind=='V_LUT6CARRY' and pin in ('Z','Z5'),'unreviewed reset Boolean primitive '+kind+'/'+pin)
    match=re.fullmatch(r"64'h([0-9a-fA-F_]+)",c['Parameters']['INIT'])
    require(match is not None,'unsupported reset LUT initializer')
    pins=[p['I'+str(i)] for i in range(5)]
    if pin=='Z':pins.append(p['I5'] if c['Parameters'].get('I5_TO_LUT')=='"TRUE"' else p['CIN'])
    return ('lut',int(match[1].replace('_',''),16),tuple(child(n) for n in pins))


def leaves(value):
    if value[0]=='constant':return set()
    if value[0]=='variable':return {value[1]}
    if value[0]=='not':return leaves(value[1])
    if value[0]=='mux':return set.union(set(),*(leaves(n) for n in value[1:]))
    return set.union(set(),*(leaves(n) for n in value[2]))


def evaluate(value,assignments):
    if value[0]=='constant':return value[1]
    if value[0]=='variable':return assignments[value[1]]
    if value[0]=='not':return 1-evaluate(value[1],assignments)
    if value[0]=='mux':return evaluate(value[1+evaluate(value[3],assignments)],assignments)
    return (value[1]>>sum(evaluate(n,assignments)<<i for i,n in enumerate(value[2])))&1


def one_ff(g,prefix):
    values=[n for n in g.ff if n.startswith(prefix)]
    require(len(values)==1,'ambiguous current FF '+prefix+': '+str(values))
    return values[0]


def actual_chains(g):
    # Native packing can retain only the [1] parent for both registers. Start
    # with the exact logical second Q and follow its actual D driver instead
    # of inferring that a source [0] prefix must survive synthesis.
    families=('ref_reset','pattern_reset','telemetry/ref_reset','telemetry/cfg_reset',
        'raw_activity/p_reset','raw_activity/r_reset','raw_activity/request_sync','raw_activity/ack_sync')
    rows=[]
    for family in families:
        second=g.by_q(family+'[1]');driver,pin=g.driver(g.ff[second]['Ports']['D'])
        require(driver in g.ff and pin=='Q','current second stage is not driven by one native FF')
        rows.append({'Family':family,**g.chain(driver,second,family+' actual D/Q chain')})
    return rows


def source_sampling_review(g,local_release):
    """Find pad sampling by actual Boolean fanout, never by register names.

    Each raw input may reach exactly one sequential D, and no other D/CE/SR
    cone. That FF must sample this pad every released PCLK and clear its
    logical level synchronously through the already-proved local release FF.
    Native complemented register encoding is accepted only by its truth table.
    """
    pads=('vs_in','hs_in','de_in');cache={};direct={pad:[] for pad in pads}
    scanned=0;cones={}
    for name,c in sorted(g.ff.items()):
        for pin in ('D','CE','SR'):
            if pin not in c['Ports']:continue
            scanned+=1;support=physical.support(g,c['Ports'][pin],cache);cones[name,pin]=support
            for pad in pads:
                if ('primary',pad) in support:
                    direct[pad].append({'FF':name,'Pin':pin})
    rows=[]
    for pad in pads:
        targets=direct[pad];names={r['FF'] for r in targets}
        require(len(names)==1 and {r['Pin'] for r in targets}=={'D'},
                'raw primary pad bypasses a single D-only sampler: '+pad+': '+str(targets))
        name=next(iter(names));c=g.ff[name];p=c['Ports']
        require(c['Primitive']=='V_FFSYN' and g.clock(p['CK'])['Domain']=='input_pixel',
                'raw pad sampler must be a synchronous-reset PCLK FF: '+pad)
        require(c['Parameters'].get('SET_RESET') in ('"RESET"','"SET"')
                and c['Parameters'].get('LRS_EN') in ('"TRUE"','"FALSE"'),
                'unreviewed raw sampler reset primitive parameters')
        expressions={pin:expression(g,p.get(pin,default)) for pin,default in
                     (('D',"1'b0"),('CE',"1'b1"),('SR',"1'b0"))}
        variables=set.union(set(),*(leaves(v) for v in expressions.values()))
        wanted={'primary:'+pad,'ff:'+local_release};allowed=wanted|{'ff:'+name}
        require(wanted<=variables and variables<=allowed,
                'raw pad sampler has missing local release or extra state/control: '+pad)
        # Include current Q even if absent from the cone, so a hidden CE hold
        # cannot masquerade as an always-sampling register.
        variables=sorted(variables|{'ff:'+name});truth=[];encodings=[]
        for bits in itertools.product((0,1),repeat=len(variables)):
            assignments=dict(zip(variables,bits))
            d,ce,sr=(evaluate(expressions[pin],assignments) for pin in ('D','CE','SR'))
            if c['Parameters']['LRS_EN']=='"TRUE"' and sr:
                nxt=int(c['Parameters']['SET_RESET']=='"SET"')
            else:nxt=d if ce else assignments['ff:'+name]
            truth.append({'Inputs':assignments,'NextQ':nxt})
        for inverted in (0,1):
            if all(row['NextQ']==((row['Inputs']['primary:'+pad] if row['Inputs']['ff:'+local_release] else 0)^inverted)
                   for row in truth):encodings.append(inverted)
        require(len(encodings)==1,'raw sampler does not unconditionally sample this pad after local synchronous release: '+pad)
        consumers=[]
        for (destination,pin),support in sorted(cones.items()):
            if destination==name or ('ff',name) not in support:continue
            target=g.ff[destination]
            require(g.clock(target['Ports']['CK'])['Domain']=='input_pixel',
                    'raw sampled Q reaches a foreign clock before the held snapshot protocol: '+pad)
            consumers.append({'DestinationFF':destination,'DestinationPin':pin,'DestinationClock':'input_pixel'})
        require(consumers,'raw pad sampler has no registered sampled-sequence consumers: '+pad)
        rows.append({'Pad':pad,'SamplerFF':name,'SamplerLogicalQ':canon(p['Q']),
            'SamplerClock':'input_pixel','LocalResetReleaseFF':local_release,
            'DirectPrimaryConsumers':targets,'Expressions':expressions,'TruthTable':truth,
            'NativeQInvertsSample':bool(encodings[0]),'LogicalResetSample':0,
            'SamplerQFirstRegisteredConsumers':consumers,'FirstRegisteredConsumersUseSamePCLK':True,
            'OnlyThisPadAndLocalReleaseAffectNextQ':True,'EveryReleasedPCLKCapturesPad':True,
            'LocalSynchronousResetVerified':True})
    require(len({r['SamplerFF'] for r in rows})==3,'raw VS/HS/DE require three independent common samplers')
    return {'SourceSamplingIsolatedVerified':True,'SourceSampling':{
        'Pads':rows,'AuditedFFCount':len(g.ff),'AuditedDCEAndSRCones':scanned,
        'DirectPrimaryConsumers':direct,'NonSamplerDirectPrimaryConsumers':[],
        'AllRawPrimaryFanoutEndsAtOneSamplerPerPad':True,
        'AllOtherFFDataEnableResetConesHaveNoDirectRawPrimarySupport':True,
        'AllSamplersUseLocalSynchronousReset':True,
        'AllSamplerQFirstRegisteredConsumersUseSamePCLK':True,
        'RegisterNamesUsedToIdentifySamplers':False,
        'ExternalACAccepted':False,'AnalogMetastabilityAccepted':False,
        'Limits':'This proves a single registered sampled sequence per pad in the native graph. External source timing/AC, analog metastability and real input video remain separate.'}}


def raw_graph_review(g,sync):
    chains={r['Family']:r for r in sync}
    require({'raw_activity/'+n for n in ('p_reset','r_reset','request_sync','ack_sync')}<=set(chains),
            'all current raw synchronization families required')
    reset_ff=set();release={}
    reset_graph=[]
    for family,clock in (('p_reset','input_pixel'),('r_reset','board27')):
        chain=chains['raw_activity/'+family]
        require(chain['DestinationClock']==clock and chain['InterstageLogic'] is None
                and chain['ClockRootsIdentical'] and chain['ClearFunctionsEquivalent']
                and chain['FirstStageOnlyFeedsSecondStage'],'raw reset release chain differs')
        for name in (chain['First'],chain['Second']):
            c=g.ff[name]
            require(c['Primitive']=='V_FFASYN','raw reset release must assert asynchronously')
            require(c['Parameters'].get('SET_RESET')=='"RESET"' and c['Parameters'].get('INIT')=="1'b0",
                    'raw reset synchronizer clear value differs')
            reset_ff.add(name)
        require(g.constant_one(g.ff[chain['First']]['Ports']['D']), 'raw reset first stage must shift constant one')
        release[clock]=chain['Second']
        reset_graph.append({'Family':chain['Family'],'First':chain['First'],'Second':chain['Second'],
            'AsyncClearExpression':expression(g,g.ff[chain['First']]['Ports']['SR']),
            'FirstOnlyFeedsSecond':True,'AsyncAssertionSynchronousRelease':True})
    business=[];cache={}
    for name,c in sorted(g.ff.items()):
        if not name.startswith('raw_activity/') or name in reset_ff:continue
        domain=g.clock(c['Ports']['CK'])['Domain'];require(domain in release,'raw business clock differs')
        require(c['Primitive']=='V_FFSYN','raw business register unexpectedly has asynchronous clear: '+name)
        support=set.union(set(),*(physical.support(g,c['Ports'][p],cache) for p in ('D','CE','SR') if p in c['Ports']))
        require(('ff',release[domain]) in support,'raw business register lacks local reset release: '+name)
        require(('primary','reset_n') not in support,'raw business reset bypasses local release: '+name)
        business.append({'FF':name,'Clock':domain,'LocalResetReleaseFF':release[domain]})
    require(business,'no current raw business registers')
    ack_chain=chains['raw_activity/ack_sync'];first=ack_chain['First']
    ack=one_ff(g,'raw_activity/snapshot_ack/')
    guard=expression(g,g.ff[first]['Ports']['D']);guard_leaves=leaves(guard)
    wanted={'ff:'+ack,'ff:'+release['input_pixel']}
    optional={'ff:'+release['board27']}
    require(wanted<=guard_leaves and guard_leaves<=wanted|optional,'ACK guard has missing/extra launch sources')
    assignments=[]
    for bits in itertools.product((0,1),repeat=len(guard_leaves)):
        values=dict(zip(sorted(guard_leaves),bits));actual=evaluate(guard,values)
        expected=values['ff:'+ack]&values['ff:'+release['input_pixel']]
        if optional & guard_leaves:expected &= values['ff:'+release['board27']]
        require(actual==expected,'ACK first-stage D is not source ACK AND source valid reset guard')
        assignments.append({'Inputs':values,'Output':actual})
    incoming=[]
    for destination,c in sorted(g.ff.items()):
        dc=g.clock(c['Ports']['CK'])['Domain']
        if dc!='board27':continue
        for pin in ('D','CE','SR'):
            if pin not in c['Ports']:continue
            for kind,source in sorted(physical.support(g,c['Ports'][pin],cache)):
                if kind!='ff' or source not in (ack,release['input_pixel']):continue
                require(destination==first and pin=='D','source ACK/reset guard bypasses ref first D')
                incoming.append({'SourceFF':source,'DestinationFF':destination,'DestinationPin':pin,
                                 'SourceClock':'input_pixel','DestinationClock':'board27'})
    require({r['SourceFF'] for r in incoming}=={ack,release['input_pixel']},
            'ACK guard two foreign launches not completely represented')
    sampling=source_sampling_review(g,release['input_pixel'])
    return {'LocalResetChains':reset_graph,'RawAsyncResetFFs':sorted(reset_ff),**sampling,
        'RawBusinessRegisters':business,'RawBusinessLocalSynchronousResetVerified':True,
        'ACKGuard':{'FirstRefFF':first,'SourceACKFF':ack,'SourceResetReleaseFF':release['input_pixel'],
            'OptionalRefReleaseFF':release['board27'],'Expression':guard,'TruthTable':assignments,
            'ForeignSources':incoming,'BothSourceLaunchesRetained':True,'NoFirstStageBypass':True,
            'OldACKMaskedWhilePCLKStoppedAndCommonResetAsserted':True},
        'RawResetEpochGuardVerified':True}


def failing_reset_paths(report):
    rows=[];block=[];line_number=0;first=0
    for line_number,line in enumerate(Path(report).open(encoding='utf-8-sig'),1):
        if line.startswith('Startpoint'):block=[line];first=line_number
        elif block:
            block.append(line)
            if line.startswith(' Slack'):
                text=''.join(block);kind=re.findall(r'^ (Recovery|Removal) time\s',text,re.M)
                if kind and 'Slack (VIOLATED)' in text:
                    def one(pattern):
                        values=re.findall(pattern,text,re.M)
                        require(len(values)==1,'missing/ambiguous failed reset record')
                        return values[0]
                    clocks=re.findall(r'^ Clock (\S+) \((rising|falling) edge\)',text,re.M)
                    require(len(clocks)==2,'failed reset needs two native clock edges')
                    rows.append({'Source':one(r'^Startpoint\s*:\s*(\S+)\s*$'),
                        'Endpoint':one(r'^Endpoint\s*:\s*(\S+)\s*$'),
                        'Corner':one(r'^Path Type\s*:\s*(?:max|min) \((slow|fast) corner\)\s*$'),
                        'Kind':kind[0].lower(),'LaunchClock':clocks[0][0],'CaptureClock':clocks[1][0],
                        'SlackNS':float(one(r'^ Slack \(VIOLATED\)\s+([-0-9.]+)\s*$')),
                        'ReportLine':first})
                block=[]
    tables,_=physical.timing.parse_summaries(Path(report).open(encoding='utf-8-sig'))
    for (corner,kind),groups in tables.items():
        if kind not in ('recovery','removal'):continue
        for pair,data in groups.items():
            identities={(r['Source'],r['Endpoint']) for r in rows if r['Corner']==corner and r['Kind']==kind
                        and (r['LaunchClock'],r['CaptureClock'])==pair}
            require(len(identities)==data['FailingChecks'], 'failed reset native detail/summary coverage differs')
    return rows


def reset_scope(g,sync,report):
    # A data synchronizer is not a reset release chain. Require a constant-one
    # first D and a direct second D before proposing either asynchronous RS.
    releases=[]
    for chain in sync:
        first=g.ff[chain['First']]
        if first['Primitive']!='V_FFASYN' or chain['InterstageLogic'] is not None:continue
        try:one=g.constant_one(first['Ports']['D'])
        except ValueError:one=False
        if one:releases.append(chain)
    safe={n for chain in releases for n in (chain['First'],chain['Second'])}
    by_parent=defaultdict(list)
    for n,c in g.ff.items():
        if c['Primitive']=='V_FFASYN':by_parent[parent(n)].append(n)
    groups=defaultdict(set);details=[];remaining=[];cache={}
    for destination,c in sorted(g.ff.items()):
        if c['Primitive']!='V_FFASYN':continue
        dc=g.clock(c['Ports']['CK'])['Domain']
        for kind,source in sorted(physical.support(g,c['Ports']['SR'],cache)):
            if kind!='ff':continue
            sc=g.clock(g.ff[source]['Ports']['CK'])['Domain']
            if sc==dc:continue
            item={'SourceFF':source,'DestinationFF':destination,'SourceClock':sc,'DestinationClock':dc,
                  'Source':parent(source)+'/CLK','Endpoint':parent(destination)+'/RS'}
            if destination not in safe:
                remaining.append(item);continue
            require(all(n in safe for n in by_parent[parent(destination)]),
                    'native RS also resets unapproved business FFs')
            details.append(item)
    failed=failing_reset_paths(report)
    safe_pairs={(r['Source'],r['Endpoint']) for r in details}
    selected={(r['Source'],r['Endpoint']) for r in failed}
    require(selected and selected<=safe_pairs,'failing reset is not an exact proved local release-chain RS')
    for source,endpoint in sorted(selected):groups[source].add(endpoint)
    queries=[];commands=[];body=[]
    for i,(source,targets) in enumerate(sorted(groups.items()),1):
        targets=sorted(targets);fr='^('+re.escape(source)+')$';to='^('+'|'.join(re.escape(n) for n in targets)+')$'
        queries.append({'Family':'local_reset_release_async_RS','Source':source,'Targets':targets,
            'FromRegex':fr,'ToRegex':to,'ExpectedTargetCount':len(targets)})
        body+=['puts {RAW_RESET_'+str(i)+'_SOURCE}','get_pins -hierarchical -regexp {'+fr+'}',
               'puts {RAW_RESET_'+str(i)+'_TARGETS}','get_pins -hierarchical -regexp {'+to+'}']
        commands.append('set_false_path -from [get_pins -hierarchical -regexp {'+fr+
                        '}] -to [get_pins -hierarchical -regexp {'+to+'}]')
    return {'NativeQueries':queries,'UnappliedResetCommands':commands,'LogicalAsyncResetRelationships':details,
        'OriginalFailingResetPaths':failed,'OnlyActuallyFailingResetPairsSelected':True,
        'UnwaivedPassingLocalReleaseRelationships':[r for r in details if (r['Source'],r['Endpoint']) not in selected],
        'RemainingForeignAsyncResetConsumers':remaining,'OnlyLocalReleaseChainRSProposed':True,
        'OrdinaryBusinessRSRemainTimed':True,'NoDataPinWaivers':True},'\n'.join(body)+'\n','\n'.join(commands)+'\n'


def derive(build_plan,export_receipt,route_receipt):
    build_plan=Path(build_plan).resolve();export_receipt=Path(export_receipt).resolve();route_receipt=Path(route_receipt).resolve()
    plan=build.validate(build_plan);export,watched=native.bind_receipt(export_receipt)
    routed,inputs=native.bind_receipt(route_receipt);native.merge(watched,inputs)
    require(export['Mode']=='export' and routed['Mode']=='report' and
        all(export[k]==routed[k] for k in ('SourceADF','SourceADFSHA256','BuildPlanSHA256'))
        and export['BuildPlanSHA256']==sha(build_plan),'reset review uses different native candidates')
    net=export_receipt.parent/'generate_netlist'/(TARGET+'_sim.v')
    native.add(watched,net);g=physical.graph(net.read_text(encoding='utf-8-sig'))
    sync=actual_chains(g)
    report=export_receipt.parent/'report_timing'/(TARGET+'.rtr');native.add(watched,report)
    raw=raw_graph_review(g,sync);scope,query,fdc=reset_scope(g,sync,report)
    native.add(watched,SAMPLER_FF_MODEL,SAMPLER_FF_MODEL_SHA)
    raw['SourceSampling']['SynchronousFFModel']=ref(SAMPLER_FF_MODEL)
    require(scope['NativeQueries'],'no current local release reset scope')
    native.query_commands(query)
    for module in (build,native,physical,boolean):native.add(watched,module.__file__)
    native.add(watched,SELF)
    result={'Schema':SCHEMA,'Target':TARGET,'Producer':ref(SELF),'AuditPassed':True,
        'BuildPlan':ref(build_plan),'ExportReceipt':ref(export_receipt),'RouteReceipt':ref(route_receipt),
        'SourceADF':ref(export['SourceADF']),'NativeNetlist':ref(net),'ActualFFs':len(g.ff),
        'Synchronizers':sync,**raw,**scope,'NativeNamesQueried':False,'ConstraintsApplied':False,
        'ResetScopeVerified':True,'HardwareAccessed':False,'HardwareReleaseAllowed':False,'TimingAccepted':False,
        'InputSHA256':{str(p):h for p,h in watched.items()},
        'Limits':'Current mapped digital reset/guard structure and unapplied exact RS proposal only. Retained configuration/UART async business resets remain timed; no top-wide local-release assertion. Native exact selectors, all remaining reset/data STA, functional/placement/routing preservation remain separate.'}
    return result,watched,query,fdc


def verify(path):
    path=Path(path).resolve();saved=read(path)
    require(saved.get('Schema')==SCHEMA and saved.get('Target')==TARGET,'wrong current raw reset review')
    actual,watched,_,_=derive(saved['BuildPlan']['Path'],saved['ExportReceipt']['Path'],saved['RouteReceipt']['Path'])
    require(json.loads(json.dumps(actual))==saved,'saved reset review differs from recomputation')
    native.add(watched,path);return actual,watched


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build-plan',type=Path,required=True)
    p.add_argument('--export-receipt',type=Path,required=True);p.add_argument('--route-receipt',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True);a=p.parse_args();out=build.work_path(a.output_dir)
    require(not out.exists(),'fresh reset-review directory required')
    value,_,query,fdc=derive(a.build_plan,a.export_receipt,a.route_receipt);out.mkdir()
    (out/'query.tcl').write_text(query,encoding='ascii',newline='\n')
    (out/'UNAPPLIED-reset-scope.fdc').write_text(fdc,encoding='ascii',newline='\n')
    write(out/'review.json',value)
    print(json.dumps({'AuditPassed':True,'RawBusinessFFs':len(value['RawBusinessRegisters']),
        'ExactResetSources':len(value['NativeQueries']),'RemainingForeignBusinessRS':len(value['RemainingForeignAsyncResetConsumers'])}))


if __name__=='__main__':main()
