"""Apply only the fisheye candidate's independently reviewed exact CDC scope.

Plans come only from a completely recomputed fisheye audit and its independent
source-diagnostic review. Application changes only one ADF copy. Large held
bundles retain their complete actual native support matrix while bounded exact
CLK/Q/endpoint collections apply the reviewed role and budget. Fresh final STA,
per-corner group effect, protocol and reset evidence remain required.
"""
import argparse
import ast
from collections import Counter
import copy
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import hdmi_camera_fisheye_fill8r3s3_build as build
import hdmi_camera_fisheye_fill8r3s3_scoped_native as native
import audit_ddr_final_timing as timing

SELF=Path(__file__).resolve()
SCHEMA='hdmi-camera-fisheye-fill8r3s3-physical-planning-v1'
AUDIT_SCHEMA='hdmi-camera-fisheye-fill8r3s3-native-audit-v1'
require,sha,read=build.require,build.sha,build.read
add,merge,ref=native.add,native.merge,native.ref
MATCH=re.compile(r"^I: Timing-5001: The pattern '(.*)' in command '(.*)' match (\d+) objects below: (.*)$")
APPLICATION_SCHEMA='hdmi-camera-fisheye-fill8r3s3-physical-application-v1'
MARKER='HDMI_CAMERA_FISHEYE_EXACT_PHYSICAL_SCOPE_SAVED'
GUIDE=Path('D:/pango/PDS_2023.2/doc/User_Constraint_Editor_User_Guide.pdf')
GUIDE_SHA='3f44bba22c92112d04b1c60d32289604498239efcfc156db888cfb0011e10dde'
_AUTHORITY_CACHE={}
_SUPPLEMENT_CACHE={}


def supplemental_reviews(scope):
    """Recompute narrow independent facts; reuse only a full hash-bound closure."""
    if not all(k in scope for k in('BuildPlan','ExportReceipt','RouteReceipt','BaselineTimingReport')):
        return {},{},{}
    macro=importlib.import_module('hdmi_camera_fisheye_fill8r3s3_macro_we_aliases')
    startup=importlib.import_module('hdmi_camera_fisheye_fill8r3s3_vendor_startup')
    watched={};values=[]
    macro_inputs={k:scope[k]for k in('Target','ProposalReady','NativeNetlist','RouteDump','BaselineTimingReport')}
    macro_inputs.update(PrimitiveBoundaries=[r for r in scope['PrimitiveBoundaries']if r['Primitive']=='V_RAM32X2'],
        SelectedEndpoints=sorted(macro.selected_functional_endpoints(scope)),
        NativeEndpointSupport={k:v for k,v in scope['NativeEndpointSupport'].items()if k.endswith('/WE')})
    cases=[('macro-write-enable',macro,macro_inputs,lambda:macro.review(scope)),
        ('vendor-startup',startup,{k:scope[k]for k in('BuildPlan','ExportReceipt','RouteReceipt')},
            lambda:startup.review(scope['BuildPlan']['Path'],scope['ExportReceipt']['Path'],scope['RouteReceipt']['Path']))]
    for kind,module,inputs,derive in cases:
        require(Path(module.__file__).resolve()==build.ROOT/'tools'/(module.__name__+'.py'),
            'supplemental provider location differs')
        key=(kind,sha(module.__file__),hashlib.sha256(json.dumps(inputs,sort_keys=True,separators=(',',':')).encode()).hexdigest())
        cached=_SUPPLEMENT_CACHE.get(key)
        if cached is None:
            value,files=derive();files=dict(files);static_helpers(files,module.__file__)
            require(value.get('Passed')is True and value.get('Missing')==[]and value.get('Violations')==[],
                'independent current supplemental physical review is incomplete: '+kind)
            require(not baseline_drift(files),'supplemental physical review input drift')
            _SUPPLEMENT_CACHE[key]=copy.deepcopy((value,files));cached=_SUPPLEMENT_CACHE[key]
        require(not baseline_drift(cached[1]),'cached supplemental physical review input drift')
        value,files=copy.deepcopy(cached);values.append(value);merge(watched,files)
    return values[0],values[1],watched


def supplemental_startup_resets(scope,review=None):
    if review is None:_,review,_=supplemental_reviews(scope)
    if not review:return []
    source=review['Source'];timing=review['RoutedTiming'];require(timing.get('CompleteActualResetPathCoverage')is True,
        'all actual startup reset physical pins need both-corner recovery/removal bounds')
    examples=[r for r in scope['ResetScopes']if r['LaunchQ']==source['SourceNativeOutputPin']]
    require(examples,'startup source lacks independently bound exact physical CLK/Q aliases')
    example=examples[0];objects=example['NativeObjects']
    require(objects['SourceFFs']==[source['SourceFF']]and objects['SourcePhysicalQ']==[source['SourcePhysicalQ']],
        'supplemental startup source differs from original native FF slot')
    targets={}
    for target in review['Targets']:targets.setdefault(target['PhysicalEndpoint'],[]).append(target)
    result=[]
    for physical,consumers in sorted(targets.items()):
        evidence=[r for r in timing['Rows']if r['PhysicalEndpoint']==physical]
        names=sorted({r['Endpoint']for r in evidence});require(names,'startup reset target lacks actual STA arcs')
        ffs=sorted(r['FF']for r in consumers);indexes=[i for i,r in enumerate(scope['ForeignRelationships'])
            if r['SourceFF']==source['SourceFF']and r.get('DestinationFF')in ffs and r.get('DestinationPin')=='SR']
        require(indexes and {scope['ForeignRelationships'][i]['DestinationFF']for i in indexes}==set(ffs),
            'supplemental reset must retain every original native foreign relationship')
        require(all(scope['ForeignRelationships'][i]['Role']=='vendor_global_common_reset_remains_timed'
            and scope['ForeignRelationships'][i].get('TimedWithoutException')is True for i in indexes),
            'supplemental startup proof cannot silently override another original audit role')
        row={k:copy.deepcopy(example[k])for k in('FromCLK','FromCLKVariants','FromCLKVariantProof')if k in example}
        row.update(LaunchQ=source['SourceNativeOutputPin'],Endpoint=names[0],
            LaunchClock=source['LaunchClock'],CaptureClock=source['CaptureClock'],
            TargetKind='SupplementalVendorStartupReset',Family=review['Family'],
            Role='independently_proven_vendor_startup_clock_stop_reset',RelationshipIndexes=indexes,
            OriginalAuditRole='vendor_global_common_reset_remains_timed',OriginalTimedWithoutException=True,
            SupplementalRoleOverrideExplicit=True,GuardAccepted=True,
            GuardProof={'SupplementalVendorStartupReviewPassed':True,'OnlyEnumeratedResetFunctionProven':True,
                'PhysicalResetPin':physical,'MinimumStartupWindowNS':review['MinimumStartupWindowNS'],
                'MaximumRequiredNS':review['MaximumRequiredNS']},
            NativeObjects={'SourceFFs':[source['SourceFF']],'DestinationFFs':ffs,
                'SourcePhysicalQ':[source['SourcePhysicalQ']],'SourceCLKNet':objects['SourceCLKNet']})
        result.append(row)
    return result


def authority(kind,path,derive):
    """Process-local verified authority; every reuse hashes its entire closure."""
    path=Path(path).absolute();require(path==path.resolve() and build.local_io(path).is_file(),'canonical authority file required')
    key=(kind,str(path),sha(path));cached=_AUTHORITY_CACHE.get(key)
    if cached is not None:
        require(not baseline_drift(cached[1]),'cached fisheye authority input drift')
        return copy.deepcopy(cached)
    value,watched=derive(path);watched=dict(watched)
    add(watched,path);add(watched,SELF)
    require(not baseline_drift(watched),'fisheye authority input changed during verification')
    _AUTHORITY_CACHE[key]=copy.deepcopy((value,watched));return copy.deepcopy((value,watched))


def baseline_drift(watched):return [str(p) for p,h in watched.items() if not build.local_io(p).is_file() or sha(p)!=h]


def exact_selector(names):
    require(isinstance(names,list) and names and names==sorted(set(names)),'sorted unique native pin names required')
    require(all(isinstance(n,str) and re.fullmatch(r'[A-Za-z_$][A-Za-z0-9_$./\[\]-]*',n) for n in names),
            'native pin names must be literal canonical objects')
    pattern='^('+'|'.join(re.escape(n) for n in names)+')$'
    return {'Pattern':pattern,'Names':names,'Command':'get_pins -hierarchical -regexp {'+pattern+'}'}


def exact_names(selectors,text):
    """One actual native result per command, with no extra/missing/duplicate pin."""
    parsed=[]
    for line in text.splitlines():
        m=MATCH.fullmatch(line)
        if not m or not m[2].startswith('get_pins '):continue
        names=m[4].split();require(int(m[3])==len(names)==len(set(names)),'native pin count/list differs')
        require(m[2] in ('get_pins -hierarchical -regexp '+m[1],
                        'get_pins -hierarchical -regexp {'+m[1]+'}'),'native query command differs')
        parsed.append((m[1],names))
    require(len(parsed)==len(selectors),'unexpected/missing native selector results')
    require(Counter(pattern for pattern,names in parsed)==Counter(q['Pattern'] for q in selectors),
            'native selector inventory differs')
    for q in selectors:
        rows=[names for pattern,names in parsed if pattern==q['Pattern']]
        require(len(rows)==1 and set(rows[0])=={'t:'+n for n in q['Names']},'actual native selector names differ')
    return {'ExactNativeNamesVerified':True,'Selectors':len(selectors),
            'Objects':sum(len(q['Names']) for q in selectors)}



