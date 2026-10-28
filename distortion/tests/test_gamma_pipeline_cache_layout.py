"""Fixed cache-selection contracts only; no simulator, PDS or board access."""
from pathlib import Path
import json
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import prepare_gamma_pipeline_d5 as prepared
import run_gamma_pipeline_d5_sim as simulation
import build_gamma_pipeline_d5 as builder


def test_fixed_cache_layout_changes_only_owned_list_and_tcl():
    parity, compact = prepared.expected(), prepared.expected(layout="compact")
    changed = {name for name in parity if parity[name] != compact[name]}
    assert changed == {f"board/{prepared.TARGET}-sources.json", f"board/build-{prepared.TARGET}.tcl"}
    names = json.loads(compact[f"board/{prepared.TARGET}-sources.json"])
    assert len(names) == 123 and len(set(names)) == 123
    assert names.count(prepared.COMPACT) == 1 and prepared.PARITY not in names
    assert names.count(prepared.SERIAL) == 1
    assert prepared.cache_layout(names) == "compact"
    assert prepared.sha(ROOT / prepared.COMPACT) == prepared.COMPACT_SHA256
    contract = prepared.integration_contract("compact")
    assert contract["index_bits"] == 5 and contract["fast_cache_bytes"] == 8192
    assert contract["fallback"] is None and contract["fallback_cache_bytes"] == 0
    assert contract["serial_source_compiled_but_unused"] is True
    assert contract["input_fifo_entries"] == 2
    assert contract["final_timing_required_before_bitstream"] is True
    before = list(simulation.COMPILE)
    verified = {"CacheLayout": "compact", "IntegrationContract": contract,
                "SourceSHA256": dict.fromkeys(names, "not-used-in-this-shape-test")}
    compiled = simulation.compile_sources(verified)
    assert prepared.COMPACT in compiled and prepared.PARITY not in compiled
    assert prepared.SERIAL in compiled and simulation.COMPILE == before
    verified["IntegrationContract"] = prepared.integration_contract("parity")
    with pytest.raises(ValueError):
        simulation.compile_sources(verified)
    for invalid in ([prepared.COMPACT, prepared.PARITY], [prepared.COMPACT] * 2,
                    ["rtl/experimental/arbitrary_cache.v"], [prepared.COMPACT, 1]):
        with pytest.raises(ValueError):
            prepared.cache_layout(invalid)


def test_stage_is_limited_to_two_owned_files(tmp_path, monkeypatch):
    list_name = f"board/{prepared.TARGET}-sources.json"
    tcl_name = f"board/build-{prepared.TARGET}.tcl"
    unchanged = "board/top-and-private-stand-in.v"
    (tmp_path / "board").mkdir()
    files = {list_name: b"parity", tcl_name: b"parity-tcl", unchanged: b"untouched"}
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    monkeypatch.setattr(prepared, "ROOT", tmp_path)
    monkeypatch.setattr(prepared, "verify_clone", lambda _: {"CacheLayout":
                        (tmp_path / list_name).read_text()})
    monkeypatch.setattr(prepared, "expected", lambda _, layout: {
        list_name: layout.encode(), tcl_name: (layout + "-tcl").encode(), unchanged: b"untouched"})
    assert prepared.stage_cache_layout("compact")["CacheLayout"] == "compact"
    assert (tmp_path / unchanged).read_bytes() == files[unchanged]
    assert prepared.stage_cache_layout("compact")["CacheLayout"] == "compact"
    assert prepared.stage_cache_layout("parity")["CacheLayout"] == "parity"
    assert all((tmp_path / name).read_bytes() == data for name, data in files.items())


def test_source_and_simulation_layout_mismatches_fail_closed(tmp_path, monkeypatch):
    original_sha = prepared.sha
    monkeypatch.setattr(prepared, "sha", lambda path: "0" * 64 if path == ROOT / prepared.COMPACT else original_sha(path))
    with pytest.raises(ValueError, match="compact cache source changed"):
        prepared.expected(layout="compact")
    proof = {"Passed": True, "Target": prepared.TARGET, "HardwareAccessed": False,
             "PDSAccessed": False, "SourceSHA256": {}, "SourceSHA256After": {},
             "CacheLayout": "parity", "IntegrationContract": prepared.integration_contract("parity")}
    path = tmp_path / "proof.json"
    path.write_text(json.dumps(proof))
    monkeypatch.setattr(builder, "APPROVED", tmp_path)
    monkeypatch.setattr(builder, "verify_prepared", lambda _: {
        "CacheLayout": "compact", "IntegrationContract": prepared.integration_contract("compact")})
    with pytest.raises(ValueError, match="cache layout/integration contract"):
        builder.validate_simulation(path)
    proof.update(CacheLayout="compact", IntegrationContract=prepared.integration_contract("compact"),
                 CompileSources={prepared.PARITY: "b" * 64})
    path.write_text(json.dumps(proof))
    monkeypatch.setattr(builder, "verify_prepared", lambda _: {
        "CacheLayout": "compact", "IntegrationContract": prepared.integration_contract("compact"),
        "SourceSHA256": {prepared.COMPACT: "b" * 64}})
    with pytest.raises(ValueError, match="compiled cache/source hashes"):
        builder.validate_simulation(path)


def test_pre_bit_tcl_gate_uses_exact_final_summary_before_gen(tmp_path):
    tkinter = pytest.importorskip("tkinter")
    tcl = tkinter.Tcl()
    tcl.setvar("test_work", str(tmp_path))
    tcl.eval("rename pwd original_pwd; proc pwd {} {return $::test_work}; proc gen_bit_stream {} {set ::generated 1}")
    directory = tmp_path / "report_timing"
    directory.mkdir()
    final = directory / f"{prepared.TARGET}.rtr"
    failed = ROOT / "build/offline-20261024/gamma-pipeline-compact5-k320-build-20261026-c/report_timing" / f"{prepared.TARGET}.rtr"
    passed = ROOT / "build/corrected_gamma_d5/report_timing/corrected_gamma_d5.rtr"
    if not failed.is_file() or not passed.is_file():
        pytest.skip("local real CAD reports unavailable; no CAD execution is part of this test")
    gate = prepared.pre_bit_timing_gate()
    recipe = prepared.expected(layout="compact")[f"board/build-{prepared.TARGET}.tcl"].decode()
    assert recipe.index("report_timing -force_to_run") < recipe.index(gate) < recipe.index("\ngen_bit_stream")
    final.write_bytes(failed.read_bytes())
    with pytest.raises(tkinter.TclError, match="refusing bitstream"):
        tcl.eval(gate + "gen_bit_stream")
    assert tcl.eval("info exists generated") == "0"
    final.write_text("A comment says All Constraints Met.\nDesign Summary : Some Constraints Violated.\n")
    with pytest.raises(tkinter.TclError):
        tcl.eval(gate + "gen_bit_stream")
    final.write_bytes(passed.read_bytes())
    tcl.eval(gate + "gen_bit_stream")
    assert tcl.eval("set generated") == "1"
