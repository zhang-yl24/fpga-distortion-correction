"""Run real checked-I2C wire integration for the isolated rearm wrapper."""
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
from run_ms72xx_checked_sim import command_rows,expected_wire_trace
from run_ms7200_ready_reentry_sim import audit_source

ROOT=Path(__file__).resolve().parents[1]
SOURCES=("rtl/experimental/ms7200_1080p30_rearm_ctl.v",
         "rtl/experimental/ms72xx_rearm_observed_ctl.v",
         "rtl/experimental/ms7210_checked_ctl.v","rtl/experimental/iic_dri_checked.v",
         "tests/tb_ms72xx_rearm_observed_e2e.sv")
HELPERS=("tools/run_ms72xx_rearm_wire_sim.py","tools/run_ms7200_ready_reentry_sim.py",
         "tools/run_ms7200_ready_level_sim.py","tools/run_ms72xx_checked_sim.py",
         "tools/run_gamma_pipeline_d5_sim.py","tools/simulation_tools.py",
         "rtl/experimental/ms72xx_ready_observed_ctl.v",
         "rtl/experimental/ms7200_1080p30_ready_ctl.v","rtl/experimental/ms7200_1080p30_ctl.v")
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()


def exact_trace(rx,tx):
    # Keep all seven existing nominal/NACK/reset epochs unchanged.
    result=expected_wire_trace()
    sequence=[(0x56,0,3,0x5a,0,0),(0x56,1,3,0,0x5a,0)]
    sequence += [(0x56,0,int(row[:4],16),int(row[4:],16),0,0) for row in rx[:300]]
    def polls(count,ready):
        return [(0x56,1,0x209c+i%4,0,ready if i%4==2 else 0,0) for i in range(count)]
    settings=[(0x56,0,int(row[:4],16),int(row[4:],16),0,0) for row in rx[304:311]]
    sequence += polls(4,2)+settings
    sequence += [(0xb2,0,3,0x5a,0,0),(0xb2,1,3,0,0x5a,0)]
    sequence += [(0xb2,0,int(row[:4],16),int(row[4:],16),0,0) for row in tx]
    sequence += polls(132,2)+polls(8,3)+polls(4,2)+settings
    sequence += polls(132,2)+polls(8,1)+polls(4,2)+settings+polls(132,2)
    if len(sequence)!=798:
        raise ValueError("reentry oracle length differs")
    result += [(7,index+1,*entry) for index,entry in enumerate(sequence)]
    return result


def read_wire(path):
    with path.open(encoding="ascii",newline="") as stream:
        reader=csv.DictReader(stream)
        if reader.fieldnames != ["scenario","request","device","read","addr","data","response","nack"]:
            raise ValueError("wire trace schema differs")
        return [(int(row["scenario"]),int(row["request"]),int(row["device"],16),int(row["read"]),
                 int(row["addr"],16),int(row["data"],16),int(row["response"],16),int(row["nack"])) for row in reader]