def clock_variants(row,scope=None):
    """Exact aliases of one physical clock pin; never a clock-domain scope."""
    original=row.get('FromCLK');exact_selector([original])
    names=row.get('FromCLKVariants')
    if names is None:return [original]
    require(isinstance(names,list)and 1<=len(names)<=8 and names==sorted(set(names))
        and original in names,'bounded exact native CLK variants required')
    for name in names:
        exact_selector([name]);require(name.endswith('/CLK'),'CLK variant is not a native clock pin')
    objects=row.get('NativeObjects',{});qs=objects.get('SourcePhysicalQ',[]);nets=objects.get('SourceCLKNet',[])
    require(len(qs)==len(nets)==1,'one physical source Q/clock net required for CLK variants')
    site=qs[0].rsplit('/',1)[0];proof=row.get('FromCLKVariantProof',{})
    if 'SharedSourceClockProofKey'in proof:
        key=proof['SharedSourceClockProofKey'];table=scope.get('SharedSourceClockProofs',{})if isinstance(scope,dict)else{}
        require(isinstance(key,str)and key in table and isinstance(table[key],dict),
            'shared source clock proof is missing from the bound current scope')
        full=table[key]
        require('SharedSourceClockProofKey'not in full
            and all(k in full and full[k]==v for k,v in proof.items()if k!='SharedSourceClockProofKey'),
            'shared source clock proof differs from its exact row reference')
        proof=full
    require(proof.get('Verified')is True and proof.get('PhysicalCLK')==site+'/CLK'
        and proof.get('CLKNet')==nets[0],'native CLK aliases lack physical-site/net identity')
    parents=proof.get('Parents')
    require(isinstance(parents,list)and all(isinstance(r,dict)for r in parents)and len(parents)==len(names)
        and [r.get('CLKPin')for r in parents]==names,'complete ordered native clock-parent proof required')
    for entry,name in zip(parents,names):
        require(entry.get('Instance')==name.rsplit('/',1)[0]and entry.get('Site')==site
            and entry.get('CLKNet')==nets[0],'CLK alias parent has another site/clock net')
    return names


def timing_endpoint_aliases(scope):
    """Finite valid STA arcs of one independently proved physical control.

    Sharing a physical input does not make the STA arc names interchangeable.
    Every observed valid arc is selected explicitly; unobserved CDB aliases do
    not become timing endpoints merely because get_pins returned them.
    """
    if not isinstance(scope,dict):return {}
    table=scope.get('QualifiedTimingControlEndpointProofs',{});require(isinstance(table,dict),'typed timing-control proof table required')
    aliases={};owners={}
    for physical,proof in table.items():
        require(isinstance(proof,dict)and proof.get('Verified')is True
            and all(proof.get(k)is True for k in('CompleteControlledFFInventoryVerified',
                'SourceSupportEqualityVerified','ClockRootAndPolarityAndMuxVerified'))
            and proof.get('GetPinsExistenceAloneAccepted')is False
            and proof.get('ArbitrarySameClockOrHierarchyPrefixAliasAccepted')is False,
            'all valid timing-control aliases need complete actual physical/net/clock/support proof')
        require(physical==proof.get('PhysicalTimingPin')and physical.rsplit('/',1)[-1]in('CE','RS'),
            'only exact proved physical CE/RS timing arcs may share a selector')
        canonical=proof.get('CanonicalTimingEndpoint');names=proof.get('OtherObservedCanonicalNames')
        require(isinstance(names,list)and names and names==sorted(set(names))and canonical in names,
            'complete finite actual reported timing-control arc names required')
        exact_selector(names)
        require(proof.get('CurrentBaselineReport')==scope.get('BaselineTimingReport'),
            'timing-control alias evidence identifies another baseline report')
        site,pin=physical.rsplit('/',1);signature=proof.get('NativeControlSignature');net=proof.get('NativeControlNet')
        controlled=proof.get('ControlledFFs');require(isinstance(controlled,list)and controlled and net and signature,
            'complete current physical-control consumers required')
        parents={entry.get('NativeParent')for entry in controlled}
        roots=set()
        for entry in controlled:
            clock=entry.get('Clock',{})
            require(entry.get('Placement',{}).get('Site')==site and entry.get('NativeControlNet')==net
                and entry.get('NativeControlSignature')==signature and clock.get('Root')and clock.get('Trace'),
                'timing aliases change control site/net/polarity/mux or clock root')
            roots.add((clock.get('Domain'),clock['Root']))
        require(len(roots)==1,'one physical control cannot mix unproved FF clock roots')
        for name in names:
            require(name.endswith('/'+pin)and name.rsplit('/',1)[0]in parents,
                'reported control alias is outside complete controlled FF inventory')
            require(name not in owners or owners[name]==canonical,'ambiguous timing endpoint physical-control owner')
            owners[name]=canonical
        aliases[canonical]={'Names':names,'PhysicalTimingPin':physical,'ProofKey':physical}
    macro,startup,_=supplemental_reviews(scope)
    for physical,proof in macro.get('ByPhysicalPin',{}).items():
        ends=proof['EquivalentCanonicalEndpoints'];names=proof['NativeTimingAliases']
        require(proof.get('Passed')is True and proof.get('CompleteFunctionalSupportIdentical')is True
            and proof.get('NativeModeClockAndPolarityIdentical')is True
            and proof.get('AllOriginalFunctionalEndpointMatrixObligationsRetained')is True
            and ends==proof['EquivalentFunctionalEndpoints']and ends==sorted(set(ends))and ends,
            'all native RAM WE aliases need complete equivalent original functional consumers')
        exact_selector(names);require(names==sorted(set(names))and set(ends)<=set(names),
            'every original functional RAM WE endpoint needs an actually observed finite timing arc')
        rows=[(part,r)for part,key in(('data','DataScopes'),('reset','UserSynchronousResetScopes'))
            for r in scope.get(key,[])if r['Endpoint']in ends]
        by_source={}
        for part,row in rows:by_source.setdefault(row['LaunchQ'],[]).append((part,row))
        for source,members in by_source.items():
            require({r['Endpoint']for _,r in members}==set(ends)and len(members)==len(ends),
                'RAM timing alias projection omits an original source/functional endpoint obligation')
            signatures=[]
            for part,row in members:
                signatures.append({'Partition':part,**{k:row.get(k)for k in('FromCLK','FromCLKVariants',
                    'FromCLKVariantProof','Role','Roles','MaximumNS','BoundBasis','SourceDomain','DestinationDomain',
                    'FunctionalDestinationPin','TargetKind')},
                    'SourceObjects':{k:row['NativeObjects'][k]for k in('SourceFFs','SourcePhysicalQ','SourceCLKNet')}})
                if part=='reset':require(row.get('GuardAccepted')is True and all(row.get('GuardProof',{}).get(k)is True
                    for k in('NativeNextQInactiveGuardVerified','LocalReleaseChainVerified','OnlyResetFunctionProven',
                        'NativeWEInactiveGuardVerified'))and row['GuardProof'].get('BusinessDataPathWaiver')is False,
                    'equivalent RAM reset timing arcs still need every original strong local no-write guard')
            require(all(x==signatures[0]for x in signatures[1:]),
                'RAM WE alias equivalence cannot merge source clocks, roles, budgets, domains or reset partitions')
        representative=ends[0]
        for canonical in ends:
            require(canonical not in aliases,'macro WE overlaps another typed physical timing input')
            aliases[canonical]={'Names':names,'PhysicalTimingPin':physical,'ProofKey':physical,
                'RepresentativeEndpoint':representative,'EquivalentCanonicalEndpoints':ends,
                'OriginalFunctionalScopeRows':len(rows),'AllOriginalFunctionalObligationsRetained':True}
    if startup:
        for row in supplemental_startup_resets(scope,startup):
            physical=row['GuardProof']['PhysicalResetPin'];names=sorted({r['Endpoint']for r in startup['RoutedTiming']['Rows']
                if r['PhysicalEndpoint']==physical})
            require(row['Endpoint']not in aliases,'supplemental startup reset overlaps an existing accepted timing-control constraint')
            aliases[row['Endpoint']]={'Names':names,'PhysicalTimingPin':physical,
                'ProofKey':'supplemental-startup:'+physical,'SupplementalStartupFamily':startup['Family']}
    return aliases


def endpoint_variants(row,aliases):
    entry=aliases.get(row['Endpoint']);return entry['Names']if entry else[row['Endpoint']]


def timing_endpoint_index(scope):
    return {name:{'Endpoint':entry.get('RepresentativeEndpoint',canonical),
        'PhysicalTimingPin':entry['PhysicalTimingPin'],'ProofKey':entry['ProofKey']}
        for canonical,entry in timing_endpoint_aliases(scope).items()for name in entry['Names']}


