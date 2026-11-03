"""Recompute this fisheye application's final native physical evidence.

No bitstream or hardware operation exists here. Baseline source exceptions
remain exact; new CDC paths require actual launch-Q/physical-slot identities,
either complete reported pairs or the executed complete native support matrix,
per-corner group effect, all ten timing tables, and independent full route and
functional/placement equivalence. Report truncation remains explicit.
"""
import argparse
from collections import Counter
from decimal import Decimal,ROUND_DOWN
import hashlib
import json
from pathlib import Path
import re
import tempfile

import hdmi_camera_fisheye_tile8df8_build as build
import hdmi_camera_fisheye_tile8df8v3_scoped_native as baseline
import hdmi_camera_fisheye_tile8df8v3_physical as application
import hdmi_camera_fisheye_tile8df8v3_scoped_native as native
import hdmi_camera_fisheye_macro_consumers as macro_consumers

SELF=Path(__file__).resolve()
SCHEMA='hdmi-camera-fisheye-tile8df8v3-final-physical-proof-v1'
MAX_PATHS=10000
require,sha,read,write=build.require,build.sha,build.read,build.write
add,merge,ref=baseline.add,baseline.merge,baseline.ref
NUM=r'[-+]?\d+(?:\.\d+)?'


def exception_paths(path):
    """Stream strict-codepage native paths; retain exact normalized bodies."""
    sections={};kind=corner=None;block=None
    def finish():
        nonlocal block
        if block is None:return
        text=''.join(block)
        require(any(s.startswith(' Slack') for s in block),'truncated fisheye native exception path')
        def one(pattern):
            values=re.findall(pattern,text,re.M);require(len(values)==1,'incomplete fisheye native exception path')
            return values[0]
        record={'Source':one(r'^Startpoint\s*:\s*(\S+)\s*$'),
            'Endpoint':one(r'^Endpoint\s*:\s*(\S+)\s*$'),
            'Corner':one(r'^Path Type\s*:\s*(?:max|min) \((slow|fast) corner\)\s*$'),
            'Exception':one(r'^Timing Exception\s*:\s*(.+?)\s*$')}
        body='\n'.join(' '.join(s.split()) for s in block if s.strip() and not set(s.strip())<=set('-='))
        record['BodySHA256']=hashlib.sha256(body.encode('utf-8')).hexdigest()
        record['SlackMet']='Slack (MET)' in text
        endpoint_rows=re.findall(r'^\s+(\S+/(?:CE|RS|WE))\s+(?:'+NUM+r'\s+'+NUM+r'\s+)?[rf]\s+'
            +re.escape(record['Endpoint'])+r'\s*$',text,re.M)
        if endpoint_rows:
            require(len(endpoint_rows)==1,'ambiguous native physical timing-control endpoint')
            record['PhysicalTimingEndpoint']=endpoint_rows[0]
        clocks=re.findall(r'^\s+Clock\s+(\S+)\s+\((rising|falling) edge\)',text,re.M)
        if clocks:
            require(len(clocks)==2,'ambiguous native launch/capture clock context')
            record.update(LaunchClock=clocks[0][0],LaunchEdge=clocks[0][1],
                CaptureClock=clocks[1][0],CaptureEdge=clocks[1][1])
        launches=re.findall(r'^\s+(\S+)\s+tco\s+('+NUM+r')\s+('+NUM+r')\s+([rf])\s+(\S+)\s*$',text,re.M)
        if len(launches)==1:
            record.update(PhysicalQ=launches[0][0],LaunchOutput=launches[0][4],LaunchTransition=launches[0][3])
            clocks=re.findall(r'^\s+(\S+/CLK)\s+(?:'+NUM+r'\s+'+NUM+r'\s+)?[rf]\s+'
                +re.escape(record['Source'])+r'\s*$',text,re.M)
            if len(clocks)==1:record['PhysicalCLK']=clocks[0]
        require(record['Corner']==corner,'native exception path/section corner differs')
        sections[(corner,kind)].append(record);block=None
    with Path(path).open(encoding='gb18030',errors='strict') as stream:
        for line in stream:
            m=re.fullmatch(r'\| Exception type\s*:\s*(\S+)\s*\n?',line)
            if m:finish();kind=m[1];corner=None;continue
            m=re.fullmatch(r'\| (Slow|Fast) Corner\s*\n?',line)
            if m:
                finish();corner=m[1].lower()
                require(kind is not None and (corner,kind) not in sections,'duplicate direct exception section')
                sections[(corner,kind)]=[];continue
            if line.startswith('Startpoint'):
                finish();require(corner is not None,'direct exception outside section');block=[line]
            elif block is not None:
                block.append(line)
                if line.startswith(' Slack'):finish()
    finish()
    expected={(c,f'{s}({k})') for c in ('slow','fast') for s,kinds in
        (('set_max_delay',('setup','recovery')),('set_min_delay',('hold','removal')),
         ('set_multicycle_path',('setup','hold','recovery','removal')),
         ('set_false_path',('setup','hold','recovery','removal'))) for k in kinds}
    require(set(sections)==expected,'all24 direct exception sections required')
    for rows in sections.values():
        require(len({r['BodySHA256'] for r in rows})==len(rows),'literal duplicate native exception path')
    return sections


