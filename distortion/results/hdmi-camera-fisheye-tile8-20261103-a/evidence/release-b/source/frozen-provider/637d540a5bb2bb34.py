"""Freeze the reviewed revision rows without preparing or executing any stage."""
from pathlib import Path
import json,sys,xml.etree.ElementTree as ET
WORK=Path(__file__).resolve().parent;ROOT=WORK.parents[1];TOOLS=ROOT/'tools'
sys.path[:0]=[str(TOOLS),str(ROOT.parent/'.venv/Lib/site-packages')]
import hdmi_camera_fisheye_fill8r3s3_build as build
ROLES=('physical','scoped_native','target_query','physical_checks','final','bitstream','program')
watched={}
def add(path,expected=None):
    path=Path(path).resolve();actual=build.sha(path)
    build.require(expected is None or actual==expected,'revision input SHA differs: '+str(path))
    build.require(str(path)not in watched or watched[str(path)]==actual,'conflicting source SHA')
    watched[str(path)]=actual;return build.ref(path)
def refs(value):
    if isinstance(value,dict):
        if set(value)=={'Path','SHA256'}:add(value['Path'],value['SHA256'])
        else:
            for item in value.values():refs(item)
    elif isinstance(value,list):
        for item in value:refs(item)
def junit(path,expected):
    tree=ET.parse(path).getroot();suites=list(tree.iter('testsuite'))
    build.require(sum(int(s.get('tests',0))for s in suites)==expected and
        all(int(s.get('failures',0))==int(s.get('errors',0))==0 for s in suites),'revision tests did not pass')
    return {'Tests':expected,'Failures':0,'Errors':0,'JUnit':add(path)}

