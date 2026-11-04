"""Single fresh raw implementation probe. Never exports/signs/releases/programs.

--prepare-source is CPU only. --execute needs an exact independent source peer
and exclusive native ownership; it runs the unchanged bounded public build API.
"""
import argparse,ast,copy,hashlib,json,os,re,shutil,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
WORK=Path(__file__).resolve().parent
REPO=WORK.parents[2]
ROOT=REPO/'distortion'
sys.path[:0]=[str(ROOT/'tools'),str(REPO/'.venv/Lib/site-packages')]
import hdmi_camera_fisheye_tile8df8bulk_build as build
import audit_ddr_final_timing as timing

CACHE_SHA='2828700483c478688cddf249608456f4f1253c5091687c11accc98a833b2df6e'
ORIGINAL_BUILD_SHA='80347a12686569d8c49cefd63d86a534a64979690c0d868973d2db2359e2ef61'
OLD_WORK=ROOT/'work/hdmi-camera-fisheye-tile8df8-20261103-a'
PROBE=REPO/'output/tile8_next15h_20261103/new-next-probe-20261104'
FREEZE=WORK/'raw-research-source-manifest-b.json'
RESULT=WORK/'raw-research-result-a.json'
BUILD=WORK/'build-a'

def note(stage,**facts):print(json.dumps(dict(Stage=stage,UTC=build.utc(),**facts)),flush=True)
def ref(path):return dict(Path=str(Path(path).resolve()),SHA256=build.sha(path))
def require(ok,message):build.require(ok,message)

def source_review():
    """Exact replay of all allowed edits, followed by whole-module AST equality."""
    original=ROOT/'tools/hdmi_camera_fisheye_tile8df8_build.py'
    require(build.sha(original)==ORIGINAL_BUILD_SHA,'original frozen build changed')
    text=original.read_text().replace('tile8df8','tile8df8bulk')
    text=text.replace("WORK=ROOT/'work/hdmi-camera-fisheye-tile8df8bulk-20261103-a'","WORK=ROOT/'work/hdmi-camera-fisheye-tile8df8bulk-20261104-a'")
    text=text.replace('rtl/experimental/hdmi_camera_fisheye_engine_tile8df8bulk.v','rtl/experimental/hdmi_camera_fisheye_engine_tile8df8.v')
    text=text.replace('board/hdmi-camera-fisheye-tile8df8bulk-build-sources.json','work/hdmi-camera-fisheye-tile8df8bulk-20261104-a/source/hdmi-camera-fisheye-tile8df8bulk-build-sources.json')
    text=text.replace('board/hdmi-camera-fisheye-tile8df8bulk-internal.fdc','work/hdmi-camera-fisheye-tile8df8bulk-20261104-a/source/hdmi-camera-fisheye-tile8df8bulk-internal.fdc')
    text=text.replace('rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v','work/hdmi-camera-fisheye-tile8df8bulk-20261104-a/source/combined-cache-probe-c.v')
    text=text.replace("'HardwareAccessed':False,'BitstreamRequested':False","'ResearchOnly':True,'FullSimulationPending':True,'ReleaseAllowed':False,'HardwareAccessed':False,'BitstreamRequested':False")
    actual=Path(build.__file__).read_text()
    require(actual==text,'new build differs beyond exact allowed replay')
    require(ast.dump(ast.parse(actual),include_attributes=False)==ast.dump(ast.parse(text),include_attributes=False),'whole build AST differs')
    require(build.WORK==WORK and build.STAGES==['Compile','Synthesize','Device Map','Place','Route','Route Optimize','Report Timing'],'scope/stages differ')
    return dict(ExactSourceReplayPassed=True,WholeModuleASTPassed=True,OriginalBuild=ref(original),NewBuild=ref(build.SELF),
        ChangedProductionRTL=['selected cache only'],AllOtherProductionBytesMustEqualOriginal=True,
        AllowedConstraintChanges='FDC filename only; exact original FDC/RCF bytes retained',
        UnchangedExecutionBudgetSeconds=1800,UnchangedSeed=3,UnchangedReportMaxPath=10000,UnchangedReportNWorst=4)

def finite_checks():
    parser=build.render_tcl(['board/hdmi_camera_fisheye_top.v'],BUILD,'P:/')
    require('pnr -force_to_run -gplace_seed 3 -optimize_multi_corner_timing' in parser,'full placement/route altered')
    require('report_timing -force_to_run -delay_type min_max -max_path 10000 -nworst 4 -report_exception TRUE' in parser,'full timing report altered')
    require(not any(word in parser for word in ('gen_bit_stream','cfg_program','get_pins','export','set_false_path','set_multicycle_path')),'unrequested stage in raw Tcl')
    for value in (True,0,59,1801):
        try:build.recipe(BUILD,maximum=value)
        except ValueError:pass
        else:raise ValueError('invalid raw budget accepted: '+repr(value))
    return dict(Passed=True,InvalidBudgetCasesRejected=4,FullSevenStageTclChecked=True,NoExportQueryPhysicalBitHardwareStage=True)

