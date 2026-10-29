"""Prepare isolated checked-I2C PDS flow; never run EDA or change old inputs.

The separate build FDC changes only SCL OUTPUT to INOUT. Existing source-only
selection, baseline role guards and physical-acceptance boundaries stay intact.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import argparse
import copy
import json
import re
import board1080_checked_profile as selection
import prepare_board1080_timing as timing

PROJECT = Path(__file__).resolve().parents[1]
MANIFEST = "board/board1080-checked-build-sources.json"
FDC = "board/board1080-checked-i2c.fdc"
BASE_FDC = "board/board1080-cdc-reset-diagnostic.fdc"
BASE_FDC_SHA256 = "2ff6dd8510e7b0566f550143561ac4138c19cd255944811b4561979f6e8b0f23"
SCHEMA = "board1080-checked-timing-preparation-v1"
INCLUDE_BINDINGS = {selection.REPLACEMENTS.get(n, n): v for n, v in timing.INCLUDE_BINDINGS.items()}
STAGES = ("compile -top_module board1080_top", "synthesize -ads -selected_syn_tool_opt 2",
          "dev_map", timing.pnr_command(), timing.post_pnr_hold_command(200),
          "report_timing -force_to_run -delay_type min_max -max_path 20")
sha, require = timing.sha, selection.require
validate_repo_alias = timing.validate_repo_alias


def render_fdc(project=PROJECT):
    raw = timing.inside(project, BASE_FDC).read_bytes()
    require(timing.sha_bytes(raw) == BASE_FDC_SHA256, "bound baseline FDC changed")
    old = b"define_attribute {p:hd_scl} {PAP_IO_DIRECTION} {OUTPUT}"
    require(raw.count(old) == 1, "exactly one baseline SCL output declaration required")
    return raw.replace(old, b"define_attribute {p:hd_scl} {PAP_IO_DIRECTION} {INOUT}", 1)


def expected_manifest(project=PROJECT):
    project = Path(project).resolve()
    base = selection.validate_profile(project)
    require(base["Constraint"] == BASE_FDC and base["source_files"].count(BASE_FDC) == 1,
            "checked source-only inventory must contain exact baseline FDC")
    expected = render_fdc(project)
    require(timing.inside(project, FDC).read_bytes() == expected,
            "checked FDC differs outside the single SCL direction change")
    result = copy.deepcopy(base)
    result.update(Schema="board1080-checked-build-closure-v1",
        Candidate="Checked I2C build candidate; SCL direction changed only, physical acceptance pending",
        source_files=[FDC if n == BASE_FDC else n for n in base["source_files"]],
        SourceSHA256={FDC if n == BASE_FDC else n: timing.sha_bytes(expected) if n == BASE_FDC else d
                      for n, d in base["SourceSHA256"].items()}, Constraint=FDC,
        BaseManifest={"Path": "distortion/" + selection.MANIFEST, "SHA256": sha(project / selection.MANIFEST)},
        SCLConstraintTransformation={"Original": BASE_FDC, "OriginalSHA256": BASE_FDC_SHA256,
            "Replacement": FDC, "ReplacementSHA256": timing.sha_bytes(expected),
            "OnlyChange": "hd_scl PAP_IO_DIRECTION OUTPUT to INOUT"},
        ElectricalConstraintStatus="DirectionUpdatedOnlyPhysicalAcceptancePending",
        FDCAndRCFUnchanged=False, RCFUnchanged=True, EligibleForPDSPreparation=True,
        EligibleForPDSOrHardware=False, PDSExecuted=False, CompiledIntegrationVerified=False,
        TimingAccepted=False, PhysicalTimingReady=False, HardwareReleaseAllowed=False,
        PreviousCandidateTimingReusable=False, PreviousCandidateBitstreamReusable=False)
    return result


def validate_profile(project=PROJECT):
    """Map only already validated baseline roles, without modifying its guards."""
    project = Path(project).resolve()
    actual = json.loads(timing.inside(project, MANIFEST).read_text(encoding="utf-8-sig"))
    require(actual == expected_manifest(project), "checked build manifest differs from exact FDC/source selection")
    base = selection.hdmi30.validate_profile(project)
    mapping = {**selection.REPLACEMENTS, BASE_FDC: FDC}
    names = actual["source_files"]
    require(names == [mapping.get(n, n) for n in base["Sources"]]
            and len(names) == len(set(n.casefold() for n in names)) == 109,
            "exact unique ordered 109-source checked closure required")
    require(set(actual["SourceSHA256"]) == set(names), "exact source hash keys required")
    for name in names:
        require(sha(timing.inside(project, name)) == actual["SourceSHA256"][name], "source SHA256 drift: " + name)
    explicit = [mapping.get(n, n) for n in base["ExplicitDesigns"]]
    require(len(explicit) == 31 and Counter(Path(n).suffix for n in explicit) == {".v": 30, ".idf": 1},
            "31 independent designs required")
    require(len(base["IDFExpandedSources"]) == 74 and len(base["Headers"]) == 3, "bound IDF/header roles differ")
    require(set(selection.REPLACEMENTS).isdisjoint(names), "legacy top or driver mixed into checked closure")
    for name in explicit + base["Headers"]:
        if name == timing.IDF:
            continue
        raw = timing.inside(project, name).read_bytes()
        includes, binding = timing.INCLUDE.findall(raw), INCLUDE_BINDINGS.get(name)
        require(len(timing.INCLUDE_DIRECTIVE.findall(raw)) == len(includes)
                and includes == ([] if binding is None else [binding[0].encode("ascii")]),
                "unexpected checked bound include: " + name)
    auxiliary = dict(base["AuxiliarySHA256"])
    for name in (selection.MANIFEST, MANIFEST, BASE_FDC):
        auxiliary[name] = sha(timing.inside(project, name))
    # Validation follows the older manifest chain; bind those identities too.
    pending = [selection.MANIFEST, selection.hdmi30.MANIFEST, selection.hdmi30.BASE]
    visited = set()
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        path = timing.inside(project, name)
        auxiliary[name] = sha(path)
        parent = json.loads(path.read_text(encoding="utf-8-sig")).get("BaseManifest")
        if parent is not None:
            require(isinstance(parent, dict) and isinstance(parent.get("Path"), str)
                    and parent["Path"].startswith("distortion/"), "invalid ancestral manifest path")
            parent_name = timing.relative_name(parent["Path"][len("distortion/"):])
            require(sha(timing.inside(project, parent_name)) == parent.get("SHA256"), "ancestral manifest hash differs")
            pending.append(parent_name)
    return {"Manifest": MANIFEST, "Sources": names, "SourceSHA256": dict(actual["SourceSHA256"]),
        "ExplicitDesigns": explicit, "IDFExpandedSources": base["IDFExpandedSources"],
        "Headers": base["Headers"], "Constraint": FDC, "RouteConstraint": base["RouteConstraint"],
        "ConstraintSHA256": {FDC: sha(project / FDC), base["RouteConstraint"]: base["ConstraintSHA256"][base["RouteConstraint"]]},
        "AuxiliarySHA256": auxiliary}


def expected_inputs(project, roles):
    """Complete preparation hashes, shared with the independent result auditor."""
    project = Path(project).resolve()
    result = {**roles["SourceSHA256"], **roles["ConstraintSHA256"], **roles["AuxiliarySHA256"]}
    helpers = (Path(__file__), Path(selection.__file__), Path(selection.hdmi30.__file__), Path(timing.__file__),
               Path(selection.hdmi30.edid.__file__), Path(selection.top.__file__), Path(selection.controller.__file__))
    for helper in helpers:
        name = helper.resolve().relative_to(PROJECT).as_posix()
        digest = sha(helper)
        require(sha(timing.inside(project, name)) == digest, "preparation helper identity differs: " + name)
        result[name] = digest
    return result


def write_profile(project=PROJECT):
    project = Path(project).resolve()
    require(not (project / FDC).exists() and not (project / MANIFEST).exists(), "derived profile already exists")
    selection.validate_profile(project)
    with (project / FDC).open("xb") as stream:
        stream.write(render_fdc(project))
    result = expected_manifest(project)
    with (project / MANIFEST).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False);stream.write("\n")
    return result


def prepare(project, work_dir, *, repo_alias="P:/", pds_shell="D:/pango/PDS_2023.2/bin/pds_shell.exe"):
    project = Path(project).resolve()
    roles = validate_profile(project)
    work = timing.fresh_work_dir(project, work_dir)
    require(re.fullmatch(r"checked-[A-Za-z0-9_-]+", work.name) is not None, "checked-* work directory required")
    alias = validate_repo_alias(project, repo_alias)
    tool = Path(pds_shell).resolve()
    require(tool.is_file(), "PDS shell executable must exist; preparation does not run it")
    executable_hash = sha(tool)
    inputs = expected_inputs(project, roles)
    work_alias = timing.alias_path(project, alias, work)
    compiled_root = work / "compiled"
    payloads, rewrites, copies, explicit = {}, [], [], []
    for name in roles["Sources"]:
        raw = timing.inside(project, name).read_bytes()
        require(timing.sha_bytes(raw) == inputs[name], "source changed during preparation: " + name)
        compiled = raw
        if name in INCLUDE_BINDINGS:
            original, header = INCLUDE_BINDINGS[name]
            matches = list(timing.INCLUDE.finditer(raw))
            require(len(matches) == 1 and matches[0][1] == original.encode("ascii"), "include changed during preparation")
            target = timing.alias_path(project, alias, compiled_root / header)
            match = matches[0]
            compiled = raw[:match.start(1)] + target.encode("ascii") + raw[match.end(1):]
            rewrites.append(dict(Source=name, OriginalInclude=original, CompiledInclude=target,
                Header=header, HeaderSHA256=inputs[header], ReplacementCount=1))
        destination = compiled_root / name
        target = timing.alias_path(project, alias, destination)
        payloads[destination] = compiled
        copies.append(dict(Source=name, OriginalSHA256=inputs[name], CompiledPath=target,
                           CompiledSHA256=timing.sha_bytes(compiled)))
        if name in roles["ExplicitDesigns"]:
            explicit.append(target)
    final_db = work_alias + "/pre-sta-final.adf"
    tcl = timing.make_tcl(explicit, timing.alias_path(project, alias, project / FDC),
        timing.alias_path(project, alias, project / roles["RouteConstraint"]), work_alias, final_db, 200).encode("ascii")
    require(validate_profile(project) == roles and expected_inputs(project, roles) == inputs,
            "profile or helpers changed during preparation")
    require(all(sha(timing.inside(project, n)) == d for n, d in inputs.items()), "input changed during preparation")
    require(sha(tool) == executable_hash, "PDS executable changed during preparation")
    command = [str(tool), "-file", work_alias + "/timing.tcl", "-work_dir", work_alias, "-project_name", "board1080_top"]
    plan = dict(Schema=SCHEMA, PreparedUTC=datetime.now(timezone.utc).isoformat(), Scope="PrepareOnlyNoEDA",
        EDAExecuted=False, HardwareAccessed=False, BitstreamRequested=False, HardwareReleaseAllowed=False,
        PhysicalTimingReady=False, TimingAccepted=False, ProjectRoot=str(project), RepoAlias=alias,
        CheckedI2CProfileVerified=True, SCLDirectionOnlyConstraintChange=True,
        PreviousCandidateTimingReused=False, PreviousCandidateBitstreamReused=False,
        ExplicitPostPNRHoldFixTarget200=True, ClockTreeHoldTargetPS=200,
        ExplicitPostPNRHoldFixCommand=STAGES[4], HDLAndConstraintInputsUnchangedByHoldOption=True,
        EDAStageCommands=list(STAGES), WorkDirectory=str(work), AliasWorkDirectory=work_alias,
        Manifest=MANIFEST, InputSHA256=inputs, PDS={"Executable": str(tool), "ExecutableSHA256": executable_hash,
            "ExpectedVersion": timing.PDS_VERSION, "VersionVerifiedByPreparation": False,
            "IPOriginToolVersion": timing.ORIGINAL_IP_TOOL_VERSION, "CrossVersionBuild": True},
        Device={"Family": "Logos2", "Device": "PG2L100H", "Speedgrade": "-6", "Package": "FBG676"},
        RoleCounts={"ManifestSources": 109, "ExplicitVerilog": 30, "ExplicitIDF": 1,
            "ExpandedIDFBodiesNotAdded": 74, "HeadersNotAdded": 3, "FDC": 1, "RCF": 1},
        ExplicitDesigns=explicit, IDFExpandedSourcesNotAdded=roles["IDFExpandedSources"],
        Constraints={"FDC": FDC, "RCF": roles["RouteConstraint"], "SHA256": roles["ConstraintSHA256"]},
        Headers={n: {"CompiledPath": timing.alias_path(project, alias, compiled_root / n), "SHA256": inputs[n]}
                 for n in roles["Headers"]},
        IncludeRewrites=rewrites, CompiledInputs=copies,
        Tcl={"Path": work_alias + "/timing.tcl", "SHA256": timing.sha_bytes(tcl)},
        PreSTAFinalDatabase=final_db, CommandToRunSeparately=command, WorkingDirectoryForCommand=work_alias,
        Limitations=["Preparation never executes PDS or validates its installed version.",
            "Only SCL direction changes in the derived FDC; pull-ups, board voltage, IO delays and physical timing remain unverified.",
            "Successful PDS exit/report generation is not timing or hardware acceptance.",
            "Copied IDF bodies are dependencies, not extra add_design entries.",
            "The guarded pre-STA snapshot must later match the final routed ADF."])
    require(not any(work.iterdir()), "work directory became nonempty during preparation")
    for destination, payload in payloads.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(payload)
    with (work / "timing.tcl").open("xb") as stream:
        stream.write(tcl)
    with (work / "plan.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(plan, stream, indent=2, ensure_ascii=False);stream.write("\n")
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-profile", action="store_true")
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--repo-alias", default="P:/")
    parser.add_argument("--pds-shell", default="D:/pango/PDS_2023.2/bin/pds_shell.exe")
    args = parser.parse_args(argv)
    if args.write_profile:
        require(args.work_dir is None, "write profile and prepare build separately")
        write_profile()
        print(json.dumps({"ManifestCreated": MANIFEST, "FDC": FDC, "EDAExecuted": False}))
    elif args.work_dir is not None:
        plan = prepare(PROJECT, args.work_dir, repo_alias=args.repo_alias, pds_shell=args.pds_shell)
        print(json.dumps({"PreparedOnly": True, "EDAExecuted": False, "Plan": str(args.work_dir / 'plan.json'),
                          "InputCount": len(plan["InputSHA256"]), "ExplicitDesignCount": len(plan["ExplicitDesigns"])}))
    else:
        roles = validate_profile()
        print(json.dumps({"ProfileValid": True, "Sources": len(roles["Sources"]), "EDAExecuted": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