def canonical_scope_lookup(scope,rows):
    aliases=timing_endpoint_aliases(scope);result={}
    for index,row in enumerate(rows):
        entry=aliases.get(row['Endpoint'],{});end=entry.get('RepresentativeEndpoint',row['Endpoint'])
        key=row['LaunchQ'],end
        if key not in result:
            value=dict(row);value['Endpoint']=end;value['OriginalScopeObligations']=[];result[key]=value
        else:
            require(row['Endpoint']in entry.get('EquivalentCanonicalEndpoints',[])
                and result[key]['OriginalScopeObligations'],
                'duplicate native pair is not an independently proved equivalent physical RAM WE input')
        result[key]['OriginalScopeObligations'].append({'Index':index,'Endpoint':row['Endpoint'],
            'RelationshipIndexes':row.get('RelationshipIndexes',[])})
    return result


def endpoint_chunks(endpoints,aliases):
    chunks=[];names=[];canonical=[]
    for end in sorted(endpoints):
        selected=endpoint_variants({'Endpoint':end},aliases);candidate=sorted(set(names)|set(selected))
        if names and(len(candidate)>70 or len(exact_selector(candidate)['Pattern'])>4096):
            chunks.append((canonical,names));names=[];canonical=[];candidate=selected
        require(len(candidate)<=70 and len(exact_selector(candidate)['Pattern'])<=4096,
            'one proved control timing-alias set exceeds bounded native selector capability')
        names=candidate;canonical.append(end)
    if names:chunks.append((canonical,names))
    return chunks


def selectors_for(rows,scope=None):
    # Current PDS independently returned every name from 4091/4094-character
    # literal unions (58/70 pins). Retain that bound and check actual names on
    # every fresh candidate; no earlier candidate's pin results are inherited.
    aliases=timing_endpoint_aliases(scope)
    names=sorted({name for r in rows for name in (clock_variants(r,scope)+[r['LaunchQ']]+endpoint_variants(r,aliases))})
    parts=[[name]for name in names]if len(names)<=240 else bounded_name_chunks(names)
    result=[exact_selector(part)for part in parts]
    require(all(len(q['Pattern'])<=4096 for q in result),'bounded literal native selector required')
    return result


def data_constraint_groups(scope):
    """Recompute every collection axis and allowed pair from exact native rows.

    The audit independently checks the complete functional/native support
    matrix. A collection may not acquire a timed relationship of another role
    or budget merely because its source and destination names share an axis.
    """
    groups=scope.get('ConstraintGroups')
    if groups is None:return []
    rows=scope['DataScopes'];require(isinstance(groups,list)and groups,'nonempty exact constraint groups required')
    memberships=[];pair_owner={}
    for number,group in enumerate(groups):
        indexes=group.get('ScopeIndexes')
        require(isinstance(indexes,list)and indexes and indexes==sorted(set(indexes))
            and all(type(i)is int and 0<=i<len(rows)for i in indexes),'exact group scope indexes required')
        selected=[rows[i]for i in indexes];memberships.extend(indexes)
        require(type(group.get('MaximumNS'))in(int,float)and math.isfinite(group['MaximumNS'])
            and group['MaximumNS']>0,'finite nonboolean native group delay budget required')
        require(all(r['Role']==group.get('Role')and r['MaximumNS']==group.get('MaximumNS')
            and r.get('SourceDomain')==group.get('SourceDomain')and r.get('DestinationDomain')==group.get('DestinationDomain')
            for r in selected)and isinstance(group.get('SourceDomain'),str)and isinstance(group.get('DestinationDomain'),
            str)and group['SourceDomain']!=group['DestinationDomain'],
            'constraint group mixes crossing roles, clock roots or delay budgets')
        require(group.get('FunctionalNativeSupportMatrixComplete')is True
            and group.get('ReportedEnumerationComplete')is False
            and group.get('MatrixConstraintCoverageComplete')is False and group.get('ConstraintsApplied')is False,
            'unapplied complete functional/native support matrix required')
        pairs={}
        for i in indexes:pairs.setdefault((rows[i]['LaunchQ'],rows[i]['Endpoint']),[]).append(i)
        expected=[{'LaunchQ':q,'Endpoint':end,'ScopeIndexes':members}for(q,end),members in sorted(pairs.items())]
        require(group.get('AllowedPairs')==expected,'group allowed-pair matrix differs from exact native scopes')
        for key,actual in (('FromCLKs',sorted({n for r in selected for n in clock_variants(r,scope)})),
            ('LaunchQs',sorted({r['LaunchQ']for r in selected})),('Endpoints',sorted({r['Endpoint']for r in selected}))):
            require(group.get(key)==actual,'group '+key+' expands or drops actual native objects')
        support=scope.get('NativeEndpointSupport');require(isinstance(support,dict),'complete native endpoint support required')
        actual=set();sources=set(group['LaunchQs']);axis_sources={}
        for r in selected:
            for ff in r['NativeObjects']['SourceFFs']:
                require(ff not in axis_sources or axis_sources[ff]==r['LaunchQ'],
                    'one qualified native source FF has conflicting launch Q identities')
                axis_sources[ff]=r['LaunchQ']
        for end in group['Endpoints']:
            entry=support.get(end,{})
            require(entry.get('SourceSupportComplete')is True and isinstance(entry.get('SourceFFs'),list)
                and entry['SourceFFs'] and entry['SourceFFs']==sorted(set(entry['SourceFFs']))
                and isinstance(entry.get('LaunchQs'),list)and entry['LaunchQs']==sorted(set(entry['LaunchQs']))
                and entry.get('FunctionalBoundaryNet')and entry.get('NativeBoundaryNet'),
                'complete actual native boundary FF/launch support required')
            projected={axis_sources[ff]for ff in entry['SourceFFs']if ff in axis_sources}
            require(projected==set(entry['LaunchQs'])&sources,
                'native launch projection drops or adds a qualified FF from complete endpoint support')
            actual.update((q,end)for q in projected)
        require(actual==set(pairs),'group Cartesian axes include unlisted actual native support or omit a supported pair')
        proof=group.get('NativeSupportMatrixProof',{})
        require(type(proof.get('SupportedAxisPairs'))is int and proof=={'AllAxisCrossProductsCheckedAgainstCompleteNativeEndpointSupport':True,
            'SourceDomain':group['SourceDomain'],'DestinationDomain':group['DestinationDomain'],
            'SupportedAxisPairs':len(actual),'MissingPairs':[],'UnexpectedPairs':[]},
            'complete native support-matrix proof differs')
        for pair in pairs:
            require(pair not in pair_owner,'native launch/endpoint occurs in multiple constraint groups')
            pair_owner[pair]=number
    require(sorted(memberships)==list(range(len(rows))),'constraint grouping drops or repeats native scopes')
    # Include relationships deliberately left timed, not only requested cuts.
    all_pairs={(r.get('SourceNativeOutputPin'),b.get('Endpoint'))
        for r in scope['ForeignRelationships']for b in r.get('NativeBoundaries',[])}
    for number,group in enumerate(groups):
        qs=set(group['LaunchQs']);ends=set(group['Endpoints'])
        require(all(pair_owner.get(pair)==number for pair in all_pairs if pair[0]in qs and pair[1]in ends),
            'collection axes include an unlisted or differently reviewed native relationship')
    return groups


def bounded_name_chunks(names,maximum=4096,maximum_names=70):
    """Literal native selectors, bounded independently of total matrix size."""
    result=[];chunk=[]
    for name in sorted(set(names)):
        candidate=chunk+[name]
        if len(exact_selector(candidate)['Pattern'])>maximum or len(candidate)>maximum_names:
            require(chunk,'one native pin name exceeds the selector bound');result.append(chunk);chunk=[name]
            require(len(exact_selector(chunk)['Pattern'])<=maximum,'one native pin name exceeds the selector bound')
        else:chunk=candidate
    if chunk:result.append(chunk)
    return result


def data_execution_chunks(scope,groups=None):
    """Partition collection commands while retaining every permitted pair.

    All Qs in a chunk retain their verified physical CLK alias union. Endpoint
    chunks contain actual support pairs, avoiding empty from-through-to rules.
    Other Cartesian combinations may only be nonexistent native paths, as
    established by the audit's complete support-matrix proof.
    """
    groups=data_constraint_groups(scope)if groups is None else groups
    rows=scope['DataScopes'];result=[];aliases=timing_endpoint_aliases(scope)
    for number,group in enumerate(groups):
        by_q={}
        for i in group['ScopeIndexes']:by_q.setdefault(rows[i]['LaunchQ'],[]).append(i)
        source_chunks=[];qs=[];clks=set()
        for q,indexes in sorted(by_q.items()):
            clocks={n for i in indexes for n in clock_variants(rows[i],scope)}
            candidate=sorted(clks|clocks)
            if qs and(max(len(exact_selector(candidate)['Pattern']),len(exact_selector(qs+[q])['Pattern']))>4096
                or len(candidate)>70 or len(qs)+1>70):
                source_chunks.append((qs,sorted(clks)));qs=[];clks=set()
            qs.append(q);clks.update(clocks)
            require(max(len(exact_selector(sorted(clks))['Pattern']),len(exact_selector(qs)['Pattern']))<=4096,
                'source Q/physical CLK alias union exceeds native selector bound')
        if qs:source_chunks.append((qs,sorted(clks)))
        covered=[]
        for qs,clocks in source_chunks:
            indexes=sorted(i for q in qs for i in by_q[q]);endpoints={rows[i]['Endpoint']for i in indexes}
            for canonical,ends in endpoint_chunks(endpoints,aliases):
                endset=set(canonical);members=[i for i in indexes if rows[i]['Endpoint']in endset]
                require(members,'empty native collection command');covered.extend(members)
                result.append({'GroupIndex':number,'ScopeIndexes':members,'FromCLKs':clocks,
                    'LaunchQs':qs,'Endpoints':ends,'CanonicalEndpoints':canonical,
                    'MaximumNS':group['MaximumNS'],'Role':group['Role']})
        require(sorted(covered)==group['ScopeIndexes'],'collection command partition omits or repeats native pairs')
    return result