def add(watched,path,expected=None):
    path=Path(path).resolve();digest=build.sha(path)
    require(expected is None or digest==expected,'input SHA mismatch: '+str(path))
    require(str(path)not in watched or watched[str(path)]==digest,'conflicting source input')
    watched[str(path)]=digest

def local_import_sources(initial):
    pending=list(map(Path,initial));found=set()
    while pending:
        path=pending.pop().resolve()
        if path in found:continue
        found.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            names=([item.name for item in node.names]if isinstance(node,ast.Import)else
                   [node.module]if isinstance(node,ast.ImportFrom)and node.module and node.level==0 else [])
            for name in names:
                target=ROOT/'tools'/(name.split('.')[0]+'.py')
                if target.is_file()and target.resolve()not in found:pending.append(target)
    return sorted(found)

def selected_sources(plan):
    old=build.read(OLD_WORK/'build-a/plan.json')
    old_manifest=build.read(ROOT/'board/hdmi-camera-fisheye-tile8df8-build-sources.json')
    current=build.read(ROOT/build.MANIFEST)
    cache_old='rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v'
    cache_new=build.REQUIRED_MODULES['ddr_neighbour_cache_scatter16_rowpipe']
    replacements={cache_old:cache_new,old_manifest['Constraint']:build.FDC}
    require(current['source_files']==[replacements.get(name,name)for name in old['SourceFiles']],'110 source order differs')
    require(len(plan['SourceFiles'])==110 and len(plan['SourceRoles']['IDFExpandedSources'])==74,'full production/IP closure missing')
    for name,digest in old_manifest['SourceSHA256'].items():
        target=replacements.get(name,name)
        require(current['SourceSHA256'][target]==(CACHE_SHA if name==cache_old else digest),'noncache production source changed: '+name)
    require(build.sha(ROOT/build.FDC)==build.sha(ROOT/old_manifest['Constraint'])=='e27a18c4a5f228ac8543e50c9b50a145f14bf1d4e640ff34361422d32f1bf78a','FDC bytes changed')
    require(build.sha(ROOT/build.RCF)==build.RCF_SHA=='981934688d526e8d686635859d811070752570a34738548154d544e41be48516','RCF changed')
    require(build.sha(ROOT/cache_new)==build.sha(PROBE/'combined-cache-probe-c.v')==CACHE_SHA,'exact cache-c byte copy required')
    require(plan['PLLClocks']==old['PLLClocks'] and plan['InputPixelPeriodNS']==old['InputPixelPeriodNS'],'clock timing changed')
    return dict(ProductionInputs=110,ExpandedDDRIPBodies=74,OnlyCacheRTLBytesDiffer=True,OriginalAndNewFDCBytesEqual=True,RCFUnchanged=True,PLLAndCoreClockUnchanged=True,CacheSHA256=CACHE_SHA)

def functional_inputs(watched):
    files=[PROBE/'combined-unit-c/simulation.json',PROBE/'combined-peer-collision-a/simulation.json',
           REPO/'output/new-next-probe-20261104/combined-normal-small-c/simulation.json',
           REPO/'output/new-next-probe-20261104/combined-sustained-small-c/simulation.json']
    refs=[]
    for path in files:
        value=build.read(path)
        require(value.get('Passed')is True and value.get('InputDrift')==[],'actual successful c unit/collision/small required: '+str(path))
        mapping=value.get('InputSHA256',value.get('SourceSHA256',{}))
        require(CACHE_SHA in mapping.values(),'actual c source identity absent: '+str(path))
        add(watched,path)
        for source,digest in mapping.items():
            src=Path(source);src=src if src.is_absolute()else ROOT/src
            add(watched,src,digest)
        for name,digest in value.get('ArtifactsSHA256',{}).items():
            relative=Path(name);require(not relative.is_absolute()and '..'not in relative.parts,'artifact path escaped')
            add(watched,path.parent/relative,digest)
        refs.append(ref(path))
    return refs

