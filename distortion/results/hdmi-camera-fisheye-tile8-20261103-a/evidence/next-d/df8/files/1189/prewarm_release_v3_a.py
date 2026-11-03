"""Public CPU authority prewarm, then wait for real root release authorization.

The frozen release driver and bit provider are never patched. Only a request
created exclusively by this wrapper is removed, after its identical bytes have
been preserved. The fresh runtime gate remains in a separate Python process.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,sys,time
WORK=Path(__file__).resolve().parent;ROOT=WORK.parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT.parent/'.venv/Lib/site-packages')]
import hdmi_camera_fisheye_tile8df8v3_bitstream as bit

REVIEW=WORK/'release-prewarm-wrapper-source-manifest-v3-a.json'
REVISION=WORK/'physical-release-provider-source-manifest-v3-a.json'
RELEASE=WORK/'run_release_v3_a.py'
ROLES=WORK/'release-input-manifest-v3-a.json'
PROOF=WORK/'final-proof-v3-a.json'
READY=WORK/'physical-to-release-v3-go-a.json'
REQUEST=WORK/'bit-request-v3-a.json'
SNAPSHOT=WORK/'release-prewarm-bit-request-v3-a.snapshot.json'
PREWARM=WORK/'release-prewarm-authority-v3-a.json'
TRANSITION=WORK/'release-prewarm-authorized-transition-v3-a.json'
EXPECTED_FIELDS={'Schema','Target','PhysicalProof','MapperSimulation','SystemSimulation','IOSimulation','Profile'}

def canonical_bytes(value):return(json.dumps(value,indent=2,allow_nan=False)+'\n').encode('utf-8')
def sha_bytes(value):return hashlib.sha256(value).hexdigest()
def note(stage,**values):print(json.dumps({'Stage':stage,**values}),flush=True)
def verify_sources(review_sha):
    bit.require(bit.sha(REVIEW)==review_sha,'reviewed wrapper manifest changed')
    reviewed=bit.read(REVIEW)
    bit.require(reviewed['Schema']=='hdmi-camera-fisheye-tile8df8v3-release-prewarm-wrapper-source-v1' and
                reviewed['ProviderSourceManifest']==bit.ref(REVISION),'exact reviewed wrapper/revision required')
    for name,digest in reviewed['InputSHA256'].items():
        bit.require(bit.build.local_io(name).is_file()and bit.sha(name)==digest,'reviewed prewarm input changed: '+name)
    original=bit.read(REVISION)
    bit.require(original['ProviderRevision']=='tile8df8v3-budget1800-a'and original['InputSHA256'].get(str(bit.SELF))==bit.sha(bit.SELF),
                'exact selected frozen bit provider required')
    for name,digest in original['InputSHA256'].items():
        bit.require(bit.build.local_io(name).is_file()and bit.sha(name)==digest,'frozen431 input changed: '+name)
    bit.require(bit.FIELDS==EXPECTED_FIELDS,'exact seven bit request fields required')
    return reviewed

def read_complete(path):
    try:return bit.read(path)
    except(FileNotFoundError,json.JSONDecodeError):return None

def wait_proof(maximum):
    deadline=time.monotonic()+maximum
    while time.monotonic()<deadline:
        value=read_complete(PROOF)
        if value is not None:
            bit.physical_flags(value)
            return bit.ref(PROOF)
        time.sleep(2)
    raise TimeoutError('no complete actual final physical proof within bounded wait')

def make_request(references):
    paths={}
    # This is the exact frozen release.main order, in the same interpreter.
    for name in bit.FIELDS-{'Schema','Target'}:
        value=references[name];path=Path(value['Path']).resolve()
        bit.require(value==bit.ref(path),'prewarm/release role reference changed: '+name)
        paths[name]=value
    return{'Schema':bit.REQUEST_SCHEMA,'Target':bit.TARGET,**paths}

def remove_owned_request(expected,snapshot):
    bit.require(REQUEST.resolve().parent==WORK.resolve()and REQUEST.name=='bit-request-v3-a.json',
                'owned request path escaped this work root')
    bit.require(snapshot==SNAPSHOT and snapshot.read_bytes()==expected and REQUEST.read_bytes()==expected,
                'owned request/snapshot bytes changed; request retained')
    REQUEST.unlink()
    bit.require(not REQUEST.exists(),'owned prewarm request removal failed')

def load_release():
    spec=importlib.util.spec_from_file_location('frozen_tile8v2_release_in_prewarm',RELEASE)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    bit.require(module.bit is bit and module.program.bit is bit,'same-interpreter selected bit module required')
    return module

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reviewed-manifest-sha256',required=True)
    parser.add_argument('--wait-proof-seconds',type=int,default=1800)
    parser.add_argument('--wait-release-seconds',type=int,default=7200)
    args=parser.parse_args(argv)
    bit.require(len(args.reviewed_manifest_sha256)==64 and
                all(c in '0123456789abcdef'for c in args.reviewed_manifest_sha256),'exact reviewed manifest SHA required')
    bit.require(1<=args.wait_proof_seconds<=7200 and 1<=args.wait_release_seconds<=14400,'bounded waits required')
    approved=verify_sources(args.reviewed_manifest_sha256)
    release=load_release()
    bit.require(not any(path.exists()for path in(REQUEST,SNAPSHOT,PREWARM,TRANSITION,WORK/'bit-v3-a',WORK/'program-v3-a')),
                'fresh wrapper artifacts and unstarted release required')
    note('wait-actual-final-proof',MaximumSeconds=args.wait_proof_seconds,CPUOnly=True)
    proof_ref=wait_proof(args.wait_proof_seconds)
    role_deadline=time.monotonic()+args.wait_proof_seconds;roles=None;roles_ref=None
    while time.monotonic()<role_deadline:
        candidate=read_complete(ROLES)
        if candidate is not None:
            bit.require(candidate.get('Schema')=='hdmi-camera-fisheye-tile8df8v3-readonly-release-input-manifest-v1' and
                candidate.get('Passed')is True and candidate.get('SelectedBitstreamProvider')==bit.ref(bit.SELF) and
                candidate.get('ProviderSourceManifest')==bit.ref(REVISION) and candidate.get('InputDrift')==[],
                'actual selected tile8v2 four-role input manifest required')
            bit.require(all(candidate.get(name)==value for name,value in approved['ExpectedRoleReferences'].items()),
                'actual four-role binding differs from the reviewed selected input identities')
            candidate_ref=bit.ref(ROLES)
            bit.require(candidate==bit.read(ROLES) and candidate_ref==bit.ref(ROLES),
                'actual four-role binding manifest changed during read')
            roles=candidate;roles_ref=candidate_ref;break
        time.sleep(2)
    bit.require(roles is not None,'actual selected four-role manifest absent within bounded wait')
    references={name:proof_ref if name=='PhysicalProof'else roles[name]for name in bit.FIELDS-{'Schema','Target'}}
    request=make_request(references);expected=canonical_bytes(request)
    started=time.monotonic();owned=False;context=None
    try:
        bit.write(REQUEST,request);owned=True
        bit.require(REQUEST.read_bytes()==expected,'frozen public writer produced unexpected bytes')
        with SNAPSHOT.open('xb')as out:out.write(expected)
        note('public-uncached-authority-prewarm',Started=True,RequestSHA256=sha_bytes(expected),CPUOnly=True)
        context=bit.audit_request(REQUEST,use_cache=False)
        bit.require(context['Request']==request and Path(context['RequestPath'])==REQUEST and
                    context['Watched'][str(REQUEST)]==sha_bytes(expected) and bit.drift(context['Watched'])==[],
                    'public prewarm context or full immutable closure differs')
        receipt={'Schema':'hdmi-camera-fisheye-tile8df8v3-release-authority-prewarm-v1','Passed':True,
            'CheckedUTC':bit.utc(),'ReviewedWrapperManifest':bit.ref(REVIEW),'ProviderSourceManifest':bit.ref(REVISION),
            'SelectedBitstreamProvider':bit.ref(bit.SELF),'FrozenReleaseDriver':bit.ref(RELEASE),
            'ActualSelectedFourRoleManifest':roles_ref,
            'ExactRequest':request,'RequestPath':str(REQUEST),'RequestSHA256':sha_bytes(expected),'RequestSnapshot':bit.ref(SNAPSHOT),
            'RequestExclusiveCreatedByWrapper':True,'OwnerPID':os.getpid(),'PublicAuditRequestUseCache':False,
            'WatchedInputSHA256':context['Watched'],'InputDrift':[],'ElapsedSeconds':round(time.monotonic()-started,3),
            'PrivateCacheAccessed':False,'ProvidersPatched':False,'BitStagePrepared':False,'PDriveCreated':False,
            'EDAExecuted':False,'HardwareAccessed':False,'ReleaseAuthorizedByPrewarm':False,
            'FreshRuntimeGateStillRequired':True}
        bit.write(PREWARM,receipt)
    finally:
        if owned:
            remove_owned_request(expected,SNAPSHOT)
    note('prewarm-complete-wait-real-root-go',Receipt=bit.ref(PREWARM),MaximumSeconds=args.wait_release_seconds,
         RequestRemovedAfterByteIdenticalSnapshot=True,EDAExecuted=False)
    deadline=time.monotonic()+args.wait_release_seconds;ready=None;ready_ref=None
    while time.monotonic()<deadline:
        candidate=read_complete(READY)
        if candidate is not None and all(candidate.get(name)is True for name in(
                'PriorWorkerEnded','PDriveReleased','UserAuthorizedVolatileSRAM','UserNotifiedBeforeExecution')):
            bit.require(candidate.get('ProviderRevision')=='tile8df8v3-budget1800-a' and
                        candidate.get('ProviderSourceManifest')==bit.ref(REVISION),'actual root release revision differs')
            bit.require(all(candidate.get(name)==request[name]for name in bit.FIELDS-{'Schema','Target'}),
                        'actual root release references differ from prewarmed exact request')
            candidate_ref=bit.ref(READY)
            bit.require(candidate==bit.read(READY)and candidate_ref==bit.ref(READY),
                        'actual root go changed while its authorization was read')
            if not Path('P:/').exists():ready=candidate;ready_ref=candidate_ref;break
        time.sleep(2)
    bit.require(ready is not None,'real root release flags and free P: did not arrive within bounded wait')
    verify_sources(args.reviewed_manifest_sha256)
    bit.require(bit.ref(ROLES)==roles_ref,'actual selected four-role manifest changed before root release')
    bit.require(not REQUEST.exists()and not(WORK/'bit-v3-a').exists()and not(WORK/'program-v3-a').exists(),
                'another release owner started; refusing duplicate execution')
    external={name:digest for name,digest in context['Watched'].items()if Path(name)!=REQUEST}
    bit.require(bit.drift(external)==[],'prewarmed external authority closure drifted before root go')
    restored=make_request(ready);comparison=WORK/'release-prewarm-recreated-request-check-v3-a.json'
    bit.write(comparison,restored)
    bit.require(comparison.read_bytes()==SNAPSHOT.read_bytes()==expected and bit.sha(comparison)==sha_bytes(expected),
                'frozen main request recreation cannot match the exact prewarm cache key')
    bit.write(TRANSITION,{'Schema':'hdmi-camera-fisheye-tile8df8v3-release-prewarm-authorized-transition-v1',
        'Passed':True,'RootReleaseGo':ready_ref,'PrewarmReceipt':bit.ref(PREWARM),'RequestComparison':bit.ref(comparison),
        'ExpectedRealRequestSHA256':sha_bytes(expected),'ExactFiveRoleReferencesMatch':True,'PDriveFree':True,
        'FrozenReleaseDriver':bit.ref(RELEASE),'UnchangedMainInvokedInSameInterpreter':True,
        'PrivateCacheAccessed':False,'FreshRuntimeGateStillRequired':True})
    bit.require(bit.ref(READY)==ready_ref,'actual authorized root go changed before unchanged main')
    note('real-root-go-invoke-unchanged-release',RootGo=ready_ref,SameInterpreter=True,
         ExactRecreatedRequestSHA256=sha_bytes(expected))
    return release.main()

if __name__=='__main__':main()