def candidate_query_bodies(scope):
    """Literal read-only exploration, granting no scope/application authority.

    A later formal application requires these complete bodies to equal its
    fully recomputed, accepted scope byte for byte.
    """
    if 'RequiredNativeObjects'in scope:
        require(scope.get('CandidateOnly')is True and scope.get('AuthorityIssued')is False,
            'only an unapplied native-object inventory can generate exploratory queries')
        plan=scope.get('BuildPlan',{});require(Path(plan.get('Path','')).is_file()
            and sha(plan['Path'])==plan.get('SHA256')and read(plan['Path']).get('Target')==build.TARGET,
            'native object inventory identifies another candidate build')
        names=scope['RequiredNativeObjects']
        require(isinstance(names,list)and names and names==sorted(set(names))and type(scope.get('Count'))is int
            and scope['Count']==len(names),'complete sorted unique literal native object inventory required')
        selectors=[exact_selector(part)for part in bounded_name_chunks(names)]
        return ['\n'.join(q['Command']for q in selectors[i:i+240])+'\n'for i in range(0,len(selectors),240)]
    canonical=scope.get('Schema')==AUDIT_SCHEMA and scope.get('Target')==build.TARGET
    if not canonical:
        require(scope.get('CandidateOnly')is True and scope.get('ProposalReady')is False
            and all(scope.get(k)is False for k in('ConstraintsApplied','TimingAccepted','HardwareReleaseAllowed')),
            'current unaccepted read-only candidate inventory required')
        plan=scope.get('BuildPlan',{});require(Path(plan.get('Path','')).is_file()
            and sha(plan['Path'])==plan.get('SHA256')and read(plan['Path']).get('Target')==build.TARGET,
            'candidate inventory must identify the actual fisheye build plan')
    rows=[]
    for key in('DataScopes','ResetScopes','VendorResetScopes','UserSynchronousResetScopes'):
        part=scope.get(key,[]);require(isinstance(part,list),'candidate exact native object lists required');rows+=part
    require(rows,'candidate native objects are empty');selectors=selectors_for(rows,scope)
    return ['\n'.join(q['Command']for q in selectors[i:i+240])+'\n'for i in range(0,len(selectors),240)]


def macro_destination(scope,row):
    """One actual distributed-memory WE with its current write-clock trace."""
    targets=row.get('NativeObjects',{}).get('DestinationObjects')
    require(isinstance(targets,list)and len(targets)==1 and isinstance(targets[0],dict),
        'one exact native macro input target required')
    target=targets[0]
    require(target.get('Primitive')in('V_RAM32X2','V_RAM64X1')and target.get('Pin')=='WE'
        and isinstance(target.get('Cell'),str)and target['Cell']and target.get('Endpoint')==row['Endpoint'],
        'only an actual typed distributed-memory write-enable target is supported')
    entries=[r for r in scope.get('PrimitiveBoundaries',[])if r.get('Cell')==target['Cell']]
    require(len(entries)==1 and entries[0].get('Primitive')==target['Primitive'],
        'native macro input lacks its actual primitive inventory')
    clocks=[r for r in entries[0].get('ClockBindings',[])if r.get('Pin')=='WCLK']
    require(len(clocks)==1 and clocks[0].get('Domain')==row.get('DestinationDomain')and clocks[0].get('Root')
        and isinstance(clocks[0].get('Trace'),list),'native macro WE destination write clock is not independently bound')
    return target


def synchronous_reset_rows(scope):
    """D/CE encoded reset functions have setup/hold, not SR recovery arcs."""
    rows=scope.get('UserSynchronousResetScopes',[])
    require(isinstance(rows,list),'explicit synchronous-reset-function inventory required')
    if not rows:return []
    relationships=scope['ForeignRelationships']
    for row in rows:
        for key in('FromCLK','LaunchQ','Endpoint'):exact_selector([row.get(key)])
        macro=row.get('TargetKind')=='MacroWriteEnableResetFunction'
        require(row['FromCLK'].endswith('/CLK')and row.get('TargetKind')in('FFSynchronousResetFunction','MacroWriteEnableResetFunction')
            and row.get('FunctionalDestinationPin')in(('WE',)if macro else('D','CE'))and row.get('GuardAccepted')is True,
            'exact typed FF D/CE synchronous-reset function required')
        proof=row.get('GuardProof',{})
        if proof.get('ProofKind')=='established_reset_state_stable_through_guarded_deassertion':
            require(not macro and all(proof.get(k)is True for k in('NativeResetStateEstablishedVerified',
                'NativeIdleResetValueInvariantVerified','SourceAdmissionGuardVerified',
                'GuardedDeassertionVerified','OnlyResetFunctionProven'))
                and type(proof.get('EstablishedPhysicalQ'))is int and proof['EstablishedPhysicalQ']in(0,1)
                and proof.get('ArbitrarySelfInactiveConstantClaimed')is False
                and proof.get('BusinessDataPathWaiver')is False
                and (proof.get('NativeNextQInactiveGuardVerified')is None
                    or proof.get('NativeNextQInactiveGuardVerified')is False),
                'encoded reset state needs established native state, invariant and guarded-deassertion admission proof')
        else:
            require(proof.get('ProofKind')in(None,'local_release_inactive_next_state')
                and all(proof.get(k)is True for k in('NativeNextQInactiveGuardVerified',
                    'LocalReleaseChainVerified','OnlyResetFunctionProven'))and proof.get('BusinessDataPathWaiver')is False,
                'synchronous reset needs actual local-release next-Q and reset-function proof')
        if macro:require(proof.get('NativeWEInactiveGuardVerified')is True,'macro reset function needs actual inactive WE=0 proof')
        objects=row.get('NativeObjects',{})
        expected={'SourceFFs','DestinationFFs','SourcePhysicalQ','SourceCLKNet'}
        require(set(objects)==expected|({'DestinationObjects'}if macro else set())
            and all(isinstance(objects.get(k),list)and objects[k]and objects[k]==sorted(set(objects[k]))
                for k in expected-({'DestinationFFs'}if macro else set()))
            and len(objects['SourcePhysicalQ'])==len(objects['SourceCLKNet'])==1,
            'synchronous-reset function lacks exact actual native FF/Q/clock identities')
        target=macro_destination(scope,row)if macro else None
        if macro:require(objects['DestinationFFs']==[],'typed macro target cannot masquerade as an ordinary FF')
        indexes=row.get('RelationshipIndexes')
        require(isinstance(indexes,list)and indexes and indexes==sorted(set(indexes))
            and all(type(i)is int and 0<=i<len(relationships)for i in indexes),
            'synchronous-reset function relationship indexes required')
        for i in indexes:
            r=relationships[i]
            require(r.get('SourceNativeClockPin')==row['FromCLK']and r.get('SourceNativeOutputPin')==row['LaunchQ']
                and r.get('DestinationPin')==row['FunctionalDestinationPin']
                and r.get('SourceFF')in objects['SourceFFs']
                and (r.get('TargetKind')=='MacroFunctionalInput'and r.get('DestinationObject')==target
                    and r.get('DestinationClock')==row['DestinationDomain']if macro else r.get('DestinationFF')in objects['DestinationFFs'])
                and r.get('SourcePhysicalQ')in objects['SourcePhysicalQ']and r.get('SourceNativeCLKNet')in objects['SourceCLKNet']
                and row['Endpoint']in {b.get('Endpoint')for b in r.get('NativeBoundaries',[])},
                'synchronous-reset function differs from actual native D/CE relationship')
    require(len({(r['LaunchQ'],r['Endpoint'])for r in rows})==len(rows),'duplicate synchronous reset native pair')
    return rows


def all_reset_rows(scope):return reset_rows(scope)+synchronous_reset_rows(scope)