def actual_source_bindings(scope,sections):
    """Collect both expected and printed clock-parent site/net facts once."""
    cdc=application.importlib.import_module('camera720_calibrated_cdc')
    parents={name.rsplit('/',1)[0] for r in (scope['DataScopes']+application.all_reset_rows(scope))
        for name in application.clock_variants(r,scope)}
    relevant={(r['LaunchQ'],r['Endpoint']) for r in (scope['DataScopes']+application.all_reset_rows(scope))}
    target_aliases=application.timing_endpoint_index(scope)
    parents.update(r['Source'].rsplit('/',1)[0] for rows in sections.values() for r in rows
        if (r.get('LaunchOutput'),target_aliases.get(r['Endpoint'],{}).get('Endpoint',r['Endpoint'])) in relevant)
    source=Path(scope['RouteDump']['Path']);require(sha(source)==scope['RouteDump']['SHA256'],'baseline direct route changed')
    with tempfile.TemporaryDirectory(prefix='direct-final-native-clocks-') as temp:
        normalized=Path(temp)/'route.adif';cdc.normalize_source_locations(source,normalized)
        audit=application.importlib.import_module('hdmi_camera_fisheye_tile8df8_audit')
        route=audit.native_route(normalized,parents) if hasattr(audit,'native_route') else cdc.endpoints.route_objects(normalized,parents)
    placements={}
    pattern=(r'\(INSTANNOTATE\s+\(INSTREF\s+(\\\S+|[A-Za-z_$][\w$/\.\[\]-]*)\s*\)\s*'
        r'\(PLACE\s+(\S+)\s+\(DEVINSTREF\s+(\w+)\s+\(SITEREF\s+(\d+)\s+(\d+)\)\)\)\s*\)')
    for name,place,kind,x,y in re.findall(pattern,source.read_text(encoding='utf-8-sig')):
        name=name.lstrip('\\')
        if name not in parents:continue
        require(name not in placements,'duplicate native direct instance placement')
        placements[name]={'Site':kind+'_'+x+'_'+y,'Primitive':place}
    require(set(placements)==parents,'native direct clock-parent placement missing')
    return route,placements


def launch_identity(row,scope_row,route,placements,scope=None,target_aliases=None):
    target_aliases={}if target_aliases is None else target_aliases
    target=target_aliases.get(row['Endpoint'])
    require(row.get('LaunchOutput')==scope_row['LaunchQ']
        and (target['Endpoint']if target else row['Endpoint'])==scope_row['Endpoint'],
            'actual direct launch Q/endpoint not in exact scope')
    if target:
        require(row.get('PhysicalTimingEndpoint')==target['PhysicalTimingPin'],
            'reported control timing alias changed its exact physical endpoint')
    expected_q=scope_row['NativeObjects']['SourcePhysicalQ']
    require(len(expected_q)==1 and row.get('PhysicalQ')==expected_q[0],'fisheye physical Q slot differs')
    site=expected_q[0].rsplit('/',1)[0]
    require(row.get('PhysicalCLK')==site+'/CLK','fisheye source physical clock/Q sites differ')
    printed=row['Source'].rsplit('/',1)[0];expected=scope_row['FromCLK'].rsplit('/',1)[0]
    if 'FromCLKVariants'in scope_row:
        require(row['Source']in application.clock_variants(scope_row,scope),'reported source clock is outside exact native CLK aliases')
    require(row['Source'].endswith('/CLK') and placements.get(printed,{}).get('Site')==site
            and placements.get(expected,{}).get('Site')==site,'direct packed clock aliases lack same-site evidence')
    nets=scope_row['NativeObjects']['SourceCLKNet']
    for alias in application.clock_variants(scope_row,scope):
        name=alias.rsplit('/',1)[0]
        require(placements.get(name,{}).get('Site')==site and route['Pins'].get((name,'CLK'))==nets[0],
            'exact CLK alias differs from independently parsed native site/net')
    require(len(nets)==1 and route['Pins'].get((printed,'CLK'))==route['Pins'].get((expected,'CLK'))==nets[0],
            'direct packed clock aliases lack exact same native CLK net')
    return row['Source']!=scope_row['FromCLK']


