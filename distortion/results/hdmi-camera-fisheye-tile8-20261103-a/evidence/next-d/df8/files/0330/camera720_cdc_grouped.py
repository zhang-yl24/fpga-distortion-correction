"""Bounded multi-source CDC queries, retaining exact pair/corner coverage.

This CPU-only adapter reuses an explicitly SHA-anchored completed v1 plan.
Every original input is rehashed; grouping is not proof that native details
exist. A separately anchored completed inspection seed can avoid repeating
the same source-semantic proof when binding actual new native receipts.
"""
import argparse
from collections import defaultdict
import copy
import hashlib
import json
from pathlib import Path
import re

import camera720_cdc_batch as base
import camera720_stage_fast as fast

native = fast.native
prep, inspect, require, sha, read = base.prep, base.inspect, base.require, base.sha, base.read
SELF = Path(__file__).resolve()
SCHEMA = 'camera720-cdc-grouped-plan-v1'
MAX_PAIRS = 64
TIMING_PER_BODY = 5


def ref(path):
    path = Path(path).absolute()
    return {'Path':str(path), 'SHA256':sha(path)}


def watch(watched, path, expected=None, pds=None):
    return native.add(watched, path, expected, pds)


def merge(watched, values, pds):
    fast.rehash({str(p):h for p,h in values.items()}, watched, Path(pds))


def domain(q):
    return (('normal', q['Clock']) if 'Clock' in q else
            ('cross', q['SourceClock'], q['DestinationClock'],
             q['MaximumNS'], q['MinimumNS'], q['SourcePeriodNS']))


def validate_queries(queries):
    seen = set()
    require(isinstance(queries,list) and queries, 'nonempty physical inventory required')
    for q in queries:
        pair = q['Source'],q['Endpoint']
        require(pair not in seen and all(base.SAFE_PIN.fullmatch(p) for p in pair),
                'duplicate or unsafe physical pair')
        seen.add(pair)
        require(q.get('Corners') == ['slow','fast'] and q.get('CheckKinds') ==
                (['setup','hold'] if 'Clock' in q else ['max-delay','min-delay']),
                'exact pair/corner kinds required')
        domain(q)
    return seen


def grouped_commands(queries, maximum_pairs=MAX_PAIRS):
    require(type(maximum_pairs) is int and 1 <= maximum_pairs <= MAX_PAIRS, 'pair budget outside 1..64')
    all_pairs = validate_queries(queries)
    domains = defaultdict(list)
    for q in queries:
        domains[domain(q)].append(q)
    result=[]
    for key,values in sorted(domains.items()):
        pairs=sorted((q['Source'],q['Endpoint']) for q in values)
        sources, endpoints, covered = set(),set(),set()
        def rectangle(ss,es):return {(s,e) for s,e in pairs if s in ss and e in es}
        def emit():
            selected=rectangle(sources,endpoints)
            require(selected and len(selected)<=maximum_pairs,'group exceeds expected-pair budget')
            command=('report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE -from {'+
                     ' '.join(sorted(sources))+'} -to {'+' '.join(sorted(endpoints))+'}')
            result.append({'Domain':list(key),'Sources':sorted(sources),'Endpoints':sorted(endpoints),
                           'ExpectedPairs':[{'Source':s,'Endpoint':e} for s,e in sorted(selected)],'Command':command})
            covered.update(selected)
        for s,e in pairs:
            if (s,e) in covered:continue
            proposed_s,proposed_e=sources|{s},endpoints|{e}
            if sources and len(rectangle(proposed_s,proposed_e))>maximum_pairs:
                emit();sources.clear();endpoints.clear()
            sources.add(s);endpoints.add(e)
        if sources:emit()
    emitted={(p['Source'],p['Endpoint']) for g in result for p in g['ExpectedPairs']}
    require(emitted==all_pairs, 'grouping dropped or invented physical pairs')
    return result


