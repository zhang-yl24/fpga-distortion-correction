"""CPU-only final C IO/CDC recipe and sealed-source native stage preparation.

Prerequisites are the real repaired-reset final export/report and source seal.
No PDS, UART, JTAG or native executor is invoked here. Printed argv is for root.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

PROJECT=Path(__file__).resolve().parents[1]
HERE=PROJECT/'work/camera720-stats-delay'
sys.path.insert(0,str(PROJECT/'tools'))
import camera720_stats_delay_cdc_proof as proof
import camera720_stats_delay_repaired_final_inspect as final

BUILD_SHA='2a263c20d7c3b5ebc0c2796bcac8bf2a3bf8380793283f0dcd1c8d2c0d405d08'
PROOF_SHA='5a2250cdc63da623c3b457dd81242edb9d23437bab0f6b87c2527e1f6e613b75'
AUTHORITY=HERE/'repaired-reset-source-authority-c.json'
EXPORT=HERE/'repaired-reset-final-export-c/result.json'
ROUTE=HERE/'repaired-reset-final-report-c/result.json'
RECIPE=HERE/'cdc-final-query-recipe-c'
HANDOFF=HERE/'final-native-query-handoff-c.json'
FINAL_PROOF=HERE/'cdc-final-proof-c.json'
PYTHON=Path(sys.executable).resolve()


def exact(path,digest):
    if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):
        raise ValueError('explicit lowercase SHA256 required')
    if not path.is_file() or proof.sha(path)!=digest:
        raise ValueError('actual prerequisite absent or hash differs: '+str(path))
    return proof.read(path)


def same_final_inputs(export,route,authority_ref):
    for value,mode in ((export,'export'),(route,'report')):
        proof.require(value.get('Schema')==final.SCHEMA and value.get('Target')==proof.TARGET
            and value.get('ExecutionPassed') is True and value.get('Mode')==mode,
            'successful explicit repaired-final receipt required')
        proof.require(value.get('SourceAuthority')==authority_ref,
            'final receipts must bind the same explicit source authority')
        proof.require(value.get('BuildPlanSHA256')==BUILD_SHA,
            'final receipt does not derive from shared-control C build')
    proof.require(all(export.get(k)==route.get(k) for k in
        ('SourceADF','SourceADFSHA256','SourceReceipt','BuildPlan','BuildPlanSHA256')),
        'export and route refer to different final candidates or reset applications')
    proof.require(export.get('NativeNetlistWithFFloc') is True and
                  'route-dump.txt' in route.get('Artifacts',{}),
                  'final placed netlist and actual route dump required')


def stage_name(body_name):
    if body_name=='query-io.tcl':return 'final-io-c'
    match=re.fullmatch(r'query-([0-9]{2})\.tcl',body_name)
    proof.require(match is not None,'unexpected generated query body name')
    return 'final-cdc-c-'+match[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authority-sha256',required=True)
    parser.add_argument('--export-sha256',required=True)
    parser.add_argument('--route-sha256',required=True)
    parser.add_argument('--commands-per-body',type=int,default=8,choices=range(1,9))
    args=parser.parse_args()
    proof.require(HERE==proof.WORK.resolve(),'exact candidate C work directory required')
    proof.require(proof.sha(proof.SELF)==PROOF_SHA,'frozen CDC producer changed')
    authority=exact(AUTHORITY,args.authority_sha256)
    export=exact(EXPORT,args.export_sha256);route=exact(ROUTE,args.route_sha256)
    authority_ref={'Path':str(AUTHORITY),'SHA256':args.authority_sha256}
    final.authority_shape(authority)
    same_final_inputs(export,route,authority_ref)
    proof.require(not RECIPE.exists() and not HANDOFF.exists() and not FINAL_PROOF.exists(),
                  'fresh final recipe, handoff and proof paths required')
    print('Deriving the actual final C graph and missing coverage; CPU only.',flush=True)
    plan=proof.prepare(EXPORT,ROUTE,RECIPE,args.commands_per_body)
    initial=plan['InitialEvidence']
    proof.require(initial['CandidateADFSHA256']==export['SourceADFSHA256']
                  and initial['ExportReceipt']==proof.ref(EXPORT)
                  and initial['RouteReceipt']==proof.ref(ROUTE),'derived final identity differs')
    watched={Path(p):h for p,h in plan['InputSHA256'].items()}
    proof.require(not proof.inspect.drift(watched),'final derivation closure changed')
    names=sorted(plan['QueryBodies'])
    proof.require(all(not (HERE/stage_name(name)).exists() for name in names),
                  'a native stage directory already exists; do not silently replace it')
    stages=[]
    print(json.dumps({'FinalRecipe':proof.ref(RECIPE/'plan.json'),
        'CandidateADFSHA256':initial['CandidateADFSHA256'],
        'Expected':initial['InitialCoverage']['ExpectedCases'],
        'Covered':initial['InitialCoverage']['CoveredCases'],
        'Missing':len(initial['InitialCoverage']['MissingCases']),
        'Groups':len(plan['Groups']),'Contexts':len(names)}),flush=True)
    for name in names:
        body=plan['QueryBodies'][name];path=Path(body['Path'])
        proof.require(path.parent==RECIPE and path.name==name and proof.sha(path)==body['SHA256'],
                      'generated body identity changed')
        work=HERE/stage_name(name)
        stage=final.prepare(AUTHORITY,args.authority_sha256,work,'query',path,300)
        value=proof.read(stage)
        proof.require(value['SourceADFSHA256']==initial['CandidateADFSHA256']
                      and value['SourceAuthority']==authority_ref,'prepared stage identity differs')
        item={'Body':body,'StagePlan':proof.ref(stage),'ResultPath':str(work/'result.json'),
              'RootExecuteArgv':[str(PYTHON),'-B','-X','utf8',str(final.SELF),
                                 '--stage-plan',str(stage),'--execute']}
        stages.append(item);print(json.dumps({'Prepared':item}),flush=True)
    argv=[str(PYTHON),'-B','-X','utf8',str(proof.SELF),'audit',
          '--export-receipt',str(EXPORT),'--route-receipt',str(ROUTE)]
    for stage in stages:argv+=['--query-receipt',stage['ResultPath']]
    argv+=['--output',str(FINAL_PROOF)]
    handoff={'Schema':'camera720-stats-delay-final-query-handoff-v1','Target':proof.TARGET,
        'Producer':proof.ref(__file__),'SourceAuthority':authority_ref,
        'ExportReceipt':proof.ref(EXPORT),'RouteReceipt':proof.ref(ROUTE),
        'CandidateADF':initial['CandidateADF'],'Recipe':proof.ref(RECIPE/'plan.json'),
        'Stages':stages,'FinalAuditArgv':argv,
        'FinalVerifyArgv':[str(PYTHON),'-B','-X','utf8',str(proof.SELF),'verify','--output',str(FINAL_PROOF)],
        'EDAExecutedByThisHelper':False,'HardwareAccessed':False,'TimingAccepted':False,
        'HardwareReleaseAllowed':False,'NativeQueriesCompleted':False,
        'Limits':'Root runs the listed native stages sequentially. Final audit requires actual successful result receipts and checks every missing identity; preparation is not acceptance.'}
    proof.inspect.diagnostic.write(HANDOFF,handoff)
    proof.require(proof.read(HANDOFF)==handoff,'handoff readback differs')
    print(json.dumps({'Handoff':proof.ref(HANDOFF),'NativeExecuted':False}),flush=True)


if __name__=='__main__':main()
