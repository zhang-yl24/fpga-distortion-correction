"""Bounded offline K320 one-shot triplet simulation; no PDS/device entry."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback
import zlib

import cv2
import numpy as np
import prepare_gamma_capture_k320_dev as candidate
import run_gamma_pipeline_d5_sim as simtool
import read_gamma_capture_k320_dev as reader
from frozen_gamma_analysis import geometry, metrics

cv2.ocl.setUseOpenCL(False)
ROOT = candidate.ROOT
APPROVED = ROOT / "build/offline-20261024"
COMPILE = ["rtl/"+n+".v" for n in ("dvp_rgb565_capture", "rgb565_burst_pack", "video_async_fifo",
           "camera_live_bridge", "ddr_video_writer", "ddr_uart_frame", "bilinear_rgb", "ddr_remap_sample",
           "mul32_pipe", "pixel_inverse_rotation", "bounded_brown_inverse_mapper")]
COMPILE += ["rtl/experimental/"+n+".v" for n in ("ddr_adaptive_cache", "ddr_adaptive_result_writer",
             "rotated_remap_core_gamma", "adaptive_gamma_frame_engine", "adaptive_gamma_tagged", "adaptive_gamma_stream")]
COMPILE += [candidate.FROZEN]
MANIFEST = APPROVED / "gp200-cam2-selected-manifest-20261026-v2-incomplete.json"


def write_words(path, blob):
    with path.open("x", encoding="ascii") as out:
        for offset in range(0, len(blob), 32):
            out.write(f"{int.from_bytes(blob[offset:offset+32], 'little'):064x}\n")


def make_reference(work, raw_bytes, binding, origin):
    coords, mask = geometry(binding["IntegerConfig"], radius_bound=binding["RadiusGuardQ22"])
    raw = np.frombuffer(raw_bytes, dtype="<u2").reshape(480,640)
    sys.path.insert(0, str(ROOT))
    from model.reference import remap_fixed
    mapped = remap_fixed(metrics.expand(raw).astype(np.uint8), coords[...,0]/256, coords[...,1]/256).astype(np.uint16)
    before = ((mapped[...,0]>>3)<<11)|((mapped[...,1]>>2)<<5)|(mapped[...,2]>>3)
    rr=(before>>11).astype(np.int64);gg=((before>>5)&63).astype(np.int64);bb=(before&31).astype(np.int64)
    lum=(77*((rr<<3)|(rr>>2))+150*((gg<<2)|(gg>>4))+29*((bb<<3)|(bb>>2)))>>8
    samples=lum[~mask]
    mode=0 if len(samples)<307200//4 else 1 if int((samples<64).sum())>=(len(samples)+1)//2 else 2 if int((samples>=192).sum())>=(len(samples)+1)//2 else 0
    tables={bits:np.array([round((v/((1<<bits)-1))**(1,.65,1.45)[mode]*((1<<bits)-1)) for v in range(1<<bits)],dtype=np.uint16) for bits in (5,6)}
    after=(tables[5][before>>11]<<11)|(tables[6][(before>>5)&63]<<5)|tables[5][before&31]
    after[mask]=0
    payloads=(raw_bytes,before.astype("<u2").tobytes(),after.astype("<u2").tobytes())
    for name,payload in zip(("source.mem","result.mem","tone.mem"),payloads):
        write_words(work/name,payload)
    record={"InputOrigin":origin,"GammaModeAfterTwoFrozenWarmupPasses":mode,"MaskedPixels":int(mask.sum()),
            "PixelsPerImage":307200,"IntegerConfig":binding["IntegerConfig"],"RadiusGuardQ22":binding["RadiusGuardQ22"],
            "CRC32":[f"{zlib.crc32(v):08X}" for v in payloads],"DevelopmentOnly":True,"CalibrationAccepted":False}
    with (work/"golden-reference.json").open("x",encoding="utf-8") as out:
        json.dump(record,out,indent=2);out.write("\n")
    return record


def derived_tb():
    text=(ROOT/"tests/tb_gamma_frozen_native.sv").read_text()
    text=candidate.replace_one(text,"module tb_gamma_frozen_native;","module tb_gamma_k320_triplet_native;")
    text=candidate.replace_one(text,'`include "D:/English/FPGA/distortion/build/gamma_frozen_native_sim/config.vh"',
                              '`include "D:/English/FPGA/distortion/'+candidate.CAL+'"\n    `include "D:/English/FPGA/distortion/'+candidate.DOMAIN+'"')
    text=candidate.replace_one(text,"gamma_frozen_capture #(.WIDTH(640),.HEIGHT(480),.BANK_STRIDE(262144))",
                              "gamma_frozen_k320_dev #(.WIDTH(640),.HEIGHT(480),.BANK_STRIDE(262144),.MAX_RADIUS_Q22(ROT_MAX_R2_Q22))")
    text=text.replace("`CAP_","CAL_")
    for name in ("source","golden","tones"):
        text=candidate.replace_one(text,name+"[0:57599]",name+"[0:19199]")
    text=candidate.replace_one(text,"source[(pairs_completed%3)*19200+(row*640+col)/16]","source[(row*640+col)/16]")
    text=candidate.replace_one(text,"txwait=1+(bytes%3)","txwait=1")
    text=candidate.replace_one(text,"wait(pairs_completed==3);if(bytes!=9*(614400+44))",
                              "wait(pairs_completed==1);repeat(1024) @(negedge core_clk);\n        if(pairs_completed!=1 || dut.state!=12 || dut.capture_active || dut.engine_start || dut.export_start || awvalid || arvalid || byte_valid) $fatal(1,\"One-shot target restarted or retained bus ownership\");\n        if(bytes!=3*(614400+44))")
    text=candidate.replace_one(text,'$display("PASS native frozen Gamma capture: three dark/bright/neutral source transactions, nine complete CRC packets, two bypass warmup passes, enhanced pixels, immutable source and export banks, DDR/UART stalls.");',
                              '$display("PASS K320 one-shot triplet: one immutable VGA input, three processing passes, three complete CRC packets, DDR and byte-channel stalls, one-shot hold.");')
    return text.encode()


def actual_t01(binding):
    from calibrate_fisheye_profile import _decode_bound_capture
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    view=next(v for v in manifest["views"] if v["view_id"]=="gp200-cam2-T01-frame1")
    path=Path(view["path"])
    if candidate.sha(path)!=view["sha256"]:
        raise ValueError("T01 image changed")
    image=cv2.imdecode(np.fromfile(path,dtype=np.uint8),cv2.IMREAD_COLOR)
    profile=json.loads(Path(binding["Profile"]).read_text(encoding="utf-8-sig"))
    record=_decode_bound_capture(view,profile,MANIFEST.parent,image,path)
    if record["physical_capture_record"] is not True:
        raise ValueError("Need source-bound actual native T01 capture, not a replay")
    return Path(record["raw_path"]).read_bytes(),record


def run(work, maximum_seconds, case_selection="both"):
    prepared=candidate.verify();binding=prepared["ProfileBinding"]
    if not work.parent.is_dir() or not work.is_relative_to(APPROVED.resolve()) or work.exists():
        raise ValueError("Fresh simulation directory must be under approved scratch")
    protected_names=json.loads((ROOT/"board/corrected_gamma_pipeline_d5-sources.json").read_text())
    protected_names += ["tools/prepare_gamma_pipeline_d5.py","tools/run_gamma_pipeline_d5_sim.py","tools/build_gamma_pipeline_d5.py"]
    protected_names += [p.relative_to(ROOT).as_posix() for pattern in ("*gamma*resume*.py", "*resume*gamma*.py")
                        for p in (ROOT/"tools").glob(pattern)]
    protected={n:candidate.sha(ROOT/n) for n in protected_names}
    sources=dict(prepared["SourceSHA256"])
    for n in (*COMPILE,"tests/tb_gamma_frozen_native.sv","tools/run_gamma_capture_k320_dev_sim.py",
              "tools/read_gamma_capture_k320_dev.py","tools/frozen_gamma_analysis.py","tools/evaluate-tone-pair.py",
              "tools/frame_protocol.py","tools/gamma_triplets.py","model/reference.py","rtl/experimental/gamma_curves.vh","rtl/video_crc32.vh"):
        sources[n]=candidate.sha(ROOT/n)
    work.mkdir(exist_ok=False)
    report={"Target":candidate.TARGET,"Passed":False,"HardwareAccessed":False,"PDSAccessed":False,
            "DevelopmentOnly":True,"CalibrationAccepted":False,"ContinuousMainValidated":False,
            "Revision":"R1","RequestedSuites":case_selection,
            "R1ActualSourceSimulationExecuted":case_selection in ("both","actual-t01"),
            "StartedUtc":datetime.now(timezone.utc).isoformat(),"SourceSHA256":sources,
            "ProtectedMainSourceSHA256":protected,"ProfileBinding":binding,"Suites":{},
            "Limits":candidate.LIMITS+" UART byte_ready/done abstracted; no real baud/fps timing claim. Real raw is replayed into synthetic DVP/DDR, not new hardware capture."}
    deadline=time.monotonic()+maximum_seconds
    try:
        raw,capture=actual_t01(binding)
        y,x=np.indices((480,640),dtype=np.uint16);pattern=(x+y)%4
        dark=(((pattern+2)<<11)|((pattern*2+4)<<5)|(pattern+1)).astype("<u2").tobytes()
        tb=work/"tb_gamma_k320_triplet_native.sv"
        with tb.open("xb") as out:out.write(derived_tb())
        report["DerivedTB"]={"Path":str(tb),"SHA256":candidate.sha(tb),"BaseSHA256":candidate.sha(ROOT/"tests/tb_gamma_frozen_native.sv")}
        cases=(("actual-t01",raw,"actual_bound_native_T01_replayed_into_RTL"),("synthetic-dark",dark,"synthetic_color_pattern_with_new_K320_parameters"))
        for label,pixels,origin in cases:
            if case_selection!="both" and label!=case_selection:
                continue
            case=work/label;case.mkdir(exist_ok=False)
            golden=make_reference(case,pixels,binding,origin)
            if label=="synthetic-dark" and golden["GammaModeAfterTwoFrozenWarmupPasses"]!=1:
                raise ValueError("Dark numerical case does not exercise Gamma1")
            bindir=Path(r"E:\Vivado\Vivado\2017.4\bin")
            simtool.tool(bindir,"xvlog.bat",["--sv",*(str(ROOT/n) for n in COMPILE),str(tb)],case,deadline,"compile")
            simtool.tool(bindir,"xelab.bat",["tb_gamma_k320_triplet_native","-s","gamma_k320_triplet"],case,deadline,"elaborate")
            simtool.tool(bindir,"xsim.bat",["gamma_k320_triplet","-runall","-log","simulation.log"],case,deadline,"simulate")
            log=(case/"simulation.log").read_text(errors="replace")
            if "PASS K320 one-shot triplet:" not in log:
                raise ValueError("Complete triplet/one-shot assertion missing")
            wire=(case/"export.bin").read_bytes()
            checked,_,triple=reader.check_wire(wire)
            if (not checked["passed"] or triple.raw.payload!=pixels or checked["crc32"]!=golden["CRC32"]
                    or checked["mode"]!=golden["GammaModeAfterTwoFrozenWarmupPasses"]):
                raise ValueError("Whole FPGA-formatted wire differs from independent source/golden")
            checked=reader.save_replay(wire,case/"triplet")
            report["Suites"][label]={"Passed":True,"Golden":golden,"WireBytes":len(wire),"WireSHA256":candidate.sha(case/"export.bin"),
                                     "Decoded":str(case/"triplet.json"),"DecodedSHA256":candidate.sha(case/"triplet.json"),
                                     "LogSHA256":candidate.sha(case/"simulation.log"),
                                     "InputCapture":capture if label=="actual-t01" else None,
                                     "FileSHA256":{p.name:candidate.sha(p) for p in case.iterdir() if p.is_file() and p.suffix in (".mem",".json",".bin",".log")}}
    except BaseException as exc:
        report["Error"]=type(exc).__name__+": "+str(exc);report["Traceback"]=traceback.format_exc()
    finally:
        report["SourceSHA256After"]={n:candidate.sha(ROOT/n) for n in sources}
        report["ProtectedMainSourceSHA256After"]={n:candidate.sha(ROOT/n) for n in protected}
        report["SourceUnchanged"]=report["SourceSHA256After"]==sources
        report["MainSourceUnchanged"]=report["ProtectedMainSourceSHA256After"]==protected
        required_count=2 if case_selection=="both" else 1
        report["ExternalMainWatchIsDiagnosticOnly"]=True
        report["MainSourceWriteOperationsByThisRunner"]=[]
        report["Passed"]=len(report["Suites"])==required_count and all(s["Passed"] for s in report["Suites"].values()) and report["SourceUnchanged"]
        report["EndedUtc"]=datetime.now(timezone.utc).isoformat()
        path=work/"gamma-k320-triplet-simulation.json"
        with path.open("x",encoding="utf-8") as out:json.dump(report,out,indent=2,allow_nan=False);out.write("\n")
        print(json.dumps({"Passed":report["Passed"],"Report":str(path),"SHA256":candidate.sha(path),"Error":report.get("Error")}))
    return report["Passed"]


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-name",default="gamma-k320-triplet-sim-20261026")
    parser.add_argument("--maximum-seconds",type=int,default=1500)
    parser.add_argument("--case",choices=("both","actual-t01","synthetic-dark"),default="both")
    parser.add_argument("--execute-simulation",action="store_true")
    args=parser.parse_args()
    if not 60<=args.maximum_seconds<=1800 or not args.work_name or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in args.work_name):
        parser.error("Need fixed approved scratch child name and 60..1800 seconds bound")
    if not args.execute_simulation:
        print(json.dumps({"Target":candidate.TARGET,"HardwareAccessed":False,"PDSAccessed":False,"SimulationStarted":False,
                          "OutputDirectory":str(APPROVED/args.work_name),"SourceCount":len(candidate.verify()["SourceSHA256"])}))
    else:
        raise SystemExit(0 if run((APPROVED/args.work_name).resolve(),args.maximum_seconds,args.case) else 1)
