"""Complete native top-N exception membership using exact two-sided queries.

CPU only. Only delays on the three physically repaired data nets may change.
An unchanged route may have at most 1 ps of printed data-net rounding; clock,
constraint, required-time, cell-delay and structural changes are never waived.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

import audit_camera_vga_hold as hold
import audit_camera_vga_physical as physical
import audit_ddr_final_timing as native

require = native.require
sha = hold.sha
NETS = frozenset(('_N101', '_N188', '_N78'))
WRITE_SOURCE='u_ddr3_test_h/u_ddrphy_top/ddrphy_dfi/phy_wrdata_d[3]/opit_0_inv_L6Q_LUT6DQL5Q_perm/CLK'
WRITE_ENDPOINT='u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/dq_loop[1].u_iobuf_dq/opit_1/TX_DATA[1]'
PS = Decimal('0.001')
NUM = hold.NUM
LOGIC = re.compile(r'^\s*Logic:\s*('+NUM+r')ns\(('+NUM+r')%\), Route:\s*('+NUM+r')ns\(('+NUM+r')%\)\s*$')
ARRIVAL = re.compile(r'^( Data arrival time\s+)('+NUM+r')(.*)$')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def normalized(lines):
    """Ignore native layout and constraint-file line numbers, not constraints."""
    return [native.normalize(line) for line in lines if line.strip()
            and not set(line.strip()) <= set('=-*')
            and not line.startswith('Exception constraint line number:')]


def record(lines, path, first_line, section=None):
    return {'Lines':lines, 'Report':str(Path(path).resolve()), 'ReportLine':first_line,
            'Section':section, 'SHA256':digest(normalized(lines))}


def read_exceptions(path):
    sections, pending, section, block, first = {}, None, None, [], 0
    with Path(path).open(encoding='gb18030') as stream:
        for n, line in enumerate(stream, 1):
            header = native.EX_HEADER.fullmatch(line.rstrip('\r\n'))
            if header:
                require(not block, 'unterminated exception path before header')
                section = None; pending = header[1]
                continue
            corner = re.fullmatch(r'\| (Slow|Fast) Corner\s*', line)
            if pending is not None and corner:
                section = (corner[1].lower(), pending)
                require(section not in sections, 'duplicate exception section')
                sections[section] = []; pending = None
                continue
            if section is None or section[1].startswith('set_false_path('):
                continue
            if line.startswith('Startpoint'):
                require(not block, 'truncated exception path')
                block = [line]; first = n
            elif block:
                block.append(line)
                if line.startswith(' Slack'):
                    sections[section].append(record(block, path, first, section)); block=[]
    require(not block and len(sections)==24, 'all 24 complete exception sections required')
    return {k:v for k,v in sections.items() if not k[1].startswith('set_false_path(')}


def parsed(row):
    if 'Parsed' not in row:
        p = hold.parse_path(row['Lines'], row['Report'], row['ReportLine'])
        require(p is not None, 'changed exception is not a fully clocked setup/hold path')
        row['Parsed'] = p
    return row['Parsed']


def identity(row):
    p = parsed(row)
    return tuple(p[k] for k in (*physical.KEYS, 'LaunchEdge', 'CaptureEdge', 'Corner', 'Kind', 'PathClass')) + (
        tuple(p['TimingExceptions']), p['DataTrace'][0]['Transition'])


def public_identity(row):
    p = parsed(row)
    return {k:p[k] for k in (*physical.KEYS, 'LaunchEdge', 'CaptureEdge', 'Corner', 'Kind', 'PathClass')} | {
        'TimingExceptions':p['TimingExceptions'], 'SourceTransition':p['DataTrace'][0]['Transition']}


def read_union(paths, sources, endpoints):
    found = {}
    for path in paths:
        block, first = [], 0
        with Path(path).open(encoding='gb18030') as stream:
            for n, line in enumerate(stream, 1):
                if line.startswith('Startpoint'):
                    require(not block or not re.search(r'^ (Setup|Hold) time', ''.join(block), re.M),
                            'truncated union setup/hold record')
                    block = [line]; first = n
                elif block:
                    block.append(line)
                    if line.startswith(' Slack'):
                        text=''.join(block)
                        s=re.findall(r'^Startpoint\s*:\s*(.+?)\s*$',text,re.M)
                        e=re.findall(r'^Endpoint\s*:\s*(.+?)\s*$',text,re.M)
                        if len(s)==len(e)==1 and s[0] in sources and e[0] in endpoints:
                            row=record(block,path,first)
                            if re.search(r'^ (Setup|Hold) time',text,re.M):
                                parsed(row); found.setdefault(row['SHA256'],row)
                        block=[]
        require(not block or not re.search(r'^ (Setup|Hold) time', ''.join(block), re.M),
                'truncated union setup/hold record at EOF')
    require(found, 'union query contains no selected paths')
    return list(found.values())


def dec(value):
    return Decimal(str(value))


def within(value, expected, label):
    require(abs(value-expected)<=PS, label+' exceeds 1 ps printed precision')


def semantic_skeleton(row,check_printed_percent=True):
    """Only independently checked data values are removed from exact text."""
    lines, arrivals, totals, active, index = [], [], [], False, 0
    for line in row['Lines']:
        if not line.strip() or set(line.strip()) <= set('=-*'):
            continue
        if line.startswith('Exception constraint line number:'):
            continue
        if re.search(r'\s+tco\s+', line): active=True
        a=ARRIVAL.fullmatch(line.rstrip('\r\n'))
        if a:
            active=False; arrivals.append(dec(a[2])); lines.append(native.normalize(a[1]+'<DATA_ARRIVAL>'+a[3])); continue
        if active:
            require(hold.NET.fullmatch(line) or hold.PIN.fullmatch(line), 'unparsed data row')
            lines.append('<CHECKED_DATA_ROW_'+str(index)+'>'); index+=1; continue
        m=LOGIC.fullmatch(line)
        if m:
            totals.append(tuple(dec(x) for x in m.groups())); lines.append('<CHECKED_LOGIC_ROUTE_TOTALS>'); continue
        if line.startswith(' Slack'):
            lines.append('<CHECKED_SLACK>'); continue
        lines.append(native.normalize(line))
    require(len(arrivals)==2 and arrivals[0]==arrivals[1] and len(totals)==1,
            'arrival/logic-route totals incomplete')
    require(index==len(parsed(row)['DataTrace']), 'data skeleton coverage differs')
    logic,lp,route,rp=totals[0]
    require(logic+route>0, 'zero data-delay total')
    within(lp,logic/(logic+route)*100,'logic percentage')
    within(rp,route/(logic+route)*100,'route percentage')
    return lines, arrivals[0], totals[0]


def compare_path(old, new, stable_routes):
    a,b=parsed(old),parsed(new)
    require(identity(old)==identity(new), 'clock/edge/type/exception identity changed')
    sa,aa,ta=semantic_skeleton(old); sb,ab,tb=semantic_skeleton(new)
    require(sa==sb, 'clock, constraint, required-time or non-data path text changed')
    require(len(a['DataTrace'])==len(b['DataTrace']), 'data path length changed')
    actual={v['Name'] for v in a['DataTrace'] if v['Type']=='net'} & NETS
    delta=Decimal(0); differences=[]; printed=[]
    for index,(x,y) in enumerate(zip(a['DataTrace'],b['DataTrace'])):
        fields=set(x)-{'DelayNS','CumulativeNS','ReportLine'}
        require(fields==set(y)-{'DelayNS','CumulativeNS','ReportLine'} and
                all(x[k]==y[k] for k in fields), 'physical/data structure changed')
        if x['Type']=='pin':
            require(x['DelayNS']==y['DelayNS'], 'primitive data delay changed')
        else:
            d=dec(y['DelayNS'])-dec(x['DelayNS'])
            if d:
                detail={'Row':index,'Net':x['Name'],'BeforeNS':x['DelayNS'],'AfterNS':y['DelayNS'],'DeltaNS':float(d)}
                if x['Name'] in NETS:
                    differences.append(detail)
                else:
                    require(not actual and stable_routes and abs(d)<=PS,
                            'unrepaired data-net delay changed beyond verified printed precision')
                    printed.append(detail)
                delta+=d
        require((x['CumulativeNS'] is None)==(y['CumulativeNS'] is None),'cumulative field changed')
        if x['CumulativeNS'] is not None:
            d=dec(y['CumulativeNS'])-dec(x['CumulativeNS'])
            within(d,delta,'cumulative data delta')
            if not actual and d:
                require(stable_routes and abs(d)<=PS,'unchanged route cumulative exceeds 1 ps')
    arrival_delta=ab-aa
    within(arrival_delta,delta,'arrival delta')
    require(ta[0]==tb[0], 'logic total changed')
    within(tb[2]-ta[2],delta,'route total delta')
    slack_delta=dec(b['SlackNS'])-dec(a['SlackNS'])
    within(slack_delta,arrival_delta*(-1 if a['Kind']=='setup' else 1),'derived slack delta')
    if not actual:
        require(stable_routes or (aa==ab and ta==tb and a['SlackNS']==b['SlackNS']),
                'printed change lacks unchanged-route proof')
        require(abs(arrival_delta)<=PS and abs(tb[2]-ta[2])<=PS and abs(slack_delta)<=PS,
                'unchanged route aggregate exceeds 1 ps')
    return {'Identity':public_identity(old),'ActualRepairedNets':sorted(actual),
            'RepairedNetChanges':differences,'UnchangedRoutePrintedChanges':printed,
            'ArrivalDeltaNS':float(arrival_delta),'SlackDeltaNS':float(slack_delta),
            'Baseline':{k:old[k] for k in ('Report','ReportLine','SHA256')},
            'Candidate':{k:new[k] for k in ('Report','ReportLine','SHA256')}}


def compare_worst_variant(old,new,context):
    """One observed native representative switch; this is NOT same-variant proof."""
    require(context and context.get('FunctionalGraphIdentical') and context.get('AllFFPlacementsIdentical')
            and context.get('AllInternalChecksMet'),'representative switch needs full functional/STA evidence')
    a,b=parsed(old),parsed(new)
    require(identity(old)==identity(new),'representative clock/edge/exception identity differs')
    require((a['Source'],a['Endpoint'],a['Corner'],a['Kind'],a['LaunchClock'],a['CaptureClock'],
             a['LaunchEdge'],a['CaptureEdge'],a['TimingExceptions'])==
            (WRITE_SOURCE,WRITE_ENDPOINT,'fast','hold','ddrphy_sysclk','phy_dq_sysclk_1',
             'rising','rising',['MultiCycle Path Setup -end 2']), 'not the observed write fast-hold representative')
    sa,aa,ta=semantic_skeleton(old);sb,ab,tb=semantic_skeleton(new)
    require(sa==sb,'representative clock/constraint/required-time structure changed')
    require(len(a['DataTrace'])==len(b['DataTrace'])==9,'unexpected write data-path length')
    for x,y in zip(a['DataTrace'],b['DataTrace']):
        fields=set(x)-{'DelayNS','CumulativeNS','Transition','ReportLine'}
        require(fields==set(y)-{'DelayNS','CumulativeNS','Transition','ReportLine'} and
                all(x[k]==y[k] for k in fields),'representative logical/physical connectivity changed')
    nets={v['Name'] for v in a['DataTrace'] if v['Type']=='net'}
    require(nets&NETS=={'_N78'},'representative does not traverse only repaired _N78')
    require(a['DataTrace'][-2]['Name']=='_N78','repaired net is not the terminal branch')
    before=[v['Transition'] for v in a['DataTrace'] if v['Type']=='pin']
    after=[v['Transition'] for v in b['DataTrace'] if v['Type']=='pin']
    require(before==['r']*5 and after==['r','f','f','f','f'],
            'native representative transition pattern differs')
    for x,y in zip(a['DataTrace'][:2],b['DataTrace'][:2]):
        require({k:v for k,v in x.items() if k!='ReportLine'}=={k:v for k,v in y.items() if k!='ReportLine'},
                'launch/data path before transition switch changed')
    require(b['SlackNS']>=0,'new worst transition still fails')
    within(dec(b['SlackNS'])-dec(a['SlackNS']),ab-aa,'representative hold slack delta')
    def clean(rows):return [{k:v for k,v in r.items() if k!='ReportLine'} for r in rows]
    return {'Identity':public_identity(old),'ActualRepairedNets':['_N78'],
            'NativeWorstTransitionRepresentativeChanged':True,'SameTransitionVariantProved':False,
            'OnlyRepairedNetDelayChanged':False,'RepairedNetChanges':[],
            'UnchangedRoutePrintedChanges':[], 'BaselineDataTrace':clean(a['DataTrace']),
            'CandidateDataTrace':clean(b['DataTrace']),'BaselineLogicRouteTotals':[float(v) for v in ta],
            'CandidateLogicRouteTotals':[float(v) for v in tb],
            'ArrivalDeltaNS':float(ab-aa),'SlackDeltaNS':b['SlackNS']-a['SlackNS'],
            'Baseline':{k:old[k] for k in ('Report','ReportLine','SHA256')},
            'Candidate':{k:new[k] for k in ('Report','ReportLine','SHA256')},
            'Evidence':'Identical functional graph and all FF sites; only three physical nets changed; exact remaining summary counts/constraints preserved and full native setup/hold both corners passed. Native selects a different endpoint data transition for this one source/endpoint.'}


def compare_records(before, after, old_union, new_union, stable_routes,context=None):
    require(set(before)==set(after) and len(before)==16, 'non-false exception section inventory changed')
    by_old,by_new=defaultdict(list),defaultdict(list)
    for row in old_union:by_old[identity(row)].append(row)
    for row in new_union:by_new[identity(row)].append(row)
    sections,needed={},{}
    for key,rows in before.items():
        now=after[key]
        require(len(rows)==len(now), 'exception section record count changed: '+str(key))
        ca,cb=Counter(r['SHA256'] for r in rows),Counter(r['SHA256'] for r in now)
        removed,added=ca-cb,cb-ca
        section={'BaselineCount':len(rows),'CandidateCount':len(now),'ByteSemanticUnchangedCount':sum((ca&cb).values()),
                 'RemovedMembers':sum(removed.values()),'AddedMembers':sum(added.values())}
        for side,values,changes,own,other in (('baseline',rows,removed,by_old,by_new),('candidate',now,added,by_new,by_old)):
            for row in values:
                if row['SHA256'] not in changes:continue
                ident=identity(row)
                require(ident in own and ident in other,
                        'union missing identity on one side: '+json.dumps(public_identity(row)))
                require(any(u['SHA256']==row['SHA256'] for u in own[ident]),
                        'union missing exact '+side+' member: '+json.dumps(public_identity(row)))
                needed[ident]=True
        sections[str(key)]=section
    checked=[]
    for ident in needed:
        old=by_old[ident];new=by_new[ident]
        require(len(old)==len(new), 'union variant count changed: '+json.dumps(public_identity(old[0])))
        remaining=list(new)
        for row in old:
            choices=[]
            for index,candidate in enumerate(remaining):
                try: outcome=compare_path(row,candidate,stable_routes)
                except ValueError:
                    try:outcome=compare_worst_variant(row,candidate,context)
                    except ValueError:continue
                choices.append((index,outcome))
            require(choices, 'no structurally equivalent union counterpart: '+json.dumps(public_identity(row)))
            index,outcome=choices[0];remaining.pop(index);checked.append(outcome)
    return {'Sections':sections,'MembershipCompletedFromBothUnions':True,'ComparedUnionPaths':checked,
            'ChangedIdentityCount':len(needed),'ComparedUnionPathCount':len(checked),
            'NativeWorstTransitionRepresentativeChanges':sum(bool(r.get('NativeWorstTransitionRepresentativeChanged')) for r in checked),
            'PrintedRoundingPathCount':sum(bool(r['UnchangedRoutePrintedChanges']) for r in checked)}


def route_chain(paths):
    require(len(paths)>=2, 'base-to-hold and hold-to-final route proofs required')
    watched={}; previous=None; first=None; last=None
    for index,path in enumerate(paths):
        path=Path(path).resolve(); watched[str(path)]=sha(path)
        proof=json.loads(path.read_text())
        require(proof.get('AuditPassed') is True, 'route proof failed')
        c=proof['Comparison']
        if index==0:
            require(proof['Schema']=='camera-vga-route-order-comparison-v1' and set(c['ChangedNets'])==NETS and
                    c['AllOtherNETANNOTATEIdentical'] and c['CDBRawTextIdentical'] and
                    c['AllNonRouteSemanticsIdenticalAfterSiblingOrderNormalization'], 'first route proof scope differs')
        else:
            require(proof['Schema']=='camera-vga-route-reset-scope-v1' and c['AllNETANNOTATEIdentical'] and
                    c['AllTargetTreesIdentical'] and c['AllNonConstraintNonRouteSemanticTokensIdentical'],
                    'later route proof scope differs')
        for name in ('Baseline','Candidate'):
            item=proof[name]; file=Path(item['Path']).resolve(); h=sha(file)
            require(h==item['SHA256'], 'route proof dump hash drift')
            watched[str(file)]=h
        if previous is not None:
            require(proof['Baseline']['SHA256']==previous, 'route proof chain is disconnected')
        else:first=proof['Baseline']
        previous=proof['Candidate']['SHA256'];last=proof['Candidate']
        for key in ('BaselineProvenance','CandidateProvenance'):
            provenance=proof[key]
            require(provenance.get('Verified') is True,'route proof missing execution provenance')
            receipt=Path(provenance['Receipt']).resolve()
            require(sha(receipt)==provenance['ReceiptSHA256'],'route receipt hash drift')
            watched[str(receipt)]=provenance['ReceiptSHA256']
            adf=Path(provenance['InputADF']).resolve()
            require(sha(adf)==provenance['InputADFSHA256'],'route ADF hash drift')
            watched[str(adf)]=provenance['InputADFSHA256']
        if index==0:base_adf=proof['BaselineProvenance']['InputADFSHA256']
        last_adf=proof['CandidateProvenance']['InputADFSHA256']
    return {'Verified':True,'OnlyChangedNets':sorted(NETS),'Baseline':first,'Candidate':last,
            'BaselineADFSHA256':base_adf,'CandidateADFSHA256':last_adf,
            'Proofs':[str(Path(p).resolve()) for p in paths]},watched


def bind_report(path,adf_hash,watched):
    """An actual completed native receipt must own every consumed report."""
    path=Path(path).resolve()
    parents=[p for p in path.parents if (p/'result.json').is_file()]
    require(parents,'report lacks an owning native receipt')
    work=parents[0];receipt=work/'result.json';value=json.loads(receipt.read_text())
    require(value.get('ExecutionPassed') is True and value.get('ExitCode')==0 and
            value.get('TimedOut') is False and not value.get('InputDrift') and
            not value.get('Diagnostics') and value.get('CompletionMarker') is True,
            'report native receipt failed')
    require(value['ResultADFSHA256']==adf_hash and sha(work/'input.adf')==adf_hash,
            'report ADF differs from route evidence')
    key=path.relative_to(work).as_posix()
    require(value['Artifacts'].get(key)==sha(path),'report not bound by native artifact receipt')
    watched[str(receipt)]=sha(receipt);watched[str(work/'input.adf')]=adf_hash
    return {'Report':str(path),'Receipt':str(receipt),'ReceiptSHA256':watched[str(receipt)],
            'ReportSHA256':sha(path),'InputADFSHA256':adf_hash}


def physical_context(path,chain,watched):
    """Recompute the strong supporting facts; do not accept an unbound boolean."""
    path=Path(path).resolve();before=sha(path);argv=json.loads(path.read_text())
    require(isinstance(argv,list) and len(argv)%2==0 and all(isinstance(v,str) for v in argv),
            'physical arguments must be flag/value pairs')
    wanted=('baseline-report','candidate-report','baseline-netlist','candidate-netlist','hold-analysis','reset-inventory')
    args={}
    for flag,value in zip(argv[::2],argv[1::2]):
        if flag.removeprefix('--') in wanted:
            require(flag not in args,'duplicate physical context argument');args[flag]=Path(value)
    require(set(args)=={'--'+v for v in wanted},'incomplete physical context inputs')
    for p in args.values():watched[str(p.resolve())]=sha(p)
    bind_report(args['--baseline-report'],chain['BaselineADFSHA256'],watched)
    bind_report(args['--candidate-report'],chain['CandidateADFSHA256'],watched)
    bind_report(args['--baseline-netlist'],chain['BaselineADFSHA256'],watched)
    bind_report(args['--candidate-netlist'],chain['CandidateADFSHA256'],watched)
    analysis=json.loads(args['--hold-analysis'].read_text())
    require(analysis['HoldFailingPathCount']==3 and
            {p['PhysicalRepairCandidate']['Net'] for p in analysis['Paths']}==NETS,'physical target inventory differs')
    pairs={(p['LaunchClock'],p['CaptureClock']) for p in analysis['Paths']}
    inventory=json.loads(args['--reset-inventory'].read_text())
    a,ac=physical.summaries(args['--baseline-report']);b,bc=physical.summaries(args['--candidate-report'])
    require(ac==bc,'clock definitions/loads changed')
    changes,totals=physical.compare_summaries(a,b,pairs,inventory)
    graph=physical.compare_exports(args['--baseline-netlist'],args['--candidate-netlist'])
    require(sha(path)==before,'physical arguments drift');watched[str(path)]=before
    return {**graph,'AllInternalChecksMet':all(v['FailingChecks']==0 for v in totals.values()),
            'CornerSummaries':totals,'SummaryChanges':changes,'InputPaths':{k:str(v.resolve()) for k,v in args.items()}}


def audit(args):
    paths=[args.baseline_exceptions,args.candidate_exceptions,args.query_plan]+args.baseline_union+args.candidate_union
    watched={str(Path(p).resolve()):sha(p) for p in paths}
    chain,route_inputs=route_chain(args.route_proof);watched.update(route_inputs)
    provenance=[]
    for paths,h in (([args.baseline_exceptions]+args.baseline_union,chain['BaselineADFSHA256']),
                    ([args.candidate_exceptions]+args.candidate_union,chain['CandidateADFSHA256'])):
        provenance += [bind_report(path,h,watched) for path in paths]
    plan=json.loads(Path(args.query_plan).read_text());sources=set(plan['Sources']);endpoints=set(plan['Endpoints'])
    require(len(sources)==len(plan['Sources']) and len(endpoints)==len(plan['Endpoints']), 'query plan duplicates')
    query=Path(plan['QueryBody']);require(sha(query)==plan['QueryBodySHA256'],'query body hash drift')
    watched[str(query.resolve())]=sha(query)
    context=physical_context(args.physical_arguments_json,chain,watched) if args.physical_arguments_json else None
    old=read_exceptions(args.baseline_exceptions);new=read_exceptions(args.candidate_exceptions)
    ou=read_union(args.baseline_union,sources,endpoints);nu=read_union(args.candidate_union,sources,endpoints)
    result=compare_records(old,new,ou,nu,True,context)
    require(all(sha(p)==h for p,h in watched.items()),'input drift during audit')
    return {'Schema':'camera-vga-exception-union-comparison-v1','AuditPassed':True,
            'AuditedUTC':datetime.now(timezone.utc).isoformat(), **result,'RouteChain':chain,
            'BaselineExceptions':str(Path(args.baseline_exceptions).resolve()),
            'CandidateExceptions':str(Path(args.candidate_exceptions).resolve()),
            'RepresentativeChangeSupportingEvidence':context,
            'BaselineUnionRecords':len(ou),'CandidateUnionRecords':len(nu),'ReportProvenance':provenance,'InputSHA256':watched,
            'ToolSHA256':{str(Path(p).resolve()):sha(p) for p in (__file__,hold.__file__,native.__file__,physical.__file__)},
            'FalsePathScopeApproved':False,'TimingAccepted':False,'HardwareAccessed':False,
            'Limits':'Only non-false exception membership/data-delay equivalence. Exact reset false paths, complete timing summaries, provenance and functional placement remain independent checks.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-exceptions','candidate-exceptions','query-plan','output'):
        p.add_argument('--'+name,type=Path,required=True)
    for name in ('baseline-union','candidate-union','route-proof'):
        p.add_argument('--'+name,type=Path,action='append',required=True)
    p.add_argument('--physical-arguments-json',type=Path)
    args=p.parse_args();require(not args.output.exists(),'fresh output required')
    result=audit(args)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:result[k] for k in ('AuditPassed','ChangedIdentityCount','ComparedUnionPathCount','PrintedRoundingPathCount')}))


if __name__=='__main__':main()
