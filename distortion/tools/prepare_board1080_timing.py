"""Prepare a frozen board1080 PDS timing recipe; never execute EDA or hardware.

The manifest is an evidence closure, not an add_design list. Its IDF owns 74
expanded HDL files. Only the 30 independent Verilog files and the IDF are added
to PDS; headers and constraints have separate roles. Restricted IP bytes are
copied and hashed, never decoded or printed.

PDS evaluates ordinary Tcl during its initial recipe parse, before EDA runs,
then evaluates it again as the flow advances. The guarded ADF snapshot skips
that first pass. Execution receipts must independently check that the snapshot
exists and its SHA256 equals the final routed ADF; absent/mismatched snapshots
must leave the unchanged-across-STA claim false. This preparer cannot make it.
"""
from pathlib import Path, PurePosixPath
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import re
import xml.etree.ElementTree as ET


PROJECT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
DEFAULT_MANIFEST = "board/board1080-rowpipe-sources.json"
IP = "platform/video_base/ipcore/ddr3_test"
IDF = IP + "/ddr3_test.idf"
HEADERS = frozenset(("rtl/video_crc32.vh", "rtl/experimental/gamma_curves.vh",
                     "board/board1080-synthetic.vh"))
INCLUDE_BINDINGS = {
    "rtl/ddr_video_reader.v": ("D:/English/FPGA/distortion/rtl/video_crc32.vh", "rtl/video_crc32.vh"),
    "rtl/experimental/ddr_adaptive_result_writer.v":
        ("D:/English/FPGA/distortion/rtl/video_crc32.vh", "rtl/video_crc32.vh"),
    "rtl/experimental/adaptive_gamma_stream.v":
        ("D:/English/FPGA/distortion/rtl/experimental/gamma_curves.vh", "rtl/experimental/gamma_curves.vh"),
    "rtl/experimental/ddr_video_output_1080_board.v":
        ("D:/English/FPGA/distortion/rtl/video_crc32.vh", "rtl/video_crc32.vh"),
    "board/board1080_rowpipe_top.v": ("board/board1080-synthetic.vh", "board/board1080-synthetic.vh"),
}
REQUIRED_DESIGNS = frozenset((*INCLUDE_BINDINGS,
    "rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v",
    "rtl/experimental/ddr_remap_sample_scatter4_rowpipe.v",
    "rtl/experimental/hdmi1080_video_system_cdc_reset.v"))
FORBIDDEN_DESIGNS = frozenset(("board/board1080_top.v", "board/board1080_cdc_reset_top.v",
    "rtl/experimental/ddr_compact_neighbour_cache_scatter4.v",
    "rtl/experimental/ddr_remap_sample_scatter4.v", "rtl/experimental/hdmi1080_video_system.v"))
INCLUDE = re.compile(rb'(?m)^[ \t]*`include[ \t]+"([^"\r\n]+)"')
INCLUDE_DIRECTIVE = re.compile(rb'(?m)^[ \t]*`include\b')
SHA = re.compile(r"[0-9a-fA-F]{64}\Z")
PDS_VERSION = "2023.2-SP3 build 154097"
ORIGINAL_IP_TOOL_VERSION = "2022.2-SP6.4 build 146967"


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_name(value):
    """Canonical ASCII project-relative paths only, including on POSIX tests."""
    if (not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_./-]+", value)
            or any(part in ("", ".", "..") for part in value.split("/"))
            or PurePosixPath(value).is_absolute()):
        raise ValueError(f"unsafe project-relative path: {value!r}")
    return value


def inside(project, name):
    name = relative_name(name)
    project = Path(project).resolve()
    path = (project / name).resolve()
    if not path.is_relative_to(project) or not path.is_file():
        raise ValueError(f"missing or escaped project file: {name}")
    return path


