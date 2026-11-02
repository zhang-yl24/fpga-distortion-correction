"""Pure current raw720 reset-only effect audit of actual fresh native exports."""
import argparse
import json
from pathlib import Path
import re
import sys

import camera720_raw_reset_fast_inspect as final
import camera720_raw_derived_inspect as baseline
import camera720_raw_reset_current as current
import audit_raw_camera_delay_reset_effect as raw_semantics
import audit_camera_vga_calibrated_reset_effect as semantics
import audit_camera_vga_routes as routes
import audit_camera_vga_route_reset_scope as route_scope

physical=final.physical
prep, require, sha=final.prep,final.require,final.sha
SELF=Path(__file__).resolve()
SCHEMA='camera720-current-raw-reset-fast-effect-v1'

def bind_file(watched,path,expected=None):
    return current.add(watched,path,expected)

def reference(path):
    path=Path(path).resolve()
    return {'Path':str(path),'SHA256':sha(path)}

def tools(watched):
    for module in list(sys.modules.values()):
        filename=getattr(module,'__file__',None)
        if filename:
            path=Path(filename).resolve()
            if path.suffix=='.py' and path.is_relative_to(prep.PROJECT/'tools'):
                bind_file(watched,path)
    bind_file(watched,SELF)

def artifact(path,receipt,name,watched):
    candidates=[Path(path).parent/n for n in receipt['Artifacts']
                if Path(n).name==name and 'report_path_timing' not in Path(n).parts]
    require(len(candidates)==1,'one exact bound artifact required: '+name)
    p=candidates[0]
    return bind_file(watched,p,receipt['Artifacts'][p.relative_to(Path(path).parent).as_posix()])

def graph(text):
    require(re.findall(r'(?m)^module\s+(\w+)\b',text)==[prep.TARGET], 'exact current720 raw top required')
    adapted,count=re.subn(r'(?m)^(module\s+)'+re.escape(prep.TARGET)+r'\b',
                         lambda m:m[1]+raw_semantics.prep.TARGET,text,count=1)
    require(count==1,'one explicit top-header adaptation required')
    return raw_semantics.functional(adapted)

