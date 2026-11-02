"""Recompute this direct application's final native physical evidence.

No bitstream or hardware operation exists here. Baseline vendor DDR exceptions
remain exact; new CDC paths require actual launch-Q/physical-slot identities,
complete per-corner coverage, all ten timing tables and independent full route
and functional/placement equivalence. Unimplemented protocol/reset acceptance
is an explicit rejection, never an inherited old-candidate count.
"""
import argparse
from collections import Counter
from decimal import Decimal,ROUND_DOWN
import hashlib
import json
from pathlib import Path
import re
import tempfile

import hdmi_camera_direct_build as build
import hdmi_camera_direct_native as baseline
import hdmi_camera_direct_physical as application
import hdmi_camera_direct_native as native

SELF=Path(__file__).resolve()
SCHEMA='hdmi-camera-direct-final-physical-proof-v1'
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
        require(any(s.startswith(' Slack') for s in block),'truncated direct native exception path')
        def one(pattern):
            values=re.findall(pattern,text,re.M);require(len(values)==1,'incomplete direct native exception path')
            return values[0]
        record={'Source':one(r'^Startpoint\s*:\s*(\S+)\s*$'),
            'Endpoint':one(r'^Endpoint\s*:\s*(\S+)\s*$'),
            'Corner':one(r'^Path Type\s*:\s*(?:max|min) \((slow|fast) corner\)\s*$'),
            'Exception':one(r'^Timing Exception\s*:\s*(.+?)\s*$')}
        body='\n'.join(' '.join(s.split()) for s in block if s.strip() and not set(s.strip())<=set('-='))
        record['BodySHA256']=hashlib.sha256(body.encode('utf-8')).hexdigest()
        record['SlackMet']='Slack (MET)' in text
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
    parents={r['FromCLK'].rsplit('/',1)[0] for r in (scope['DataScopes']+scope['ResetScopes'])}
    relevant={(r['LaunchQ'],r['Endpoint']) for r in (scope['DataScopes']+scope['ResetScopes'])}
    parents.update(r['Source'].rsplit('/',1)[0] for rows in sections.values() for r in rows
        if (r.get('LaunchOutput'),r['Endpoint']) in relevant)
    source=Path(scope['RouteDump']['Path']);require(sha(source)==scope['RouteDump']['SHA256'],'baseline direct route changed')
    with tempfile.TemporaryDirectory(prefix='direct-final-native-clocks-') as temp:
        normalized=Path(temp)/'route.adif';cdc.normalize_source_locations(source,normalized)
        audit=application.importlib.import_module('hdmi_camera_direct_audit')
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


def launch_identity(row,scope_row,route,placements):
    require(row.get('LaunchOutput')==scope_row['LaunchQ'] and row['Endpoint']==scope_row['Endpoint'],
            'actual direct launch Q/endpoint not in exact scope')
    expected_q=scope_row['NativeObjects']['SourcePhysicalQ']
    require(len(expected_q)==1 and row.get('PhysicalQ')==expected_q[0],'direct physical Q slot differs')
    site=expected_q[0].rsplit('/',1)[0]
    require(row.get('PhysicalCLK')==site+'/CLK','direct source physical clock/Q sites differ')
    printed=row['Source'].rsplit('/',1)[0];expected=scope_row['FromCLK'].rsplit('/',1)[0]
    require(row['Source'].endswith('/CLK') and placements.get(printed,{}).get('Site')==site
            and placements.get(expected,{}).get('Site')==site,'direct packed clock aliases lack same-site evidence')
    nets=scope_row['NativeObjects']['SourceCLKNet']
    require(len(nets)==1 and route['Pins'].get((printed,'CLK'))==route['Pins'].get((expected,'CLK'))==nets[0],
            'direct packed clock aliases lack exact same native CLK net')
    return row['Source']!=scope_row['FromCLK']