def canonical_vendor_resets(scope,rows):
    """One unqualified pin constraint may have several internal clock proofs.

    Capture clocks are not aliases. The exact from/through/to false-path
    command contains no capture-clock or edge qualifier and is identical for
    these independently reviewed contexts. Preserve every original row and
    native report reference instead of treating one context as the others.
    """
    grouped={}
    for index,row in enumerate(rows):
        grouped.setdefault((row['FromCLK'],row['LaunchQ'],row['Endpoint']),[]).append((index,row))
    result=[]
    for entries in grouped.values():
        if len(entries)==1:result.append(entries[0][1]);continue
        common=[];origins=[];contexts=[]
        for index,row in entries:
            body=copy.deepcopy(row);capture=body.pop('CaptureClock')
            report=body['GuardProof'].pop('NativeReportCheck',None)
            expected={'Source':row['FromCLK'],'Endpoint':row['Endpoint'],'LaunchClock':row['LaunchClock'],
                'CaptureClock':capture,'Family':row['Family']}
            require(isinstance(report,dict)and all(report.get(k)==v for k,v in expected.items())
                and report.get('CaptureEdgesComplete')is True,'each typed reset capture context needs its own current report proof')
            variants=report.get('NativeVariants')
            require(isinstance(variants,list)and variants,'typed reset capture context has no native path evidence')
            for variant in variants:
                require(all(variant.get(k)==v for k,v in expected.items())
                    and variant.get('Corner')in('slow','fast')
                    and variant.get('LaunchEdge')in('rising','falling')and variant.get('CaptureEdge')in('rising','falling')
                    and variant.get('LaunchDataTransition')in('r','f')
                    and type(variant.get('NativeReportLine'))is int and variant['NativeReportLine']>0
                    and isinstance(variant.get('NativePathSHA256'),str)
                    and re.fullmatch('[0-9a-f]{64}',variant['NativePathSHA256']),
                    'typed reset native capture-context path identity differs')
            common.append(body);contexts.append(capture)
            origins.append({'Partition':'VendorResetScopes','Index':index,
                'RowSHA256':hashlib.sha256(json.dumps(row,sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest(),
                'CaptureClock':capture,'GuardProof':copy.deepcopy(row['GuardProof'])})
        require(all(body==common[0]for body in common[1:]),
            'duplicate typed reset constraints have conflicting physical identities, guards or constraint semantics')
        require(len(set(contexts))==len(contexts),'ambiguous repeated typed reset capture context')
        target=common[0]['NativeObjects']['DestinationObjects'][0]
        inventory=[r for r in scope.get('PrimitiveBoundaries',[])if r.get('Cell')==target['Cell']]
        require(len(inventory)==1 and inventory[0].get('Primitive')==target['Primitive'],
            'multi-clock reset target lacks its current primitive clock inventory')
        clocks=[r for r in inventory[0].get('ClockBindings',[])if r.get('Domain')in contexts]
        require(set(contexts)=={r.get('Domain')for r in clocks}
            and all(r.get('Root')and r.get('Pin')and isinstance(r.get('Trace'),list)and r['Trace']for r in clocks),
            'each internal reset capture clock needs its actual target pin/root/trace')
        # This is a checked common body, not a first-wins row. Context-specific
        # fields live only in complete provenance, so no clock is mislabelled.
        value=common[0];value['CaptureClocks']=sorted(contexts)
        value['ResetConstraintEvidence']={'OriginalRows':origins,'TargetClockBindings':clocks,
            'Constraint':'set_false_path','FromThroughToUnchanged':True,
            'CaptureClockQualifier':None,'EdgeQualifier':None,'CheckTypeQualifier':None,
            'DistinctInternalCaptureClocksAreAliases':False,'AllOriginalRowsRemainCoverageObligations':True}
        clock_variants(value,scope);result.append(value)
    return result


def reset_rows(scope):
    ordinary=scope.get('ResetScopes');vendor=scope.get('VendorResetScopes',[])
    require(isinstance(ordinary,list)and isinstance(vendor,list),'explicit fisheye reset inventories required')
    for row in ordinary:
        for key in ('FromCLK','LaunchQ','Endpoint'):exact_selector([row.get(key)])
        require(row['FromCLK'].endswith('/CLK')and row['Endpoint'].endswith(('/SR','/RS'))
            and row.get('GuardAccepted')is True and row.get('GuardProof'),
            'exact guarded ordinary FF reset scope required')
        indexes=row.get('RelationshipIndexes')
        require(isinstance(indexes,list)and indexes and indexes==sorted(set(indexes)),
            'reset relationship indexes required')
        for index in indexes:
            require(type(index)is int and 0<=index<len(scope['ForeignRelationships']),'reset relationship index invalid')
            relationship=scope['ForeignRelationships'][index]
            require(relationship.get('SourceNativeClockPin')==row['FromCLK']
                and relationship.get('SourceNativeOutputPin')==row['LaunchQ']
                and relationship.get('DestinationPin')=='SR'
                and row['Endpoint']in {b.get('Endpoint')for b in relationship.get('NativeBoundaries',[])},
                'reset scope differs from actual native SR relationship')
    families={'entry_rdc','cpd_reset','dqs_reset','iol_reset','training_reset'}
    for row in vendor:
        for key in ('FromCLK','LaunchQ','Endpoint'):exact_selector([row.get(key)])
        require(row.get('TargetKind')=='DDRPrimitiveReset'and row.get('Family')in families
            and row.get('GuardAccepted')is True,'reviewed typed DDR reset scope required')
        proof=row.get('GuardProof',{})
        require(proof.get('NativeVendorResetGraphPassed')is True and proof.get('CurrentReportCoverageVerified')is True
            and proof.get('HistoricalEndpointCountsInherited')is False,'current typed DDR reset graph/report proof missing')
        objects=row.get('NativeObjects',{});targets=objects.get('DestinationObjects')
        require(isinstance(targets,list)and len(targets)==1,'one exact typed DDR primitive reset target required')
        target=targets[0]
        require(isinstance(target,dict)and target.get('Endpoint')==row['Endpoint']
            and target.get('Cell')and target.get('Primitive')in ('V_FFASYN','V_CLKPD','V_DDC_E2','V_ISERDES_E2','V_OSERDES_E2')
            and target.get('Pin')in ('SR','RST','RST_TRAINING_N'),
            'DDR target must retain actual functional primitive reset port')
        require(isinstance(objects.get('SourceFFs'),list)and objects['SourceFFs']
            and len(objects.get('SourcePhysicalQ',[]))==len(objects.get('SourceCLKNet',[]))==1,
            'DDR reset source must retain actual physical FF Q/clock identities')
        classifier=importlib.import_module('prepare_camera_vga_reset_scope')
        require(classifier.classify({'Source':row['FromCLK'],'Endpoint':row['Endpoint'],
            'LaunchClock':row['LaunchClock'],'CaptureClock':row['CaptureClock']})==row['Family'],
            'current DDR reset source/target/clock family differs')
    rows=ordinary+canonical_vendor_resets(scope,vendor)+supplemental_startup_resets(scope)
    require(len({(r['FromCLK'],r['LaunchQ'],r['Endpoint'])for r in rows})==len(rows),'duplicate typed reset path')
    return rows


def reset_constraint_evidence(scope):
    canonical=reset_rows(scope)
    return {'OriginalOrdinaryRows':len(scope.get('ResetScopes',[])),
        'OriginalVendorRows':len(scope.get('VendorResetScopes',[])),
        'CanonicalNativeConstraints':len(canonical),
        'MultiCaptureConstraints':[{'FromCLK':r['FromCLK'],'LaunchQ':r['LaunchQ'],'Endpoint':r['Endpoint'],
            **r['ResetConstraintEvidence']}for r in canonical if 'ResetConstraintEvidence'in r],
        'AllOriginalRowsRemainCoverageObligations':True,'DifferentCaptureClocksDeclaredAliases':False}


def scope_plan(scope,require_ready=True):
    require(scope.get('Schema')==AUDIT_SCHEMA and scope.get('Target')==build.TARGET,'new fisheye audit required')
    if require_ready:
        require(scope.get('ProposalReady') is True and scope.get('Blockers')==[],'fisheye audit has unresolved blockers')
    require(all(scope.get(k) is False for k in ('ConstraintsApplied','TimingAccepted','HardwareReleaseAllowed')),
            'fisheye audit overclaims physical acceptance')
    relationships=scope.get('ForeignRelationships');rows=scope.get('DataScopes')
    require(isinstance(relationships,list) and isinstance(rows,list) and rows,'actual direct foreign-data scopes required')
    triples=[];seen=set()
    for row in rows:
        names=[row.get(k) for k in ('FromCLK','LaunchQ','Endpoint')]
        for name in names:exact_selector([name])
        require(names[0].endswith('/CLK') and not names[1].endswith('/CLK'),'actual launch clock/Q required')
        identity=tuple(names);require(identity not in seen,'duplicate native launch triple');seen.add(identity)
        budget=row.get('MaximumNS')
        require(type(budget) in (int,float) and math.isfinite(budget) and budget>0,'finite positive independently derived budget required')
        require(isinstance(row.get('Role'),str) and row['Role'] and not re.search(r'unknown|unclassified|unreviewed',row['Role'],re.I)
                and isinstance(row.get('BoundBasis'),str) and row['BoundBasis'],'reviewed crossing role and budget basis required')
        indexes=row.get('RelationshipIndexes')
        require(isinstance(indexes,list) and indexes and all(type(i) is int and 0<=i<len(relationships) for i in indexes)
                and indexes==sorted(set(indexes)),'exact relationship indexes required')
        objects=row.get('NativeObjects');macro=row.get('TargetKind')=='MacroFunctionalInput'
        expected_fields={'SourceFFs','DestinationFFs','SourcePhysicalQ','SourceCLKNet'}
        require(isinstance(objects,dict) and set(objects)==expected_fields|({'DestinationObjects'}if macro else set()),
                'complete actual native launch identities required')
        require(all(isinstance(objects[k],list)and objects[k]and all(isinstance(n,str)and n for n in objects[k])
            and objects[k]==sorted(set(objects[k]))for k in expected_fields-({'DestinationFFs'}if macro else set())),
            'sorted native identity inventories required')
        target=macro_destination(scope,row)if macro else None
        if macro:require(objects['DestinationFFs']==[],'native macro input target must not claim FF placement')
        require(len(objects['SourcePhysicalQ'])==len(objects['SourceCLKNet'])==1,'conflicting physical source slot/clock-net identities')
        for index in indexes:
            r=relationships[index]
            require(r.get('SourceNativeClockPin')==names[0] and r.get('SourceNativeOutputPin')==names[1]
                    and r.get('SourceFF') in objects['SourceFFs'] and
                    (r.get('TargetKind')=='MacroFunctionalInput'and r.get('DestinationObject')==target
                        and r.get('DestinationPin')=='WE'and r.get('DestinationClock')==row['DestinationDomain']
                        if macro else r.get('DestinationFF') in objects['DestinationFFs']),
                    'native launch row differs from its actual foreign relationship')
            require(names[2] in {b.get('Endpoint') for b in r.get('NativeBoundaries',[])},
                    'scope endpoint is not an actual mapped boundary')
            require(r.get('SourcePhysicalQ') in objects['SourcePhysicalQ']
                    and r.get('SourceNativeCLKNet') in objects['SourceCLKNet'],
                    'scope physical Q slot/CLK net differs from mapped relationship')
        require(set(objects['SourceFFs'])=={relationships[i]['SourceFF']for i in indexes}
            and (macro or set(objects['DestinationFFs'])=={relationships[i]['DestinationFF']for i in indexes}),
            'native FF identity inventory includes unrelated source or destination FFs')
        triples.append(row)
    groups=data_constraint_groups(scope);resets=reset_rows(scope);sync=synchronous_reset_rows(scope)
    pairsets=[{(r['LaunchQ'],r['Endpoint'])for r in part}for part in(rows,resets,sync)]
    require(all(not pairsets[i]&pairsets[j]for i in range(3)for j in range(i)),
        'data, ordinary reset and synchronous-reset function scopes overlap')
    selectors=selectors_for(rows+resets+sync,scope)
    return {'ExactLaunchTriples':triples,'NativeSelectors':selectors,
        'PreflightQueryBody':'\n'.join(q['Command'] for q in selectors)+'\n',
        'PreflightQueryBodies':['\n'.join(q['Command']for q in selectors[i:i+240])+'\n'
            for i in range(0,len(selectors),240)],
        'ActualDataScopeCount':len(triples),'ResetScopes':resets,'UserSynchronousResetScopes':sync,'ConstraintGroups':groups,
        'ConstraintsApplicable':False,'ExecutableFDCCommands':[],
        'RequiredBeforeApplication':['Native launch-Q-qualified max-delay and hold-scope capability proof',
            'Complete same-CLK companion-Q coverage or demonstrated through-Q isolation',
            'Independent native protocol/interstage and exact reset audit'],
        'TimingAccepted':False,'BitstreamAllowed':False,'HardwareReleaseAllowed':False}


def all_ten_pass(tables):
    require(set(tables)=={(c,k) for c in ('slow','fast') for k in timing.KINDS},'ten direct timing tables required')
    for key,rows in tables.items():
        require(rows,'empty direct timing table')
        for pair,row in rows.items():
            require(set(row)=={'WorstSlackNS','TotalNegativeSlackNS','FailingChecks','TotalChecks'},'unknown native timing summary fields')
            require(all(type(row[k]) in (int,float) and math.isfinite(row[k]) for k in ('WorstSlackNS','TotalNegativeSlackNS'))
                    and type(row['FailingChecks']) is int and type(row['TotalChecks']) is int
                    and row['TotalChecks']>0 and row['FailingChecks']==0 and row['WorstSlackNS']>=0
                    and row['TotalNegativeSlackNS']==0,'unresolved direct timing check: '+str((key,pair)))
    return {'STAAllTenPassed':True,'TimingTables':len(tables),'CandidateCountsInherited':False}


def summaries(path):
    with Path(path).open(encoding='gb18030',errors='strict') as stream:return timing.parse_summaries(stream)


def compare_final_summaries(first,second):
    a,clocks_a=summaries(first);b,clocks_b=summaries(second)
    all_ten_pass(a);all_ten_pass(b)
    require(a==b and clocks_a==clocks_b,'independent direct summaries/clocks differ')
    return {'STAAllTenPassed':True,'ClockAndSummaryIdentityPreserved':True,
            'ExceptionPathCoverageAccepted':False}



def static_helpers(watched,*paths):
    """Bind local source imports recursively, independently of importing callers."""
    pending=[Path(p).resolve() for p in paths];seen=set()
    while pending:
        path=pending.pop()
        if path in seen:continue
        seen.add(path);add(watched,path)
        tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        names=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):names.extend(n.name.split('.')[0] for n in node.names)
            elif isinstance(node,ast.ImportFrom):
                if node.module:names.append(node.module.split('.')[0])
                if node.module in (None,'tools'):names.extend(n.name.split('.')[0] for n in node.names)
        for name in names:
            source=SELF.parent/(name+'.py')
            if source.is_file():pending.append(source)
    return watched


def _bind_audit(path):
    path=Path(path).absolute();saved=read(path)
    audit=importlib.import_module('hdmi_camera_fisheye_fill8r3s3_audit')
    require(Path(audit.__file__).resolve()==SELF.with_name('hdmi_camera_fisheye_fill8r3s3_audit.py'),'fisheye audit provider location differs')
    require(callable(getattr(audit,'derive',None)),'fisheye audit producer is not complete')
    current,inputs=audit.derive(saved['BuildPlan']['Path'],saved['ExportReceipt']['Path'],saved['RouteReceipt']['Path'])
    current=json.loads(json.dumps(current))
    require({k:v for k,v in saved.items() if k!='InputSHA256'}=={k:v for k,v in current.items() if k!='InputSHA256'},
            'fisheye audit facts differ from full recomputation')
    require(set(saved['InputSHA256'])<=set(current['InputSHA256']) and
        all(current['InputSHA256'][p]==h for p,h in saved['InputSHA256'].items()),'saved fisheye audit closure missing or changed')
    watched={};merge(watched,inputs);merge(watched,saved['InputSHA256']);merge(watched,current['InputSHA256'])
    for module in (build,native,timing,audit):add(watched,module.__file__)
    add(watched,SELF);add(watched,path)
    return saved,watched


def bind_audit(path):return authority('scope-audit',path,_bind_audit)


def bind_reduction_review(path,scope,watched):
    provider=importlib.import_module('hdmi_camera_fisheye_fill8r3s3_warnings')
    require(Path(provider.__file__).resolve()==SELF.with_name('hdmi_camera_fisheye_fill8r3s3_warnings.py'),
            'direct reduction review provider location differs')
    def derive(p):
        value,inputs=provider.verify(p);inputs=dict(inputs)
        static_helpers(inputs,provider.__file__);return value,inputs
    value,inputs=authority('source-reductions',path,derive);merge(watched,inputs)
    require(value['BuildPlan']==scope['BuildPlan'] and value.get('SourceDiagnosticReviewPassed') is True,
            'source reduction review belongs to another direct build')
    return value


def application_commands(scope):
    proposal=scope_plan(scope);commands=[];selectors={q['Pattern']:q for q in proposal['NativeSelectors']}
    aliases=timing_endpoint_aliases(scope)
    grouped=data_execution_chunks(scope,proposal['ConstraintGroups'])
    for row in grouped or proposal['ExactLaunchTriples']:
        q=([exact_selector(row[k])for k in('FromCLKs','LaunchQs','Endpoints')]if grouped else
            [exact_selector(clock_variants(row,scope)),exact_selector([row['LaunchQ']]),exact_selector(endpoint_variants(row,aliases))])
        require(all(len(item['Pattern'])<=4096 for item in q),'bounded exact application selector required')
        selectors.update({item['Pattern']:item for item in q})
        route=' -from ['+q[0]['Command']+'] -through ['+q[1]['Command']+'] -to ['+q[2]['Command']+']'
        commands.extend(['set_max_delay -datapath_only'+route+' '+format(row['MaximumNS'],'.12g'),
                         'set_false_path -hold'+route])
    for row in proposal['ResetScopes']+proposal['UserSynchronousResetScopes']:
        queries=[exact_selector(clock_variants(row,scope)),exact_selector([row['LaunchQ']]),exact_selector(endpoint_variants(row,aliases))]
        selectors.update({q['Pattern']:q for q in queries})
        commands.append('set_false_path -from ['+queries[0]['Command']+'] -through ['+queries[1]['Command']+
            '] -to ['+queries[2]['Command']+']')
    return commands,list(selectors.values()),proposal['PreflightQueryBody']



def literal_query_selectors(body):
    """Only the canonical small literal query grammar can qualify fragments."""
    selectors=[]
    for line in body.splitlines():
        match=re.fullmatch(r'get_pins -hierarchical -regexp \{(\^\(.+\)\$)\}',line)
        require(match is not None,'preflight fragment contains a nonliteral or nonquery command')
        names=[re.sub(r'\\(.)',r'\1',part)for part in match[1][2:-2].split('|')]
        require(1<=len(names)<=70,'preflight fragments require a bounded literal native pin inventory')
        selector=exact_selector(names)
        require(len(selector['Pattern'])<=4096 and selector['Command']==line,
            'preflight fragment is not the bounded canonical literal native selector')
        selectors.append(selector)
    require(selectors and len(selectors)<=240 and body=='\n'.join(q['Command']for q in selectors)+'\n',
        'bounded complete canonical preflight fragment required')
    require(len({q['Pattern']for q in selectors})==len(selectors),'ambiguous repeated selector in native fragment')
    names=[n for q in selectors for n in q['Names']]
    require(len(names)==len(set(names)),'ambiguous repeated native name in one fragment')
    return selectors


def bind_preflight_fragments(scope,preflight,watched):
    preflights=[Path(p).resolve()for p in(preflight if isinstance(preflight,(list,tuple))else[preflight])]
    require(preflights and len(set(preflights))==len(preflights),'unique native preflight fragment receipts required')
    covered=set();bodies=[]
    for receipt_path in preflights:
        query,inputs=native.bind_receipt(receipt_path);merge(watched,inputs)
        require(query['Mode']=='query'and query['BuildPlanSHA256']==scope['BuildPlan']['SHA256']
            and query['SourceADF']==scope['SourceADF']['Path']and query['SourceADFSHA256']==scope['SourceADF']['SHA256'],
            'fisheye native preflight shard uses another source')
        body=Path(query['QueryBody']).read_text(encoding='ascii');selectors=literal_query_selectors(body)
        exact_names(selectors,(receipt_path.parent/'stdout.log').read_text(encoding='gb18030',errors='strict'))
        names={n for q in selectors for n in q['Names']}
        require(not covered&names,'duplicate native name across preflight fragments')
        covered.update(names);bodies.append(body)
    return preflights,covered,bodies


def preflight_qualification(scope,preflight,watched):
    proposal=scope_plan(scope);preflights,covered,bodies=bind_preflight_fragments(scope,preflight,watched)
    required={n for q in proposal['NativeSelectors']for n in q['Names']}
    require(required<=covered,'missing current native names in verified preflight fragments: '+str(sorted(required-covered)))
    identical=bodies==proposal['PreflightQueryBodies']
    return preflights,{'PreflightMode':'exact-current-query-bodies'if identical else'verified-native-name-fragments',
        'ExactCurrentQueryBodiesIdentical':identical,'RequiredNativeNames':sorted(required),
        'RequiredNativeObjectCount':len(required),'VerifiedNativeObjectCount':len(covered),
        'UnusedExploratoryNames':sorted(covered-required),'MissingNativeNames':[],
        'NativeSelectorGrammar':{'OnlyCanonicalEscapedLiterals':True,'MaximumPatternCharacters':4096,'MaximumLiteralNames':70},
        'ExploratoryNamesGrantConstraintAuthority':False}


def preflight_receipts(scope,preflight,watched):return preflight_qualification(scope,preflight,watched)[0]


def supplemental_query_bodies(scope,preflight):
    """Query only missing literal names; formal application rechecks all pieces."""
    watched={};_,covered,_=bind_preflight_fragments(scope,preflight,watched)
    required={n for body in candidate_query_bodies(scope)for q in literal_query_selectors(body)for n in q['Names']}
    names=sorted(required-covered);selectors=[exact_selector(part)for part in bounded_name_chunks(names)]
    return ['\n'.join(q['Command']for q in selectors[i:i+240])+'\n'for i in range(0,len(selectors),240)]


def application_recipe(audit_path,reduction_review,preflight,work,maximum=600,require_alias=False):
    work=build.work_path(work);require(type(maximum) is int and 60<=maximum<=600,'bounded60..600s fisheye application required')
    scope,watched=bind_audit(audit_path);commands,selectors,body=application_commands(scope)
    macro_review,startup_review,supplemental_inputs=supplemental_reviews(scope);merge(watched,supplemental_inputs)
    diagnostic=bind_reduction_review(reduction_review,scope,watched)
    preflights,preflight_review=preflight_qualification(scope,preflight,watched)
    plan=build.validate(scope['BuildPlan']['Path'])
    if require_alias:build.paths.validate_repo_alias(build.ROOT,plan['RepoAlias'])
    semantics=importlib.import_module('camera720_stats_delay_reset_apply')
    static_helpers(watched,SELF,build.__file__,native.__file__,semantics.__file__)
    add(watched,GUIDE,GUIDE_SHA);add(watched,Path('D:/anaconda3/python.exe'))
    require(not any(p.is_relative_to(work) for p in watched),'fisheye application output overlaps source evidence')
    source_receipt=read(diagnostic['SourceBuildReceipt']['Path'])
    value={'Schema':APPLICATION_SCHEMA,'Target':build.TARGET,'ScopeAudit':ref(audit_path),
        'ReductionReview':ref(reduction_review),'PreflightQuery':ref(preflights[0]),
        'PreflightQueries':[ref(p)for p in preflights],
        'PreflightMode':preflight_review['PreflightMode'],'PreflightQualification':preflight_review,
        **{k:scope[k] for k in ('BuildPlan','ExportReceipt','RouteReceipt','SourceADF','NativeNetlist','RouteDump')},
        'ExactLaunchTriples':scope['DataScopes'],'ExactResetTriples':reset_rows(scope),
        'ExactSynchronousResetTriples':synchronous_reset_rows(scope),
        'ResetConstraintCanonicalization':reset_constraint_evidence(scope),
        'QualifiedTimingEndpointAliases':timing_endpoint_aliases(scope),
        'SupplementalMacroWriteEnableReview':macro_review,
        'SupplementalVendorStartupReview':startup_review,
        'ConstraintGroups':data_constraint_groups(scope),'DataExecutionChunks':data_execution_chunks(scope),
        'NativeSelectors':selectors,'QueryBody':body,'ExactCommands':commands,
        'SourceDiagnosticBodies':sorted({native.diagnostic_body(row) for row in source_receipt['Diagnostics']}),
        'SourceDiagnosticsPreserved':source_receipt['Diagnostics'],'WorkDirectory':str(work),
        'RepoAlias':plan['RepoAlias'],'MaximumSeconds':maximum,'ExpectedStages':[],
        'CommandCapability':{'VendorGuide':ref(GUIDE),'Sections':['2.2.4.1','2.2.4.4'],
            'FromCLKThroughActualQToExactEndpoint':True,'ActualExceptionCoverageStillRequired':True,
            'ExactSamePhysicalCLKVariants':True,'ThroughQRemainsSingleton':not bool(scope.get('ConstraintGroups')),
            'ExactFunctionalQUnions':bool(scope.get('ConstraintGroups')),
            'CompleteNativeSupportMatrixRequired':bool(scope.get('ConstraintGroups')),'NoClockDomainScope':True},
        'ResetExceptionsApplied':bool(all_reset_rows(scope)),'ResetAcceptanceInherited':False,
        'HardwareAccessed':False,'BitstreamRequested':False,'HardwareReleaseAllowed':False,'TimingAccepted':False,
        'InputSHA256':{str(p):h for p,h in watched.items()}}
    w=build.paths.alias_path(build.ROOT,plan['RepoAlias'],work)
    value['Command']=[plan['Command'][0],'-file',w+'/stage.tcl','-work_dir',w,'-project_name',build.TARGET]
    return value,watched


def render_application(value):
    w=build.paths.alias_path(build.ROOT,value['RepoAlias'],Path(value['WorkDirectory']))
    return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
        'add_design {'+w+'/dummy.v}\nif {[info script] ne {}} {\n'
        '    mpnr -input {'+w+'/input.adf}\n    '+native.INIT+'\n'
        '    file copy {'+w+'/input.adf} {'+w+'/post-init.adf}\n'+value['QueryBody']+
        '\n'.join(value['ExactCommands'])+'\n    save_adif\n'
        '    file copy {'+w+'/input.adf} {'+w+'/saved-scope.adf}\n'
        '    .switch_db -route -input {'+w+'/input.adf} -output {'+w+'/route-dump.txt}\n'
        '    puts {'+MARKER+'}\n    flush stdout\n}\n')


