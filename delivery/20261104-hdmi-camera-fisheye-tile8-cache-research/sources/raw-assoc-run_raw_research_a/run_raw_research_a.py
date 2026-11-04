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
import hdmi_camera_fisheye_assoc2way256_build as build
import audit_ddr_final_timing as timing

CACHE_SHA='745f4f2cbc26f733d991eca2998484542a131c47f2d747504194f8ecaca95f0b'
ORIGINAL_BUILD_SHA='80347a12686569d8c49cefd63d86a534a64979690c0d868973d2db2359e2ef61'
OLD_WORK=ROOT/'work/hdmi-camera-fisheye-tile8df8-20261103-a'
PROBE=REPO/'output/new-next-probe-20261104/assoc2way256-a'
FREEZE=WORK/'raw-research-source-manifest-a.json'
RESULT=WORK/'raw-research-result-a.json'
BUILD=WORK/'build-a'

def note(stage,**facts):print(json.dumps(dict(Stage=stage,UTC=build.utc(),**facts)),flush=True)
def ref(path):return dict(Path=str(Path(path).resolve()),SHA256=build.sha(path))
def require(ok,message):build.require(ok,message)

def source_review():
    """Exact replay of all allowed edits, followed by whole-module AST equality."""
    original=ROOT/'tools/hdmi_camera_fisheye_tile8df8_build.py'
    require(build.sha(original)==ORIGINAL_BUILD_SHA,'original frozen build changed')
    text=original.read_text().replace('tile8df8','assoc2way256')
    text=text.replace("WORK=ROOT/'work/hdmi-camera-fisheye-assoc2way256-20261103-a'","WORK=ROOT/'work/hdmi-camera-fisheye-assoc2way256-20261104-a'")
    text=text.replace('rtl/experimental/hdmi_camera_fisheye_engine_assoc2way256.v','work/hdmi-camera-fisheye-assoc2way256-20261104-a/source/hdmi_camera_fisheye_engine_index10_a.v')
    text=text.replace('board/hdmi-camera-fisheye-assoc2way256-build-sources.json','work/hdmi-camera-fisheye-assoc2way256-20261104-a/source/hdmi-camera-fisheye-assoc2way256-build-sources.json')
    text=text.replace('board/hdmi-camera-fisheye-assoc2way256-internal.fdc','work/hdmi-camera-fisheye-assoc2way256-20261104-a/source/hdmi-camera-fisheye-assoc2way256-internal.fdc')
    text=text.replace('rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v','work/hdmi-camera-fisheye-assoc2way256-20261104-a/source/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_b.v')
    text=text.replace("'HardwareAccessed':False,'BitstreamRequested':False","'ResearchOnly':True,'FullSimulationPending':True,'ReleaseAllowed':False,'HardwareAccessed':False,'BitstreamRequested':False")
    text=text.replace("'CacheIndexBits':8,'CacheLogicalBytes':65536","'CacheIndexBits':10,'CacheLogicalBytes':262144,'CacheWays':2,'CacheSets':512,'TagReadPipeline':True")
    actual=Path(build.__file__).read_text()
    require(actual==text,'new build differs beyond exact allowed replay')
    require(ast.dump(ast.parse(actual),include_attributes=False)==ast.dump(ast.parse(text),include_attributes=False),'whole build AST differs')
    require(build.WORK==WORK and build.STAGES==['Compile','Synthesize','Device Map','Place','Route','Route Optimize','Report Timing'],'scope/stages differ')
    return dict(ExactSourceReplayPassed=True,WholeModuleASTPassed=True,OriginalBuild=ref(original),NewBuild=ref(build.SELF),
        ChangedProductionRTL=['selected cache','engine INDEX_BITS8-to10 only'],AllOtherProductionBytesMustEqualOriginal=True,
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
    engine_old='rtl/experimental/hdmi_camera_fisheye_engine_tile8df8.v'
    engine_new=build.REQUIRED_MODULES['hdmi_camera_fisheye_engine_tile8']
    original_engine=(ROOT/engine_old).read_bytes()
    require(original_engine.count(b'.INDEX_BITS(8)')==1,'original engine unique INDEX8 anchor missing')
    require((ROOT/engine_new).read_bytes()==original_engine.replace(b'.INDEX_BITS(8)',b'.INDEX_BITS(10)'),'engine differs beyond unique INDEX8-to10')
    require(build.sha(ROOT/engine_new)=='f5cacc66d2f51a273ed947a107380805461c7ef823b49c46a3c628ebdd027bd8','actual same simulation engine SHA required')
    replacements={cache_old:cache_new,engine_old:engine_new,old_manifest['Constraint']:build.FDC}
    require(current['source_files']==[replacements.get(name,name)for name in old['SourceFiles']],'110 source order differs')
    require(len(plan['SourceFiles'])==110 and len(plan['SourceRoles']['IDFExpandedSources'])==74,'full production/IP closure missing')
    for name,digest in old_manifest['SourceSHA256'].items():
        target=replacements.get(name,name)
        require(current['SourceSHA256'][target]==(CACHE_SHA if name==cache_old else 'f5cacc66d2f51a273ed947a107380805461c7ef823b49c46a3c628ebdd027bd8' if name==engine_old else digest),'noncache production source changed: '+name)
    require(build.sha(ROOT/build.FDC)==build.sha(ROOT/old_manifest['Constraint'])=='e27a18c4a5f228ac8543e50c9b50a145f14bf1d4e640ff34361422d32f1bf78a','FDC bytes changed')
    require(build.sha(ROOT/build.RCF)==build.RCF_SHA=='981934688d526e8d686635859d811070752570a34738548154d544e41be48516','RCF changed')
    require(build.sha(ROOT/cache_new)==build.sha(PROBE/'rtl/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_b.v')==CACHE_SHA,'exact cache-c byte copy required')
    require(plan['PLLClocks']==old['PLLClocks'] and plan['InputPixelPeriodNS']==old['InputPixelPeriodNS'],'clock timing changed')
    return dict(ProductionInputs=110,ExpandedDDRIPBodies=74,OnlyCacheAndEngineRTLBytesDiffer=True,CacheWays=2,CacheSets=512,CacheIndexBits=10,CacheLogicalBytes=262144,OriginalAndNewFDCBytesEqual=True,RCFUnchanged=True,PLLAndCoreClockUnchanged=True,CacheSHA256=CACHE_SHA)

def functional_inputs(watched):
    files=[PROBE/'unit-c/simulation.json',PROBE/'boundary-a/simulation.json',
           PROBE/'system-normal-small-b/simulation.json',PROBE/'system-sustained-small-b/simulation.json']
    refs=[]
    for path in files:
        value=build.read(path)
        require(value.get('Passed')is True and value.get('InputDrift')==[],'actual successful c unit/collision/small required: '+str(path))
        mapping=value.get('InputSHA256',value.get('SourceSHA256',{}))
        require(CACHE_SHA in mapping.values(),'actual c source identity absent: '+str(path))
        if path.parent.name.startswith('system-'):
            require(value.get('CacheIndexBits')==10 and value.get('SetIndexBits')==9 and value.get('Ways')==2
                    and value.get('CacheCapacityBytes')==262144,'small simulation geometry is not the selected 256KiB/two-way design')
            require('f5cacc66d2f51a273ed947a107380805461c7ef823b49c46a3c628ebdd027bd8' in mapping.values()
                    and value.get('OriginalAllPixelCRCOracleAndOwnershipAssertionsRetained')is True,
                    'same INDEX10 engine and complete original small assertions required')
        add(watched,path)
        for source,digest in mapping.items():
            src=Path(source);src=src if src.is_absolute()else ROOT/src
            add(watched,src,digest)
        for name,digest in value.get('ArtifactsSHA256',{}).items():
            relative=Path(name);require(not relative.is_absolute()and '..'not in relative.parts,'artifact path escaped')
            add(watched,path.parent/relative,digest)
        for name,digest in value.get('OutputSHA256',{}).items():
            relative=Path(name);require(not relative.is_absolute()and '..'not in relative.parts,'small output artifact path escaped')
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
                 ROOT/'board/hdmi-camera-fisheye-tile8df8-build-sources.json',PROBE/'rtl/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_b.v'):
        add(watched,path)
    functional=functional_inputs(watched)
    for path in (PROBE/'source-ready-b.json',PROBE/'assoc2-tagpipe-b-independent-design-peer-a.json',PROBE/'rtl/hdmi_camera_fisheye_engine_index10_a.v'):
        add(watched,path)
    assoc_peer=build.read(PROBE/'assoc2-tagpipe-b-independent-design-peer-a.json')
    require(assoc_peer.get('Passed')is True and assoc_peer.get('InputDrift')==[],'actual independent 2way source/unit/boundary review required')
    for path,digest in assoc_peer['InputSHA256'].items():add(watched,path,digest)
    ready=build.read(PROBE/'source-ready-b.json')
    require(ready.get('Passed')is True and ready.get('InputDrift')==[],'actual final associative source snapshot required')
    for path,digest in ready['InputSHA256'].items():add(watched,path,digest)
    helpers=local_import_sources([Path(__file__),build.SELF,Path(timing.__file__)])
    for helper in helpers:add(watched,helper)
    require(all(build.sha(path)==digest for path,digest in watched.items()),'source drift during preparation')
    value=dict(Schema='assoc2way256-raw-research-source-freeze-v1',Passed=True,ResearchOnly=True,
        FullSimulationPending=True,ReleaseAllowed=False,FullNativeSimulationClaimedPassed=False,
        PriorPhysicalSignoffInherited=False,PreparedUTC=build.utc(),SourceReview=review,FiniteChecks=tests,
        SourceDifference=sources,AssociativeSourceAndUnitPeer=ref(PROBE/'assoc2-tagpipe-b-independent-design-peer-a.json'),ActualUnitCollisionSmallGates=functional,StaticLocalImportSources=[str(path)for path in helpers],
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
    rows=[];counts={};bits={'even':0,'odd':0};seen=set()
    for line in text.splitlines():
        columns=[part.strip()for part in line.split('|')[1:-1]]
        if not columns or not re.fullmatch(r'(even|odd)_pixels_\d+(?:_\d+)*',columns[0]):continue
        require(len(columns)==7,'actual pixel RAM report columns differ')
        name,sizea,sizeb,writea,writeb,mode,primitive=columns
        require(name not in seen,'duplicate actual pixel RAM primitive');seen.add(name)
        require(mode=='TRUE_DUAL_PORT' and writea==writeb=='READ_BEFORE_WRITE' and
                primitive in ('GTP_DRM36K_E1','GTP_DRM18K_E1'),'pixel RAM did not map to required TDP/RBW DRM: '+name)
        def geometry(value):
            found=re.fullmatch(r'(\d+)\s*([KM]?)\s*x\s*(\d+)',value)
            require(found is not None,'unrecognized actual RAM geometry: '+value)
            return int(found[1])*({'':1,'K':1024,'M':1024*1024}[found[2]]),int(found[3])
        da,wa=geometry(sizea);db,wb=geometry(sizeb)
        require((da,wa)==(db,wb),'asymmetric pixel RAM port mapping')
        parity=name.split('_',1)[0];bits[parity]+=da*wa;counts[primitive]=counts.get(primitive,0)+1
        rows.append(dict(Primitive=name,Type=primitive,Depth=da,PortDataWidth=wa,LogicalBits=da*wa,ActualMappingRow=line.strip()))
    require(rows and bits=={'even':1048576,'odd':1048576},'actual pixel RAM total capacity differs from 256KiB')
    vm=BUILD/'synthesize/hdmi_camera_fisheye_top_syn.vm';body=vm.read_text(encoding='utf-8',errors='replace')
    require(all(re.search(re.escape(row['Type'])+r'\s*/\*\s*'+re.escape(row['Primitive'])+r'\s*\*/',body)for row in rows),'synthesis netlist lacks exact RAM primitives')
    return dict(Passed=True,CachePrimitiveCounts=counts,CachePrimitiveCount=len(rows),LogicalPixelBytes=sum(bits.values())//8,
        LogicalBitsByParity=bits,ExpectedWays=2,ExpectedSets=512,ExpectedPhysicalLines=1024,
        DRM36Equivalent=counts.get('GTP_DRM36K_E1',0)+counts.get('GTP_DRM18K_E1',0)/2,
        PrimitiveCountPresupposed=False,TrueDualPortAndReadBeforeWrite=True,
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
    created=False;result=dict(Schema='assoc2way256-raw-research-result-v1',Passed=False,ResearchOnly=True,
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
