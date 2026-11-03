"""Fresh INDEX8 direct-fill PDS plus raw native inspection only when ordinary core timing passes."""
from pathlib import Path
import json,os,shutil,subprocess,sys
WORK=Path(__file__).resolve().parent
PEER_WORK=WORK.with_name('hdmi-camera-fisheye-tile8df9-20261103-a')
REPO=WORK.parents[2]
sys.path[:0]=[str(REPO/'distortion/tools'),str(REPO/'.venv/Lib/site-packages')]
import hdmi_camera_fisheye_tile8df8_build as build
import hdmi_camera_fisheye_tile8df8_native as native
import hdmi_camera_fisheye_tile8df8_scoped_native as scoped
import audit_ddr_final_timing as timing

def note(stage,**values):print(json.dumps({'Stage':stage,**values}),flush=True)
def disk(stage,minimum):
    amount=shutil.disk_usage('D:/').free;note(stage,DiskFreeBytes=amount,MinimumBytes=minimum)
    build.require(amount>=minimum,'insufficient free disk for '+stage)

def compress_completed(stage):
    helper=WORK/'compress_completed_physical_v2_evidence_a.py'
    manifest=build.read(WORK/'physical-compression-helper-source-manifest-v2.json')
    build.require(build.ref(helper)==manifest['NewHelper'],'completed-stage compression helper drift')
    subprocess.run([sys.executable,'-B',str(helper),'--stage',stage,'--tag','raw-a'],
                   check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

def bind_peer_collision():
    path=PEER_WORK/'cache-commit-collision-a/simulation.json';value=build.read(path)
    build.require(value.get('Schema')=='tile8-directfill-independent-peer-commit-collision-v1' and
                  value.get('Passed')is True and value.get('HDLSimulationExecuted')is True and
                  value.get('InputDrift')==[] and value.get('PDSAccessed')is False and
                  value.get('HardwareAccessed')is False and not value.get('Error'),
                  'actual independent final-RAM-commit collision simulation required')
    for name,digest in value['SourceSHA256'].items():
        build.require(build.sha(name)==digest,'peer collision source drift: '+name)
    for name,digest in value['ArtifactsSHA256'].items():
        relative=Path(name)
        build.require(not relative.is_absolute() and '..' not in relative.parts,
                      'peer artifact path escaped actual output')
        build.require(build.sha(path.parent/relative)==digest,'peer collision artifact drift: '+name)
    summary=value['Summary']
    build.require(summary.get('IndexBits')==9 and summary.get('Cases')==4 and
                  summary.get('IndependentRAMPixelsChecked')==864 and
                  summary.get('SuccessfulCommonResetRecoveries')==4 and
                  all(summary.get(name)is True for name in ('Passed','NinthRAndLastCommitCollision',
                      'MalformedFinalRID','MissingFinalRLAST','ResetBeforeFinalRAMCommit','FaultQuarantineChecked')),
                  'complete actual collision/reset recovery coverage required')
    expected=['0,ninth_R_vs_last_commit,128,4,0','1,malformed_final_R,112,3,0',
              '2,malformed_final_R,112,3,0','3,common_reset_vs_last_commit,0,0,0']
    build.require((path.parent/'peer-commit-cases.csv').read_text().splitlines()[1:]==expected,
                  'actual collision case trace differs')
    log=(path.parent/'simulation.log').read_text(encoding='utf-8',errors='replace')
    build.require('PASS DIRECTFILL PEER real final-commit/fault/reset collisions' in log and
                  '$finish called' in log,'independent peer RTL simulation did not complete')
    return build.ref(path)

def main():
    build.require(native.build is build and scoped.build is build and scoped.raw_native is native,'df8 provider imports differ')
    from hdmi_camera_fisheye_directfill_contract import review as cache_source_review
    import run_hdmi_camera_fisheye_tile8df8_system_sim as system_sim
    unit_path=PEER_WORK/'cache-unit-a/simulation.json';unit=build.read(unit_path)
    build.require(unit.get('Passed')is True and unit.get('InputDrift')==[],
                  'actual independent direct-fill cache test required')
    candidate=build.ROOT/build.REQUIRED_MODULES['ddr_neighbour_cache_scatter16_rowpipe']
    source_review,cache_inputs=cache_source_review(candidate)
    build.require(source_review.get('Passed')is True,'current pinned direct-fill source review required')
    peer_collision=bind_peer_collision()
    build.require(unit['SourceSHA256'].get(str(candidate))==build.sha(candidate),
                  'direct-fill cache regression must bind the exact built source')
    for source_name,h in unit['SourceSHA256'].items():
        build.require(build.sha(source_name)==h,'cache unit source drift: '+source_name)
    for path in (WORK/'system-small-a/simulation.json',WORK/'system-native-a/simulation.json'):
        checked,watched=system_sim.verify(path)
        build.require(checked.get('Passed')is True and checked.get('FunctionalPassed')is True and
                      checked.get('InputDrift')==[] and checked.get('DirectFillCache')is True and
                      checked.get('CacheIndexBits')==8,'own complete direct-fill system gate required')
    writer_path=build.ROOT/'work/hdmi-camera-fisheye-tile8-20261103-a/writer-unit-c/simulation.json'
    writer=build.read(writer_path)
    build.require(writer.get('Passed')is True and writer.get('InputDrift')==[],
                  'unchanged dualstripe writer completed unit gate required')
    for source_name,h in writer['SourceSHA256'].items():
        source_path=Path(source_name)if Path(source_name).is_absolute()else build.ROOT/source_name
        build.require(build.sha(source_path)==h,'unchanged writer source drift: '+source_name)
    note('candidate-functional-gates',CacheUnit=build.ref(unit_path),
         SystemNative=build.ref(WORK/'system-native-a/simulation.json'),
         SourceReviewPassed=True,CacheIndexBits=8,DirectFillCache=True,PeerCollision=peer_collision)
    build.require(not Path('P:/').exists(),'P: must be free before owned df8 alias creation')
    disk('df8-build-preflight',5*2**30)
    created=subprocess.run(['subst.exe','P:',str(REPO)],capture_output=True)
    build.require(created.returncode==0 and os.path.samefile('P:/',REPO),'owned df8 P: creation failed')
    completed=False
    try:
        plan=build.prepare(WORK/'build-a',maximum=1800)
        build.validate(WORK/'build-a/plan.json',require_alias=True)
        longest=max(plan['PreparedSHA256'],key=len);build.add({},longest,plan['PreparedSHA256'][longest])
        build.write(WORK/'build-started-a.json',{'Schema':'hdmi-camera-fisheye-tile8df8-build-started-v1','StartedUTC':build.utc(),
            'BuildPlan':build.ref(WORK/'build-a/plan.json'),'BuildProvider':build.ref(build.SELF),
            'NativeProvider':native.ref(native.SELF),'ScopedNativeProvider':scoped.ref(scoped.SELF),
            'CacheTest':build.ref(unit_path),'LongPathInputLength':len(longest),'LongPathAddPassed':True,'HardwareAccessed':False})
        note('df8-actual-build-start',Work=str(WORK/'build-a'),ProviderSHA256=build.sha(build.SELF),CacheSHA256=build.sha(candidate))
        result=build.execute(WORK/'build-a/plan.json')
        note('df8-build-result',**{k:result.get(k)for k in ('BuildCompleted','ElapsedSeconds','ExitCode','Error','TimedOut','InputDrift','NativeErrors')})
        build.require(result['BuildCompleted'],'df8 actual build failed')
        build.verify_execution(WORK/'build-a/execution-result.json')
        report=WORK/'build-a/report_timing'/(build.TARGET+'.rtr')
        with report.open(encoding='gb18030',errors='strict')as stream:tables,_=timing.parse_summaries(stream)
        core=[{'Corner':corner,'Kind':kind,**rows[pair]}for (corner,kind),rows in tables.items()
            for pair in [('ddrphy_sysclk',)]if kind=='mpw'and pair in rows]
        core += [{'Corner':corner,'Kind':kind,**rows[('ddrphy_sysclk','ddrphy_sysclk')]}for (corner,kind),rows in tables.items()
            if kind!='mpw'and ('ddrphy_sysclk','ddrphy_sysclk')in rows]
        passed=len(core)==10 and all(r['FailingChecks']==0 and r['WorstSlackNS']>=0 and r['TotalNegativeSlackNS']==0 for r in core)
        build.write(WORK/'raw-core-timing-a.json',{'Schema':'hdmi-camera-fisheye-tile8df8-raw-core-timing-v1','Passed':passed,
            'Report':build.ref(report),'Rows':core,'OnlyOrdinaryCoreChecks':True,'PhysicalReleaseAllowed':False})
        note('df8-raw-core-timing',Passed=passed,Rows=core)
        if not passed:
            build.write(WORK/'raw-native-not-run-a.json',{'Schema':'hdmi-camera-fisheye-tile8df8-raw-native-not-run-v1',
                'BuildCompleted':True,'OrdinaryCoreTimingPassed':False,'NativeEDAExecuted':False,
                'Reason':'Own complete raw core timing fails; no export/report or physical application is authorized by this worker.',
                'BuildReceipt':build.ref(WORK/'build-a/execution-result.json'),'HardwareAccessed':False})
            return 2
        for name,mode in [('export-a','export'),('route-a','report')]:
            disk('df8-native-'+mode,3*2**30);note('df8-native-prepare',Mode=mode,Work=str(WORK/name))
            nplan=native.prepare(WORK/'build-a/plan.json',WORK/name,mode,maximum=600)
            result=native.execute(nplan)
            note('df8-native-result',Mode=mode,**{k:result.get(k)for k in ('ExecutionPassed','ElapsedSeconds','ExitCode','Error','InputDrift','SourceADFUnchanged','IndependentADFCopyUnchanged')})
            build.require(result['ExecutionPassed'],'df8 actual native '+mode+' failed')
            _,watched=native.bind_receipt(WORK/name/'result.json');note('df8-native-verified',Mode=mode,InputCount=len(watched))
            compress_completed(name)
        completed=True
    finally:
        build.require(os.path.samefile('P:/',REPO),'df8 owned alias changed before cleanup')
        subprocess.run(['subst.exe','P:','/D'],check=True,capture_output=True)
        build.require(not Path('P:/').exists(),'df8 P: cleanup failed')
        note('df8-worker-cleanup',PriorWorkerEnded=True,PDriveReleased=True,Completed=completed)
    if completed:
        build.write(WORK/'raw-native-completed-a.json',{'Schema':'hdmi-camera-fisheye-tile8df8-raw-native-completed-v1',
            'PriorWorkerEnded':True,'PDriveReleased':True,'BuildPlan':build.ref(WORK/'build-a/plan.json'),
            'ExportReceipt':build.ref(WORK/'export-a/result.json'),'RouteReceipt':build.ref(WORK/'route-a/result.json'),
            'CompletedUTC':build.utc(),'HardwareAccessed':False})
    return 0

if __name__=='__main__':raise SystemExit(main())