def validate_exceptions(scope,original_path,current_path,applied=None):
    before=exception_paths(original_path);now=exception_paths(current_path)
    target_aliases=application.timing_endpoint_index(scope)
    if target_aliases:
        require(isinstance(applied,dict)and applied.get('ConstraintsApplied')is True
            and applied.get('NativeQueriesVerified')is True and applied.get('RoutesAndPlacementUnchanged')is True
            and applied.get('QualifiedTimingEndpointAliases')==application.timing_endpoint_aliases(scope)
            and applied.get('ExactCommands')==application.application_commands(scope)[0],
            'every distinct valid STA endpoint arc needs its executed exact finite alias selector')
    groups=application.data_constraint_groups(scope)
    if groups:
        require(isinstance(applied,dict)and applied.get('ConstraintsApplied')is True
            and applied.get('NativeQueriesVerified')is True and applied.get('RoutesAndPlacementUnchanged')is True
            and applied.get('ConstraintGroups')==groups
            and applied.get('DataExecutionChunks')==application.data_execution_chunks(scope,groups)
            and applied.get('ExactCommands')==application.application_commands(scope)[0],
            'complete matrix coverage requires the verified executed native collection constraints')
    pair_group={(p['LaunchQ'],p['Endpoint']):i for i,g in enumerate(groups)for p in g['AllowedPairs']}
    route,placements=actual_source_bindings(scope,now)
    lookup=application.canonical_scope_lookup(scope,scope['DataScopes'])
    resets={(r['LaunchQ'],r['Endpoint']):r for r in application.reset_rows(scope)}
    require(len(resets)==len(application.reset_rows(scope)),'ambiguous guarded direct reset launch/endpoint scope')
    reset_evidence=application.reset_constraint_evidence(scope)
    if reset_evidence['MultiCaptureConstraints']:
        require(isinstance(applied,dict)and applied.get('ConstraintsApplied')is True
            and applied.get('NativeQueriesVerified')is True and applied.get('RoutesAndPlacementUnchanged')is True
            and applied.get('ResetConstraintCanonicalization')==reset_evidence
            and applied.get('ExactCommands')==application.application_commands(scope)[0],
            'all original typed reset contexts require the verified identical executed native pin constraints')
    synchronous=application.canonical_scope_lookup(scope,application.synchronous_reset_rows(scope))
    require(not(set(lookup)&set(synchronous)or set(resets)&set(synchronous)),
        'synchronous reset function overlaps data or SR reset exception')
    coverage={};aliases=set();enumerated=True;reset_contexts={};observed_target_aliases=set()
    for key,rows in now.items():
        original=Counter(r['BodySHA256'] for r in before[key]);current=Counter(r['BodySHA256'] for r in rows)
        require(not original-current,'baseline vendor exception path changed/disappeared')
        remaining=original.copy();added=[]
        for row in rows:
            if remaining[row['BodySHA256']]>0:remaining[row['BodySHA256']]-=1
            else:added.append(row)
        corner,kind=key;seen=set();transitions={}
        for row in added:
            target=target_aliases.get(row['Endpoint'])
            identity=(row.get('LaunchOutput'),target['Endpoint']if target else row['Endpoint'])
            reset_kind=kind in ('set_false_path(recovery)','set_false_path(removal)')
            selected=(resets if reset_kind else synchronous if kind=='set_false_path(setup)'else
                {**lookup,**synchronous}if kind=='set_false_path(hold)'else lookup)
            require(identity in selected,'unrequested direct exception path/companion Q')
            expected=selected[identity]
            if launch_identity(row,expected,route,placements,scope,target_aliases):aliases.add((row['Source'],expected['FromCLK']))
            if target:observed_target_aliases.add(row['Endpoint'])
            if kind=='set_max_delay(setup)':
                match=re.fullmatch(r'MaxDelay Path ([0-9.]+)ns -datapath_only',row['Exception'])
                # PDS prints picosecond precision by truncating the selected ns budget.
                budget=Decimal(str(expected['MaximumNS'])).quantize(Decimal('.001'),rounding=ROUND_DOWN)
                require(match is not None and Decimal(match[1])==budget and row['SlackMet'],
                        'direct maximum-delay value/slack differs')
            elif kind in('set_false_path(hold)','set_false_path(setup)'):
                require(row['Exception']=='False Path','unexpected data hold/synchronous-reset-function exception')
            elif reset_kind:
                require(row['Exception']=='False Path','unexpected guarded direct reset exception')
                contexts=expected.get('CaptureClocks',[expected.get('CaptureClock')])
                if contexts!=[None]:
                    require(row.get('CaptureClock')in contexts and row.get('LaunchClock')==expected.get('LaunchClock'),
                        'reported typed reset has an unreviewed launch/capture clock context')
                    reset_contexts.setdefault(corner+'_'+kind,set()).add((identity[0],identity[1],row['CaptureClock']))
            else:require(False,'new unapproved direct exception type: '+kind)
            seen.add(identity);transitions.setdefault(identity,set()).add(row['LaunchTransition'])
        expected=(set(lookup)if kind=='set_max_delay(setup)'else set(lookup)|set(synchronous)if kind=='set_false_path(hold)'else
                  set(synchronous)if kind=='set_false_path(setup)'else
                  set(resets) if kind in ('set_false_path(recovery)','set_false_path(removal)') else set())
        data_kind=kind in ('set_max_delay(setup)','set_false_path(hold)')
        observed_groups=sorted({pair_group[p]for p in seen if p in pair_group})if groups and data_kind else []
        if groups and data_kind:
            require(seen<=expected and observed_groups==list(range(len(groups))),
                'missing two-corner actual exception evidence for a native constraint group: '+str((corner,kind)))
            if kind=='set_false_path(hold)':require(set(synchronous)<=seen,'synchronous-reset function hold coverage missing')
        else:
            require(seen==expected,'missing direct exception launch/endpoint coverage: '+str((corner,kind,len(seen),len(expected))))
        enumerated=enumerated and seen==expected
        # PDS's nworst variants need not differ in launch transition: this
        # candidate's two hold paths both launch rising Q and differ later in
        # the path. Require every actual launch/endpoint identity; retain all
        # reported variants and compare them exactly in the fresh-process gate.
        coverage[corner+'_'+kind]={'BaselinePaths':len(before[key]),'AddedPaths':len(added),'ActualLaunchPairs':len(seen),
            'ExpectedNativePairs':len(expected),'ObservedConstraintGroups':observed_groups,
            'ReportedPairEnumerationComplete':seen==expected,
            'ReportedLaunchTransitions':{json.dumps(k):sorted(v) for k,v in sorted(transitions.items())},
            'AllPossibleLaunchTransitionsEnumerated':False}
    return {'Complete':True,'PerSection':coverage,'ClockAliasesVerified':len(aliases),
        'AllVendorExceptionsPreserved':True,'AllActualLaunchPairsCovered':enumerated,
        'ReportedEnumerationComplete':enumerated,'MatrixConstraintCoverageComplete':bool(groups),
        'MatrixConstraintGroups':len(groups),'MatrixNativePairs':len(lookup)if groups else 0,
        'OriginalFunctionalDataScopeObligations':len(scope['DataScopes']),
        'OriginalFunctionalSynchronousResetObligations':len(application.synchronous_reset_rows(scope)),
        'EquivalentRAMWEFunctionalObligationsVerifiedBeforeProjection':True,
        'SynchronousResetFunctions':len(synchronous),'SynchronousResetSetupHoldCoverageComplete':True,
        'ResetConstraintCanonicalization':reset_evidence,
        'OriginalVendorResetCaptureContextObligations':len(scope.get('VendorResetScopes',[])),
        'ReportedVendorResetCaptureContexts':{k:[list(v)for v in sorted(values)]for k,values in sorted(reset_contexts.items())},
        'ResetCaptureContextConstraintCoverageComplete':True,
        'ResetCaptureContextCoverageBasis':'individually_verified_original_contexts_and_identical_unqualified_executed_pin_constraints',
        'DifferentInternalCaptureClocksDeclaredAliases':False,
        'QualifiedTimingEndpointAliases':application.timing_endpoint_aliases(scope),
        'ReportedTimingEndpointAliases':sorted(observed_target_aliases),
        'TimingEndpointAliasEnumerationComplete':observed_target_aliases==set(target_aliases),
        'AllFiniteQualifiedTimingEndpointArcsExplicitlyConstrained':True,
        'CoverageBasis':('complete_native_support_matrix_and_executed_exact_collection_constraints'if groups
            else'complete_reported_native_launch_endpoint_pairs'),
        'CompanionQLeakage':False}


