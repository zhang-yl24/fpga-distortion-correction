"""Freeze an independent processing/output diagnostic recipe; never run EDA.

The rowpipe manifest remains the immutable source baseline. Only the new top,
pattern source, independent TX control and a derived constraint file differ.
The DDR IDF owns its expanded bodies; they are copied but never added twice.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import argparse
import json
import re
import xml.etree.ElementTree as ET

import prepare_board1080_timing as paths


PROJECT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
BASE = "board/board1080-rowpipe-sources.json"
BASE_SHA256 = "7aa056eeb40f1cbce938ecc2c59b00500f8fa3d15b787243c987288e68bb05c9"
BASE_RCF_SHA256 = "981934688d526e8d686635859d811070752570a34738548154d544e41be48516"
MANIFEST = "board/processed-output-sources.json"
FDC = "board/processed-output-diagnostic.fdc"
TOP = "board/processed_output_top.v"
PATTERN = "rtl/experimental/processed_output_pattern.v"
TARGET = "processed_output_top"
REMOVED = frozenset((
    "board/board1080_rowpipe_top.v",
    "platform/video_base/ipcore/cfg_pll/cfg_pll.v",
    "platform/video_base/source/hdmi/iic_dri.v",
    "platform/video_base/source/hdmi/ms7200_ctl.v",
    "platform/video_base/source/hdmi/ms7210_ctl.v",
    "platform/video_base/source/hdmi/ms72xx_ctl.v",
    "rtl/experimental/dvp_mode_admission_monitor.v",
    "rtl/experimental/hdmi1080_input_status.v",
))
ADDED = (TOP, PATTERN, "board/hdmi_tx_init.v", "rtl/reg16_i2c.v", "board/ms7210_commands.vh")
HEADERS = paths.HEADERS | {"board/ms7210_commands.vh"}
INCLUDES = {name: binding for name, binding in paths.INCLUDE_BINDINGS.items()
            if name != "board/board1080_rowpipe_top.v"}
INCLUDES[TOP] = ("board/board1080-synthetic.vh", "board/board1080-synthetic.vh")
INCLUDES["board/hdmi_tx_init.v"] = (
    "D:/English/FPGA/distortion/board/ms7210_commands.vh", "board/ms7210_commands.vh")
INPUT_PORTS = frozenset(("pixclk_in", "vs_in", "hs_in", "de_in",
                         *(f"{colour}_in[{bit}]" for colour in "rgb" for bit in range(8))))
PIN_ATTRIBUTE = re.compile(r"define_attribute \{p:([^}]+)\} \{PAP_IO_(\w+)\} \{([^}]+)\}")
FALSE_FLAGS = ("HardwareReleaseAllowed", "PhysicalTimingReady", "TimingAccepted",
               "ExternalIOAccepted", "CDCPhysicalAccepted", "EligibleForPDSOrHardware")


def require(value, message):
    if not value:
        raise ValueError(message)


def base_manifest(project):
    project = Path(project).resolve()
    path = paths.inside(project, BASE)
    require(paths.sha(path) == BASE_SHA256, "rowpipe baseline manifest changed")
    base = json.loads(path.read_text(encoding="utf-8-sig"))
    names, hashes = base.get("source_files"), base.get("SourceSHA256")
    require(isinstance(names, list) and isinstance(hashes, dict) and set(names) == set(hashes)
            and len(names) == len(set(name.casefold() for name in names)), "invalid baseline closure")
    require(REMOVED <= set(names), "required baseline removals are missing")
    for name in names:
        require(paths.sha(paths.inside(project, name)) == hashes[name], "baseline source drift: " + name)
    require(base.get("Target") == "board1080_top", "unexpected baseline top")
    route = base.get("RouteConstraint")
    require(route == "board/board1080-ddr-ioclk-priority.rcf", "unexpected baseline route contract")
    require(paths.sha(paths.inside(project, route)) == BASE_RCF_SHA256, "baseline DDR route contract drift")
    return base


def constraint_bytes(project, base=None):
    """Derive only declared input/cfg removal and the real SCL direction."""
    base = base or base_manifest(project)
    text = paths.inside(project, base["Constraint"]).read_text(encoding="utf-8-sig")
    require(text.count("# USER CDC inventory") == 1 and text.count("# Bound every user clock-domain pair") == 1,
            "baseline CDC comment anchors changed")
    text = text[text.index("create_clock -name board27"):]
    start = text.index("# USER CDC inventory")
    stop = text.index("# Bound every user clock-domain pair")
    text = text[:start] + (
        "# Independent output CDC: board27 control, DDR core, and pixel clock.\n"
        "# Existing input write-link is driven by an internal controlled source;\n"
        "# no external RX clock, receiver lock or cfg PLL exists in this top.\n"
        "# Output FIFO Gray pointers and held lease/toggle paths still require\n"
        "# final-netlist stage, placement, skew and protocol review.\n") + text[stop:]
    scl_old = "define_attribute {p:hd_scl} {PAP_IO_DIRECTION} {OUTPUT}"
    require(text.count(scl_old) == 1, "baseline SCL direction anchor changed")
    text = text.replace(scl_old, "define_attribute {p:hd_scl} {PAP_IO_DIRECTION} {INOUT}")
    kept = []
    for line in text.splitlines():
        match = PIN_ATTRIBUTE.fullmatch(line.strip())
        if match and match[1] in INPUT_PORTS:
            continue
        if "input_pixel" in line or "cfg_clk" in line or line.startswith("#75.1MHz"):
            continue
        if line.startswith("# PROVISIONAL: source sampling") or line.startswith("# Missing: configured PCLK"):
            continue
        kept.append(line)
    header = (
        "# INDEPENDENT PROCESSING/OUTPUT DIAGNOSTIC ONLY. No external IO sign-off.\n"
        "# 114 package pins; no HDMI RX or sensor ports; TX SCL/SDA are INOUT.\n"
        "# board27=27MHz; pixel=74.25MHz; DDR reference/core contract unchanged.\n"
        "# No guessed output_delay, global clock groups or new false paths.\n"
        "# BASE V1.4 versus local V1.2 trace skew remains unverified.\n"
        "# Existing cross-clock 8ns/max and 0ns/min are diagnostic bounds only.\n"
        "# Do not import a previous routed _N173 net or old reset endpoint names.\n")
    return (header + "\n".join(kept).rstrip() + "\n").encode("ascii")


def derived_names(base):
    result = []
    for name in base["source_files"]:
        if name in REMOVED:
            continue
        result.append(FDC if name == base["Constraint"] else name)
    result.extend(ADDED)
    require(len(result) == len(set(n.casefold() for n in result)), "derived closure has duplicate names")
    return result


def top_ports(text):
    clean = re.sub(r"/\*.*?\*/|//[^\n]*|\(\*.*?\*\)", "", text, flags=re.S)
    matches = list(re.finditer(r"\bmodule\s+" + TARGET + r"\b", clean))
    require(len(matches) == 1, "one candidate top module required")
    tail = clean[matches[0].end():].lstrip()
    if tail.startswith("#"):
        tail = tail[1:].lstrip()
        require(tail.startswith("("), "invalid top parameter list")
        level, end = 0, None
        for pos, char in enumerate(tail):
            level += (char == "(") - (char == ")")
            if level == 0:
                end = pos + 1
                break
        require(end is not None, "unterminated top parameter list")
        tail = tail[end:].lstrip()
    interface = re.match(r"\((.*?)\)\s*;", tail, re.S)
    require(interface is not None, "invalid top interface")
    ports, direction, bounds = {}, None, None
    for part in interface[1].split(","):
        match = re.fullmatch(r"\s*(?:(input|output|inout)\s+)?(?:wire\s+|reg\s+)?"
                             r"(?:\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*)?([A-Za-z_]\w*)\s*", part)
        require(match is not None, "unsupported candidate port declaration")
        typ, high, low, name = match.groups()
        if typ:
            direction, bounds = typ.upper(), None
        require(direction is not None, "port direction is missing")
        if high is not None:
            bounds = (int(high), int(low))
            require(bounds[0] >= bounds[1], "ascending port range is unsupported")
        expanded = [name] if bounds is None else [f"{name}[{n}]" for n in range(bounds[1], bounds[0] + 1)]
        for pin in expanded:
            require(pin not in ports, "duplicate top port")
            ports[pin] = direction
    return ports


def audit_constraint(project, data, base, *, check_top=True):
    require(data == constraint_bytes(project, base), "constraint differs outside exact derivation")
    text = data.decode("ascii")
    baseline = paths.inside(project, base["Constraint"]).read_text(encoding="utf-8-sig")
    rows, original = {}, {}
    for source, output in ((text, rows), (baseline, original)):
        for line in source.splitlines():
            match = PIN_ATTRIBUTE.fullmatch(line.strip())
            if match:
                pin, key, value = match.groups()
                require(key not in output.setdefault(pin, {}), "duplicate FDC attribute")
                output[pin][key] = value
    require(set(rows) == set(original) - INPUT_PORTS and len(rows) == 114, "exact114 output-only pins required")
    for pin, attrs in rows.items():
        expected = dict(original[pin])
        if pin == "hd_scl":
            expected["DIRECTION"] = "INOUT"
        require(attrs == expected, "retained pin/electrical attribute differs: " + pin)
    require(rows["hd_scl"]["DIRECTION"] == rows["hd_sda"]["DIRECTION"] == "INOUT", "TX lines must be bidirectional")
    require(sum(pin.startswith("mem_") for pin in rows) == 71, "DDR71 pin contract differs")
    require(len({attrs["LOC"] for attrs in rows.values()}) == len(rows), "package pin collision")
    require("input_pixel" not in text and "cfg_clk" not in text and not INPUT_PORTS & set(rows), "RX/cfg constraint remains")
    require(not re.search(r"^\s*(?:set_input_delay|set_output_delay|set_clock_groups|set_false_path)\b", text, re.M),
            "external timing/blanket exceptions cannot be introduced by diagnostic preparation")
    if check_top:
        ports = top_ports(paths.inside(project, TOP).read_text(encoding="utf-8-sig"))
        require(set(ports) == set(rows), "candidate top ports differ from exact114 FDC pins")
        require(all(ports[pin] == attrs["DIRECTION"] for pin, attrs in rows.items()), "candidate top/FDC direction mismatch")
    return {"PackagePins": len(rows), "DDRPins": 71, "RemovedRXInputPins": len(INPUT_PORTS),
            "UnchangedRetainedElectricalAttributes": True, "TXSCLAndSDAInout": True,
            "ExternalIOAccepted": False}


def create_constraint(project=PROJECT):
    base = base_manifest(project)
    data = constraint_bytes(project, base)
    audit_constraint(project, data, base, check_top=False)
    with (Path(project) / FDC).open("xb") as stream:
        stream.write(data)
    return {"Constraint": FDC, "SHA256": paths.sha_bytes(data)}


def freeze_manifest(project=PROJECT):
    project = Path(project).resolve()
    base = base_manifest(project)
    names = derived_names(base)
    source_hashes = {name: paths.sha(paths.inside(project, name)) for name in names}
    manifest = {"Schema": "independent-processed-output-source-closure-v1", "Target": TARGET,
                "Candidate": "Controlled pattern -> existing processing/DDR/output; independent TX; diagnostic only",
                "source_files": names, "SourceSHA256": source_hashes,
                "Constraint": FDC, "RouteConstraint": base["RouteConstraint"],
                "RouteConstraintSHA256": paths.sha(paths.inside(project, base["RouteConstraint"])),
                "BaseManifest": {"Path": BASE, "SHA256": BASE_SHA256},
                "RemovedBaselineSources": sorted(REMOVED), "AddedSources": list(ADDED),
                "SourceRoleRule": "IDF owns expanded DDR bodies; headers and constraints are not independent designs.",
                "DDRBodyComparison": ddr_body_comparison(project),
                "InputDebuggingPaused": True, "PhysicalInputExercised": False,
                **{flag: False for flag in FALSE_FLAGS}}
    validate(project, manifest=manifest)
    with (project / MANIFEST).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(manifest, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return manifest


def validate(project=PROJECT, *, manifest=None):
    project = Path(project).resolve()
    base = base_manifest(project)
    if manifest is None:
        manifest = json.loads(paths.inside(project, MANIFEST).read_text(encoding="utf-8-sig"))
    require(manifest.get("Schema") == "independent-processed-output-source-closure-v1"
            and manifest.get("Target") == TARGET, "unexpected candidate manifest identity")
    require(all(manifest.get(flag) is False for flag in FALSE_FLAGS), "preparation cannot assert physical/timing/hardware acceptance")
    require(manifest.get("BaseManifest") == {"Path": BASE, "SHA256": BASE_SHA256}, "baseline binding differs")
    ddr_audit = ddr_body_comparison(project)
    require(manifest.get("DDRBodyComparison") == ddr_audit, "DDR body provenance comparison differs")
    names, hashes = manifest.get("source_files"), manifest.get("SourceSHA256")
    require(names == derived_names(base) and isinstance(hashes, dict) and set(hashes) == set(names), "candidate derivation differs")
    for name in names:
        require(paths.sha(paths.inside(project, name)) == hashes[name], "candidate source hash mismatch: " + name)
    require(not REMOVED & set(names), "removed receiver/configuration design remains")
    require(manifest.get("Constraint") == FDC and manifest.get("RouteConstraint") == base["RouteConstraint"], "constraint roles differ")
    route = base["RouteConstraint"]
    require(paths.sha(paths.inside(project, route)) == manifest.get("RouteConstraintSHA256"), "route constraint drift")
    pin_audit = audit_constraint(project, paths.inside(project, FDC).read_bytes(), base)
    source = ET.parse(paths.inside(project, paths.IDF)).getroot().find("file_list/source")
    require(source is not None, "IDF source section missing")
    bodies = [paths.IP + "/" + paths.relative_name(entry.get("pathname")) for entry in source.findall("file")]
    require(len(bodies) == len(set(bodies)) and Counter(PurePosixPath(n).suffix for n in bodies) == {".vp": 71, ".v": 3},
            "unchanged DDR IDF ownership differs")
    require({n for n in names if n.startswith(paths.IP + "/")} == set(bodies) | {paths.IDF}, "unowned or missing DDR dependency")
    headers = {n for n in names if PurePosixPath(n).suffix == ".vh"}
    require(headers == HEADERS, "candidate header roles differ")
    explicit = [n for n in names if n not in set(bodies) | headers | {FDC}]
    require(Counter(PurePosixPath(n).suffix for n in explicit) == {".v": len(explicit) - 1, ".idf": 1}, "unsupported independent design role")
    for name in explicit + sorted(headers):
        if name == paths.IDF:
            continue
        data = paths.inside(project, name).read_bytes()
        includes = paths.INCLUDE.findall(data)
        binding = INCLUDES.get(name)
        require(len(paths.INCLUDE_DIRECTIVE.findall(data)) == len(includes)
                and includes == ([] if binding is None else [binding[0].encode("ascii")]),
                "unexpected/missing exact include: " + name)
    return {"Manifest": MANIFEST, "Sources": names, "SourceSHA256": hashes,
            "ExplicitDesigns": explicit, "IDFExpandedSources": bodies, "Headers": sorted(headers),
            "Constraint": FDC, "RouteConstraint": route, "PinAudit": pin_audit,
            "DDRBodyComparison": ddr_audit,
            "ConstraintSHA256": {FDC: hashes[FDC], route: manifest["RouteConstraintSHA256"]},
            "RoleCounts": {"ManifestSources": len(names), "ExplicitVerilog": len(explicit) - 1,
                           "ExplicitIDF": 1, "ExpandedIDFBodiesNotAdded": len(bodies),
                           "HeadersNotAdded": len(headers), "FDC": 1, "RCF": 1}}


def ddr_body_comparison(project):
    chunks = []
    for name in ("board/board1080_rowpipe_top.v", TOP):
        raw = paths.inside(project, name).read_bytes()
        start = b"    wire ddr_ref_clk,core_clk,ddr_init_done,ddr_pll_lock;"
        stop = b'    (* async_reg="true" *) reg [1:0] ref_reset'
        require(raw.count(start) == 1 and raw.count(stop) == 1, "DDR instance provenance anchors differ")
        chunks.append(raw[raw.index(start):raw.index(stop)])
    normal = [chunk.replace(b"\r\n", b"\n") for chunk in chunks]
    require(normal[0] == normal[1], "candidate changed DDR wiring/APB/inactive debug body")
    return {"BaselineTop": "board/board1080_rowpipe_top.v", "CandidateTop": TOP,
            "BaselineBodySHA256": paths.sha_bytes(chunks[0]), "CandidateBodySHA256": paths.sha_bytes(chunks[1]),
            "RawBytesIdentical": chunks[0] == chunks[1], "EquivalentAfterCRLFNormalization": True,
            "NormalizedBodySHA256": paths.sha_bytes(normal[0]),
            "IncludesDDRInterfaceAPBAndInactiveDebugTieOffs": True,
            "DoesNotProvePhysicalTiming": True}


def make_tcl(designs, constraint, route, work_alias):
    quote = paths.tcl_path
    commands = ["# Independent diagnostic preparation only; no bitstream or hardware command.",
                "set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676"]
    commands += ["add_design " + quote(name) for name in designs]
    commands += ["add_constraint " + quote(constraint), "compile -top_module " + TARGET,
                 "synthesize -ads -selected_syn_tool_opt 2", "dev_map", "add_constraint " + quote(route),
                 "pnr -optimize_multi_corner_timing -fix_hold_violation",
                 "if {[file exists " + quote(work_alias + "/place_route/" + TARGET + "_pnr.adf") + "]} {",
                 "    file copy " + quote(work_alias + "/place_route/" + TARGET + "_pnr.adf") + " " + quote(work_alias + "/pre-sta-final.adf"),
                 "}", "report_timing -force_to_run -delay_type min_max -max_path 20"]
    return "\n".join(commands) + "\n"


def recipe_path(project, alias, path):
    if alias != "direct":
        return paths.alias_path(project, alias, path)
    path = Path(path).resolve()
    require(path.is_relative_to(Path(project).resolve().parent), "direct recipe path escaped repository")
    value = path.as_posix()
    paths.tcl_path(value)
    return value


def prepare(project, work_dir, *, repo_alias="P:/", pds_shell="D:/pango/PDS_2023.2/bin/pds_shell.exe", maximum_seconds=1800):
    project = Path(project).resolve()
    require(type(maximum_seconds) is int and 60 <= maximum_seconds <= 7200, "external EDA deadline must be60..7200 seconds")
    roles = validate(project)
    work = Path(work_dir).absolute()
    expected_parent = project / "build/processed-output"
    require(work.parent == expected_parent and work.resolve() == work and work.is_dir() and not any(work.iterdir()),
            "work directory must be a fresh existing direct child of build/processed-output, without junctions")
    alias = "direct" if repo_alias == "direct" else paths.validate_repo_alias(project, repo_alias)
    if alias == "direct":
        recipe_path(project, alias, project)
    tool = Path(pds_shell).resolve()
    require(tool.is_file(), "PDS shell executable must exist; preparation does not execute it")
    auxiliary = {MANIFEST: paths.sha(paths.inside(project, MANIFEST)), BASE: BASE_SHA256,
                 SELF.relative_to(PROJECT).as_posix(): paths.sha(SELF),
                 "tools/prepare_board1080_timing.py": paths.sha(Path(paths.__file__))}
    input_hashes = {**roles["SourceSHA256"], **roles["ConstraintSHA256"], **auxiliary}
    root = work / "compiled"
    payloads, copies, rewrites, designs = {}, [], [], []
    for name in list(roles["Sources"]) + [roles["RouteConstraint"]]:
        data = paths.inside(project, name).read_bytes()
        require(paths.sha_bytes(data) == input_hashes[name], "source changed during preparation: " + name)
        compiled = data
        if name in INCLUDES:
            old, header = INCLUDES[name]
            matches = list(paths.INCLUDE.finditer(data))
            require(len(matches) == 1 and matches[0][1] == old.encode("ascii"), "include changed during preparation")
            replacement = recipe_path(project, alias, root / header)
            match = matches[0]
            compiled = data[:match.start(1)] + replacement.encode("ascii") + data[match.end(1):]
            rewrites.append({"Source": name, "OriginalInclude": old, "CompiledInclude": replacement,
                             "Header": header, "HeaderSHA256": input_hashes[header], "ReplacementCount": 1})
        destination = root / name
        payloads[destination] = compiled
        compiled_alias = recipe_path(project, alias, destination)
        copies.append({"Source": name, "OriginalSHA256": input_hashes[name], "CompiledPath": compiled_alias,
                       "CompiledSHA256": paths.sha_bytes(compiled)})
        if name in roles["ExplicitDesigns"]:
            designs.append(compiled_alias)
    work_alias = recipe_path(project, alias, work)
    tcl = make_tcl(designs, recipe_path(project, alias, root / FDC),
                   recipe_path(project, alias, root / roles["RouteConstraint"]), work_alias).encode("ascii")
    for name, digest in input_hashes.items():
        require(paths.sha(paths.inside(project, name)) == digest, "input changed before write: " + name)
    command = [str(tool), "-file", work_alias + "/timing.tcl", "-work_dir", work_alias, "-project_name", TARGET]
    plan = {"Schema": "independent-processed-output-diagnostic-preparation-v1",
            "PreparedUTC": datetime.now(timezone.utc).isoformat(), "Scope": "PrepareOnlyNoEDA",
            "EDAExecuted": False, "HardwareAccessed": False, "BitstreamRequested": False,
            **{flag: False for flag in FALSE_FLAGS}, "Target": TARGET, "ProjectRoot": str(project),
            "WorkDirectory": str(work), "RepoAlias": alias, "AliasWorkDirectory": work_alias,
            "Manifest": MANIFEST, "InputSHA256": input_hashes, "RoleCounts": roles["RoleCounts"],
            "PinAudit": roles["PinAudit"], "DDRBodyComparison": roles["DDRBodyComparison"], "ExplicitDesigns": designs,
            "IDFExpandedSourcesNotAdded": roles["IDFExpandedSources"], "IncludeRewrites": rewrites,
            "CompiledInputs": copies, "Constraints": {"FDC": FDC, "RCF": roles["RouteConstraint"],
                                                       "CopiedIntoFrozenCompiledTree": True},
            "Tcl": {"Path": work_alias + "/timing.tcl", "SHA256": paths.sha_bytes(tcl)},
            "PDS": {"Executable": str(tool), "ExecutableSHA256": paths.sha(tool),
                    "ExpectedVersion": paths.PDS_VERSION, "VersionVerifiedByPreparation": False},
            "CommandToRunSeparately": command, "WorkingDirectoryForCommand": work_alias,
            "MaximumSecondsForExternalExecutor": maximum_seconds, "ExternalDeadlineRequired": True,
            "PreSTAFinalDatabase": work_alias + "/pre-sta-final.adf",
            "Limitations": ["No EDA is executed. A separate executor must enforce the supplied wall-time deadline.",
                "No old routed net, physical repair or reset endpoint exception is imported.",
                "New final-netlist pin/CDC/DDR reset/dual-corner timing and external IO audits remain pending.",
                "Before claiming unchanged across STA, compare pre-sta-final.adf with the actual final routed ADF.",
                "This controlled pattern is not current camera capture or a calibrated lens source."]}
    require(not any(work.iterdir()), "work directory became nonempty during preparation")
    for destination, data in payloads.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as stream:
            stream.write(data)
    with (work / "timing.tcl").open("xb") as stream:
        stream.write(tcl)
    with (work / "plan.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(plan, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--create-constraint", action="store_true")
    mode.add_argument("--freeze-manifest", action="store_true")
    mode.add_argument("--audit-only", action="store_true")
    mode.add_argument("--work-dir", type=Path)
    parser.add_argument("--repo-alias", default="P:/", help="mapped repository drive, or direct for an ASCII repository path")
    parser.add_argument("--pds-shell", default="D:/pango/PDS_2023.2/bin/pds_shell.exe")
    parser.add_argument("--maximum-seconds", type=int, default=1800)
    args = parser.parse_args(argv)
    try:
        if args.create_constraint:
            result = create_constraint()
        elif args.freeze_manifest:
            manifest = freeze_manifest()
            result = {"Manifest": MANIFEST, "SHA256": paths.sha(PROJECT / MANIFEST), "SourceCount": len(manifest["source_files"])}
        elif args.audit_only:
            roles = validate()
            result = {"Passed": True, "RoleCounts": roles["RoleCounts"], "PinAudit": roles["PinAudit"]}
        else:
            plan = prepare(PROJECT, args.work_dir, repo_alias=args.repo_alias, pds_shell=args.pds_shell,
                           maximum_seconds=args.maximum_seconds)
            result = {"PreparedOnly": True, "Plan": str(Path(plan["WorkDirectory"]) / "plan.json"),
                      "RoleCounts": plan["RoleCounts"], "EDAExecuted": False}
    except (ValueError, OSError, ET.ParseError, json.JSONDecodeError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
