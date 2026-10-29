"""Exact, isolated Gamma + parity-hit pipeline candidate; never build/program.

Default is read-only validation. --stage exclusively creates the new candidate
files, and refuses to overwrite any of them. Stable source and helpers stay put.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "corrected_gamma_d5"
TARGET = "corrected_gamma_pipeline_d5"
INDEX_BITS = 5
PARITY = "rtl/experimental/ddr_pipeline_parity_cache.v"
COMPACT = "rtl/experimental/ddr_compact_neighbour_cache.v"
COMPACT_SHA256 = "da07e9ac7efa0ca53fd470c47b74039276de35069c5bb8f77ed8620565c2e531"
CACHE_FILES = {"parity": PARITY, "compact": COMPACT}
SERIAL = "rtl/experimental/ddr_pipeline_serial_cache.v"
FRAME = "rtl/experimental/pipeline_gamma_frame_engine.v"
VIDEO = "rtl/experimental/ddr_gamma_pipeline_video.v"
CALIBRATION = f"board/{TARGET}-calibration.vh"
ROTATION_DOMAIN = f"board/{TARGET}-rotation-domain.vh"
PARAMETER_MOVES = {"board/calibration-trial.vh": CALIBRATION,
                   "board/rotation-domain.vh": ROTATION_DOMAIN}
ANCHORS = {
    "board/corrected_gamma_d5.v": "e6bd1865a8972852b4eeaea13c8f735d3b49351f43809cbfcb12a1acea335399",
    "board/corrected_gamma_d5.fdc": "d03368bccb8704b491e7cc359cbe20b859bcb41c7c9c108475caac2ae07eae91",
    "board/corrected_gamma_d5-pins.json": "63e059c7126fbcf07fbb61e10a77981ab04cb350077a82c5151a8b4ae3c6e7a4",
    "board/corrected_gamma_d5-sources.json": "78579796dca4dd9cd3f3be608d38b8b85a6e8304c2bb83ffbe25b59ee9e7c4c2",
    "board/build-corrected_gamma_d5.tcl": "0d73ea25ba9580fec06b92f8257da5eb18eb9e464f5b5bba4add34bc80c01733",
    "rtl/experimental/adaptive_gamma_frame_engine.v": "6379b55ae259d68aab5447d41102f1c93f6cdf674c4994a12f8853a7bc1d5248",
    "rtl/experimental/ddr_gamma_video.v": "026a226fe9809c7842f056388385e0f1cde58eb0dd2fc22475dd313aacc99e46",
    PARITY: "280156b43a0814f7f99bae983132f6c18d85db9bc8771c4dd25bd0db6e5df094",
    SERIAL: "4c1341418a989f619558684cfaf80906c844264834882b715594b31337db9e9f",
}
CONTRACT = {
    "reference_target": BASE, "cache": PARITY, "fallback": SERIAL,
    "index_bits": INDEX_BITS, "fast_cache_bytes": 16384, "fallback_cache_bytes": 8192,
    "sampler_tag_bits": 25, "gamma_and_geometry_mask_preserved": True,
    "camera_d5_pad": "AA23", "uart_rx_pad": "B24", "pin_count": 130,
    "private_calibration_include": CALIBRATION, "private_rotation_domain_include": ROTATION_DOMAIN,
    "private_parameter_policy": "Current files must equal historical reference bytes. Later real-calibration generation may replace these private inputs with a newly bound profile and fresh simulation; never edit stable global includes.",
    "calibration_scope": "Historical reproducible VGA lens parameters only; new lens K/D pending real calibration",
    "hardware_performance_verified": False, "final_route_verified": False,
    "final_timing_required_before_bitstream": True,
    "limits": "Cache integration candidate; inherited baseline ownership/fault checks are preserved. This is not the newer guarded raw command/thermal-interlock target. No new lens quality, physical fps or resource saving claim.",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_one(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise ValueError("Expected exactly one clone edit: " + old)
    return text.replace(old, new)


def cache_layout(names=None):
    """Recognize exactly one fixed public cache from the owned source list."""
    if names is None:
        names = json.loads((ROOT / f"board/{TARGET}-sources.json").read_text())
    if not isinstance(names, list) or any(type(name) is not str for name in names):
        raise ValueError("Candidate source list must be a list of exact source paths")
    selected = [kind for kind, name in CACHE_FILES.items() if names.count(name) == 1]
    if len(selected) != 1 or sum(names.count(name) for name in CACHE_FILES.values()) != 1:
        raise ValueError("Need exactly one fixed parity/compact public cache")
    return selected[0]


def integration_contract(layout):
    if layout not in CACHE_FILES:
        raise ValueError("Cache layout is fixed to parity/compact at INDEX5")
    contract = dict(CONTRACT, cache_layout=layout)
    if layout == "compact":
        contract.update(cache=COMPACT, cache_sha256=COMPACT_SHA256, fallback=None,
                        fast_cache_bytes=8192, fallback_cache_bytes=0, burst_staging_bytes=256,
                        input_fifo_entries=2,
                        input_fifo_scope="registered xy/tag queue; public ready has no coordinate or inner-ready combinational dependency",
                        decoded_query_entries=1,
                        decoded_query_scope="elastic signed pixel-number/bounds/fraction/tag registers before live tag lookup and RAM address selection",
                        serial_source_compiled_but_unused=True,
                        cache_storage_layout="two shared 16-bit true-dual-port even/odd memories")
    return contract


def pre_bit_timing_gate():
    """Tcl-only fail-closed gate for this work directory's final report."""
    return r'''# Final saved-DB timing must pass before any SRAM file is generated.
set final_timing_path [file join [pwd] report_timing @TARGET@.rtr]
if {![file isfile $final_timing_path]} {
    error "Missing final timing report; refusing bitstream generation"
}
set final_timing_handle [open $final_timing_path r]
set final_timing_text [read $final_timing_handle]
close $final_timing_handle
set final_timing_summaries 0
set final_timing_passes 0
foreach final_timing_line [split $final_timing_text "\n"] {
    if {[regexp {^[ \t]*Design Summary[ \t]*:} $final_timing_line]} {
        incr final_timing_summaries
        if {[regexp {^[ \t]*Design Summary[ \t]*:[ \t]*All Constraints Met\.[ \t]*\r?$} $final_timing_line]} {
            incr final_timing_passes
        }
    }
}
if {$final_timing_summaries != 1 || $final_timing_passes != 1} {
    error "Final timing did not meet all constraints; refusing bitstream generation"
}
'''.replace("@TARGET@", TARGET)


