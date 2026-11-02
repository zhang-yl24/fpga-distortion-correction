"""Exact source-metadata reassessment of the completed calibrated hold save.

The original failed receipt is retained. Only numeric source locations outside
CDB entries and the sole empty FILEMAP are accepted as serialization metadata.
All route, CDB definition/reference and other semantic bytes are rechecked.
This module has no EDA or hardware execution entry point.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

import camera720_calibrated_hold_route as original

inspect,prep,require,sha=original.inspect,original.prep,original.require,original.sha
add,ref,read=original.add,original.ref,original.read
SELF=Path(__file__).resolve()
SCHEMA='camera720-calibrated-route-reassessment-v1'
SOURCE_RECEIPT_SHA='f5c7a2e4df273a54a8bd72682153eb51578ac0d9e4df016a8180c0fed42cb489'
SOURCE_ERROR='ValueError: source file table changed beyond supported serialization'
SOURCE_RESULT_ADF='826441df556ae5e4e1541b2a5efa55e420f80abaade153fb91bfa0355fec55c4'


def merge_inputs(watched,bound):
    for name,h in bound.items():
        p=Path(name).absolute()
        require(p==p.resolve() and p.is_file() and re.fullmatch(r'[0-9a-f]{64}',h)
                and sha(p)==h and (p not in watched or watched[p]==h),'verified input closure drift')
        watched[p]=h


def metadata_change(before,after):
    a,b=before['ExcludedBlocks']['FILETABLE'],after['ExcludedBlocks']['FILETABLE']
    require(a['Tokens']==['(','FILETABLE','(','FILEMAP','2','""',')',')']
            and b['Tokens']==['(','FILETABLE',')'], 'only the actual sole empty FILEMAP removal is supported')
    rows=before['SourceAnnotationsOutsideCDBEntries']
    require(rows and after['SourceAnnotationsOutsideCDBEntries']==[],
            'only complete removal of actual outside-CDB source locations supported')
    counts=Counter()
    for row in rows:
        tokens=row['Tokens']
        require(len(tokens)==4 and tokens[0]=='(' and tokens[3]==')'
                and tokens[1] in ('FILEID','LINENUM') and re.fullmatch(r'\d+',tokens[2]),
                'unexpected source metadata payload')
        counts[tokens[1]]+=1
    require(counts['FILEID']==counts['LINENUM'],'source file/line metadata inventory differs')
    return {'ExactEmptyFileMapRemoval':True,'BeforeFileTableTokens':a['Tokens'],
        'AfterFileTableTokens':b['Tokens'],'BeforeFileTableTokenSHA256':a['TokenSHA256'],
        'AfterFileTableTokenSHA256':b['TokenSHA256'],'RemovedOutsideCDBMetadataCounts':dict(counts),
        'RemainingOutsideCDBMetadataCount':0,'CDBEntrySourceLocationsSeparatelyComparedInFull':True,
        'FunctionalOrTimingExceptionChangePermitted':False}


def compare_route_dumps(before_path,after_path,targets,requested):
    before=original.routes.inspect(Path(before_path),targets)
    after=original.routes.inspect(Path(after_path),targets)
    require(set(before['NetAnnotations'])==set(after['NetAnnotations']),'route inventory changed')
    changed={n for n,h in before['NetAnnotations'].items() if after['NetAnnotations'][n]!=h}
    require({original.routes.annotation_name(n) for n in changed}=={t['Net'] for t in targets},
            'unrequested route changed or requested route did not change')
    checks=[]
    require(len(targets)==len(requested)==1,'one measured terminal branch required')
    for t,row in zip(targets,requested):
        a,b=before['BranchInventory'][t['Net']],after['BranchInventory'][t['Net']]
        require(a['LogicalConnections']==b['LogicalConnections'] and set(a['Leaves'])==set(b['Leaves']),
                'logical connection or physical leaf changed')
        for leaf,chain in a['Leaves'].items():
            if leaf!=t['ToRoutePin']:require(chain==b['Leaves'][leaf],'unrequested sibling changed')
        chain=b['Leaves'][t['ToRoutePin']];pins=row['Pins'].rstrip(';').split('>')
        require(chain!=a['Leaves'][t['ToRoutePin']] and any(chain[i:i+len(pins)]==pins for i in range(len(chain)-len(pins)+1)),
                'requested contiguous detour absent')
        checks.append({'Net':t['Net'],'Before':a,'After':b,'UnrequestedSiblingsPreserved':len(a['Leaves'])-1})
    parser=original.serialization_module();a,b=parser.extract(Path(before_path)),parser.extract(Path(after_path))
    comparison=parser.reference_comparison(a,b)
    for key in ('DefinitionsEqual','ParentObjectsEqual','AllFullEntriesEqualWithinParent',
                'AllResolvedEntriesEqualWithinParent','OtherNonRouteTokensEqual'):
        require(comparison[key] is True,'nonroute semantic change: '+key)
    require(a['ExcludedBlocks']['CDB']['TokenSHA256']==b['ExcludedBlocks']['CDB']['TokenSHA256'],
            'constraint definitions changed')
    metadata=metadata_change(a,b)
    return {'Passed':True,'ChangedNets':sorted(changed),'RouteCount':len(before['NetAnnotations']),
        'AllOtherRoutesUnchanged':True,'FunctionalAndPlacementSemanticsUnchanged':True,
        'FullCDBDefinitionsAndPerParentReferencesIdentical':True,
        'CDBDefinitionCount':comparison['DefinitionCountBefore'],'CDBReferenceCount':comparison['EntryCountBefore'],
        'CDBParentCount':len(comparison['ParentChecks']),
        'BeforeOtherSemanticSHA256':a['OtherNonRouteTokensSHA256'],
        'AfterOtherSemanticSHA256':b['OtherNonRouteTokensSHA256'],
        'SourceMetadataDisposition':metadata,'BranchChecks':checks,'TimingAcceptanceImplied':False}


def bind_original(path,watched):
    path=inspect.canonical(path,prep.WORK);add(watched,path,SOURCE_RECEIPT_SHA)
    work=path.parent;value=read(path)
    require(value.get('Schema')==original.SCHEMA and value.get('ExecutionPassed') is False
            and value.get('Error')==SOURCE_ERROR and 'RouteComparison' not in value,
            'only the exact metadata-rejected original receipt is eligible')
    native_only={**value,'Error':None,'RouteComparison':{'Passed':True}}
    require(original.execution_ok(native_only),'native save had another execution failure')
    plan,bound=original.bound_plan(work/'stage-plan.json',False)
    merge_inputs(watched,bound)
    require(all(value.get(k)==v for k,v in plan.items()) and value['StagePlanSHA256']==sha(work/'stage-plan.json'),
            'original receipt differs from exact recipe')
    require(value['Artifacts']==original.artifact_hashes(work),'original artifact inventory differs')
    for name,h in value['Artifacts'].items():add(watched,inspect.canonical(work/name,work),h)
    require(inspect.scan_diagnostics(work)==[],'original native critical/error diagnostic')
    log=(work/'stdout.log').read_text(encoding='gb18030',errors='replace')
    require(inspect.diagnostic.stage_events(log)==[] and original.MARKER in log,'native stage identity changed')
    require(sha(work/'post-init.adf')==original.ORIGINAL_ADF
            and sha(work/'input.adf')==sha(work/'saved-route.adf')==SOURCE_RESULT_ADF==value['ResultADFSHA256'],
            'original initialization/save chain differs')
    for name in ('input.adf','post-init.adf','saved-route.adf'):
        p=work/name
        require(value['ADFReadback'][name]=={'Path':str(p),'SHA256':sha(p),'Bytes':p.stat().st_size},'ADF readback differs')
    require(value['ResultADF']==value['ADFReadback']['input.adf'],'result ADF identity differs')
    return value


def audit_value(path):
    path=Path(path).resolve();watched={};source=bind_original(path,watched)
    dump=path.parent/'route-dump.txt'
    comparison=compare_route_dumps(source['OriginalRouteDump']['Path'],dump,source['MeasuredTargets'],source['Routes'])
    add(watched,SELF);add(watched,original.__file__)
    require(not inspect.drift(watched),'reassessment evidence drift')
    keys=('Target','BuildPlan','BuildPlanSHA256','SourceADF','SourceADFSHA256','ResultADF','ResultADFSHA256',
          'BuildDiagnosticsReview','BuildExecutionCompletedWithoutError','BuildDiagnosticsCleared','OriginalRouteDump',
          'OriginalExportReceipt','Routes','MeasuredTargets','ExactRouteCommands','ExactResetCommands','ResetProof')
    value={'Schema':SCHEMA,**{k:source[k] for k in keys},'Producer':ref(SELF),
        'OriginalExecutionReceipt':ref(path),'SourceExecutionPassed':False,'SourceExecutionError':SOURCE_ERROR,
        'ValidationMethod':{'Function':'camera720_calibrated_route_reassessment.audit_value','Producer':ref(SELF)},
        'OriginalReceiptUnmodified':True,'ReassessmentPassed':True,'NativeRouteDump':ref(dump),
        'RouteComparison':comparison,'EDAExecuted':False,'HardwareAccessed':False,'TimingAccepted':False,
        'HardwareReleaseAllowed':False,'OpticalCorrectionAccepted':False,
        'InputSHA256':{str(p):h for p,h in sorted(watched.items(),key=lambda row:str(row[0]))}}
    return value,watched


def bind_completed(path,watched):
    """Bind the exact completed audit and every byte; callers bind its explicit SHA.

    The first audit_value performs all semantic parsing. Subsequent native-stage
    boundaries rehash its entire closure and preserve the exact original receipt,
    plan, artifacts and candidate, without repeating the expensive parser.
    """
    path=inspect.canonical(path,prep.WORK);saved=read(path)
    require(saved.get('Schema')==SCHEMA and saved.get('Target')==prep.TARGET and saved.get('ReassessmentPassed') is True,
            'current route reassessment required')
    require(saved.get('Producer')==ref(SELF) and saved.get('ValidationMethod')=={
        'Function':'camera720_calibrated_route_reassessment.audit_value','Producer':ref(SELF)},'audit producer changed')
    require(saved.get('SourceExecutionPassed') is False and saved.get('SourceExecutionError')==SOURCE_ERROR
            and saved.get('OriginalReceiptUnmodified') is True,'original failed status must remain explicit')
    for key in ('EDAExecuted','HardwareAccessed','TimingAccepted','HardwareReleaseAllowed','OpticalCorrectionAccepted'):
        require(saved.get(key) is False,'reassessment exceeds its scope')
    require(isinstance(saved.get('InputSHA256'),dict) and saved['InputSHA256'],'completed audit closure missing')
    merge_inputs(watched,saved['InputSHA256'])
    source_path=original.binding(saved['OriginalExecutionReceipt'],watched)
    require(sha(source_path)==SOURCE_RECEIPT_SHA,'different original failed receipt')
    source=read(source_path);work=source_path.parent
    require(source['Schema']==original.SCHEMA and source['ExecutionPassed'] is False and source['Error']==SOURCE_ERROR
            and original.execution_ok({**source,'Error':None,'RouteComparison':{'Passed':True}}),
            'original native failure differs')
    require(source['Artifacts']==original.artifact_hashes(work),'original artifacts differ')
    for name,h in source['InputSHA256'].items():
        require(saved['InputSHA256'].get(name)==h,'audit omitted original source input')
    for name,h in source['Artifacts'].items():
        require(saved['InputSHA256'].get(str(work/name))==h,'audit omitted original native artifact')
    for key in ('Target','BuildPlan','BuildPlanSHA256','SourceADF','SourceADFSHA256','ResultADF','ResultADFSHA256',
                'BuildDiagnosticsReview','BuildExecutionCompletedWithoutError','BuildDiagnosticsCleared','OriginalRouteDump',
                'OriginalExportReceipt','Routes','MeasuredTargets','ExactRouteCommands','ExactResetCommands','ResetProof'):
        require(saved.get(key)==source[key],'sealed source identity differs: '+key)
    require(source['ResultADFSHA256']==SOURCE_RESULT_ADF and saved['NativeRouteDump']==ref(work/'route-dump.txt')
            and saved['RouteComparison']['Passed'] is True
            and saved['RouteComparison']['SourceMetadataDisposition']['ExactEmptyFileMapRemoval'] is True,
            'sealed comparison or candidate differs')
    for p in (SELF,source_path,Path(source['ResultADF']['Path']),work/'route-dump.txt',work/'stage-plan.json'):
        require(saved['InputSHA256'].get(str(p))==sha(p),'audit omitted required evidence')
    add(watched,path);require(not inspect.drift(watched),'completed reassessment drift')
    return saved


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve()
    require(out.parent==prep.WORK and not out.exists(),'fresh reassessment work-root JSON required')
    value,_=audit_value(a.receipt)
    with out.open('x',encoding='utf-8',newline='\n') as stream:stream.write(json.dumps(value,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'Output':ref(out),'ReassessmentPassed':True,'SourceExecutionPassed':False,'EDAExecuted':False}))


if __name__=='__main__':main()
