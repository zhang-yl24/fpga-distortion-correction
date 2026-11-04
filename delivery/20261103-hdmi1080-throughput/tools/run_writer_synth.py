"""Isolated PDS synthesis cost probe, no pin mapping, timing signoff or hardware."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[1]
BASELINE = ROOT / "delivery/20261103-hdmi1080-demo-source/native/source/rtl"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work",type=Path,required=True)
    parser.add_argument("--pds-shell",type=Path,required=True)
    args=parser.parse_args()
    args.work=args.work.resolve()
    args.work.mkdir(parents=True,exist_ok=False)
    report={"passed":False,"hardware_accessed":False,"pds_accessed":True,
        "scope":"isolated unconstrained synthesis only; no device_map/place/route or timing signoff",
        "derived_copy_changes":["top defaults WIDTH=1920 HEIGHT=1080", "remove external frame_tiled port and tie its internal net to 0", "bind CRC header include to local copied file"],
        "variants":{}}
    for variant in ("baseline","candidate"):
        work=(args.work / variant).resolve()
        work.mkdir(exist_ok=False)
        source=BASELINE / "experimental/ddr_adaptive_result_writer.v" if variant=="baseline" else PACKAGE / "rtl/ddr_adaptive_result_writer.v"
        text=source.read_text(encoding="utf-8-sig")
        text=text.replace("parameter WIDTH=640,HEIGHT=480","parameter WIDTH=1920,HEIGHT=1080",1)
        text=text.replace("input frame_valid,frame_tiled,output frame_ready","input frame_valid,output frame_ready",1)
        text=text.replace(");", ");\n    wire frame_tiled=1'b0;",1)
        text=re.sub(r'`include "[^"]*video_crc32.vh"', '`include "'+(work / "video_crc32.vh").as_posix()+'"',text)
        (work / "writer.v").write_text(text,encoding="utf-8")
        (work / "video_crc32.vh").write_bytes((BASELINE / "video_crc32.vh").read_bytes())
        script="""proc checked {command} {
    set rc [catch {uplevel 1 $command} result]
    if {$rc != 0} { puts stderr $result; exit 1 }
    puts $result
}
"""
        script+=f"cd {{{work.as_posix()}}}\n"
        script+=f"checked [list add_design {{{(work / 'writer.v').as_posix()}}}]\n"
        script+="checked [list set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676]\n"
        script+="checked [list compile -top_module ddr_adaptive_result_writer_capture_local]\n"
        script+="checked [list synthesize -ads -selected_syn_tool_opt 2]\nputs {WRITER_SYNTH_PROBE_COMPLETE}\n"
        tcl=work / "synth.tcl"
        tcl.write_text(script,encoding="utf-8")
        command=[str(args.pds_shell),"-file",str(tcl),"-work_dir",str(work),"-project_name","writer_probe"]
        result=subprocess.run(command,cwd=work,capture_output=True,text=True,errors="replace",timeout=600)
        log=result.stdout+result.stderr
        (work / "probe-console.log").write_text(log,encoding="utf-8")
        synth_log=work / "prj_tasks/syn_1/synthesize/run.log"
        if result.returncode or "WRITER_SYNTH_PROBE_COMPLETE" not in log or not synth_log.exists():
            raise RuntimeError(f"{variant} isolated synthesis failed; inspect {work}")
        synthesized=synth_log.read_text(encoding="utf-8",errors="replace")
        patterns={"LUT":r"Total LUTs:\s+([\d.]+)","FF":r"Total Registers:\s+([\d.]+)",
                  "DRM":r"Total DRMs\s*=\s*([\d.]+)","APM":r"Total APMs\s*=\s*([\d.]+)","IO":r"Total I/O ports\s*=\s*([\d.]+)"}
        metrics={key:float(re.search(pattern,synthesized).group(1)) for key,pattern in patterns.items()}
        report["variants"][variant]={"source":str(source.relative_to(ROOT)),"source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
            "derived_source_sha256":hashlib.sha256((work / "writer.v").read_bytes()).hexdigest(),"metrics":metrics,"command":command,
            "synthesis_log":str(synth_log),"synthesis_log_sha256":hashlib.sha256(synth_log.read_bytes()).hexdigest()}
        print(variant,metrics,flush=True)
    report["delta"]={key:report["variants"]["candidate"]["metrics"][key]-report["variants"]["baseline"]["metrics"][key] for key in patterns}
    report["passed"]=True
    (args.work / "writer-synthesis.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("delta",report["delta"])


if __name__=="__main__":
    main()