def bodies(queries, sites=(), maximum_pairs=MAX_PAIRS, per_body=TIMING_PER_BODY):
    require(type(per_body) is int and 1<=per_body<=TIMING_PER_BODY,'timing commands must be 1..5 per context')
    groups=grouped_commands(queries,maximum_pairs)
    chunks=[[g['Command'] for g in groups[first:first+per_body]] for first in range(0,len(groups),per_body)]
    if sites:
        require(len(sites)==len(set(sites)) and all(re.fullmatch(r'[A-Za-z0-9_]+',s) for s in sites),'unsafe/duplicate site')
        # Keep the full five-query contexts free of route-dump overhead.
        if not chunks or len(chunks[-1])>=per_body:chunks.append([])
        chunks[-1] += ['show -dev_instance {'+s+'}' for s in sorted(sites)]
        chunks[-1].append('.switch_db -route -input {@WORK@/input.adf} -output {@WORK@/route-dump.txt}')
    texts=[]
    for chunk in chunks:
        body='# Grouped probe only; every physical pair/corner still requires native coverage.\n'+'\n'.join(chunk)+'\n'
        inspect.query_commands(body)
        texts.append(body)
    return texts,groups


def bind_original(path, expected_sha, watched):
    path=inspect.canonical(path,prep.WORK)
    require(native.physical.digest(expected_sha) and sha(path)==expected_sha,'explicit completed v1 plan SHA differs')
    value=read(path)
    require(value.get('Schema')==base.SCHEMA and value.get('Target')==prep.TARGET and
            value.get('FinalExportReevaluated') is True,'completed current v1 structural preparation required')
    require(all(value.get(k) is False for k in ('HardwareAccessed','EDAExecuted','TimingAccepted','HardwareReleaseAllowed')),
            'v1 plan exceeds preparation scope')
    export=Path(value['ExportReceipt']['Path']);receipt=read(export)
    pds=receipt['Command'][0]
    merge(watched,value['InputSHA256'],pds)
    watch(watched,path,expected_sha)
    for p,h in ((export,value['ExportReceipt']['SHA256']),
                (Path(value['CandidateADF']['Path']),value['CandidateADF']['SHA256']),
                (Path(value['Netlist']['Path']),value['Netlist']['SHA256']),
                (base.SELF,sha(base.SELF))):
        require(value['InputSHA256'].get(str(p))==h,'v1 authority omits current source/producer')
        watch(watched,p,h,pds)
    native.receipt_flags(receipt)
    require(receipt['Mode']=='export' and receipt['SourceADF']==value['CandidateADF']['Path'] and
            receipt['SourceADFSHA256']==value['CandidateADF']['SHA256'] and
            receipt['BuildPlanSHA256']==value['BuildPlanSHA256'] and receipt['Netlist']==value['Netlist'],
            'v1 plan differs from actual final export')
    validate_queries(value['Queries'])
    require(value['ExpectedCases']==len(value['Queries'])*4,'v1 expected-case count differs')
    texts,groups=base.bodies(value['Queries'],value['IOSites'])
    require(value['Groups']==groups and value['QueryBodies']=={
        f'query-{i:02}.tcl':hashlib.sha256(t.encode('ascii')).hexdigest() for i,t in enumerate(texts)},'v1 query recipe differs')
    for name,h in value['QueryBodies'].items():watch(watched,path.parent/name,h)
    watch(watched,SELF)
    return value


def bind_seed(seed_ref, candidate, build_sha, watched):
    require(isinstance(seed_ref,dict) and set(seed_ref)=={'Path','SHA256'},'explicit inspection seed reference required')
    seed,original,bound=fast.bind_seed(seed_ref['Path'],seed_ref['SHA256'])
    require(seed['SourceADF']==candidate and original['BuildPlanSHA256']==build_sha,'inspection seed has different candidate/build')
    merge(watched,bound,original['Command'][0]);watch(watched,SELF)
    return seed,original,bound