def prepare_application(audit_path,reduction_review,preflight,work,maximum=600):
    work=build.work_path(work);require(not work.exists(),'fresh fisheye physical application directory required')
    value,_=application_recipe(audit_path,reduction_review,preflight,work,maximum,require_alias=True)
    work.mkdir();shutil.copyfile(value['SourceADF']['Path'],work/'input.adf')
    (work/'dummy.v').write_text(native.DUMMY,encoding='ascii',newline='\n')
    (work/'stage.tcl').write_text(render_application(value),encoding='ascii',newline='\n')
    value['PreparedUTC']=build.utc();build.write(work/'stage-plan.json',value);return work/'stage-plan.json'


def check_application(path,fresh=False,require_alias=False):
    path=Path(path).absolute();saved=read(path);work=build.work_path(path.parent)
    require(path.name=='stage-plan.json' and saved.get('Schema')==APPLICATION_SCHEMA,'fisheye physical stage plan required')
    current,watched=application_recipe(saved['ScopeAudit']['Path'],saved['ReductionReview']['Path'],
        [row['Path']for row in saved.get('PreflightQueries',[saved['PreflightQuery']])],work,saved['MaximumSeconds'],require_alias)
    require(set(saved)==set(current)|{'PreparedUTC'} and {k:v for k,v in saved.items() if k!='PreparedUTC'}==current,
            'fisheye physical application recipe differs')
    require((work/'stage.tcl').read_text(encoding='ascii')==render_application(current)
            and (work/'dummy.v').read_text(encoding='ascii')==native.DUMMY,'fisheye physical stage Tcl/dummy differs')
    if fresh:
        require({p.name for p in work.iterdir()}=={'stage-plan.json','stage.tcl','dummy.v','input.adf'}
            and sha(work/'input.adf')==current['SourceADF']['SHA256'],'fresh original direct ADF copy required')
    for name in ('stage-plan.json','stage.tcl','dummy.v'):add(watched,work/name)
    return saved,watched