def expected(parameters=None, layout="parity") -> dict[str, bytes]:
    if layout not in CACHE_FILES:
        raise ValueError("Cache layout is fixed to parity/compact at INDEX5")
    cache = CACHE_FILES[layout]
    if layout == "compact" and sha(ROOT / COMPACT) != COMPACT_SHA256:
        raise ValueError("Frozen compact cache source changed")
    for name, digest in ANCHORS.items():
        if sha(ROOT / name) != digest:
            raise ValueError("Frozen reference changed: " + name)
    text = lambda n: (ROOT / n).read_text(encoding="utf-8")
    frame = replace_one(text("rtl/experimental/adaptive_gamma_frame_engine.v"),
                        "module adaptive_gamma_frame_engine #(", "module pipeline_gamma_frame_engine #(")
    frame = replace_one(frame, ".INDEX_BITS(4)", ".INDEX_BITS(5)")
    video = replace_one(text("rtl/experimental/ddr_gamma_video.v"),
                        "module ddr_gamma_video #(", "module ddr_gamma_pipeline_video #(")
    video = replace_one(video, "adaptive_gamma_frame_engine #(", "pipeline_gamma_frame_engine #(")
    top = replace_one(text(f"board/{BASE}.v"), "module " + BASE + "(", "module " + TARGET + "(")
    top = replace_one(top, "ddr_gamma_video #(", "ddr_gamma_pipeline_video #(")
    for old, new in PARAMETER_MOVES.items():
        top = replace_one(top, "/" + old + '"', "/" + new + '"')
    mapping = {f"board/{BASE}{s}": f"board/{TARGET}{s}" for s in (".v", ".fdc", "-pins.json", "-sources.json")}
    mapping[f"board/build-{BASE}.tcl"] = f"board/build-{TARGET}.tcl"
    mapping.update({"rtl/experimental/adaptive_gamma_frame_engine.v": FRAME,
                    "rtl/experimental/ddr_gamma_video.v": VIDEO,
                    "rtl/experimental/ddr_adaptive_cache.v": cache})
    mapping.update(PARAMETER_MOVES)
    names = [mapping.get(n.replace("\\", "/"), n.replace("\\", "/"))
             for n in json.loads(text(f"board/{BASE}-sources.json"))]
    names.insert(names.index(cache) + 1, SERIAL)
    if len(names) != len(set(names)):
        raise ValueError("Duplicate source in new candidate")
    tcl = text(f"board/build-{BASE}.tcl")
    for old, new in mapping.items():
        tcl = tcl.replace("/" + old + "}", "/" + new + "}")
    tcl = replace_one(tcl, "-top_module " + BASE, "-top_module " + TARGET)
    tcl = replace_one(tcl, "add_design {D:/English/FPGA/distortion/" + cache + "}",
                      "add_design {D:/English/FPGA/distortion/" + cache + "}\n" +
                      "add_design {D:/English/FPGA/distortion/" + SERIAL + "}")
    timing = "report_timing -force_to_run -max_path 5\n"
    tcl = replace_one(tcl, timing, timing + pre_bit_timing_gate())
    return {
        FRAME: frame.encode(), VIDEO: video.encode(), f"board/{TARGET}.v": top.encode(),
        f"board/{TARGET}.fdc": (ROOT / f"board/{BASE}.fdc").read_bytes(),
        f"board/{TARGET}-pins.json": (ROOT / f"board/{BASE}-pins.json").read_bytes(),
        f"board/{TARGET}-sources.json": (json.dumps(names, indent=2) + "\n").encode(),
        f"board/build-{TARGET}.tcl": tcl.encode(),
        CALIBRATION: parameters[CALIBRATION] if parameters else (ROOT / "board/calibration-trial.vh").read_bytes(),
        ROTATION_DOMAIN: parameters[ROTATION_DOMAIN] if parameters else (ROOT / "board/rotation-domain.vh").read_bytes(),
    }


