"""Prepare one closed tile8v2 proof/release family; execute no native stage."""
from pathlib import Path
import ast,hashlib,json
WORK=Path(__file__).resolve().parent;ROOT=WORK.parents[1];TOOLS=ROOT/'tools'
OLD_WORK=ROOT/'work/hdmi-camera-fisheye-fill8r3s3-20261103-a'
ROLES=('physical','scoped_native','target_query','physical_checks','final','bitstream','program')
SUPPLEMENTS={'macro_we_aliases':'macro_we_aliases','startup_timing':'startup_timing',
             'vendor_startup_bounded_b':'vendor_startup_bounded_b'}
def renamed(text):
    return(text.replace('hdmi_camera_fisheye_fill8r3s3v2_','hdmi_camera_fisheye_tile8v2_')
        .replace('hdmi_camera_fisheye_fill8r3s3_','hdmi_camera_fisheye_tile8_')
        .replace('hdmi-camera-fisheye-fill8r3s3v2-','hdmi-camera-fisheye-tile8v2-')
        .replace('hdmi-camera-fisheye-fill8r3s3-','hdmi-camera-fisheye-tile8-')
        .replace('HDMI_CAMERA_FISHEYE_FILL8R3S3V2_','HDMI_CAMERA_FISHEYE_TILE8V2_')
        .replace('HDMI_CAMERA_FISHEYE_S3V2_','HDMI_CAMERA_FISHEYE_TILE8V2_'))
def fresh(path,text):
    ast.parse(text)
    with path.open('x',encoding='utf-8',newline='\n')as out:out.write(text)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(path):return{'Path':str(Path(path).resolve()),'SHA256':sha(path)}
rows=[]
for role in ROLES:
    source=TOOLS/f'hdmi_camera_fisheye_fill8r3s3v2_{role}.py'
    target=TOOLS/f'hdmi_camera_fisheye_tile8v2_{role}.py'
    text=renamed(source.read_text(encoding='utf-8-sig'))
    if role=='bitstream':
        text=text.replace("'run_hdmi_camera_fisheye_fill8r3_system_sim'","'run_hdmi_camera_fisheye_tile8_system_sim'")
        text=text.replace("'hdmi_camera_fisheye_engine','hdmi_camera_fisheye_core'",
                          "'hdmi_camera_fisheye_engine_tile8','hdmi_camera_fisheye_core'")
        text=text.replace("'ddr_neighbour_cache_scatter16_rowpipe','ddr_remap_sample_scatter4','ddr_read_arbiter')]),",
                          "'ddr_neighbour_cache_scatter16_rowpipe','ddr_remap_sample_scatter4','ddr_read_arbiter',\n                'ddr_adaptive_result_writer_dualstripe')]),")
        old="        require(len(value.get('Frames',[]))==2 and all(int(row['scatter_cycles'])==8*int(row['fills'])"
        new="""        require(value.get('CandidateEngine')==build.REQUIRED_MODULES['hdmi_camera_fisheye_engine_tile8'] and
            value.get('CandidateWriter')==build.REQUIRED_MODULES['ddr_adaptive_result_writer_dualstripe'] and
            value.get('CorrectedCoordinatesTiled8x8')is True and value.get('RawCoordinatesRaster')is True,
            'actual tile8 corrected/raw engine and dual-stripe writer evidence required')
        # Bind every executed production RTL/header, including bank, writer,
        # arbitration and display, not just the changed three role names.
        compiled={row['Source']:row for row in plan['CompiledInputs']}
        production,headers,_,_=provider.closure()
        for name in (*production,*headers):
            if name==provider.BENCH:continue
            original=str((ROOT/name).resolve());observed=sources[name];row=compiled.get(name)
            require(plan['InputSHA256'].get(original)==observed and row is not None and
                row['OriginalSHA256']==observed and sha(row['CompiledPath'])==row['CompiledSHA256'] and
                plan['PreparedSHA256'].get(row['CompiledPath'])==row['CompiledSHA256'],
                'tile8 entire executed production source/header differs from built closure: '+name)
            add(watched,row['CompiledPath'],row['CompiledSHA256'])
        require(len(value.get('Frames',[]))==2 and all(int(row['scatter_cycles'])==8*int(row['fills'])"""
        assert text.count(old)==1;text=text.replace(old,new)
    fresh(target,text);rows.append({'Original':ref(source),'New':ref(target)})
for role in SUPPLEMENTS:
    source=TOOLS/f'hdmi_camera_fisheye_fill8r3s3_{role}.py'
    target=TOOLS/f'hdmi_camera_fisheye_tile8_{role}.py'
    fresh(target,renamed(source.read_text(encoding='utf-8-sig')));rows.append({'Original':ref(source),'New':ref(target)})

