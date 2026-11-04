"""Prepare a compact actual-board child; never copy to git, stage, commit or push."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
WORK=REPO/'distortion/work/hdmi-camera-fisheye-assoc2way256-fastpipe-20261104-a'
LAB=REPO/'output/new-next-probe-20261104/assoc2way256-fastpipe-a'
PUB=REPO/'distortion/work/tile8df8-publish-20261104'
DELIVERY='delivery/20261104-hdmi-camera-fisheye-tile8-cache-research'
CHILD=DELIVERY+'/v4-firstpass-camera-20261104'
HEAD='fa32a111c8d2b1ca22beefa9918479fc54573769'
BRANCH='codex/hdmi-camera-fisheye-tile8-directfill'
AUTHORITY_SHA='8d587bf30b8e678116188a0dcd581d258c50b67187660d16b6ae780916a6c482'
PROOF_SHA='4e331eb3b6bf21e12b5f9446e03e477156fefeeeddaeb760ab5eb3224a3b85e0'
MAX_EMBED=32*1024*1024
MAX_TOTAL=128*1024*1024
spec=importlib.util.spec_from_file_location('v4_saved_pack',HERE/'plan_board_followup_a.py')
pack=importlib.util.module_from_spec(spec);spec.loader.exec_module(pack)
verify=pack.verify
require,local=verify.require,verify.local

def sha(path):return verify.digest(path)[1]
def read(path):return json.loads(local(path).read_text(encoding='utf-8-sig'))
def ref(path):return dict(Path=str(Path(path).resolve()),SHA256=sha(path))
def write(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as stream:json.dump(value,stream,indent=2,allow_nan=False);stream.write('\n')

def inventory():
    values={}
    def add(role,path):
        require(role not in values,'duplicate explicit evidence role');values[role]=Path(path).resolve()
    for role,name in (
        ('authority','release-v4-authority-a.json'),('first-pass-proof','final-proof-v2-b.json'),
        ('request','bit-request-v4-a.json'),('closed-sha-witness','bit-request-v4-a-closure-sha-witness.json'),
        ('release-worker','run_release_v4_a.py'),('bit-plan','bit-v4-a/bitstream-plan.json'),
        ('bit-execution','bit-v4-a/execution-result.json'),('bit-verification','bit-v4-a/verification.json'),
        ('pre-bit-audit','bit-v4-a/pre-bit-audit.json'),('bitstream','bit-v4-a/generate_bitstream/hdmi_camera_fisheye_top.sbit'),
        ('bit-native-header','bit-v4-a/generate_bitstream/hdmi_camera_fisheye_top.bgr'),
        ('bit-tcl','bit-v4-a/bitstream.tcl'),('bit-stdout','bit-v4-a/stdout.log'),('bit-stderr','bit-v4-a/stderr.log'),
        ('bit-flow','bit-v4-a/flow.log'),('program-plan','program-v4-reuse-a/plan.json'),('program-receipt','program-v4-reuse-a/receipt.json'),
        ('program-scan-tcl','program-v4-reuse-a/scan.tcl'),('program-program-tcl','program-v4-reuse-a/program.tcl'),
        ('camera30-measurement','fps-corrected-v4-reuse-a/receipt.json'),('camera30-wire','fps-corrected-v4-reuse-a/wire.bin')):
        add(role,WORK/name)
    for role,name in (
        ('first-pass-observation','first-pass-physical-proof-observation-v4-a.json'),
        ('root-firstpass-interruption-observation','firstpass-proof-root-observation-v4-a.json'),
        ('second-pass-stop-request','second-pass-stop-request-v4-a.json'),('second-pass-stop-observation','second-pass-stop-observation-v4-a.json'),
        ('physical-interrupted-launch','physical-continuation-launch-v2-b.json'),('physical-interrupted-exit','physical-continuation-exit-v2-b.json'),
        ('original-disk-full-exit','physical-exit-v1-a.json'),('previous-unknown-wrapper-exit','physical-continuation-exit-v1-b.json'),
        ('previous-export-timeout','physical-export-timeout-observation-v2-b.json'),
        ('release-launcher','launch_release_v4_a.ps1'),('release-launch','release-launch-v4-a.json'),('release-exit','release-exit-v4-a.json'),
        ('release-stdout','release-v4-a.stdout.log'),('release-stderr','release-v4-a.stderr.log'),
        ('camera30-independent-review','board-fps30-independent-review-v4-reuse-a.json'),('board-decoder','verify_board_fps_v4_reuse_a.py'),
        ('camera30-comparison','board30-short-measured-comparison-v4-reuse-a.json'),('camera30-comparison-markdown','board30-short-measured-comparison-v4-reuse-a.md'),
        ('camera30-comparison-source','compare_board30_single_v4_reuse_a.py'),
        ('finite-cadence-scope','sustained-four-frame-cadence-scope-a.json'),('finite-cadence-note','sustained-four-frame-cadence-scope-a.md')):
        add(role,LAB/name)
    for role,name in (('bit-provider','hdmi_camera_fisheye_assoc2way256_fastpipev4_bitstream.py'),
        ('program-provider','hdmi_camera_fisheye_assoc2way256_fastpipev4_program.py'),('camera-measurement-source','measure_hdmi_fisheye_fps.py')):
        add(role,REPO/'distortion/tools'/name)
    for role,name in (('claim-scope-note','CLAIM_SCOPE_NOTE_C.md'),('delivery-preparer','prepare_actual_delivery_v4_e.py')):
        add(role,HERE/name)
    for role,path in (
        ('reuse-helper',WORK/'run_program_saved_v4_b.py'),
        ('reuse-claim',WORK/'saved-verification-program-continuation-v4-b.json'),
        ('reuse-launch',LAB/'release-reuse-launch-v4-b.json'),('reuse-exit',LAB/'release-reuse-exit-v4-b.json'),
        ('reuse-stdout',LAB/'release-reuse-v4-b.stdout.log'),('reuse-stderr',LAB/'release-reuse-v4-b.stderr.log'),
        ('skip-repeated-bit-verification',LAB/'skip-repeated-bit-verification-v4-a.json')):
        add(role,path)
    return values

def exact(record,path,message):require(record==ref(path),message)

def release_identity(launch,ended,authority_sha,worker_sha,launcher_sha,launch_sha):
    require(launch.get('Schema')=='fastpipe-release-launch-v4' and ended.get('Schema')=='fastpipe-release-exit-v4' and
        type(launch.get('PID')) is int and launch['PID']>0 and launch['PID']==ended.get('PID') and
        isinstance(launch.get('CreationUTC'),str) and bool(launch['CreationUTC']) and launch['CreationUTC']==ended.get('CreationUTC') and
        type(ended.get('ExitCode')) is int and ended['ExitCode']==-1 and
        all(d.get('ProcessHandleRetained') is True for d in (launch,ended)) and
        launch.get('AuthoritySHA256')==ended.get('AuthoritySHA256')==authority_sha and
        launch.get('WorkerSHA256')==ended.get('WorkerSHA256')==worker_sha and
        launch.get('LauncherSHA256')==ended.get('LauncherSHA256')==launcher_sha and
        ended.get('LaunchReceiptSHA256')==launch_sha,'actual retained release completion identity required')

def terminal(paths):
    missing=[r for r,p in paths.items() if not local(p).is_file()]
    require(not missing,'actual board delivery evidence pending: '+','.join(missing))
    docs={r:read(paths[r]) for r in ('authority','first-pass-observation','closed-sha-witness','bit-plan','bit-execution','bit-verification',
        'pre-bit-audit','program-plan','program-receipt','release-launch','release-exit','second-pass-stop-observation',
        'physical-interrupted-exit','camera30-measurement','camera30-independent-review','camera30-comparison')}
    auth,proof,witness,bp,ex,vp,gate,pp,pr,launch,ended,stop,oldexit,measured,review,comparison=(docs[r] for r in docs)
    proof_ref=dict(Path=str(paths['first-pass-proof']),SHA256=PROOF_SHA)
    require(sha(paths['authority'])==AUTHORITY_SHA and auth.get('PhysicalProof')==proof_ref,
        'exact executed authority and first-pass proof reference required')
    state=local(paths['first-pass-proof']).stat()
    require(witness['InputSHA256'].get(str(paths['first-pass-proof']))==PROOF_SHA and
        witness['FileIdentity'].get(str(paths['first-pass-proof']))==[state.st_size,state.st_mtime_ns,state.st_ctime_ns,state.st_ino],
        'once-hashed first-pass proof file identity changed')
    require(auth.get('FirstPassCompleted') is True and auth.get('FullFinalReevaluationSkippedAtUserRequest') is True and
        auth.get('FlashAuthorized') is False and stop.get('SecondPassIntentionallyInterrupted') is True and
        stop.get('SecondPassPassed') is False and stop.get('ActualExitCode')==oldexit.get('ExitCode')==-1 and
        all(stop.get(k) is True for k in ('FirstPassProofPreserved','WorkerAbsent','PDSAbsent','PDriveReleased','OriginalExitReceiptPreserved')),
        'first-pass reuse and real interrupted second pass must remain separate')
    require(stop['FirstPassProof']==proof_ref==proof['FirstPassProof'],'interrupted proof reference changed')
    exact(stop['ActualExitReceipt'],paths['physical-interrupted-exit'],'actual interrupted exit reference changed')
    require(proof.get('FirstPassProofComplete') is True and proof.get('NativeResultsAllActualExitZero') is True and
        all(proof['Flags'].get(k) is True for k in ('Passed','STAAllTenPassed','NetlistEquivalent','AllFFPlacementsEquivalent',
            'RoutesUnchanged','ResetAccepted','SourceSamplingIsolatedVerified','NativeWarningsReviewed',
            'VendorDDRClockResetAccepted','FrameBoundaryViewSelectionAccepted','FisheyeProfileAccepted','UserCDCAccepted')),
        'saved firstpass observation is incomplete')
    require(witness.get('AllSHA256VerifiedOnce') is True and witness.get('FullPhysicalOrSimulationRederived') is False,
        'actual once-checked source closure witness required')
    exact(witness['Authority'],paths['authority'],'source witness authority differs')
    exact(witness['Request'],paths['request'],'source witness request differs')
    exact(bp['ClosureWitness'],paths['closed-sha-witness'],'bit plan closure witness differs')
    exact(bp['SavedAuthority'],paths['authority'],'bit plan authority differs')
    release_identity(launch,ended,AUTHORITY_SHA,sha(paths['release-worker']),sha(paths['release-launcher']),sha(paths['release-launch']))
    continuation=read(paths['reuse-claim']);reused_launch=read(paths['reuse-launch']);reused_exit=read(paths['reuse-exit'])
    skipped=read(paths['skip-repeated-bit-verification'])
    require(continuation.get('Schema')=='fastpipe-saved-bit-verification-continuation-v4-b' and
        continuation.get('ReusedVerification') is True and continuation.get('STAReexecuted') is False and
        continuation.get('BitstreamRegenerated') is False and continuation.get('PreviousWorkerPID')==launch['PID'] and
        continuation.get('PreviousWorkerAbsentObserved') is True,'actual saved-verification continuation required')
    exact(continuation['Source'],paths['reuse-helper'],'saved verification helper source changed')
    exact(continuation['SavedVerification'],paths['bit-verification'],'completed verification reuse changed')
    exact(continuation['Authority'],paths['authority'],'reused authority changed')
    require(reused_launch.get('Schema')=='fastpipe-release-reuse-launch-v4-b' and
        reused_exit.get('Schema')=='fastpipe-release-reuse-exit-v4-b' and
        type(reused_launch.get('PID')) is int and reused_launch['PID']>0 and reused_launch['PID']==reused_exit.get('PID') and
        reused_launch.get('CreationUTC')==reused_exit.get('CreationUTC') and bool(reused_launch.get('CreationUTC')) and
        all(d.get('ProcessHandleRetained') is True for d in (reused_launch,reused_exit)) and
        type(reused_exit.get('ExitCode')) is int and reused_exit['ExitCode']==0 and
        reused_launch.get('WorkerSHA256')==reused_exit.get('WorkerSHA256')==sha(paths['reuse-helper']), 'actual successful reuse worker identity required')
    require(not Path('P:/').exists(),'actual reuse alias cleanup is not yet complete')
    require(skipped.get('UserRequestedSkipDuplicate') is True and skipped.get('HardwareClaimAbsent') is True and
        skipped.get('PID')==launch['PID'] and skipped.get('BitVerificationSHA256')==sha(paths['bit-verification']) and
        skipped.get('BitstreamSHA256')==vp['Bitstream']['SHA256'],'actual prehardware interruption must remain preserved')
    require(review['Identity'].get('SavedBitVerificationReused') is True and
        review['Identity'].get('OriginalReleaseWorkerExitCode')==-1 and review['Identity'].get('OriginalReleaseWorkerSuccessClaimed') is False,
        'independent board review must preserve original release interruption')
    exact(review['Identity']['ProgramContinuation'],paths['reuse-claim'],'board review changed programming continuation')
    require(ex.get('ExitCode')==0 and ex.get('TimedOut') is False and ex.get('InputDrift')==[] and not ex.get('Error'),
        'real native bit generation did not pass')
    require(vp.get('Verified') is True and gate.get('GatePassed') is True and all(vp['FreshSTA'].get(k) is True for k in
        ('STAAllTenPassed','ClockAndSummaryIdentityPreserved','AllExceptionPathsPreserved')),'fresh bit STA/exception gate failed')
    require(pr.get('Passed') is True and pr.get('DoneConfirmed') is True and pr.get('ExpectedDeviceAndIDConfirmed') is True and
        pr.get('FlashWritten') is False and pr.get('CleanupErrors')==[] and pp.get('Operation')=='volatile_sram_only',
        'actual SRAM device/DONE completion required')
    bit=pr['Bitstream'];exact({k:bit[k] for k in ('Path','SHA256')},paths['bitstream'],'actual programmed bit differs')
    require(bit.get('Bytes')==local(paths['bitstream']).stat().st_size and bit==pp['Bitstream']==vp['Bitstream']==measured['bitstream'],
        'generated/programmed/measured bit identity differs')
    require(measured.get('passed') is True and measured.get('uart_transmit_bytes')==0 and review.get('Passed') is True and
        review.get('InputDrift')==[] and review.get('TargetFPSNotAssumed') is True and review.get('PixelAppearanceNotVerified') is True,
        'independent actual camera short review required')
    exact(review['Measurement'],paths['camera30-measurement'],'camera review measurement differs')
    exact(review['Identity']['ProgramReceipt'],paths['program-receipt'],'camera review program identity differs')
    exact(review['Identity']['SavedFirstPassAuthority'],paths['authority'],'camera review authority differs')
    require(pr.get('PlanSHA256')==sha(paths['program-plan']) and pr.get('ExecutorSHA256')==sha(paths['program-provider']),
        'actual SRAM plan and executor binding differ')
    require(comparison.get('Schema')=='fastpipe-board30-single-window-comparison-v4' and comparison.get('ReportGenerated') is True and
        comparison.get('Only30SecondsNot600') is True and comparison.get('NoVisual') is True,
        'actual short-window assessment required')
    exact(comparison['Short30Seconds']['Review'],paths['camera30-independent-review'],'comparison changed independent review')
    exact(comparison['Short30Seconds']['Measurement'],paths['camera30-measurement'],'comparison changed measurement')
    assessment=comparison['Assessment']['MeetsRequested30FPSCriteria']
    require(type(assessment) is bool,'actual 30 FPS assessment must be explicit')
    for role,path in paths.items():
        expected=review['InputSHA256'].get(str(path))
        if expected is not None and role!='first-pass-proof':require(sha(path)==expected,'selected independent review input changed: '+role)
    exact({'Path':measured['wire']['path'],'SHA256':measured['wire']['sha256']},paths['camera30-wire'],'raw camera wire differs')
    analysis=review['Analysis'];rates=analysis['IndependentHostRates']
    require(analysis.get('AcquisitionBudgetSeconds')==30 and analysis.get('FaultSamples')==0 and
        analysis.get('BlankScanIncrements')==0 and analysis.get('ClockCrossCheckWithin3Percent') is True and
        all(type(x) in (int,float) and math.isfinite(x) and x>=0 for x in rates.values()) and
        rates.get('unique_presented_frames_per_second',0)>0,'valid actual short camera observations required')
    for name,digest in pr['Logs'].items():
        p=(paths['program-receipt'].parent/name).resolve();require(p.is_relative_to(paths['program-receipt'].parent),'program log escaped')
        require(sha(p)==digest,'actual programming log changed');paths['program-log-'+name]=p
    return dict(Schema='fastpipe-v4-compact-actual-delivery-summary-v1',ActualSavedBoardEvidenceChecked=True,
        FirstPassProofReused=True,FullPhysicalOrSimulationReevaluated=False,SecondPassActualExitCode=-1,
        SecondPassCompleted=False,OriginalReleaseActualExitCode=-1,ReleaseActualExitCode=0,SavedVerificationReused=True,
        ReuseAliasReleasedObservedAtPackaging=True,PackagingObservationUTC=datetime.now(timezone.utc).isoformat(),Bitstream=bit,VolatileSRAMOnly=True,FlashWritten=False,
        ActualAcquisitionBudgetSeconds=30,ActualAcquisitionWallSeconds=analysis['ActualAcquisitionWallSeconds'],
        IndependentHostRates=rates,Only30SecondsNot600=True,LongRun600SecondsClaimed=False,
        MeetsRequested30FPSCriteria=assessment,
        FreshSTA={k:vp['FreshSTA'][k] for k in ('STAAllTenPassed','ClockAndSummaryIdentityPreserved','AllExceptionPathsPreserved')},
        TargetFPSAssumed=False,PixelAppearanceVerified=False,FiniteSimulationAcceptedFrames=4,
        FiniteSimulationNewFrameIntervals=3,HistoricalNativeArtifactsRemainReferenced=True)

def git(*args):
    return subprocess.check_output(['git','-c','core.fsmonitor=false','-C',str(PUB),*args],
        env=dict(os.environ,GIT_OPTIONAL_LOCKS='0')).decode().strip()

def publication_guard():
    require(git('rev-parse','HEAD')==HEAD and git('branch','--show-current')==BRANCH,'original publication branch/base changed')
    require(not git('status','--porcelain','--untracked-files=all'),'publication checkout must remain clean')
    require(not (PUB/CHILD).exists(),'new delivery child must not exist')
    baseline=read(HERE.parent/'publication/research-archive-sealed-c.json')
    require(len(baseline['Files'])==1063,'original 1063 payload inventory required')
    tracked=set(git('ls-files',DELIVERY).splitlines())
    require(all(DELIVERY+'/'+row['BundlePath'] in tracked for row in baseline['Files']),'original published inventory missing')
    return dict(OriginalPayloadCount=1063,BaseHEAD=HEAD,PublicationBranch=BRANCH,CleanTrackedBaseline=True,
        Baseline=ref(HERE.parent/'publication/research-archive-sealed-c.json'),
        OldPayloadsRehashed=False,ProtectionMode='exact original HEAD and clean checkout; only new child paths allowed')

def preview(output):
    paths=inventory();present=[];missing=[]
    for role,path in paths.items():
        (present if local(path).is_file() else missing).append(dict(Role=role,Path=str(path),Bytes=local(path).stat().st_size if local(path).is_file() else None))
    value=dict(Schema='fastpipe-v4-compact-delivery-preview-v1',PreparationOnly=True,Child=CHILD,Present=present,Missing=missing,
        NativeArtifactsRehashed=False,Sealed=False,CopyExecuted=False,GitIndexModified=False,Pushed=False)
    write(output,value);return dict(Preview=str(output),Present=len(present),Missing=len(missing),Sealed=False)

def seal(output):
    paths=inventory();summary=terminal(paths);protection=publication_guard()
    assets=output.with_suffix('');require(not assets.exists(),'fresh compact assets path required');assets.mkdir()
    bundle=assets/'bundle';bundle.mkdir();files=[];logical=[];external=[]
    verified=read(paths['bit-verification']);proof=read(paths['first-pass-observation'])
    original_proof=paths.pop('first-pass-proof')
    external.append(dict(Role='completed-first-pass-proof',Path=str(original_proof),SHA256=PROOF_SHA,
        Bytes=local(original_proof).stat().st_size,Packaged=False,
        Reason='once-hashed exact saved proof/file identity; large JSON not repackaged'))
    for role,name in (('fresh-sta-report','report_timing/hdmi_camera_fisheye_top.rtr'),
                      ('fresh-sta-exceptions','report_timing/hdmi_camera_fisheye_top_exception.rtr')):
        path=WORK/'bit-v4-a'/name;digest=verified['EvidenceSHA256'][name]
        if local(path).stat().st_size<=MAX_EMBED:
            require(sha(path)==digest,'selected fresh STA artifact changed');paths[role]=path
        else:external.append(dict(Role=role,Path=str(path),SHA256=digest,Bytes=local(path).stat().st_size,
            Packaged=False,Reason='large artifact retained by exact successful verification reference'))
    for key in ('Application','FinalExport','FinalRoute','FinalADF'):
        external.append(dict(Role='historical-'+key,**proof[key],Packaged=False,Reason='saved firstpass reference; native artifact not recopied'))
    for index,row in enumerate(proof['FinalQueries']):external.append(dict(Role='historical-FinalQuery-'+str(index),**row,Packaged=False))
    write(assets/'actual-summary.json',summary)
    write(assets/'native-reference-index.json',dict(References=external,ReferenceOnly=True,ReferenceContentsRehashed=False,
        FullNativeReproducibilityClaimed=False,SourceClosureWitness=ref(paths['closed-sha-witness'])))
    rates=summary['IndependentHostRates']
    lines=['# V4 first-pass reuse and camera observation','',
        'This child records actual native bit generation, fresh STA acceptance, volatile SRAM programming and one independently decoded 30-second camera observation.',
        '',f"Measured unique presented frames/s: {rates['unique_presented_frames_per_second']:.6f}. Scan refreshes are a separate counter; the exact rate dictionary and measured duration are in actual-summary.json.",
        '', 'Requested 30 FPS counter criterion: '+('MET.' if summary['MeetsRequested30FPSCriteria'] else 'NOT MET.'),
        '', 'Only the recorded 30-second observation is claimed. No 600-second stability test or visual pixel acceptance is claimed by this package. The comparison report states whether the observed values satisfy its 30 FPS criterion; the goal is not assumed.',
        '', 'The completed first physical proof is reused at the user’s request. Original release worker 24952 was also interrupted with actual exit -1 before hardware access when it repeated already completed bit verification. A separately recorded continuation reused the successful bit verification and performed real SRAM programming and the camera observation. Its redundant second verification was interrupted with actual worker exit -1. The first-pass proof and interruption records remain separate. Earlier disk-full exit1, unknown wrapper exit and export timeout remain preserved.',
        '', 'The bit provider performed one full source SHA pass, then reused exact saved file-identity witnesses for unchanged inputs. Fresh bit-stage STA, exceptions, bit identity and real device/DONE programming checks remained active. No Flash was written.',
        '', 'The simulation accepted four frames by an explicit testbench cap and observed three new-frame intervals near 33.333 ms. This is finite cadence evidence, not a sustained 30 FPS claim over all sixteen source frames.',
        '', 'The package includes selected evidence bytes and the actual sbit. Large historical native artifacts remain exact references in native-reference-index.json and original receipts; they are not repackaged as a complete native build archive.',
        '', 'The original 1,063 research payloads and prior deliveries are outside this append-only child. Run python verify_saved_bundle_a.py --bundle . to verify the packaged bytes only.']
    (assets/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    paths.update({'actual-summary':assets/'actual-summary.json','native-reference-index':assets/'native-reference-index.json',
        'readme':assets/'README.md','portable-verifier':HERE/'verify_saved_bundle_a.py'})
    require(sum(local(p).stat().st_size for p in paths.values())<=MAX_TOTAL,'compact selected bundle exceeds 128MiB; review selection')
    for role,path in paths.items():
        require(local(path).stat().st_size<=MAX_EMBED,'selected evidence exceeds compact bound: '+role)
        name=path.name if role in ('readme','actual-summary','native-reference-index','portable-verifier') else 'evidence/'+role+'/'+path.name
        new,item=pack.pack_file(bundle,path,name,role);files.extend(new);logical.append(item)
    manifest=dict(Schema='tile8-fastpipe-board-saved-byte-manifest-v1',SavedEvidenceOnly=True,HDLReexecuted=False,
        STAReexecuted=False,HardwareAccessed=False,Files=files,LogicalPayloads=logical)
    write(bundle/'sha-manifest.json',manifest);checked=verify.review(bundle)
    for item in logical:
        require(verify.digest(item['OriginalPath'])==(item['Bytes'],item['SHA256']),'selected original bytes changed while packing')
    require(publication_guard()==protection,'publication worktree changed while preparing')
    targets={CHILD+'/'+row['BundlePath']:dict(Bytes=row['Bytes'],SHA256=row['SHA256']) for row in files}
    targets[CHILD+'/sha-manifest.json']=dict(Bytes=(bundle/'sha-manifest.json').stat().st_size,SHA256=sha(bundle/'sha-manifest.json'))
    value=dict(Schema='fastpipe-v4-compact-delivery-plan-v1',Sealed=True,Child=CHILD,PreparedBundle=str(bundle),
        ActualSummary=summary,PortableSavedByteReview=checked,ProtectedPublication=protection,ExactStageTargets=targets,
        CopyExecuted=False,GitIndexModified=False,CommitCreated=False,Pushed=False,NoNetworkWrite=True)
    write(output,value);return dict(Plan=str(output),SHA256=sha(output),Sealed=True,Files=len(files),CopyExecuted=False)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--seal',action='store_true');args=parser.parse_args();output=args.output.resolve()
    require(output.is_relative_to(HERE) and not output.exists(),'fresh local preparation output required')
    print(json.dumps(seal(output) if args.seal else preview(output)))

if __name__=='__main__':main()