def bind_native_fast(path, mode, watched, candidate, build_sha, inspection_seed, seed_context=None):
    """Bind actual export/query bytes against an explicitly completed source proof.

    This does not approve a query body as a CDC/IO probe. Consumers must check
    their body inventory separately. seed_context must be the result of the
    actual bind_seed call in the same audit, never a serialized claimed flag.
    """
    context=seed_context or bind_seed(inspection_seed,candidate,build_sha,watched)
    seed,original,bound=context
    require(seed['SourceADF']==candidate and original['BuildPlanSHA256']==build_sha,'seed context differs')
    merge(watched,bound,original['Command'][0])
    path=inspect.canonical(path,prep.WORK);work=prep.work_path(path.parent)
    require(path.name=='result.json','exact actual receipt required')
    value=read(path);native.receipt_flags(value)
    require(value['Mode']==mode and mode in ('query','export') and value['SourceADF']==candidate['Path'] and
            value['SourceADFSHA256']==candidate['SHA256'] and value['BuildPlanSHA256']==build_sha,
            'native receipt candidate/build/mode differs')
    require(value.get('FastExecutionSeed')==inspection_seed and value.get('FastExecutor')==ref(fast.SELF) and
            value.get('FullSourceProofReused') is True and value.get('AllProofInputsRehashed') is True,
            'native execution lacks the anchored fast proof')
    body=Path(value['QueryBody']) if mode=='query' else None
    expected,tcl=fast.envelope(original,work,mode,body,value['MaximumSeconds'])
    stage_path=watch(watched,work/'stage-plan.json',value['StagePlanSHA256']);stage=read(stage_path)
    require(set(stage)==set(expected)|{'PreparedUTC'} and isinstance(stage['PreparedUTC'],str) and stage['PreparedUTC'] and
            {k:v for k,v in stage.items() if k!='PreparedUTC'}==expected and
            all(value.get(k)==v for k,v in stage.items()),'native stage differs from exact source recipe')
    merge(watched,expected['InputSHA256'],expected['Command'][0])
    watch(watched,path);watch(watched,work/'input.adf',candidate['SHA256'])
    watch(watched,work/'executor-snapshot.py',sha(native.SELF))
    require((work/'stage.tcl').read_bytes()==tcl.encode('ascii'),'native executed Tcl differs')
    if mode=='query':
        require((work/'dummy.v').read_bytes()==native.physical.DUMMY.encode('ascii'),'native dummy drift')
        watch(watched,work/'dummy.v')
        require(value['InputSHA256'].get(str(body))==sha(body),'query body unbound')
    artifacts=value.get('Artifacts')
    require(isinstance(artifacts,dict) and {'stage.tcl','stdout.log','stderr.log'}<=set(artifacts),'native artifact inventory missing')
    for name,h in artifacts.items():
        p=inspect.canonical(work/name,work);watch(watched,p,h)
        if p.suffix=='.log':
            text=p.read_text(encoding='gb18030',errors='replace')
            require(not re.search(r'(?m)^\s*(?:E:|F:|ERROR:|FATAL:|Traceback).*$',text),'actual native diagnostic present')
    log=(work/'stdout.log').read_text(encoding='gb18030',errors='replace')
    require(native.MARKER in log and [list(e) for e in native.diagnostic.stage_events(log)]==value['ActualEvents'],
            'actual native completion/stages differ')
    if mode=='export':
        net=Path(value['Netlist']['Path'])
        require(net==work/'generate_netlist'/(prep.TARGET+'_sim.v') and
                artifacts.get(net.relative_to(work).as_posix())==value['Netlist']['SHA256'],'placed export differs')
        watch(watched,net,value['Netlist']['SHA256'])
    require(not inspect.drift(watched),'native receipt proof drifted')
    return value


def prepare(original_path, original_sha, output, inspection_seed, maximum_pairs=MAX_PAIRS, per_body=TIMING_PER_BODY):
    watched={};old=bind_original(original_path,original_sha,watched)
    bind_seed(inspection_seed,old['CandidateADF'],old['BuildPlanSHA256'],watched)
    texts,groups=bodies(old['Queries'],old['IOSites'],maximum_pairs,per_body)
    keep=('CandidateADF','BuildPlanSHA256','Netlist','ExportReceipt','Queries','IOSites','ComponentChecks',
          'Constraints','ActualCells','ActualFFs','ExpectedCases')
    value={k:copy.deepcopy(old[k]) for k in keep}
    value.update(Schema=SCHEMA,Target=prep.TARGET,CreatedUTC=inspect.utc(),Producer=ref(SELF),
        OriginalBatchPlan={'Path':str(Path(original_path).absolute()),'SHA256':original_sha},
        InspectionSeed=inspection_seed,CompletedV1PreparationReused=True,AllPriorInputsRehashed=True,
        MaximumExpectedPairsPerGroup=maximum_pairs,MaximumTimingCommandsPerBody=per_body,
        Groups=groups,QueryBodies={f'query-{i:02}.tcl':hashlib.sha256(t.encode('ascii')).hexdigest() for i,t in enumerate(texts)},
        NativeTimingCommands=len(groups),NativeContexts=len(texts),CoverageAssumedFromGrouping=False,
        HardwareAccessed=False,EDAExecuted=False,TimingAccepted=False,HardwareReleaseAllowed=False)
    return base.write_output(output,'grouped-plan.json',value,watched,{f'query-{i:02}.tcl':t for i,t in enumerate(texts)})