def real_parameters(profile_path, audit_path, development_only=False):
    """Accept the existing real-calibration and full numerical-audit contracts."""
    profile_path, audit_path = Path(profile_path).resolve(), Path(audit_path).resolve()
    profile = json.loads(profile_path.read_text(encoding="utf-8-sig"))
    audit = json.loads(audit_path.read_text(encoding="utf-8-sig"))
    if type(development_only) is not bool:
        raise ValueError("development_only must be an explicit boolean")
    ready = (profile.get("passed") is True and profile.get("candidate_ready_for_profile_review") is True and
             profile.get("independent_spatial_coverage_passed") is True and profile.get("development_only") is not True)
    if (profile.get("model") != "fisheye" or profile.get("provenance") != "real_chessboard_captures" or
            profile.get("image_size") != [640, 480] or
            (not ready and not (development_only and profile.get("development_only") is True))):
        raise ValueError("need an independently held-out, coverage-passed real VGA fisheye profile")
    identity = {k: profile.get(k) for k in ("camera_id", "lens_id", "profile_id", "capture_mode_id")}
    if any(not isinstance(v, str) or not v.strip() for v in identity.values()):
        raise ValueError("profile must bind camera/lens/profile/capture-mode identity")
    audit_ready = audit.get("candidate_ready_for_profile_review") is True
    development_audit = (development_only and profile.get("development_only") is True and
                         audit.get("candidate_ready_for_profile_review") is False and
                         audit.get("source_profile_development_only") is True)
    if (audit.get("passed") is not True or not (development_audit if development_only else audit_ready) or
            audit.get("synthetic_input") is not False or audit.get("provenance") != "real_chessboard_captures" or
            audit.get("sample_stride") != 1 or audit.get("full_requested_frames_checked") is not True or
            audit.get("source_image_size") != [640,480] or audit.get("output_size") != [640,480] or
            audit.get("source_profile_file_sha256", "").lower() != sha(profile_path) or
            audit.get("profile_sha256") != hashlib.sha256(json.dumps(profile, sort_keys=True, allow_nan=False).encode()).hexdigest() or
            any(audit.get(k) != identity[k] for k in ("camera_id", "profile_id")) or
            audit.get("existing_board_radius_guard_applied") is not False):
        raise ValueError("mapping audit is not full-frame and bound to this real profile")
    rows = audit.get("frames", [])
    angles = {round(float(row.get("angle_deg", -1)) % 360, 6) for row in rows}
    criteria = audit.get("criteria", {})
    if (not set(range(0,360,30)).issubset(angles) or not rows or
            not isinstance(criteria.get("maximum_coordinate_error_px"), (int,float)) or
            isinstance(criteria.get("maximum_coordinate_error_px"), bool) or
            not 0 < criteria["maximum_coordinate_error_px"] <= .25 or
            any(row.get("coordinates_checked") != 307200 or row.get("numerical_gates_passed") is not True or
                row.get("fixed_point_invalid_coordinates") != 0 or row.get("fixed_point_folded_samples") != 0 or
                row.get("reference_folded_samples") != 0 for row in rows)):
        raise ValueError("need full twelve-angle quarter-pixel/no-fold/no-overflow audit")
    config = audit.get("integer_config")
    if (not isinstance(config, list) or len(config) != 13 or
            any(type(v) is not int or not -(1 << (bits-1)) <= v < (1 << (bits-1))
                for v,bits in zip(config,[24]*6+[32]*7)) or config[11:] != [0,0]):
        raise ValueError("audit does not fit the existing radial-only fixed-point register contract")
    guard = audit.get("required_radius_guard_q22_for_checked_rays")
    if type(guard) is not int or not 0 < guard < (1 << 31) or guard != max(row["maximum_normalized_radius_squared_q22"] for row in rows)+2:
        raise ValueError("new radius guard must come from this audit, not the old lens")
    names = "OUT_CX OUT_CY SRC_CX SRC_CY SRC_FX SRC_FY INV_FX INV_FY K1 K2 K3 P1 P2".split()
    header = ("// Actual-data DEVELOPMENT ONLY fit; calibration not accepted.\n" if development_only else
              "// Real four-coefficient fisheye profile; bounded Brown approximation, not exact fisheye.\n")
    header += "".join(f"localparam signed [{bits-1}:0] CAL_{name}={bits}'sh{value&((1<<bits)-1):0{bits//4}x};\n"
                      for name,value,bits in zip(names,config,[24]*6+[32]*7))
    domain = f"// Radius covers explicitly audited rays/angles only; outside is masked.\nlocalparam ROT_MAX_R2_Q22=32'd{guard};\n"
    parameters = {CALIBRATION: header.encode(), ROTATION_DOMAIN: domain.encode()}
    binding = {"schema": 1, "Target": TARGET, "ParameterOrigin": ("actual_data_exploratory_fisheye_brown_approximation"
               if development_only else "real_calibrated_fisheye_brown_approximation"),
               "Profile": str(profile_path), "ProfileSHA256": sha(profile_path),
               "MappingAudit": str(audit_path), "MappingAuditSHA256": sha(audit_path),
               "Identity": identity, "ImageSize": [640,480], "IntegerConfig": config, "RadiusGuardQ22": guard,
               "PrivateParameterSHA256": {n: hashlib.sha256(v).hexdigest() for n,v in parameters.items()},
               "DevelopmentOnly": development_only, "CalibrationAccepted": bool(ready and not development_only),
               "HardwareReleaseAllowed": False, "OpticalAcceptanceComplete": False,
               "Limits": ("Actual-data exploratory model approximation; calibration remains unaccepted. " if development_only else
                          "Real calibration and model approximation, pending same-source RTL/final build/held-out optical acceptance. ")+
                         "Audited angles/rays do not prove a continuous all-angle supremum or measured 200-degree coverage."}
    return parameters, binding


