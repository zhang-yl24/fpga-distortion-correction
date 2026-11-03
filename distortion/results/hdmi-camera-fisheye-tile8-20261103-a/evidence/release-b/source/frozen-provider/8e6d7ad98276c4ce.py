"""Create isolated physical/release revision; retain every shared S3 authority."""
from pathlib import Path
import ast,hashlib,json
WORK=Path(__file__).resolve().parent;ROOT=WORK.parents[1];TOOLS=ROOT/'tools'
ROLES=('physical','scoped_native','target_query','physical_checks','final','bitstream','program')
NAMES={f'hdmi_camera_fisheye_fill8r3s3_{role}':f'hdmi_camera_fisheye_fill8r3s3v2_{role}'for role in ROLES}
SCHEMAS={f'hdmi-camera-fisheye-fill8r3s3-{suffix}':f'hdmi-camera-fisheye-fill8r3s3v2-{suffix}'for suffix in(
    'physical-planning-v1','physical-application-v1','scoped-native-inspection-v1','targeted-native-query-v1',
    'final-physical-proof-v1','bitstream-request-v1','bitstream-plan-v1','bitstream-execution-v1',
    'pre-bit-gate-v1','bitstream-verification-v1','sram-plan-v1','sram-execution-v1')}
MARKERS={'HDMI_CAMERA_FISHEYE_EXACT_PHYSICAL_SCOPE_SAVED':'HDMI_CAMERA_FISHEYE_S3V2_EXACT_PHYSICAL_SCOPE_SAVED',
    'HDMI_CAMERA_FISHEYE_FILL8R3S3_SCOPED_NATIVE_INSPECTION_COMPLETE':'HDMI_CAMERA_FISHEYE_FILL8R3S3V2_SCOPED_NATIVE_INSPECTION_COMPLETE',
    'HDMI_CAMERA_FISHEYE_TARGETED_QUERY_COMPLETE':'HDMI_CAMERA_FISHEYE_S3V2_TARGETED_QUERY_COMPLETE',
    'HDMI_CAMERA_FISHEYE_PRE_BIT_GATE_PASS':'HDMI_CAMERA_FISHEYE_S3V2_PRE_BIT_GATE_PASS',
    'HDMI_CAMERA_FISHEYE_BITSTREAM_COMPLETE':'HDMI_CAMERA_FISHEYE_S3V2_BITSTREAM_COMPLETE'}
def rewrite(text):
    for old,new in sorted(NAMES.items(),key=lambda item:-len(item[0])):text=text.replace(old,new)
    for old,new in {**SCHEMAS,**MARKERS}.items():text=text.replace(old,new)
    return text
def fresh(path,text):
    ast.parse(text)
    with path.open('x',encoding='utf-8',newline='\n')as out:out.write(text)
for role in ROLES:
    source=TOOLS/f'hdmi_camera_fisheye_fill8r3s3_{role}.py'
    text=rewrite(source.read_text(encoding='utf-8-sig'))
    if role=='physical':
        old="    startup=importlib.import_module('hdmi_camera_fisheye_fill8r3s3_vendor_startup')"
        new="""    startup=importlib.import_module('hdmi_camera_fisheye_fill8r3s3_vendor_startup_bounded_b')
    require(startup.SCHEMA=='hdmi-camera-fisheye-fill8r3s3-vendor-startup-isolation-v2-bounded-b',
            'exact bounded-B vendor startup authority required')"""
        assert text.count(old)==1;text=text.replace(old,new)
    fresh(TOOLS/f'hdmi_camera_fisheye_fill8r3s3v2_{role}.py',text)

driver=rewrite((WORK/'run_physical_a.py').read_text())
driver=driver.replace("WORK / 'physical-progress-a.json'","WORK / 'physical-progress-v2-a.json'")
driver=driver.replace("WORK / 'native-to-physical-go-a.json'","WORK / 'native-to-physical-v2-go-a.json'")
driver=driver.replace("'compress_completed_physical_evidence_a.py'","'compress_completed_physical_v2_evidence_a.py'")
driver=driver.replace("'physical-compression-helper-source-manifest.json'","'physical-compression-helper-source-manifest-v2.json'")
driver=driver.replace("manifest['New']", "manifest['NewHelper']")
old="""    note('audit', Started=True)
    scope, _ = audit.derive(build_plan, refs['ExportReceipt'], refs['RouteReceipt'])
    build.require(scope['ProposalReady'] is True and scope['Blockers'] == [], 'r2 native audit blocked')
    audit_dir = WORK / 'audit-a'
    audit_dir.mkdir(exist_ok=False)
    scope_path = audit_dir / 'scope.json'
    save(scope_path, scope)
    proposal = physical.scope_plan(scope)"""