def main():
    output=WORK/'provider-revision-v2-source-manifest-a.json'
    build.require(not output.exists(),'fresh immutable provider revision manifest required')
    original=build.read(WORK/'root-adapter-source-manifest.json')
    for row in original['Files'].values():add(row['NewPath'],row['NewSHA256'])
    add(WORK/'root-adapter-source-manifest.json')
    original_build=build.read(WORK/'build-provider-source-manifest.json')
    for row in original_build['NewFiles']:add(row['Path'],row['SHA256'])
    add(WORK/'build-provider-source-manifest.json')
    audit_freeze=build.read(WORK/'audit-provider-final-freeze-a.json')
    build.require(audit_freeze['Passed']is True and audit_freeze['SourceDiagnosticReviewPassed']is True,
                  'completed original S3 source warning review required')
    for row in audit_freeze['Providers']:add(row['Adapted'],row['AdaptedSHA256'])
    add(WORK/'audit-provider-final-freeze-a.json');refs(audit_freeze.get('SourceWarningReceipt'))
    bounded=add(TOOLS/'hdmi_camera_fisheye_fill8r3s3_vendor_startup_bounded_b.py',
        'c75f3123b59e8f83efd9cfcab3486e851b1c7daa9b787385eaaadfb30b238f16')
    proof_path=WORK/'vendor-native-cell-v2-proposal-b/actual-34-field-review-a.json';proof=build.read(proof_path)
    build.require(proof['Passed']is True and proof['CompleteActualFFInventory']==34 and len(proof['PhysicalRSPins'])==7,
                  'actual bounded-B 34FF/seven-site proof required')
    own=build.read(WORK/'vendor-own-tests-d-bounded-b/result.json')
    build.require(own['Passed']is True and own['Tests']==28 and own['Failures']==own['Errors']==0,
                  'actual bounded-B 28 tests required')
    own_ref=add(WORK/'vendor-own-tests-d-bounded-b/result.json');refs(own)
    proof_ref=add(proof_path,'efc7030919761cae1767669a7eafecc8dea710a13b99a6a8641bcffe5ab2ed6d');refs(proof)
    peers={}
    for name in ('vendor-native-cell-peer-review-b.json','provider-revision-v2-independent-closure-review-a.json',
                 'provider-revision-v2-fps-peer-review-a.json'):
        value=build.read(WORK/name);build.require(value['Passed']is True,'independent provider review must pass')
        peers[name]=add(WORK/name);refs(value)
    helper_manifest=build.read(WORK/'physical-compression-helper-source-manifest-v2.json')
    build.require(helper_manifest['Passed']is True and helper_manifest['CompressionExecuted']is False,
                  'prepared exact completed-only compression helper required')
    refs(helper_manifest);helper_ref=add(WORK/'physical-compression-helper-source-manifest-v2.json')
    adapters={role:add(TOOLS/f'hdmi_camera_fisheye_fill8r3s3v2_{role}.py')for role in ROLES}
    drivers={name:add(WORK/name)for name in ('run_physical_v2_a.py','run_release_v2_a.py')}
    for name in ('prepare_provider_revision_v2.py','check_provider_revision_v2_tests.py','provider-revision-v2-plan-a.md',
                 'freeze_provider_revision_v2.py'):
        add(WORK/name)
    for path in (WORK/'root-adapter-tests-v2-a').glob('*.py'):add(path)
    tests={'RetainedAndImportContracts':junit(WORK/'root-adapter-tests-v2-a/results.xml',327),
           'DriverManifestCases':junit(WORK/'root-adapter-tests-v2-a/driver-results.xml',6),
           'BoundedParser':junit(WORK/'vendor-native-cell-v2-proposal-b/parser-tests.xml',12)}
    for path in (WORK/'vendor-native-cell-v2-proposal-b').glob('test_*.py'):add(path)
    raw={name:add(WORK/name)for name in ('build-a/plan.json','build-a/execution-result.json','raw-core-timing-a.json',
        'export-a/result.json','route-a/result.json','audit-a/scope.json','preflight-a-00/result.json',
        'physical-worker-initial-stopped-before-application-a.json','release-input-manifest-a.json')}
    shared={role:add(TOOLS/f'hdmi_camera_fisheye_fill8r3s3_{role}.py')for role in(
        'build','native','audit','protocol','startup','warnings','macro_we_aliases','startup_timing')}
    build.require(all(build.sha(path)==digest for path,digest in watched.items()),'revision source drift during freeze')
    result={'Schema':'hdmi-camera-fisheye-fill8r3s3v2-provider-source-manifest-v1','ProviderRevision':'s3v2-bounded-b',
        'Passed':True,'FrozenUTC':build.utc(),'NewAdapters':adapters,'NewDrivers':drivers,'SharedOriginalS3Providers':shared,
        'BoundedVendorProvider':bounded,'Actual34FFProof':proof_ref,'Actual28TestReceipt':own_ref,'Tests':tests,
        'IndependentReviews':peers,'CompletedOnlyCompressionHelperManifest':helper_ref,'ExistingS3Evidence':raw,
        'SharedS3Statuses':{'OriginalNineRootProvidersUnchanged':True,'OriginalBuildRawScopedInputsUnchanged':True,
            'OriginalAuditProtocolStartupWarningsUnchanged':True,'OriginalSourceWarningReviewPassed':True},
        'PreservedAuditSchema':'hdmi-camera-fisheye-fill8r3s3-native-audit-v1','PreservedWorkDirectory':str(WORK),
        'InputSHA256':dict(sorted(watched.items())),'InputDrift':[],'ManifestSelfIncluded':False,
        'FreshFullAuditRevalidationStillRequired':True,'FreshBoundedBStartupReviewStillRequired':True,
        'PhysicalStagePrepared':False,'RootGoPrepared':False,'PDriveAccessed':False,'EDAExecuted':False,
        'BitStagePrepared':False,'HardwareAccessed':False,'HardwareReleaseAllowed':False}
    build.write(output,result)
    print(json.dumps({'Passed':True,'Manifest':build.ref(output),'InputRows':len(watched),
                      'Tests':{name:value['Tests']for name,value in tests.items()},'EDAExecuted':False}),flush=True)

if __name__=='__main__':main()
