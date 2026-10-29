"""CPU-only preparation contracts; fixtures contain no vendor IP or EDA run."""
from pathlib import Path
import json
import re
import sys
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_board1080_timing as timing


@pytest.fixture
def closure(tmp_path, monkeypatch):
    project = tmp_path / "distortion"
    project.mkdir()
    bodies = [timing.IP + f"/rtl/hash_only_{i}.vp" for i in range(71)]
    bodies += [timing.IP + f"/wrapper_{i}.v" for i in range(3)]
    designs = sorted(timing.REQUIRED_DESIGNS)
    designs += [f"rtl/independent_{i}.v" for i in range(30 - len(designs))]
    names = designs + [timing.IDF] + bodies + sorted(timing.HEADERS) + ["board/diagnostic.fdc"]
    for name in names:
        path = project / name
        path.parent.mkdir(parents=True, exist_ok=True)
        # Deliberately non-UTF8 comments ensure preparation preserves bytes.
        data = b"// SYNTHETIC CPU FIXTURE \xb2\xe2\n"
        if name in timing.INCLUDE_BINDINGS:
            include, _ = timing.INCLUDE_BINDINGS[name]
            data += b'    `include "' + include.encode("ascii") + b'"\n'
        path.write_bytes(data)
    root = ET.Element("ip_inst")
    file_list = ET.SubElement(root, "file_list")
    source = ET.SubElement(file_list, "source")
    for name in bodies:
        ET.SubElement(source, "file", pathname=name[len(timing.IP) + 1:])
    # A simulation output is deliberately not a synthesis dependency.
    output = ET.SubElement(file_list, "output")
    ET.SubElement(output, "file", pathname="sim_lib/not_a_synthesis_source.v")
    ET.ElementTree(root).write(project / timing.IDF, encoding="utf-8")
    rcf = project / "board/priority.rcf"
    rcf.write_bytes(b"# SYNTHETIC RCF\n")
    manifest = {"Target": "board1080_top", "source_files": names,
                "Constraint": "board/diagnostic.fdc", "RouteConstraint": "board/priority.rcf"}
    manifest_path = project / timing.DEFAULT_MANIFEST

    def bind():
        manifest["SourceSHA256"] = {name: timing.sha(project / name) for name in manifest["source_files"]}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    bind()
    script = project / "tools/prepare_board1080_timing.py"
    script.parent.mkdir()
    script.write_bytes(b"# synthetic preparer identity\n")
    monkeypatch.setattr(timing, "SELF", script)
    work = project / "build/board1080-timing/fresh-a"
    work.mkdir(parents=True)
    tool = tmp_path / "pds_shell.exe"
    tool.write_bytes(b"synthetic executable identity; never run")
    return project, manifest, bind, work, tool


def test_real_manifest_has_exact_idf_and_design_roles():
    roles = timing.validate_manifest(timing.PROJECT)
    assert len(roles["Sources"]) == 109
    assert len(roles["ExplicitDesigns"]) == 31
    assert len(roles["IDFExpandedSources"]) == 74
    assert set(roles["ExplicitDesigns"]).isdisjoint(roles["IDFExpandedSources"])
    assert roles["Headers"] == sorted(timing.HEADERS)
    assert roles["RouteConstraint"] in roles["ConstraintSHA256"]