new="""    note('audit-source-load', Started=True)
    scope_path = WORK / 'audit-a/scope.json'
    scope = build.read(scope_path)
    build.require(scope['Schema'] == physical.AUDIT_SCHEMA and scope['Target'] == build.TARGET and
                  scope['ProposalReady'] is True and scope['Blockers'] == [] and
                  scope['BuildPlan'] == native.ref(build_plan) and
                  scope['ExportReceipt'] == native.ref(refs['ExportReceipt']) and
                  scope['RouteReceipt'] == native.ref(refs['RouteReceipt']),
                  'exact completed original S3 audit facts required')
    # application_recipe.bind_audit performs one fresh full original audit derive;
    # later calls reuse only its existing full-hash authority cache.
    proposal = physical.scope_plan(scope)"""
assert driver.count(old)==1;driver=driver.replace(old,new)
old="""            plan = raw.prepare(build_plan, WORK / f'preflight-a-{index:02}', 'query',
                               body=body_path, maximum=600)
            preflights.append(run_stage(raw, plan, f'preflight-{index:02}'))"""
new="""            prior = WORK / f'preflight-a-{index:02}/result.json'
            reuse = False
            if prior.is_file():
                value, _ = raw.bind_receipt(prior)
                reuse = (value['Mode'] == 'query' and value['SourceProof'] is None and
                         value['BuildPlanSHA256'] == build.sha(build_plan) and
                         value['SourceADF'] == scope['SourceADF']['Path'] and
                         value['SourceADFSHA256'] == scope['SourceADF']['SHA256'] and
                         Path(value['QueryBody']).read_text(encoding='ascii') == body)
            if reuse:
                preflights.append(prior)
                note('preflight-reused-exact', Index=index, Receipt=native.ref(prior),
                     ExactBodyAndSourceBinding=True)
            else:
                plan = raw.prepare(build_plan, WORK / f'preflight-v2-a-{index:02}', 'query',
                                   body=body_path, maximum=600)
                preflights.append(run_stage(raw, plan, f'preflight-v2-{index:02}'))"""
assert driver.count(old)==1;driver=driver.replace(old,new)
driver=driver.replace("WORK / 'physical-bodies-a'","WORK / 'physical-bodies-v2-a'")
for old,new in [('physical-a','physical-v2-a'),('export-scoped-a','export-scoped-v2-a'),
                ('route-scoped-a','route-scoped-v2-a'),('checks-scoped-a-','checks-scoped-v2-a-'),
                ('final-proof-a.json','final-proof-v2-a.json')]:driver=driver.replace("'"+old,"'"+new)
old="    refs = {}"
new="""    build.require(handoff.get('ProviderRevision') == 's3v2-bounded-b' and
                  handoff.get('ProviderSourceManifest') == native.ref(WORK / 'provider-revision-v2-source-manifest-a.json'),
                  'root handoff must bind the exact isolated provider revision')
    refs = {}"""
assert driver.count(old)==1;driver=driver.replace(old,new)
fresh(WORK/'run_physical_v2_a.py',driver)

release=rewrite((WORK/'run_release_a.py').read_text())
for old,new in [('physical-to-release-go-a.json','physical-to-release-v2-go-a.json'),('bit-request-a.json','bit-request-v2-a.json'),
                ('bit-a','bit-v2-a'),('program-a','program-v2-a'),('fps-corrected-a','fps-corrected-v2-a')]:
    release=release.replace("'"+old,"'"+new)
release=release.replace("'release-event-'","'release-v2-event-'")
fresh(WORK/'run_release_v2_a.py',release)

tests=WORK/'root-adapter-tests-v2-a';tests.mkdir()
for source in (WORK/'root-adapter-tests-a').glob('*.py'):
    fresh(tests/source.name,rewrite(source.read_text()))
print(json.dumps({'NewAdapters':[str(TOOLS/f'hdmi_camera_fisheye_fill8r3s3v2_{role}.py')for role in ROLES],
    'Driver':str(WORK/'run_physical_v2_a.py'),'TestFiles':len(list(tests.glob('*.py'))),
    'SharedS3ModulesUnchanged':True,'EDAExecuted':False,'PDriveAccessed':False}))
