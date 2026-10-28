"""Bounded offline init/line-model simulation; never PDS or hardware."""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import hashlib
import importlib.util
import json
import os
import sys
import time
import uuid
import prepare_ov5640_rgb565_720 as prepared

ROOT=prepared.ROOT
APPROVED=ROOT/"build/offline-20261024"
NAMES=("rtl/reg16_i2c.v","rtl/experimental/ov5640_rgb565_720_init.v",prepared.ROM,prepared.MANIFEST,
       "tests/tb_ov5640_rgb565_720_init.sv","tools/prepare_ov5640_rgb565_720.py",
       "tools/run_ov5640_rgb565_720_sim.py","tools/run-cadence-diagnostic-init-sim.py",
       "tools/ov5640_clock_sequence_audit.py",prepared.BASE,prepared.PROPOSAL)
CASES=("complete720_readback_unique_wake_rmw_and_verified_data_high","pad_read_address_nack_no_wake",
       "initial_clock_default_mismatch_no_pll_writes","preflight_geometry_mismatch_no_wake",
       "postwake_read_nack_never_configured","masked_rmw_match_cannot_excuse_fullbyte_noack")
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_text(encoding="utf-8-sig"))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--maximum-seconds",type=int,default=600);args=parser.parse_args()
    if not APPROVED.is_dir() or not 60<=args.maximum_seconds<=1800:parser.error("existing approved scratch and finite60..1800s bound required")
    mode=prepared.verify();before={n:sha(ROOT/n) for n in NAMES}
    # Read-only watch of the independently running Gamma PDS source set/helpers.
    gamma=load(ROOT/"board/corrected_gamma_pipeline_d5-sources.json")
    protected={n:sha(ROOT/n) for n in gamma}
    protected.update({"tools/"+n:sha(ROOT/"tools"/n) for n in
                      ("prepare_gamma_pipeline_d5.py","run_gamma_pipeline_d5_sim.py","build_gamma_pipeline_d5.py")})
    work=APPROVED/("rgb565720-init-sim-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+"-"+uuid.uuid4().hex[:6])
    work.mkdir(exist_ok=False)
    report={"Passed":False,"HardwareAccessed":False,"PDSAccessed":False,"SyntheticOnly":True,
            "SourceSHA256":before,"ProtectedGammaSourceSHA256":protected,"OutputDirectory":str(work),
            "RegisterActionCount":len(mode["Actions"]),"ImageSize":[1280,720],"ModeAdmissionPassed":False,
            "ClockActivityAndLineFreshnessMonitorImplemented":False,
            "Limits":"Real reg16_i2c with synthetic open-drain register model. Complete critical readback/configuration only. No PCLK/line/frame-freshness admission, raw authorization, measured mode/fps/PLL lock/voltage/optics or hardware acceptance. The independent existing720 downstream digital test is separate."}
    try:
        spec=importlib.util.spec_from_file_location("owned_vivado_sim",ROOT/"tools/run-cadence-diagnostic-init-sim.py")
        helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
        config_path=ROOT.parent/"team-config.local.json";config=load(config_path) if config_path.is_file() else {}
        bin_dir=Path(os.environ.get("FPGA_VIVADO_BIN") or config.get("vivado_bin") or r"E:\Vivado\Vivado\2017.4\bin")
        deadline=time.monotonic()+args.maximum_seconds;top="tb_ov5640_rgb565_720_init"
        files=[str(ROOT/n) for n in NAMES if n.endswith((".v",".sv"))]
        helper.run_tool(bin_dir,"xvlog.bat",["--sv",*files],work,deadline,"compile")
        helper.run_tool(bin_dir,"xelab.bat",[top,"-s",top],work,deadline,"elaborate")
        helper.run_tool(bin_dir,"xsim.bat",[top,"-runall","-log","simulation.log"],work,deadline,"simulate")
        text=(work/"simulation.log").read_text(encoding="utf-8",errors="replace")
        import re
        if re.findall(r"(?m)^PASS_CASE (\S+)\s*$",text)!=list(CASES) or "PASS RGB565720 init:" not in text or re.search(r"(?im)^\s*(?:fatal|error):",text):
            raise ValueError("required720 register line-model cases did not pass")
        report["SourceSHA256After"]={n:sha(ROOT/n) for n in before}
        if report["SourceSHA256After"]!=before or any(sha(ROOT/n)!=h for n,h in protected.items()):
            raise ValueError("new720 or frozen Gamma input changed")
        prepared.verify();report["Passed"]=True;report["PassedCases"]=list(CASES)
        report["SimulationLogSHA256"]=sha(work/"simulation.log");report["TransactionTraceSHA256"]=sha(work/"rgb565720-transactions.csv")
    except Exception as exc:report["Error"]=str(exc);print(str(exc),file=sys.stderr)
    finally:
        report["EndedUtc"]=datetime.now(timezone.utc).isoformat()
        output=work/"rgb565720-register-simulation.json";output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8");print(output)
    return 0 if report["Passed"] else 1


if __name__=="__main__":raise SystemExit(main())
