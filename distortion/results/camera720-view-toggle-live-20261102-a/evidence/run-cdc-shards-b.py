"""Replay fully bound fresh query preparation in four-command native shards.

The earlier 38-command context remains a failed, unused receipt. Its successful
independent IO context is rebound. Previously completed CPU derivation is reused
only under its exact producer and complete canonical watched SHA256 closure.
"""
from concurrent.futures import ThreadPoolExecutor
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import threading

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import camera720_view_toggle_build as build
import camera720_view_toggle_final_inspect as final
import camera720_view_toggle_reset_apply as reset
import camera720_view_toggle_cdc_proof as cdc

SELF=Path(__file__).resolve();HERE=SELF.parent;LOG=HERE/'cdc-shard-driver-b.json'
SNAPSHOT=HERE/'cdc-shard-driver-b.snapshot.py'
build.require(not SNAPSHOT.exists(),'fresh driver snapshot required')
SNAPSHOT.write_bytes(SELF.read_bytes());DRIVER_SHA=build.sha(SELF)
LOCK=threading.RLock();RECORDS=[]
SEED=HERE/'cdc-final-queries-a/plan.json';seed=build.read(SEED)
build.require(build.sha(SEED)=='c568ea3746e55e58da6db6951f3f02fe345667474e1bad862fee9f3cc8edd6de',
              'known fully derived current CPU plan SHA differs')


def check(watched):
    for p,h in watched.items():
        p=Path(p)
        build.require(p==p.resolve() and p.is_file() and build.sha(p)==h,'reused CPU closure drift '+str(p))


build.require(seed['Schema']==cdc.PLAN_SCHEMA and seed['Target']==build.TARGET
              and seed['Producer']==final.ref(cdc.SELF),'fresh plan producer/target/schema differs')
seed_watched={Path(p):h for p,h in seed['InputSHA256'].items()};check(seed_watched)
build.require(seed['InitialEvidence']['CandidateADF']==final.ref(HERE/'reset-save-a/input.adf'),
              'seed is not current final reset ADF')


def save():
    build.require(build.sha(SELF)==build.sha(SNAPSHOT)==DRIVER_SHA,'executing driver source changed')
    LOG.write_text(json.dumps({'Schema':'camera720-view-toggle-cdc-shard-driver-v1',
        'Driver':{'Path':str(SNAPSHOT),'SHA256':DRIVER_SHA},'SeedPlan':final.ref(SEED),
        'HardwareAccessed':False,'BitstreamRequested':False,'CommandsPerContext':4,'ParallelContexts':3,
        'ReusePolicy':'Previously completed deterministic CPU derivation only. Exact saved producer and every canonical watched SHA rechecked; no new CPU parse claimed. Native shards execute unchanged frozen tools.',
        'ExcludedFailedReceipt':str(HERE/'cdc-final-query-00-a/result.json'),'Records':RECORDS},indent=2)+'\n',encoding='utf-8')


def restored_watch(path):
    value=build.read(path);watch={Path(p):h for p,h in value['InputSHA256'].items()}
    watch[path.parent/'stage-plan.json']=value['StagePlanSHA256']
    watch[path]=build.sha(path)
    for name,h in value['Artifacts'].items():watch[path.parent/name]=h
    build.require(all(seed_watched.get(p)==h for p,h in watch.items()),
                  'restored binder role was not in completed seed closure')
    check(watch)
    return value,watch


original_final=final.bind_receipt;original_reset=reset.bind_completed
reset_path=HERE/'reset-save-a/result.json'
reset_value,reset_watch=restored_watch(reset_path)
known={str(HERE/name/'result.json'):restored_watch(HERE/name/'result.json')
       for name in ('final-export-a','final-route-a')}


def restored_reset(path):
    path=Path(path).resolve()
    if path==reset_path:
        with LOCK:
            check(reset_watch)
            RECORDS.append({'Binder':'reset.bind_completed','Path':str(path),
                'ReusedCompletedCPUParse':True,'WatchedRehashed':len(reset_watch)});save()
            return copy.deepcopy((reset_value,reset_watch))
    return original_reset(path)