def run(workdir):
    work=Path(workdir).resolve()
    if work.exists():
        raise FileExistsError("fresh integration work directory required")
    audit_source()
    old_wrapper=(ROOT/"rtl/experimental/ms72xx_ready_observed_ctl.v").read_text()
    wrapper=(ROOT/SOURCES[1]).read_text()
    expected=old_wrapper.replace("module ms72xx_ready_observed_ctl #(","module ms72xx_rearm_observed_ctl #(",1).replace(
        "    ms7200_1080p30_ready_ctl rx_controller (","    ms7200_1080p30_rearm_ctl rx_controller (",1)
    if wrapper!=expected:
        raise ValueError("wrapper differs beyond module/RX-module substitutions")
    rx=command_rows(ROOT/SOURCES[0],311)
    tx=command_rows(ROOT/SOURCES[2],49)
    if rx!=command_rows(ROOT/"rtl/experimental/ms7200_1080p30_ctl.v",311):
        raise ValueError("311 RX register/EDID commands differ")
    bound={name:sha(ROOT/name) for name in (*SOURCES,*HELPERS)}
    work.mkdir(parents=True)
    for filename,rows in (("rx_expected.hex",rx),("tx_expected.hex",tx)):
        (work/filename).write_text("\n".join(rows)+"\n",encoding="ascii")
    vectors={name:sha(work/name) for name in ("rx_expected.hex","tx_expected.hex")}
    report=dict(Schema="ms72xx-rearm-wire-simulation-v1",Passed=False,
                StartedUTC=datetime.now(timezone.utc).isoformat(),SourceSHA256=bound,
                All311RXCommandsUnchanged=True,All49TXCommandsUnchanged=True,
                WrapperOnlyModuleSubstitutions=True,HardwareAccessed=False,PDSAccessed=False,
                TransactionDriverStub=False,WireLevelI2CExecuted=True,Commands=[],
                Limits="Clocked SCL/SDA wire oracle with synthetic slave replies. Covers complete03/01-to02 re-entry, steady02, existing checked-driver NACK/reset/ownership cases and per-STOP telemetry. Does not model physical receiver register effects, PLL locking or real HDMI pixels.")
    started=time.monotonic()
    try:
        bin_dir=resolve_vivado_bin(ROOT.parent)
        for executable,args,stage in (
            ("xvlog.bat",["--sv",*[str(ROOT/name) for name in SOURCES]],"compile"),
            ("xelab.bat",["tb_ms72xx_rearm_observed_e2e","-s","rearm_wire_tb"],"elaborate"),
            ("xsim.bat",["rearm_wire_tb","-runall","-log","simulation.log"],"simulate"),
        ):
            row=dict(Stage=stage,Argv=[str(bin_dir/executable),*args],ReturnCode=None)
            report["Commands"].append(row)
            tool(bin_dir,executable,args,work,started+300,stage)
            row["ReturnCode"]=0
        log=(work/"simulation.log").read_text(encoding="utf-8",errors="replace")
        if "MS72XX_REARM_OBSERVED_E2E_SIM_PASS" not in log or re.search(r"(?im)^\s*(?:fatal|error):",log):
            raise ValueError("native wire assertions did not complete")
        if [int(n) for n in re.findall(r"(?m)^MS72XX_E2E_SCENARIO_PASS scenario=(\d+)\b",log)]!=list(range(8)):
            raise ValueError("eight scenarios did not complete")
        stages=re.findall(r"(?m)^MS72XX_REENTRY_WIRE_STAGE (.+?) PASS$",log)
        if stages!=["first02_and_33_stable_polls","complete03_to02_once_then33_stable_polls","complete01_to02_once_then33_stable_polls"]:
            raise ValueError("reentry stage coverage differs")
        actual=read_wire(work/"wire-transactions.csv")
        wanted=exact_trace(rx,tx)
        if actual!=wanted:
            first=next((index for index,(a,b) in enumerate(zip(actual,wanted)) if a!=b),min(len(actual),len(wanted)))
            raise ValueError("exact wire oracle mismatch at index "+str(first))
        with (work/"telemetry-transactions.csv").open(encoding="ascii",newline="") as stream:
            observed=list(csv.DictReader(stream))
        successful=[row for row in actual if row[-1]==0]
        if len(actual)!=2915 or len(successful)!=2910 or len(observed)!=2910:
            raise ValueError("wire/telemetry transaction counts differ")
        counters={}
        for wire,tap in zip(successful,observed):
            scenario,request,device,read,address,data,response,_=wire
            counters[scenario]=counters.get(scenario,0)+1
            expected_meta=(2 if device==0xb2 else 0)|read
            if (int(tap["scenario"]),int(tap["request"]),int(tap["completed"]),int(tap["meta"],16),int(tap["addr"],16),int(tap["value"],16)) != (
                scenario,request,counters[scenario],expected_meta,address,response if read else data):
                raise ValueError("telemetry differs from successful physical wire transaction")
        summary=json.loads((work/"summary.json").read_text())
        for key,wanted_value in dict(Passed=True,Scenarios=8,ActualRXControllerExecuted=True,
            ActualTXControllerExecuted=True,TransactionDriverStub=False,WireLevelI2CExecuted=True,
            EarlyRXFailure=True,LastRXSettingFailure=True,FirstTXFailureAfterRXDone=True,
            LastTXWriteFailure=True,PostCompletionFailure=True,CommonResetRecovery=True,
            FailureSameCycleGating=True,NoAutoRetry=True,BackgroundRXPollResumed=True,
            TelemetryComparedToWire=True,SuccessfulTelemetryUpdates=2910,NACKTelemetrySuppressed=5,
            HardwareAccessed=False).items():
            if type(summary.get(key)) is not type(wanted_value) or summary[key]!=wanted_value:
                raise ValueError("summary coverage differs: "+key)
        report.update(Passed=True,Summary=summary,WireTransactions=2915,SuccessfulTelemetryCompared=2910,
                      NACKsSuppressed=5,ReentryScenarioTransactions=798,InitialWrites=300,
                      ReentrySettingGroups=3,ReentrySettingsPerGroup=7,TXWritesOnlyOnce=49,
                      StablePollsPerReadyInterval=33,ReentryStages=stages,
                      PassLines=[line for line in log.splitlines() if "_PASS" in line or line.startswith("MS72XX_REENTRY_WIRE_STAGE ")])
    except Exception as error:
        report["Error"]=type(error).__name__+": "+str(error)
    finally:
        report["SourceDrift"]=[name for name,wanted in bound.items() if sha(ROOT/name)!=wanted]
        report["VectorDrift"]=[name for name,wanted in vectors.items() if sha(work/name)!=wanted]
        report["Passed"]=report["Passed"] and not report["SourceDrift"] and not report["VectorDrift"]
        report["ElapsedSeconds"]=round(time.monotonic()-started,3)
        report["EndedUTC"]=datetime.now(timezone.utc).isoformat()
        report["EvidenceSHA256"]={path.name:sha(path) for path in work.iterdir()
            if path.is_file() and path.suffix in (".log",".csv",".json",".hex")}
        with (work/"simulation-result.json").open("x",encoding="utf-8",newline="\n") as stream:
            json.dump(report,stream,indent=2);stream.write("\n")
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir",type=Path,required=True)
    args=parser.parse_args()
    result=run(args.workdir)
    print(json.dumps({key:result.get(key) for key in ("Passed","Error","ElapsedSeconds","WireTransactions","SuccessfulTelemetryCompared","NACKsSuppressed","ReentryStages","SourceDrift")}))
    raise SystemExit(0 if result["Passed"] else 1)
