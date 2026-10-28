"""Post-validate only the fixed720 native0/preparse-gate-error case; never run CAD/devices."""
from pathlib import Path
from datetime import datetime, timezone
import argparse, json, re
import build_raw720_cam2 as b

TARGET=b.TARGET;APPROVED=b.APPROVED
BUILDER_SHA='90c8e84311d959cc1e42d2a27dcf4602dcdee3fed13c03bd8d0984ebcf4586ce'
PREPARED_SHA='accaaba32e8146d60a2d4f78ee2ad44f261215dc41a15cc10d9a3f21efd3be00'
SIM_SHA='6aa9e462dfc3dcadce56dd58992240485560772b73e349bd6674f5c45d27f029'
ORIGINAL_ERROR='ValueError: PDS SRAM generation not successful'
POLICY='raw720-fixed-initial-Tcl-gate-preparse-v1'

def expected_prefix_errors():
    script=str((b.ROOT/b.OWN[3]).resolve())
    report=(b.ROOT/f'board/report_timing/{TARGET}.rtr').as_posix()
    def flow(line):return f'E: Flow-0163: Failed to parse file "{script}" at line {line}. Check if the command options or arguments are valid.'
    return ['E: Missing final timing report',flow(38),
        f'E: couldn\'t open "{report}": no such file or directory',flow(39),
        'E: can\'t read "final_timing_handle": no such variable',flow(40),
        'E: can\'t read "final_timing_handle": no such variable',flow(41),
        'E: can\'t read "final_timing_text": no such variable',flow(44),
        'E: Final timing failed; no bitstream',flow(50)]

def audit_runtime_log(stdout,stderr,work):
    if stderr:raise ValueError('this fixed case requires an empty original stderr')
    work=Path(work).resolve()
    marker=f"Analyzing project file '{(work/(TARGET+'.pds')).as_posix()}'."
    if marker not in stdout:raise ValueError('missing exact actual-project flow boundary')
    before,after=stdout.split(marker,1)
    errors=[line.strip() for line in before.splitlines() if re.match(r'^\s*E:',line)]
    if errors!=expected_prefix_errors():raise ValueError('unrecognized/changed prefix error, script/report path or gate line')
    if re.search(r'(?im)^\s*(?:F:|ERROR\b|FATAL\b)',before):raise ValueError('unexpected fatal/error before flow')
    if re.search(r'(?im)^\s*(?:E:|F:|ERROR\b|FATAL\b)',after):raise ValueError('any actual-flow error is disqualifying')
    first=f'Executing : add_design {(b.ROOT/"rtl/raw_camera_capture.v").as_posix()}'
    if not after.lstrip().startswith(first):raise ValueError('flow does not start at the fixed first source')
    commands=[f'compile -top_module {TARGET}','synthesize -ads -selected_syn_tool_opt 2','dev_map',
        'pnr -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE',
        'report_timing -max_path 5','gen_bit_stream -scbv {High Voltage} -unused_io_status UNUSED']
    positions=[]
    for command in commands:
        matches=list(re.finditer(r'(?m)^Executing : '+re.escape(command)+r' successfully\.\s*$',after))
        if len(matches)!=1:raise ValueError('one successful actual stage required: '+command)
        positions.append(matches[0].start())
    if positions!=sorted(positions):raise ValueError('actual-stage order differs')
    bitline=f'The bitstream file is "{(work/f"generate_bitstream/{TARGET}.sbit").as_posix()}"'
    if after.count(bitline)!=1:raise ValueError('named generated bitstream line differs')
    return {'RecognizedPrefixErrors':errors,'ActualFlowBoundary':marker,'ActualStageSuccesses':commands,
            'RuntimeErrors':0,'PreBitGateExecutionProven':False,
            'GateLimitation':'PDS pre-parser evaluated the custom gate before flow; generated impl.tcl omits it. Acceptance here is POST-build final saved-DB validation, not proof that a runtime pre-bit gate executed.'}

def audit_native_result(result):
    fixed={'Target':TARGET,'Passed':False,'HardwareAccessed':False,'ProcessExitCode':0,'Error':ORIGINAL_ERROR}
    if any(not b.same(result.get(k),v) for k,v in fixed.items()):raise ValueError('only the fixed original native0/log-only rejection is eligible')
    times=[]
    for key in ('StartedUtc','EndedUtc'):
        value=datetime.fromisoformat(result[key])
        if value.tzinfo is None:raise ValueError('aware original build timestamps required')
        times.append(value.timestamp())
    if times[1]<times[0]:raise ValueError('build has not ended in timestamp order')
    return times

