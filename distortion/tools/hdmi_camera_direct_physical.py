"""Apply only the direct candidate's independently reviewed exact CDC scope.

Plans come only from a completely recomputed direct audit and its independent
two-counter source range review. Application changes only one ADF copy; fresh
final STA and complete path/protocol/reset proof remain required. No previous
candidate's counts, DDR rules or read-only diagnostic bridge are reused.
"""
import argparse
import ast
from collections import Counter
import copy
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

import hdmi_camera_direct_build as build
import hdmi_camera_direct_native as native
import audit_ddr_final_timing as timing

SELF=Path(__file__).resolve()
SCHEMA='hdmi-camera-direct-physical-planning-v1'
AUDIT_SCHEMA='hdmi-camera-direct-native-audit-v1'
require,sha,read=build.require,build.sha,build.read
add,merge,ref=native.add,native.merge,native.ref
MATCH=re.compile(r"^I: Timing-5001: The pattern '(.*)' in command '(.*)' match (\d+) objects below: (.*)$")
APPLICATION_SCHEMA='hdmi-camera-direct-physical-application-v1'
MARKER='HDMI_CAMERA_DIRECT_EXACT_PHYSICAL_SCOPE_SAVED'
GUIDE=Path('D:/pango/PDS_2023.2/doc/User_Constraint_Editor_User_Guide.pdf')
GUIDE_SHA='3f44bba22c92112d04b1c60d32289604498239efcfc156db888cfb0011e10dde'
_AUTHORITY_CACHE={}


def authority(kind,path,derive):
    """Process-local verified authority; every reuse hashes its entire closure."""
    path=Path(path).absolute();require(path==path.resolve() and path.is_file(),'canonical authority file required')
    key=(kind,str(path),sha(path));cached=_AUTHORITY_CACHE.get(key)
    if cached is not None:
        require(not baseline_drift(cached[1]),'cached direct authority input drift')
        return copy.deepcopy(cached)
    value,watched=derive(path);watched=dict(watched)
    add(watched,path);add(watched,SELF)
    require(not baseline_drift(watched),'direct authority input changed during verification')
    _AUTHORITY_CACHE[key]=copy.deepcopy((value,watched));return copy.deepcopy((value,watched))


def baseline_drift(watched):return [str(p) for p,h in watched.items() if not Path(p).is_file() or sha(p)!=h]


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


def selectors_for(rows):
    # All nine individual CLK/Q/I4/RS names were actually queried in the first
    # native preflight. Preserve that exact bounded form without cross products.
    names=sorted({r[key] for r in rows for key in ('FromCLK','LaunchQ','Endpoint')})
    result=[exact_selector([name]) for name in names]
    require(all(len(q['Pattern'])<=4096 for q in result),'bounded literal native selector required')
    return result


def reset_rows(scope):
    rows=scope.get('ResetScopes');require(isinstance(rows,list),'explicit direct reset inventory required')
    for row in rows:
        for key in ('FromCLK','LaunchQ','Endpoint'):exact_selector([row.get(key)])
        require(row['FromCLK'].endswith('/CLK') and row['Endpoint'].endswith(('/SR','/RS'))
            and row.get('GuardAccepted') is True and row.get('GuardProof'),
            'exact guarded native SR reset scope required')
        require(isinstance(row.get('RelationshipIndexes'),list) and row['RelationshipIndexes']
            and row['RelationshipIndexes']==sorted(set(row['RelationshipIndexes'])),'reset source relationship indexes required')
        for index in row['RelationshipIndexes']:
            require(type(index) is int and 0<=index<len(scope['ForeignRelationships']),'reset relationship index invalid')
            relationship=scope['ForeignRelationships'][index]
            require(relationship.get('SourceNativeClockPin')==row['FromCLK']
                and relationship.get('SourceNativeOutputPin')==row['LaunchQ']
                and relationship.get('DestinationPin')=='SR'
                and row['Endpoint'] in {b.get('Endpoint') for b in relationship.get('NativeBoundaries',[])},
                'reset scope differs from actual native SR relationship')
    return rows


