"""Fixed INDEX3/5 compact/parity map-only probe. Default plan; no route/bit/board.

Copies the frozen top byte-for-byte. INDEX3 clones FRAME with only5 ->3;
INDEX5 uses the original FRAME bytes/path with no parameter specialization.
All original sources, board constraints and private parameters stay unchanged.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,math,os,re,subprocess,sys
import build_gamma_pipeline_d5 as core

ROOT,TARGET,APPROVED=core.ROOT,core.TARGET,core.APPROVED
COMPACT="rtl/experimental/ddr_compact_neighbour_cache.v"
COMPACT_SHA="bac32945e4f4fe492f92a8b93065462b5c5fca2c247c8b4592d96e8b0f85c753"
sha,load,write_new,stop_owned=core.sha,core.load,core.write_new,core.stop_owned


def derive(work,cache_kind="compact",index_bits=3):
    if cache_kind not in ("compact","parity"):raise ValueError("cache-kind is fixed to compact/parity")
    if type(index_bits) is not int or index_bits not in (3,5):raise ValueError("index-bits is fixed to3/5")
    source=(ROOT/f"board/{TARGET}.v").read_bytes()
    frame_source=(ROOT/core.prepared.FRAME).read_bytes()
    old,new=b".INDEX_BITS(5)",b".INDEX_BITS(3)"
    if frame_source.count(old)!=1:raise ValueError("fixed FRAME index specialization differs")
    frame_bytes=frame_source.replace(old,new) if index_bits==3 else None
    top=work/(TARGET+"_original_top.v")
    frame=work/"pipeline_gamma_frame_engine_index3.v" if index_bits==3 else ROOT/core.prepared.FRAME
    tcl_source=(ROOT/f"board/build-{TARGET}.tcl").read_text(encoding="utf-8")
    boundary=f"compile -force_to_run -top_module {TARGET}\n"
    if tcl_source.count(boundary)!=1:raise ValueError("fixed compile boundary differs")
    prefix=tcl_source.split(boundary)[0]
    def replace_one(text,old,new):
        if text.count(old)!=1:raise ValueError("exact main source line missing: "+old)
        return text.replace(old,new)
    path=lambda name:(ROOT/name).as_posix()
    if cache_kind=="compact":
        prefix=replace_one(prefix,"add_design {"+path(core.prepared.PARITY)+"}","add_design {"+path(COMPACT)+"}")
        prefix=replace_one(prefix,"add_design {"+path(core.prepared.SERIAL)+"}\n","")
    if index_bits==3:
        prefix=replace_one(prefix,"add_design {"+path(core.prepared.FRAME)+"}","add_design {"+frame.as_posix()+"}")
    prefix=replace_one(prefix,"add_design {"+path(f"board/{TARGET}.v")+"}","add_design {"+top.as_posix()+"}")
    tcl=prefix+boundary+"synthesize -force_to_run -ads -selected_syn_tool_opt 2\ndev_map -force_to_run\n"
    if re.search(r"(?m)^\s*(?:pnr|report_timing|gen_bit_stream|cfg_\w+)\b",tcl):
        raise ValueError("map probe contains forbidden routing/programming/bit stage")
    return top,source,frame,frame_bytes,tcl


def parse_resources(path):
    text=core.read_text(path);resources={}
    for name in ("LUT","FF","APM","DRM","IO"):
        values=re.findall(r"(?m)^\|\s*"+name+r"\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|",text)
        if len(values)!=1:raise ValueError("missing/ambiguous DMR resource: "+name)
        used,available=map(int,values[0])
        if not 0<=used<=available:raise ValueError("invalid DMR resource count")
        resources[name]={"used":used,"available":available}
    if resources["IO"]["used"]!=130:raise ValueError("map is not the full130-I/O main top")
    return resources


def run_probe(workdir,*,execute=False,timeout_seconds=1800,pds_bin=None,cache_kind="compact",index_bits=3):
    if type(execute) is not bool or type(timeout_seconds) not in (int,float) or not math.isfinite(timeout_seconds) or not 60<=timeout_seconds<=7200:
        raise ValueError("explicit execute flag and finite60..7200s offline bound required")
    if cache_kind not in ("compact","parity"):raise ValueError("cache-kind is fixed to compact/parity")
    if type(index_bits) is not int or index_bits not in (3,5):raise ValueError("index-bits is fixed to3/5")
    probe_name=TARGET+"_"+cache_kind+"_index"+str(index_bits)+"_map"
    work=Path(workdir).resolve()
    if not APPROVED.is_dir() or work==APPROVED.resolve() or not work.is_relative_to(APPROVED.resolve()) or not work.parent.is_dir() or work.exists():
        raise ValueError("fresh approved scratch child required; no overwrite")
    main=core.prepared.verify_clone()
    if len(main["SourceSHA256"])!=123 or (cache_kind=="compact" and sha(ROOT/COMPACT)!=COMPACT_SHA):
        raise ValueError("frozen main123 or compact revision differs")
    cache_sources={COMPACT:COMPACT_SHA} if cache_kind=="compact" else {n:main["SourceSHA256"][n] for n in (core.prepared.PARITY,core.prepared.SERIAL)}
    helper_paths=[Path(__file__),Path(core.__file__),Path(core.prepared.__file__),ROOT/"tools/run_gamma_pipeline_d5_sim.py",ROOT/"tools/resume_gamma_pipeline_d5.py"]
    helpers={str(p):sha(p) for p in helper_paths}
    config_path=ROOT.parent/"team-config.local.json";config=load(config_path) if config_path.is_file() else {}
    pds=Path(pds_bin or os.environ.get("FPGA_PDS_BIN") or config.get("pds_bin") or r"E:\Pango\PDS_2022.2-SP6.4\bin").resolve()
    if execute and not (pds/"pds_shell.exe").is_file():raise ValueError("existing PDS pds_shell.exe required")
    work.mkdir();top,top_bytes,frame,frame_bytes,tcl_text=derive(work,cache_kind,index_bits);tcl=work/"map-only.tcl"
    with top.open("xb") as f:f.write(top_bytes)
    if frame_bytes is not None:
        with frame.open("xb") as f:f.write(frame_bytes)
    with tcl.open("x",encoding="utf-8") as f:f.write(tcl_text)
    command=[str(pds/"pds_shell.exe"),"-file",str(tcl),"-work_dir",str(work),"-project_name",probe_name]
    plan={"Probe":probe_name,"TopModule":TARGET,"CacheKind":cache_kind,"Stage":"map_only","ExecuteMap":execute,"IndexBits":index_bits,
          "HardwareAccessed":False,"FinalTimingPassed":False,"BitstreamGenerated":False,
          "MainSourceSHA256":main["SourceSHA256"],"CacheSourceSHA256":cache_sources,
          "DerivedTop":str(top),"DerivedTopSHA256":sha(top),"DerivedTclSHA256":sha(tcl),"HelperSHA256":helpers,
          "FrameInput":str(frame),"FrameInputSHA256":sha(frame),"FrameBytesChanged":index_bits==3,
          "OriginalFrameSHA256":sha(ROOT/core.prepared.FRAME),
          "Derivation":"Top byte-for-byte unchanged; INDEX3 scratch FRAME only .INDEX_BITS(5)->(3), INDEX5 original FRAME unchanged. Compact replaces parity/removes unused serial; parity retains both original cache sources. No defparam.",
          "ConstraintSHA256":main["SourceSHA256"][f"board/{TARGET}.fdc"],"ExpectedInputPins":130,
          "OutputDirectory":str(work),"Command":command,"Limits":"Mapping resources only. No placement/routing/physicalpin/timing/bitstream/hardware/fps/new-lens acceptance. Compact full-native regression is independently tracked, not implied by map success."}
    write_new(work/"map-plan.json",plan)
    if not execute:return plan
    result={"Probe":probe_name,"CacheKind":cache_kind,"IndexBits":index_bits,"Passed":False,"Stage":"map_only","HardwareAccessed":False,"FinalTimingPassed":False,
            "BitstreamGenerated":False,"StartedUtc":datetime.now(timezone.utc).isoformat(),"ProcessExitCode":None,"TimedOut":False,
            "MainSourceSHA256":main["SourceSHA256"],"CacheSourceSHA256":cache_sources}
    child=None
    try:
        flags={"creationflags":subprocess.CREATE_NO_WINDOW} if os.name=="nt" else {}
        with (work/"map-stdout.log").open("xb") as stdout,(work/"map-stderr.log").open("xb") as stderr:
            child=subprocess.Popen(command,cwd=work,stdout=stdout,stderr=stderr,**flags);result["OwnedPID"]=child.pid
            try:result["ProcessExitCode"]=child.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:result["TimedOut"]=True;stop_owned(child,work);raise ValueError("owned map-only process exceeded explicit offline bound")
        if type(result["ProcessExitCode"]) is not int or result["ProcessExitCode"]!=0:raise ValueError("native map exit nonzero/unavailable")
        if (core.prepared.verify_clone()!=main or any(sha(ROOT/n)!=h for n,h in cache_sources.items()) or
                any(sha(Path(n))!=h for n,h in helpers.items()) or sha(top)!=plan["DerivedTopSHA256"] or
                sha(frame)!=plan["FrameInputSHA256"] or sha(tcl)!=plan["DerivedTclSHA256"]):
            raise ValueError("main/compact/helper/derived source drift during map probe")
        log=core.read_text(work/"map-stdout.log")+"\n"+core.read_text(work/"map-stderr.log")
        if re.search(r"(?im)^\s*(?:E:|ERROR:|FATAL:)",log) or not re.search(r"(?m)^Executing : dev_map(?: -force_to_run)? successfully\.\s*$",log):
            raise ValueError("device map did not finish cleanly")
        reports=[p for p in (work/"device_map"/f"{TARGET}.dmr",work/"device_map"/f"{probe_name}.dmr") if p.is_file()]
        if len(reports)!=1:raise ValueError("map resource report is missing or ambiguous")
        result.update(Resources=parse_resources(reports[0]),ResourceReport=str(reports[0]),ResourceReportSHA256=sha(reports[0]),Passed=True)
        if (re.search(r"(?m)^Executing : (?:pnr|gen_bit_stream)\b",log) or
                list(work.glob("place_route/*_pnr.adf")) or list(work.glob("generate_bitstream/*.sbit"))):
            result["Passed"]=False;raise ValueError("unexpected route/bit stage directory in map-only probe")
    except (Exception,KeyboardInterrupt) as exc:result["Error"]=type(exc).__name__+": "+str(exc)
    finally:
        if child is not None and child.poll() is None:
            try:stop_owned(child,work)
            except Exception as exc:result["CleanupError"]=str(exc);result["Passed"]=False
        result["MainSourceSHA256After"]={n:sha(ROOT/n) if (ROOT/n).is_file() else None for n in main["SourceSHA256"]}
        result["CacheSourceSHA256After"]={n:sha(ROOT/n) if (ROOT/n).is_file() else None for n in cache_sources}
        if result["MainSourceSHA256After"]!=main["SourceSHA256"] or result["CacheSourceSHA256After"]!=cache_sources:result["Passed"]=False
        result["EndedUtc"]=datetime.now(timezone.utc).isoformat();write_new(work/"map-result.json",result)
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--workdir",required=True);parser.add_argument("--execute-map",action="store_true")
    parser.add_argument("--cache-kind",choices=("compact","parity"),default="compact")
    parser.add_argument("--index-bits",type=int,choices=(3,5),default=3)
    parser.add_argument("--timeout-seconds",type=float,default=1800);parser.add_argument("--pds-bin");args=parser.parse_args()
    try:result=run_probe(args.workdir,execute=args.execute_map,timeout_seconds=args.timeout_seconds,pds_bin=args.pds_bin,cache_kind=args.cache_kind,index_bits=args.index_bits)
    except (ValueError,OSError) as exc:print(str(exc),file=sys.stderr);raise SystemExit(1)
    print(json.dumps(result,indent=2));raise SystemExit(0 if not args.execute_map or result.get("Passed") else 1)