def application_evidence(value,work):
    text=(work/'stdout.log').read_text(encoding='gb18030',errors='strict')
    expected=Counter(re.findall(r'get_pins -hierarchical -regexp \{([^{}]+)\}',
        value['QueryBody']+'\n'+'\n'.join(value['ExactCommands'])))
    selectors={q['Pattern']:q for q in value['NativeSelectors']};actual=Counter()
    for line in text.splitlines():
        m=MATCH.fullmatch(line)
        if not m or not m[2].startswith('get_pins '):continue
        require(m[1] in selectors,'unexpected application native selector')
        q=selectors[m[1]];names=m[4].split()
        require(m[2] in (q['Command'],q['Command'].replace('{'+q['Pattern']+'}',q['Pattern']))
            and int(m[3])==len(names)==len(set(names)) and set(names)=={'t:'+n for n in q['Names']},
            'application native selector identity differs')
        actual[m[1]]+=1
    require(actual==expected,'missing/extra application native selectors')
    require(build.events(text)==[] and text.splitlines().count(MARKER)==1,'unexpected fisheye application native events/marker')
    diagnostics=build.diagnostics(work)
    retained=native.retained_reductions(value['SourceDiagnosticsPreserved'],diagnostics,value['SourceDiagnosticBodies'])
    require(sha(value['SourceADF']['Path'])==sha(work/'post-init.adf')==value['SourceADF']['SHA256'],
            'fisheye application initialization mutated original ADF')
    final=ref(work/'input.adf')
    require(final['SHA256']==sha(work/'saved-scope.adf') and final['SHA256']!=value['SourceADF']['SHA256'],
            'direct scoped ADF save/readback differs')
    semantics=importlib.import_module('camera720_stats_delay_reset_apply')
    routes=semantics.compare_routes(value['RouteDump']['Path'],work/'route-dump.txt')
    require(routes['AllNETANNOTATEIdentical'] and routes['AllNonConstraintNonRouteSemanticTokensIdentical']
            and routes['CDBChanged'],'fisheye application changed routing/placement or saved no CDB constraints')
    return {'ResultADF':final,'ConstraintsApplied':True,'NativeQueriesVerified':True,'ActualSelectorOccurrences':dict(actual),
        'InitializationPreservedADF':True,'SavedADFReadbackMatches':True,'OriginalADFUnchanged':True,
        'RouteComparison':routes,'RoutesAndPlacementUnchanged':True,'Diagnostics':diagnostics,
        'RetainedReductionReview':retained,'DiagnosticsCleared':False,'Artifacts':native.artifacts(work)}


