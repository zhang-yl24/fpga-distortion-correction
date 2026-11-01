"""Replay current calibrated camera frames through unmodified processing/output RTL.

No device/PDS is accessed. Explicit f240 source-bound Brown configuration; gamma
bypassed. Coordinates and actual scan pixels match independent integer oracles.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
import zlib

import numpy as np
from PIL import Image

import generate_1080_core_vectors as cpu
from calibrate_fisheye_profile import _decode_bound_capture
import cv2
from run_gamma_pipeline_d5_sim import tool
from simulation_tools import prepare_compile_sources, resolve_vivado_bin, verify_compile_sources

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "work/calibrated-camera-vga"
SESSION = ROOT / "work/camera-vga-calibration-20261031"
PACKAGE = ROOT / "results/camera-vga-calibration-20261101-a"
PACKAGE_SHA = "cec6b65f0e7629ff8d9a012a288e28b576329cc330379207801bbc964e872a58"
FRAMES = ("held-05", "held-06")
COMPILE = (
    "rtl/mul32_pipe.v", "rtl/pixel_inverse_rotation.v", "rtl/bounded_brown_inverse_mapper.v",
    "rtl/bilinear_rgb.v", "rtl/ddr_read_arbiter.v", "rtl/ddr_video_reader.v", "rtl/video_async_fifo.v",
    "rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v",
    "rtl/experimental/ddr_remap_sample_scatter4_rowpipe.v",
    "rtl/experimental/rotated_remap_core_gamma_scatter4.v",
    "rtl/experimental/adaptive_gamma_stream.v", "rtl/experimental/adaptive_gamma_tagged.v",
    "rtl/experimental/ddr_adaptive_result_writer.v", "rtl/experimental/pipeline_gamma_frame_engine_1080_scatter4.v",
    "rtl/experimental/ddr_video_output_1080_board.v", "tests/tb_calibrated_camera_output.sv",
)
HEADERS = ("rtl/experimental/gamma_curves.vh", "rtl/video_crc32.vh")
HELPERS = ("tools/run_calibrated_camera_output_sim.py", "tools/generate_1080_core_vectors.py",
           "tools/calibrate_fisheye_profile.py", "tools/generate-brown-vectors.py",
           "model/reference.py", "tools/fisheye_forward_inverse.py", "tools/stereo_fisheye_calibrate.py", "tools/calibrate.py", "tools/wideangle_mapping_audit.py", "tools/simulation_tools.py", "tools/run_gamma_pipeline_d5_sim.py")
MARKER = "PASS calibrated camera output:"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def crc(words):
    return f"{zlib.crc32(np.asarray(words, dtype='<u2').tobytes()) & 0xffffffff:08X}"


def write_mem(path, words, *, beats=False):
    with Path(path).open("x", encoding="ascii", newline="\n") as stream:
        if beats:
            payload = np.asarray(words, dtype="<u2").tobytes()
            stream.writelines(f"{int.from_bytes(payload[i:i+32], 'little'):064x}\n" for i in range(0, len(payload), 32))
        else:
            stream.writelines(f"{int(word):04x}\n" for word in np.asarray(words).ravel())


def model_inputs():
    """Use exactly the frozen numerical candidate, not an arbitrary JSON claim."""
    manifest = PACKAGE / 'manifest.json'
    if sha(manifest) != PACKAGE_SHA:
        raise ValueError('calibration package manifest changed')
    files = {v['Path']: v for v in load(manifest)['Files']}
    watched = {str(manifest): sha(manifest)}
    values = {}
    for name in ('profiles/fisheye-profile-a.json', 'profiles/validation-freeze-a.json',
                 'reports/brown-mapping-f240-a.json'):
        path = SESSION / name
        frozen = PACKAGE / name
        if sha(path) != files[name]['SHA256'] or sha(frozen) != files[name]['SHA256']:
            raise ValueError('current calibration input differs from frozen package: '+name)
        watched[str(path)] = sha(path); watched[str(frozen)] = sha(frozen)
        values[name] = load(path)
    profile = values['profiles/fisheye-profile-a.json']
    mapping = values['reports/brown-mapping-f240-a.json']
    freeze = values['profiles/validation-freeze-a.json']
    expected = [81792, 61312, 82234, 64062, 40848, 40921, 4473924, 4473924,
                -674237, 121875, -11577, 0, 0]
    if (mapping.get('passed') is not True or mapping.get('full_requested_frames_checked') is not True
            or mapping.get('source_image_size') != [640, 480] or mapping.get('output_size') != [640, 480]
            or mapping.get('integer_config') != expected
            or mapping.get('required_radius_guard_q22_for_checked_rays') != 11610104
            or mapping.get('source_profile_file_sha256') != sha(SESSION/'profiles/fisheye-profile-a.json')
            or len(mapping.get('frames', [])) != 1 or mapping['frames'][0].get('angle_deg') != 0
            or profile.get('candidate_ready_for_profile_review') is not True
            or profile.get('provenance') != 'real_chessboard_captures'):
        raise ValueError('only the reviewed current VGA f240 zero-angle model is supported')
    visibility = profile['model_scope']['physical_visibility']['record']
    if (visibility['FullFrameCoverageClaimAllowed'] is not False
            or visibility['ExcludedCoverageCells'] != [[2, 2]]):
        raise ValueError('physical visibility restriction must remain explicit')
    for name, digest in mapping['source_sha256'].items():
        path = ROOT / name.replace('\\', '/')
        if sha(path) != digest:
            raise ValueError('frozen mapping oracle source changed')
        watched[str(path)] = digest
    return profile, mapping, freeze, watched


def fixed_coordinates(config, guard):
    yy, xx = np.indices((480, 640), dtype=np.int64)
    sx, sy, bad, r2 = cpu.project_integer(xx*256, yy*256, config)
    mask = bad | (r2 > guard) | (sx <= -256) | (sy <= -256) | (sx >= 640*256) | (sy >= 480*256)
    scalar = cpu.scalar_oracle()
    checks = 0
    for y in np.unique(np.linspace(0, 479, 13, dtype=int)):
        for x in np.unique(np.linspace(0, 639, 17, dtype=int)):
            x0, y0, invalid = scalar.project(int(x)*256, int(y)*256, config)
            if (x0, y0, bool(invalid)) != (int(sx[y, x]), int(sy[y, x]), bool(bad[y, x])):
                raise ValueError('independent scalar/vector mapper disagreement')
            checks += 1
    if np.any(mask) or int(r2.max())+2 != guard:
        raise ValueError('current f240 all-valid geometry/guard differs from audited mapping')
    return sx, sy, bad | (r2 > guard), mask, {
        'MaskedPixels': int(mask.sum()), 'ArithmeticInvalidPixels': int(bad.sum()),
        'MaximumRadiusSquaredQ22': int(r2.max()), 'ScalarCoordinateCrosschecks': checks}


def fixtures(work):
    profile, mapping, freeze, watched = model_inputs()
    config = mapping['integer_config']; guard = mapping['required_radius_guard_q22_for_checked_rays']
    headers = [f'localparam integer VEC_WIDTH=640,VEC_HEIGHT=480,VEC_RADIUS_GUARD_Q22={guard};']
    for name, value in zip(cpu.NAMES, config):
        bits = 24 if name in cpu.NAMES[:6] else 32
        headers.append(f"localparam signed [{bits-1}:0] VEC_{name}={bits}'sh{value & ((1<<bits)-1):0{bits//4}x};")
    (work/'config.vh').write_text('\n'.join(headers)+'\n', encoding='ascii', newline='\n')
    sx, sy, invalid, mask, statistics = fixed_coordinates(config, guard)
    packed_coordinates = ((invalid.astype(np.uint64) << 48)
                          | ((sx.astype(np.uint64) & 0xffffff) << 24)
                          | (sy.astype(np.uint64) & 0xffffff))
    with (work/'coordinates.mem').open('x', encoding='ascii', newline='\n') as out:
        out.writelines(f'{int(value):013x}\n' for value in packed_coordinates.ravel())
    selected = {v['ViewID']: v for v in freeze['SelectedViews']}
    records, goldens = [], []
    for index, view_id in enumerate(FRAMES):
        selected_view = selected[view_id]
        quality_path = Path(selected_view['QualityPath'])
        if sha(quality_path) != selected_view['QualitySHA256']:
            raise ValueError('selected current capture quality file changed')
        quality = load(quality_path)
        if (quality['warnings'] != [] or quality['complete_board_detected'] is not True
                or quality['manifest_view_candidate']['view_id'] != view_id
                or quality['manifest_view_candidate']['split'] != 'held_out'):
            raise ValueError('current source is not the selected complete held-out capture')
        metadata = Path(quality['metadata_path']); image_path = Path(quality['image_path']).resolve()
        if sha(image_path) != quality['image_sha256']:
            raise ValueError('source PNG hash changed')
        image = cv2.imdecode(np.fromfile(image_path, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError('source PNG cannot be read')
        capture = _decode_bound_capture(quality['manifest_view_candidate'], profile,
                                        metadata.parent, image, image_path)
        if capture['physical_capture_record'] is not True:
            raise ValueError('physical native raw source required')
        raw = Path(capture['raw_path']); source = np.frombuffer(raw.read_bytes(), dtype='<u2').reshape(480, 640)
        # No RTL output or OpenCV interpolator enters this exact integer golden.
        sampled = cpu.remap_fixed(cpu.expand565(source), sx/256., sy/256.)
        expected = np.where(mask, 0, cpu.pack565(sampled)).astype(np.uint16)
        write_mem(work/f'source{index}.mem', source, beats=True)
        write_mem(work/f'expected{index}.mem', expected)
        Image.fromarray(cpu.expand565(source)).save(work/f'frame{index+1}-source.png')
        Image.fromarray(cpu.expand565(expected)).save(work/f'frame{index+1}-expected.png')
        record = {'FrameID': index+1, 'ViewID': view_id, 'CaptureTransactionID': selected_view['FrameID'],
            'Path': str(raw), 'SHA256': sha(raw), 'Metadata': str(metadata), 'MetadataSHA256': sha(metadata),
            'Image': str(image_path), 'ImageSHA256': sha(image_path),
            'QualityPath': str(quality_path), 'QualitySHA256': sha(quality_path),
            'SourceCRC32': crc(source), 'ExpectedCRC32': crc(expected), 'GammaMode': 0,
            'GammaEnabled': False, 'Statistics': statistics, 'CaptureBinding': capture}
        if record['SourceCRC32'] != selected_view['CRC32']:
            raise ValueError('source CRC differs from selected physical frame')
        for path in (raw, metadata, image_path, quality_path):watched[str(path)] = sha(path)
        records.append(record); goldens.append(expected)
    if records[0]['SourceCRC32'] == records[1]['SourceCRC32'] or records[0]['ExpectedCRC32'] == records[1]['ExpectedCRC32']:
        raise ValueError('new reused-bank epoch must have distinct real source and output pixels')
    for filename, key in (('source-crcs.mem', 'SourceCRC32'), ('expected-crcs.mem', 'ExpectedCRC32')):
        (work/filename).write_text('\n'.join(v[key] for v in records)+'\n', encoding='ascii', newline='\n')
    model = {'IntegerConfig': config, 'RadiusGuardQ22': guard, 'OutputK': mapping['output_K'],
             'AngleDegrees': 0, 'GammaEnabled': False, 'PhysicalVisibility': profile['model_scope']['physical_visibility'],
             'ProfilePath': str(SESSION/'profiles/fisheye-profile-a.json'),
             'ProfileSHA256': sha(SESSION/'profiles/fisheye-profile-a.json'),
             'MappingPath': str(SESSION/'reports/brown-mapping-f240-a.json'),
             'MappingSHA256': sha(SESSION/'reports/brown-mapping-f240-a.json')}
    return records, watched, goldens, model

def run(workdir, maximum_seconds):
    work = Path(workdir).resolve()
    if not work.is_relative_to(BASE.resolve()) or work == BASE.resolve():
        raise ValueError("workdir must be a new child of work/calibrated-camera-vga")
    if not 30 <= maximum_seconds <= 1800:
        raise ValueError("whole native run bound must be30..1800 seconds")
    work.mkdir(parents=True, exist_ok=False)
    source_hashes = {name: sha(ROOT/name) for name in (*COMPILE, *HEADERS, *HELPERS)}
    report = {"Passed": False, "StartedUtc": datetime.now(timezone.utc).isoformat(), "MaximumSeconds": maximum_seconds,
              "HardwareAccessed": False, "PDSAccessed": False, "PhysicalInputExercised": False,
              "CurrentCameraVerified": False, "CalibrationNumericalProfileBound": True, "CalibrationAccepted": False, "HardwareReleaseAllowed": False,
              "SourcePreloadedInModeledDDR": True, "RealOutputAsyncFIFO": True, "RTLResultUsedForGolden": False,
              "Width": 640, "Height": 480, "FrameCount": 2, "CoreClockHz": 125000000, "PixelClockHz": 25000000,
              "AdaptedRaster": {"HT": 800, "VT": 525, "HS": 96, "VS": 2, "X0": 144, "Y0": 35},
              "SourceSHA256": source_hashes, "Commands": [], "OutputDirectory": str(work),
              "Model": "Current source-bound f240 calibrated Brown approximation, exact zero-angle rotation, gamma bypass",
              "Limits": "Current captured CAM2 raw images and calibrated f240 model; source starts in modeled DDR. No live ingress, physical DDR/HDMI mode, fps, timing or board acceptance. Bench owns serialized source/result leases; production bank manager and concurrency are not exercised. Right-bottom physical obstruction remains outside optical acceptance."}
    watched = {}; fixture_hashes = {}
    deadline = time.monotonic()+maximum_seconds
    try:
        records, watched, expected, model_binding = fixtures(work)
        report["CurrentCameraFrames"] = records
        report["ModelBinding"] = model_binding
        report["IntegerConfig"] = model_binding["IntegerConfig"]
        report["RadiusGuardQ22"] = model_binding["RadiusGuardQ22"]
        fixture_hashes = {p.name: sha(p) for p in work.iterdir() if p.is_file()}
        report["FixtureSHA256"] = fixture_hashes
        compiled, bindings = prepare_compile_sources(ROOT, COMPILE, HEADERS, work)
        report["RelocatedSources"] = bindings
        bin_dir = resolve_vivado_bin(ROOT.parent)
        stages = (("xvlog.bat", ["--sv", *map(str, compiled)], "compile"),
                  ("xelab.bat", ["tb_calibrated_camera_output", "-s", "calibrated_camera_output"], "elaborate"),
                  ("xsim.bat", ["calibrated_camera_output", "-runall", "-log", "simulation.log"], "simulate"))
        for executable, argv, stage in stages:
            command = {"Stage": stage, "NativeArgv": [str(bin_dir/executable), *argv], "ReturnCode": None}
            report["Commands"].append(command)
            tool(bin_dir, executable, argv, work, deadline, stage)
            command["ReturnCode"] = 0
        log = (work/"simulation.log").read_text(encoding="utf-8", errors="replace")
        if MARKER not in log or "$finish called" not in log or re.search(r"(?im)^\s*(?:fatal|error):", log):
            raise ValueError("full replay completion marker absent or RTL error")
        summary = load(work/"summary.json")
        checks = {"passed": True, "frames_processed": 2, "frames_unique_scanned": 2, "pixels_compared": 614400, "coordinates_compared": 614400,
                  "source_bank_reuses": 1, "result_bank_reuses": 1, "bank_releases": 2,
                  "result_beats": 38400, "display_read_beats": 38400, "underflows": 0, "crc_mismatches": 0, "final_drain": True}
        if any(type(summary.get(k)) is not type(v) or summary.get(k) != v for k, v in checks.items()):
            raise ValueError("all-frame processing/real pixel scan/epoch/drain contract failed")
        if any(type(summary.get(k)) is not int or summary[k] <= 0 for k in ("aw_stall_cycles", "w_stall_cycles", "ar_stall_cycles", "fifo_peak")):
            raise ValueError("DDR/FIFO pressure was not exercised")
        with (work/"frames.csv").open(encoding="ascii", newline="") as stream:
            rows = list(csv.DictReader(stream))
        if len(rows) != 2:
            raise ValueError("missing replay frame rows")
        for item, row in zip(records, rows):
            if (int(row["frame_id"]) != item["FrameID"] or int(row["source_epoch"]) != item["FrameID"]
                    or int(row["result_epoch"]) != item["FrameID"] or int(row["pixels"]) != 307200
                    or row["source_crc32"].upper() != item["SourceCRC32"]
                    or any(row[k].upper() != item["ExpectedCRC32"] for k in ("result_crc32", "reader_crc32", "scan_crc32"))
                    or not int(row["start_cycle"]) < int(row["process_done_cycle"]) < int(row["release_cycle"])):
                raise ValueError("per-frame source/result/read/scan CRC or event order differs")
        actual = np.loadtxt(work/"scan-pixels.mem", dtype=np.uint16, converters={0: lambda value: int(value, 16)}, ndmin=1)
        if actual.shape != (614400,):
            raise ValueError("actual pixel dump is incomplete")
        for index, golden in enumerate(expected):
            pixels = actual[index*307200:(index+1)*307200].reshape(480, 640)
            if not np.array_equal(pixels, golden) or crc(pixels) != records[index]["ExpectedCRC32"]:
                raise ValueError("independent post-run actual DE/RGB pixel comparison failed")
            Image.fromarray(cpu.expand565(pixels)).save(work/f"frame{index+1}-actual-scan.png")
        verify_compile_sources(ROOT, COMPILE, HEADERS, work, bindings)
        report.update(Passed=True, Summary=summary, Frames=rows, ActualDERGBScanned=True,
                      PassLines=[line for line in log.splitlines() if line.startswith(("PASS", "REPLAY_FRAME_PASS"))])
    except (Exception, KeyboardInterrupt) as error:
        report["Error"] = type(error).__name__+": "+str(error)
    finally:
        after = {name: sha(ROOT/name) for name in source_hashes}
        report["SourceSHA256After"] = after
        report["InputSHA256"] = watched
        report["InputSHA256After"] = {name: sha(name) for name in watched}
        report["FixtureSHA256After"] = {name: sha(work/name) for name in fixture_hashes}
        if after != source_hashes or report["InputSHA256After"] != watched or report["FixtureSHA256After"] != fixture_hashes:
            report.update(Passed=False, SourceOrInputDrift=True)
        report["FinishedUtc"] = datetime.now(timezone.utc).isoformat()
        report["LogSHA256"] = {p.name: sha(p) for p in work.glob("*.log")}
        report["ResultSHA256"] = {p.name: sha(p) for p in work.iterdir() if p.is_file() and p.name in ("frames.csv", "summary.json", "scan-pixels.mem", "frame1-actual-scan.png", "frame2-actual-scan.png")}
        (work/"calibrated-camera-output-simulation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"Passed": report["Passed"], "Error": report.get("Error"), "Report": str(work/"calibrated-camera-output-simulation.json")}, ensure_ascii=False))
    return 0 if report["Passed"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=int, default=900)
    args = parser.parse_args()
    return run(args.workdir, args.maximum_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
