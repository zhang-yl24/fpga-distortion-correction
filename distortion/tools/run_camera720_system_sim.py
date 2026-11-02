"""Full720 DVP/system/DDR/1080p30 digital regression; no physical hardware.

Execute the actual camera_vga_video_system controller and all production data
paths with the new top's exact identity configuration. DDR and sensor are models.
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

import generate_1080_core_vectors as cpu
import run_camera_vga_system_sim as previous
from run_gamma_pipeline_d5_sim import tool
from simulation_tools import prepare_compile_sources, resolve_vivado_bin, verify_compile_sources

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'work/camera720-system'
WIDTH, HEIGHT, FRAMES = 1280, 720, 2
PIXELS, BEATS = WIDTH*HEIGHT, WIDTH*HEIGHT//16
CONFIG = 'board/camera720-identity.vh'
COMPILE = tuple(n for n in previous.COMPILE
                if n not in ('tests/processed_output_ip_stubs.sv', 'tests/tb_camera_vga_system.sv'))+('tests/tb_camera720_system.sv',)
HEADERS = ('rtl/experimental/gamma_curves.vh', 'rtl/video_crc32.vh')
HELPERS = tuple(dict.fromkeys((*previous.HELPERS, 'tools/run_camera720_system_sim.py', 'tools/prepare_gamma_pipeline_d5.py', CONFIG)))
REPORT = 'camera720-system-simulation.json'
MARKER = 'PASS camera720 system:'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def crc(pixels):
    return f'{zlib.crc32(np.asarray(pixels, dtype="<u2").tobytes()) & 0xffffffff:08X}'


def fixtures(work):
    header = (ROOT/CONFIG).read_bytes()
    config = [int(v) for v in re.findall(rb"C720_\w+=\d+'sd(\d+)", header)]
    guard = int(re.search(rb'C720_RADIUS_Q22=(\d+)', header)[1])
    if len(config) != 13:
        raise ValueError('exactly 13 identity coefficients required')
    yy, xx = np.indices((HEIGHT, WIDTH), dtype=np.int64)
    sx, sy, bad, radius = cpu.project_integer(xx*256, yy*256, config)
    if not np.array_equal(sx, xx*256) or not np.array_equal(sy, yy*256) or bad.any() or (radius > guard).any():
        raise ValueError('new top configuration is not exact full-frame integer identity')
    (work/'config.vh').write_bytes(header)
    sources, records = [], []
    with (work/'source-beats.mem').open('x', encoding='ascii', newline='\n') as beats, \
         (work/'expected.mem').open('x', encoding='ascii', newline='\n') as pixels:
        for index in range(FRAMES):
            source = cpu.texture(WIDTH, HEIGHT, index%2)
            if index == 2:
                source = np.roll(source, (37, 53), (0, 1)) ^ np.uint16(0x0841)
            # Full RGB565 reconstruction checks zero-weight out-of-bounds
            # neighbours at the last row/column, independently of RTL.
            expected = cpu.pack565(cpu.remap_fixed(cpu.expand565(source), sx/256., sy/256.))
            if not np.array_equal(expected, source):
                raise ValueError('CPU identity reconstruction changed a source pixel')
            payload = np.asarray(source, dtype='<u2').tobytes()
            beats.writelines(f"{int.from_bytes(payload[j:j+32], 'little'):064x}\n" for j in range(0, len(payload), 32))
            pixels.writelines(f'{int(v):04x}\n' for v in expected.ravel())
            sources.append(source)
            records.append({'FrameID': index+1, 'SourceCRC32': crc(source), 'ExpectedCRC32': crc(expected)})
    if len({r['SourceCRC32'] for r in records}) != FRAMES:
        raise ValueError('distinct frame epochs required')
    (work/'crcs.mem').write_text('\n'.join(r['ExpectedCRC32'] for r in records)+'\n', encoding='ascii', newline='\n')
    return sources, records, {'IntegerConfig': config, 'RadiusGuardQ22': guard,
                              'ExactIdentityCoordinateCount': PIXELS, 'Provenance': 'new_transport_header',
                              'LensCalibrationAccepted': False, 'GammaEnabled': False}


def validate_summary(summary):
    expected = {'passed': True, 'frames': FRAMES, 'width': WIDTH, 'height': HEIGHT,
                'source_beats': FRAMES*BEATS, 'result_beats': FRAMES*BEATS,
                'unique_scans': FRAMES, 'underflows': 0, 'crc_mismatches': 0, 'final_drain': True}
    if any(type(summary.get(k)) is not type(v) or summary.get(k) != v for k, v in expected.items()):
        raise ValueError('full720 frame, ownership or final-drain coverage differs')
    positive = ('aw_stalls', 'w_stalls',
                'ar_stalls', 'read_contention_cycles', 'write_contention_cycles', 'capture_process_overlap',
                'process_scan_overlap', 'capture_scan_overlap', 'capture_fifo_peak', 'display_fifo_peak',
                'complete_rasters', 'black_border_pixels')
    if any(type(summary.get(k)) is not int or summary[k] <= 0 for k in positive):
        raise ValueError('missing concurrent pipeline/DDR/raster coverage')
    count = summary['unique_scans']+summary['repeat_scans']
    if summary['scanned_pixels'] != count*PIXELS or summary['scan_crc_checks'] != count:
        raise ValueError('incomplete complete-frame scan/CRC coverage')
    if summary['capture_fifo_peak'] > 64 or summary['display_fifo_peak'] > 512 or summary['complete_rasters'] < 3:
        raise ValueError('FIFO/raster bound differs')


def validate_outputs(work, expected, records, summary):
    actual_counts = {frame_id: 0 for frame_id in range(1, FRAMES+1)}
    scan_crcs = []
    with (work/'scan-pixels.mem').open(encoding='ascii') as stream:
        for _ in range(summary['unique_scans']+summary['repeat_scans']):
            pixels = np.empty(PIXELS, dtype=np.uint16)
            frame_id = None
            for index in range(PIXELS):
                fields = stream.readline().split()
                if len(fields) != 2:
                    raise ValueError('incomplete actual scan dump')
                fid, value = int(fields[0]), int(fields[1], 16)
                if fid not in actual_counts or not 0 <= value <= 65535:
                    raise ValueError('unexpected scan epoch/pixel')
                if frame_id is None:
                    frame_id = fid
                if fid != frame_id:
                    raise ValueError('scan epoch changed inside an active picture')
                pixels[index] = value
            if not np.array_equal(pixels.reshape(HEIGHT, WIDTH), expected[frame_id-1]):
                raise ValueError('actual HDMI RGB differs from independent CPU input/identity oracle')
            actual_crc = crc(pixels)
            if actual_crc != records[frame_id-1]['ExpectedCRC32']:
                raise ValueError('actual HDMI pixel dump CRC differs')
            actual_counts[frame_id] += 1
            scan_crcs.append({'FrameID': frame_id, 'ActualScanCRC32': actual_crc, 'Pixels': PIXELS})
        if stream.read().strip():
            raise ValueError('extra actual HDMI pixels after reported complete scans')
    if any(count == 0 for count in actual_counts.values()):
        raise ValueError('not every source epoch reached HDMI')
    with (work/'events.csv').open(encoding='ascii', newline='') as stream:
        events = list(csv.DictReader(stream))
    if len(events) != 2*FRAMES:
        raise ValueError('missing source/result publication event')
    for frame_id in range(1, FRAMES+1):
        subset = [r for r in events if int(r['id']) == frame_id]
        if len(subset) != 2 or [r['event'] for r in subset] != ['commit', 'release']:
            raise ValueError('invalid frame ownership event order')
        if not int(subset[0]['core_cycle']) < int(subset[1]['core_cycle']):
            raise ValueError('source released before processing finished')
        if any(r['crc32'].upper() != records[frame_id-1]['ExpectedCRC32'] for r in subset):
            raise ValueError('source/result completion CRC differs')
    return scan_crcs


def run(workdir, maximum_seconds=1800):
    supplied = Path(workdir).absolute()
    work = supplied.resolve()
    if supplied != work or work.parent != BASE.resolve() or work.exists():
        raise ValueError('fresh canonical direct child of work/camera720-system required')
    if type(maximum_seconds) is not int or not 120 <= maximum_seconds <= 1800:
        raise ValueError('whole native deadline must be 120..1800 seconds')
    work.mkdir(parents=True)
    before = {name: sha(ROOT/name) for name in (*COMPILE, *HEADERS, *HELPERS)}
    report = {'Schema': 'camera720-full-system-simulation-v1', 'Passed': False,
              'StartedUTC': datetime.now(timezone.utc).isoformat(), 'SourceSHA256': before,
              'SourceGeometry': [WIDTH, HEIGHT], 'OutputActiveArea': [1920, 1080],
              'OutputRaster': [2200, 1125], 'NominalModeledClocksHz': {'Core': 125000000, 'Camera': 48000000, 'Pixel': 74250000},
              'SensorHTSPixels': 1892, 'SensorVTSLines': 740, 'Commands': [],
              'RealDVPCaptureExecuted': True, 'RealCameraSystemControllerExecuted': True,
              'RealBankMapperReaderWriterFIFOAndScanExecuted': True, 'RTLResultUsedForGolden': False,
              'HardwareAccessed': False, 'PDSAccessed': False, 'PhysicalIPExecuted': False,
              'OpticalCalibrationAccepted': False, 'MeasuredFrameRate': None,
              'Limits': 'Synthetic two-frame sensor and DDR models; actual production system/controller/data paths at full geometry. Uses identity transport, not lens calibration. Frame boundaries can wait for source reservations. Final test-only suppression of an extra grant leaves accepted work intact. No SCCB, board startup, physical electrical timing/DDR/HDMI, clock-stop recovery or measured frame-rate claim.'}
    fixture_hashes = {}
    started = time.monotonic()
    try:
        expected, records, model = fixtures(work)
        report.update(Model=model, Frames=records)
        fixture_hashes = {p.name: sha(p) for p in work.iterdir() if p.is_file()}
        report['FixtureSHA256'] = fixture_hashes
        compiled, bindings = prepare_compile_sources(ROOT, COMPILE, HEADERS, work)
        report['CompileBindings'] = bindings
        bin_dir = resolve_vivado_bin(ROOT.parent)
        for executable, args, stage in (
                ('xvlog.bat', ['--sv', *map(str, compiled)], 'compile'),
                ('xelab.bat', ['tb_camera720_system', '-s', 'camera720_system', '--timescale', '1ps/1ps', '--O3'], 'elaborate'),
                ('xsim.bat', ['camera720_system', '-runall', '-log', 'simulation.log'], 'simulate')):
            item = {'Stage': stage, 'NativeArgv': [str(bin_dir/executable), *args], 'ReturnCode': None}
            report['Commands'].append(item)
            tool(bin_dir, executable, args, work, started+maximum_seconds, stage)
            item['ReturnCode'] = 0
        log = (work/'simulation.log').read_text(encoding='utf-8', errors='replace')
        if MARKER not in log or '$finish called' not in log or re.search(r'(?im)^\s*(?:fatal|error):', log):
            raise ValueError('complete full720 native pass marker missing')
        summary = json.loads((work/'summary.json').read_text(encoding='ascii'))
        validate_summary(summary)
        scans = validate_outputs(work, expected, records, summary)
        verify_compile_sources(ROOT, COMPILE, HEADERS, work, bindings)
        report.update(Passed=True, Summary=summary, ActualScanChecks=scans,
                      ActualScanPixelsCompared=summary['scanned_pixels'])
    except (Exception, KeyboardInterrupt) as error:
        report['Error'] = type(error).__name__+': '+str(error)
    finally:
        report['SourceSHA256After'] = {name: sha(ROOT/name) for name in before}
        report['FixtureSHA256After'] = {name: sha(work/name) for name in fixture_hashes}
        if before != report['SourceSHA256After'] or fixture_hashes != report['FixtureSHA256After']:
            report.update(Passed=False, SourceOrFixtureDrift=True)
        report['ElapsedSeconds'] = round(time.monotonic()-started, 3)
        report['LogSHA256'] = {p.name: sha(p) for p in work.glob('*.log')}
        report['ResultSHA256'] = {name: sha(work/name) for name in ('summary.json', 'events.csv', 'scan-pixels.mem') if (work/name).is_file()}
        (work/REPORT).write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'Passed': report['Passed'], 'Error': report.get('Error'), 'Report': str(work/REPORT)}))
    return 0 if report['Passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--maximum-seconds', type=int, default=1800)
    args = parser.parse_args()
    return run(args.workdir, args.maximum_seconds)


if __name__ == '__main__':
    raise SystemExit(main())