# New executions require their own root handoffs and schema; current build/raw
# worker's tile8_scoped_native stays exactly as sealed throughout its lifetime.
driver=renamed((OLD_WORK/'run_physical_v2_a.py').read_text(encoding='utf-8-sig'))
driver=driver.replace('s3v2-bounded-b','tile8v2-bounded-b').replace('S3v2','tile8v2').replace('S3','tile8')
driver=driver.replace('provider-revision-v2-source-manifest-a.json','physical-release-provider-source-manifest-a.json')
driver=driver.replace('hdmi-camera-fisheye-tile8v2-provider-source-manifest-v1','hdmi-camera-fisheye-tile8v2-provider-source-manifest-v1')
old="""    note('audit-source-load', Started=True)
    scope_path = WORK / 'audit-a/scope.json'
    scope = build.read(scope_path)
    build.require(scope['Schema'] == physical.AUDIT_SCHEMA and scope['Target'] == build.TARGET and
                  scope['ProposalReady'] is True and scope['Blockers'] == [] and
                  scope['BuildPlan'] == native.ref(build_plan) and
                  scope['ExportReceipt'] == native.ref(refs['ExportReceipt']) and
                  scope['RouteReceipt'] == native.ref(refs['RouteReceipt']),
                  'exact completed original tile8 audit facts required')
    # application_recipe.bind_audit performs one fresh full original audit derive;
    # later calls reuse only its existing full-hash authority cache.
    proposal = physical.scope_plan(scope)"""
new="""    note('audit', Started=True)
    scope, _ = audit.derive(build_plan, refs['ExportReceipt'], refs['RouteReceipt'])
    build.require(scope['Schema'] == physical.AUDIT_SCHEMA and scope['ProposalReady'] is True
                  and scope['Blockers'] == [], 'actual tile8 native audit blocked')
    audit_dir = WORK / 'audit-a'
    audit_dir.mkdir(exist_ok=False)
    scope_path = audit_dir / 'scope.json'
    save(scope_path, scope)
    proposal = physical.scope_plan(scope)"""
assert driver.count(old)==1;driver=driver.replace(old,new)
fresh(WORK/'run_physical_v2_a.py',driver)
release=renamed((OLD_WORK/'run_release_v2_a.py').read_text(encoding='utf-8-sig'))
release=release.replace('s3v2-bounded-b','tile8v2-bounded-b').replace('provider-revision-v2-source-manifest-a.json',
    'physical-release-provider-source-manifest-a.json')
fresh(WORK/'run_release_v2_a.py',release)

helper=renamed((OLD_WORK/'compress_completed_physical_v2_evidence_a.py').read_text(encoding='utf-8-sig'))
fresh(WORK/'compress_completed_physical_v2_evidence_a.py',helper)
manifest=json.loads((OLD_WORK/'physical-compression-helper-source-manifest-v2.json').read_text())
manifest=json.loads(renamed(json.dumps(manifest)))
manifest['OriginalFrozenHelper']=ref(OLD_WORK/'compress_completed_physical_v2_evidence_a.py')
manifest['NewHelper']=ref(WORK/'compress_completed_physical_v2_evidence_a.py')
manifest['CompressionExecuted']=False
with(WORK/'physical-compression-helper-source-manifest-v2.json').open('x',encoding='utf-8')as out:
    json.dump(manifest,out,indent=2);out.write('\n')
testdir=WORK/'physical-release-tests-a';testdir.mkdir()
for source in(OLD_WORK/'root-adapter-tests-v2-a').glob('*.py'):
    fresh(testdir/source.name,renamed(source.read_text(encoding='utf-8-sig')).replace('s3v2-bounded-b','tile8v2-bounded-b').replace(
        'provider-revision-v2-source-manifest-a.json','physical-release-provider-source-manifest-a.json').replace(
        'run_hdmi_camera_fisheye_fill8r3_system_sim','run_hdmi_camera_fisheye_tile8_system_sim'))
summary={'Schema':'hdmi-camera-fisheye-tile8v2-physical-release-adaptation-v1','Prepared':True,'Adapters':rows,
    'Driver':ref(WORK/'run_physical_v2_a.py'),'ReleaseDriver':ref(WORK/'run_release_v2_a.py'),
    'ActiveOriginalTile8ScopedProvider':ref(TOOLS/'hdmi_camera_fisheye_tile8_scoped_native.py'),
    'SharedBuildWorkRemainsTile8':True,'RawReceiptsMustBeActualTile8':True,
    'S3InputsModified':False,'EDAExecuted':False,'PDriveAccessed':False,'HardwareAccessed':False,
    'FinalSourceManifestFrozen':False,'OwnNativeCoreAndFullSimulationStillRequired':True}
with(WORK/'physical-release-adaptation-prebuild-a.json').open('x',encoding='utf-8')as out:json.dump(summary,out,indent=2);out.write('\n')
print(json.dumps({'Adapters':len(rows),'Tests':len(list(testdir.glob('*.py'))),'Prepared':True,'EDAExecuted':False}))