def execute_application(path):
    value,watched=check_application(path,fresh=True,require_alias=True);work=Path(value['WorkDirectory'])
    require(os.name=='nt','fisheye physical application requires Windows')
    result={**value,'StagePlanSHA256':sha(path),'StartedUTC':build.utc(),'EDAExecuted':False,'ExitCode':None,
        'TimedOut':False,'StoppedForUnexpectedStage':False,'ExecutionPassed':False}
    build.write(work/'execution-start.json',result);process=None;start=time.monotonic()
    try:
        with (work/'stdout.log').open('xb') as out,(work/'stderr.log').open('xb') as err:
            process=subprocess.Popen(value['Command'],cwd=work,stdout=out,stderr=err,shell=False,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));result.update(EDAExecuted=True,OwnedPID=process.pid)
            while process.poll() is None:
                remaining=value['MaximumSeconds']-(time.monotonic()-start)
                if remaining<=0:result['TimedOut']=True;break
                try:process.wait(timeout=min(2,remaining))
                except subprocess.TimeoutExpired:pass
                if build.events((work/'stdout.log').read_text(encoding='gb18030',errors='replace')):
                    result['StoppedForUnexpectedStage']=True;break
    except BaseException as error:result['Error']=type(error).__name__+': '+str(error)
    finally:
        result['Cleanup']=(build.cleanup.stop_owned_tree(process,work,'bounded exact fisheye physical application')
            if process is not None and process.poll() is None else {'Complete':True,'ParentExited':True})
        if process is not None:result['ExitCode']=process.poll()
    try:
        result.update(application_evidence(value,work));result['InputDrift']=native.drift(watched)
        result['ExecutionPassed']=(result['ExitCode']==0 and result['EDAExecuted'] is True and not result['TimedOut']
            and not result['StoppedForUnexpectedStage'] and not result.get('Error') and result['InputDrift']==[]
            and result['Cleanup']['Complete'] is True)
    except Exception as error:result['Error']=type(error).__name__+': '+str(error)
    result.update(FinishedUTC=build.utc(),ElapsedSeconds=round(time.monotonic()-start,3));build.write(work/'result.json',result)
    return result


def _bind_application(path):
    path=Path(path).absolute();saved=read(path);work=build.work_path(path.parent)
    plan,watched=check_application(work/'stage-plan.json')
    require(path.name=='result.json' and all(saved.get(k)==v for k,v in plan.items())
        and saved.get('StagePlanSHA256')==sha(work/'stage-plan.json') and saved.get('ExecutionPassed') is True
        and saved.get('EDAExecuted') is True and saved.get('ExitCode')==0 and saved.get('TimedOut') is False
        and saved.get('StoppedForUnexpectedStage') is False and not saved.get('Error') and saved.get('InputDrift')==[]
        and saved.get('Cleanup',{}).get('Complete') is True,'unclean fisheye physical application receipt')
    expected=application_evidence(plan,work)
    require(all(saved.get(k)==v for k,v in expected.items()),'fisheye physical application evidence changed')
    for name,h in expected['Artifacts'].items():add(watched,work/name,h)
    add(watched,path);return saved,watched


def bind_application(path):return authority('physical-application',path,_bind_application)


def prepare(audit_path,output):
    scope,watched=bind_audit(audit_path);value=scope_plan(scope)
    output=Path(output).absolute()
    require(output==output.resolve() and output.parent==build.WORK.resolve() and output.suffix=='.json'
            and output not in watched,'new canonical direct planning sidecar required')
    value={'Schema':SCHEMA,'Target':build.TARGET,'ScopeAudit':ref(audit_path),
        **{k:scope[k] for k in ('BuildPlan','ExportReceipt','RouteReceipt','SourceADF')},**value,
        'CPUOnly':True,'EDAExecuted':False,'HardwareAccessed':False,
        'InputSHA256':{str(p):h for p,h in watched.items()}}
    build.write(output,value);return output


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--audit',type=Path)
    p.add_argument('--output',type=Path);p.add_argument('--query-body',action='store_true')
    p.add_argument('--candidate-only',action='store_true',help='generate read-only literal queries without accepting an audit')
    p.add_argument('--reduction-review',type=Path);p.add_argument('--preflight-query',type=Path,action='append')
    p.add_argument('--work-dir',type=Path);p.add_argument('--maximum-seconds',type=int,default=600)
    p.add_argument('--execute',type=Path);p.add_argument('--verify-application',type=Path);a=p.parse_args()
    if a.verify_application:
        bind_application(a.verify_application);print('{"Verified":true,"HardwareAccessed":false}');return 0
    if a.execute:
        value=execute_application(a.execute)
        print(json.dumps({k:value.get(k) for k in ('ExecutionPassed','ElapsedSeconds','Error')}));return 0 if value['ExecutionPassed'] else 1
    require(a.audit is not None,'--audit required')
    if a.query_body:
        require(a.output is not None,'--output required')
        if a.candidate_only:
            digest=sha(a.audit);candidate=read(a.audit)
            bodies=(supplemental_query_bodies(candidate,a.preflight_query)if a.preflight_query
                else candidate_query_bodies(candidate))
            require(sha(a.audit)==digest,'candidate native object inventory changed during query generation')
        else:
            scope,_=bind_audit(a.audit);bodies=scope_plan(scope,require_ready=False)['PreflightQueryBodies']
        if not bodies:
            print(json.dumps({'QueryBodies':[],'CandidateOnly':True,'TimingAccepted':False,
                'HardwareReleaseAllowed':False,'RequiredNamesAlreadyObserved':True}));return 0
        if len(bodies)==1:
            with a.output.open('x',encoding='ascii',newline='\n')as out:out.write(bodies[0])
            paths=[a.output]
        else:
            a.output.mkdir(exist_ok=False);paths=[]
            for i,body in enumerate(bodies):
                path=a.output/f'preflight-{i:02}.tcl';path.write_text(body,encoding='ascii',newline='\n');paths.append(path)
        print(json.dumps({'QueryBodies':[str(path)for path in paths],'CandidateOnly':a.candidate_only,
            'TimingAccepted':False,'HardwareReleaseAllowed':False}));return 0
    require(not a.candidate_only,'--candidate-only is limited to --query-body')
    if a.work_dir:
        require(a.reduction_review is not None and a.preflight_query is not None,
                'formal --reduction-review and --preflight-query required')
        path=prepare_application(a.audit,a.reduction_review,a.preflight_query,a.work_dir,a.maximum_seconds)
        print(json.dumps({'Prepared':True,'StagePlan':str(path)}));return 0
    require(a.output is not None,'--output required')
    print(json.dumps({'PlanningOnly':True,'Output':str(prepare(a.audit,a.output)),'ConstraintsApplicable':False}));return 0


if __name__=='__main__':raise SystemExit(main())