def load_profile_binding(path):
    path = Path(path).resolve()
    record = json.loads(path.read_text(encoding="utf-8-sig"))
    parameters, expected_record = real_parameters(record["Profile"], record["MappingAudit"],record.get("DevelopmentOnly",False))
    if record != expected_record:
        raise ValueError("profile binding changed or does not match its profile/audit")
    return parameters, {"Path": str(path), "SHA256": sha(path), **record}


def verify_clone(profile_binding=None) -> dict:
    parameters, bound = load_profile_binding(profile_binding) if profile_binding else (None, None)
    layout = cache_layout()
    for name, payload in expected(parameters, layout).items():
        if (ROOT / name).read_bytes() != payload:
            raise ValueError("Candidate is not the exact minimal clone: " + name)
    names = json.loads((ROOT / f"board/{TARGET}-sources.json").read_text())
    pins = json.loads((ROOT / f"board/{TARGET}-pins.json").read_text())
    if len(pins) != 130 or len(set(pins.values())) != 130 or pins.get("cam_data[5]") != "AA23" or pins.get("uart_rxd") != "B24":
        raise ValueError("Stable full Gamma pin contract changed")
    if "rtl/experimental/ddr_adaptive_cache.v" in names or "rtl/experimental/ddr_pipeline_hit_cache.v" in names:
        raise ValueError("Multiple public cache implementations selected")
    contract = integration_contract(layout)
    if bound:
        contract.update(calibration_scope=("Actual-data DEVELOPMENT ONLY fit; calibration not accepted" if bound["DevelopmentOnly"] else
                                           "Real calibrated profile, bounded Brown approximation; optical and hardware acceptance pending"),
                        private_parameter_policy="Explicit SHA-bound real profile/audit; new simulation required", parameter_origin=bound["ParameterOrigin"])
    references = dict(ANCHORS)
    if layout == "compact":
        references[COMPACT] = COMPACT_SHA256
    result = {"Target": TARGET, "CacheLayout": layout, "IntegrationContract": contract,
            "SourceSHA256": {n: sha(ROOT / n) for n in names},
            "ReferenceSHA256": references, "HardwareAccessed": False, "PDSAccessed": False}
    if bound:
        result["ProfileBinding"] = bound
    return result


