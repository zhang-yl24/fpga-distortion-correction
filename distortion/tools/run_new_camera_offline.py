"""Run CPU-only new-lens checks and retain a source-bound local report.

Only an existing approved work directory is accepted. This invokes Python
reference tests and file audits, never PDS, UART, JTAG or a download command.
Synthetic profiles remain labelled synthetic and can never release hardware.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
TEST_NAMES = (
    'reference', 'calibrate', 'host_protocol', 'frame_protocol',
    'slanted_edge_analysis', 'grid_straightness', 'chessboard_sharpness',
    'gamma_triplets', 'native_optical_audit', 'pds_source_manifest',
    'completed_angle_coverage', 'session_capture_scope', 'host_cli',
    'camera_mode_preflight', 'wideangle_mapping_audit', 'stereo_fisheye_calibrate',
    'camera_eye_pin_audit', 'native_camera_capture', 'calibrate_fisheye_profile',
    'program_native_raw',
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, required=True,
                        help='existing, user-approved scratch directory inside distortion/build')
    parser.add_argument('--output', type=Path, required=True,
                        help='new report file in existing distortion/output/project')
    parser.add_argument('--rtl-report', type=Path,
                        help='optional existing raw capture simulation report; verify hashes and replay its synthetic stream')
    args = parser.parse_args()
    work, output = args.workdir.resolve(), args.output.resolve()
    build = (ROOT/'distortion/build').resolve()
    project = (ROOT/'distortion/output/project').resolve()
    if not work.is_dir() or work == build or not work.is_relative_to(build):
        parser.error('--workdir must already exist strictly inside distortion/build')
    if output.parent != project or output.exists():
        parser.error('--output must be a new filename directly in distortion/output/project')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    prefix = work/('offline-'+stamp)
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
           'PYTHONPATH': str(ROOT/'distortion'), 'FPGA_TEST_WORKDIR': str(work)}
    records = []

    def run(name, arguments, expected=0):
        command = [sys.executable, *map(str, arguments)]
        completed = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                   text=True, encoding='utf-8', errors='replace')
        log = Path(str(prefix)+'-'+name+'.log')
        with log.open('x', encoding='utf-8') as stream:
            stream.write(completed.stdout+'\n'+completed.stderr)
        row = {'check': name, 'command': command, 'cwd': str(ROOT),
               'expected_return_code': expected, 'actual_return_code': completed.returncode,
               'passed': completed.returncode == expected, 'log': str(log), 'log_sha256': sha(log)}
        if name == 'pytest':
            row['pytest_summary'] = next((line.strip() for line in reversed(completed.stdout.splitlines())
                if 'passed' in line or 'failed' in line), None)
        records.append(row)
        print(name+': '+('PASS' if row['passed'] else 'FAIL')+f' (exit {completed.returncode}, expected {expected})', flush=True)
        return completed

    test_paths = ['distortion/tests/test_'+name+'.py' for name in TEST_NAMES]
    tracked = sorted(set(test_paths + [str(path.relative_to(ROOT)).replace('\\', '/')
        for folder in ('distortion/tools', 'distortion/model') for path in (ROOT/folder).glob('*.py')]
        + ['handoff/audit-baselines.py', '.github/workflows/reference-checks.yml',
        'distortion/output/project/new-camera-profile.template.json',
        'distortion/output/project/fisheye-intrinsics.template.json',
        'distortion/output/project/stereo-capture-manifest.template.json',
        'distortion/output/project/native-capture-binding.template.json',
        'distortion/output/project/fisheye-dataset-manifest.template.json',
        'distortion/output/project/ov5640-cam2-reference-session.binding.json']))
    source_before = {name: sha(ROOT/name) for name in tracked}
    run('baseline-audit', ['handoff/audit-baselines.py'])
    run('pytest', ['-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                  '--basetemp='+str(prefix)+'-pytest', *test_paths])
    unknown = run('unknown-camera-block', ['distortion/tools/camera_mode_preflight.py', '--profile',
        'distortion/output/project/new-camera-profile.template.json', '--scope', 'raw-capture'], expected=2)
    try:
        unknown_profile = json.loads(unknown.stdout)['profile']
        unknown_semantics = (unknown_profile['new_configuration_download_blocked'] is True and
            unknown_profile['hardware_ready'] is False and bool(unknown_profile['blockers']))
    except (ValueError, KeyError, TypeError):
        unknown_semantics = False
    records.append({'check': 'unknown-camera-block-semantics', 'passed': unknown_semantics})
    run('unreviewed-new-module-program-block', ['distortion/tools/program_native_raw.py', '--binding',
        'distortion/output/project/ov5640-cam2-reference-session.binding.json', '--workdir', work], expected=2)
    run('dual-vga-budget', ['distortion/tools/camera_mode_preflight.py', '--explore',
        '--width', '640', '--height', '480', '--fps', '30', '--cameras', '2'])
    # Explicitly fabricated intrinsics exercise a full VGA multi-angle workload.
    # They are never parameters of the newly arrived physical camera.
    synthetic = {'model': 'fisheye', 'camera_id': 'SYNTHETIC-CPU-ONLY',
        'profile_id': 'synthetic-offline-moderate', 'provenance': 'synthetic',
        'image_size': [640, 480], 'K': [[700., 0, 319.5], [0, 700., 239.5], [0, 0, 1]],
        'D': [-.03, .004, -.0008, .0001]}
    synthetic_path, map_report = Path(str(prefix)+'-synthetic-profile.json'), Path(str(prefix)+'-synthetic-mapping.json')
    write_new(synthetic_path, synthetic)
    run('synthetic-vga-mapping', ['distortion/tools/wideangle_mapping_audit.py', synthetic_path,
        '--angles', *[str(a) for a in range(0, 360, 30)], '13.7', '--output', map_report])
    synthetic['K'] = [[70., 0, 319.5], [0, 70., 239.5], [0, 0, 1]]
    synthetic['profile_id'] = 'synthetic-outside-fixed-domain'
    extreme_path, reject_report = Path(str(prefix)+'-synthetic-extreme-profile.json'), Path(str(prefix)+'-synthetic-rejection.json')
    write_new(extreme_path, synthetic)
    run('synthetic-domain-rejection', ['distortion/tools/wideangle_mapping_audit.py', extreme_path,
        '--angles', '0', '--output', reject_report], expected=1)
    for name, path, expected_pass in (('synthetic-mapping-semantics', map_report, True),
                                       ('synthetic-rejection-semantics', reject_report, False)):
        data = json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
        records.append({'check': name, 'passed': bool(data and data.get('passed') is expected_pass and
            data.get('synthetic_input') is True and data.get('hardware_release_allowed') is False),
            'report': str(path), 'report_sha256': sha(path) if path.is_file() else None})
    if args.rtl_report:
        rtl_path = args.rtl_report.resolve()
        rtl = json.loads(rtl_path.read_text(encoding='utf-8-sig'))
        rtl_sources = rtl.get('SourceSHA256', {})
        sim_log = rtl_path.parent/'simulation.log'
        wire_path = rtl_path.parent/'raw-camera-capture-synthetic-stream.bin'
        rtl_ok = bool(rtl.get('Passed') is True and rtl.get('HardwareAccessed') is False and
            rtl.get('SyntheticOnly') is True and rtl_sources and sim_log.is_file() and wire_path.is_file())
        rtl_ok &= all((ROOT/'distortion'/name).resolve().is_relative_to((ROOT/'distortion').resolve()) and
            (ROOT/'distortion'/name).is_file() and sha(ROOT/'distortion'/name) == str(digest).lower()
            for name, digest in rtl_sources.items())
        rtl_ok &= bool(sim_log.is_file() and sha(sim_log) == str(rtl.get('SimulationLogSHA256', '')).lower() and
                       wire_path.is_file() and sha(wire_path) == str(rtl.get('SyntheticStreamSHA256', '')).lower())
        records.append({'check': 'raw-rtl-report-source-binding', 'passed': rtl_ok,
                        'report': str(rtl_path), 'report_sha256': sha(rtl_path)})
        if rtl_ok:
            sys.path.insert(0, str(ROOT/'distortion/tools'))
            from frame_protocol import FrameParser
            parser = FrameParser()
            packets = parser.feed(wire_path.read_bytes())
            valid = bool(packets and parser.rejected == 0 and not parser.buffer and
                len({(p.width, p.height) for p in packets}) == 1)
            records.append({'check': 'raw-rtl-wire-independent-parser', 'passed': valid,
                            'frame_ids': [p.frame_id for p in packets]})
            if valid:
                replay_binding = Path(str(prefix)+'-rtl-replay-binding.json')
                replay_summary = Path(str(prefix)+'-rtl-replay-summary.json')
                write_new(replay_binding, {'schema': 1, 'camera_id': 'SYNTHETIC-RTL-CAMERA',
                    'lens_id': 'SYNTHETIC-NO-LENS', 'profile_id': 'synthetic-rtl',
                    'capture_mode_id': 'synthetic-raw-rgb565', 'eye': 'CAM2',
                    'image_size': [packets[0].width, packets[0].height], 'pixel_format': 'RGB565_LE'})
                run('raw-rtl-native-receiver-replay', ['distortion/tools/native_camera_capture.py',
                    '--replay', wire_path, '--binding', replay_binding, '--directory', work,
                    '--session-id', 'rtl-replay-'+stamp, '--frames', str(len(packets)), '--summary', replay_summary])
                replay = json.loads(replay_summary.read_text(encoding='utf-8')) if replay_summary.is_file() else {}
                replay_ok = bool(replay and replay.get('passed') is True and replay.get('hardware_accessed') is False and
                    all(frame.get('source_kind') == 'offline_uart_replay' and frame.get('geometry_applied') is None and
                        frame.get('identity_verified_on_wire') is False for frame in replay.get('frames', [])))
                records.append({'check': 'raw-rtl-replay-remains-offline-unverified', 'passed': replay_ok,
                    'report': str(replay_summary), 'report_sha256': sha(replay_summary) if replay_summary.is_file() else None})
    source_after = {name: sha(ROOT/name) for name in tracked}
    records.append({'check': 'sources-unchanged-during-run', 'passed': source_before == source_after})
    report = {'schema': 1, 'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'passed': all(row['passed'] for row in records), 'hardware_accessed': False,
        'pds_invoked': False, 'new_physical_camera_data_used': False, 'new_bitstream_built': False,
        'python': sys.executable, 'python_version': platform.python_version(),
        'dependency_versions': {name: importlib.metadata.version(name) for name in ('numpy', 'opencv-python', 'pytest')},
        'workdir': str(work), 'checks': records, 'source_sha256': source_after,
        'limits': 'Local CPU reference/protocol/tool validation and file/hash audits only. Synthetic calibration is not a measurement of the new lens. No new camera initialization, stereo FPGA path, routed timing, optical result, throughput, latency, sync or award level is established. CI configuration is edited locally; a cloud CI run is not asserted.'}
    write_new(output, report)
    print('Report: '+str(output), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
