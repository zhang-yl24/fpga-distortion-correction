"""Resume offline route from sealed map+placement; default plan, no board path.

Retains mapping/placement, not unfinished routing iterations. Canonical build
manifest is produced only by the existing builder's validator. Resume provenance
is separate, and an old timeout/null exit is never upgraded into success.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import json
import math
import os
import subprocess
import sys
import build_gamma_pipeline_d5 as core

ROOT,TARGET,APPROVED=core.ROOT,core.TARGET,core.APPROVED
sha,load,write_new,stop_owned=core.sha,core.load,core.write_new,core.stop_owned


def source_context(previous):
    previous=Path(previous).resolve()
    if not previous.is_relative_to(APPROVED.resolve()) or not previous.is_dir():
        raise ValueError("previous attempt must be a sealed approved scratch directory")
    plan_path=previous/"plan.json";result_path=previous/"gamma-pipeline-build-result.json"
    plan,result=load(plan_path),load(result_path)
    before=core.prepared.verify_clone()
    if (plan.get("Target")!=TARGET or result.get("Target")!=TARGET or type(result.get("TimedOut")) is not bool or
            result.get("SourceSHA256")!=before["SourceSHA256"] or
            result.get("SourceSHA256After")!=before["SourceSHA256"] or plan.get("SourceSHA256")!=before["SourceSHA256"] or
            Path(result.get("OutputDirectory","")).resolve()!=previous or len(before["SourceSHA256"])!=123):
        raise ValueError("old attempt is unsealed or source123 differs; never resume an active/unknown job")
    if result.get("Passed") is True:
        raise ValueError("previous attempt already passed; use its validated artifact instead")
    simulation=core.validate_simulation(plan["SimulationEvidence"]["Path"])
    if simulation["SHA256"]!=plan["SimulationEvidence"]["SHA256"]:
        raise ValueError("old attempt simulation evidence changed")
    mapping=previous/"device_map"/f"{TARGET}_map.adf"
    placement=previous/"place_route"/f"{TARGET}_plc.adf"
    for path in (mapping,placement):
        if not path.resolve().is_relative_to(previous) or path.stat().st_size==0:
            raise ValueError("nonempty owned map/placement DB required")
    context={"PreviousAttempt":str(previous),"PreviousPlan":str(plan_path),"PreviousPlanSHA256":sha(plan_path),
             "PreviousResult":str(result_path),"PreviousResultSHA256":sha(result_path),
             "PreviousTimedOut":result["TimedOut"],"PreviousProcessExitCode":result.get("ProcessExitCode"),
             "PreviousPassed":False,"MapDatabase":str(mapping),"PlacementDatabase":str(placement),
             "InputDatabaseSHA256":{str(p):sha(p) for p in (mapping,placement)},
             "ResumeScope":"Reuse mapped and placed design; restart routing, not an unfinished-route checkpoint"}
    return before,simulation,context


def derive_tcl(work,context):
    text=(ROOT/f"board/build-{TARGET}.tcl").read_text(encoding="utf-8")
    marker=f"compile -force_to_run -top_module {TARGET}\n"
    if text.count(marker)!=1:raise ValueError("fixed target compile boundary differs")
    prefix=text.split(marker)[0]
    if "set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676" not in prefix:
        raise ValueError("full fixed architecture/source/constraint context missing")
    mapping=Path(context["MapDatabase"]).as_posix();placement=Path(context["PlacementDatabase"]).as_posix()
    timing=(work/"report_timing"/f"{TARGET}.rtr").as_posix()
    return prefix+f'''# Reuse only sealed mapping and placement; no compile/synthesis/map restart.
pnr -force_to_run -input_db_file {{{mapping}}} -input_place_db_file {{{placement}}} -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE
report_timing -force_to_run -max_path 5
set timing_file [open {{{timing}}} r]
set timing_summary [read $timing_file]
close $timing_file
if {{[string first {{All Constraints Met}} $timing_summary] < 0}} {{error {{Final timing failed; no bitstream}}}}
gen_bit_stream -force_to_run -scbv {{High Voltage}} -unused_io_status UNUSED
'''


def check_inputs(context,helpers):
    for name,digest in context["InputDatabaseSHA256"].items():
        if sha(Path(name))!=digest:raise ValueError("sealed input DB SHA changed: "+name)
    for path_key,sha_key in (("PreviousPlan","PreviousPlanSHA256"),("PreviousResult","PreviousResultSHA256")):
        if sha(Path(context[path_key]))!=context[sha_key]:raise ValueError("old attempt evidence changed")
    for name,digest in helpers.items():
        if sha(Path(name))!=digest:raise ValueError("resume/build/preparation helper changed")


def run_resume(previous,workdir,*,execute=False,timeout_seconds=7200,pds_bin=None):
    if type(execute) is not bool or type(timeout_seconds) not in (int,float) or not math.isfinite(timeout_seconds) or not 60<=timeout_seconds<=7200:
        raise ValueError("explicit execute flag and finite60..7200s offline bound required")
    work=Path(workdir).resolve()
    if not APPROVED.is_dir() or work==APPROVED.resolve() or not work.is_relative_to(APPROVED.resolve()) or not work.parent.is_dir() or work.exists():
        raise ValueError("fresh B below existing approved scratch required; no overwrite")
    before,simulation,context=source_context(previous)
    helpers={str(p):sha(p) for p in (Path(__file__),Path(core.__file__),Path(core.prepared.__file__),ROOT/"tools/run_gamma_pipeline_d5_sim.py")}
    config_path=ROOT.parent/"team-config.local.json";config=load(config_path) if config_path.is_file() else {}
    pds=Path(pds_bin or os.environ.get("FPGA_PDS_BIN") or config.get("pds_bin") or r"E:\Pango\PDS_2022.2-SP6.4\bin").resolve()
    if execute and not (pds/"pds_shell.exe").is_file():raise ValueError("existing PDS pds_shell.exe required")
    work.mkdir();tcl=work/"resume.tcl"
    with tcl.open("x",encoding="utf-8") as stream:stream.write(derive_tcl(work,context))
    command=[str(pds/"pds_shell.exe"),"-file",str(tcl),"-work_dir",str(work),"-project_name",TARGET]
    plan={"Target":TARGET,"ExecuteResume":execute,"HardwareAccessed":False,"TimeoutSeconds":timeout_seconds,
          "OutputDirectory":str(work),"SourceSHA256":before["SourceSHA256"],"SimulationEvidence":simulation,
          "Context":context,"HelperSHA256":helpers,"DerivedTclSHA256":sha(tcl),"Command":command,
          "HistoricalReferenceParametersOnly":True,"NewLensCorrectionVerified":False}
    write_new(work/"resume-plan.json",plan)
    if not execute:return plan
    result={"Target":TARGET,"Passed":False,"HardwareAccessed":False,"TimedOut":False,"ProcessExitCode":None,
            "StartedUtc":datetime.now(timezone.utc).isoformat(),"OutputDirectory":str(work),"Context":context,
            "SourceSHA256":before["SourceSHA256"]}
    child=None
    try:
        check_inputs(context,helpers)
        if core.prepared.verify_clone()!=before:raise ValueError("source changed before resume")
        with (work/"build-stdout.log").open("xb") as stdout,(work/"build-stderr.log").open("xb") as stderr:
            flags={"creationflags":subprocess.CREATE_NO_WINDOW} if os.name=="nt" else {}
            child=subprocess.Popen(command,cwd=work,stdout=stdout,stderr=stderr,**flags);result["OwnedPID"]=child.pid
            try:result["ProcessExitCode"]=child.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                result["TimedOut"]=True;stop_owned(child,work);raise ValueError("owned resumed PDS exceeded explicit offline bound")
        if type(result["ProcessExitCode"]) is not int or result["ProcessExitCode"]!=0:
            raise ValueError("resumed native exit nonzero/unavailable")
        check_inputs(context,helpers)
        if sha(tcl)!=plan["DerivedTclSHA256"]:raise ValueError("derived resume Tcl changed")
        manifest=core.validate_artifacts(work,before,simulation)
        # Deliberately no resume-only fields in the canonical manifest.
        write_new(work/"validated-build.json",manifest)
        result.update(Passed=True,ValidatedBuild=str(work/"validated-build.json"),ValidatedBuildSHA256=sha(work/"validated-build.json"))
    except (Exception,KeyboardInterrupt) as exc:result["Error"]=type(exc).__name__+": "+str(exc)
    finally:
        if child is not None and child.poll() is None:
            try:stop_owned(child,work)
            except Exception as exc:result["CleanupError"]=str(exc);result["Passed"]=False
        result["SourceSHA256After"]={n:sha(ROOT/n) if (ROOT/n).is_file() else None for n in before["SourceSHA256"]}
        if result["SourceSHA256After"]!=before["SourceSHA256"]:result["Passed"]=False;result["SourceDrift"]=True
        result["InputDatabaseSHA256After"]={n:sha(Path(n)) if Path(n).is_file() else None for n in context["InputDatabaseSHA256"]}
        if result["InputDatabaseSHA256After"]!=context["InputDatabaseSHA256"]:result["Passed"]=False;result["InputDatabaseDrift"]=True
        result["EndedUtc"]=datetime.now(timezone.utc).isoformat();write_new(work/"resume-result.json",result)
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--previous",required=True);parser.add_argument("--workdir",required=True)
    parser.add_argument("--execute-resume",action="store_true");parser.add_argument("--timeout-seconds",type=float,default=7200);parser.add_argument("--pds-bin")
    args=parser.parse_args()
    try:result=run_resume(args.previous,args.workdir,execute=args.execute_resume,timeout_seconds=args.timeout_seconds,pds_bin=args.pds_bin)
    except (ValueError,OSError) as exc:print(str(exc),file=sys.stderr);raise SystemExit(1)
    print(json.dumps(result,indent=2));raise SystemExit(0 if not args.execute_resume or result.get("Passed") else 1)
