"""Bounded simulation of the actual registered raw-camera power-on release.

Read-only planning is the default. --execute runs only Vivado simulation; no
PDS, bitstream, serial port, programmer, or connected board is accessed.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

from run_gamma_pipeline_d5_sim import tool
from simulation_tools import resolve_vivado_bin

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work/raw-camera-upright'
SOURCES = ('rtl/experimental/raw_camera_power_ready.v', 'tests/tb_raw_camera_power_ready.sv')
HELPERS = ('tools/run_raw_camera_power_ready_sim.py', 'tools/run_gamma_pipeline_d5_sim.py',
           'tools/simulation_tools.py')
PASS = ('RAW_CAMERA_POWER_READY_PASS edges=1048608 checks=2097216 '
        'small_release_edge=8 native_release_edge=1048576 hold_edges=32')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def plan(work, maximum_seconds=180):
    work = Path(work).absolute()
    if work != work.resolve() or work.parent != WORK or work.exists() or not re.fullmatch(r'[A-Za-z0-9_-]+', work.name):
        raise ValueError('fresh canonical direct work/raw-camera-upright child required')
    if type(maximum_seconds) is not int or not 30 <= maximum_seconds <= 300:
        raise ValueError('whole simulation deadline must be 30..300 seconds')
    bin_dir = resolve_vivado_bin(ROOT.parent).resolve()
    stages = [
        ('xvlog.bat', ['--sv', *[str(ROOT / name) for name in SOURCES]], 'compile'),
        ('xelab.bat', ['tb_raw_camera_power_ready', '-s', 'raw_camera_power_ready_tb',
                       '--timescale', '1ns/1ps'], 'elaborate'),
        ('xsim.bat', ['raw_camera_power_ready_tb', '-runall', '-log', 'simulation.log'], 'simulate'),
    ]
    if not all((bin_dir / name).is_file() for name, _, _ in stages):
        raise ValueError('required Vivado simulation tools are missing')
    record = {'Schema': 'raw-camera-power-ready-simulation-v1', 'Passed': False,
              'WorkDirectory': str(work), 'MaximumSeconds': maximum_seconds,
              'SourceSHA256': {name: sha(ROOT / name) for name in SOURCES + HELPERS},
              'Commands': [{'Stage': stage, 'Argv': [str(bin_dir / name), *args]}
                           for name, args, stage in stages],
              'HardwareAccessed': False, 'PDSAccessed': False, 'PowerDelayAccelerated': False,
              'Limits': 'RTL startup release only, including all1048576 production clock edges. '
                        'No FPGA power-up/init-state, reset CDC, recovery/removal or external timing acceptance.'}
    return work, bin_dir, stages, record


def run(work, maximum_seconds=180):
    work, bin_dir, stages, record = plan(work, maximum_seconds)
    work.mkdir(parents=True)
    started = time.monotonic()
    record['StartedUTC'] = datetime.now(timezone.utc).isoformat()
    try:
        for name, args, stage in stages:
            tool(bin_dir, name, args, work, started + maximum_seconds, stage)
        log = (work / 'simulation.log').read_text(encoding='utf-8', errors='replace')
        lines = [line.strip() for line in log.splitlines() if line.startswith('RAW_CAMERA_POWER_READY_')]
        if lines != [PASS] or re.search(r'(?im)^\s*(?:fatal|error):', log):
            raise ValueError('startup assertion coverage did not complete exactly')
        record.update(Passed=True, PassLine=PASS)
    except (Exception, KeyboardInterrupt) as error:
        record['Error'] = type(error).__name__ + ': ' + str(error)
    finally:
        record['SourceDrift'] = [name for name, digest in record['SourceSHA256'].items()
                                 if sha(ROOT / name) != digest]
        record['Passed'] = record['Passed'] and not record['SourceDrift']
        record['ElapsedSeconds'] = round(time.monotonic() - started, 3)
        record['LogSHA256'] = {p.name: sha(p) for p in work.glob('*.log')}
        (work / 'startup-simulation.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--maximum-seconds', type=int, default=180)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.execute:
        result = run(args.work_dir, args.maximum_seconds)
        print(json.dumps({k: result[k] for k in ('Passed', 'ElapsedSeconds', 'SourceDrift', 'HardwareAccessed')},
                         ensure_ascii=False))
        return 0 if result['Passed'] else 1
    _, _, _, result = plan(args.work_dir, args.maximum_seconds)
    print(json.dumps({**result, 'PreparedOnly': True, 'EDAExecuted': False}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
