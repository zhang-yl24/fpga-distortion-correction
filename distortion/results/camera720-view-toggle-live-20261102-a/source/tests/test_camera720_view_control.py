"""Real RTL button regression; Icarus when installed, otherwise local XSim."""
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (ROOT / "rtl/experimental/camera720_view_control.v",
           ROOT / "tests/tb_camera720_view_control.sv")
PASS = "CAMERA720_VIEW_CONTROL_PASS debounce=4,1 bounce hold reset pulse boundary"


def test_button_rtl(tmp_path):
    work = tmp_path.resolve()
    iverilog, vvp = shutil.which("iverilog"), shutil.which("vvp")
    if iverilog and vvp:
        compiled = subprocess.run(
            [iverilog, "-g2012", "-s", "tb_camera720_view_control", "-o", str(work / "sim.vvp"),
             *map(str, SOURCES)], cwd=work, capture_output=True, text=True, timeout=60)
        assert compiled.returncode == 0, compiled.stdout + compiled.stderr
        simulated = subprocess.run([vvp, str(work / "sim.vvp")], cwd=work,
                                   capture_output=True, text=True, timeout=60)
        log = simulated.stdout + simulated.stderr
        assert simulated.returncode == 0, log
    else:
        sys.path.insert(0, str(ROOT / "tools"))
        from simulation_tools import resolve_vivado_bin
        from run_gamma_pipeline_d5_sim import tool
        binary = resolve_vivado_bin(ROOT.parent).resolve()
        if os.name != "nt" or not all((binary / name).is_file()
                                       for name in ("xvlog.bat", "xelab.bat", "xsim.bat")):
            pytest.skip("button RTL simulation requires Icarus or configured local XSim")
        deadline = time.monotonic() + 120
        tool(binary, "xvlog.bat", ["--sv", *map(str, SOURCES)], work, deadline, "compile")
        tool(binary, "xelab.bat", ["tb_camera720_view_control", "-s", "camera720_view_control_tb",
                                   "--timescale", "1ns/1ps"], work, deadline, "elaborate")
        tool(binary, "xsim.bat", ["camera720_view_control_tb", "-runall", "-log", "simulation.log"],
             work, deadline, "simulate")
        log = (work / "simulation.log").read_text(encoding="utf-8", errors="replace")
    assert log.count(PASS) == 1, log
    assert not re.search(r"(?im)^\s*(?:fatal|error):", log), log
