"""Freeze an isolated CAM2 VGA processing/output recipe; never run EDA.

The previously displayed controlled-source top remains an immutable baseline.
Only camera-facing wrappers/top and the added CAM2 constraints differ.
The DDR IDF owns its expanded bodies; they are copied but never added twice.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import argparse
import json
import re
import tempfile
import xml.etree.ElementTree as ET

import prepare_board1080_timing as paths


PROJECT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
BASE = "board/processed-output-sources.json"
BASE_SHA256 = "899c59bdbc1adfdb5fb0e67f54b576f999cb6f5ed88661bd8f630aa2a0ab687a"
BASE_RCF_SHA256 = "981934688d526e8d686635859d811070752570a34738548154d544e41be48516"
MANIFEST = "board/camera-vga-output-sources.json"
FDC = "board/camera-vga-output-diagnostic.fdc"
TOP = "board/camera_vga_output_top.v"
TARGET = "camera_vga_output_top"
TEMP_BUILD = Path(tempfile.gettempdir()).resolve() / "codex-camera-vga-output"
WORK_BUILD_RELATIVE = "work/camera-vga-output"
RAW_FDC = "board/raw_camera_capture_cam2_ref.fdc"
RAW_PINS = "board/raw_camera_capture_cam2_ref-pins.json"
RAW_FDC_SHA = "ac7f3b30b3def97187947046b638ae8df1c0fa33670ff865ad4107acb562be7a"
RAW_PINS_SHA = "886c51cf850b42d77e8cf3eb2c1ae74829b72d8e3ed9e2ee9d78c4f950e639e2"
REMOVED = frozenset((
    "board/processed_output_top.v", "rtl/experimental/processed_output_pattern.v",
    "rtl/experimental/hdmi1080_capture_cdc.v", "rtl/experimental/hdmi1080_input_dma.v",
    "rtl/experimental/hdmi1080_input_write_link.v", "rtl/experimental/hdmi1080_video_system_cdc_reset.v",
))
ADDED = (TOP, "rtl/experimental/dvp_rgb565_capture_cdc.v",
         "rtl/experimental/camera_vga_input_dma.v", "rtl/experimental/camera_vga_input_write_link.v",
         "rtl/experimental/camera_vga_video_system.v", "rtl/experimental/ov5640_cadence_trial_init.v",
         "rtl/experimental/capture_warmup.v", "board/ov5640_cadence_trial_commands.vh")
HEADERS = paths.HEADERS | {"board/ms7210_commands.vh", "board/ov5640_cadence_trial_commands.vh"}
INCLUDES = {name: binding for name, binding in paths.INCLUDE_BINDINGS.items()
            if name != "board/board1080_rowpipe_top.v"}
INCLUDES[TOP] = ("board/board1080-synthetic.vh", "board/board1080-synthetic.vh")
INCLUDES["board/hdmi_tx_init.v"] = (
    "D:/English/FPGA/distortion/board/ms7210_commands.vh", "board/ms7210_commands.vh")
INCLUDES["rtl/experimental/ov5640_cadence_trial_init.v"] = (
    "D:/English/FPGA/distortion/board/ov5640_cadence_trial_commands.vh", "board/ov5640_cadence_trial_commands.vh")
CAM_INPUTS = frozenset(("cam_pclk", "cam_vsync", "cam_href", *(f"cam_data[{bit}]" for bit in range(8))))
CAM_INOUTS = frozenset(("cam_rst_n", "cam_scl", "cam_sda"))
CAM_PORTS = CAM_INPUTS | CAM_INOUTS
PIN_ATTRIBUTE = re.compile(r"define_attribute \{p:([^}]+)\} \{PAP_IO_(\w+)\} \{([^}]+)\}")
FALSE_FLAGS = ("HardwareReleaseAllowed", "PhysicalTimingReady", "TimingAccepted",
               "ExternalIOAccepted", "CDCPhysicalAccepted", "EligibleForPDSOrHardware")


def require(value, message):
    if not value:
        raise ValueError(message)


def base_manifest(project):
    project = Path(project).resolve()
    path = paths.inside(project, BASE)
    require(paths.sha(path) == BASE_SHA256, "displayed processing/output baseline manifest changed")
    base = json.loads(path.read_text(encoding="utf-8-sig"))
    names, hashes = base.get("source_files"), base.get("SourceSHA256")
    require(isinstance(names, list) and isinstance(hashes, dict) and set(names) == set(hashes)
            and len(names) == len(set(name.casefold() for name in names)), "invalid baseline closure")
    require(REMOVED <= set(names), "required baseline removals are missing")
    for name in names:
        require(paths.sha(paths.inside(project, name)) == hashes[name], "baseline source drift: " + name)
    require(base.get("Target") == "processed_output_top", "unexpected baseline top")
    route = base.get("RouteConstraint")
    require(route == "board/board1080-ddr-ioclk-priority.rcf", "unexpected baseline route contract")
    require(paths.sha(paths.inside(project, route)) == BASE_RCF_SHA256, "baseline DDR route contract drift")
    require(paths.sha(paths.inside(project, RAW_FDC)) == RAW_FDC_SHA
            and paths.sha(paths.inside(project, RAW_PINS)) == RAW_PINS_SHA, "historical CAM2 pin reference changed")
    return base


def camera_attributes(project):
    expected = json.loads(paths.inside(project, RAW_PINS).read_text())
    rows = {}
    for line in paths.inside(project, RAW_FDC).read_text().splitlines():
        match = PIN_ATTRIBUTE.fullmatch(line.strip())
        if match and match[1] in CAM_PORTS:
            pin, key, value = match.groups()
            require(key not in rows.setdefault(pin, {}), "duplicate historical camera attribute")
            rows[pin][key] = value
    require(set(rows) == CAM_PORTS and len(rows) == 14, "exact14 CAM2 pin inventory required")
    for pin in rows:
        require(rows[pin]['LOC'] == expected[pin], "historical camera pad mismatch")
        require('DIRECTION' not in rows[pin], "historical camera direction unexpectedly explicit")
        rows[pin]['DIRECTION'] = 'INPUT' if pin in CAM_INPUTS else 'INOUT'
    require(rows['cam_data[5]']['LOC'] == 'AA23', "corrected CAM2 D5 required")
    return rows


def constraint_bytes(project, base=None):
    base = base or base_manifest(project)
    text = paths.inside(project, base['Constraint']).read_text(encoding='utf-8-sig')
    text = text[text.index('create_clock -name board27'):]
    start = text.index('# Independent output CDC:')
    stop = text.index('# Bound every user clock-domain pair', start)
    text = text[:start] + (
        '# Camera VGA candidate: board27 configuration, camera_pclk capture, DDR core, pixel output.\n'
        '# Camera first-stage/Gray/mailbox paths need new final-netlist and physical review.\n') + text[stop:]
    lines = [
        '# CAM2 VGA -> existing DDR/processing/output diagnostic; not camera or IO acceptance.',
        '# 128 package pins = unchanged114 processing/output plus exact14 CAM2 reference pins.',
        '# Camera 48MHz/20.833ns and input delay0..5ns are historical PROVISIONAL budgets.',
        '# Actual sensor PCLK, board skew and external sampling margin remain UNMEASURED.',
        '# No old routed repair, reset exception, false path or clock-group waiver is imported.',
        text.rstrip(), '',
        'create_clock -name camera_pclk -period 20.833 [get_ports cam_pclk]',
        'set_input_delay -clock camera_pclk -max 5.0 [get_ports {cam_data[*] cam_vsync cam_href}]',
        'set_input_delay -clock camera_pclk -min 0.0 [get_ports {cam_data[*] cam_vsync cam_href}]',
        '# Extend diagnostic CDC bounds only to real camera/control/core domain pairs.',
    ]
    for other in ('board27', 'ddrphy_sysclk'):
        for first, last in (('camera_pclk', other), (other, 'camera_pclk')):
            lines.extend([f'set_max_delay -datapath_only -from [get_clocks {{{first}}}] -to [get_clocks {{{last}}}] 8.0',
                          f'set_min_delay -from [get_clocks {{{first}}}] -to [get_clocks {{{last}}}] 0.0'])
    lines += ['# Retain historical camera pad/electrical attributes; directions follow actual new top.']
    for pin, attrs in sorted(camera_attributes(project).items()):
        for key, value in attrs.items():
            lines.append(f'define_attribute {{p:{pin}}} {{PAP_IO_{key}}} {{{value}}}')
    return ('\n'.join(lines)+'\n').encode('ascii')


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
    require(data == constraint_bytes(project, base), 'constraint differs outside exact camera derivation')
    text = data.decode('ascii')
    rows, original = {}, {}
    for source, output in ((text, rows), (paths.inside(project, base['Constraint']).read_text(), original)):
        for line in source.splitlines():
            match = PIN_ATTRIBUTE.fullmatch(line.strip())
            if match:
                pin, key, value = match.groups()
                require(key not in output.setdefault(pin, {}), 'duplicate FDC attribute')
                output[pin][key] = value
    require(len(original) == 114 and not CAM_PORTS & set(original), 'baseline exact114 contract differs')
    require(set(rows) == set(original) | CAM_PORTS and len(rows) == 128, 'exact128 pins required')
    require(all(rows[pin] == attrs for pin, attrs in original.items()), 'retained baseline pad/electrical attribute changed')
    require({p: rows[p] for p in CAM_PORTS} == camera_attributes(project), 'camera pad/electrical derivation changed')
    require(sum(pin.startswith('mem_') for pin in rows) == 71, 'DDR71 contract differs')
    require(len({attrs['LOC'] for attrs in rows.values()}) == len(rows), 'package pin collision')
    require(not re.search(r'^\s*(?:set_output_delay|set_clock_groups|set_false_path)\b', text, re.M),
            'new external output constraints or blanket exceptions forbidden')
    delays = re.findall(r'^set_input_delay.*$', text, re.M)
    require(delays == ['set_input_delay -clock camera_pclk -max 5.0 [get_ports {cam_data[*] cam_vsync cam_href}]',
                       'set_input_delay -clock camera_pclk -min 0.0 [get_ports {cam_data[*] cam_vsync cam_href}]'],
            'historical provisional input budgets changed')
    if check_top:
        ports = top_ports(paths.inside(project, TOP).read_text())
        require(set(ports) == set(rows), 'top/FDC128 pin set differs')
        require(all(ports[pin] == attrs['DIRECTION'] for pin, attrs in rows.items()), 'top/FDC direction differs')
    return {'PackagePins': 128, 'DDRPins': 71, 'CameraPins': 14, 'RetainedPins': 114,
            'UnchangedRetainedElectricalAttributes': True, 'CameraInputTimingProvisional': True,
            'ExternalIOAccepted': False, 'NoUARTPort': True, 'CameraD5': 'AA23'}


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
    manifest = {"Schema": "independent-camera-vga-output-source-closure-v1", "Target": TARGET,
                "Candidate": "CAM2 VGA RGB565 -> existing processing/DDR/output; independent TX; diagnostic only",
                "source_files": names, "SourceSHA256": source_hashes,
                "Constraint": FDC, "RouteConstraint": base["RouteConstraint"],
                "RouteConstraintSHA256": paths.sha(paths.inside(project, base["RouteConstraint"])),
                "BaseManifest": {"Path": BASE, "SHA256": BASE_SHA256},
                "RemovedBaselineSources": sorted(REMOVED), "AddedSources": list(ADDED),
                "SourceRoleRule": "IDF owns expanded DDR bodies; headers and constraints are not independent designs.",
                "DDRBodyComparison": ddr_body_comparison(project),
                "CameraInputDevelopment": True, "PhysicalInputExercised": False,
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
    require(manifest.get("Schema") == "independent-camera-vga-output-source-closure-v1"
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
    for name in ("board/processed_output_top.v", TOP):
        raw = paths.inside(project, name).read_bytes()
        start = b"    wire ddr_ref_clk,core_clk,ddr_init_done,ddr_pll_lock;"
        stop = b'    (* async_reg="true" *) reg [1:0] ref_reset'
        require(raw.count(start) == 1 and raw.count(stop) == 1, "DDR instance provenance anchors differ")
        chunks.append(raw[raw.index(start):raw.index(stop)])
    normal = [chunk.replace(b"\r\n", b"\n") for chunk in chunks]
    require(normal[0] == normal[1], "candidate changed DDR wiring/APB/inactive debug body")
    return {"BaselineTop": "board/processed_output_top.v", "CandidateTop": TOP,
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
    require(path.is_relative_to(Path(project).resolve()) or path.is_relative_to(TEMP_BUILD),
            "direct recipe path escaped project or exact camera temporary root")
    value = path.as_posix()
    paths.tcl_path(value)
    return value


def work_parent_allowed(project, work):
    """Allow only direct children of the three exact camera scratch roots."""
    work = Path(work).absolute()
    project = Path(project).resolve()
    roots = (project / "build/camera-vga-output", project / WORK_BUILD_RELATIVE, TEMP_BUILD)
    return (work == work.resolve() and work.parent in roots
            and work.parent == work.parent.resolve())


def prepare(project, work_dir, *, repo_alias="P:/", pds_shell="D:/pango/PDS_2023.2/bin/pds_shell.exe", maximum_seconds=1800):
    project = Path(project).resolve()
    require(type(maximum_seconds) is int and 60 <= maximum_seconds <= 7200, "external EDA deadline must be60..7200 seconds")
    roles = validate(project)
    work = Path(work_dir).absolute()
    require(work_parent_allowed(project, work) and work.is_dir() and not any(work.iterdir()),
            "fresh canonical direct child of project build/camera-vga-output, work/camera-vga-output or exact OS-temp/codex-camera-vga-output required")
    require(work.parent != TEMP_BUILD or repo_alias == "direct", "temporary camera work requires direct ASCII paths")
    alias = "direct" if repo_alias == "direct" else paths.validate_repo_alias(project, repo_alias)
    if alias == "direct":
        recipe_path(project, alias, project)
    tool = Path(pds_shell).resolve()
    require(tool.is_file(), "PDS shell executable must exist; preparation does not execute it")
    auxiliary = {MANIFEST: paths.sha(paths.inside(project, MANIFEST)), BASE: BASE_SHA256,
                 SELF.relative_to(PROJECT).as_posix(): paths.sha(SELF),
                 "tools/prepare_board1080_timing.py": paths.sha(Path(paths.__file__)),
                 RAW_FDC: RAW_FDC_SHA, RAW_PINS: RAW_PINS_SHA}
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
    plan = {"Schema": "independent-camera-vga-output-diagnostic-preparation-v1",
            "PreparedUTC": datetime.now(timezone.utc).isoformat(), "Scope": "PrepareOnlyNoEDA",
            "EDAExecuted": False, "HardwareAccessed": False, "BitstreamRequested": False,
            **{flag: False for flag in FALSE_FLAGS}, "Target": TARGET, "ProjectRoot": str(project),
            "WorkDirectory": str(work), "ScratchRoot": str(work.parent), "RepoAlias": alias, "AliasWorkDirectory": work_alias,
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
                "Camera input is a new candidate; no current camera capture or calibrated lens result is established."]}
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