def bind_plan(path, expected_sha, watched):
    path=inspect.canonical(path,prep.WORK)
    require(native.physical.digest(expected_sha) and sha(path)==expected_sha,'explicit grouped plan SHA differs')
    plan=read(path)
    require(plan.get('Schema')==SCHEMA and plan.get('Target')==prep.TARGET and plan.get('Producer')==ref(SELF),
            'wrong grouped plan/producer')
    require(plan.get('CompletedV1PreparationReused') is True and plan.get('AllPriorInputsRehashed') is True and
            plan.get('CoverageAssumedFromGrouping') is False and all(plan.get(k) is False for k in
            ('HardwareAccessed','EDAExecuted','TimingAccepted','HardwareReleaseAllowed')),'grouped plan exceeds scope')
    old=bind_original(plan['OriginalBatchPlan']['Path'],plan['OriginalBatchPlan']['SHA256'],watched)
    context=bind_seed(plan['InspectionSeed'],plan['CandidateADF'],plan['BuildPlanSHA256'],watched)
    require({str(p):h for p,h in watched.items()}==plan['InputSHA256'],'grouped input closure differs')
    for k in ('CandidateADF','BuildPlanSHA256','Netlist','ExportReceipt','Queries','IOSites','ComponentChecks',
              'Constraints','ActualCells','ActualFFs','ExpectedCases'):
        require(plan[k]==old[k],'grouped plan changed validated physical inventory: '+k)
    texts,groups=bodies(plan['Queries'],plan['IOSites'],plan['MaximumExpectedPairsPerGroup'],plan['MaximumTimingCommandsPerBody'])
    require(plan['Groups']==groups and plan['QueryBodies']=={
        f'query-{i:02}.tcl':hashlib.sha256(t.encode('ascii')).hexdigest() for i,t in enumerate(texts)} and
        plan['NativeTimingCommands']==len(groups) and plan['NativeContexts']==len(texts),'grouped query recipe differs')
    watch(watched,path,expected_sha)
    for name,h in plan['QueryBodies'].items():watch(watched,path.parent/name,h)
    require(not inspect.drift(watched),'grouped preparation drifted')
    return plan,texts,context


def approved_body(body, plan, initial):
    commands=inspect.query_commands(body)
    if body in initial:return
    allowed={g['Command'] for g in base.group_commands(plan['Queries'],exact=True)}
    require(len(commands)<=TIMING_PER_BODY and all(c in allowed for c in commands),
            'query is not a planned grouped body or bounded exact supplement')