def prepare_source():
    require(not FREEZE.exists()and not BUILD.exists(),'fresh source freeze/build required')
    review=source_review();tests=finite_checks()
    if not (ROOT/build.MANIFEST).exists():build.write_manifest()
    plan,payloads=build.recipe(BUILD,maximum=1800,require_alias=False)
    sources=selected_sources(plan);watched=dict(plan['InputSHA256'])
    for path in (Path(__file__),timing.__file__,ROOT/'tools/hdmi_camera_fisheye_tile8df8_build.py',OLD_WORK/'build-a/plan.json',
                 ROOT/'board/hdmi-camera-fisheye-tile8df8-build-sources.json',PROBE/'combined-cache-probe-c.v'):
        add(watched,path)
    functional=functional_inputs(watched)
    helpers=local_import_sources([Path(__file__),build.SELF,Path(timing.__file__)])
    for helper in helpers:add(watched,helper)
    require(all(build.sha(path)==digest for path,digest in watched.items()),'source drift during preparation')
    value=dict(Schema='tile8df8bulk-raw-research-source-freeze-v1',Passed=True,ResearchOnly=True,
        FullSimulationPending=True,ReleaseAllowed=False,FullNativeSimulationClaimedPassed=False,
        PriorPhysicalSignoffInherited=False,PreparedUTC=build.utc(),SourceReview=review,FiniteChecks=tests,
        SourceDifference=sources,ActualUnitCollisionSmallGates=functional,StaticLocalImportSources=[str(path)for path in helpers],
        ExpectedPlan=plan,ExpectedPreparedSHA256={str(path):build.digest(data)for path,data in payloads.items()},
        InputSHA256=dict(sorted(watched.items())),InputDrift=[],EDAExecuted=False,HardwareAccessed=False)
    build.write(FREEZE,value);note('research-source-ready',Manifest=ref(FREEZE),Inputs=len(watched),PhysicalOrReleaseAllowed=False)

def pds_processes():
    command="$ErrorActionPreference='Stop'; @(Get-CimInstance Win32_Process -Filter \"Name='pds_shell.exe'\"|Select-Object ProcessId,ParentProcessId,CreationDate,CommandLine)|ConvertTo-Json -Compress"
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True,timeout=20,
                          creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    require(result.returncode==0 and not result.stderr,'actual OS PDS query failed')
    text=result.stdout.decode('utf-8-sig').strip()
    if not text:return []
    value=json.loads(text);return value if isinstance(value,list)else[value]

def mapping_result():
    path=BUILD/'synthesize/apm_drm_lutram_utilization.log'
    text=path.read_text(encoding='gb18030',errors='strict')
    rows=[]
    for parity in ('even','odd'):
        for index in range(8):
            name=parity+'_pixels_'+str(index)
            found=[line for line in text.splitlines()if re.search(r'\b'+re.escape(name)+r'\b',line)]
            require(len(found)==1 and all(word in found[0]for word in ('4 K x 8','TRUE_DUAL_PORT','READ_BEFORE_WRITE','GTP_DRM36K_E1')),'actual cache TDP DRM mapping differs: '+name)
            rows.append(dict(Primitive=name,ActualMappingRow=found[0].strip()))
    vm=BUILD/'synthesize/hdmi_camera_fisheye_top_syn.vm';body=vm.read_text(encoding='utf-8',errors='replace')
    require(all(re.search(r'GTP_DRM36K_E1\s*/\*\s*'+row['Primitive']+r'\s*\*/',body)for row in rows),'synthesis netlist lacks exact RAM primitives')
    return dict(Passed=True,CacheDRM36KCount=16,LogicalPixelBytes=65536,TrueDualPortAndReadBeforeWrite=True,
        Utilization=ref(path),SynthesisNetlist=ref(vm),Rows=rows)

def core_result():
    path=BUILD/'report_timing/hdmi_camera_fisheye_top.rtr'
    with path.open(encoding='gb18030',errors='strict')as stream:tables,_=timing.parse_summaries(stream)
    rows=[]
    for corner in ('slow','fast'):
        for kind in ('setup','hold','recovery','removal','mpw'):
            pair=('ddrphy_sysclk',)if kind=='mpw'else('ddrphy_sysclk','ddrphy_sysclk')
            require(pair in tables.get((corner,kind),{}),'ordinary core timing row missing')
            rows.append(dict(Corner=corner,Kind=kind,**tables[(corner,kind)][pair]))
    passed=all(row['FailingChecks']==0 and row['WorstSlackNS']>=0 and row['TotalNegativeSlackNS']==0 for row in rows)
    return dict(Passed=passed,Rows=rows,Report=ref(path),AllTenRequired=True,OnlyOrdinaryCoreChecks=True,PhysicalSignoff=False)

