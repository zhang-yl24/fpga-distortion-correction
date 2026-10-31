"""Source-substitution and frozen-role checks for the independent output recipe."""
from pathlib import Path
import json
import shutil
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_processed_output as output


REAL_PROJECT = output.PROJECT


@pytest.fixture
def candidate(tmp_path_factory, monkeypatch):
    # Keep the vendor's long leaf names below the native Windows MAX_PATH
    # boundary, as in the real short build/processed-output recipe directory.
    project = tmp_path_factory.mktemp("po") / "distortion"
    base = json.loads((REAL_PROJECT / output.BASE).read_text(encoding="utf-8-sig"))
    names = set(base["source_files"]) | set(output.ADDED) | {
        output.BASE, output.FDC, base["RouteConstraint"],
        "tools/prepare_processed_output.py", "tools/prepare_board1080_timing.py"}
    for name in names:
        destination = project / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REAL_PROJECT / name, destination)
    monkeypatch.setattr(output, "PROJECT", project)
    monkeypatch.setattr(output, "SELF", project / "tools/prepare_processed_output.py")
    return project


def frozen(project):
    return output.freeze_manifest(project)


def test_real_derivation_owns_exact_pins_and_complete_ddr():
    base = output.base_manifest(REAL_PROJECT)
    names = output.derived_names(base)
    assert not output.REMOVED & set(names)
    assert output.FDC in names
    assert set(output.ADDED) <= set(names)
    audit = output.audit_constraint(REAL_PROJECT, (REAL_PROJECT / output.FDC).read_bytes(), base)
    assert audit["PackagePins"] == 114
    assert audit["DDRPins"] == 71
    assert audit["RemovedRXInputPins"] == 28
    assert audit["TXSCLAndSDAInout"]
    assert not audit["ExternalIOAccepted"]


def test_freeze_never_inherits_old_role_count_or_physical_pass(candidate):
    manifest = frozen(candidate)
    roles = output.validate(candidate)
    assert len(manifest["source_files"]) == len(output.derived_names(output.base_manifest(candidate)))
    assert len(manifest["source_files"]) != 109
    assert len(roles["IDFExpandedSources"]) == 74
    assert len(roles["Headers"]) == 4
    assert not set(roles["ExplicitDesigns"]) & set(roles["IDFExpandedSources"])
    assert all(manifest[flag] is False for flag in output.FALSE_FLAGS)
    assert manifest["DDRBodyComparison"]["EquivalentAfterCRLFNormalization"]


def test_freeze_rejects_missing_new_source_without_manifest(candidate):
    (candidate / output.PATTERN).unlink()
    with pytest.raises(ValueError, match="missing or escaped"):
        frozen(candidate)
    assert not (candidate / output.MANIFEST).exists()


def test_source_hash_drift_is_rejected(candidate):
    frozen(candidate)
    path = candidate / output.PATTERN
    path.write_bytes(path.read_bytes() + b"\n// changed candidate\n")
    with pytest.raises(ValueError, match="candidate source hash mismatch"):
        output.validate(candidate)


def test_manifest_cannot_add_unrelated_rtl(candidate):
    manifest = frozen(candidate)
    manifest["source_files"].append("board/unrelated.v")
    manifest["SourceSHA256"]["board/unrelated.v"] = "0" * 64
    with pytest.raises(ValueError, match="candidate derivation differs"):
        output.validate(candidate, manifest=manifest)


@pytest.mark.parametrize("flag", output.FALSE_FLAGS)
def test_manifest_cannot_assert_release(candidate, flag):
    manifest = frozen(candidate)
    manifest[flag] = True
    with pytest.raises(ValueError, match="cannot assert physical"):
        output.validate(candidate, manifest=manifest)


def test_even_rehashed_constraint_substitution_is_rejected(candidate):
    manifest = frozen(candidate)
    path = candidate / output.FDC
    path.write_bytes(path.read_bytes().replace(b"{p:pix_clk} {PAP_IO_LOC} {T24}", b"{p:pix_clk} {PAP_IO_LOC} {T23}"))
    manifest["SourceSHA256"][output.FDC] = output.paths.sha(path)
    with pytest.raises(ValueError, match="outside exact derivation"):
        output.validate(candidate, manifest=manifest)


def test_even_rehashed_tx_include_cannot_escape_closure(candidate):
    manifest = frozen(candidate)
    path = candidate / "board/hdmi_tx_init.v"
    path.write_bytes(path.read_bytes().replace(b"D:/English/FPGA/distortion/board/ms7210_commands.vh", b"C:/other/table.vh"))
    manifest["SourceSHA256"]["board/hdmi_tx_init.v"] = output.paths.sha(path)
    with pytest.raises(ValueError, match="unexpected/missing exact include"):
        output.validate(candidate, manifest=manifest)