def compare_fresh_sta(proof,report,exceptions):
    result=application.compare_final_summaries(proof['FreshSTAReport']['Path'],report)
    require(result.get('STAAllTenPassed')is True and result.get('ClockAndSummaryIdentityPreserved')is True,
        'fresh fisheye summaries/clocks are not accepted')
    require(exception_paths(proof['FreshSTAExceptions']['Path'])==exception_paths(exceptions),
            'fresh direct complete native exception paths changed')
    return {key:True for key in ('STAAllTenPassed','ClockAndSummaryIdentityPreserved','AllExceptionPathsPreserved')}


def native_acceptance(scope):
    """Require explicit native evidence; proposal readiness alone grants nothing."""
    acceptance=scope.get('NativeAcceptance',{})
    require(all(acceptance.get(k) is True for k in ('ResetAccepted',
        'ProtocolSafetyAccepted','SourceSamplingIsolatedVerified')) and acceptance.get('Missing')==[]
        and acceptance.get('Violations')==[],'complete explicit fisheye native reset/protocol/PHY/IO acceptance required')
    return acceptance



def pipeline_evidence(scope):
    consumer_review=macro_consumers.review(scope)
    require(consumer_review['Passed']and consumer_review['Missing']==[]and consumer_review['Violations']==[],
        'actual arithmetic/memory output domain differs from its user FF consumer')
    """Bind the actual new native partitions and the independently rebuilt C profile."""
    acceptance=scope.get('NativeAcceptance',{})
    required=('VendorDDRClockResetAccepted','FrameBoundaryViewSelectionAccepted','FisheyeProfileAccepted','UserCDCAccepted')
    require(all(acceptance.get(k)is True for k in required),'complete current fisheye/DDR/view/CDC partition proof required')
    clock=scope.get('NativeClockReview',{}).get('CoreClock',{})
    require(clock.get('Domain')=='ddrphy_sysclk'and type(clock.get('FrequencyHz'))is int
        and clock['FrequencyHz']==125000000 and clock.get('PeriodNS')==8.0
        and clock.get('CurrentGeneratedClockVerified')is True and clock.get('PLLParametersVerified')is True
        and clock.get('ConstrainedCoreMHz')==125 and clock.get('InputParameterMetadataMHz')==50
        and clock.get('PhysicalFrequencyMeasured')is False
        and clock.get('FrequencyBasis')=='current_constraint_and_native_1_to_1_clock_trace'
        and type(clock.get('NativeRatioNumerator'))is int and clock['NativeRatioNumerator']>0
        and clock.get('NativeRatioDenominator')==clock['NativeRatioNumerator']
        and clock.get('NativeRoot')and isinstance(clock.get('Trace'),list)and clock['Trace'],
        'current125MHz constraint and1:1native PLL trace metadata required; physical frequency is separately measured')
    partitions=scope.get('SourcePartitions')
    require(isinstance(partitions,dict)and partitions.get('NativeEvidenceComplete')is True
        and partitions.get('SourceBytesAloneClaimNativeSafety')is False and partitions.get('Missing')==[]
        and partitions.get('Violations')==[],'actual source/native partition inventory incomplete')
    plan=build.validate(scope['BuildPlan']['Path']);profile,inputs=build.fisheye_profile_binding()
    require(plan['FisheyeProfile']==profile,'current C fisheye profile differs from compiled plan')
    return {**{k:True for k in required},'SourcePartitions':partitions,'FisheyeProfile':profile,'FPSClockBasis':clock,
        'NativeMacroUserConsumerReview':consumer_review},inputs