def audit_value(application_path,export_path):
    watched={};tools(watched)
    application_path=final.canonical(application_path,prep.WORK)
    export_path=final.canonical(export_path,prep.WORK)
    new,new_inputs=final.bind_receipt(export_path);current.merge(watched,new_inputs)
    require(new['SourceReceipt']==reference(application_path), 'final source receipt differs')
    require(watched.get(application_path)==sha(application_path), 'application absent from verified authority closure')
    application=physical.read(application_path)
    require(application['Mode']=='save-reset-only' and physical.execution_ok(application)
            and application['ExactRouteCommands']==[], 'only clean reset-only application accepted')
    old_path=Path(application['SourceReceipt']['Path'])
    require(watched.get(old_path)==current.EXPORT_SHA==sha(old_path), 'exact baseline export not authority-bound')
    old=current.read(old_path)
    current.exact_export(old)
    require(old['ExecutionPassed'] is True and old['InputDrift']==[] and old['Diagnostics']==[]
            and old['InputADFUnchanged'] is True, 'sealed baseline export was not clean')
    require(baseline.scan_diagnostics(old_path.parent)==[], 'baseline native diagnostic drift')
    for name,digest in old['Artifacts'].items():
        p=(old_path.parent/name).resolve()
        require(watched.get(p)==digest==sha(p), 'baseline artifact absent from authority closure')
    require(old['Mode']==new['Mode']=='export'
            and old['SourceADFSHA256']==application['SourceADFSHA256']==current.SOURCE_SHA
            and new['SourceADFSHA256']==application['ResultADFSHA256']
            and new['SourceReceipt']==reference(application_path)
            and old['BuildPlanSHA256']==new['BuildPlanSHA256']==application['BuildPlanSHA256'],
            'native export/source mutation chain differs')
    scope_path=Path(application['ResetScopePlan']['Path'])
    require(sha(scope_path)==application['ResetScopePlan']['SHA256'],'reset scope drift')
    scope=current.read(scope_path)
    br=artifact(old_path,old,prep.TARGET+'.rtr',watched)
    cr=artifact(export_path,new,prep.TARGET+'.rtr',watched)
    be=artifact(old_path,old,prep.TARGET+'_exception.rtr',watched)
    ce=artifact(export_path,new,prep.TARGET+'_exception.rtr',watched)
    inv=current.reset.inventory(br)
    queries,_,_=current.reset.native_scope(inv)
    require(queries==application['NativeQueries']==scope['NativeQueries'], 'actual baseline reset inventory differs')
    old_net=bind_file(watched,old['Netlist']['Path'],old['Netlist']['SHA256'])
    new_net=bind_file(watched,new['Netlist']['Path'],new['Netlist']['SHA256'])
    before_graph,after_graph=graph(old_net.read_text(encoding='utf-8-sig')),graph(new_net.read_text(encoding='utf-8-sig'))
    require(before_graph==after_graph,'reset application changed functional graph/declarations/FF placement')
    bt,bc=semantics.pure_physical.summaries(br);ct,cc=semantics.pure_physical.summaries(cr)
    require(bc==cc,'clock definitions and loads changed')
    totals,changes=semantics.compare_timing(bt,ct,inv)
    with be.open(encoding='gb18030') as stream:old_false=semantics.native.parse_false_paths(stream)
    with ce.open(encoding='gb18030') as stream:new_false=semantics.native.parse_false_paths(stream)
    false_counts=semantics.compare_false_paths(old_false,new_false,inv)
    nonfalse=semantics.nonfalse_equal(semantics.exception_syntax.read_exceptions(be),
                                    semantics.exception_syntax.read_exceptions(ce))
    old_dump=bind_file(watched,application['BaselineRouteDump']['Path'],application['BaselineRouteDump']['SHA256'])
    new_dump=artifact(application_path,application,'route-dump.txt',watched)
    a,b=routes.inspect(old_dump,{}),routes.inspect(new_dump,{})
    sa,sb=route_scope.constraint_separated(old_dump),route_scope.constraint_separated(new_dump)
    comparison=semantics.compare_routes(a,b,sa,sb)
    require(a['ExcludedBlockSHA256']['FILETABLE']==b['ExcludedBlockSHA256']['FILETABLE'],
            'reset changed source file table')
    comparison['FileTableUnchanged']=True
    bind_file(watched,application_path);bind_file(watched,export_path);tools(watched)
    require(not final.drift(watched),'reset effect input drift')
    result={'Schema':SCHEMA,'Target':prep.TARGET,'CreatedUTC':prep.utc(),
        'Producer':reference(SELF),'AuditPassed':True,'ResetEffectVerified':True,
        'BuildPlan':application['BuildPlan'],'BuildPlanSHA256':application['BuildPlanSHA256'],
        'Application':reference(application_path),'SourceReceipt':reference(export_path),
        'SourceAuthority':new['SourceAuthority'],
        'BaselineExport':reference(old_path),'FinalExport':reference(export_path),
        'SourceADF':reference(application['SourceADF']),'ResultADF':reference(application['ResultADF']['Path']),
        'CandidateADFSHA256':new['SourceADFSHA256'],'ResetScopePlan':application['ResetScopePlan'],
        'VendorBasis':application['VendorBasis'],'NativeQueryReceipt':application['NativeQueryReceipt'],
        'BaselineFunctionalComparison':application['BaselineFunctionalComparison'],
        'BaselineSerialization':application['BaselineSerialization'],
        'FunctionalGraphIdentical':True,'AllFFPlacementsIdentical':True,'ModuleDeclarationsIdentical':True,
        'ActualCellCount':len(before_graph['Cells']),'ActualFFCount':len(before_graph['FFPlacement']),
        'FunctionalPartSHA256':{k:semantics.digest(v) for k,v in before_graph.items()},
        'RouteComparison':comparison,'RoutingUnchanged':True,
        'ExactResetExceptionUnionVerified':True,'NoDataFalsePaths':True,
        'ClockDefinitionsAndLoadsUnchanged':True,'DataTimingChecksPreserved':True,
        'AllInternalChecksMet':True,'CornerSummaries':totals,'TimingSummaryChanges':changes,
        'FalsePathCounts':false_counts,'NonFalseExceptionComparison':nonfalse,
        'VendorSameConfigurationVerified':True,'RegisteredEntryContractVerified':True,
        'InternalResetContractVerified':True,'InputSHA256':{str(p):h for p,h in watched.items()},
        'BuildDiagnosticsCleared':False,'TimingAccepted':False,'HardwareReleaseAllowed':False,
        'CDCPhysicalAccepted':False,'ExternalACAccepted':False,'HardwareAccessed':False,
        'EDAExecuted':False,'OpticalCorrectionAccepted':False,
        'Limits':'Actual current raw native reset effect only: exact recovery exception union, unchanged routes and full functional/placement equality. Build diagnostic disposition, CDC, external IO, bitstream and hardware release remain separate.'}
    return json.loads(json.dumps(result)),watched

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--application',type=Path,required=True)
    parser.add_argument('--export',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.absolute()
    require(output==output.resolve() and output.is_relative_to(prep.WORK)
            and output.parent.is_dir() and output.suffix=='.json' and not output.exists(),
            'fresh in-workspace JSON effect output required')
    value,_=audit_value(args.application,args.export)
    inspect=final.inspect
    inspect.diagnostic.write(output,value)
    require(current.read(output)==value,'effect output readback differs')
    print(json.dumps({k:value[k] for k in ('AuditPassed','AllInternalChecksMet','ExactResetExceptionUnionVerified','NoDataFalsePaths')}))

if __name__=='__main__':main()
