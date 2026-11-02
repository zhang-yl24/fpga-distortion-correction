"""Fresh current effect implementation; sealed authority and offline bit only.

Separate from the earlier running CDC driver so source hashes always describe
the actual loaded script. Every memo hit rehashes all watched file content.
"""
from datetime import datetime, timezone
import copy
import json
from pathlib import Path
import sys
import time
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import camera720_view_toggle_build as build
import camera720_view_toggle_route as route
import camera720_view_toggle_reset_apply as reset
import camera720_view_toggle_final_inspect as final
import camera720_view_toggle_reset_effect as effect
import camera720_view_toggle_cdc_proof as cdc
import camera720_view_toggle_bitstream as bit

SELF=Path(__file__).resolve();HERE=SELF.parent;LOG=HERE/'bit-authority-driver-c.json';RECORDS=[]
SNAPSHOT=HERE/'bit-authority-driver-c.snapshot.py'
build.require(not SNAPSHOT.exists(),'fresh authority driver snapshot required')
SNAPSHOT.write_bytes(SELF.read_bytes());DRIVER_SHA=build.sha(SELF)


def save():
    build.require(build.sha(SELF)==build.sha(SNAPSHOT)==DRIVER_SHA,'executing authority driver changed')
    LOG.write_text(json.dumps({'Schema':'camera720-view-toggle-authority-driver-v1','Driver':final.ref(SNAPSHOT),
        'HardwareAccessed':False,'BitstreamRequested':True,
        'CachePolicy':'Deterministic CPU parse reused only after full canonical/is_file/SHA256 watched closure recheck; fresh EDA never cached.',
        'Records':RECORDS},indent=2)+'\n',encoding='utf-8')


def memo(module,name):
    original=getattr(module,name);cache={}
    def call(path):
        key=str(Path(path).resolve())
        if key in cache:
            result=cache[key]
            for p,h in result[-1].items():
                p=Path(p)
                build.require(p==p.resolve() and p.is_file() and build.sha(p)==h,'cached input drift '+str(p))
            RECORDS.append({'Function':module.__name__+'.'+name,'Path':key,'Watched':len(result[-1]),
                'Validation':'Full watched SHA256 recheck; deterministic CPU parse reused'});save()
            return copy.deepcopy(result)
        result=original(path);cache[key]=copy.deepcopy(result)
        RECORDS.append({'Function':module.__name__+'.'+name,'Path':key,'Watched':len(result[-1]),
            'Validation':'Original full CPU parse performed'});save()
        return result
    setattr(module,name,call)


for module,name in ((route,'bind_completed'),(reset,'bind_completed'),(final,'bind_receipt'),
                    (effect,'verify'),(cdc,'verify')):memo(module,name)

try:
    limit=time.monotonic()+1800
    needed=[HERE/'effect-a.json',HERE/'cdc-final-proof-b.json',HERE/'final-cpu-tests.xml']
    while not all(p.is_file() for p in needed):
        build.require(time.monotonic()<limit,'bounded evidence wait expired')
        time.sleep(2)
    build.require(build.sha(HERE/'cdc-final-proof-b.json')=='650f0d84d5929b410f91c9fbcca7d630d418c3749f938681bdac57fad844fdc2', 'exact completed final digital proof SHA required')
    completed=build.read(HERE/'cdc-shard-driver-b.json')['Records'][-1]
    build.require(completed['ScopedDigitalChecksPassed'] is True and completed['Proof']==final.ref(HERE/'cdc-final-proof-b.json'), 'digital producer completion receipt differs')
    build.require(build.read(HERE/'effect-a.json')['Producer']==final.ref(effect.SELF),
                  'effect proof was not produced by current loaded implementation')
    xml=ET.parse(needed[-1]).getroot()
    build.require(sum(int(s.get('tests','0')) for s in xml.iter('testsuite'))>0
        and all(int(s.get('failures','0'))==int(s.get('errors','0'))==0 for s in xml.iter('testsuite')),
        'targeted regression failed')
    request={'Schema':bit.REQUEST_SCHEMA,'Target':build.TARGET}
    roles={'BuildPlan':HERE/'build-a/plan.json','CandidateADF':HERE/'reset-save-a/input.adf',
        'FinalInspectionReceipt':HERE/'final-export-a/result.json','ResetApplicationReceipt':HERE/'reset-save-a/result.json',
        'ResetEffectAudit':HERE/'effect-a.json','FinalCDCProof':HERE/'cdc-final-proof-b.json',
        'BuildDiagnosticsDisposition':HERE/'build-diagnostics-disposition.json',
        'SystemSimulation':build.ROOT/'work/camera720-view-toggle-sim/full-b/camera720-view-toggle-simulation.json',
        'BaselineAuthority':build.ROOT/'work/camera720-stats-delay/bit-authority-c.json'}
    for role,path in roles.items():request[role]=final.ref(path)
    request_path=HERE/'bit-request-c.json';build.write(request_path,request)
    authority=HERE/'bit-authority-c.json';sealed=bit.prepare_authority(request_path,authority)
    RECORDS.append({'Authority':final.ref(authority),'BoundInputs':len(sealed['InputSHA256']),
                    'TargetedTests':final.ref(needed[-1])});save()
    bit.prepare(authority,build.sha(authority),HERE/'bit-c')
    print('BIT_PLAN '+str(HERE/'bit-c/bitstream-plan.json'),flush=True)
    verified=bit.execute(HERE/'bit-c')
    RECORDS.append({'PipelinePassed':True,'Bitstream':verified['Bitstream'],
                    'Verification':final.ref(HERE/'bit-c/verification.json')});save()
    print('BIT_READY '+json.dumps(verified['Bitstream']),flush=True)
except BaseException as error:
    RECORDS.append({'PipelinePassed':False,'Error':type(error).__name__+': '+str(error),
                    'UTC':datetime.now(timezone.utc).isoformat()});save()
    raise