def test_preparation_freezes_bytes_and_builds_roles_without_running_tool(closure, monkeypatch):
    project, manifest, _, work, tool = closure
    monkeypatch.setattr(timing, "validate_repo_alias", lambda project, alias: timing.alias_format(alias))
    original = {name: (project / name).read_bytes() for name in manifest["source_files"]}
    plan = timing.prepare(project, work, pds_shell=tool)
    assert plan["EDAExecuted"] is False
    assert plan["BitstreamRequested"] is False
    assert plan["PDS"]["VersionVerifiedByPreparation"] is False
    assert plan["PDS"]["ExecutableSHA256"] == timing.sha(tool)
    assert len(plan["ExplicitDesigns"]) == 31
    assert all(path.endswith((".v", ".idf")) for path in plan["ExplicitDesigns"])
    assert sum(path.endswith(".idf") for path in plan["ExplicitDesigns"]) == 1
    assert len(plan["CompiledInputs"]) == 109
    assert len(plan["IncludeRewrites"]) == 5
    for rewrite in plan["IncludeRewrites"]:
        name = rewrite["Source"]
        expected = original[name].replace(rewrite["OriginalInclude"].encode("ascii"),
                                           rewrite["CompiledInclude"].encode("ascii"), 1)
        assert (work / "compiled" / name).read_bytes() == expected
        assert rewrite["HeaderSHA256"] == timing.sha(project / rewrite["Header"])
        assert rewrite["CompiledInclude"].startswith("P:/distortion/build/board1080-timing/fresh-a/compiled/")
    assert all((project / name).read_bytes() == content for name, content in original.items())
    for record in plan["CompiledInputs"]:
        assert record["CompiledSHA256"] == timing.sha(work / "compiled" / record["Source"])
    assert timing.DEFAULT_MANIFEST in plan["InputSHA256"]
    assert "tools/prepare_board1080_timing.py" in plan["InputSHA256"]
    assert manifest["RouteConstraint"] in plan["InputSHA256"]
    assert "ShareRouterControlSignal" not in plan
    assert "HDLAndConstraintInputsUnchangedByRouteOption" not in plan
    tcl = (work / "timing.tcl").read_text(encoding="ascii")
    assert tcl.count("\nadd_design ") == 31
    assert "add_design {P:/distortion/build/board1080-timing/fresh-a/compiled/" + timing.IDF + "}" in tcl
    assert tcl.index("dev_map") < tcl.index("add_constraint {P:/distortion/board/priority.rcf}") < tcl.index("pnr -")
    assert tcl.index("pnr -") < tcl.index("file copy ") < tcl.index("report_timing -")
    assert "-share_router_control_signal" not in tcl
    assert plan["EDAStageCommands"][3] == "pnr -optimize_multi_corner_timing -fix_hold_violation"
    assert "gen_bit_stream" not in tcl
    assert timing.sha(work / "timing.tcl") == plan["Tcl"]["SHA256"]
    assert json.loads((work / "plan.json").read_text(encoding="utf-8"))["ExplicitDesigns"] == plan["ExplicitDesigns"]
    with pytest.raises(ValueError, match="fresh existing child"):
        timing.prepare(project, work, pds_shell=tool)