def validate_exceptions(scope,original_path,current_path):
    before=exception_paths(original_path);now=exception_paths(current_path)
    route,placements=actual_source_bindings(scope,now)
    lookup={(r['LaunchQ'],r['Endpoint']):r for r in scope['DataScopes']}
    require(len(lookup)==len(scope['DataScopes']),'ambiguous direct launch/endpoint budgets')
    resets={(r['LaunchQ'],r['Endpoint']):r for r in scope['ResetScopes']}
    require(len(resets)==len(scope['ResetScopes']),'ambiguous guarded direct reset launch/endpoint scope')
    coverage={};aliases=set()
    for key,rows in now.items():
        original=Counter(r['BodySHA256'] for r in before[key]);current=Counter(r['BodySHA256'] for r in rows)
        require(not original-current,'baseline vendor exception path changed/disappeared')
        remaining=original.copy();added=[]
        for row in rows:
            if remaining[row['BodySHA256']]>0:remaining[row['BodySHA256']]-=1
            else:added.append(row)
        corner,kind=key;seen=set();transitions={}
        for row in added:
            identity=(row.get('LaunchOutput'),row['Endpoint'])
            reset_kind=kind in ('set_false_path(recovery)','set_false_path(removal)')
            selected=resets if reset_kind else lookup
            require(identity in selected,'unrequested direct exception path/companion Q')
            expected=selected[identity]
            if launch_identity(row,expected,route,placements):aliases.add((row['Source'],expected['FromCLK']))
            if kind=='set_max_delay(setup)':
                match=re.fullmatch(r'MaxDelay Path ([0-9.]+)ns -datapath_only',row['Exception'])
                # PDS prints picosecond precision by truncating the selected ns budget.
                budget=Decimal(str(expected['MaximumNS'])).quantize(Decimal('.001'),rounding=ROUND_DOWN)
                require(match is not None and Decimal(match[1])==budget and row['SlackMet'],
                        'direct maximum-delay value/slack differs')
            elif kind=='set_false_path(hold)':require(row['Exception']=='False Path','unexpected direct hold exception')
            elif reset_kind:require(row['Exception']=='False Path','unexpected guarded direct reset exception')
            else:require(False,'new unapproved direct exception type: '+kind)
            seen.add(identity);transitions.setdefault(identity,set()).add(row['LaunchTransition'])
        expected=(set(lookup) if kind in ('set_max_delay(setup)','set_false_path(hold)') else
                  set(resets) if kind in ('set_false_path(recovery)','set_false_path(removal)') else set())
        require(seen==expected,'missing direct exception launch/endpoint coverage: '+str((corner,kind,len(seen),len(expected))))
        # PDS's nworst variants need not differ in launch transition: this
        # candidate's two hold paths both launch rising Q and differ later in
        # the path. Require every actual launch/endpoint identity; retain all
        # reported variants and compare them exactly in the fresh-process gate.
        coverage[corner+'_'+kind]={'BaselinePaths':len(before[key]),'AddedPaths':len(added),'ActualLaunchPairs':len(seen),
            'ReportedLaunchTransitions':{json.dumps(k):sorted(v) for k,v in sorted(transitions.items())},
            'AllPossibleLaunchTransitionsEnumerated':False}
    return {'Complete':True,'PerSection':coverage,'ClockAliasesVerified':len(aliases),
        'AllVendorExceptionsPreserved':True,'AllActualLaunchPairsCovered':True,'CompanionQLeakage':False}


def compare_fresh_sta(proof,report,exceptions):
    result=application.compare_final_summaries(proof['FreshSTAReport']['Path'],report)
    require(exception_paths(proof['FreshSTAExceptions']['Path'])==exception_paths(exceptions),
            'fresh direct complete native exception paths changed')
    return {**result,'AllExceptionPathsPreserved':True}


def native_acceptance(scope):
    """Require explicit native evidence; proposal readiness alone grants nothing."""
    acceptance=scope.get('NativeAcceptance',{})
    require(all(acceptance.get(k) is True for k in ('ResetAccepted',
        'ProtocolSafetyAccepted','SourceSamplingIsolatedVerified')) and acceptance.get('Missing')==[]
        and acceptance.get('Violations')==[],'complete explicit direct native reset/protocol/PHY/IO acceptance required')
    return acceptance