def final_facts(application_path,export_path,route_path,query_paths):
    application_path,export_path,route_path=[Path(p).resolve() for p in (application_path,export_path,route_path)]
    query_paths=[Path(p).resolve() for p in query_paths]
    app,watched=application.bind_application(application_path)
    scope,inputs=application.bind_audit(app['ScopeAudit']['Path']);merge(watched,inputs)
    macro_review,startup_review,inputs=application.supplemental_reviews(scope);merge(watched,inputs)
    acceptance=native_acceptance(scope)
    evidence,profile_inputs=pipeline_evidence(scope);merge(watched,profile_inputs)
    exported,inputs=native.bind_receipt(export_path);merge(watched,inputs)
    routed,inputs=native.bind_receipt(route_path);merge(watched,inputs)
    for value,mode in ((exported,'export'),(routed,'report')):
        require(value['Mode']==mode and value['SourceProof']==ref(application_path)
            and value['SourceADF']==app['ResultADF']['Path'] and value['SourceADFSHA256']==app['ResultADF']['SHA256'] and value['BuildPlanSHA256']==app['BuildPlan']['SHA256'],
            'final fisheye native evidence identifies another application')
    checks=application.importlib.import_module('hdmi_camera_fisheye_tile8df8v3_physical_checks')
    require(Path(checks.__file__).resolve()==build.ROOT/'tools'/'hdmi_camera_fisheye_tile8df8v3_physical_checks.py',
        'fisheye final native query-check provider location differs')
    for path in query_paths:
        value,inputs=checks.bind_query_receipt(path);merge(watched,inputs)
        require(value['Mode']=='query' and value['SourceProof']==ref(application_path)
            and value['SourceADF']==app['ResultADF']['Path'] and value['SourceADFSHA256']==app['ResultADF']['SHA256']
            and value['BuildPlanSHA256']==app['BuildPlan']['SHA256'],'fisheye final query uses another source')
    audit=application.importlib.import_module('hdmi_camera_fisheye_tile8df8_audit')
    net=baseline.artifact(export_path,exported,build.TARGET+'_sim.v')
    before=Path(app['NativeNetlist']['Path']).read_text(encoding='utf-8-sig');after=net.read_text(encoding='utf-8-sig')
    build_dir=Path(app['BuildPlan']['Path']).parent
    require(audit.graph(before,build_dir).g==audit.graph(after,build_dir).g,
            'direct functional graph/declarations/FF placement changed')
    # Route comparison also covers all LUT/FF/macros' physical annotations and every net tree.
    dump=baseline.artifact(route_path,routed,'route-dump.txt')
    semantics=application.importlib.import_module('camera720_stats_delay_reset_apply')
    routes=semantics.compare_routes(app['RouteDump']['Path'],dump)
    require(routes['AllNETANNOTATEIdentical'] and routes['AllNonConstraintNonRouteSemanticTokensIdentical'],
            'fisheye final routes/placements changed')
    report=baseline.artifact(export_path,exported,build.TARGET+'.rtr')
    exceptions=baseline.artifact(export_path,exported,build.TARGET+'_exception.rtr')
    application.compare_final_summaries(report,baseline.artifact(route_path,routed,build.TARGET+'.rtr'))
    original,inputs=baseline.bind_receipt(app['ExportReceipt']['Path']);merge(watched,inputs)
    old_exceptions=baseline.artifact(app['ExportReceipt']['Path'],original,build.TARGET+'_exception.rtr')
    coverage=validate_exceptions(scope,old_exceptions,exceptions,app)
    # Detailed IO/interstage and native warning interpretation is a separate
    # completed producer, not a caller-supplied collection of true booleans.
    checks=application.importlib.import_module('hdmi_camera_fisheye_tile8df8v3_physical_checks')
    require(Path(checks.__file__).resolve()==SELF.with_name('hdmi_camera_fisheye_tile8df8v3_physical_checks.py'),
            'fisheye final native-check provider location differs')
    checked,inputs=checks.derive(scope,application_path,export_path,route_path,query_paths);merge(watched,inputs)
    require(all(checked.get(k) is True for k in ('Passed','NativeWarningsReviewed','ResetAccepted','InterstageTimingAccepted')),
            'fisheye final native checks incomplete')
    diagnostic=application.bind_reduction_review(app['ReductionReview']['Path'],scope,watched)
    source_warnings=application.importlib.import_module('hdmi_camera_fisheye_tile8df8_warnings')
    require(Path(source_warnings.__file__).resolve()==SELF.with_name('hdmi_camera_fisheye_tile8df8_warnings.py'),
        'fisheye source-warning provider location differs')
    source_review,inputs=source_warnings.derive(app['BuildPlan']['Path']);merge(watched,inputs)
    require(source_review['Passed'] is True,'source warning review incomplete')
    application.static_helpers(watched,SELF,checks.__file__,semantics.__file__,source_warnings.__file__)
    for path in (net,dump,report,exceptions):add(watched,path)
    result={'Schema':SCHEMA,'Target':build.TARGET,'Passed':True,'BuildPlan':app['BuildPlan'],
        'Application':ref(application_path),'FinalADF':app['ResultADF'],'FinalExport':ref(export_path),
        'FinalRoute':ref(route_path),'FinalQueries':[ref(p) for p in query_paths],
        'ReductionReview':app['ReductionReview'],'SourceDiagnosticReviewPassed':diagnostic['SourceDiagnosticReviewPassed'],
        'SourceWarningReview':source_review,
        'FreshSTAReport':ref(report),'FreshSTAExceptions':ref(exceptions),'NativeMaxPaths':MAX_PATHS,
        'STAAllTenPassed':True,'NetlistEquivalent':True,'AllFFPlacementsEquivalent':True,'RoutesUnchanged':True,
        'ResetAccepted':True,'SourceSamplingIsolatedVerified':True,'NativeWarningsReviewed':True,
        'NativeAcceptance':acceptance,'ExceptionCoverage':coverage,'RouteComparison':routes,**checked,**evidence,
        'ViewSelection':scope.get('ViewSelection',{}),'VendorResetReview':scope.get('VendorResetReview',{}),
        'SupplementalMacroWriteEnableReview':macro_review,'SupplementalVendorStartupReview':startup_review,
        'HardwareAccessed':False,'HardwareReleaseAllowed':False,'ExternalACAccepted':False,'RGBPixelsVerified':False,
        'InputSHA256':{str(p):h for p,h in watched.items()}}
    require(not baseline.drift(watched),'fisheye final physical input drift');return result,watched


def verify(path):
    path=Path(path).absolute();saved=read(path)
    require(saved.get('Schema')==SCHEMA and saved.get('Target')==build.TARGET,'current fisheye final proof required')
    current,watched=final_facts(saved['Application']['Path'],saved['FinalExport']['Path'],saved['FinalRoute']['Path'],
        [row['Path'] for row in saved['FinalQueries']])
    require(json.loads(json.dumps(current))==saved,'fisheye final proof differs from complete recomputation')
    add(watched,path);return saved,watched


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--application',type=Path)
    p.add_argument('--export-receipt',type=Path);p.add_argument('--route-receipt',type=Path)
    p.add_argument('--query-receipt',action='append',type=Path,default=[]);p.add_argument('--output',type=Path)
    p.add_argument('--verify',type=Path);a=p.parse_args()
    if a.verify:verify(a.verify);print('{"Verified":true}');return 0
    require(a.application and a.export_receipt and a.route_receipt and a.output,'complete final proof inputs required')
    value,_=final_facts(a.application,a.export_receipt,a.route_receipt,a.query_receipt);write(a.output,value)
    print(json.dumps({'Passed':True,'Proof':str(a.output)}));return 0


if __name__=='__main__':raise SystemExit(main())