def tcl_path(value):
    # A fixed ASCII alphabet also excludes braces, substitutions, backslashes,
    # command separators and newline injection. All generated Tcl is braced.
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z]:/[A-Za-z0-9_./-]*", value):
        raise ValueError(f"unsafe Tcl path: {value!r}")
    if any(part in (".", "..") for part in value[3:].split("/")):
        raise ValueError(f"unsafe Tcl path: {value!r}")
    return "{" + value + "}"


def alias_format(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z]:/", value):
        raise ValueError("repo alias must be one ASCII drive root, for example P:/")
    return value[0].upper() + ":/"


def validate_repo_alias(project, value):
    alias = alias_format(value)
    try:
        matches = Path(alias).samefile(Path(project).resolve().parent)
    except OSError as exc:
        raise ValueError(f"repo alias is not an accessible mapping: {alias}") from exc
    if not matches:
        raise ValueError("repo alias must map to this exact repository root")
    return alias


def alias_path(project, alias, path):
    path = Path(path).resolve()
    try:
        relative = path.relative_to(Path(project).resolve().parent).as_posix()
    except ValueError as exc:
        raise ValueError("alias target escaped repository") from exc
    value = alias_format(alias) + relative_name(relative)
    tcl_path(value)
    return value


def fresh_work_dir(project, work_dir):
    root = (Path(project).resolve() / "build/board1080-timing").resolve()
    work = Path(work_dir).resolve()
    if work.parent != root or not work.is_dir() or any(work.iterdir()):
        raise ValueError("work directory must be a fresh existing child of build/board1080-timing")
    # Reject a symlink/junction that turns the intended output tree into a
    # different location, including an aliased build root.
    expected_root = Path(project).resolve() / "build/board1080-timing"
    if root != expected_root or Path(work_dir).absolute() != work:
        raise ValueError("work directory must not traverse symlinks or junctions")
    relative_name(work.name)
    return work


def _bound_hash(value, name):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError(f"missing or invalid SHA256: {name}")
    return value.lower()