def audit(plan_path, expected_sha, receipt_paths):
    watched={};plan,texts,context=bind_plan(plan_path,expected_sha,watched)
    reports,logs,refs=[],[],[]
    require(receipt_paths,'actual native receipts required')
    for path in receipt_paths:
        receipt=bind_native_fast(path,'query',watched,plan['CandidateADF'],plan['BuildPlanSHA256'],plan['InspectionSeed'],context)
        approved_body(Path(receipt['QueryBody']).read_text(encoding='ascii'),plan,texts)
        work=Path(path).absolute().parent
        reports.extend(work/name for name in receipt['Artifacts'] if name.endswith('.rtr'))
        logs.append((work/'stdout.log').read_text(encoding='gb18030'))
        refs.append(ref(path))
    require(reports,'no receipt-bound native timing reports')
    records,violations=base.collect(plan['Queries'],sorted(set(reports)))
    result=base.coverage(plan['Queries'],records,violations)
    site_blocks={}
    for log in logs:
        for block in re.findall(r'(?ms)^Site \S+ \(\d+\) :\r?\n.*?(?=^Site |^Executing :|\Z)',log):
            site=re.match(r'Site (\S+)',block)[1]
            require(site not in site_blocks or site_blocks[site]==block,'native site evidence conflicts')
            site_blocks[site]=block
    pins=copy.deepcopy(plan['ComponentChecks']['Pins']);site_error=None
    try:base.structure.io.apply_native_sites(pins,''.join(site_blocks.values()))
    except ValueError as error:site_error=str(error)
    missing_pairs={(r['Source'],r['Endpoint']) for r in result['MissingCases']}
    missing=[q for q in plan['Queries'] if (q['Source'],q['Endpoint']) in missing_pairs]
    commands=[g['Command'] for g in base.group_commands(missing,exact=True)] if missing else []
    supplements={f'supplement-{i//TIMING_PER_BODY:02}.tcl':'# Exact missing pairs; no inferred coverage.\n'+
        '\n'.join(commands[i:i+TIMING_PER_BODY])+'\n' for i in range(0,len(commands),TIMING_PER_BODY)}
    result.update(Schema='camera720-cdc-native-coverage-v1',Target=prep.TARGET,Producer=ref(SELF),
        BatchPlan={'Path':str(Path(plan_path).absolute()),'SHA256':expected_sha},
        OriginalBatchPlan=plan['OriginalBatchPlan'],InspectionSeed=plan['InspectionSeed'],
        CandidateADF=plan['CandidateADF'],NativeReceipts=refs,Records=records,Violations=violations,
        MissingPairCount=len(missing_pairs),Pins=pins,NativeSiteError=site_error,
        NativeSiteMappingVerified=site_error is None,
        EnumeratedPathsAndSitesPassed=result['EnumeratedPathsTimingPassed'] and site_error is None,
        NativeElectricalSettingsVerified=False,AnalogMTBFProven=False,TimingAccepted=False,
        HardwareAccessed=False,EDAExecuted=False,HardwareReleaseAllowed=False,
        Limits='Explicitly anchored full structural proof and exact native pair/corner coverage; grouping does not imply coverage. Electrical/overall timing/optical/board release are separate.')
    require(not inspect.drift(watched),'native coverage evidence drifted')
    result['InputSHA256']={str(p):h for p,h in watched.items()}
    return result,watched,supplements


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True)
    a=sub.add_parser('prepare');a.add_argument('--original-plan',type=Path,required=True)
    a.add_argument('--original-sha256',required=True);a.add_argument('--inspection-seed',type=Path,required=True)
    a.add_argument('--inspection-seed-sha256',required=True)
    a.add_argument('--maximum-pairs',type=int,default=MAX_PAIRS);a.add_argument('--timing-per-body',type=int,default=TIMING_PER_BODY)
    c=sub.add_parser('check');c.add_argument('--grouped-plan',type=Path,required=True)
    c.add_argument('--grouped-plan-sha256',required=True);c.add_argument('--query-receipt',type=Path,action='append',required=True)
    for child in (a,c):child.add_argument('--output-dir',type=Path,required=True)
    args=p.parse_args()
    if args.mode=='prepare':
        result=prepare(args.original_plan,args.original_sha256,args.output_dir,
            {'Path':str(args.inspection_seed.absolute()),'SHA256':args.inspection_seed_sha256},args.maximum_pairs,args.timing_per_body)
    else:
        result,watched,payloads=audit(args.grouped_plan,args.grouped_plan_sha256,args.query_receipt)
        base.write_output(args.output_dir,'coverage.json',result,watched,payloads)
    print(json.dumps({k:result[k] for k in ('ExpectedCases','NativeTimingCommands','NativeContexts','CoveredCases','MissingPairCount',
           'EnumeratedPathsAndSitesPassed') if k in result}))
    return 0 if args.mode=='prepare' or result['EnumeratedPathsAndSitesPassed'] else 1


if __name__=='__main__':raise SystemExit(main())
