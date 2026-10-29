"""CPU-only checked-build preparation; no external processes or vendor decoding."""
from pathlib import Path
import json
import shutil
import sys
import tempfile
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_board1080_checked as tool


@pytest.fixture
def project():
    # Copy bound files as opaque bytes. This exercises real validation guards,
    # unlike replacing validated role functions with synthetic accept-all ones.
    # Full vendor dependency names approach MAX_PATH after compiled/ staging.
    # Keep this disposable CPU fixture short without mapping any drive.
    temporary = tempfile.TemporaryDirectory(prefix="chk-")
    root = Path(temporary.name) / "distortion"
    roles = tool.validate_profile()
    base = tool.selection.hdmi30.validate_profile(tool.PROJECT)
    names = set(tool.expected_inputs(tool.PROJECT, roles)) | set(base["Sources"])
    names |= set(tool.selection.REPLACEMENTS) | set(base["AuxiliarySHA256"])
    names.add(tool.selection.hdmi30.ORIGINAL)
    for name in names:
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(tool.PROJECT / name, destination)
    try:
        yield root
    finally:
        temporary.cleanup()


def test_real_checked_roles_change_only_exact_scl_direction():
    roles = tool.validate_profile()
    source = tool.selection.validate_profile()
    assert len(roles["Sources"]) == 109 and len(roles["ExplicitDesigns"]) == 31
    assert len(roles["IDFExpandedSources"]) == 74 and len(roles["Headers"]) == 3
    assert set(roles["Sources"]) - set(source["source_files"]) == {tool.FDC}
    assert set(source["source_files"]) - set(roles["Sources"]) == {tool.BASE_FDC}
    assert (tool.PROJECT / tool.FDC).read_bytes() == tool.render_fdc()
    with pytest.raises(ValueError):
        tool.timing.validate_manifest(tool.PROJECT, tool.MANIFEST)


def test_cpu_preparation_stages_all_bound_bytes_and_never_executes_tool(project, tmp_path, monkeypatch):
    work = project / "build/board1080-timing/checked-cpu"
    work.mkdir(parents=True)
    executable = tmp_path / "pds_shell.exe"
    executable.write_bytes(b"SYNTHETIC EXECUTABLE IDENTITY; NEVER EXECUTE")
    # Only filesystem drive availability is replaced for a CPU fixture.
    # No profile/role validator is patched or bypassed.
    monkeypatch.setattr(tool, "validate_repo_alias", lambda project, alias: tool.timing.alias_format(alias))
    plan = tool.prepare(project, work, pds_shell=executable)
    assert plan["Schema"] == tool.SCHEMA and plan["EDAStageCommands"] == list(tool.STAGES)
    assert plan["EDAExecuted"] is plan["TimingAccepted"] is plan["HardwareReleaseAllowed"] is False
    assert plan["CheckedI2CProfileVerified"] and plan["SCLDirectionOnlyConstraintChange"]
    assert len(plan["CompiledInputs"]) == 109 and len(plan["ExplicitDesigns"]) == 31
    assert len(plan["IncludeRewrites"]) == 5
    assert "board/board1080_checked_top.v" in {r["Source"] for r in plan["IncludeRewrites"]}
    assert set(plan["InputSHA256"]) == set(tool.expected_inputs(project, tool.validate_profile(project)))
    for row in plan["CompiledInputs"]:
        assert tool.sha(work / "compiled" / row["Source"]) == row["CompiledSHA256"]
        assert tool.sha(project / row["Source"]) == row["OriginalSHA256"]
    for row in plan["IncludeRewrites"]:
        original = (project / row["Source"]).read_bytes()
        expected = original.replace(row["OriginalInclude"].encode(), row["CompiledInclude"].encode(), 1)
        assert (work / "compiled" / row["Source"]).read_bytes() == expected
    tcl = (work / "timing.tcl").read_text()
    assert tcl.count("\nadd_design ") == 31
    assert "add_constraint {P:/distortion/" + tool.FDC + "}" in tcl
    assert tool.STAGES[4] in tcl and "gen_bitstream" not in tcl
    assert plan["PDS"]["ExecutableSHA256"] == tool.sha(executable)
    assert plan["Tcl"]["SHA256"] == tool.sha(work / "timing.tcl")
    with pytest.raises(ValueError, match="fresh existing"):
        tool.prepare(project, work, pds_shell=executable)


@pytest.mark.parametrize("mutation", ("fdc_extra", "source_drift", "old_top", "duplicate", "escape", "wrong_constraint", "wrong_hash"))
def test_unapproved_profile_changes_fail_before_any_build_write(project, mutation):
    work = project / "build/board1080-timing/checked-reject"
    work.mkdir(parents=True)
    path = project / tool.MANIFEST
    manifest = json.loads(path.read_text())
    if mutation == "fdc_extra":
        with (project / tool.FDC).open("ab") as stream: stream.write(b"\nset_false_path -from [all_registers]\n")
    elif mutation == "source_drift":
        with (project / "rtl/experimental/iic_dri_checked.v").open("ab") as stream: stream.write(b"\n// drift\n")
    elif mutation == "duplicate": manifest["source_files"][1] = manifest["source_files"][0]
    elif mutation == "old_top":
        manifest["source_files"] = ["board/board1080_rowpipe_top.v" if n == "board/board1080_checked_top.v" else n for n in manifest["source_files"]]
    elif mutation == "escape": manifest["source_files"][0] = "../outside.v"
    elif mutation == "wrong_constraint": manifest["Constraint"] = tool.BASE_FDC
    else: manifest["SourceSHA256"][tool.FDC] = "0" * 64
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError): tool.prepare(project, work)
    assert not list(work.iterdir())


@pytest.mark.parametrize("location", ("outside", "wrong_prefix"))
def test_output_location_is_bounded_before_alias_or_tool_use(project, tmp_path, location):
    work = tmp_path / "outside" if location == "outside" else project / "build/board1080-timing/hdmi30-bad"
    work.mkdir(parents=True)
    with pytest.raises(ValueError, match="fresh existing|checked-"):
        tool.prepare(project, work)
    assert not list(work.iterdir())


def test_profile_creation_is_exclusive_and_does_not_change_frozen_selection(project):
    before = tool.sha(project / tool.selection.MANIFEST)
    with pytest.raises(ValueError, match="already exists"): tool.write_profile(project)
    assert tool.sha(project / tool.selection.MANIFEST) == before
