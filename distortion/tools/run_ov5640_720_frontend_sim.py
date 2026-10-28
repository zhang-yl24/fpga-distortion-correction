"""Offline real-I2C init plus complete synthetic720 geometry/clock-stop test."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,importlib.util,json,os,re,sys,time,uuid
import prepare_ov5640_rgb565_720 as prepared

ROOT=prepared.ROOT;APPROVED=ROOT/"build/offline-20261024"
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_text(encoding="utf-8-sig"))
SOURCES=("rtl/reg16_i2c.v","rtl/experimental/ov5640_rgb565_720_init.v",
         "rtl/experimental/dvp_mode_admission_monitor.v","rtl/experimental/ov5640_rgb565_720_frontend.v",
         "tests/tb_ov5640_rgb565_720_frontend.sv",prepared.ROM,prepared.MANIFEST,
         "tools/prepare_ov5640_rgb565_720.py","tools/run_ov5640_720_frontend_sim.py",
         "tools/run-cadence-diagnostic-init-sim.py")


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("--monitor-evidence",type=Path,required=True)
    args=parser.parse_args();mode=prepared.verify();monitor_path=args.monitor_evidence.resolve();monitor=load(monitor_path)
    if not APPROVED.is_dir() or not monitor_path.is_relative_to(APPROVED.resolve()) or monitor.get("Passed") is not True or monitor.get("SourceSHA256")!=monitor.get("SourceSHA256After"):
        parser.error("completed source-bound monitor evidence under approved scratch required")
    for n,h in monitor["SourceSHA256"].items():
        if sha(ROOT/n)!=h:parser.error("monitor source/evidence changed")
    before={n:sha(ROOT/n) for n in SOURCES}
    protected={n:sha(ROOT/n) for n in load(ROOT/"board/corrected_gamma_pipeline_d5-sources.json")}
    protected.update({"tools/"+n:sha(ROOT/"tools"/n) for n in ("prepare_gamma_pipeline_d5.py","run_gamma_pipeline_d5_sim.py","build_gamma_pipeline_d5.py","resume_gamma_pipeline_d5.py")})
    work=APPROVED/("rgb565720-frontend-sim-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+"-"+uuid.uuid4().hex[:6]);work.mkdir(exist_ok=False)
    report={"Passed":False,"HardwareAccessed":False,"PDSAccessed":False,"SyntheticDVPOnly":True,"SourceSHA256":before,
            "MonitorEvidence":str(monitor_path),"MonitorEvidenceSHA256":sha(monitor_path),"OutputDirectory":str(work),
            "RegisterActions":len(mode["Actions"]),"Geometry":[2560,720],"ProtectedGammaSHA256":protected,
            "HardwareReleaseAllowed":False,"RawTransactionCoreInstantiated":False,"MeasuredFPS":None,
            "Limits":"Real reg16_i2c line model and two full-size synthetic HREF/VSYNC geometry frames at nominal42MHzPCLK/27MHzref, not pixel-content/DDR/UART transport. Source clock halt revokes admission while configured registers remain. No board pins/polarity inferred, no analog PLLlock, measured clock/fps, electrical/CDC constraints, PDS, optical or hardware acceptance. Admission must not reset in-flight transactions."}
    try:
        spec=importlib.util.spec_from_file_location("owned_frontend_sim",ROOT/"tools/run-cadence-diagnostic-init-sim.py")
        helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
        config_path=ROOT.parent/"team-config.local.json";config=load(config_path) if config_path.is_file() else {}
        bin_dir=Path(os.environ.get("FPGA_VIVADO_BIN") or config.get("vivado_bin") or r"E:\Vivado\Vivado\2017.4\bin")
        deadline=time.monotonic()+600;top="tb_ov5640_rgb565_720_frontend"
        helper.run_tool(bin_dir,"xvlog.bat",["--sv",*[str(ROOT/n) for n in SOURCES if n.endswith((".v",".sv"))]],work,deadline,"compile")
        helper.run_tool(bin_dir,"xelab.bat",[top,"-s",top],work,deadline,"elaborate")
        helper.run_tool(bin_dir,"xsim.bat",[top,"-runall","-log","simulation.log"],work,deadline,"simulate")
        text=(work/"simulation.log").read_text(encoding="utf-8",errors="replace")
        required=("PASS frontend configured remains disarmed before live geometry","PASS frontend full2560x720 lines and nominal42MHz-domain edge accounting; two fresh frames","PASS RGB565720 frontend:")
        if not all(v in text for v in required) or re.search(r"(?im)^\s*(?:fatal|error):",text):raise ValueError("complete frontend init/live geometry/clock-stop test failed")
        report["SourceSHA256After"]={n:sha(ROOT/n) for n in before}
        if report["SourceSHA256After"]!=before or any(sha(ROOT/n)!=h for n,h in protected.items()):raise ValueError("frontend or frozen Gamma source/helper drift")
        report.update(Passed=True,DigitalAdmissionTestPassed=True,SimulationLogSHA256=sha(work/"simulation.log"))
    except Exception as exc:report["Error"]=str(exc);print(str(exc),file=sys.stderr)
    finally:
        path=work/"rgb565720-frontend-simulation.json";path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8");print(path)
    return 0 if report["Passed"] else 1


if __name__=="__main__":raise SystemExit(main())