def final_facts(application_path,export_path,route_path,query_paths):
    application_path,export_path,route_path=[Path(p).resolve() for p in (application_path,export_path,route_path)]
    query_paths=[Path(p).resolve() for p in query_paths]
    app,watched=application.bind_application(application_path)
    scope,inputs=application.bind_audit(app['ScopeAudit']['Path']);merge(watched,inputs)
    acceptance=native_acceptance(scope)
    exported,inputs=native.bind_receipt(export_path);merge(watched,inputs)
    routed,inputs=native.bind_receipt(route_path);merge(watched,inputs)
    for value,mode in ((exported,'export'),(routed,'report')):
        require(value['Mode']==mode and value['SourceProof']==ref(application_path)
            and value['SourceADF']==app['ResultADF']['Path'] and value['SourceADFSHA256']==app['ResultADF']['SHA256'] and value['BuildPlanSHA256']==app['BuildPlan']['SHA256'],
            'final direct native evidence identifies another application')
    for path in query_paths:
        value,inputs=native.bind_receipt(path);merge(watched,inputs)
        require(value['Mode']=='query' and value['SourceProof']==ref(application_path)
            and value['SourceADF']==app['ResultADF']['Path'] and value['SourceADFSHA256']==app['ResultADF']['SHA256'],'direct final query uses another source')
    audit=application.importlib.import_module('hdmi_camera_direct_audit')
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
            'direct final routes/placements changed')
    report=baseline.artifact(export_path,exported,build.TARGET+'.rtr')
    exceptions=baseline.artifact(export_path,exported,build.TARGET+'_exception.rtr')
    application.compare_final_summaries(report,baseline.artifact(route_path,routed,build.TARGET+'.rtr'))
    original,inputs=baseline.bind_receipt(app['ExportReceipt']['Path']);merge(watched,inputs)
    old_exceptions=baseline.artifact(app['ExportReceipt']['Path'],original,build.TARGET+'_exception.rtr')
    coverage=validate_exceptions(scope,old_exceptions,exceptions)
    # Detailed IO/interstage and native warning interpretation is a separate
    # completed producer, not a caller-supplied collection of true booleans.
    checks=application.importlib.import_module('hdmi_camera_direct_physical_checks')
    require(Path(checks.__file__).resolve()==SELF.with_name('hdmi_camera_direct_physical_checks.py'),
            'direct final native-check provider location differs')
    checked,inputs=checks.derive(scope,application_path,export_path,route_path,query_paths);merge(watched,inputs)
    require(all(checked.get(k) is True for k in ('Passed','NativeWarningsReviewed','ResetAccepted','InterstageTimingAccepted')),
            'direct final native checks incomplete')
    diagnostic=application.bind_reduction_review(app['ReductionReview']['Path'],scope,watched)
    source_warnings=application.importlib.import_module('hdmi_camera_direct_warnings')
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
        'NativeAcceptance':acceptance,'ExceptionCoverage':coverage,'RouteComparison':routes,**checked,
        'HardwareAccessed':False,'HardwareReleaseAllowed':False,'ExternalACAccepted':False,'RGBPixelsVerified':False,
        'InputSHA256':{str(p):h for p,h in watched.items()}}
    require(not baseline.drift(watched),'direct final physical input drift');return result,watched


def verify(path):
    path=Path(path).absolute();saved=read(path)
    require(saved.get('Schema')==SCHEMA and saved.get('Target')==build.TARGET,'current direct final proof required')
    current,watched=final_facts(saved['Application']['Path'],saved['FinalExport']['Path'],saved['FinalRoute']['Path'],
        [row['Path'] for row in saved['FinalQueries']])
    require(json.loads(json.dumps(current))==saved,'direct final proof differs from complete recomputation')
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
