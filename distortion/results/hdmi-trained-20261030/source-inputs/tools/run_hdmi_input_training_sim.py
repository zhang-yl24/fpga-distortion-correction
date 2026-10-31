"""Native digital tests of the isolated two-line HDMI polarity trainer.

Frozen observer RTL and existing build helpers are read without modification.
No PDS, bitstream generation or hardware access is performed.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import re
import time

from run_gamma_pipeline_d5_sim import tool
from simulation_tools import resolve_vivado_bin

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "rtl/experimental/hdmi1080_input_status_trained.v",
    "rtl/experimental/hdmi1080_input_status_cdc.v",
    "rtl/experimental/dvp_mode_admission_monitor_cdc.v",
    "tests/tb_hdmi_input_polarity_training.sv",
    "tests/tb_hdmi_input_training_raster.sv",
)
NATIVE_TB = "tests/tb_board1080_input_status_cdc.sv"
HELPERS = ("tools/run_hdmi_input_training_sim.py", "tools/run_gamma_pipeline_d5_sim.py",
           "tools/simulation_tools.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(work, maximum_seconds=600):
    work = Path(work).resolve()
    if not 60 <= maximum_seconds <= 900 or work.exists() or not work.parent.is_dir():
        raise ValueError("fresh directory in an existing parent and bound 60..900 seconds required")
    work.mkdir()
    hashes = {name: sha(ROOT / name) for name in (*SOURCES, NATIVE_TB, *HELPERS)}
    native = (ROOT / NATIVE_TB).read_text(encoding="utf-8")
    if native.count("hdmi1080_input_status_cdc dut(") != 1:
        raise ValueError("original native test module anchor differs")
    native = native.replace("hdmi1080_input_status_cdc dut(", "hdmi1080_input_status_trained dut(", 1)
    native_tb = work / "tb_board1080_input_status_trained.sv"
    native_tb.write_text(native, encoding="utf-8", newline="\n")
    report = dict(Schema="hdmi-input-training-simulation-v1", Passed=False,
                  StartedUTC=datetime.now(timezone.utc).isoformat(), SourceSHA256=hashes,
                  GeneratedNativeTB={"Source": NATIVE_TB, "Path": str(native_tb),
                                     "SHA256": sha(native_tb), "Transformation": "Only the DUT module name changes to the isolated trained candidate."},
                  Commands=[], Suites={}, HardwareAccessed=False, PDSAccessed=False,
                  BitstreamGenerated=False, HardwareReleaseAllowed=False,
                  Limits="Digital startup training, timing geometry and fault tests only. The injected one-sample transient is hypothetical; it does not establish the physical cause. No candidate mapped CDC/STA, external AC, real input pixels, DDR or corrected display acceptance.")
    deadline = time.monotonic() + maximum_seconds
    try:
        bin_dir = resolve_vivado_bin(ROOT.parent)
        def stage(name, args, label):
            item = {"Stage": label, "Argv": [str(bin_dir / name), *args], "ReturnCode": None}
            report["Commands"].append(item)
            tool(bin_dir, name, args, work, deadline, label)
            item["ReturnCode"] = 0
        stage("xvlog.bat", ["--sv", *[str(ROOT / name) for name in SOURCES], str(native_tb)], "compile")
        suites = (("directed", "tb_hdmi_input_polarity_training", "PASS hdmi input polarity training directed regression"),
                  ("raster", "tb_hdmi_input_training_raster", "PASS trained observer recovers first-DE transient"),
                  ("native", "tb_board1080_input_status_cdc", "PASS board1080 input_status_cdc unit:"))
        for label, top, marker in suites:
            snapshot = "hdmi_training_" + label
            stage("xelab.bat", [top, "-s", snapshot], label + "-elaborate")
            stage("xsim.bat", [snapshot, "-runall", "-log", label + "-simulation.log"], label + "-simulate")
            text = (work / (label + "-simulation.log")).read_text(encoding="utf-8", errors="replace")
            if marker not in text or re.search(r"(?im)^\s*(?:fatal|error):", text):
                raise ValueError("native training suite did not pass: " + label)
            result = {"Passed": True, "Top": top}
            if label == "directed":
                cases = re.findall(r"(?m)^POLARITY_TRAINING_CASE (\S+) PASS\s*$", text)
                if len(cases) != 11 or len(set(cases)) != 11 or "POLARITY_TRAINING_SUMMARY cases=11 " not in text:
                    raise ValueError("eleven directed training cases required")
                result["Cases"] = cases
            elif label == "raster":
                result["Summary"] = json.loads((work / "counterexample-summary.json").read_text())
                result["Samples"] = re.findall(r"(?m)^COUNTEREXAMPLE_SAMPLE .+$", text)
                if len(result["Samples"]) != 2 or result["Summary"]["transient_samples"] != 1:
                    raise ValueError("one transient sample and two complete-raster observations required")
            else:
                result["Summary"] = json.loads((work / "input-status-cdc-unit-summary.json").read_text())
                if not result["Summary"]["passed"] or result["Summary"]["qualification_phases"] != 2 or result["Summary"]["polarity_mask"] != 3:
                    raise ValueError("both full-raster polarities required")
            report["Suites"][label] = result
        report["Passed"] = True
    except Exception as error:
        report["Error"] = type(error).__name__ + ": " + str(error)
    finally:
        report["EndedUTC"] = datetime.now(timezone.utc).isoformat()
        report["SourceDrift"] = [name for name, wanted in hashes.items() if sha(ROOT / name) != wanted]
        report["Passed"] = report["Passed"] and not report["SourceDrift"]
        report["EvidenceSHA256"] = {path.name: sha(path) for path in work.iterdir()
                                    if path.is_file() and path.suffix in (".log", ".json", ".sv")}
        with (work / "simulation-result.json").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=int, default=600)
    args = parser.parse_args()
    result = run(args.workdir, args.maximum_seconds)
    print(json.dumps({"Passed": result["Passed"], "Error": result.get("Error"), "WorkDirectory": str(args.workdir)}))
    raise SystemExit(0 if result["Passed"] else 1)
