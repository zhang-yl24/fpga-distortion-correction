"""Independent 720p correction system regression; prepare CPU fixtures by default.

--synthetic uses test-only Brown coefficients, never a current-lens profile.
--header accepts an explicitly supplied, unaccepted C720 parameter header.
Only --execute-simulation launches the modeled Vivado system simulation. Neither
mode accesses PDS, JTAG, UART, a board, or establishes optical calibration.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time

import numpy as np

import generate_1080_core_vectors as cpu
import run_camera720_system_sim as identity
from run_gamma_pipeline_d5_sim import tool
from simulation_tools import prepare_compile_sources, resolve_vivado_bin, verify_compile_sources

ROOT = identity.ROOT
BASE = ROOT/'work/camera720-corrected-system'
WIDTH, HEIGHT, FRAMES = 1280, 720, 2
COMPILE = tuple('tests/tb_camera720_corrected_system.sv' if n == 'tests/tb_camera720_system.sv' else n
                for n in identity.COMPILE)
HEADERS = identity.HEADERS
HELPERS = tuple(dict.fromkeys((*identity.HELPERS, 'tools/run_camera720_corrected_system_sim.py',
                              'tools/generate_1080_core_vectors.py', 'tools/generate-brown-vectors.py',
                              'model/reference.py', 'tools/simulation_tools.py')))
REPORT = 'camera720-corrected-system-simulation.json'
MARKER = 'PASS camera720 corrected system:'
sha, crc = identity.sha, identity.crc
BITS = (24,)*6+(32,)*7


def validate_config(config, guard):
    if len(config) != 13 or any(type(v) is not int or not -(1 << (b-1)) <= v < (1 << (b-1))
                               for v, b in zip(config, BITS)):
        raise ValueError('13 correctly sized signed integer coefficients required')
    if any(config[i] <= 0 for i in (4, 5, 6, 7)):
        raise ValueError('positive source focal lengths and output inverse focal lengths required')
    if type(guard) is not int or not 0 < guard < (1 << 31):
        raise ValueError('positive signed-32 radius guard required')


def parse_header(text):
    """Strict data-only decimal localparams; unary minus precedes the sized literal."""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    text = re.sub(r'//[^\n]*', '', text)
    declaration = re.compile(r"localparam\s+signed\s*\[(\d+):0\]\s+C720_(\w+)\s*=\s*(-?)\s*(\d+)'sd(\d+)\s*;")
    found = {}
    for match in declaration.finditer(text):
        upper, name, sign, width, magnitude = match.groups()
        if name not in cpu.NAMES or name in found:
            raise ValueError('unknown or duplicate C720 coefficient')
        bits = BITS[cpu.NAMES.index(name)]
        if int(upper)+1 != bits or int(width) != bits:
            raise ValueError('coefficient declaration/literal width differs')
        found[name] = (-1 if sign else 1)*int(magnitude)
    remainder = declaration.sub('', text)
    radius = re.compile(r'localparam\s+C720_RADIUS_Q22\s*=\s*(\d+)\s*;')
    guards = radius.findall(remainder)
    if len(found) != 13 or len(guards) != 1 or radius.sub('', remainder).strip():
        raise ValueError('exactly 13 coefficients and one radius declaration required; no executable content')
    config, guard = [found[n] for n in cpu.NAMES], int(guards[0])
    validate_config(config, guard)
    return config, guard


def render_header(config, guard):
    validate_config(config, guard)
    lines = ['// TEST INPUT ONLY: does not establish lens calibration or board acceptance.']
    for name, value, bits in zip(cpu.NAMES, config, BITS):
        lines.append(f"localparam signed [{bits-1}:0] C720_{name}={'-' if value < 0 else ''}{bits}'sd{abs(value)};")
    return '\n'.join([*lines, f'localparam C720_RADIUS_Q22={guard};', ''])


def synthetic_config(width=WIDTH, height=HEIGHT):
    config = cpu.parameters(width, height)
    # Same deliberately nonidentity stress family as the existing output-only
    # regression. Keep neighbouring reads mostly interior; K2 and P2 are negative.
    config[4] = (config[4]*9+5)//10
    config[5] = (config[5]*9+5)//10
    return config, 2 << 22


def geometry(width, height, config, guard):
    validate_config(config, guard)
    if type(width) is not int or type(height) is not int or not 4 <= width <= WIDTH or not 4 <= height <= HEIGHT or width*height % 16:
        raise ValueError('bounded geometry with complete 256-bit beats required')
    # Enforce the mapper's documented normalized-domain bound before numpy
    # multiplication. Python integers avoid accidental int64 overflow here.
    for axis, extent in enumerate((width, height)):
        if any(abs((((u-config[axis])*config[6+axis])+(1 << 15)) >> 16) > 2*cpu.Q
               for u in (0, (extent-1)*256)):
            raise ValueError('output rectangle exceeds normalized mapper domain')
    yy, xx = np.indices((height, width), dtype=np.int64)
    sx, sy, bad, radius = cpu.project_integer(xx*256, yy*256, config)
    invalid = bad | (radius > guard) | (sx <= -256) | (sy <= -256) | (sx >= width*256) | (sy >= height*256)
    scalar = cpu.scalar_oracle()
    checks = 0
    for y in np.unique(np.linspace(0, height-1, min(13, height), dtype=int)):
        for x in np.unique(np.linspace(0, width-1, min(17, width), dtype=int)):
            a, b, failed = scalar.project(int(x)*256, int(y)*256, config)
            if (a, b, bool(failed)) != (int(sx[y, x]), int(sy[y, x]), bool(bad[y, x])):
                raise ValueError('independent scalar/vector coordinate disagreement')
            checks += 1
    stats = {'ScalarCoordinateCrosschecks': checks, 'ArithmeticInvalidPixels': int(bad.sum()),
             'MaskedPixels': int(invalid.sum()), 'NonidentityCoordinateCount': int(((sx != xx*256) | (sy != yy*256)).sum()),
             'MaximumRadiusSquaredQ22': int(radius.max()), 'Pixels': width*height}
    return sx, sy, invalid, stats


def fixtures(work, header, *, width=WIDTH, height=HEIGHT):
    config, guard = parse_header(header)
    sx, sy, invalid, stats = geometry(width, height, config, guard)
    (work/'config.vh').write_text(header, encoding='ascii', newline='\n')
    expected, records = [], []
    paths = ('source-beats.mem', 'corrected-beats.mem', 'source-pixels.mem', 'expected.mem')
    from contextlib import ExitStack
    with ExitStack() as stack:
        outputs = {name: stack.enter_context((work/name).open('x', encoding='ascii', newline='\n')) for name in paths}
        for index in range(FRAMES):
            source = cpu.texture(width, height, index)
            mapped = cpu.remap_fixed(cpu.expand565(source), np.where(invalid, -(1 << 23), sx)/256.,
                                    np.where(invalid, -(1 << 23), sy)/256.)
            corrected = np.where(invalid, 0, cpu.pack565(mapped)).astype(np.uint16)
            for words, beat_name, pixel_name in ((source, 'source-beats.mem', 'source-pixels.mem'),
                                                (corrected, 'corrected-beats.mem', 'expected.mem')):
                payload = np.asarray(words, dtype='<u2').tobytes()
                outputs[beat_name].writelines(f"{int.from_bytes(payload[j:j+32], 'little'):064x}\n" for j in range(0, len(payload), 32))
                outputs[pixel_name].writelines(f'{int(v):04x}\n' for v in words.ravel())
            expected.append(corrected)
            records.append({'FrameID': index+1, 'SourceCRC32': crc(source), 'CorrectedCRC32': crc(corrected),
                            'ChangedPixels': int((source != corrected).sum())})
    if len({r['SourceCRC32'] for r in records}) != FRAMES or len({r['CorrectedCRC32'] for r in records}) != FRAMES:
        raise ValueError('distinct source and corrected frame epochs required')
    for name, key in (('source-crcs.mem', 'SourceCRC32'), ('corrected-crcs.mem', 'CorrectedCRC32')):
        (work/name).write_text('\n'.join(r[key] for r in records)+'\n', encoding='ascii', newline='\n')
    return expected, records, {'IntegerConfig': config, 'RadiusGuardQ22': guard, **stats,
                              'LensCalibrationAccepted': False, 'GammaEnabled': False}


def validate_outputs(work, expected, records, summary):
    if len(expected) != FRAMES or len(records) != FRAMES or [r['FrameID'] for r in records] != [1, 2]:
        raise ValueError('exact two reference epochs required')
    shape = expected[0].shape
    if any(v.shape != shape or v.dtype != np.dtype('uint16') for v in expected) or len(shape) != 2:
        raise ValueError('consistent RGB565 reference images required')
    for i, record in enumerate(records):
        if any(not re.fullmatch('[0-9A-F]{8}', record.get(k, '')) for k in ('SourceCRC32', 'CorrectedCRC32')) or crc(expected[i]) != record['CorrectedCRC32']:
            raise ValueError('reference CRC metadata differs')
    if summary.get('unique_scans') != FRAMES or type(summary.get('repeat_scans')) is not int or summary['repeat_scans'] < 0:
        raise ValueError('invalid complete scan count')
    counts, scan_crcs = {i: 0 for i in (1, 2)}, []
    with (work/'scan-pixels.mem').open(encoding='ascii') as stream:
        for _ in range(FRAMES+summary['repeat_scans']):
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
                    raise ValueError('scan epoch changed inside an active picture')
                pixels[index] = value
            if not np.array_equal(pixels.reshape(shape), expected[frame_id-1]):
                raise ValueError('actual HDMI RGB differs from independent corrected oracle')
            actual_crc = crc(pixels)
            if actual_crc != records[frame_id-1]['CorrectedCRC32']:
                raise ValueError('actual HDMI corrected CRC differs')
            counts[frame_id] += 1
            scan_crcs.append({'FrameID': frame_id, 'ActualScanCRC32': actual_crc, 'Pixels': pixels.size})
        if stream.read().strip():
            raise ValueError('extra actual HDMI pixels after reported complete scans')
    if any(count == 0 for count in counts.values()):
        raise ValueError('not every source epoch reached HDMI')
    with (work/'events.csv').open(encoding='ascii', newline='') as stream:
        events = list(csv.DictReader(stream))
    if len(events) != 2*FRAMES:
        raise ValueError('missing source/result publication event')
    for frame_id in (1, 2):
        subset = [r for r in events if int(r['id']) == frame_id]
        if len(subset) != 2 or [r['event'] for r in subset] != ['commit', 'release']:
            raise ValueError('invalid frame ownership event order')
        if not int(subset[0]['core_cycle']) < int(subset[1]['core_cycle']):
            raise ValueError('source released before processing finished')
        if subset[0]['crc32'].upper() != records[frame_id-1]['SourceCRC32']:
            raise ValueError('source completion CRC differs')
        if subset[1]['crc32'].upper() != records[frame_id-1]['CorrectedCRC32']:
            raise ValueError('corrected completion CRC differs')
    return scan_crcs


def run(workdir, *, synthetic=False, header_path=None, execute_simulation=False, maximum_seconds=1800):
    supplied, work = Path(workdir).absolute(), Path(workdir).resolve()
    if supplied != work or work.parent != BASE.resolve() or work.exists():
        raise ValueError('fresh canonical direct child of work/camera720-corrected-system required')
    if type(synthetic) is not bool or type(execute_simulation) is not bool or synthetic == (header_path is not None):
        raise ValueError('choose exactly one synthetic test model or supplied unaccepted header')
    if type(maximum_seconds) is not int or not 120 <= maximum_seconds <= 1800:
        raise ValueError('whole simulator deadline must be 120..1800 seconds')
    header_path = None if header_path is None else Path(header_path).resolve()
    header = render_header(*synthetic_config()) if synthetic else header_path.read_text(encoding='ascii')
    parse_header(header)
    work.mkdir(parents=True)
    inputs = {str((ROOT/name).resolve()): sha(ROOT/name) for name in (*COMPILE, *HEADERS, *HELPERS)}
    if header_path is not None:
        inputs[str(header_path)] = sha(header_path)
    report = {'Schema': 'camera720-corrected-system-simulation-v1', 'Prepared': False, 'Passed': False,
              'SimulationExecuted': False, 'StartedUTC': datetime.now(timezone.utc).isoformat(),
              'InputSHA256': inputs, 'ModelKind': 'synthetic_test_only' if synthetic else 'supplied_header_unaccepted',
              'SourceGeometry': [WIDTH, HEIGHT], 'OutputActiveArea': [1920, 1080], 'Commands': [],
              'HardwareAccessed': False, 'PDSAccessed': False, 'PhysicalIPExecuted': False,
              'OpticalCalibrationAccepted': False, 'MeasuredFrameRate': None,
              'RTLResultUsedForGolden': False,
              'Limits': 'Independent CPU fixture preparation is not RTL execution. Optional full system simulation uses synthetic sensor and DDR models, the production camera/controller/mapper/scan, and test-only or supplied unaccepted coefficients. No actual lens, SCCB, board startup, electrical timing, physical DDR/HDMI, clock-stop recovery, or measured FPS acceptance.'}
    hashes, started = {}, time.monotonic()
    try:
        expected, records, model = fixtures(work, header)
        if synthetic and any(r['ChangedPixels'] == 0 or r['SourceCRC32'] == r['CorrectedCRC32'] for r in records):
            raise ValueError('synthetic correction must exercise distinct source and result CRCs')
        report.update(Model=model, Frames=records, Prepared=True)
        hashes = {p.name: sha(p) for p in work.iterdir() if p.is_file()}
        report['FixtureSHA256'] = hashes
        if execute_simulation:
            compiled, bindings = prepare_compile_sources(ROOT, COMPILE, HEADERS, work)
            report['CompileBindings'] = bindings
            bin_dir = resolve_vivado_bin(ROOT.parent)
            for executable, args, stage in (
                    ('xvlog.bat', ['--sv', *map(str, compiled)], 'compile'),
                    ('xelab.bat', ['tb_camera720_corrected_system', '-s', 'camera720_corrected_system', '--timescale', '1ps/1ps', '--O3'], 'elaborate'),
                    ('xsim.bat', ['camera720_corrected_system', '-runall', '-log', 'simulation.log'], 'simulate')):
                item = {'Stage': stage, 'NativeArgv': [str(bin_dir/executable), *args], 'ReturnCode': None}
                report['Commands'].append(item)
                tool(bin_dir, executable, args, work, started+maximum_seconds, stage)
                item['ReturnCode'] = 0
                if stage == 'simulate':
                    report['SimulationExecuted'] = True
            log = (work/'simulation.log').read_text(encoding='utf-8', errors='replace')
            if MARKER not in log or '$finish called' not in log or re.search(r'(?im)^\s*(?:fatal|error):', log):
                raise ValueError('complete corrected system simulator pass marker missing')
            summary = json.loads((work/'summary.json').read_text(encoding='ascii'))
            identity.validate_summary(summary)
            scans = validate_outputs(work, expected, records, summary)
            verify_compile_sources(ROOT, COMPILE, HEADERS, work, bindings)
            report.update(Passed=True, Summary=summary, ActualScanChecks=scans, ActualScanPixelsCompared=summary['scanned_pixels'])
    except (Exception, KeyboardInterrupt) as error:
        report['Error'] = type(error).__name__+': '+str(error)
    finally:
        report['InputSHA256After'] = {name: sha(name) if Path(name).is_file() else None for name in inputs}
        report['FixtureSHA256After'] = {name: sha(work/name) if (work/name).is_file() else None for name in hashes}
        if inputs != report['InputSHA256After'] or hashes != report['FixtureSHA256After']:
            report.update(Passed=False, Prepared=False, SourceOrFixtureDrift=True)
        report['ElapsedSeconds'] = round(time.monotonic()-started, 3)
        report['LogSHA256'] = {p.name: sha(p) for p in work.glob('*.log')}
        report['ResultSHA256'] = {name: sha(work/name) for name in ('summary.json', 'events.csv', 'scan-pixels.mem') if (work/name).is_file()}
        (work/REPORT).write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps({'Prepared': report['Prepared'], 'Passed': report['Passed'], 'SimulationExecuted': report['SimulationExecuted'],
                      'Error': report.get('Error'), 'Report': str(work/REPORT)}))
    return 0 if not report.get('Error') and report['Prepared'] and (not execute_simulation or report['Passed']) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--synthetic', action='store_true', help='test-only nonlinear coefficients; not a lens profile')
    group.add_argument('--header', type=Path, help='C720 decimal localparams; input remains optically unaccepted')
    parser.add_argument('--execute-simulation', action='store_true', help='explicitly launch modeled system simulator; default is CPU preparation only')
    parser.add_argument('--maximum-seconds', type=int, default=1800)
    args = parser.parse_args()
    return run(args.workdir, synthetic=args.synthetic, header_path=args.header,
               execute_simulation=args.execute_simulation, maximum_seconds=args.maximum_seconds)


if __name__ == '__main__':
    raise SystemExit(main())
