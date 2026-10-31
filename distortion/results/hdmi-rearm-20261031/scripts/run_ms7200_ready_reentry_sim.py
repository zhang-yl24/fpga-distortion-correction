"""A/B complete-poll readiness re-entry against the frozen ready controller.

No EDA, source mutation, I2C hardware or board programming is performed.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import csv
import hashlib
import json
import re
import time

from simulation_tools import resolve_vivado_bin
from run_gamma_pipeline_d5_sim import tool
from run_ms7200_ready_level_sim import command_rows

ROOT=Path(__file__).resolve().parents[1]
OLD="rtl/experimental/ms7200_1080p30_ready_ctl.v"
NEW="rtl/experimental/ms7200_1080p30_rearm_ctl.v"
TB="tests/tb_ms7200_ready_reentry.sv"
OLD_SHA256="6918a4a46135094addc443c45235077887b1daaca81f4f255163f635c7828959"
NEW_SHA256="ea87e1e8c3588af0675c97f87408ddb115d8b0fb08fb84a93c3e820c5a3dee2e"
HEADER=("// Isolated readiness-entry rearm candidate; requires independent native audit.\n"
        "// Only first-ready or transition into ready=02 admits the fixed seven writes.\n"
        "// This digital change does not identify the physical HDMI/PCLK failure cause.\n")
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_source():
    before=(ROOT/OLD).read_text(encoding="utf-8")
    after=(ROOT/NEW).read_text(encoding="utf-8")
    if sha(ROOT/OLD)!=OLD_SHA256 or sha(ROOT/NEW)!=NEW_SHA256:
        raise ValueError("frozen source identity changed")
    expected=HEADER+before.replace("module ms7200_1080p30_ready_ctl(",
                                  "module ms7200_1080p30_rearm_ctl(",1).replace(
                                  "(!status_sample_seen || previous_ready==2'b00);",
                                  "(!status_sample_seen || previous_ready!=2'b10);",1)
    if after!=expected:
        raise ValueError("candidate changed logic outside the explicit re-entry condition")
    rows=command_rows(before)
    if command_rows(after)!=rows:
        raise ValueError("311 ordered commands changed")
    return rows


def audit_trace(path,commands,rearm):
    with path.open(encoding="ascii",newline="") as stream:
        rows=list(csv.DictReader(stream))
    if not rows:
        raise ValueError("transaction trace is empty")
    expected_counts={0:7,1:0,2:14 if rearm else 7,3:14 if rearm else 7,
                     4:14,5:7 if rearm else 0,6:7 if rearm else 0,7:7,8:7,9:0}
    counts={case:0 for case in range(10)}
    settings=commands[304:311]
    for row in rows:
        case=int(row["scenario"])
        if case not in counts or int(row["rearm"])!=rearm:
            raise ValueError("trace scenario identity differs")
        if int(row["write"]) and int(row["state"],16)==0x20:
            value=row["address"]+row["value"]
            if value.lower()!=settings[counts[case]%7].lower():
                raise ValueError("trace setting command order/value differs")
            counts[case]+=1
    if counts!=expected_counts:
        raise ValueError("independent trace admission count differs: "+repr(counts))
    return dict(Requests=len(rows),SettingWritesByCase=counts,
                SevenFixedSettingWritesUnchanged=True,TraceSHA256=sha(path))


def run(workdir,maximum_seconds=180):
    work=Path(workdir).resolve()
    if work.exists() and (not work.is_dir() or any(work.iterdir())):
        raise ValueError("new or empty simulation work directory required")
    commands=audit_source()
    work.mkdir(parents=True,exist_ok=True)
    names=(OLD,NEW,TB,"tools/run_ms7200_ready_reentry_sim.py",
           "tools/run_ms7200_ready_level_sim.py","tools/simulation_tools.py",
           "tools/run_gamma_pipeline_d5_sim.py")
    inputs={name:sha(ROOT/name) for name in names}
    (work/"rx_expected.hex").write_text("\n".join(commands)+"\n",encoding="ascii")
    vector=sha(work/"rx_expected.hex")
    result=dict(Schema="ms7200-ready-reentry-ab-simulation-v1",Passed=False,
                StartedUTC=datetime.now(timezone.utc).isoformat(),SourceSHA256=inputs,
                All311CommandsUnchanged=True,ReadySourceSHA256=OLD_SHA256,
                RearmSourceSHA256=NEW_SHA256,OnlyAdmissionConditionChanged=True,
                HardwareAccessed=False,PDSAccessed=False,TransactionDriverStub=True,
                WireLevelI2CExecuted=False,Commands=[],
                Limits="Synthetic successful-transaction responses, not a wire slave or real HDMI receiver. Incomplete byte completion is covered; NACK handling belongs to the unchanged checked driver/wrapper and is not simulated here. This proves re-entry admission behavior, not the physical PCLK or VS failure cause.")
    started=time.monotonic()
    try:
        bin_dir=resolve_vivado_bin(ROOT.parent)
        for executable,args,stage in (
            ("xvlog.bat",["--sv",str(ROOT/OLD),str(ROOT/NEW),str(ROOT/TB)],"compile"),
            ("xelab.bat",["tb_ms7200_ready_reentry","-s","ready_reentry_ab_tb"],"elaborate"),
            ("xsim.bat",["ready_reentry_ab_tb","-runall","-log","simulation.log"],"simulate"),
        ):
            record=dict(Stage=stage,Argv=[str(bin_dir/executable),*args],ReturnCode=None)
            result["Commands"].append(record)
            tool(bin_dir,executable,args,work,started+maximum_seconds,stage)
            record["ReturnCode"]=0
        log=(work/"simulation.log").read_text(encoding="utf-8",errors="replace")
        if "MS7200_READY_REENTRY_AB_SIM_PASS" not in log or re.search(r"(?im)^\s*(?:fatal|error):",log):
            raise ValueError("native A/B assertions did not finish")
        case_rows=re.findall(r"(?m)^MS7200_REENTRY_CASE rearm=(\d) scenario=(\d+) .* PASS$",log)
        if sorted((int(a),int(b)) for a,b in case_rows)!=[(a,b) for a in range(2) for b in range(10)]:
            raise ValueError("twenty A/B case reports required")
        for name,rearm in (("old-summary.json",0),("rearm-summary.json",1)):
            summary=json.loads((work/name).read_text())
            expected=dict(Passed=True,Rearm=rearm,Cases=10,InitialCommandsPerEpoch=300,
                          SettingsPerAdmission=7,Stable02DoesNotRepeat=True,
                          IncompletePollRejected=True,TransactionDriverStub=True,
                          WireLevelI2CExecuted=False,HardwareAccessed=False)
            if any(type(summary.get(key)) is not type(value) or summary[key]!=value for key,value in expected.items()):
                raise ValueError("A/B summary coverage differs")
        result["OldTraceAudit"]=audit_trace(work/"old-transactions.csv",commands,0)
        result["RearmTraceAudit"]=audit_trace(work/"rearm-transactions.csv",commands,1)
        result["PassLines"]=[line for line in log.splitlines() if line.startswith("MS7200_REENTRY_CASE ")]
        result["Passed"]=True
    except Exception as error:
        result["Error"]=type(error).__name__+": "+str(error)
    finally:
        result["SourceDrift"]=[name for name,digest in inputs.items() if sha(ROOT/name)!=digest]
        result["VectorDrift"]=sha(work/"rx_expected.hex")!=vector
        result["Passed"]=result["Passed"] and not result["SourceDrift"] and not result["VectorDrift"]
        result["ElapsedSeconds"]=round(time.monotonic()-started,3)
        result["EndedUTC"]=datetime.now(timezone.utc).isoformat()
        result["EvidenceSHA256"]={path.name:sha(path) for path in work.iterdir()
            if path.is_file() and path.suffix in (".log",".csv",".json",".hex")}
        with (work/"simulation-result.json").open("x",encoding="utf-8",newline="\n") as stream:
            json.dump(result,stream,indent=2);stream.write("\n")
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir",type=Path,required=True)
    args=parser.parse_args()
    outcome=run(args.workdir)
    print(json.dumps({key:outcome.get(key) for key in ("Passed","Error","ElapsedSeconds","OldTraceAudit","RearmTraceAudit","SourceDrift")}))
    raise SystemExit(0 if outcome["Passed"] else 1)