def validate_manifest(project, manifest_name=DEFAULT_MANIFEST):
    """Return validated roles and original hashes without modifying files."""
    project = Path(project).resolve()
    manifest_path = inside(project, manifest_name)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    names, hashes = manifest.get("source_files"), manifest.get("SourceSHA256")
    if (not isinstance(names, list) or len(names) != 109
            or any(not isinstance(name, str) for name in names)
            or len(set(name.casefold() for name in names)) != len(names)
            or not isinstance(hashes, dict) or set(hashes) != set(names)):
        raise ValueError("manifest must bind a unique 109-file closure with exactly one SHA256 per source")
    source_hashes = {}
    for name in names:
        path = inside(project, name)
        actual = sha(path)
        if actual != _bound_hash(hashes[name], name):
            raise ValueError(f"source SHA256 mismatch: {name}")
        source_hashes[name] = actual
    if manifest.get("Target") != "board1080_top" or names.count(IDF) != 1:
        raise ValueError("board1080_top and the expected DDR IDF are required")
    source_node = ET.parse(inside(project, IDF)).getroot().find("file_list/source")
    if source_node is None:
        raise ValueError("IDF source/file closure is missing")
    idf_names = [relative_name(element.get("pathname")) for element in source_node.findall("file")]
    if (len(idf_names) != 74 or len(set(n.casefold() for n in idf_names)) != 74
            or Counter(PurePosixPath(n).suffix for n in idf_names) != {".vp": 71, ".v": 3}):
        raise ValueError("IDF source/file must contain exactly 71 VP and 3 Verilog bodies")
    bodies = [IP + "/" + name for name in idf_names]
    if not set(bodies).issubset(names):
        raise ValueError("manifest does not include the complete IDF source/file closure")
    # No unowned VP or extra file under the IP subtree can silently be treated
    # as a separate design. The source/file section, not output/sim_lib, owns it.
    if {n for n in names if n.startswith(IP + "/")} != set(bodies) | {IDF}:
        raise ValueError("manifest contains unowned or missing DDR IP bodies")
    headers = {name for name in names if PurePosixPath(name).suffix == ".vh"}
    if headers != HEADERS:
        raise ValueError("exactly the three bound board1080 headers are required")
    constraint = relative_name(manifest.get("Constraint"))
    route_constraint = relative_name(manifest.get("RouteConstraint"))
    if (PurePosixPath(constraint).suffix != ".fdc" or constraint not in names
            or PurePosixPath(route_constraint).suffix != ".rcf"
            or route_constraint in names):
        raise ValueError("FDC and separate RCF constraint roles are required")
    constraint_hashes = {constraint: sha(inside(project, constraint)),
                         route_constraint: sha(inside(project, route_constraint))}
    explicit = [name for name in names if name not in set(bodies) | headers | {constraint}]
    if (len(explicit) != 31 or Counter(PurePosixPath(n).suffix for n in explicit) != {".v": 30, ".idf": 1}
            or not REQUIRED_DESIGNS.issubset(explicit) or FORBIDDEN_DESIGNS.intersection(names)):
        raise ValueError("expected 30 independent Verilog designs plus IDF, with only rowpipe variants")
    # Check every readable standalone design/header so an unexpected nested or
    # legacy include cannot silently bind a file outside this frozen closure.
    for name in explicit + sorted(headers):
        if name == IDF:
            continue
        data = inside(project, name).read_bytes()
        includes = INCLUDE.findall(data)
        expected = INCLUDE_BINDINGS.get(name)
        if (len(INCLUDE_DIRECTIVE.findall(data)) != len(includes)
                or includes != ([] if expected is None else [expected[0].encode("ascii")])):
            raise ValueError(f"unexpected or missing bound include: {name}")
    auxiliary = {manifest_name: sha(manifest_path)}
    base = manifest.get("BaseManifest")
    if base is not None:
        if not isinstance(base, dict) or not isinstance(base.get("Path"), str) or not base["Path"].startswith("distortion/"):
            raise ValueError("base manifest must be within distortion")
        base_name = relative_name(base["Path"][len("distortion/"):])
        base_hash = sha(inside(project, base_name))
        if base_hash != _bound_hash(base.get("SHA256"), base_name):
            raise ValueError("base manifest SHA256 mismatch")
        auxiliary[base_name] = base_hash
    return {"Manifest": manifest_name, "Sources": names, "SourceSHA256": source_hashes,
            "ExplicitDesigns": explicit, "IDFExpandedSources": bodies,
            "Headers": sorted(headers), "Constraint": constraint, "RouteConstraint": route_constraint,
            "ConstraintSHA256": constraint_hashes, "AuxiliarySHA256": auxiliary}


def post_pnr_hold_command(clock_tree_hold_target_ps):
    if clock_tree_hold_target_ps is None:
        return None
    if type(clock_tree_hold_target_ps) is not int or clock_tree_hold_target_ps != 200:
        raise ValueError("clock-tree hold target must be absent or exactly 200 ps")
    return ("route_optimize -force_to_run -fix_hold_violation_in_route TRUE "
            "-fix_hold_violation_threshold_for_clk_tree 200")


def make_tcl(designs, constraint, route_constraint, work, final_db, clock_tree_hold_target_ps=None):
    hold_command = post_pnr_hold_command(clock_tree_hold_target_ps)
    lines = ["# Generated preparation only; all timing acceptance remains pending.",
             "# No bitstream generation or hardware command is present.",
             "set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676"]
    lines += ["add_design " + tcl_path(path) for path in designs]
    lines += ["add_constraint " + tcl_path(constraint),
              "compile -top_module board1080_top",
              "synthesize -ads -selected_syn_tool_opt 2", "dev_map",
              "add_constraint " + tcl_path(route_constraint),
              "pnr -optimize_multi_corner_timing -fix_hold_violation"]
    if hold_command is not None:
        lines.append(hold_command)
    lines += [
              "if {[file exists " + tcl_path(work + "/place_route/board1080_top_pnr.adf") + "]} {",
              "    file copy " + tcl_path(work + "/place_route/board1080_top_pnr.adf") + " " + tcl_path(final_db),
              "}",
              "report_timing -force_to_run -delay_type min_max -max_path 20"]
    return "\n".join(lines) + "\n"