@pytest.mark.parametrize("mutation, message", [
    ("duplicate", "unique 109-file"),
    ("hash", "SHA256 mismatch"),
    ("hash_key", "unique 109-file"),
    ("path", "unsafe project-relative path"),
    ("idf_body", "complete IDF"),
    ("role", "30 independent Verilog"),
    ("header", "three bound"),
    ("include", "bound include"),
])
def test_bad_closures_fail_before_any_output(closure, mutation, message):
    project, manifest, bind, work, tool = closure
    names = manifest["source_files"]
    if mutation == "duplicate":
        names[-1] = names[0].upper()
    elif mutation == "hash":
        (project / names[0]).write_bytes(b"changed after binding")
    elif mutation == "hash_key":
        manifest["SourceSHA256"]["extra.v"] = "0" * 64
    elif mutation in ("path", "idf_body", "role", "header"):
        if mutation == "path":
            old, new = names[0], "../escape.v"
            # Do not bind through an escaping path; use a forged manifest hash.
            names[names.index(old)] = new
            manifest["SourceSHA256"][new] = manifest["SourceSHA256"].pop(old)
        else:
            if mutation == "idf_body":
                old, new = timing.IP + "/rtl/hash_only_0.vp", "rtl/unowned.vp"
            elif mutation == "role":
                old, new = "rtl/independent_0.v", "rtl/unowned.sv"
            else:
                old, new = "rtl/video_crc32.vh", "rtl/unbound_header.vh"
            names[names.index(old)] = new
            (project / new).write_bytes((project / old).read_bytes())
            bind()
    elif mutation == "include":
        name = "rtl/ddr_video_reader.v"
        (project / name).write_bytes(b'`include "D:/outside/unbound.vh"\n')
        bind()
    (project / timing.DEFAULT_MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        timing.prepare(project, work, pds_shell=tool)
    assert not list(work.iterdir())


def test_idf_path_escape_is_rejected(closure):
    project, _, bind, _, _ = closure
    path = project / timing.IDF
    root = ET.parse(path)
    root.getroot().find("file_list/source/file").set("pathname", "../escaped.vp")
    root.write(path, encoding="utf-8")
    bind()
    with pytest.raises(ValueError, match="unsafe project-relative"):
        timing.validate_manifest(project)


def test_snapshot_copy_is_inside_exact_final_database_existence_guard():
    work = "P:/distortion/build/board1080-timing/fresh-a"
    source, snapshot = work + "/place_route/board1080_top_pnr.adf", work + "/pre-sta-final.adf"
    tcl = timing.make_tcl([], "P:/distortion/board/a.fdc", "P:/distortion/board/a.rcf", work, snapshot)
    guarded = ("if {[file exists {" + source + "}]} {\n"
               "    file copy {" + source + "} {" + snapshot + "}\n}")
    assert tcl.count(guarded) == 1
    assert len(re.findall(r"(?m)^\s*file copy ", tcl)) == 1
    assert not re.search(r"(?m)^file copy ", tcl)
    assert tcl.index("pnr -") < tcl.index(guarded) < tcl.index("report_timing -")


def test_optional_200ps_hold_target_adds_only_one_stage_and_preserves_constraints():
    work = "P:/distortion/build/board1080-timing/fresh-a"
    arguments = (["P:/distortion/compiled/top.v"], "P:/distortion/board/a.fdc",
                 "P:/distortion/board/a.rcf", work, work + "/pre-sta-final.adf")
    original = timing.make_tcl(*arguments)
    assert timing.make_tcl(*arguments, clock_tree_hold_target_ps=None) == original
    enhanced = timing.make_tcl(*arguments, clock_tree_hold_target_ps=200)
    command = ("route_optimize -force_to_run -fix_hold_violation_in_route TRUE "
               "-fix_hold_violation_threshold_for_clk_tree 200")
    assert enhanced.count(command) == 1
    assert enhanced.replace(command + "\n", "", 1) == original
    assert enhanced.index("pnr -") < enhanced.index(command) < enhanced.index("if {[file exists")
    assert "-input_db_file" not in enhanced and "seed" not in enhanced
    assert "create_clock" not in enhanced and "create_generated_clock" not in enhanced


def test_optional_hold_target_is_bound_in_plan_without_source_or_constraint_edits(closure, monkeypatch):
    project, manifest, _, work, tool = closure
    monkeypatch.setattr(timing, "validate_repo_alias", lambda project, alias: timing.alias_format(alias))
    before = {name: timing.sha(project / name) for name in manifest["source_files"]}
    rcf_before = timing.sha(project / manifest["RouteConstraint"])
    plan = timing.prepare(project, work, pds_shell=tool, clock_tree_hold_target_ps=200)
    command = timing.post_pnr_hold_command(200)
    assert plan["ExplicitPostPNRHoldFixTarget200"] is True
    assert plan["ClockTreeHoldTargetPS"] == 200
    assert plan["ExplicitPostPNRHoldFixCommand"] == command
    assert plan["EDAStageCommands"][4] == command
    assert plan["HDLAndConstraintInputsUnchangedByHoldOption"] is True
    assert all(timing.sha(project / name) == digest for name, digest in before.items())
    assert timing.sha(project / manifest["RouteConstraint"]) == rcf_before
    assert plan["EDAExecuted"] is False


def test_optional_hold_target_rejects_other_values_before_preparing(closure):
    project, _, _, work, tool = closure
    for value in (True, 0, 100, 201, "200", 200.0):
        with pytest.raises(ValueError, match="exactly 200"):
            timing.prepare(project, work, pds_shell=tool, clock_tree_hold_target_ps=value)
    assert not list(work.iterdir())


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("hold_target", [None, 200])
def test_explicit_control_chain_option_changes_only_pnr_line(enabled, hold_target):
    work = "P:/distortion/build/board1080-timing/fresh-a"
    args = ([], "P:/distortion/board/a.fdc", "P:/distortion/board/a.rcf", work, work + "/pre-sta-final.adf")
    baseline = timing.make_tcl(*args, clock_tree_hold_target_ps=hold_target)
    assert baseline == timing.make_tcl(*args, clock_tree_hold_target_ps=hold_target,
                                       share_router_control_signal=None)
    explicit = timing.make_tcl(*args, clock_tree_hold_target_ps=hold_target,
                               share_router_control_signal=enabled)
    suffix = " -share_router_control_signal " + ("TRUE" if enabled else "FALSE")
    assert explicit.count(suffix) == 1
    assert explicit.replace(suffix, "", 1) == baseline
    assert next(line for line in explicit.splitlines() if line.startswith("pnr ")) == timing.pnr_command(enabled)


@pytest.mark.parametrize("enabled", [False, True])
def test_control_chain_option_is_bound_in_generated_tcl_and_plan_without_input_edits(closure, monkeypatch, enabled):
    project, manifest, _, work, tool = closure
    monkeypatch.setattr(timing, "validate_repo_alias", lambda project, alias: timing.alias_format(alias))
    before = {name: timing.sha(project / name) for name in manifest["source_files"]}
    rcf_before = timing.sha(project / manifest["RouteConstraint"])
    plan = timing.prepare(project, work, pds_shell=tool, share_router_control_signal=enabled)
    tcl = (work / "timing.tcl").read_bytes()
    command = timing.pnr_command(enabled)
    assert plan["ShareRouterControlSignal"] is enabled
    assert plan["EDAStageCommands"][3] == command
    assert tcl.splitlines().count(command.encode("ascii")) == 1
    assert plan["HDLAndConstraintInputsUnchangedByRouteOption"] is True
    assert plan["ClockTreeHoldTargetPS"] is None and plan["ExplicitPostPNRHoldFixCommand"] is None
    assert b"route_optimize" not in tcl
    assert plan["Tcl"]["SHA256"] == timing.sha_bytes(tcl)
    assert plan["InputSHA256"]["tools/prepare_board1080_timing.py"] == timing.sha(timing.SELF)
    assert plan["PDS"]["ExecutableSHA256"] == timing.sha(tool)
    assert plan["Device"] == {"Family": "Logos2", "Device": "PG2L100H", "Speedgrade": "-6", "Package": "FBG676"}
    assert all(timing.sha(project / name) == digest for name, digest in before.items())
    assert timing.sha(project / manifest["RouteConstraint"]) == rcf_before
    assert all(plan["InputSHA256"][name] == digest for name, digest in before.items())
    assert plan["EDAExecuted"] is False and plan["HardwareReleaseAllowed"] is False
    assert json.loads((work / "plan.json").read_text())["ShareRouterControlSignal"] is enabled


def test_invalid_control_chain_option_rejected_before_output(closure):
    project, _, _, work, tool = closure
    for value in (0, 1, 0., 1., "false", "TRUE", [], {}):
        with pytest.raises(ValueError, match="explicit boolean"):
            timing.prepare(project, work, pds_shell=tool, share_router_control_signal=value)
    assert not list(work.iterdir())


@pytest.mark.parametrize("flag, expected", [(None, None), ("false", False), ("true", True)])
def test_cli_forwards_only_explicit_control_chain_setting(tmp_path, monkeypatch, flag, expected):
    seen = []
    def prepare(project, work, **options):
        seen.append(options)
        return {"WorkDirectory": str(work), "ExplicitDesigns": []}
    monkeypatch.setattr(timing, "prepare", prepare)
    args = ["--work-dir", str(tmp_path)]
    if flag is not None:
        args += ["--share-router-control-signal", flag]
    assert timing.main(args) == 0
    assert seen[0]["share_router_control_signal"] is expected
    assert seen[0]["clock_tree_hold_target_ps"] is None


def test_guard_skips_pds_preparse_and_copies_once_when_database_exists():
    # Use an in-process Tcl interpreter, with every PDS command and file
    # operation replaced by local callbacks; no EDA/process/disk access.
    tk = pytest.importorskip("tkinter")
    try:
        interpreter = tk.Tcl()
    except tk.TclError as exc:
        pytest.skip(f"Tcl runtime unavailable: {exc}")
    work = "P:/distortion/build/board1080-timing/fresh-a"
    source, snapshot = work + "/place_route/board1080_top_pnr.adf", work + "/pre-sta-final.adf"
    tcl = timing.make_tcl([], "P:/distortion/board/a.fdc", "P:/distortion/board/a.rcf", work, snapshot)
    available, copies = False, []

    def file_operation(operation, *args):
        if operation == "exists":
            assert args == (source,)
            return "1" if available else "0"
        assert operation == "copy" and args == (source, snapshot)
        copies.append(args)
        return ""

    interpreter.eval("rename file original_file")
    interpreter.createcommand("file", file_operation)
    for command in ("set_arch", "add_constraint", "compile", "synthesize", "dev_map", "pnr", "report_timing"):
        interpreter.createcommand(command, lambda *args: "")
    interpreter.eval(tcl)
    assert copies == []  # Initial PDS parse: the final database does not exist.
    available = True
    interpreter.eval(tcl)
    assert copies == [(source, snapshot)]  # Runtime after PNR: one exact snapshot.


@pytest.mark.parametrize("directive", [b'`include "../unbound.vh"\n', b'`include UNBOUND_MACRO\n'])
def test_header_cannot_add_an_unbound_nested_include(closure, directive):
    project, _, bind, _, _ = closure
    (project / "rtl/video_crc32.vh").write_bytes(directive)
    bind()
    with pytest.raises(ValueError, match="bound include"):
        timing.validate_manifest(project)


@pytest.mark.parametrize("path", ["P:/bad{path}", "P:/bad}path", "P:/bad\npath", "P:/bad;path",
                                   "P:/bad$path", "P:/bad[path]", "P:/bad\\path", "P:/../escape"])
def test_tcl_paths_reject_injection_and_traversal(path):
    with pytest.raises(ValueError, match="unsafe Tcl path"):
        timing.tcl_path(path)


@pytest.mark.parametrize("alias", ["P:/nested", "P:\\", "PP:/", "P:/\n", "1:/"])
def test_alias_format_is_one_drive_root(alias):
    with pytest.raises(ValueError, match="ASCII drive root"):
        timing.alias_format(alias)


def test_alias_must_resolve_to_this_repository(closure, monkeypatch):
    project, _, _, _, _ = closure
    monkeypatch.setattr(Path, "samefile", lambda self, other: False)
    with pytest.raises(ValueError, match="exact repository"):
        timing.validate_repo_alias(project, "P:/")


@pytest.mark.parametrize("kind", ["nonempty", "missing", "outside", "root"])
def test_work_directory_must_be_existing_empty_and_scoped(closure, kind):
    project, _, _, work, _ = closure
    if kind == "nonempty":
        (work / "stale.adf").write_bytes(b"stale")
    elif kind == "missing":
        work = work.parent / "not-created"
    elif kind == "outside":
        work = project.parent / "outside-build"
        work.mkdir()
    else:
        work = work.parent
    with pytest.raises(ValueError, match="fresh existing child"):
        timing.fresh_work_dir(project, work)