def audit_final_timing(text,work,db_time,report_time,bit_time,start_time,end_time):
    if len(re.findall(r'(?m)^Design Summary\s*:',text))!=1 or not re.search(r'(?m)^Design Summary\s*:\s*All Constraints Met\.\s*$',text):raise ValueError('exactly one AllMet final timing summary required')
    db=Path(work)/f'place_route/{TARGET}_pnr.adf'
    if str(db).replace('\\','/').lower() not in text.replace('\\','/').lower():raise ValueError('final report does not reference this saved routed DB')
    if not start_time<=db_time<=report_time<=bit_time<=end_time:raise ValueError('native start -> saved DB -> final timing -> bit -> native end order differs')

def inspect_build(build_dir):
    work=Path(build_dir).resolve()
    if work==APPROVED.resolve() or not work.is_relative_to(APPROVED.resolve()) or not work.is_dir():raise ValueError('ended fixed target below approved scratch required')
    if b.sha(b.__file__)!=BUILDER_SHA or b.sha(b.ROOT/f'board/{TARGET}-sources.json')!=PREPARED_SHA:raise ValueError('frozen original builder/prepared SHA differs')
    prepared=b.verify_sources();plan=b.load(work/'plan.json');result=b.load(work/'build-result.json')
    times=audit_native_result(result)
    expected={'Target':TARGET,'ExecuteBuild':True,'HardwareAccessed':False,'Operation':'offline_compile_route_sram_file_only',
        'NoFlashOrProgrammingOperation':True,'SourceSHA256':prepared['SourceSHA256'],'BuilderSHA256':BUILDER_SHA,
        'PreparedSHA256':PREPARED_SHA,'RawCaptureContract':b.RAW_CONTRACT,'InputModeContract':b.MODE_CONTRACT,
        'SimulationEvidence':plan.get('SimulationEvidence'),'SimulationEvidenceSHA256':SIM_SHA}
    if len(prepared['source_files'])!=109 or not b.same(plan,expected):raise ValueError('sealed original109-source build plan differs')
    simpath=Path(plan['SimulationEvidence']).resolve()
    if b.sha(simpath)!=SIM_SHA:raise ValueError('fixed complete720 integration evidence changed')
    b.verify_simulation(simpath)
    if (work/'plan.json').stat().st_mtime>times[0]:raise ValueError('build plan postdates native build start')
    stdout=b.read_text(work/'build-stdout.log');stderr=(work/'build-stderr.log').read_bytes()
    log_audit=audit_runtime_log(stdout,stderr,work)
    manifest={'Target':TARGET,'Device':'PG2L100H','Package':'FBG676','SCBV':'High Voltage','UnusedIO':'UNUSED',
        'ProcessExitCode':0,'HardwareAccessed':False,'SourceSHA256':prepared['SourceSHA256'],
        'PreparedSHA256':PREPARED_SHA,'BuilderSHA256':BUILDER_SHA,'RawCaptureContract':b.RAW_CONTRACT,
        'GuardedControlContract':b.control_contract(),'InputModeContract':b.MODE_CONTRACT,
        'SimulationEvidence':str(simpath),'SimulationEvidenceSHA256':SIM_SHA,'Limits':b.LIMITS}
    for key,hashkey,relative in [('Bitstream','SHA256',f'generate_bitstream/{TARGET}.sbit'),
        ('TimingReport','TimingSHA256',f'report_timing/{TARGET}.rtr'),('PinReport','PinReportSHA256',f'place_route/{TARGET}_prr.prt'),
        ('FinalRoutedDatabase','FinalRoutedDatabaseSHA256',f'place_route/{TARGET}_pnr.adf'),
        ('AfterHoldTimingReport','AfterHoldTimingSHA256',f'place_route/{TARGET}_timing_summary_after_hold_fix.txt')]:
        path=work/relative
        if not path.is_file() or path.stat().st_size==0:raise ValueError('nonempty named actual artifact required: '+key)
        manifest[key]=str(path);manifest[hashkey]=b.sha(path)
    db=Path(manifest['FinalRoutedDatabase']);final=Path(manifest['TimingReport']);bit=Path(manifest['Bitstream'])
    audit_final_timing(b.read_text(final),work,db.stat().st_mtime,final.stat().st_mtime,bit.stat().st_mtime,*times)
    pins=b.validate_pins(manifest['PinReport'])
    if len(pins)!=129:raise ValueError('all129 actual routed pins required')
    original_names=('plan.json','build-result.json','build-stdout.log','build-stderr.log','impl.tcl')
    originals={name:b.sha(work/name) for name in original_names}
    return {'Policy':POLICY,'Target':TARGET,'Eligible':True,'HardwareAccessed':False,'PDSAccessed':False,
        'ValidationStage':'post_build_final_saved_db','OriginalBuildResultPassed':False,
        'OriginalBuildResultPreserved':True,'BuildDirectory':str(work),'PostValidatorSHA256':b.sha(__file__),
        'OriginalFileSHA256':originals,'LogAudit':log_audit,'SourceCount':109,'RoutedPinCount':129,
        'ProposedManifest':manifest,
        'Limits':'This independent post-validation does not rewrite or upgrade the original builder failure, does not prove pre-bit gate execution, and does not establish physical720/FPS/PLL/optics/temperature safety. No CAD, programming or serial operation is performed.'}

