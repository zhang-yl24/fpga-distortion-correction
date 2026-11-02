"""Three-frame runtime view switching regression; no physical device access.

CPU preparation is the default. --execute-simulation runs the production
camera/DDR/remap/HDMI logic with modeled sensor and external DDR transactions.
The same profile-selection header is used by this test and the board top.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

import numpy as np

import run_camera720_corrected_system_sim as corrected
from run_gamma_pipeline_d5_sim import tool
from simulation_tools import prepare_compile_sources, resolve_vivado_bin, verify_compile_sources

ROOT = corrected.ROOT
BASE = ROOT / 'work/camera720-view-toggle-sim'
PROFILE = ROOT / 'results/camera720-stats-live-20261102-a/source/board/camera720-current-lens.vh'
SELECT = 'board/camera720-view-select.vh'
RAW = 'board/camera720-identity.vh'
WIDTH, HEIGHT, FRAMES = 1280, 720, 3
PIXELS, BEATS = WIDTH * HEIGHT, WIDTH * HEIGHT // 16
COMPILE = tuple('tests/tb_camera720_view_toggle.sv' if n == 'tests/tb_camera720_corrected_system.sv' else n
                for n in corrected.COMPILE)
HEADERS = (*corrected.HEADERS, SELECT)
HELPERS = (*corrected.HELPERS, RAW, 'tools/run_camera720_view_toggle_sim.py')
REPORT = 'camera720-view-toggle-simulation.json'
MARKER = 'PASS camera720 view toggle:'
sha, crc, cpu = corrected.sha, corrected.crc, corrected.cpu


def fixtures(work, header):
    """Separate integer geometry and bilinear oracle for every frame epoch."""
    config, guard = corrected.parse_header(header)
    raw, _ = corrected.parse_header((ROOT / RAW).read_text(encoding='ascii'))
    geometries = [corrected.geometry(WIDTH, HEIGHT, values, guard) for values in (config, raw)]
    sx, sy, invalid, raw_stats = geometries[1]
    yy, xx = np.indices((HEIGHT, WIDTH), dtype=np.int64)
    if not np.array_equal(sx, xx * 256) or not np.array_equal(sy, yy * 256) or invalid.any():
        raise ValueError('raw profile is not exact identity under the shared radius guard')
    (work / 'config.vh').write_text(header, encoding='ascii', newline='\n')
    (work / 'camera720-view-select.vh').write_bytes((ROOT / SELECT).read_bytes())
    expected, records = [], []
    paths = ('source-beats.mem', 'corrected-beats.mem', 'source-pixels.mem', 'expected.mem')
    with ExitStack() as stack:
        outputs = {n: stack.enter_context((work / n).open('x', encoding='ascii', newline='\n')) for n in paths}
        for index, mode in enumerate(('corrected', 'raw', 'corrected')):
            source = cpu.texture(WIDTH, HEIGHT, index % 2)
            if index == 2:
                source = np.roll(source, (37, 53), (0, 1)) ^ np.uint16(0x0841)
            sx, sy, invalid, _ = geometries[int(mode == 'raw')]
            mapped = cpu.remap_fixed(cpu.expand565(source), np.where(invalid, -(1 << 23), sx) / 256.,
                                    np.where(invalid, -(1 << 23), sy) / 256.)
            result = np.where(invalid, 0, cpu.pack565(mapped)).astype(np.uint16)
            if (mode == 'raw') != np.array_equal(source, result):
                raise ValueError('raw must preserve every pixel and corrected must change this texture')
            for words, beat_name, pixel_name in ((source, 'source-beats.mem', 'source-pixels.mem'),
                                                (result, 'corrected-beats.mem', 'expected.mem')):
                payload = np.asarray(words, dtype='<u2').tobytes()
                outputs[beat_name].writelines(f"{int.from_bytes(payload[j:j+32], 'little'):064x}\n"
                                              for j in range(0, len(payload), 32))
                outputs[pixel_name].writelines(f'{int(v):04x}\n' for v in words.ravel())
            expected.append(result)
            records.append({'FrameID': index + 1, 'Mode': mode, 'SourceCRC32': crc(source),
                            'CorrectedCRC32': crc(result), 'ChangedPixels': int((source != result).sum())})
    for key in ('SourceCRC32', 'CorrectedCRC32'):
        if len({r[key] for r in records}) != FRAMES:
            raise ValueError('distinct frame epochs required')
    for filename, key in (('source-crcs.mem', 'SourceCRC32'), ('corrected-crcs.mem', 'CorrectedCRC32')):
        (work / filename).write_text('\n'.join(r[key] for r in records) + '\n', encoding='ascii', newline='\n')
    return expected, records, {'CorrectedConfig': config, 'RawConfig': raw, 'RadiusGuardQ22': guard,
                              'CorrectedGeometry': geometries[0][3], 'RawGeometry': raw_stats,
                              'RawPreservesAllRGB565Pixels': True, 'GammaEnabled': False}


def validate_summary(summary):
    expected = {'passed': True, 'frames': FRAMES, 'width': WIDTH, 'height': HEIGHT,
                'source_beats': FRAMES * BEATS, 'result_beats': FRAMES * BEATS,
                'unique_scans': FRAMES, 'underflows': 0, 'crc_mismatches': 0, 'final_drain': True,
                'midframe_mode_changes': 2, 'pending_mode_changes': 4}
    if any(type(summary.get(k)) is not type(v) or summary.get(k) != v for k, v in expected.items()):
        raise ValueError('full-frame switching, ownership or final-drain coverage differs')
    positive = ('aw_stalls', 'w_stalls', 'ar_stalls', 'read_contention_cycles', 'write_contention_cycles',
                'capture_process_overlap', 'process_scan_overlap', 'capture_scan_overlap',
                'capture_fifo_peak', 'display_fifo_peak', 'complete_rasters', 'black_border_pixels',
                'repeat_scans', 'source_bank_reuses', 'result_bank_reuses')
    if any(type(summary.get(k)) is not int or summary[k] <= 0 for k in positive):
        raise ValueError('missing active/pending/repeated-display or DDR coverage')
    count = FRAMES + summary['repeat_scans']
    if summary['scanned_pixels'] != count * PIXELS or summary['scan_crc_checks'] != count:
        raise ValueError('incomplete scan/CRC coverage')
    if summary['capture_fifo_peak'] > 64 or summary['display_fifo_peak'] > 512 or summary['complete_rasters'] < 3:
        raise ValueError('FIFO/raster bound differs')


def validate_outputs(work, expected, records, summary):
    if len(expected) != FRAMES or len(records) != FRAMES or [r['Mode'] for r in records] != ['corrected', 'raw', 'corrected']:
        raise ValueError('three ordered view references required')
    counts, scan_crcs = {i: 0 for i in range(1, FRAMES + 1)}, []
    for i, record in enumerate(records):
        if record['FrameID'] != i + 1 or crc(expected[i]) != record['CorrectedCRC32']:
            raise ValueError('reference epoch/CRC metadata differs')
    with (work / 'scan-pixels.mem').open(encoding='ascii') as stream:
        for _ in range(FRAMES + summary['repeat_scans']):
            pixels = np.empty(expected[0].size, dtype=np.uint16)
            frame_id = None
            for index in range(pixels.size):
                fields = stream.readline().split()
                if len(fields) != 2:
                    raise ValueError('incomplete actual scan dump')
                fid, value = int(fields[0]), int(fields[1], 16)
                if fid not in counts or not 0 <= value <= 65535:
                    raise ValueError('unexpected scan epoch/pixel')
                if frame_id is None:
                    frame_id = fid
                if fid != frame_id:
                    raise ValueError('scan epoch changed inside active picture')
                pixels[index] = value
            if not np.array_equal(pixels.reshape(expected[frame_id - 1].shape), expected[frame_id - 1]):
                raise ValueError('actual HDMI differs from per-frame independent view oracle')
            actual_crc = crc(pixels)
            if actual_crc != records[frame_id - 1]['CorrectedCRC32']:
                raise ValueError('actual HDMI CRC differs')
            counts[frame_id] += 1
            scan_crcs.append({'FrameID': frame_id, 'Mode': records[frame_id - 1]['Mode'],
                             'ActualScanCRC32': actual_crc, 'Pixels': pixels.size})
        if stream.read().strip():
            raise ValueError('extra HDMI pixels after complete scans')
    if any(count == 0 for count in counts.values()):
        raise ValueError('not every source epoch reached HDMI')
    with (work / 'events.csv').open(encoding='ascii', newline='') as stream:
        events = list(csv.DictReader(stream))
    if len(events) != 2 * FRAMES:
        raise ValueError('missing source/result publication event')
    for frame_id in counts:
        subset = [r for r in events if int(r['id']) == frame_id]
        if len(subset) != 2 or [r['event'] for r in subset] != ['commit', 'release']:
            raise ValueError('invalid ownership event order')
        if not int(subset[0]['core_cycle']) < int(subset[1]['core_cycle']):
            raise ValueError('source released before processing finished')
        if subset[0]['crc32'].upper() != records[frame_id - 1]['SourceCRC32']:
            raise ValueError('source completion CRC differs')
        if subset[1]['crc32'].upper() != records[frame_id - 1]['CorrectedCRC32']:
            raise ValueError('view result completion CRC differs')
    return scan_crcs


def run(workdir, *, execute_simulation=False, maximum_seconds=3600):
    work = Path(workdir).absolute()
    if work != work.resolve() or work.parent != BASE.resolve() or work.exists():
        raise ValueError('fresh canonical direct child of work/camera720-view-toggle-sim required')
    if type(maximum_seconds) is not int or not 120 <= maximum_seconds <= 3600:
        raise ValueError('simulator deadline must be 120..3600 seconds')
    work.mkdir(parents=True)
    inputs = {str((ROOT / n).resolve()): sha(ROOT / n) for n in (*COMPILE, *HEADERS, *HELPERS)}
    inputs[str(PROFILE.resolve())] = sha(PROFILE)
    report = {'Schema': 'camera720-view-toggle-simulation-v1', 'Prepared': False, 'Passed': False,
              'SimulationExecuted': False, 'StartedUTC': datetime.now(timezone.utc).isoformat(),
              'InputSHA256': inputs, 'SourceGeometry': [WIDTH, HEIGHT], 'OutputActiveArea': [1920, 1080],
              'ModeSequence': ['corrected', 'raw', 'corrected'], 'Commands': [],
              'HardwareAccessed': False, 'PDSAccessed': False, 'PhysicalIPExecuted': False,
              'OpticalCalibrationAccepted': False, 'MeasuredFrameRate': None, 'RTLResultUsedForGolden': False,
              'Limits': 'Mode requests are injected after debounce, during processing and pending results. '
                        'Sensor and DDR are models. This checks frame atomicity, pixels, CRC, banks and scan '
                        'using the production mux and datapaths; not physical timing, key electrical behavior, '
                        'measured FPS or actual lens optical acceptance.'}
    hashes, started = {}, time.monotonic()
    try:
        expected, records, model = fixtures(work, PROFILE.read_text(encoding='ascii'))
        report.update(Model=model, Frames=records, Prepared=True)
        hashes = {p.name: sha(p) for p in work.iterdir() if p.is_file()}
        report['FixtureSHA256'] = hashes
        if execute_simulation:
            compiled, bindings = prepare_compile_sources(ROOT, COMPILE, HEADERS, work)
            report['CompileBindings'] = bindings
            bin_dir = resolve_vivado_bin(ROOT.parent)
            for executable, args, stage in (
                    ('xvlog.bat', ['--sv', *map(str, compiled)], 'compile'),
                    ('xelab.bat', ['tb_camera720_view_toggle', '-s', 'camera720_view_toggle', '--timescale', '1ps/1ps', '--O3'], 'elaborate'),
                    ('xsim.bat', ['camera720_view_toggle', '-runall', '-log', 'simulation.log'], 'simulate')):
                item = {'Stage': stage, 'NativeArgv': [str(bin_dir / executable), *args], 'ReturnCode': None}
                report['Commands'].append(item)
                tool(bin_dir, executable, args, work, started + maximum_seconds, stage)
                item['ReturnCode'] = 0
                if stage == 'simulate':
                    report['SimulationExecuted'] = True
            log = (work / 'simulation.log').read_text(encoding='utf-8', errors='replace')
            if MARKER not in log or '$finish called' not in log or re.search(r'(?im)^\s*(?:fatal|error):', log):
                raise ValueError('complete runtime view simulator pass marker missing')
            summary = json.loads((work / 'summary.json').read_text(encoding='ascii'))
            validate_summary(summary)
            scans = validate_outputs(work, expected, records, summary)
            verify_compile_sources(ROOT, COMPILE, HEADERS, work, bindings)
            report.update(Passed=True, Summary=summary, ActualScanChecks=scans,
                          ActualScanPixelsCompared=summary['scanned_pixels'])
    except (Exception, KeyboardInterrupt) as error:
        report['Error'] = type(error).__name__ + ': ' + str(error)
    finally:
        report['InputSHA256After'] = {name: sha(name) if Path(name).is_file() else None for name in inputs}
        report['FixtureSHA256After'] = {name: sha(work / name) if (work / name).is_file() else None for name in hashes}
        if inputs != report['InputSHA256After'] or hashes != report['FixtureSHA256After']:
            report.update(Passed=False, Prepared=False, SourceOrFixtureDrift=True)
        report['ElapsedSeconds'] = round(time.monotonic() - started, 3)
        report['LogSHA256'] = {p.name: sha(p) for p in work.glob('*.log')}
        report['ResultSHA256'] = {n: sha(work / n) for n in ('summary.json', 'events.csv', 'scan-pixels.mem') if (work / n).is_file()}
        (work / REPORT).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'Prepared': report['Prepared'], 'Passed': report['Passed'], 'SimulationExecuted': report['SimulationExecuted'],
                      'Error': report.get('Error'), 'Report': str(work / REPORT)}))
    return 0 if not report.get('Error') and report['Prepared'] and (not execute_simulation or report['Passed']) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--execute-simulation', action='store_true')
    parser.add_argument('--maximum-seconds', type=int, default=3600)
    args = parser.parse_args()
    return run(args.workdir, execute_simulation=args.execute_simulation, maximum_seconds=args.maximum_seconds)


if __name__ == '__main__':
    raise SystemExit(main())