def stage_cache_layout(layout, profile_binding=None):
    """Switch only the owned list/Tcl; keep INDEX5, top and private bytes."""
    before = verify_clone(profile_binding)
    parameters, _ = load_profile_binding(profile_binding) if profile_binding else (None, None)
    files = expected(parameters, layout)
    owned = (f"board/{TARGET}-sources.json", f"board/build-{TARGET}.tcl")
    for name, payload in files.items():
        if name not in owned and (ROOT / name).read_bytes() != payload:
            raise ValueError("Cache switch must not change another candidate file: " + name)
    # Validate everything before either narrowly owned file is written.
    if before["CacheLayout"] != layout:
        for name in owned:
            (ROOT / name).write_bytes(files[name])
    return verify_clone(profile_binding)


def stage_profile(profile_path, audit_path, output, previous_binding=None, development_only=False):
    """Only candidate-private parameters change; existing binding/evidence stays."""
    verify_clone(previous_binding)
    output = Path(output).resolve()
    approved = (ROOT/"build/offline-20261024").resolve()
    if not output.is_relative_to(approved) or not output.parent.is_dir() or output.exists():
        raise ValueError("binding must be a new file in an existing approved scratch directory")
    parameters, binding = real_parameters(profile_path, audit_path,development_only)
    # No stable include or previous result is touched. The human supplied the
    # explicit new profile/audit via --stage-profile; default remains read-only.
    for name,payload in parameters.items():
        (ROOT/name).write_bytes(payload)
    with output.open("x",encoding="utf-8") as stream:
        json.dump(binding, stream, indent=2, allow_nan=False);stream.write("\n")
    return verify_clone(output)


