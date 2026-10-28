"""Bounded offline cache unit: decoded timing cut + retained FIFO/cache cases."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, re, sys, time, uuid

ROOT = Path(__file__).resolve().parents[1]
APPROVED = ROOT / "build/offline-20261024"
sys.path.insert(0, str(ROOT / "tools"))
from run_gamma_pipeline_d5_sim import tool

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    backup = APPROVED / "ddr_compact_neighbour_cache-FFD8CB22-before-decoded-query-20261026.v"
    old = json.loads(backup.with_suffix(".source.json").read_text(encoding="utf-8"))
    assert APPROVED.is_dir() and sha(backup) == old["SHA256"] == "ffd8cb223329995ce3a2b6938ba2e50ea5d28758187182704b9fc8baf4ed3edf"
    protected = old["ProtectedBefore"]
    assert all(sha(ROOT / n) == h for n, h in protected.items()), "Frozen source/helper changed"
    names = ("rtl/experimental/ddr_compact_neighbour_cache.v", "tests/tb_compact_decoded_query.sv",
             "tests/tb_compact_ready_fifo2.sv", "tests/tb_compact_neighbour_cache.sv",
             "tools/run_compact_decoded_unit.py", "tools/run_gamma_pipeline_d5_sim.py")
    before = {n: sha(ROOT / n) for n in names}
    work = APPROVED / ("compact-decoded-unit-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:6])
    work.mkdir(exist_ok=False)
    text = (ROOT / names[3]).read_text(encoding="utf-8")
    assert text.count("dut.valid_lines[dut.selected_line]") == 1
    text = text.replace("dut.valid_lines[dut.selected_line]", "dut.inner.valid_lines[dut.inner.selected_line]")
    legacy = work / "tb_compact_neighbour_cache_private_hierarchy.sv"
    legacy.write_text(text, encoding="utf-8")
    report = {"Passed": False, "HardwareAccessed": False, "PDSAccessed": False,
              "SourceSHA256": before, "ProtectedBefore": protected, "PreviousCacheSHA256": sha(backup),
              "PreviousCacheBackup": str(backup), "DerivedLegacySHA256": sha(legacy),
              "LegacyOnlyEdit": "Private .inner hierarchy for fault valid-line assertion", "Workdir": str(work)}
    try:
        deadline = time.monotonic() + 240
        bin_dir = Path(r"E:/Vivado/Vivado/2017.4/bin")
        top = "tb_compact_decoded_query"
        for executable, args, stage in (
            ("xvlog.bat", ["--sv", str(ROOT / names[0]), str(legacy), str(ROOT / names[2]), str(ROOT / names[1])], "compile"),
            ("xelab.bat", [top, "-s", top], "elaborate"),
            ("xsim.bat", [top, "-runall", "-log", "simulation.log"], "simulate")):
            report["Stage"] = stage
            tool(bin_dir, executable, args, work, deadline, stage)
        text = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
        required = ("PASS decoded signed17/32 odd-WIDTH639", "PASS decoded elastic stall",
                    "PASS FIFO2 ready boundary", "PASS FIFO2 queued fault quarantine",
                    "PASS compact cache WIDTH640:", "PASS compact cache WIDTH1024:",
                    "PASS compact decoded-query/FIFO2/conflict/fault directed regression")
        assert all(n in text for n in required) and not re.search(r"(?im)^\s*(?:fatal|error):", text)
        report.update(Passed=True, PassLines=[line for line in text.splitlines() if line.startswith("PASS ")])
    except (Exception, KeyboardInterrupt) as exc:
        report["Error"] = type(exc).__name__ + ": " + str(exc)
    finally:
        report["SourceSHA256After"] = {n: sha(ROOT / n) for n in names}
        report["ProtectedAfter"] = {n: sha(ROOT / n) for n in protected}
        if report["SourceSHA256After"] != before or report["ProtectedAfter"] != protected:
            report.update(Passed=False, SourceDrift=True)
        report["LogSHA256"] = {p.name: sha(p) for p in work.glob("*.log")}
        report["Limits"] = "Digital unit only: decoded signed address boundary, FIFO2 admission, conflict/negative/border,80-hit streaming, stall/frame-drain and DDR fault tests. Main actual-input suites and fresh final PDS timing remain required. No clock/constraint/algorithm precision change."
        output = work / "compact-decoded-unit.json"
        output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: v for k, v in report.items() if not k.startswith("Protected")}, indent=2))
        print(output)
    return 0 if report["Passed"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
