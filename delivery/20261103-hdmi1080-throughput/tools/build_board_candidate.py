"""Hash-bound PDS 2025.2 board flow. Generates artifacts; never programs hardware.

prepare creates a fresh source closure and UART-only pin overlay. run executes
one stage at a time. Diagnostic bit generation requires explicit selection and
a complete fresh two-corner STA tied to the same routed database and 144 pads.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

import prepare_candidate as prep

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
TOP = "board1080_top"
KINDS = ("setup", "hold", "recovery", "removal", "mpw")
ARCH = {"family":"Logos2", "device":"PG2L100H", "speedgrade":"-6", "package":"FBG676"}
EXPECTED_CLOCKS = {"board27":37.037037,"input_pixel":13.315579,"pixel_clk":37.037037*4/11,
    "cfg_clk":99.9999999,"ref_clk":8.0,"rst_clk":8.0,"ddrphy_sysclk":8.0,
    "phy_dq_clk_0":1.0,"phy_dq_clk_1":1.0,"phy_dq_sysclk_0":8.0,"phy_dq_sysclk_1":8.0}
UART = """# Board UART-only pin overlay; no timing exceptions or clock changes.
# TX evidence: distortion/board/bringup.fdc:11-15.
# RX evidence: distortion/board/corrected_gamma_d5.fdc:827-833.
# CP2102 FPGA UART RX=B24, TX=C24. Top names follow the sealed HDMI design.
define_attribute {p:telemetry_rx} {PAP_IO_DIRECTION} {INPUT}
define_attribute {p:telemetry_rx} {PAP_IO_LOC} {B24}
define_attribute {p:telemetry_rx} {PAP_IO_VCCIO} {3.3}
define_attribute {p:telemetry_rx} {PAP_IO_STANDARD} {LVCMOS33}
define_attribute {p:telemetry_rx} {PAP_IO_NONE} {TRUE}
define_attribute {p:telemetry_rx} {PAP_IO_PULLUP} {TRUE}
define_attribute {p:telemetry_tx} {PAP_IO_DIRECTION} {OUTPUT}
define_attribute {p:telemetry_tx} {PAP_IO_LOC} {C24}
define_attribute {p:telemetry_tx} {PAP_IO_VCCIO} {3.3}
define_attribute {p:telemetry_tx} {PAP_IO_STANDARD} {LVCMOS33}
define_attribute {p:telemetry_tx} {PAP_IO_DRIVE} {4}
define_attribute {p:telemetry_tx} {PAP_IO_SLEW} {SLOW}
"""


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")


def ref(path):
    path=Path(path).resolve()
    return {"path":str(path), "sha256":sha(path)}


def check_ref(item):
    require(Path(item["path"]).is_file() and sha(item["path"])==item["sha256"], "Artifact changed: "+item["path"])


def tcl(path):
    value=Path(path).resolve().as_posix()
    require(not any(c in value for c in '{}\r\n"'), "Unsupported Tcl path")
    return "{"+value+"}"


def fdc_pins(text):
    pins={}
    for port,key,value in re.findall(r"(?m)^\s*define_attribute\s+\{p:([^{}]+)\}\s+\{PAP_IO_(\w+)\}\s+\{([^{}]+)\}\s*$",text):
        row=pins.setdefault(port,{})
        require(key not in row, "Duplicate pin attribute: "+port+":"+key)
        row[key]=value
    return pins


def top_ports(text):
    text=re.sub(r"/\*.*?\*/|//[^\n]*|\(\*.*?\*\)","",text,flags=re.S)
    match=re.search(r"module\s+board1080_top\s*(?:#\(.*?\)\s*)?\((.*?)\)\s*;",text,re.S)
    require(match is not None,"Cannot parse frozen top interface")
    ports={};direction=None;bounds=None
    for piece in match[1].split(","):
        found=re.fullmatch(r"\s*(?:(input|output|inout)\s+)?(?:wire\s+|reg\s+)?(?:\[(\d+):(\d+)\]\s*)?(\w+)\s*",piece)
        require(found is not None,"Unrecognized port declaration")
        typ,hi,lo,name=found.groups()
        if typ: direction=typ.upper();bounds=None
        if hi is not None: bounds=(int(lo),int(hi))
        require(direction is not None,"Missing port direction")
        for port in ([name] if bounds is None else [f"{name}[{i}]" for i in range(bounds[0],bounds[1]+1)]):
            require(port not in ports,"Duplicate top port")
            ports[port]=direction
    return ports


def source_pin_audit(work, plan):
    native=work/"native"
    recipe=read_json(prep.BASE/"manifests/build-recipe.json")
    original="\n".join((native/p).read_text(encoding="utf-8-sig") for p in recipe["constraints"])
    overlay=(work/"uart-pins.fdc").read_text(encoding="utf-8")
    require(overlay==UART,"UART overlay drift")
    pins=fdc_pins(original+"\n"+overlay)
    ports=top_ports((native/prep.TOP).read_text(encoding="utf-8-sig"))
    require(len(pins)==len(ports)==144 and set(pins)==set(ports),"Exact 144 top/FDC port contract required")
    require(len({p["LOC"] for p in pins.values()})==144,"Package pin conflict")
    for port,row in pins.items():
        require(row.get("DIRECTION")==ports[port] and set(("LOC","VCCIO","STANDARD"))<=set(row),"Incomplete pin contract: "+port)
    require(pins["telemetry_rx"]["LOC"]=="B24" and pins["telemetry_tx"]["LOC"]=="C24","UART mapping differs")
    return pins


def verify_inputs(work, allow_runner_drift=False):
    plan=read_json(work/"board-flow.json")
    check_ref(plan["preparation"])
    check_ref(plan["recipe"])
    check_ref(plan["uart_overlay"])
    if not allow_runner_drift: check_ref(plan["runner"])
    preparation=read_json(work/"preparation.json")
    require(preparation["work_directory"]==str(work),"Prepared tree was moved; regenerate absolute bindings")
    for row in preparation["files"]:
        require(sha(work/"native"/row["path"])==row["compile_sha256"],"Compiled source drift: "+row["path"])
    require(source_pin_audit(work,plan)==plan["expected_pins"],"Source pin inventory changed")
    return plan


def prepare(args):
    result=prep.prepare(args.dependency_native,args.run_name,args.variant,args.mode,args.output_root)
    work=Path(result["work_directory"]).resolve()
    (work/"uart-pins.fdc").write_text(UART,encoding="utf-8")
    plan={"schema":"hdmi1080-board-flow-v1", "prepared_utc":datetime.now(timezone.utc).isoformat(),
        "preparation":ref(work/"preparation.json"),"recipe":ref(prep.BASE/"manifests/build-recipe.json"),
        "uart_overlay":ref(work/"uart-pins.fdc"),"runner":ref(__file__),"architecture":ARCH,
        "pds_generation":"2025.2", "variant":args.variant,"mode":args.mode,"param_id_hex":result["param_id_hex"],
        "source_constraint_profile":"sealed diagnostic FDC, unchanged; UART physical attributes only added",
        "external_io_timing_accepted":False,"cdc_protocol_and_reset_signoff":False,"hardware_accessed":False,
        "uart_pin_evidence":[{"file":"distortion/board/bringup.fdc","lines":"11-15","binding":"telemetry_tx=C24 3.3V LVCMOS33 4mA SLOW"},
                             {"file":"distortion/board/corrected_gamma_d5.fdc","lines":"827-833","binding":"telemetry_rx=B24 3.3V LVCMOS33 pullup"}]}
    plan["expected_pins"]=source_pin_audit(work,plan)
    save(work/"board-flow.json",plan)
    return {"prepared":True,"work":str(work),"pins":144,"param_id_hex":result["param_id_hex"],"hardware_accessed":False}


def unique(directory, pattern, required_segment=None):
    matches=[p for p in directory.rglob(pattern) if "bak" not in p.parts and "logbackup" not in p.parts
             and (required_segment is None or required_segment in p.parts)]
    require(len(matches)==1,f"Expected one {pattern} under {directory}, found {len(matches)}")
    return matches[0]


def verify_device(directory):
    project=directory/(TOP+".pds")
    parts=[element.attrib for element in ET.parse(project).findall(".//part")]
    require(parts and all(all(p.get(k)==v for k,v in ARCH.items()) for p in parts),"Native project device/package differs")
    return ref(project)


def constraint_refs(work, stage):
    recipe=read_json(prep.BASE/"manifests/build-recipe.json")
    paths=[work/"native"/p for p in recipe["constraints"]]+[work/"uart-pins.fdc"]
    if stage!="map": paths.append(Path(receipt(work,"map")["artifacts"]["pcf"]["path"]))
    return [ref(path) for path in paths]


def verify_constraint_import(directory, expected):
    items=ET.parse(directory/(TOP+".pds")).findall(".//item")
    imported={(directory/item.attrib["file"]).resolve() for item in items
              if item.attrib.get("format") in ("fdc","pcf") and "file" in item.attrib}
    require(imported=={Path(item["path"]).resolve() for item in expected},"Native project constraint import differs")
    for item in expected: check_ref(item)
    return {"passed":True,"constraints":expected}


def native_pin_audit(pcf, prt, expected, mapped_only=False):
    generated={}
    for line in pcf.read_text(encoding="utf-8-sig").splitlines():
        match=re.fullmatch(r"def_port \{([^{}]+)\} (.+)",line)
        if not match: continue
        require(match[1] not in generated,"Duplicate native PCF port")
        generated[match[1]]=dict(re.findall(r"(\w+)=([^\s]+)",match[2]))
    require(set(generated)==set(expected),"Native PCF does not preserve all 144 declared pins")
    for port,wanted in expected.items():
        for key in ("LOC","VCCIO","STANDARD"):
            native_key="IOSTANDARD" if key=="STANDARD" else key
            require(generated[port].get(native_key)==wanted[key],"PCF electrical/location mismatch: "+port+":"+key)
        for key in ("DRIVE","SLEW"):
            if key in wanted:
                require(generated[port].get(key)==wanted[key],"PCF electrical/location mismatch: "+port+":"+key)
        if wanted.get("PULLUP")=="TRUE":
            require(generated[port].get("BUS_KEEPER")=="PULLUP","PCF pullup mismatch: "+port)
    routed={};banks=defaultdict(set);reserved={}
    by_pad={v["LOC"]:k for k,v in expected.items()}
    for line in prt.read_text(encoding="utf-8-sig").splitlines():
        fields=line.split("|")
        if len(fields)!=7: continue
        pad,site,bank,function,port,direction,assigned=fields
        if assigned=="YES":
            require(pad not in reserved,"Duplicate reserved package pad")
            reserved[pad]={"bank":bank,"port":port,"direction":direction}
            require(pad in by_pad,"Native map reserves unexpected package pad: "+pad)
            banks[bank].add(expected[by_pad[pad]]["VCCIO"])
        if not port: continue
        require(port in expected and port not in routed,"Unexpected or duplicate routed port: "+port)
        require(expected[port]["LOC"]==pad and expected[port]["DIRECTION"].lower()==direction and assigned=="YES","Routed pin assignment mismatch: "+port)
        routed[port]={"pad":pad,"bank":bank,"direction":direction}
    require(set(reserved)==set(by_pad),"Reserved package pads differ from 144 declared pins")
    if not mapped_only: require(set(routed)==set(expected),"Routed 144-pin inventory incomplete")
    require(all(len(v)==1 for v in banks.values()),"A physical bank contains inconsistent declared supply voltages")
    return {"passed":True,"pin_count":144,"pcf":ref(pcf),"pin_report":ref(prt),
            "bank_declared_vccio":{k:next(iter(v)) for k,v in sorted(banks.items())},"pins":routed,
            "physical_supply_voltage_measured":False,"routed_port_assignment_verified":not mapped_only,
            "reserved_pads":reserved,"phase":"map-reservation" if mapped_only else "routed-assignment"}


def routed_electrical_audit(pcf, report, expected):
    """Compare every Map PCF port attribute against final native IO Port Info."""
    generated={}
    for line in pcf.read_text(encoding="utf-8-sig").splitlines():
        match=re.fullmatch(r"def_port \{([^{}]+)\} (.+)",line)
        if match: generated[match[1]]=dict(re.findall(r"(\w+)=([^\s]+)",match[2]))
    columns=None;actual={}
    for line in report.read_text(encoding="utf-8-sig",errors="replace").splitlines():
        cells=[cell.strip() for cell in line.split("|")][1:]
        if cells and cells[-1]=="": cells.pop()
        if cells and cells[0]=="PORT" and "IOSTANDARD" in cells: columns=cells;continue
        if columns and cells and cells[0] in expected:
            require(cells[0] not in actual and len(cells)==len(columns),"Duplicate/malformed routed IO row")
            actual[cells[0]]=dict(zip(columns,cells))
    require(set(actual)==set(generated)==set(expected),"Final IO electrical report requires all 144 ports")
    for port,attrs in generated.items():
        require(actual[port]["DIRECTION"]==expected[port]["DIRECTION"].lower() and actual[port]["CONSTRAINT"]=="YES",
                "Unconstrained or incorrect IO direction: "+port)
        for key,value in attrs.items():
            require(actual[port].get(key)==value,"Routed electrical mismatch: "+port+":"+key)
    return {"passed":True,"all_map_pcf_port_attributes_verified":True,"ports":actual,"report":ref(report)}


def parse_clocks(text):
    clocks={};active=False
    for line in text.splitlines():
        if line.strip()=="Clock Summary:": active=True;continue
        if active and line.strip()=="Clock Groups:": break
        if not active: continue
        match=re.match(r"^\s*(\S+)\s+(\d+\.\d+)\s+\{([^}]+)\}\s+(Declared|Generated)(.*)$",line)
        if match:
            name,period,waveform,kind,tail=match.groups()
            require(name not in clocks,"Duplicate clock summary name")
            clocks[name]={"period_ns":float(period),"waveform":waveform,"type":kind,"detail":tail.strip()}
    require(set(clocks)==set(EXPECTED_CLOCKS),"Expected all eleven frozen clocks; unexpected/missing clock names")
    for name,period in EXPECTED_CLOCKS.items():
        require(abs(clocks[name]["period_ns"]-period)<=0.0011,"Frozen clock period mismatch: "+name)
        require(clocks[name]["type"]==("Declared" if name in ("board27","input_pixel","ref_clk") else "Generated"),
                "Frozen clock type mismatch: "+name)
    return clocks


def parse_timing(path):
    text=path.read_text(encoding="utf-8-sig",errors="replace")
    for key,value in (("Device","PG2L100H"),("Speed Grade","-6"),("Package","FBG676"),("Design",TOP)):
        require(re.search(r"(?m)^\| "+re.escape(key)+r"\s*:\s*"+re.escape(value)+r"\s*$",text),"STA device/header mismatch: "+key)
    require("Timing analysis mode : multi corner" in text,"Multi-corner STA required")
    num=r"[-+]?\d+(?:\.\d+)?"
    header=re.compile(r"^(Setup|Hold|Recovery|Removal|Minimum Pulse Width) Summary\((Slow|Fast) Corner\):\s*$")
    rows=re.compile(r"^\s*(\S+)\s+(\S+)\s+("+num+r")\s+("+num+r")\s+(\d+)\s+(\d+)\s*$")
    pulse=re.compile(r"^\s*(\S+)\s+("+num+r")\s+("+num+r")\s+(\d+)\s+(\d+)\s*$")
    tables={};current=None;clock_lines=[];in_clocks=False
    for line in text.splitlines():
        if line.startswith("Startpoint"): break
        if line.strip()=="Clock Summary:": in_clocks=True;continue
        if in_clocks:
            if line.strip()=="Clock Groups:": in_clocks=False
            elif line.strip() and not set(line.strip())<=set("-=*"): clock_lines.append(line)
        match=header.fullmatch(line)
        if match:
            kind="mpw" if match[1]=="Minimum Pulse Width" else match[1].lower()
            current=match[2].lower()+"_"+kind
            require(current not in tables,"Duplicate timing summary")
            tables[current]=[];continue
        if current is None: continue
        match=(pulse if current.endswith("mpw") else rows).fullmatch(line)
        if match:
            values=match.groups();count=1 if current.endswith("mpw") else 2
            wns,tns,failing,total=values[count:]
            require(math.isfinite(float(wns)) and math.isfinite(float(tns)),"Non-finite timing data")
            require(0<=int(failing)<=int(total),"Invalid timing endpoint counts")
            tables[current].append({"clocks":list(values[:count]),"worst_slack_ns":float(wns),
                                    "total_negative_slack_ns":float(tns),"failing_checks":int(failing),"total_checks":int(total)})
    expected={c+"_"+k for c in ("slow","fast") for k in KINDS}
    require(set(tables)==expected and all(tables.values()) and clock_lines,"All ten nonempty timing summaries and clocks are required")
    require(all(sum(row["total_checks"] for row in rows)>0 for rows in tables.values()),"Every timing summary requires positive endpoint coverage")
    summaries={key:{"worst_slack_ns":min(r["worst_slack_ns"] for r in value),
                    "failing_checks":sum(r["failing_checks"] for r in value)} for key,value in tables.items()}
    passed=all(r["worst_slack_ns"]>=0 and r["failing_checks"]==0 for r in summaries.values())
    return {"complete_two_corner_report":True,"all_native_checks_met":passed,"summaries":summaries,"verified_clocks":parse_clocks(text),
            "all_rows":tables,"clock_summary_lines":clock_lines,"timing_report":ref(path)}


def prefix(work):
    return ["proc checked {command} {", "  set rc [catch {uplevel 1 $command} result]",
            "  if {$rc != 0} { puts stderr $result; exit 1 }", "  puts $result", "}",
            "cd "+tcl(work),"checked [list set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676]"]


def stage_tcl(work, stage, directory, input_db=None, seed=1):
    lines=prefix(directory)
    recipe=read_json(prep.BASE/"manifests/build-recipe.json")
    constraints=[work/"native"/p for p in recipe["constraints"]]+[work/"uart-pins.fdc"]
    if stage=="map":
        recipe=read_json(prep.BASE/"manifests/build-recipe.json")
        lines += ["checked [list add_design "+tcl(work/"native"/p)+"]" for p in recipe["designs"]]
        lines += ["checked [list add_constraint "+tcl(work/"native"/p)+"]" for p in recipe["constraints"]]
        lines += ["checked [list add_constraint "+tcl(work/"uart-pins.fdc")+"]",
            "checked [list compile -top_module board1080_top -include_path "+tcl(work/"native/b4/rtl")+"]",
            "checked [list synthesize -ads -selected_syn_tool_opt 2]","checked [list dev_map]"]
    else:
        dummy=directory/"dummy.v";dummy.write_text("module board1080_top(); endmodule\n",encoding="ascii")
        lines += ["checked [list add_design "+tcl(dummy)+"]"]
        lines += ["checked [list add_constraint "+tcl(p)+"]" for p in constraints]
        mapped=receipt(work,"map")
        pcf=Path(mapped["artifacts"]["pcf"]["path"])
        lines += ["checked [list add_constraint "+tcl(pcf)+" -pnr_set pnr_1]",
                  "puts {EXPLICIT_FROZEN_FDC_UART_OVERLAY_AND_MAP_PCF_LOADED}"]
        if stage=="route":
            # ADF alone does not retain the external physical/timing files.
            # PDS 2025.2's aggregate pnr action retains input_db_file in the
            # wrapper options but does not forward it to Place. Use the native
            # action sequence documented in Tcl Command Guide section 2.2.4.
            lines += ["checked [list place -force_to_run -input_db_file "+tcl(input_db)+f" -gplace_seed {seed}]",
                      "checked [list route -force_to_run]",
                      "checked [list route_optimize -force_to_run -fix_hold_violation_in_route TRUE]",
                      "checked [list report_timing -force_to_run -input_db_file "+tcl(directory/"prj_tasks/pnr_1/place_route"/(TOP+"_pnr.adf"))+
                      " -delay_type min_max -max_path 1 -nworst 1]"]
        elif stage=="sta":
            lines += ["checked [list report_timing -force_to_run -input_db_file "+tcl(input_db)+
                      " -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE -report_io_datasheet]"]
        elif stage=="bitstream":
            lines += ["checked [list gen_bit_stream -force_to_run -input_db_file "+tcl(input_db)+
                      " -scbv {High Voltage} -unused_io_status UNUSED]"]
    lines += ["puts {BOARD_"+stage.upper()+"_STAGE_COMPLETE}"]
    return "\n".join(lines)+"\n"


def receipt(work, stage):
    result=read_json(work/(stage+"-result.json"))
    require(result.get("stage_completed") is True,"Previous stage is incomplete: "+stage)
    for item in result.get("artifacts",{}).values(): check_ref(item)
    check_ref(result["board_flow"])
    require(result["board_flow"]==ref(work/"board-flow.json"),"Stage belongs to another preparation")
    return result


def run(args):
    work=args.work.resolve();plan=verify_inputs(work)
    stage=args.stage
    require(1<=args.attempt<=99,"Attempt must be in [1,99]")
    directory=work/"stages"/(stage if args.attempt==1 else stage+f"-{args.attempt:02d}")
    require(not directory.exists(),"Stage directory exists; preserve it and prepare a new run for a retry")
    require(args.pds_shell.is_file(),"PDS executable missing")
    require(1<=args.seed<=99999 and 1<=args.timeout_seconds<=43200,"Invalid seed/time limit")
    require(not args.diagnostic_bit or stage=="bitstream","--diagnostic-bit applies only to bitstream stage")
    prior=None;input_db=None;timing=None
    if stage=="route":
        prior=receipt(work,"map");input_db=Path(prior["artifacts"]["map_db"]["path"])
    elif stage=="sta":
        prior=receipt(work,"route");input_db=Path(prior["artifacts"]["route_db"]["path"])
    elif stage=="bitstream":
        prior=receipt(work,"sta");routed=receipt(work,"route");mapped=receipt(work,"map")
        input_db=Path(routed["artifacts"]["route_db"]["path"])
        require(prior["input_db"]==ref(input_db),"STA does not bind current routed DB")
        require(prior["timing"]["complete_two_corner_report"] and routed["pins"]["passed"] and mapped["pins"]["passed"],"Complete fresh STA and native pin checks required")
        require(routed["electrical"]["passed"] and routed["constraint_import"]["passed"] and prior["constraint_import"]["passed"],
                "Verified final IO electrical attributes and explicit stage constraints required")
        require(set(prior["timing"]["verified_clocks"])==set(EXPECTED_CLOCKS),"STA expected-clock contract absent")
        timing=prior["timing"]
        if not args.diagnostic_bit:
            require(timing["all_native_checks_met"],"Native timing has violations; no normal bitstream export")
            require(plan["external_io_timing_accepted"] and plan["cdc_protocol_and_reset_signoff"],
                    "Frozen constraints retain diagnostic IO/CDC limits; explicit --diagnostic-bit preserves that status")
    previous_attempt=None
    result_path=work/(stage+"-result.json")
    if result_path.exists():
        old_result=read_json(result_path)
        require(old_result.get("stage_completed") is False,"Successful native stages are immutable; prepare a new run")
        archive=work/"provenance"/(stage+"-attempt-"+sha(result_path)+".json")
        archive.parent.mkdir(exist_ok=True)
        if not archive.exists(): shutil.copyfile(result_path,archive)
        require(sha(archive)==sha(result_path),"Previous attempt archive differs")
        previous_attempt=ref(archive)
    directory.mkdir(parents=True,exist_ok=False)
    source_ref=ref(input_db) if input_db is not None else None
    script=directory/(stage+".tcl")
    script.write_text(stage_tcl(work,stage,directory,input_db,args.seed),encoding="utf-8")
    result={"schema":"hdmi1080-board-stage-v1","stage":stage,"stage_completed":False,
        "stage_directory":str(directory),"attempt":args.attempt,"previous_attempt":previous_attempt,
        "started_utc":datetime.now(timezone.utc).isoformat(),"board_flow":ref(work/"board-flow.json"),
        "input_db":source_ref,"script":ref(script),"pds_executable":ref(args.pds_shell),
        "hardware_accessed":False,"physical_timing_accepted":False,"hardware_release_allowed":False,
        "diagnostic_bit_requested":bool(args.diagnostic_bit),"artifacts":{}}
    result["explicit_constraints"]=constraint_refs(work,stage)
    command=[str(args.pds_shell.resolve()),"-file",str(script),"-work_dir",str(directory),"-project_name",TOP]
    result["command"]=command
    log=directory/"console.log";started=time.monotonic()
    try:
        with log.open("w",encoding="utf-8") as stream:
            process=subprocess.run(command,cwd=directory,stdout=stream,stderr=subprocess.STDOUT,timeout=args.timeout_seconds)
        result["returncode"]=process.returncode
        text=log.read_text(encoding="utf-8",errors="replace")
        require(process.returncode==0 and "BOARD_"+stage.upper()+"_STAGE_COMPLETE" in text,"PDS stage failed; inspect "+str(log))
        result["device_project"]=verify_device(directory)
        if stage!="map": result["constraint_import"]=verify_constraint_import(directory,result["explicit_constraints"])
        verify_inputs(work)
        if source_ref: check_ref(source_ref)
        if stage=="map":
            database=unique(directory,"*.adf","device_map")
            pcf=unique(directory,TOP+".pcf","device_map")
            prt=unique(directory,TOP+"_dmr.prt","device_map")
            result["pins"]=native_pin_audit(pcf,prt,plan["expected_pins"],mapped_only=True)
            result["artifacts"]={"map_db":ref(database),"pcf":ref(pcf),"pin_report":ref(prt)}
        elif stage=="route":
            database=unique(directory,TOP+"_pnr.adf","place_route")
            prt=unique(directory,TOP+"_prr_route_optimize.prt","place_route")
            pcf=Path(prior["artifacts"]["pcf"]["path"])
            result["pins"]=native_pin_audit(pcf,prt,plan["expected_pins"])
            io=unique(directory,TOP+".rur","place_route")
            clocks=unique(directory,TOP+".rtr","report_timing")
            result["electrical"]=routed_electrical_audit(pcf,io,plan["expected_pins"])
            result["verified_clocks"]=parse_clocks(clocks.read_text(encoding="utf-8-sig",errors="replace"))
            result["artifacts"]={"route_db":ref(database),"pin_report":ref(prt),"pcf":ref(pcf),"electrical_report":ref(io),"clock_report":ref(clocks)}
        elif stage=="sta":
            report=unique(directory,TOP+".rtr","report_timing")
            exceptions=unique(directory,TOP+"_exception.rtr","report_timing")
            result["timing"]=parse_timing(report)
            result["artifacts"]={"timing":ref(report),"exceptions":ref(exceptions)}
        else:
            bit=unique(directory,TOP+".sbit","generate_bitstream")
            result["label"]="DIAGNOSTIC_NOT_TIMING_SIGNOFF" if args.diagnostic_bit else "TIMING_AND_REVIEW_GATES_MET"
            target=work/"export"/(plan["variant"]+"_"+plan["mode"]+"_"+plan["param_id_hex"]+"_"+result["label"]+".sbit")
            target.parent.mkdir(exist_ok=True)
            require(not target.exists(),"Export target already exists")
            shutil.copyfile(bit,target)
            result["timing"]=timing
            result["artifacts"]={"native_bitstream":ref(bit),"exported_bitstream":ref(target)}
        result["stage_completed"]=True
    except Exception as exc:
        result["error"]=type(exc).__name__+": "+str(exc)
        raise
    finally:
        result["elapsed_seconds"]=round(time.monotonic()-started,3)
        if log.exists(): result["log"]=ref(log)
        save(work/(stage+"-result.json"),result)
    return {"stage":stage,"completed":True,"result":str(work/(stage+"-result.json")),
            "all_native_checks_met":result.get("timing",{}).get("all_native_checks_met"),
            "label":result.get("label"),"hardware_accessed":False}


def migrate_runner(args):
    """Preserve execution provenance while upgrading only the CPU controller."""
    work=args.work.resolve();plan=verify_inputs(work,allow_runner_drift=True)
    previous=args.previous_runner.resolve()
    require(sha(previous)==plan["runner"]["sha256"],"Previous runner snapshot must match bound execution version")
    require(sha(__file__)!=plan["runner"]["sha256"],"Runner migration is unnecessary")
    old_plan=ref(work/"board-flow.json")
    results=[]
    for path in work.glob("*-result.json"):
        result=read_json(path)
        require(result["board_flow"]==old_plan,"Stage receipt has unrelated board-flow identity")
        for key in ("script","log","device_project"):
            if key in result: check_ref(result[key])
        for item in result.get("artifacts",{}).values(): check_ref(item)
        results.append((path,result))
    directory=work/"provenance"/("runner-migration-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    directory.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(previous,directory/"previous-runner.py")
    shutil.copyfile(work/"board-flow.json",directory/"previous-board-flow.json")
    migration={"recorded_utc":datetime.now(timezone.utc).isoformat(),"previous_runner":ref(directory/"previous-runner.py"),
               "new_runner":ref(__file__),"previous_board_flow":ref(directory/"previous-board-flow.json"),
               "source_or_constraint_changes":False,"eda_reexecuted":False,"prior_receipts":{}}
    for path,_ in results:
        shutil.copyfile(path,directory/path.name)
        migration["prior_receipts"][path.name]=ref(directory/path.name)
    save(directory/"migration.json",migration)
    plan.setdefault("runner_migrations",[]).append(ref(directory/"migration.json"))
    plan["runner"]=ref(__file__)
    save(work/"board-flow.json",plan)
    for path,result in results:
        result.setdefault("execution_runner",migration["previous_runner"])
        result.setdefault("previous_receipts",[]).append(migration["prior_receipts"][path.name])
        result["board_flow"]=ref(work/"board-flow.json")
        result["audit_runner"]=ref(__file__)
        save(path,result)
    verify_inputs(work)
    return {"runner_migrated":True,"source_or_constraint_changes":False,"eda_reexecuted":False,"record":str(directory/"migration.json")}


def audit_existing(args):
    """Reinspect a successful native stage after a CPU format-adapter failure."""
    work=args.work.resolve();plan=verify_inputs(work);stage=args.stage
    path=work/(stage+"-result.json");result=read_json(path)
    directory=Path(result.get("stage_directory",work/"stages"/stage)).resolve()
    require(directory.is_relative_to(work/"stages"),"Stage directory escaped preparation")
    require(result.get("returncode")==0 and not result.get("stage_completed"),"Audit recovery requires a successful native run and failed CPU receipt")
    require(result["board_flow"]==ref(work/"board-flow.json"),"Existing stage belongs to another source plan")
    for key in ("script","log","device_project"):
        if key in result: check_ref(result[key])
    if result.get("input_db"): check_ref(result["input_db"])
    log=Path(result["log"]["path"]).read_text(encoding="utf-8",errors="replace")
    require("BOARD_"+stage.upper()+"_STAGE_COMPLETE" in log,"Native stage completion marker absent")
    verify_device(directory)
    if stage!="map":
        require("explicit_constraints" in result,"Legacy stage omitted explicit constraints; preserve and rerun")
        result["constraint_import"]=verify_constraint_import(directory,result["explicit_constraints"])
    if stage=="map":
        database=unique(directory,"*.adf","device_map");pcf=unique(directory,TOP+".pcf","device_map")
        prt=unique(directory,TOP+"_dmr.prt","device_map")
        result["pins"]=native_pin_audit(pcf,prt,plan["expected_pins"],mapped_only=True)
        result["artifacts"]={"map_db":ref(database),"pcf":ref(pcf),"pin_report":ref(prt)}
    elif stage=="route":
        mapped=receipt(work,"map");database=unique(directory,TOP+"_pnr.adf","place_route")
        pcf=Path(mapped["artifacts"]["pcf"]["path"]);prt=unique(directory,TOP+"_prr_route_optimize.prt","place_route")
        result["pins"]=native_pin_audit(pcf,prt,plan["expected_pins"])
        io=unique(directory,TOP+".rur","place_route");clocks=unique(directory,TOP+".rtr","report_timing")
        result["electrical"]=routed_electrical_audit(pcf,io,plan["expected_pins"])
        result["verified_clocks"]=parse_clocks(clocks.read_text(encoding="utf-8-sig",errors="replace"))
        result["artifacts"]={"route_db":ref(database),"pin_report":ref(prt),"pcf":ref(pcf),"electrical_report":ref(io),"clock_report":ref(clocks)}
    else:
        report=unique(directory,TOP+".rtr","report_timing");exceptions=unique(directory,TOP+"_exception.rtr","report_timing")
        result["timing"]=parse_timing(report)
        result["artifacts"]={"timing":ref(report),"exceptions":ref(exceptions)}
    result.setdefault("recovered_errors",[]).append(result.pop("error",None))
    result.update(stage_completed=True,cpu_reaudit_utc=datetime.now(timezone.utc).isoformat(),audit_runner=ref(__file__),eda_reexecuted=False)
    save(path,result)
    return {"stage":stage,"completed":True,"cpu_reaudit_only":True,"eda_reexecuted":False,"receipt":str(path)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest="command",required=True)
    command=commands.add_parser("prepare")
    command.add_argument("--dependency-native",type=Path,required=True)
    command.add_argument("--run-name",required=True)
    command.add_argument("--output-root",type=Path,required=True)
    command.add_argument("--variant",choices=("baseline","writer","cache","both"),default="cache")
    command.add_argument("--mode",choices=tuple(prep.MODES),default="corrected")
    command=commands.add_parser("run")
    command.add_argument("--work",type=Path,required=True)
    command.add_argument("--stage",choices=("map","route","sta","bitstream"),required=True)
    command.add_argument("--pds-shell",type=Path,required=True)
    command.add_argument("--seed",type=int,default=1)
    command.add_argument("--timeout-seconds",type=int,default=10800)
    command.add_argument("--diagnostic-bit",action="store_true")
    command.add_argument("--attempt",type=int,default=1,help="Fresh numbered directory for retrying a failed stage; previous attempts are retained")
    command=commands.add_parser("migrate-runner")
    command.add_argument("--work",type=Path,required=True)
    command.add_argument("--previous-runner",type=Path,required=True)
    command=commands.add_parser("audit-existing")
    command.add_argument("--work",type=Path,required=True)
    command.add_argument("--stage",choices=("map","route","sta"),required=True)
    args=parser.parse_args()
    result={"prepare":prepare,"run":run,"migrate-runner":migrate_runner,"audit-existing":audit_existing}[args.command](args)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
