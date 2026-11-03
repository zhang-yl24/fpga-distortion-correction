"""Bounded three-frame pixel-stream/DMA/core regression; never accesses hardware."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import json
import re
import time

import run_hdmi1080_lens_core_small_sim as previous

ROOT=previous.ROOT
BASE=ROOT/"build/offline-20261024/continuous-input1080-20261027-a"
BENCH="tests/tb_hdmi1080_continuous.sv"
COMPILE=tuple(BENCH if n=="tests/tb_hdmi1080_lens_core_small.sv" else n for n in previous.COMPILE)
HELPERS=(*previous.HELPERS,"tools/run_hdmi1080_continuous_sim.py","tools/generate_continuous1080_vectors.py")
REPORT="continuous-simulation.json"
MARKER="PASS hdmi1080 continuous:"
FLAGS={"SyntheticInput":True,"DevelopmentOnly":True,"CalibrationAccepted":False,
       "HardwareReleaseAllowed":False,"NewLensCorrectionVerified":False,"PreBitGateExecutionProven":False,
       "HardwareAccessed":False,"PDSAccessed":False,"SimulationExecuted":False,"RTLResultUsedForGolden":False}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                      parse_constant=lambda n: (_ for _ in ()).throw(ValueError("nonfinite JSON "+n)))


def existing_child(path):
    p=Path(path).resolve()
    if not p.is_dir() or p==BASE.resolve() or not p.is_relative_to(BASE.resolve()):
        raise ValueError("existing child of this approved isolated directory required")
    return p


def fixture_sequence(directory, mode):
    directory=existing_child(directory);metadata=directory/"sequence.json";r=load(metadata)
    w,h=(32,16) if mode=="small" else (1920,1080)
    if (r.get("Schema")!=1 or r.get("SequenceGenerated") is not True or
        (r.get("Width"),r.get("Height"))!=(w,h) or r.get("FrameCount")!=3 or
        r.get("FrameIDs")!=[1,2,3] or r.get("BankExpected")!=[0,1,0] or
        any(r.get(k) is not v for k,v in FLAGS.items())):
        raise ValueError("exact three-frame independent synthetic fixture contract required")
    if (r.get("ExpectedGammaMode")!=0 or r.get("GammaEnableRequired") is not False or
        r.get("Rotation",{}).get("AngleDegrees")!=0 or
        r.get("ReferenceSHA256")!=r.get("ReferenceSHA256After") or
        r.get("InputsAndReferencesUnchanged") is not True):
        raise ValueError("fixed-zero/GM0 independent reference binding differs")
    config=r.get("IntegerConfig")
    if (not isinstance(config,list) or len(config)!=13 or any(type(v) is not int for v in config)
        or not all(config[j]!=0 for j in (8,9,10,11,12))):
        raise ValueError("nonzero radial and tangential13-integer model required")
    watched={str(metadata):sha(metadata)}
    for n,d in r["ReferenceSHA256"].items():
        if sha(n)!=d:raise ValueError("independent CPU reference/input changed: "+n)
        watched[n]=d
    files={}
    for index,frame in enumerate(r["Frames"]):
        if (frame.get("FrameID")!=index+1 or frame.get("BankExpected")!=(index%2) or
            frame.get("PixelCount")!=w*h or frame.get("Length")!=2*w*h):
            raise ValueError("sequence frame identity/payload differs")
        for logical,stem in (("source","source"),("expected","expected"),("masks","masks"),("crc","crc"),("sourcecrc","sourcecrc")):
            item=frame["Files"][logical];p=directory/f"{stem}{index}.mem"
            if Path(item["Path"]).resolve()!=p or p.stat().st_size!=item["Bytes"] or sha(p)!=item["SHA256"]:
                raise ValueError("fixture named hash/size differs: "+str(p))
            watched[str(p)]=item["SHA256"];files[p.name]=p.read_bytes()
        if files[f"crc{index}.mem"].decode("ascii").strip().upper()!=frame["ExpectedPixelCRC32"]:
            raise ValueError("expected CRC file differs")
        if files[f"sourcecrc{index}.mem"].decode("ascii").strip().upper()!=frame["SourcePixelCRC32"]:
            raise ValueError("source CRC file differs")
    if (r["Frames"][0]["SourcePixelCRC32"]==r["Frames"][2]["SourcePixelCRC32"] or
        r["Frames"][0]["ExpectedPixelCRC32"]==r["Frames"][2]["ExpectedPixelCRC32"] or
        r["Frames"][2].get("EverySourcePixelChangedFromFrame0") is not True):
        raise ValueError("new bank0 epoch requires distinct independent source/golden")
    item=r["ConfigInclude"];p=directory/"config.vh"
    if Path(item["Path"]).resolve()!=p or sha(p)!=item["SHA256"]:
        raise ValueError("config include differs")
    files["config.vh"]=p.read_bytes();watched[str(p)]=item["SHA256"]
    return r,watched,files


def positive_count(value):
    if type(value) is int:return value>0
    return isinstance(value,list) and bool(value) and all(type(x) is int and x>=0 for x in value) and sum(value)>0


def run(args):
    mode=args.mode;work=existing_child(args.workdir)
    limit=120 if mode=="small" else 1800
    maximum=limit if args.maximum_seconds is None else args.maximum_seconds
    if type(maximum) is not int or not 1<=maximum<=limit:
        raise ValueError(f"{mode} total budget must be in1..{limit} seconds")
    if any(work.iterdir()):raise ValueError("fresh empty work outputs required; previous evidence never overwritten")
    seq,inputs,fixtures=fixture_sequence(args.sequence_dir,mode)
    sources={n:sha(ROOT/n) for n in (*COMPILE,*previous.base.HEADERS,*HELPERS)}
    for n,d in previous.FROZEN.items():
        if sources.get(n)!=d:raise ValueError("frozen RTL differs: "+n)
    if mode=="native":
        if args.small_report is None:raise ValueError("native requires the completed small continuous receipt")
        small_path=Path(args.small_report).resolve();small=load(small_path)
        if (not small_path.is_relative_to(BASE.resolve()) or small.get("Mode")!="small" or
            small.get("Passed") is not True or small.get("FunctionalPassed") is not True or
            small.get("SourceSHA256")!=sources or small.get("SourceSHA256After")!=sources):
            raise ValueError("small gate failed, changed source, or wrong case; no native execution")
        for n,d in small["LogSHA256"].items():
            if sha(small_path.parent/n)!=d:raise ValueError("small completed log changed")
    else:small_path=None
    if mode=="small":ht,vt,x0,y0,vs,rate,maxcycles=80,40,10,3,1,0,2000000
    else:ht,vt,x0,y0,vs,rate,maxcycles=2200,1125,192,41,5,60,80000000
    timing=(f"localparam integer SIM_HT={ht},SIM_VT={vt},SIM_X0={x0},SIM_Y0={y0},SIM_VS={vs};\n"
            f"localparam integer SIM_FRAMES=3,SIM_MAX_CYCLES={maxcycles},SIM_DISPLAY_RATE={rate};\n")
    fixtures["timing.vh"]=timing.encode("ascii")
    r=dict(Marker="FPGA-1031-INPUT1080-CONTINUOUS-ONE",Mode=mode,Passed=False,FunctionalPassed=False,
           Digital30fpsBudgetMet=False,SyntheticInput=True,DevelopmentOnly=True,HardwareAccessed=False,PDSAccessed=False,
           HardwareAuthorizationGenerated=False,GateState={k:False for k in ("PreBitGateExecutionProven","HardwareReleaseAllowed","NewLensCorrectionVerified","CalibrationAccepted")},
           StartedUtc=datetime.now(timezone.utc).isoformat(),MaximumSeconds=maximum,MaximumSystemCycles=maxcycles,
           SourceSHA256=sources,InputSHA256=inputs,SequenceMetadata=str(Path(args.sequence_dir).resolve()/"sequence.json"),
           Width=seq["Width"],Height=seq["Height"],FrameIDs=[1,2,3],InputPixelClockHz=74250000,SystemClockHz=125000000,
           PixelClockHalfPeriodPs="2000000/297, integer remainder accumulator",HTotal=ht,VTotal=vt,X0=x0,Y0=y0,
           InputFIFOAddrBits=6,InputFIFODataBytes=2048,CorrectionCacheIndexBits=7,CorrectionCacheDataBytes=32768,
           ModeledInputFps=74250000/(ht*vt),ModeledReadbackRequestHz=rate,
           InputDDRPreloaded=False,ProcessingCoreIsProxy=False,DisplayDDRReadbackOnly=True,
           SmallGate=None if small_path is None else dict(Path=str(small_path),SHA256=sha(small_path)),Commands=[])
    deadline=time.monotonic()+maximum
    try:
        for n,data in fixtures.items():
            with (work/n).open("xb") as out:out.write(data)
        r["FixtureSHA256"]={n:sha(work/n) for n in fixtures}
        bin_dir=Path("E:/Vivado/Vivado/2017.4/bin")
        stages=(("xvlog.bat",["--sv",*[str(ROOT/n) for n in COMPILE]],"compile"),
                ("xelab.bat",["tb_hdmi1080_continuous","-s","hdmi1080_continuous"],"elaborate"),
                ("xsim.bat",["hdmi1080_continuous","-runall","-log","simulation.log"],"simulate"))
        for executable,argv,stage in stages:
            entry=dict(Stage=stage,NativeArgv=[str(bin_dir/executable),*argv],ReturnCode=None);r["Commands"].append(entry)
            try:
                previous.base.tool(bin_dir,executable,argv,work,deadline,stage);entry["ReturnCode"]=0
            except (Exception,KeyboardInterrupt) as exc:
                match=re.search(r"failed, exit=(-?\d+)",str(exc))
                if match:entry["ReturnCode"]=int(match.group(1))
                entry["Error"]=str(exc);raise
        text=(work/"simulation.log").read_text(encoding="utf-8",errors="replace")
        if MARKER not in text or re.search(r"(?im)^\s*(?:fatal|error):",text):
            raise ValueError("three-frame completion absent or RTL fatal/error")
        s=load(work/"summary.json");r["Summary"]=s
        w,h=seq["Width"],seq["Height"]
        expected={"passed":True,"width":w,"height":h,"frames_input":3,"frames_committed":3,"frames_processed":3,
                  "frames_readback":3,"source_beats":3*w*h//16,"result_beats":3*w*h//16,"readback_beats":3*w*h//16,
                  "dropped_frames":0,"overflow_frames":0,"no_free_frames":0,"final_drain":True}
        if any(type(s.get(k)) is not type(v) or s[k]!=v for k,v in expected.items()):
            raise ValueError("continuous count/drop/geometry/final-drain contract failed")
        for key,meta in (("source_crc32","SourcePixelCRC32"),("result_crc32","ExpectedPixelCRC32")):
            if [v.upper() for v in s.get(key,[])]!=[f[meta] for f in seq["Frames"]]:
                raise ValueError("actual summary CRC differs from independent per-ID golden")
        required=("write_contention","read_contention","aw_stall","w_stall","physical_ar_stall","same_aw_w","delayed_aw_w")
        missing=[k for k in required if not positive_count(s.get(k))]
        if mode=="small" and (type(s.get("commit_stall")) is not int or s["commit_stall"]<20):missing.append("commit_stall>=20")
        r["CoverageFailures"]=missing
        with (work/"frames.csv").open(encoding="utf-8-sig",newline="") as stream:rows=list(csv.DictReader(stream))
        if len(rows)!=3:raise ValueError("three complete frame timestamp rows required")
        parsed=[]
        for i,row in enumerate(rows):
            q={k:v if "crc" in k else int(v) for k,v in row.items()}
            if (q["frame_id"]!=i+1 or q["source_bank"]!=i%2 or q["result_bank"]!=2+i%2 or
                not q["input_first_ps"]<q["input_last_ps"]<q["commit_ps"]<q["source_release_ps"]<=q["display_grant_ps"]<q["readback_done_ps"] or
                q["result_publish_ps"]>q["display_grant_ps"]):
                raise ValueError("frame epoch/bank/timestamps differ")
            q["end_to_end_model_latency_ms"]=(q["readback_done_ps"]-q["input_first_ps"])/1e9
            q["processing_clock_cycles_from_stamps"]=(q["source_release_ps"]-q["commit_ps"])/8000
            if (q["source_crc32"].upper()!=seq["Frames"][i]["SourcePixelCRC32"] or
                q["result_crc32"].upper()!=seq["Frames"][i]["ExpectedPixelCRC32"] or
                q["scatter_cycles"]!=32*q["fills"]):
                raise ValueError("per-ID pixel CRC or32-cycle cache fill count differs")
            parsed.append(q)
        r.update(FunctionalPassed=True,Frames=parsed,CoveragePassed=not missing,PassLines=[n for n in text.splitlines() if n.startswith("PASS")])
        r["InputFirstPixelIntervalsPs"]=[parsed[i]["input_first_ps"]-parsed[i-1]["input_first_ps"] for i in (1,2)]
        r["NewFrameReadbackIntervalsPs"]=[parsed[i]["readback_done_ps"]-parsed[i-1]["readback_done_ps"] for i in (1,2)]
        r["NewFrameReadbackIntervalsSystemCycles"]=[d/8000 for d in r["NewFrameReadbackIntervalsPs"]]
        r["ReadbackNewFrameFpsOverAllThree"]=(2e12/(parsed[2]["readback_done_ps"]-parsed[0]["readback_done_ps"]))
        r["ProcessingBudgetCycles"]=125000000/30
        r["Digital30fpsBudgetMet"]=mode=="native" and all(max(q["processing_cycles"],q["processing_clock_cycles_from_stamps"])<=125000000/30 for q in parsed)
        r["DigitalBudgetDefinition"]="Each real DMA commit accepted to source released, including ongoing capture-write/readback competition. Readback intervals/rate and full first-pixel latency reported separately over ALL three IDs; no post-drop window, refresh count or steady-state hardware claim."
        r["LongTermSteadyStateProven"]=False
        if mode=="native":
            expected_period_ps=1e12/30
            if any(abs(d-expected_period_ps)>2 for d in r["InputFirstPixelIntervalsPs"]):
                raise ValueError("native input cadence is not30fps under exact rational pixel clock")
        r["Passed"]=not missing and (mode=="small" or r["Digital30fpsBudgetMet"])
        if not r["Passed"]:r["Error"]="coverage missing or processing exceeds declared125MHz/30fps digital budget"
    except (Exception,KeyboardInterrupt) as exc:
        r["Error"]=type(exc).__name__+": "+str(exc)
    finally:
        r["SourceSHA256After"]={n:sha(ROOT/n) for n in sources}
        r["InputSHA256After"]={n:sha(n) for n in inputs}
        r["FixtureSHA256After"]={n:sha(work/n) if (work/n).is_file() else None for n in fixtures}
        if (r["SourceSHA256After"]!=sources or r["InputSHA256After"]!=inputs or r.get("FixtureSHA256")!=r["FixtureSHA256After"]):
            r.update(Passed=False,FunctionalPassed=False,SourceOrFixtureDrift=True)
        r["LogSHA256"]={p.name:sha(p) for p in work.glob("*.log")}
        if (work/"frames.csv").is_file():
            try:
                with (work/"frames.csv").open(encoding="utf-8-sig",newline="") as stream:
                    r["ObservedFrameRowsIncludingPartialRun"]=list(csv.DictReader(stream))
            except (OSError,csv.Error) as exc:r["PartialRowsReadError"]=str(exc)
        r["ResultFiles"]={p.name:sha(p) for n in ("summary.json","frames.csv","events.csv") if (p:=work/n).is_file()}
        r["EndedUtc"]=datetime.now(timezone.utc).isoformat()
        r["Limits"]="RTL pixel-stream model, synthetic nonzero Brown/GM0; no physical HDMI source/chip lock/CDC RAM inference/resources/final STA/optics or hardware FPS. Full data/results remain even if digital throughput or coverage fails. No hardware authorization."
        with (work/REPORT).open("x",encoding="utf-8") as out:json.dump(r,out,indent=2,allow_nan=False);out.write("\n")
    return r


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode",choices=("small","native"),required=True)
    p.add_argument("--workdir",type=Path,required=True)
    p.add_argument("--sequence-dir",type=Path,required=True)
    p.add_argument("--small-report",type=Path)
    p.add_argument("--maximum-seconds",type=int)
    args=p.parse_args()
    try:r=run(args)
    except (ValueError,KeyError,OSError) as exc:p.exit(1,str(exc)+"\n")
    print(json.dumps({"Report":str(args.workdir.resolve()/REPORT),"Passed":r["Passed"],"FunctionalPassed":r["FunctionalPassed"],
                      "Digital30fpsBudgetMet":r["Digital30fpsBudgetMet"],"Commands":r["Commands"],"Error":r.get("Error")},indent=2))
    return 0 if r["Passed"] else 1


if __name__=="__main__":raise SystemExit(main())
