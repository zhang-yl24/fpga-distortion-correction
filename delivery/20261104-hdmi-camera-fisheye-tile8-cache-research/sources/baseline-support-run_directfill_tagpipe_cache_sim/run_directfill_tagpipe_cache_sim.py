"""Actual direct-fill cache simulation with independent pixels and stream CRC."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
import zlib

from run_fill8_rowpipe_cache_sim import run_tool
from simulation_tools import resolve_vivado_bin

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'work/hdmi-camera-fisheye-tile8df9-tagpipe-20261103-a'
SOURCE = ROOT / 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill_tagpipe.v'
BENCH = ROOT / 'tests/tb_directfill_tagpipe_cache.sv'
CASES = ((639, 480, 3), (1920, 1080, 7), (1920, 1080, 8), (1920, 1080, 9))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rgb(x, y, bank, epoch, width, height):
    if not (0 <= x < width and 0 <= y < height):
        return 0
    position = y * width + x
    pixel = (position * 109 + (position >> 3) * 53 +
             (position ^ (position >> 9)) * 17 + 0xac37 + bank * 0x2513 + epoch * 0x149b) & 65535
    red, green, blue = pixel >> 11, (pixel >> 5) & 63, pixel & 31
    return ((red << 3 | red >> 2) << 16 |
            (green << 2 | green >> 4) << 8 | blue << 3 | blue >> 2)


def validate_trace(path, width, height):
    pending, actual, expected, outputs = {}, bytearray(), bytearray(), 0
    for line in path.read_text().splitlines():
        fields = line.split()
        if fields[0] == 'Q':
            x, y, tag, bank, epoch = map(int, fields[1:])
            require(tag not in pending, 'duplicate sparse oracle tag')
            pending[tag] = (x, y, bank, epoch)
        elif fields[0] == 'O':
            p00, p10, p01, p11, fx, fy, tag = (int(item, 16) for item in fields[1:])
            require(tag in pending, 'output without accepted query')
            x, y, bank, epoch = pending.pop(tag)
            x0, y0 = x // 256, y // 256
            pixels = [rgb(x0 + dx, y0 + dy, bank, epoch, width, height)
                      for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1))]
            require([p00, p10, p01, p11] == pixels and fx == (x & 255) and fy == (y & 255),
                    'independent Python pixel/fraction oracle differs')
            for values, target in (((p00, p10, p01, p11), actual), (pixels, expected)):
                for pixel in values:
                    target.extend(pixel.to_bytes(3, 'big'))
                target.extend((fx, fy))
                target.extend(tag.to_bytes(4, 'big'))
            outputs += 1
        else:
            raise ValueError('invalid independent trace record')
    require(set(pending) == {500}, 'only the deliberate last-commit reset query may be canceled')
    require(actual == expected and outputs > 250, 'complete independent stream differs')
    require(zlib.crc32(actual) == zlib.crc32(expected), 'independent stream CRC differs')
    return {'Outputs': outputs, 'OracleBytes': len(actual), 'CRC32': f'{zlib.crc32(actual):08x}',
            'SHA256': hashlib.sha256(actual).hexdigest(), 'ResetCanceledQueries': 1,
            'ActualMatchesIndependentPixelOracle': True}


def validate(work):
    log = (work / 'simulation.log').read_text(errors='replace')
    require('PASS TAGPIPE complete independent cache regression' in log and '$finish called' in log,
            'complete simulation finish marker required')
    require(not re.search(r'(?im)^\s*(fatal|error):', log), 'RTL assertion failure')
    cases = {}
    for width, height, index in CASES:
        suffix = f'{width}-i{index}'
        value = json.loads((work / ('summary-' + suffix + '.json')).read_text())
        exact = {'passed': True, 'width': width, 'height': height, 'index_bits': index,
                 'commits_per_fill': 8, 'reset_before_last_commit': 1, 'fault_cases': 6,
                 'warm_stream_outputs': 64, 'warm_span_cycles': 63, 'warm_first_valid_latency': 5}
        require(all(type(value.get(key)) is type(expected) and value[key] == expected
                    for key, expected in exact.items()), 'missing exact coverage: ' + suffix)
        require(value['complete_fills'] >= 10 and value['ram_pixels_checked'] == value['complete_fills'] * 128,
                'all 128 pixels of each complete RAM line must be checked')
        positive = ('same_cycle_first_beats', 'delayed_first_beats', 'continuous_commit_pairs',
                    'normal_outputs', 'ar_stalls', 'r_gaps', 'output_stalls', 'input_stalls',
                    'queue_full', 'frame_pending', 'fast_queries', 'slow_queries', 'frame_drains',
                    'lookup_miss_overlap', 'query_refreshes', 'stale_valid_refreshes',
                    'result_stall_metadata_cycles', 'slow_lookup_cycles')
        require(all(type(value.get(key)) is int and value[key] > 0 for key in positive),
                'vacuous handshake/commit coverage: ' + suffix)
        trace = validate_trace(work / ('trace-' + suffix + '.txt'), width, height)
        require(trace['Outputs'] == value['normal_outputs'], 'stream output coverage differs')
        cases[suffix] = {**value, 'IndependentTrace': trace}
    return cases


def run(output, maximum):
    output = Path(output).resolve()
    require(not output.exists() and output.is_relative_to(BASE.resolve()) and
            output.name.startswith('cache-unit-') and 30 <= maximum <= 600,
            'fresh bounded cache-unit-* under the isolated candidate WORK required')
    output.mkdir(parents=True)
    helpers = (Path(__file__).resolve(), ROOT / 'tools/run_fill8_rowpipe_cache_sim.py',
               ROOT / 'tools/simulation_tools.py')
    watched = {str(path.resolve()): sha(path) for path in (SOURCE, BENCH, *helpers)}
    result = {'Schema': 'tile8-directfill-tagpipe-independent-cache-simulation-v1', 'Passed': False,
              'StartedUTC': datetime.now(timezone.utc).isoformat(), 'SourceSHA256': watched,
              'PDSAccessed': False, 'HardwareAccessed': False, 'FullFrameSimulated': False,
              'Oracle': 'Independent signed coordinate, RGB565 source, four-neighbour/fraction/tag stream and Python CRC32.',
              'SingleRegisteredBeatPerWrite': True, 'PostReceiveScatterCycles': 0}
    started = time.monotonic()
    try:
        binary = resolve_vivado_bin(ROOT.parent)
        result['VivadoBin'] = str(binary)
        deadline = started + maximum
        run_tool(binary, 'xvlog.bat', ['--sv', str(SOURCE), str(BENCH)], output, deadline, 'compile')
        run_tool(binary, 'xelab.bat', ['tb_directfill_tagpipe_cache', '-s', 'tagpipe_tb'], output, deadline, 'elaborate')
        run_tool(binary, 'xsim.bat', ['tagpipe_tb', '-runall', '-log', 'simulation.log'], output, deadline, 'simulate')
        result['Cases'] = validate(output)
        result['Passed'] = True
    except BaseException as error:
        result['Error'] = type(error).__name__ + ': ' + str(error)
    result['InputDrift'] = [name for name, digest in watched.items() if sha(name) != digest]
    if result['InputDrift']:
        result['Passed'] = False
    result['ElapsedSeconds'] = round(time.monotonic() - started, 3)
    result['EndedUTC'] = datetime.now(timezone.utc).isoformat()
    result['ArtifactsSHA256'] = {str(path.relative_to(output)): sha(path) for path in output.rglob('*')
                               if path.is_file() and path.suffix in ('.log', '.txt', '.json')}
    with (output / 'simulation.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--maximum-seconds', type=int, default=240)
    args = parser.parse_args()
    value = run(args.output, args.maximum_seconds)
    print(json.dumps({key: value.get(key) for key in ('Passed', 'Error', 'ElapsedSeconds', 'InputDrift', 'Cases')}, indent=2))
    raise SystemExit(0 if value['Passed'] else 1)