def execute(args):
    require(build.sha(FREEZE)==args.source_manifest_sha,'exact research source manifest SHA required')
    frozen=build.read(FREEZE);require(frozen['Passed']is True and frozen['ReleaseAllowed']is False,'research scope differs')
    require(not BUILD.exists()and not RESULT.exists()and not Path('P:/').exists(),'fresh build/result and free P: required')
    require(build.sha(args.independent_peer)==args.independent_peer_sha,'independent peer SHA differs')
    peer=build.read(args.independent_peer)
    require(peer.get('Passed')is True and peer.get('Independent')is True and peer.get('SourceContractReviewOnly')is True and peer.get('InputDrift')==[],'actual independent source peer required')
    require(peer['InputSHA256'].get(str(Path(__file__).resolve()))==build.sha(__file__)and peer['InputSHA256'].get(str(build.SELF.resolve()))==build.sha(build.SELF),'peer omitted actual controller/build source')
    combined={}
    for mapping in (frozen['InputSHA256'],peer['InputSHA256']):
        for path,digest in mapping.items():
            require(path not in combined or combined[path]==digest,'peer/frozen input SHA conflict: '+path)
            require(build.sha(path)==digest,'input drift before raw probe: '+path)
            combined[path]=digest
    source_review();require(not pds_processes(),'PDS already running')
    require(shutil.disk_usage('D:/').free>=5*2**30,'less than 5GiB free for raw research')
    created=False;result=dict(Schema='tile8df8bulk-raw-research-result-v1',Passed=False,ResearchOnly=True,
        FullSimulationPending=True,ReleaseAllowed=False,HardwareAccessed=False,BitstreamRequested=False,
        PhysicalOrReleaseStageExecuted=False,PriorPhysicalSignoffInherited=False,StartedUTC=build.utc(),
        SourceManifest=ref(FREEZE),IndependentPeer=ref(args.independent_peer),EDAExecuted=False,InputDrift=[])
    try:
        alias=subprocess.run(['subst.exe','P:',str(REPO)],capture_output=True)
        require(alias.returncode==0 and os.path.samefile('P:/',REPO),'owned P: creation failed');created=True
        plan=build.prepare(BUILD,maximum=1800);expected=copy.deepcopy(frozen['ExpectedPlan'])
        require({key:value for key,value in plan.items()if key!='PreparedUTC'}==expected,'actual plan differs from CPU-frozen recipe')
        require(plan['PreparedSHA256']==frozen['ExpectedPreparedSHA256'],'actual prepared bytes differ')
        build.validate(BUILD/'plan.json',require_alias=True);note('actual-raw-start',Plan=ref(BUILD/'plan.json'),CacheSHA256=CACHE_SHA)
        receipt=build.execute(BUILD/'plan.json');result['EDAExecuted']=receipt['EDAExecuted'];result['BuildReceipt']=ref(BUILD/'execution-result.json')
        require(receipt['BuildCompleted']is True,'actual raw build did not complete')
        build.verify_execution(BUILD/'execution-result.json')
        core=core_result();build.write(WORK/'raw-core-timing-a.json',core);result['CoreTiming']=core
        mapping=mapping_result();build.write(WORK/'raw-cache-ram-mapping-a.json',mapping);result['RAMMapping']=mapping
        result['Passed']=core['Passed']and mapping['Passed'];note('raw-research-evaluated',CoreAllTenPassed=core['Passed'],RAMMappingPassed=mapping['Passed'])
    except BaseException as error:
        result['Error']=type(error).__name__+': '+str(error);note('raw-research-error',Error=result['Error'])
    finally:
        if created:
            try:
                require(not pds_processes(),'PDS still alive; retaining owned alias')
                receipt_path=BUILD/'execution-result.json'
                if receipt_path.exists():require(build.read(receipt_path).get('Cleanup',{}).get('Complete')is True,'native cleanup incomplete; retaining alias')
                require(os.path.samefile('P:/',REPO),'owned alias identity changed')
                dropped=subprocess.run(['subst.exe','P:','/D'],capture_output=True)
                require(dropped.returncode==0 and not Path('P:/').exists(),'owned alias release failed')
                created=False;result['OwnedAliasReleased']=True
            except Exception as error:result.update(Passed=False,CleanupError=type(error).__name__+': '+str(error),OwnedAliasReleased=False)
        result['InputDrift']=[path for path,digest in frozen['InputSHA256'].items()if build.sha(path)!=digest]
        if result['InputDrift']:result['Passed']=False
        result['FinishedUTC']=build.utc();build.write(RESULT,result)
    note('raw-research-finished',Passed=result['Passed'],Result=ref(RESULT),ReleaseAllowed=False)
    return 0 if result['Passed']else 2

def main():
    parser=argparse.ArgumentParser(description=__doc__);group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prepare-source',action='store_true');group.add_argument('--execute',action='store_true')
    parser.add_argument('--source-manifest-sha');parser.add_argument('--independent-peer',type=Path);parser.add_argument('--independent-peer-sha')
    args=parser.parse_args()
    if args.prepare_source:prepare_source();return 0
    require(args.source_manifest_sha and args.independent_peer and args.independent_peer_sha,'all exact execution references required')
    return execute(args)

if __name__=='__main__':sys.exit(main())
