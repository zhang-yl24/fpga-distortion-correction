"""Execute exact final native CDC queries with content-guarded CPU proof reuse."""
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
import camera720_view_toggle_route as route
import camera720_view_toggle_reset_apply as reset
import camera720_view_toggle_final_inspect as final
import camera720_view_toggle_cdc_proof as cdc
import camera720_view_toggle_reset_effect as effect
import camera720_view_toggle_bitstream as bit

SELF=Path(__file__).resolve();HERE=SELF.parent;LOG=HERE/'final-cdc-driver-a.json'
LOCK=threading.RLock();RECORDS=[]


def save():
    LOG.write_text(json.dumps({'Schema':'camera720-view-toggle-final-cdc-driver-v1',
        'Driver':final.ref(SELF),'HardwareAccessed':False,'BitstreamRequested':True,
        'CachePolicy':'Only deterministic CPU parses reused after every full canonical/is_file/SHA256 closure check. Native queries execute unchanged and never cached.',
        'Records':RECORDS},indent=2)+'\n',encoding='utf-8')


def memo(module,name,index=-1):
    original=getattr(module,name);cache={}
    def call(*args):
        key=tuple(str(Path(p).resolve()) for p in args)
        with LOCK:
            if key in cache:
                result=cache[key];watched=result[index]
                for p,h in watched.items():
                    p=Path(p)
                    build.require(p==p.resolve() and p.is_file() and build.sha(p)==h,'cached input drift '+str(p))
                RECORDS.append({'Function':module.__name__+'.'+name,'Inputs':key,'Watched':len(watched),
                    'Validation':'Every watched SHA256 rechecked; deterministic CPU parse reused',
                    'UTC':datetime.now(timezone.utc).isoformat()});save()
                return copy.deepcopy(result)
            result=original(*args);cache[key]=copy.deepcopy(result)
            RECORDS.append({'Function':module.__name__+'.'+name,'Inputs':key,'Watched':len(result[index]),
                'Validation':'Original full CPU parse performed','UTC':datetime.now(timezone.utc).isoformat()});save()
            return result
    setattr(module,name,call)


for module,name,index in ((route,'bind_completed',-1),(reset,'bind_completed',-1),
    (final,'bind_receipt',-1),(cdc,'derive',1)):
    memo(module,name,index)

try:
    export=HERE/'final-export-a/result.json';routing=HERE/'final-route-a/result.json'
    initial=cdc.prepare(export,routing,HERE/'cdc-final-queries-a',80)
    build.require(initial['InitialEvidence']['CandidateADFSHA256']==build.sha(HERE/'reset-save-a/input.adf'),
                  'final query candidate is not exact reset save')
    stages=[]
    for name,body in initial['QueryBodies'].items():
        stages.append(final.prepare(HERE/'build-a/plan.json',HERE/'reset-save-a/input.adf',
            HERE/('cdc-final-'+Path(name).stem+'-a'),'query',HERE/'reset-save-a/result.json',body['Path']))
    print('QUERY_PLANS '+json.dumps([str(p) for p in stages]),flush=True)
    with ThreadPoolExecutor(max_workers=2) as pool:
        values=list(pool.map(final.execute,stages))
    print('QUERY_RESULTS '+json.dumps([{k:v.get(k) for k in ('Mode','ExecutionPassed','ElapsedSeconds','Error')}
                                      for v in values]),flush=True)
    build.require(all(v['ExecutionPassed'] for v in values),'final native query did not complete')
    receipts=[p.parent/'result.json' for p in stages]
    value,_=cdc.audit_value(export,routing,receipts)
    build.write(HERE/'cdc-final-proof-a.json',value)
    RECORDS.append({'Audit':final.ref(HERE/'cdc-final-proof-a.json'),
        'Passed':value['ScopedDigitalChecksPassed'],'Missing':value['Missing'],'Violations':value['Violations']});save()
    print('CDC_FINAL '+json.dumps({k:value[k] for k in
          ('CandidateADFSHA256','ExpectedCases','ObservedCases','ScopedDigitalChecksPassed','Missing','Violations')}),flush=True)
    build.require(value['ScopedDigitalChecksPassed'],'final digital proof incomplete')
    # Authority completes all semantic validation once; native --gate later
    # starts a separate process and rehashes that sealed full input closure.
    memo(cdc,'verify');memo(effect,'verify')
    tests=HERE/'release-cpu-tests-a.xml'
    import xml.etree.ElementTree as ET
    suites=ET.parse(tests).getroot()
    build.require(sum(int(s.get('tests','0')) for s in suites.iter('testsuite'))>0
                  and all(int(s.get('failures','0'))==int(s.get('errors','0'))==0
                      for s in suites.iter('testsuite')), 'targeted release regression failed')
    request={'Schema':bit.REQUEST_SCHEMA,'Target':build.TARGET}
    roles={'BuildPlan':HERE/'build-a/plan.json','CandidateADF':HERE/'reset-save-a/input.adf',
        'FinalInspectionReceipt':export,'ResetApplicationReceipt':HERE/'reset-save-a/result.json',
        'ResetEffectAudit':HERE/'effect-a.json','FinalCDCProof':HERE/'cdc-final-proof-a.json',
        'BuildDiagnosticsDisposition':HERE/'build-diagnostics-disposition.json',
        'SystemSimulation':build.ROOT/'work/camera720-view-toggle-sim/full-b/camera720-view-toggle-simulation.json',
        'BaselineAuthority':build.ROOT/'work/camera720-stats-delay/bit-authority-c.json'}
    for role,path in roles.items():request[role]=final.ref(path)
    request_path=HERE/'bit-request-a.json';build.write(request_path,request)
    authority=HERE/'bit-authority-a.json';sealed=bit.prepare_authority(request_path,authority)
    RECORDS.append({'Authority':final.ref(authority),'BoundInputs':len(sealed['InputSHA256']),
                    'TargetedTests':final.ref(tests)});save()
    prepared=bit.prepare(authority,build.sha(authority),HERE/'bit-a')
    print('BIT_PLAN '+json.dumps({'Path':str(HERE/'bit-a/bitstream-plan.json'),
          'AuthoritySHA256':build.sha(authority),'BoundInputs':len(sealed['InputSHA256'])}),flush=True)
    verified=bit.execute(HERE/'bit-a')
    RECORDS.append({'PipelinePassed':True,'Bitstream':verified['Bitstream'],
                    'Verification':final.ref(HERE/'bit-a/verification.json')});save()
    print('BIT_READY '+json.dumps(verified['Bitstream']),flush=True)
except BaseException as error:
    RECORDS.append({'Passed':False,'Error':type(error).__name__+': '+str(error)});save()
    raise