def stage() -> dict:
    files = expected()
    if any((ROOT / n).exists() for n in files):
        raise ValueError("Refuse to overwrite candidate files; default command validates existing files")
    for name, payload in files.items():
        if not (ROOT / name).parent.is_dir():
            raise ValueError("Use existing source directories only")
        with (ROOT / name).open("xb") as out:
            out.write(payload)
    return verify_clone()


def isolate_parameters() -> dict:
    """One explicit migration of this new candidate; preserve the stable tree."""
    files = expected()
    top_name, list_name = f"board/{TARGET}.v", f"board/{TARGET}-sources.json"
    old_top = files[top_name]
    old_names = json.loads(files[list_name])
    for old, new in PARAMETER_MOVES.items():
        old_top = old_top.replace(("/" + new + '"').encode(), ("/" + old + '"').encode())
        old_names = [old if n == new else n for n in old_names]
    previous = {top_name: old_top, list_name: (json.dumps(old_names, indent=2) + "\n").encode()}
    if any((ROOT/n).exists() for n in (CALIBRATION, ROTATION_DOMAIN)):
        raise ValueError("Private parameter files already exist; default command validates")
    for name, payload in files.items():
        if name not in (CALIBRATION, ROTATION_DOMAIN) and (ROOT/name).read_bytes() != previous.get(name, payload):
            raise ValueError("Only the original frozen new candidate may migrate: " + name)
    for name in (CALIBRATION, ROTATION_DOMAIN):
        with (ROOT/name).open("xb") as out:
            out.write(files[name])
    # These two are exclusively owned new candidate files, verified byte-for-byte
    # immediately above. No stable source, global include or shared helper edits.
    for name in (top_name, list_name):
        (ROOT/name).write_bytes(files[name])
    return verify_clone()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    choices = parser.add_mutually_exclusive_group()
    choices.add_argument("--stage", action="store_true")
    choices.add_argument("--isolate-parameters", action="store_true")
    choices.add_argument("--stage-profile", action="store_true")
    choices.add_argument("--stage-cache-layout", choices=tuple(CACHE_FILES))
    parser.add_argument("--profile-binding", type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--mapping-audit", type=Path)
    parser.add_argument("--binding-output", type=Path)
    parser.add_argument("--development-profile", action="store_true",help="explicit actual-data exploratory fit, never calibration/hardware acceptance")
    args = parser.parse_args()
    if args.stage_profile and not all((args.profile,args.mapping_audit,args.binding_output)):
        parser.error("--stage-profile requires --profile, --mapping-audit and --binding-output")
    if args.development_profile and not args.stage_profile:parser.error("--development-profile is only valid with --stage-profile")
    result = (stage_profile(args.profile,args.mapping_audit,args.binding_output,args.profile_binding,args.development_profile) if args.stage_profile
              else stage_cache_layout(args.stage_cache_layout,args.profile_binding) if args.stage_cache_layout
              else stage() if args.stage else isolate_parameters() if args.isolate_parameters else verify_clone(args.profile_binding))
    print(json.dumps({"passed": True, "target": result["Target"],
                      "source_count": len(result["SourceSHA256"]), "contract": result["IntegrationContract"]}))
