"""Execute the actual HDMI30 controller against a transaction-level I2C model.

This checks emitted register commands, repeated EDID writes, completion, busy
delays and reset replay. It does not simulate the wire-level I2C driver, PHY,
host EDID negotiation, full video pipeline or physical board.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import csv
import json
import re
import time

import board1080_edid as edid
from simulation_tools import resolve_vivado_bin
from run_gamma_pipeline_d5_sim import tool as vivado_tool

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "build/board1080-hdmi30"
CONTROLLER = "rtl/experimental/ms7200_1080p30_ctl.v"
BENCH = "tests/tb_board1080_hdmi30_edid.sv"
TOP = "tb_board1080_hdmi30_edid"
REPORT = "hdmi30-controller-simulation.json"
SOURCES = (CONTROLLER, BENCH, "platform/video_base/source/hdmi/ms7200_ctl.v",
           "tools/board1080_edid.py", "tools/run_board1080_hdmi30_sim.py",
           "tools/simulation_tools.py", "tools/run_gamma_pipeline_d5_sim.py")


def write_vectors(work):
    work = Path(work)
    commands = edid.command_rows(ROOT / CONTROLLER)
    payload = edid.build_edid(ROOT / SOURCES[2])
    for filename, content in (
            ("edid_expected.hex", "".join(f"{byte:02x}\n" for byte in payload)),
            ("commands_expected.hex", "".join(f"{addr:04x}{data:02x}\n" for _, addr, data in commands))):
        with (work / filename).open("x", encoding="ascii", newline="\n") as stream:
            stream.write(content)
    return {name: edid.sha(work / name) for name in ("edid_expected.hex", "commands_expected.hex")}


def validate_results(work):
    work = Path(work)
    summary = json.loads((work / "summary.json").read_text(encoding="utf-8"))
    required = {"Passed": True, "Epochs": 2, "InitialWritesPerEpoch": 300, "SettingWritesPerEpoch": 7,
                "EDIDWritesPerEpoch": 264, "ResetReplayPassed": True,
                "VariableBusyDelaysExercised": True, "ActualControllerExecuted": True,
                "PhysicalI2CVerified": False}
    if any(type(summary.get(key)) is not type(value) or summary[key] != value
           for key, value in required.items()):
        raise ValueError("controller coverage or verification scope differs")
    with (work / "hdmi30-commands.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows or set(rows[0]) != {"epoch", "index", "write", "addr", "data", "response", "busy_cycles"}:
        raise ValueError("transaction log schema differs")
    commands = edid.command_rows(ROOT / CONTROLLER)
    expected = commands[:300] + commands[304:311]
    # This receipt certifies this bounded bench, including its two status
    # polls (not-ready, then ready). Separate write/read subsequences would
    # silently accept settings before readiness or reads after all writes.
    sequence = [(-1, 1, 3, 0x5A, 0), (-1, 0, 3, 0x5A, 0x5A)]
    sequence += [(index, 1, address, data, 0) for index, address, data in commands[:300]]
    sequence += [(-1, 0, 0x209C + index % 4, 0, 2 if index == 6 else 0)
                 for index in range(8)]
    sequence += [(index, 1, address, data, 0) for index, address, data in commands[304:311]]
    ordered = [(epoch, *entry, 12 + number % 5 * 7) for epoch in (1, 2)
               for number, entry in enumerate(sequence)]
    observed = [(int(row["epoch"]), int(row["index"]), int(row["write"]),
                 int(row["addr"], 16), int(row["data"], 16),
                 int(row["response"], 16), int(row["busy_cycles"])) for row in rows]
    if observed != ordered:
        raise ValueError("ordered reset epochs, readiness responses or transaction delays differ")
    epochs = {int(row["epoch"]) for row in rows}
    if epochs != {1, 2} or any(row["write"] not in ("0", "1") for row in rows):
        raise ValueError("two reset epochs with explicit transaction directions required")
    for epoch in (1, 2):
        writes = [row for row in rows if int(row["epoch"]) == epoch and row["write"] == "1"]
        actual = [(int(row["index"]), int(row["addr"], 16), int(row["data"], 16))
                  for row in writes if int(row["index"]) >= 0]
        if actual != expected:
            raise ValueError("emitted writes differ from all 300 init and seven setting commands")
        scratch = [row for row in writes if int(row["index"]) < 0]
        if len(scratch) != 1 or int(scratch[0]["index"]) != -1 or \
                (int(scratch[0]["addr"], 16), int(scratch[0]["data"], 16)) != (3, 0x5A):
            raise ValueError("identification scratch write differs")
        delays = {int(row["busy_cycles"]) for row in rows if int(row["epoch"]) == epoch}
        if delays != {12, 19, 26, 33, 40}:
            raise ValueError("variable busy delays not exercised")
        memory = bytearray(256)
        edid_writes = 0
        for _, address, data in actual:
            if 0xD00 <= address < 0xE00:
                memory[address - 0xD00] = data
                edid_writes += 1
        if edid_writes != 264 or bytes(memory) != edid.build_edid(ROOT / SOURCES[2]):
            raise ValueError("emitted EDID bytes are incomplete or differ")
        reads = [row for row in rows if int(row["epoch"]) == epoch and row["write"] == "0"]
        if len(reads) < 9 or int(reads[0]["addr"], 16) != 3 or int(reads[0]["response"], 16) != 0x5A:
            raise ValueError("device identification/status read sequence missing")
        if any(int(row["index"]) != -1 for row in reads):
            raise ValueError("read incorrectly marked as table write")
        for index, row in enumerate(reads[1:]):
            if int(row["addr"], 16) != 0x209C + index % 4:
                raise ValueError("status poll order differs")
    return summary, rows


def run(workdir, maximum_seconds=120):
    if type(maximum_seconds) is not int or not 30 <= maximum_seconds <= 180:
        raise ValueError("whole-run budget must be integer30..180 seconds")
    work = Path(workdir).resolve()
    if work.parent != BASE.resolve() or not work.is_dir() or any(work.iterdir()):
        raise ValueError("fresh existing child of build/board1080-hdmi30 required")
    profile = edid.audit_controller(ROOT / CONTROLLER, ROOT / SOURCES[2])
    before = {name: edid.sha(ROOT / name) for name in SOURCES}
    bin_dir = resolve_vivado_bin(ROOT.parent)
    report = {"Schema": "board1080-hdmi30-controller-simulation-v1", "Passed": False,
              "StartedUTC": datetime.now(timezone.utc).isoformat(), "MaximumSeconds": maximum_seconds,
              "SourceSHA256": before, "ProfileAudit": profile, "Commands": [],
              "PhysicalI2CVerified": False, "HardwareAccessed": False,
              "HostModeSelectionVerified": False, "FullVideoPipelineExecuted": False,
              "PDSAccessed": False, "HardwareReleaseAllowed": False}
    started = time.monotonic()
    vectors = {}
    try:
        vectors = write_vectors(work)
        for executable, arguments, stage in (
                ("xvlog.bat", ["--sv", str(ROOT / CONTROLLER), str(ROOT / BENCH)], "compile"),
                ("xelab.bat", [TOP, "-s", "hdmi30_controller"], "elaborate"),
                ("xsim.bat", ["hdmi30_controller", "-runall", "-log", "simulation.log"], "simulate")):
            command = {"Stage": stage, "NativeArgv": [str(bin_dir / executable), *arguments], "ReturnCode": None}
            report["Commands"].append(command)
            vivado_tool(bin_dir, executable, arguments, work, started + maximum_seconds, stage)
            command["ReturnCode"] = 0
        log = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        if "BOARD1080_HDMI30_EDID_SIM_PASS" not in log or re.search(r"(?im)^\s*(?:fatal|error):", log):
            raise ValueError("controller assertions did not complete successfully")
        summary, rows = validate_results(work)
        report.update(Passed=True, ActualControllerExecuted=True, Summary=summary,
                      TransactionCount=len(rows), WritesPerEpoch=307,
                      PassLines=[line for line in log.splitlines() if line.startswith("PASS")])
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = str(error)
    finally:
        report["InputDrift"] = [name for name, digest in before.items()
                                if not (ROOT / name).is_file() or edid.sha(ROOT / name) != digest]
        report["VectorDrift"] = [name for name, digest in vectors.items()
                                 if not (work / name).is_file() or edid.sha(work / name) != digest]
        report["Passed"] = report["Passed"] and not report["InputDrift"] and not report["VectorDrift"]
        report["EvidenceSHA256"] = {path.name: edid.sha(path) for path in work.iterdir()
                                    if path.is_file() and path.suffix in (".log", ".hex", ".csv", ".json")}
        report["ElapsedSeconds"] = round(time.monotonic() - started, 3)
        report["EndedUTC"] = datetime.now(timezone.utc).isoformat()
        with (work / REPORT).open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False); stream.write("\n")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", required=True, type=Path)
    parser.add_argument("--maximum-seconds", type=int, default=120)
    args = parser.parse_args(argv)
    result = run(args.work_dir, args.maximum_seconds)
    print(json.dumps({"Passed": result["Passed"], "Error": result.get("Error"),
                      "Report": str(args.work_dir / REPORT)}))
    return 0 if result["Passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
