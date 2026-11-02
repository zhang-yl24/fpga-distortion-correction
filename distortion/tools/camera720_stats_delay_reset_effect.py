"""CPU audit of exact statistics reset effects using fresh native evidence."""
import argparse
import json
from pathlib import Path

import camera720_stats_delay_reset_apply as physical
import audit_camera_vga_calibrated_reset_effect as semantics

proof,inspect,prep=physical.proof,physical.inspect,physical.prep
require,sha,read,add,ref=physical.require,physical.sha,physical.read,physical.add,physical.ref
SELF=Path(__file__).resolve()
SCHEMA='camera720-calibrated-stats-delay-reset-effect-v1'


def audit_value(application_path,export_path):
    import camera720_stats_delay_final_inspect as final_provider
    watched={};application_path=Path(application_path).resolve();export_path=Path(export_path).resolve()
    application=physical.bind_completed(application_path,watched)
    final_schema=read(export_path).get('Schema')
    require(final_provider.SCHEMA==final_schema and Path(final_provider.__file__).resolve()==prep.PROJECT/'tools/camera720_stats_delay_final_inspect.py',
            'unexpected final native provider')
    final,inputs=final_provider.bind_receipt(export_path);proof.merge(watched,inputs)
    require(final['Mode']=='export' and final['SourceReceipt']==ref(application_path)
            and final['SourceADFSHA256']==application['ResultADFSHA256'], 'final export belongs to another reset result')
    old_path=physical.binding(application['BaselineExport'],watched)
    old,inputs=inspect.bind_receipt(old_path);proof.merge(watched,inputs)
    require(old['Mode']=='export' and old['SourceADFSHA256']==application['SourceADFSHA256'], 'baseline export differs')
    old_net=add(watched,old['Netlist']['Path'],old['Netlist']['SHA256'])
    new_net=add(watched,final['Netlist']['Path'],final['Netlist']['SHA256'])
    old_graph,new_graph=physical.functional(old_net),physical.functional(new_net)
    require(old_graph==new_graph,'reset application changed cells, declarations or FF placements')
    br=physical.artifact(old_path,old,prep.TARGET+'.rtr',watched)
    cr=physical.artifact(export_path,final,prep.TARGET+'.rtr',watched)
    be=physical.artifact(old_path,old,prep.TARGET+'_exception.rtr',watched)
    ce=physical.artifact(export_path,final,prep.TARGET+'_exception.rtr',watched)
    inv,_=proof.inventory(br)
    queries,_,commands=proof.exact_scope(inv)
    require(queries==application['NativeQueries'] and commands==application['ExactResetCommands'], 'baseline recovery scope differs')
    bt,bc=physical.timing.summaries(br);ct,cc=physical.timing.summaries(cr)
    require(bc==cc,'clock definitions or loads changed')
    summaries,changes=semantics.compare_timing(bt,ct,inv)
    with be.open(encoding='gb18030') as stream:before=semantics.native.parse_false_paths(stream)
    with ce.open(encoding='gb18030') as stream:after=semantics.native.parse_false_paths(stream)
    false=semantics.compare_false_paths(before,after,inv)
    nonfalse=semantics.nonfalse_equal(semantics.exception_syntax.read_exceptions(be),
                                    semantics.exception_syntax.read_exceptions(ce))
    old_dump=physical.binding(application['BaselineRouteDump'],watched)
    new_dump=physical.artifact(application_path,application,'route-dump.txt',watched)
    route=physical.compare_routes(old_dump,new_dump)
    require(route==application['RouteComparison'],'reset route comparison changed')
    for module in (inspect,final_provider,physical,semantics,semantics.pure_physical,semantics.native,
                   semantics.exception_syntax,physical.io,physical.io.structure):add(watched,module.__file__)
    add(watched,SELF);add(watched,export_path)
    require(not inspect.drift(watched),'reset effect input drift')
    result={'Schema':SCHEMA,'Target':prep.TARGET,'Producer':ref(SELF),'AuditPassed':True,
        'ApplicationReceipt':ref(application_path),'BaselineExportReceipt':ref(old_path),'CandidateExportReceipt':ref(export_path),
        'SourceADF':ref(application['SourceADF']),'ResultADF':ref(application['ResultADF']['Path']),
        'CandidateADFSHA256':final['SourceADFSHA256'],'ResetProof':application['ResetProof'],
        'FunctionalGraphIdentical':True,'AllFFPlacementsIdentical':True,'ModuleDeclarationsIdentical':True,
        'ActualCellCount':len(old_graph['Cells']),'ActualFFCount':len(old_graph['FFPlacement']),
        'FunctionalPartSHA256':{k:semantics.digest(v) for k,v in old_graph.items()},
        'RouteComparison':route,'RoutingUnchanged':True,'ExactResetExceptionUnionVerified':True,
        'NoDataFalsePaths':True,'ClockDefinitionsAndLoadsUnchanged':True,'DataTimingChecksPreserved':True,
        'AllInternalChecksMet':True,'CornerSummaries':summaries,'TimingSummaryChanges':changes,
        'FalsePathCounts':false,'NonFalseExceptionComparison':nonfalse,
        'LogicalResetChecksByCorner':{c:r['LogicalChecks'] for c,r in inv['Corners'].items()},
        'NativeResetEdgeVariantsByCorner':{c:r['NativeVariants'] for c,r in inv['Corners'].items()},
        'InputSHA256':{str(p):h for p,h in sorted(watched.items(),key=lambda x:str(x[0]))},
        'BuildDiagnosticsCleared':False,'TimingAccepted':False,'HardwareReleaseAllowed':False,
        'CDCPhysicalAccepted':False,'ExternalACAccepted':False,'HardwareAccessed':False,'EDAExecuted':False,
        'Limits':'Exact current reset-only digital effects, full functional and FF-placement equality, unchanged routes and unaffected timed path summaries. External AC, CDC, bitstream and board observations remain separate.'}
    return result,watched


def verify(path):
    saved=read(path);require(saved.get('Schema')==SCHEMA and saved.get('Target')==prep.TARGET,'wrong reset effect identity')
    watched={};application=physical.binding(saved['ApplicationReceipt'],watched)
    export=physical.binding(saved['CandidateExportReceipt'],watched)
    actual,inputs=audit_value(application,export);proof.merge(watched,inputs)
    require(actual==saved,'reset effect differs from recomputation');add(watched,path)
    return actual,watched


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--application',type=Path,required=True)
    p.add_argument('--export',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve();require(out.parent.is_dir() and out.is_relative_to(prep.WORK) and not out.exists(),'fresh effect JSON required')
    value,_=audit_value(a.application,a.export)
    data=json.dumps(value,indent=2,allow_nan=False)+'\n'
    with out.open('x',encoding='utf-8',newline='\n') as stream:stream.write(data)
    print(json.dumps({'Output':ref(out),'AuditPassed':value['AuditPassed'],'AllInternalChecksMet':value['AllInternalChecksMet'],
                      'LogicalResetChecksByCorner':value['LogicalResetChecksByCorner']}))


if __name__=='__main__':main()