def prepare(project, work_dir, *, manifest_name=DEFAULT_MANIFEST, repo_alias="P:/",
            pds_shell="D:/pango/PDS_2023.2/bin/pds_shell.exe", clock_tree_hold_target_ps=None):
    hold_command = post_pnr_hold_command(clock_tree_hold_target_ps)
    project = Path(project).resolve()
    roles = validate_manifest(project, manifest_name)
    work = fresh_work_dir(project, work_dir)
    alias = validate_repo_alias(project, repo_alias)
    tool = Path(pds_shell).resolve()
    if not tool.is_file():
        raise ValueError("PDS shell executable must exist; preparation does not run it")
    self_name = SELF.resolve().relative_to(project).as_posix()
    inside(project, self_name)
    roles["AuxiliarySHA256"][self_name] = sha(SELF)
    work_alias = alias_path(project, alias, work)
    compiled_root = work / "compiled"
    rewrites, copies, explicit = [], [], []
    payloads = {}
    for name in roles["Sources"]:
        original = inside(project, name).read_bytes()
        if sha_bytes(original) != roles["SourceSHA256"][name]:
            raise ValueError(f"source changed during preparation: {name}")
        compiled = original
        if name in INCLUDE_BINDINGS:
            expected, header = INCLUDE_BINDINGS[name]
            matches = list(INCLUDE.finditer(original))
            if len(matches) != 1 or matches[0].group(1) != expected.encode("ascii"):
                raise ValueError(f"include changed during preparation: {name}")
            header_alias = alias_path(project, alias, compiled_root / header)
            match = matches[0]
            compiled = original[:match.start(1)] + header_alias.encode("ascii") + original[match.end(1):]
            rewrites.append({"Source": name, "OriginalInclude": expected, "CompiledInclude": header_alias,
                             "Header": header, "HeaderSHA256": roles["SourceSHA256"][header], "ReplacementCount": 1})
        destination = compiled_root / name
        compiled_alias = alias_path(project, alias, destination)
        copies.append({"Source": name, "OriginalSHA256": roles["SourceSHA256"][name],
                       "CompiledPath": compiled_alias, "CompiledSHA256": sha_bytes(compiled)})
        payloads[destination] = compiled
        if name in roles["ExplicitDesigns"]:
            explicit.append(compiled_alias)
    final_db = work_alias + "/pre-sta-final.adf"
    tcl = make_tcl(explicit, alias_path(project, alias, project / roles["Constraint"]),
                   alias_path(project, alias, project / roles["RouteConstraint"]), work_alias, final_db,
                   clock_tree_hold_target_ps)
    tcl_bytes = tcl.encode("ascii")
    # Validate all inputs again before the first write. A preparation failure
    # cannot leave an apparently ready plan based on a partly changed closure.
    input_hashes = {**roles["SourceSHA256"], **roles["ConstraintSHA256"], **roles["AuxiliarySHA256"]}
    for name, digest in input_hashes.items():
        if sha(inside(project, name)) != digest:
            raise ValueError(f"input changed during preparation: {name}")
    command = [str(tool), "-file", work_alias + "/timing.tcl", "-work_dir", work_alias,
               "-project_name", "board1080_top"]
    plan = {"Schema": "board1080-timing-preparation-v1", "PreparedUTC": datetime.now(timezone.utc).isoformat(),
            "Scope": "PrepareOnlyNoEDA", "EDAExecuted": False, "HardwareAccessed": False,
            "BitstreamRequested": False, "HardwareReleaseAllowed": False, "PhysicalTimingReady": False,
            "TimingAccepted": False, "ProjectRoot": str(project), "RepoAlias": alias,
            "ExplicitPostPNRHoldFixTarget200": clock_tree_hold_target_ps == 200,
            "ClockTreeHoldTargetPS": clock_tree_hold_target_ps,
            "ExplicitPostPNRHoldFixCommand": hold_command,
            "HDLAndConstraintInputsUnchangedByHoldOption": True,
            "EDAStageCommands": ["compile -top_module board1080_top",
                "synthesize -ads -selected_syn_tool_opt 2", "dev_map",
                "pnr -optimize_multi_corner_timing -fix_hold_violation"]
                + ([hold_command] if hold_command is not None else [])
                + ["report_timing -force_to_run -delay_type min_max -max_path 20"],
            "WorkDirectory": str(work), "AliasWorkDirectory": work_alias,
            "Manifest": roles["Manifest"], "InputSHA256": input_hashes,
            "PDS": {"Executable": str(tool), "ExecutableSHA256": sha(tool),
                    "ExpectedVersion": PDS_VERSION, "VersionVerifiedByPreparation": False,
                    "IPOriginToolVersion": ORIGINAL_IP_TOOL_VERSION, "CrossVersionBuild": True},
            "Device": {"Family": "Logos2", "Device": "PG2L100H", "Speedgrade": "-6", "Package": "FBG676"},
            "RoleCounts": {"ManifestSources": 109, "ExplicitVerilog": 30, "ExplicitIDF": 1,
                           "ExpandedIDFBodiesNotAdded": 74, "HeadersNotAdded": 3, "FDC": 1, "RCF": 1},
            "ExplicitDesigns": explicit, "IDFExpandedSourcesNotAdded": roles["IDFExpandedSources"],
            "Constraints": {"FDC": roles["Constraint"], "RCF": roles["RouteConstraint"],
                            "SHA256": roles["ConstraintSHA256"]},
            "Headers": {name: {"CompiledPath": alias_path(project, alias, compiled_root / name),
                               "SHA256": roles["SourceSHA256"][name]} for name in roles["Headers"]},
            "IncludeRewrites": rewrites, "CompiledInputs": copies,
            "Tcl": {"Path": work_alias + "/timing.tcl", "SHA256": sha_bytes(tcl_bytes)},
            "PreSTAFinalDatabase": final_db, "CommandToRunSeparately": command,
            "WorkingDirectoryForCommand": work_alias,
            "Limitations": ["Preparation does not execute or verify the installed PDS version.",
                "A successful tool exit only confirms report generation; inspect both timing corners and exclusions.",
                "Copied IDF bodies are dependencies, not additional add_design entries.",
                "The guarded Tcl snapshot is skipped at initial parse; execution must check its existence and SHA256 against final ADF before claiming unchanged across STA.",
                "External IO/CDC and training/reset protocol acceptance remain separate requirements."]}
    # Exclusive creation protects against accidentally reusing a populated
    # directory. No overwrite, deletion, external process or hardware access.
    if any(work.iterdir()):
        raise ValueError("work directory became nonempty during preparation")
    for destination, content in payloads.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(content)
    with (work / "timing.tcl").open("xb") as stream:
        stream.write(tcl_bytes)
    with (work / "plan.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(plan, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST, help="path relative to distortion")
    parser.add_argument("--work-dir", required=True, type=Path, help="fresh existing child of build/board1080-timing")
    parser.add_argument("--repo-alias", default="P:/")
    parser.add_argument("--pds-shell", default="D:/pango/PDS_2023.2/bin/pds_shell.exe")
    parser.add_argument("--clock-tree-hold-target-ps", type=int, choices=(200,), default=None,
                        help="optional explicit post-PNR hold optimization target; no partial resume")
    args = parser.parse_args(argv)
    try:
        plan = prepare(PROJECT, args.work_dir, manifest_name=args.manifest,
                       repo_alias=args.repo_alias, pds_shell=args.pds_shell,
                       clock_tree_hold_target_ps=args.clock_tree_hold_target_ps)
    except (ValueError, OSError, ET.ParseError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps({"PreparedOnly": True, "Plan": str(Path(plan["WorkDirectory"]) / "plan.json"),
                      "ExplicitDesignCount": len(plan["ExplicitDesigns"]), "EDAExecuted": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
