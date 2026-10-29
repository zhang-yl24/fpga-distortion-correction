"""CPU-only contracts for the actual rowpipe board-top control runner."""
from pathlib import Path
import json
import sys

import pytest

_import_path = list(sys.path)
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    import run_board1080_rowpipe_control_sim as runner
finally:
    sys.path[:] = _import_path


def test_runner_targets_actual_rowpipe_top_and_not_legacy_top():
    assert runner.COMPILE[1] == "board/board1080_rowpipe_top.v"
    assert "board/board1080_top.v" not in runner.COMPILE
    assert runner.TOP == "tb_board1080_control"
    assert runner.HEADER == "board/board1080-synthetic.vh"


def test_real_stub_headers_bind_and_production_bodies_are_not_compiled():
    headers = runner.bound_headers()
    assert set(headers) == runner.EXPECTED_STUBS
    assert all(item["ProductionBodyCompiled"] is False for item in headers.values())
    assert headers["hdmi1080_video_system"]["RelativePath"] == \
        "rtl/experimental/hdmi1080_video_system_cdc_reset.v"


def test_compile_closure_keeps_actual_top_and_stages_its_relative_header(tmp_path):
    compiled, relocated, staged = runner.prepare_sources(runner.ROOT, tmp_path)
    assert compiled[1] == runner.ROOT / runner.COMPILE[1]
    assert runner.COMPILE[1] not in relocated
    assert Path(staged["Path"]).read_bytes() == (runner.ROOT / runner.HEADER).read_bytes()
    runner.verify_compile_sources(runner.ROOT, runner.COMPILE, (runner.HEADER,), tmp_path, relocated)


def test_swapped_top_include_is_outside_compile_closure(tmp_path):
    project, work = tmp_path / "project", tmp_path / "work"
    top = project / runner.COMPILE[1]
    top.parent.mkdir(parents=True)
    top.write_text('`include "board/other.vh"\n', encoding="ascii")
    work.mkdir()
    with pytest.raises(ValueError, match="bound synthetic header"):
        runner.prepare_sources(project, work)


def test_missing_bound_stub_header_rejected(tmp_path):
    stub = tmp_path / runner.COMPILE[0]
    stub.parent.mkdir(parents=True)
    stub.write_text('// HEADER_BINDING {"Module":"cfg_pll","Path":"missing.v","HeaderSHA256":"'
                    + "0" * 64 + '"}\n', encoding="ascii")
    with pytest.raises(ValueError, match="missing or outside"):
        runner.bound_headers(tmp_path)


def test_result_contract_rejects_actual_datapath_claim(tmp_path):
    (tmp_path / "summary.json").write_text(json.dumps({
        "passed": True, "test_only_stubs": True,
        "startup_missing_qualifiers_blocked": 7,
        "runtime_fault_cases": 6, "first_fault_sticky_cases": 6,
        "held_stub_aw_routing_cases": 6, "common_reset_cases": 6,
        "cold_power_delay_reference_cycles": 1000000,
        "actual_system_datapath_verified": True,
        "actual_fifo_verified": False,
        "physical_ddr_or_pll_or_iic_verified": False,
        "clock_stop_recovery_verified": False,
    }), encoding="ascii")
    (tmp_path / "control-events.csv").write_text(
        "event,case\n", encoding="ascii")
    with pytest.raises(ValueError, match="control coverage"):
        runner.validate_results(tmp_path)


def test_result_contract_requires_seven_startup_and_six_runtime_cases(tmp_path):
    (tmp_path / "summary.json").write_text(json.dumps({
        "passed": True, "test_only_stubs": True,
        "startup_missing_qualifiers_blocked": 7,
        "runtime_fault_cases": 6, "first_fault_sticky_cases": 6,
        "held_stub_aw_routing_cases": 6, "common_reset_cases": 6,
        "cold_power_delay_reference_cycles": 1000000,
        "actual_system_datapath_verified": False,
        "actual_fifo_verified": False,
        "physical_ddr_or_pll_or_iic_verified": False,
        "clock_stop_recovery_verified": False,
    }), encoding="ascii")
    (tmp_path / "control-events.csv").write_text(
        "event,case\nruntime_fault_quarantined,1\n", encoding="ascii")
    with pytest.raises(ValueError, match="seven startup"):
        runner.validate_results(tmp_path)