def restored_final(path):
    path=Path(path).resolve();key=str(path)
    if key in known:
        with LOCK:
            value,watch=known[key];check(watch)
            RECORDS.append({'Binder':'final.bind_receipt','Path':key,
                'ReusedCompletedCPUParse':True,'WatchedRehashed':len(watch)});save()
            return copy.deepcopy((value,watch))
    return original_final(path)


reset.bind_completed=restored_reset;final.bind_receipt=restored_final
initial=seed['InitialEvidence']
io_file=seed['QueryBodies']['query-io.tcl']
io_body=Path(io_file['Path']).read_text(encoding='ascii')
build.require(final.ref(io_file['Path'])==io_file,'seed IO body changed')


def restored_derive(export_path,route_path):
    build.require(Path(export_path).resolve()==HERE/'final-export-a/result.json'
        and Path(route_path).resolve()==HERE/'final-route-a/result.json','reused derivation identity differs')
    check(seed_watched)
    watched={**seed_watched,SEED:build.sha(SEED),SNAPSHOT:DRIVER_SHA}
    RECORDS.append({'DerivationReused':True,'SeedPlan':final.ref(SEED),'WatchedRehashed':len(seed_watched)});save()
    return copy.deepcopy(initial),watched,io_body


cdc.derive=restored_derive
try:
    groups,bodies=cdc.query_bodies(initial['Queries'],initial['InitialCoverage']['MissingCases'],4)
    build.require(groups==seed['Groups'] and len(groups)==38,'exact complete current CDC groups changed')
    output=HERE/'cdc-final-shards-b';build.require(not output.exists(),'fresh shard preparation required');output.mkdir()
    stages=[]
    for name,body in bodies.items():
        path=output/name;path.write_text(body,encoding='ascii',newline='\n')
        stages.append(final.prepare(HERE/'build-a/plan.json',HERE/'reset-save-a/input.adf',
            HERE/('cdc-shard-'+Path(name).stem+'-b'),'query',reset_path,path))
    build.write(output/'plan.json',{'Schema':cdc.PLAN_SCHEMA,'Target':build.TARGET,'Producer':final.ref(cdc.SELF),
        'SeedPlan':final.ref(SEED),'Groups':groups,'CommandsPerBody':4,
        'QueryBodies':{n:final.ref(output/n) for n in bodies},
        'InputSHA256':{str(p):h for p,h in seed_watched.items()},'DriverSnapshot':final.ref(SNAPSHOT)})
    print('SHARD_PLANS '+json.dumps([str(p) for p in stages]),flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures=[pool.submit(final.execute,p) for p in stages]
        values=[]
        for future in futures:
            value=future.result();values.append(value)
            print('SHARD_RESULT '+json.dumps({k:value.get(k) for k in
                ('WorkDirectory','ExecutionPassed','ElapsedSeconds','Error')}),flush=True)
    build.require(all(v['ExecutionPassed'] for v in values),'fresh shard incomplete; no partial receipt acceptance')
    receipts=[p.parent/'result.json' for p in stages]+[HERE/'cdc-final-query-io-a/result.json']
    result,_=cdc.audit_value(HERE/'final-export-a/result.json',HERE/'final-route-a/result.json',receipts)
    build.write(HERE/'cdc-final-proof-b.json',result)
    RECORDS.append({'Proof':final.ref(HERE/'cdc-final-proof-b.json'),'ScopedDigitalChecksPassed':result['ScopedDigitalChecksPassed'],
                    'Missing':result['Missing'],'Violations':result['Violations']});save()
    print('CDC_FINAL '+json.dumps({k:result[k] for k in
        ('CandidateADFSHA256','ExpectedCases','ObservedCases','ScopedDigitalChecksPassed','Missing','Violations')}),flush=True)
    build.require(result['ScopedDigitalChecksPassed'],'full final digital proof incomplete')
except BaseException as error:
    RECORDS.append({'Passed':False,'Error':type(error).__name__+': '+str(error),
                    'UTC':datetime.now(timezone.utc).isoformat()});save()
    raise