def test_even_rehashed_header_cannot_hide_nested_include(candidate):
    manifest = frozen(candidate)
    path = candidate / "board/ms7210_commands.vh"
    path.write_bytes(path.read_bytes() + b'\n`include "other.vh"\n')
    manifest["SourceSHA256"]["board/ms7210_commands.vh"] = output.paths.sha(path)
    with pytest.raises(ValueError, match="unexpected/missing exact include"):
        output.validate(candidate, manifest=manifest)


def test_top_direction_must_match_real_bidirectional_tx(candidate):
    path = candidate / output.TOP
    path.write_bytes(path.read_bytes().replace(b"inout hd_scl,hd_sda", b"output hd_scl,hd_sda"))
    with pytest.raises(ValueError, match="direction mismatch"):
        frozen(candidate)


def test_ddr_apb_tieoff_edit_cannot_be_rehashed(candidate):
    path = candidate / output.TOP
    path.write_bytes(path.read_bytes().replace(b".apb_enable(1'b0)", b".apb_enable(1'b1)"))
    with pytest.raises(ValueError, match="changed DDR wiring/APB"):
        frozen(candidate)


@pytest.mark.parametrize("alias", ["P:/", "direct"])
def test_preparation_snapshots_all_inputs_and_has_no_eda_side_effect(candidate, monkeypatch, alias):
    frozen(candidate)
    work = candidate / "build/processed-output/unit-a"
    work.mkdir(parents=True)
    fake_tool = candidate / "fake-pds.exe"
    fake_tool.write_bytes(b"This is not executable and must not be run")
    monkeypatch.setattr(output.paths, "validate_repo_alias", lambda project, alias: "P:/")
    before = {path: path.read_bytes() for path in candidate.rglob("*") if path.is_file()}
    plan = output.prepare(candidate, work, pds_shell=fake_tool, maximum_seconds=240, repo_alias=alias)
    assert not plan["EDAExecuted"] and not plan["HardwareAccessed"] and not plan["BitstreamRequested"]
    assert plan["ExternalDeadlineRequired"] and plan["MaximumSecondsForExternalExecutor"] == 240
    assert all(plan[flag] is False for flag in output.FALSE_FLAGS)
    for path, data in before.items():
        assert path.read_bytes() == data
    tcl = (work / "timing.tcl").read_text()
    assert "compile -top_module processed_output_top" in tcl
    assert "generate_bitstream" not in tcl and "_N173" not in tcl
    assert len([line for line in tcl.splitlines() if line.startswith("add_design ")]) == len(plan["ExplicitDesigns"])
    assert all(name not in tcl for name in plan["IDFExpandedSourcesNotAdded"])
    for binding in plan["CompiledInputs"]:
        source = binding["Source"]
        original = (candidate / source).read_bytes()
        compiled = (work / "compiled" / source).read_bytes()
        assert output.paths.sha_bytes(original) == binding["OriginalSHA256"]
        assert output.paths.sha_bytes(compiled) == binding["CompiledSHA256"]
        if source in output.INCLUDES:
            old, _ = output.INCLUDES[source]
            replacement = next(row["CompiledInclude"] for row in plan["IncludeRewrites"] if row["Source"] == source)
            assert compiled == original.replace(old.encode(), replacement.encode(), 1)
        else:
            assert compiled == original
    assert (work / "compiled" / output.FDC).read_bytes() == (candidate / output.FDC).read_bytes()
    assert (work / "compiled" / plan["Constraints"]["RCF"]).is_file()
    snapshot = (work / "plan.json").read_bytes()
    with pytest.raises(ValueError, match="fresh existing"):
        output.prepare(candidate, work, pds_shell=fake_tool, repo_alias=alias)
    assert (work / "plan.json").read_bytes() == snapshot


@pytest.mark.parametrize("deadline", [0, 59, 7201, True])
def test_invalid_external_deadline_fails_before_output(tmp_path, deadline):
    with pytest.raises(ValueError, match="deadline"):
        output.prepare(tmp_path / "missing", tmp_path / "work", maximum_seconds=deadline)
    assert not (tmp_path / "work").exists()


def test_freeze_is_exclusive(candidate):
    frozen(candidate)
    before = (candidate / output.MANIFEST).read_bytes()
    with pytest.raises(FileExistsError):
        frozen(candidate)
    assert (candidate / output.MANIFEST).read_bytes() == before


def test_direct_recipe_path_rejects_workspace_escape_and_tcl_specials(tmp_path):
    project = tmp_path / "repo" / "distortion"
    with pytest.raises(ValueError, match="escaped repository"):
        output.recipe_path(project, "direct", tmp_path / "outside")
    with pytest.raises(ValueError, match="unsafe Tcl path"):
        output.recipe_path(project, "direct", project / "bad path")
