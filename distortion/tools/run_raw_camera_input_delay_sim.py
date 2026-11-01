"""Simulate eight real vendor input delay models without PDS or board access."""
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
VENDOR = Path('D:/pango/PDS_2023.2/arch/vendor/pango/verilog/simulation')
MODELS = ('GTP_INBUF.v', 'GTP_ZEROHOLDDELAY.v')
SOURCES = ('rtl/experimental/raw_camera_input_delay.v', 'tests/tb_raw_camera_input_delay.sv')
HELPERS = ('tools/run_raw_camera_input_delay_sim.py', 'tools/run_gamma_pipeline_d5_sim.py', 'tools/simulation_tools.py')
PASS = 'RAW_CAMERA_INPUT_DELAY_PASS values=256 checks=768 bits=8 nominal_delay_ps=1500'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(work, execute=False):
    work = Path(work).absolute()
    if work != work.resolve() or work.parent != WORK or work.exists() or not re.fullmatch(r'[A-Za-z0-9_-]+', work.name):
        raise ValueError('fresh canonical direct raw-camera-upright work directory required')
    binary = resolve_vivado_bin(ROOT.parent).resolve()
    paths = [VENDOR / n for n in MODELS] + [ROOT / n for n in SOURCES]
    watched = {str(p.resolve()):sha(p) for p in paths + [ROOT / n for n in HELPERS]}
    stages = [('xvlog.bat', ['--sv', *map(str, paths)], 'compile'),
              ('xelab.bat', ['tb_raw_camera_input_delay', '-s', 'raw_camera_input_delay_tb', '--timescale', '1ps/1ps'], 'elaborate'),
              ('xsim.bat', ['raw_camera_input_delay_tb', '-runall', '-log', 'simulation.log'], 'simulate')]
    if not all((binary / name).is_file() for name, _, _ in stages):
        raise ValueError('Vivado simulation tools missing')
    record = {'Schema':'raw-camera-input-delay-simulation-v1', 'Passed':False, 'MaximumSeconds':120,
              'InputSHA256':watched, 'Commands':[{'Stage':stage, 'Argv':[str(binary/name), *args]} for name,args,stage in stages],
              'EDAExecuted':execute, 'PDSAccessed':False, 'HardwareAccessed':False,
              'Limits':'Vendor functional simulation only. Nominal 1500ps does not prove mapped hardware, PVT delay, or external timing acceptance.'}
    if not execute: return record
    work.mkdir()
    started = time.monotonic(); record['StartedUTC'] = datetime.now(timezone.utc).isoformat()
    try:
        for name, args, stage in stages:
            tool(binary, name, args, work, started+120, stage)
        log = (work / 'simulation.log').read_text(encoding='utf-8', errors='replace')
        if [line.strip() for line in log.splitlines() if line.startswith('RAW_CAMERA_INPUT_DELAY_')] != [PASS]:
            raise ValueError('complete vendor delay coverage marker missing')
        if re.search(r'(?im)^\s*(?:fatal|error):', log): raise ValueError('vendor simulation reported an error')
        record.update(Passed=True, PassLine=PASS)
    except (Exception, KeyboardInterrupt) as error:
        record['Error'] = type(error).__name__ + ': ' + str(error)
    finally:
        record['InputDrift'] = [p for p,h in watched.items() if sha(p) != h]
        record['Passed'] = record['Passed'] and not record['InputDrift']
        record['ElapsedSeconds'] = round(time.monotonic()-started, 3)
        record['LogSHA256'] = {p.name:sha(p) for p in work.glob('*.log')}
        (work / 'input-delay-simulation.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8', newline='\n')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args(); value = run(args.work_dir, args.execute)
    print(json.dumps({k:value[k] for k in ('Passed','EDAExecuted','ElapsedSeconds','InputDrift','Error') if k in value}))
    return 0 if not args.execute or value['Passed'] else 1


if __name__ == '__main__': raise SystemExit(main())
