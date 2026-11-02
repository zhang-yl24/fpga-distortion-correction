"""Prove exact reset-only effects on this current view-toggle candidate.

Full native double-corner STA, exact false-path union, all functional cells and
FF sites, and every physical route are rechecked from bound native evidence.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

import camera720_view_toggle_reset_apply as physical
import camera720_view_toggle_final_inspect as inspect
import audit_camera_vga_calibrated_reset_effect as semantics

SELF=Path(__file__).resolve()
SCHEMA='camera720-view-toggle-reset-effect-v1'
TARGET,require,sha,read=physical.TARGET,physical.require,physical.sha,physical.read
add,merge,ref=physical.add,physical.merge,physical.ref
KEY_ENDPOINT=re.compile(r'^view_control/key_sync\[0\]/[A-Za-z0-9_]+/D$')


def false_paths(path):
    """Separate actual asynchronous KEY1 records from clocked reset records."""
    sections={};pending=None;section=None;block=[]
    def finish():
        if not block:return
        text=''.join(block)
        start=re.findall(r'^Startpoint\s*:\s*(.+?)\s*$',text,re.M)
        require(len(start)==1,'missing or ambiguous false-path startpoint')
        if start[0]=='key1_n (port)':
            endpoint=re.findall(r'^Endpoint\s*:\s*(\S+)\s*$',text,re.M)
            clocks=re.findall(r'^ Clock (\S+) \((rising|falling) edge\)',text,re.M)
            kind=section[1];corner=section[0]
            require(kind in ('setup','hold') and len(endpoint)==1 and KEY_ENDPOINT.fullmatch(endpoint[0])
                    and clocks==[('ddrphy_sysclk','rising')] and
                    re.findall(r'^Path Group\s*:\s*(\S+)\s*$',text,re.M)==['ddrphy_sysclk']
                    and re.findall(r'^Path Type\s*:\s*(max|min) \((slow|fast) corner\)\s*$',text,re.M)==
                        [('max' if kind=='setup' else 'min',corner)]
                    and re.search(r'^Path Class\s*:\s*false timing path\s*$',text,re.M)
                    and 'Timing Exception  :  False Path' in text,
                    'KEY1 false path reaches another target, clock or exception kind')
            transitions=re.findall(r'^ C23\s+[-+0-9.]+\s+[-+0-9.]+\s+([rf])\s+key1_n \(port\)\s*$',text,re.M)
            require(len(transitions)==1,'KEY1 pad source transition evidence missing')
            normalized=semantics.exception_syntax.normalized(block)
            sections[section]['Key'].append({'Endpoint':endpoint[0],'Transition':transitions[0],
                                            'SHA256':semantics.digest(normalized)})
        else:
            sections[section]['Reset'].append(semantics.native.path_record(block,expected_kind=section[1]))
    with Path(path).open(encoding='gb18030') as stream:
        for line in stream:
            header=semantics.native.EX_HEADER.fullmatch(line.rstrip('\r\n'))
            if header:
                finish();block=[];section=None
                match=semantics.native.EX_KIND.fullmatch(header[1]);pending=match[1] if match else None
                continue
            if pending:
                corner=re.fullmatch(r'\| (Slow|Fast) Corner\s*',line)
                if corner:
                    section=(corner[1].lower(),pending);pending=None
                    require(section not in sections,'duplicate false-path section')
                    sections[section]={'Key':[],'Reset':[]}
                    continue
            if section is None:continue
            if line.startswith('Startpoint'):
                finish();block=[line]
            elif block:block.append(line)
    finish()
    require(set(sections)=={(c,k) for c in ('slow','fast') for k in ('setup','hold','recovery','removal')},
            'eight complete false-path sections required')
    return sections


def compare_false_paths(before,after,inventory):
    require(set(before)==set(after),'false-path section inventory differs')
    endpoints=set();key_counts={}
    for section,old in before.items():
        require(not old['Reset'],'baseline contains unrelated clocked false path')
        key=old['Key'];now=after[section]['Key']
        expected=2 if section[1] in ('setup','hold') else 0
        # PDS may report two capture-delay/edge representatives with the same
        # source-pad transition. Preserve those exact distinct native bodies;
        # do not invent r/f source coverage that the report did not provide.
        require(len(key)==expected and len({x['SHA256'] for x in key})==expected
                and all(x['Transition'] in ('r','f') for x in key),
                'KEY1 baseline has missing, duplicate or invalid native variants')
        require(Counter(x['SHA256'] for x in key)==Counter(x['SHA256'] for x in now),
                'existing KEY1 pad exception path changed')
        endpoints.update(x['Endpoint'] for x in key)
        key_counts['_'.join(section)]=len(key)
    require(len(endpoints)==1,'KEY1 baseline reaches more than first synchronizer D')
    expected={c:{semantics.native.path_identity(p) for check in inventory['Corners'][c]['Checks']
                 for p in check['NativeVariants']} for c in ('slow','fast')}
    reset_counts=semantics.native.validate_exception_sets(
        {s:v['Reset'] for s,v in after.items()},expected)
    return {'PreservedKEY1Endpoint':next(iter(endpoints)),'PreservedKEY1Paths':key_counts,
            'AddedExactResetPaths':reset_counts,'NoOtherDataFalsePaths':True}


def audit_value(application_path,export_path):
    application_path,export_path=Path(application_path).resolve(),Path(export_path).resolve()
    application,watched=physical.bind_completed(application_path)
    final,inputs=inspect.bind_receipt(export_path);merge(watched,inputs)
    require(final['Mode']=='export' and final['SourceReceipt']==ref(application_path)
            and final['SourceADFSHA256']==application['ResultADFSHA256']
            and final['BuildPlanSHA256']==application['BuildPlanSHA256'],
            'final export belongs to another reset derivative')
    baseline_path=Path(application['BaselineExport']['Path'])
    baseline,inputs=inspect.bind_receipt(baseline_path);merge(watched,inputs)
    require(baseline['Mode']=='export' and baseline['SourceADFSHA256']==application['SourceADFSHA256'],
            'baseline export differs from pre-reset candidate')
    before_net=physical.artifact(baseline_path,baseline,TARGET+'_sim.v',watched)
    after_net=physical.artifact(export_path,final,TARGET+'_sim.v',watched)
    before_graph,after_graph=physical.functional(before_net),physical.functional(after_net)
    require(before_graph==after_graph,'reset save changed functional graph, module declarations or FF placement')
    br=physical.artifact(baseline_path,baseline,TARGET+'.rtr',watched)
    cr=physical.artifact(export_path,final,TARGET+'.rtr',watched)
    be=physical.artifact(baseline_path,baseline,TARGET+'_exception.rtr',watched)
    ce=physical.artifact(export_path,final,TARGET+'_exception.rtr',watched)
    inventory,_=physical.proof.report_inventory(br)
    queries,_,_,commands=physical.proof.exact_scope(inventory)
    require(inventory==application['Inventory'] and queries==application['NativeQueries']
            and commands==application['ExactResetCommands'], 'pre-reset native recovery scope changed')
    bt,bc=physical.timing.summaries(br);ct,cc=physical.timing.summaries(cr)
    require(bc==cc,'clock definitions or loads changed')
    summaries,changes=semantics.compare_timing(bt,ct,inventory)
    counts=compare_false_paths(false_paths(be),false_paths(ce),inventory)
    other=semantics.nonfalse_equal(semantics.exception_syntax.read_exceptions(be),
                                  semantics.exception_syntax.read_exceptions(ce))
    routing=physical.compare_routes(application['BaselineRouteDump']['Path'],
                                     application_path.parent/'route-dump.txt')
    require(routing==application['RouteComparison'],'reset routing comparison changed')
    for module in (physical,inspect,semantics,semantics.native,semantics.exception_syntax,
                   physical.timing,physical.proof,physical.route_semantics): add(watched,module.__file__)
    add(watched,SELF)
    require(not inspect.drift(watched),'reset effect evidence drift')
    result={'Schema':SCHEMA,'Target':TARGET,'Producer':ref(SELF),'AuditPassed':True,
        'ApplicationReceipt':ref(application_path),'BaselineExportReceipt':ref(baseline_path),
        'CandidateExportReceipt':ref(export_path),'CandidateADFSHA256':final['SourceADFSHA256'],
        'SourceADF':ref(application['SourceADF']),'ResultADF':ref(application['ResultADF']['Path']),
        'FunctionalGraphIdentical':True,'AllFFPlacementsIdentical':True,'ModuleDeclarationsIdentical':True,
        'ActualCellCount':len(before_graph['Cells']),'ActualFFCount':len(before_graph['FFPlacement']),
        'FunctionalPartSHA256':{k:semantics.digest(v) for k,v in before_graph.items()},
        'RoutingUnchanged':True,'RouteComparison':routing,'ExactResetExceptionUnionVerified':True,
        'NoDataFalsePaths':True,'NoNewDataFalsePaths':True,'ExistingKEY1PadExceptionPreserved':True,
        'DataTimingChecksPreserved':True,'ClockDefinitionsAndLoadsUnchanged':True,
        'AllInternalChecksMet':True,'CornerSummaries':summaries,'TimingSummaryChanges':changes,
        'FalsePathCounts':counts,'NonFalseExceptionComparison':other,
        'LogicalResetChecksByCorner':{c:r['LogicalChecks'] for c,r in inventory['Corners'].items()},
        'NativeResetEdgeVariantsByCorner':{c:r['NativeVariants'] for c,r in inventory['Corners'].items()},
        'InputSHA256':{str(p):h for p,h in watched.items()},
        'EDAExecuted':False,'HardwareAccessed':False,'HardwareReleaseAllowed':False,'TimingAccepted':False,
        'Limits':'Current digital reset-only effect. External AC, CDC, bitstream and board observations remain separate.'}
    return result,watched


def verify(path):
    path=Path(path).resolve();saved=read(path)
    require(saved.get('Schema')==SCHEMA and saved.get('Target')==TARGET,'wrong reset effect identity')
    actual,watched=audit_value(saved['ApplicationReceipt']['Path'],saved['CandidateExportReceipt']['Path'])
    require(actual==saved,'reset effect differs from full recomputation');add(watched,path)
    return actual,watched


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--application',type=Path,required=True)
    p.add_argument('--export',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();require(out.parent.is_dir() and out.is_relative_to(physical.build.WORK)
        and not out.exists(),'fresh in-workspace effect JSON required')
    value,_=audit_value(a.application,a.export);physical.build.write(out,value)
    require(read(out)==value,'effect output readback differs')
    print(json.dumps({'Output':str(out),'AuditPassed':True,'AllInternalChecksMet':True,
                     'CornerSummaries':value['CornerSummaries']}));return 0


if __name__=='__main__':raise SystemExit(main())