def finalize(build_dir,*,execute=False,plan_path=None):
    if type(execute) is not bool:raise ValueError('explicit boolean finalize flag required')
    work=Path(build_dir).resolve();path=Path(plan_path).resolve() if plan_path else work/'post-validation-plan.json'
    if path.parent!=work or not re.fullmatch(r'post-validation-plan(?:-[a-zA-Z0-9_-]+)?\.json',path.name):raise ValueError('new named validation plan must stay inside this build')
    checked=inspect_build(work)
    if not execute:
        if path.exists():
            if not b.same(b.load(path),checked):raise ValueError('old validation plan differs; use a new named plan, never overwrite')
        else:b.write_new(path,checked)
        return {'Finalize':False,'HardwareAccessed':False,'Plan':str(path),'PlanSHA256':b.sha(path),**checked}
    if not path.is_file() or not b.same(b.load(path),checked):raise ValueError('current sealed post-validation plan required before explicit finalize')
    manifest_path=work/'validated-build.json';receipt_path=work/'post-validation-receipt.json'
    if manifest_path.exists() or receipt_path.exists():raise ValueError('never overwrite existing validation/receipt')
    manifest=dict(checked['ProposedManifest'])
    manifest['PostValidationProof']={'Policy':POLICY,'ValidationStage':'post_build_final_saved_db','PreBitGateExecutionProven':False,
        'OriginalBuildResultPassed':False,'OriginalBuildResultSHA256':checked['OriginalFileSHA256']['build-result.json'],
        'ValidationPlan':str(path),'ValidationPlanSHA256':b.sha(path),'PostValidatorSHA256':b.sha(__file__),
        'ReceiptPath':str(receipt_path)}
    # No monkeypatch: the original frozen builder performs its real final
    # saved-DB/source/simulation/bit/pin validation against this standard schema.
    b.write_new(manifest_path,manifest)
    validated=b.validate_target(work)
    after=inspect_build(work)
    if not b.same(after,checked) or validated!=manifest:raise ValueError('post-validation source/artifact/original evidence changed')
    receipt={'Passed':True,'Target':TARGET,'HardwareAccessed':False,'PDSAccessed':False,'ValidationStage':'post_build_final_saved_db',
        'PreBitGateExecutionProven':False,'OriginalBuildResultPassed':False,'OriginalBuildResultPreserved':True,
        'OriginalFileSHA256':checked['OriginalFileSHA256'],'ValidationPlan':str(path),'ValidationPlanSHA256':b.sha(path),
        'ValidatedBuild':str(manifest_path),'ValidatedBuildSHA256':b.sha(manifest_path),'PostValidatorSHA256':b.sha(__file__),
        'FrozenBuilderValidateTargetCalled':True,'CheckedAtUtc':datetime.now(timezone.utc).isoformat(),
        'Limits':checked['Limits']}
    b.write_new(receipt_path,receipt)
    return {'Finalize':True,'Receipt':str(receipt_path),'ReceiptSHA256':b.sha(receipt_path),**receipt}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build-dir',required=True);parser.add_argument('--plan');parser.add_argument('--finalize',action='store_true');args=parser.parse_args()
    result=finalize(args.build_dir,execute=args.finalize,plan_path=args.plan)
    print(json.dumps(result,indent=2,allow_nan=False));return 0
if __name__=='__main__':raise SystemExit(main())