def scope_plan(scope,require_ready=True):
    require(scope.get('Schema')==AUDIT_SCHEMA and scope.get('Target')==build.TARGET,'new direct audit required')
    if require_ready:
        require(scope.get('ProposalReady') is True and scope.get('Blockers')==[],'direct audit has unresolved blockers')
    require(all(scope.get(k) is False for k in ('ConstraintsApplied','TimingAccepted','HardwareReleaseAllowed')),
            'direct audit overclaims physical acceptance')
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
        objects=row.get('NativeObjects')
        require(isinstance(objects,dict) and set(objects)=={'SourceFFs','DestinationFFs','SourcePhysicalQ','SourceCLKNet'},
                'complete actual native launch identities required')
        require(all(isinstance(v,list) and v and all(isinstance(n,str) and n for n in v) and v==sorted(set(v))
                    for v in objects.values()),'sorted native identity inventories required')
        require(len(objects['SourcePhysicalQ'])==len(objects['SourceCLKNet'])==1,'conflicting physical source slot/clock-net identities')
        for index in indexes:
            r=relationships[index]
            require(r.get('SourceNativeClockPin')==names[0] and r.get('SourceNativeOutputPin')==names[1]
                    and r.get('SourceFF') in objects['SourceFFs'] and r.get('DestinationFF') in objects['DestinationFFs'],
                    'native launch row differs from its actual foreign relationship')
            require(names[2] in {b.get('Endpoint') for b in r.get('NativeBoundaries',[])},
                    'scope endpoint is not an actual mapped boundary')
            require(r.get('SourcePhysicalQ') in objects['SourcePhysicalQ']
                    and r.get('SourceNativeCLKNet') in objects['SourceCLKNet'],
                    'scope physical Q slot/CLK net differs from mapped relationship')
        triples.append(row)
    resets=reset_rows(scope);selectors=selectors_for(rows+resets)
    return {'ExactLaunchTriples':triples,'NativeSelectors':selectors,
        'PreflightQueryBody':'\n'.join(q['Command'] for q in selectors)+'\n',
        'ActualDataScopeCount':len(triples),'ResetScopes':resets,
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
    audit=importlib.import_module('hdmi_camera_direct_audit')
    require(Path(audit.__file__).resolve()==SELF.with_name('hdmi_camera_direct_audit.py'),'direct audit provider location differs')
    require(callable(getattr(audit,'derive',None)),'direct audit producer is not complete')
    current,inputs=audit.derive(saved['BuildPlan']['Path'],saved['ExportReceipt']['Path'],saved['RouteReceipt']['Path'])
    current=json.loads(json.dumps(current))
    require({k:v for k,v in saved.items() if k!='InputSHA256'}=={k:v for k,v in current.items() if k!='InputSHA256'},
            'direct audit facts differ from full recomputation')
    require(set(saved['InputSHA256'])<=set(current['InputSHA256']) and
        all(current['InputSHA256'][p]==h for p,h in saved['InputSHA256'].items()),'saved direct audit closure missing or changed')
    watched={};merge(watched,inputs);merge(watched,saved['InputSHA256']);merge(watched,current['InputSHA256'])
    for module in (build,native,timing,audit):add(watched,module.__file__)
    add(watched,SELF);add(watched,path)
    return saved,watched


def bind_audit(path):return authority('scope-audit',path,_bind_audit)


def bind_reduction_review(path,scope,watched):
    provider=importlib.import_module('hdmi_camera_direct_reductions')
    require(Path(provider.__file__).resolve()==SELF.with_name('hdmi_camera_direct_reductions.py'),
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
    for row in proposal['ExactLaunchTriples']:
        q=[exact_selector([row[k]]) for k in ('FromCLK','LaunchQ','Endpoint')]
        selectors.update({item['Pattern']:item for item in q})
        route=' -from ['+q[0]['Command']+'] -through ['+q[1]['Command']+'] -to ['+q[2]['Command']+']'
        commands.extend(['set_max_delay -datapath_only'+route+' '+format(row['MaximumNS'],'.12g'),
                         'set_false_path -hold'+route])
    for row in proposal['ResetScopes']:
        queries=[exact_selector([row[key]]) for key in ('FromCLK','LaunchQ','Endpoint')]
        selectors.update({q['Pattern']:q for q in queries})
        commands.append('set_false_path -from ['+queries[0]['Command']+'] -through ['+queries[1]['Command']+
            '] -to ['+queries[2]['Command']+']')
    return commands,list(selectors.values()),proposal['PreflightQueryBody']


def application_recipe(audit_path,reduction_review,preflight,work,maximum=600,require_alias=False):
    work=build.work_path(work);require(type(maximum) is int and 60<=maximum<=600,'bounded60..600s direct application required')
    scope,watched=bind_audit(audit_path);commands,selectors,body=application_commands(scope)
    diagnostic=bind_reduction_review(reduction_review,scope,watched)
    query,inputs=native.bind_receipt(preflight);merge(watched,inputs)
    require(query['Mode']=='query' and query['BuildPlanSHA256']==scope['BuildPlan']['SHA256']
            and query['SourceADF']==scope['SourceADF']['Path'] and query['SourceADFSHA256']==scope['SourceADF']['SHA256'],
            'direct native preflight uses another source')
    require(Path(query['QueryBody']).read_text(encoding='ascii')==body,'direct preflight body differs from exact current scopes')
    exact_names(scope_plan(scope)['NativeSelectors'],(Path(preflight).parent/'stdout.log').read_text(encoding='gb18030',errors='strict'))
    plan=build.validate(scope['BuildPlan']['Path'])
    if require_alias:build.paths.validate_repo_alias(build.ROOT,plan['RepoAlias'])
    semantics=importlib.import_module('camera720_stats_delay_reset_apply')
    static_helpers(watched,SELF,build.__file__,native.__file__,semantics.__file__)
    add(watched,GUIDE,GUIDE_SHA);add(watched,Path('D:/anaconda3/python.exe'))
    require(not any(p.is_relative_to(work) for p in watched),'direct application output overlaps source evidence')
    source_receipt=read(diagnostic['SourceBuildReceipt']['Path'])
    value={'Schema':APPLICATION_SCHEMA,'Target':build.TARGET,'ScopeAudit':ref(audit_path),
        'ReductionReview':ref(reduction_review),'PreflightQuery':ref(preflight),
        **{k:scope[k] for k in ('BuildPlan','ExportReceipt','RouteReceipt','SourceADF','NativeNetlist','RouteDump')},
        'ExactLaunchTriples':scope['DataScopes'],'ExactResetTriples':scope['ResetScopes'],
        'NativeSelectors':selectors,'QueryBody':body,'ExactCommands':commands,
        'SourceDiagnosticBodies':sorted({native.diagnostic_body(row) for row in source_receipt['Diagnostics']}),
        'SourceDiagnosticsPreserved':source_receipt['Diagnostics'],'WorkDirectory':str(work),
        'RepoAlias':plan['RepoAlias'],'MaximumSeconds':maximum,'ExpectedStages':[],
        'CommandCapability':{'VendorGuide':ref(GUIDE),'Sections':['2.2.4.1','2.2.4.4'],
            'FromCLKThroughActualQToExactEndpoint':True,'ActualExceptionCoverageStillRequired':True},
        'ResetExceptionsApplied':bool(scope['ResetScopes']),'ResetAcceptanceInherited':False,
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
    work=build.work_path(work);require(not work.exists(),'fresh direct physical application directory required')
    value,_=application_recipe(audit_path,reduction_review,preflight,work,maximum,require_alias=True)
    work.mkdir();shutil.copyfile(value['SourceADF']['Path'],work/'input.adf')
    (work/'dummy.v').write_text(native.DUMMY,encoding='ascii',newline='\n')
    (work/'stage.tcl').write_text(render_application(value),encoding='ascii',newline='\n')
    value['PreparedUTC']=build.utc();build.write(work/'stage-plan.json',value);return work/'stage-plan.json'


def check_application(path,fresh=False,require_alias=False):
    path=Path(path).absolute();saved=read(path);work=build.work_path(path.parent)
    require(path.name=='stage-plan.json' and saved.get('Schema')==APPLICATION_SCHEMA,'direct physical stage plan required')
    current,watched=application_recipe(saved['ScopeAudit']['Path'],saved['ReductionReview']['Path'],
        saved['PreflightQuery']['Path'],work,saved['MaximumSeconds'],require_alias)
    require(set(saved)==set(current)|{'PreparedUTC'} and {k:v for k,v in saved.items() if k!='PreparedUTC'}==current,
            'direct physical application recipe differs')
    require((work/'stage.tcl').read_text(encoding='ascii')==render_application(current)
            and (work/'dummy.v').read_text(encoding='ascii')==native.DUMMY,'direct physical stage Tcl/dummy differs')
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
    require(build.events(text)==[] and text.splitlines().count(MARKER)==1,'unexpected direct application native events/marker')
    diagnostics=build.diagnostics(work)
    retained=native.retained_reductions(value['SourceDiagnosticsPreserved'],diagnostics,value['SourceDiagnosticBodies'])
    require(sha(value['SourceADF']['Path'])==sha(work/'post-init.adf')==value['SourceADF']['SHA256'],
            'direct application initialization mutated original ADF')
    final=ref(work/'input.adf')
    require(final['SHA256']==sha(work/'saved-scope.adf') and final['SHA256']!=value['SourceADF']['SHA256'],
            'direct scoped ADF save/readback differs')
    semantics=importlib.import_module('camera720_stats_delay_reset_apply')
    routes=semantics.compare_routes(value['RouteDump']['Path'],work/'route-dump.txt')
    require(routes['AllNETANNOTATEIdentical'] and routes['AllNonConstraintNonRouteSemanticTokensIdentical']
            and routes['CDBChanged'],'direct application changed routing/placement or saved no CDB constraints')
    return {'ResultADF':final,'ConstraintsApplied':True,'NativeQueriesVerified':True,'ActualSelectorOccurrences':dict(actual),
        'InitializationPreservedADF':True,'SavedADFReadbackMatches':True,'OriginalADFUnchanged':True,
        'RouteComparison':routes,'RoutesAndPlacementUnchanged':True,'Diagnostics':diagnostics,
        'RetainedReductionReview':retained,'DiagnosticsCleared':False,'Artifacts':native.artifacts(work)}


def execute_application(path):
    value,watched=check_application(path,fresh=True,require_alias=True);work=Path(value['WorkDirectory'])
    require(os.name=='nt','direct physical application requires Windows')
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
        result['Cleanup']=(build.cleanup.stop_owned_tree(process,work,'bounded exact direct physical application')
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
        and saved.get('Cleanup',{}).get('Complete') is True,'unclean direct physical application receipt')
    expected=application_evidence(plan,work)
    require(all(saved.get(k)==v for k,v in expected.items()),'direct physical application evidence changed')
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
    p.add_argument('--reduction-review',type=Path);p.add_argument('--preflight-query',type=Path)
    p.add_argument('--work-dir',type=Path);p.add_argument('--maximum-seconds',type=int,default=600)
    p.add_argument('--execute',type=Path);p.add_argument('--verify-application',type=Path);a=p.parse_args()
    if a.verify_application:
        bind_application(a.verify_application);print('{"Verified":true,"HardwareAccessed":false}');return 0
    if a.execute:
        value=execute_application(a.execute)
        print(json.dumps({k:value.get(k) for k in ('ExecutionPassed','ElapsedSeconds','Error')}));return 0 if value['ExecutionPassed'] else 1
    require(a.audit is not None,'--audit required')
    if a.query_body:
        require(a.output is not None,'--output required');scope,_=bind_audit(a.audit)
        with a.output.open('x',encoding='ascii',newline='\n') as out:out.write(scope_plan(scope,require_ready=False)['PreflightQueryBody'])
        print(json.dumps({'QueryBody':str(a.output)}));return 0
    if a.work_dir:
        require(a.reduction_review is not None and a.preflight_query is not None,
                'formal --reduction-review and --preflight-query required')
        path=prepare_application(a.audit,a.reduction_review,a.preflight_query,a.work_dir,a.maximum_seconds)
        print(json.dumps({'Prepared':True,'StagePlan':str(path)}));return 0
    require(a.output is not None,'--output required')
    print(json.dumps({'PlanningOnly':True,'Output':str(prepare(a.audit,a.output)),'ConstraintsApplicable':False}));return 0


if __name__=='__main__':raise SystemExit(main())
