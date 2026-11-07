"""Exact frozen system/fixture replay with only the experimental cache replaced."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = ROOT / 'distortion/work/hdmi-camera-fisheye-tile8df8-20261103-a'
LAB = ROOT / 'output/new-next-probe-20261104'
SOURCE = ROOT / 'distortion/rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill_tagpipe.v'
PIN = 'cc47c00bf2458491c1def0c5be3a2f8d209269a57dc2259d46ce7ce1054486a1'
CACHE = 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v'
sys.path.insert(0, str(ROOT / '.venv/Lib/site-packages'))
sys.path.insert(0, str(ROOT / 'distortion/tools'))
from run_fill8_rowpipe_cache_sim import run_tool
from simulation_tools import resolve_vivado_bin
import run_hdmi_camera_fisheye_tile8df8_system_sim as normal
import run_hdmi_camera_fisheye_tile8df8_sustained_sim as sustained


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=('normal', 'sustained'), required=True)
    parser.add_argument('--mode', choices=('small', 'native'), required=True)
    args = parser.parse_args()
    family = normal if args.kind == 'normal' else sustained
    original_name = 'system-' + ('sustained-' if args.kind == 'sustained' else '') + args.mode + '-a'
    original = BASE / original_name
    baseline_path = original / 'simulation.json'
    baseline = read(baseline_path)
    require(baseline['Passed'] is True and baseline['Mode'] == args.mode, 'actual complete baseline required')
    require(sha(SOURCE) == PIN, 'experimental cache identity differs')
    unit_path = HERE / 'direct10-tagpipe-unit-a/simulation.json'
    unit = read(unit_path)
    require(unit['Passed'] is True and unit['InputDrift'] == [] and
            unit['InputSHA256'].get(str(SOURCE)) == PIN, 'same-source completed unit oracle required')
    work = LAB / ('direct10-tagpipe-' + args.kind + '-' + args.mode + '-a')
    require(not work.exists(), 'fresh isolated simulation directory required')
    small_gate = None
    if args.mode == 'native':
        small_path = LAB / ('direct10-tagpipe-' + args.kind + '-small-a/simulation.json')
        small_gate = read(small_path)
        require(small_gate['Passed'] is True and small_gate['CacheSHA256'] == PIN and
                small_gate['InputDrift'] == [], 'same-kind/same-cache small gate required')
    watched = {str(p.resolve()): sha(p) for p in (Path(__file__), SOURCE, baseline_path, unit_path,
               Path(normal.__file__), Path(sustained.__file__), ROOT / 'distortion/tools/run_fill8_rowpipe_cache_sim.py',
               ROOT / 'distortion/tools/simulation_tools.py')}
    for name, digest in unit['InputSHA256'].items():
        require(sha(name) == digest, 'actual completed unit input drift')
        require(name not in watched or watched[name] == digest, 'unit/native input identity conflict')
        watched[name] = digest
    operations = []
    transformed = {}
    compiled = []
    for name, row in baseline['CompileSnapshot'].items():
        path = Path(row['Path'])
        require(sha(path) == row['SHA256'], 'frozen actual prepared source differs: ' + name)
        watched[str(path)] = row['SHA256']
        production_path = ROOT / 'distortion' / name
        require(sha(production_path) == baseline['SourceSHA256'][name], 'frozen production source drift: ' + name)
        watched[str(production_path)] = baseline['SourceSHA256'][name]
        src = SOURCE if name == CACHE else path
        dst = work / 'compiled-sources' / name
        operations.append((src, dst, sha(src)))
        if name == 'rtl/experimental/hdmi_camera_fisheye_engine_tile8df8.v':
            original_data = path.read_bytes()
            require(original_data.count(b'.INDEX_BITS(8)') == 1, 'unique original engine cache capacity required')
            transformed[dst] = original_data.replace(b'.INDEX_BITS(8)', b'.INDEX_BITS(10)')
        compiled.append(dst)
    require(len(compiled) == 22 and CACHE in baseline['CompileSnapshot'], 'complete selected system source closure required')
    for name, digest in baseline['FixtureSHA256'].items():
        src = original / name
        require(sha(src) == digest, 'frozen pixel/CRC fixture differs: ' + name)
        watched[str(src)] = digest
        operations.append((src, work / name, digest))
        if name == 'config.vh':
            config = src.read_bytes()
            require(config.count(b'SIM_CACHE_INDEX_BITS=8') == 1, 'unique original bench cache capacity required')
            transformed[work / name] = config.replace(b'SIM_CACHE_INDEX_BITS=8', b'SIM_CACHE_INDEX_BITS=10')
    headers = list((original / 'relocated-headers').rglob('*.vh'))
    require(len(headers) == 3, 'complete actual header set required')
    for src in headers:
        name = src.relative_to(original).as_posix()
        relative_source = src.relative_to(original / 'relocated-headers').as_posix()
        require(sha(src) == baseline['SourceSHA256'][relative_source], 'frozen relocated header drift')
        watched[str(src)] = sha(src)
        operations.append((src, work / name, sha(src)))
    work.mkdir(parents=True)
    for src, dst, digest in operations:
        dst.parent.mkdir(parents=True, exist_ok=True)
        with src.open('rb') as reader, dst.open('xb') as writer:
            if dst in transformed:
                writer.write(transformed[dst])
            else:
                shutil.copyfileobj(reader, writer)
        expected_digest = hashlib.sha256(transformed[dst]).hexdigest() if dst in transformed else digest
        require(sha(dst) == expected_digest, 'exact transformed input copy drift')
        watched[str(dst)] = expected_digest
    if args.mode == 'native':
        small_path = LAB / ('direct10-tagpipe-' + args.kind + '-small-a/simulation.json')
        watched[str(small_path)] = sha(small_path)
        for name, digest in small_gate['InputSHA256'].items():
            require(sha(name) == digest, 'same-source completed small input drift')
            require(name not in watched or watched[name] == digest, 'small/native input identity conflict')
            watched[name] = digest
    if args.mode == 'native':
        for name in baseline['CompileSnapshot']:
            small_source = small_path.parent / 'compiled-sources' / name
            native_source = work / 'compiled-sources' / name
            require(sha(small_source) == sha(native_source), 'small/native canonical prepared source differs: ' + name)
        for header in headers:
            rel = header.relative_to(original)
            require(sha(small_path.parent / rel) == sha(work / rel), 'small/native canonical header differs')
    report = {'Schema': 'tile8-direct10-tagpipe-full-system-research-v1', 'Passed': False,
              'Kind': args.kind, 'Mode': args.mode, 'StartedUTC': datetime.now(timezone.utc).isoformat(),
              'CacheSHA256': PIN, 'InputSHA256': watched, 'BaselineReceipt': {'Path': str(baseline_path), 'SHA256': sha(baseline_path)},
              'ProductionLogicChanges': [CACHE, 'engine INDEX_BITS8to10'], 'BenchConfigChange': 'SIM_CACHE_INDEX_BITS8to10',
              'SmallGate': {'Path': str(small_path), 'SHA256': sha(small_path)} if small_gate else None,
              'CacheIndexBits': 10, 'CapacityBytes': 262144, 'CanonicalSmallNativeSourceClosureVerified': args.mode == 'native', 'OriginalBenchAndAllAssertionsUnchanged': True,
              'OriginalPixelCRCFixturesCopiedExactly': True, 'OriginalProductionRTLModified': False,
              'NativeEDAExecuted': False, 'HardwareAccessed': False, 'TimingOrBoardAcceptance': False,
              'InputDrift': [], 'Commands': []}
    started = time.monotonic()
    try:
        tool_dir = resolve_vivado_bin(ROOT)
        deadline = started + (300 if args.mode == 'small' else 3600)
        top = family.TOP
        for executable, argv, stage in (
            ('xvlog.bat', ['--sv', *map(str, compiled)], 'compile'),
            ('xelab.bat', [top, '-s', 'combined_' + args.kind + '_c'], 'elaborate'),
            ('xsim.bat', ['combined_' + args.kind + '_c', '-runall', '-log', 'simulation.log'], 'simulate')):
            run_tool(tool_dir, executable, argv, work, deadline, stage)
            report['Commands'].append({'Stage': stage, 'ReturnCode': 0})
        log = (work / 'simulation.log').read_text(errors='replace')
        require(family.MARKER in log and '$finish called' in log and
                not re.search(r'(?im)^\s*(fatal|error):', log), 'original full-system assertions/finish failed')
        summary, rows = family.assess(work, baseline['Fixture'], 'directfill')
        report.update(Passed=True, Summary=summary, Frames=rows,
            Performance=list(csv.DictReader((work / 'performance.csv').open(newline=''))),
            ResetProbe=family.reset_probe(log, args.mode))
        old_frames = baseline['Frames']
        report['ProcessingCycleComparison'] = [
            {'FrameID': int(new['frame_id']), 'OldCycles': int(old['hardware_process_cycles']),
             'NewCycles': int(new['hardware_process_cycles']),
             'SavedCycles': int(old['hardware_process_cycles']) - int(new['hardware_process_cycles'])}
            for old, new in zip(old_frames, rows)]
    except Exception as error:
        report['Error'] = type(error).__name__ + ': ' + str(error)
    report['InputDrift'] = [name for name, digest in watched.items() if sha(name) != digest]
    report['Passed'] = report['Passed'] and not report['InputDrift']
    report['ElapsedSeconds'] = round(time.monotonic() - started, 3)
    report['EndedUTC'] = datetime.now(timezone.utc).isoformat()
    with (work / 'simulation.json').open('x', encoding='utf-8') as target:
        json.dump(report, target, indent=2); target.write('\n')
    print(json.dumps({key: report.get(key) for key in ('Passed', 'Kind', 'Mode', 'Error', 'ElapsedSeconds', 'InputDrift', 'ProcessingCycleComparison')}))
    raise SystemExit(0 if report['Passed'] else 1)


if __name__ == '__main__':
    main()
