"""Preserved independent pixel/fault oracle for isolated decoded-slow RTL."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'distortion/tools'))
from run_fill8_rowpipe_cache_sim import run_tool
from simulation_tools import resolve_vivado_bin
import run_directfill_rowpipe_cache_sim as oracle


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.parent != HERE:
        raise ValueError('fresh output under this isolated probe directory required')
    source = HERE / 'dead-select-probe-d.v'
    manifest = json.loads((HERE / 'dead-select-probe-source-d.json').read_text())
    if sha(source) != manifest['Variant']['SHA256']:
        raise ValueError('experimental source identity differs')
    bench = ROOT / 'distortion/tests/tb_directfill_rowpipe_cache.sv'
    if sha(bench) != '1095a80958e59950fe2ff49a8ff10401e4a17ddb5a32e1c817515cf05c20f5f4':
        raise ValueError('preserved independent oracle differs')
    watched = {str(p): sha(p) for p in (source, bench, Path(__file__), Path(oracle.__file__),
               ROOT / 'distortion/tools/run_fill8_rowpipe_cache_sim.py', ROOT / 'distortion/tools/simulation_tools.py')}
    output.mkdir()
    result = {'Schema': 'tile8-dead-select-unit-experiment-v1', 'Passed': False,
              'StartedUTC': datetime.now(timezone.utc).isoformat(), 'InputSHA256': watched,
              'ExperimentalOnly': True, 'OriginalProductionRTLModified': False,
              'NativeEDAExecuted': False, 'HardwareAccessed': False, 'FullFrameSimulated': False}
    started = time.monotonic()
    try:
        binary = resolve_vivado_bin(ROOT)
        deadline = started + 300
        run_tool(binary, 'xvlog.bat', ['--sv', str(source), str(bench)], output, deadline, 'compile')
        run_tool(binary, 'xelab.bat', ['tb_directfill_rowpipe_cache', '-s', 'dead_select_unit_d'], output, deadline, 'elaborate')
        run_tool(binary, 'xsim.bat', ['dead_select_unit_d', '-runall', '-log', 'simulation.log'], output, deadline, 'simulate')
        result['OriginalIndependentOracleCases'] = oracle.validate(output)
        result['Passed'] = True
    except Exception as error:
        result['Error'] = type(error).__name__ + ': ' + str(error)
    result['InputDrift'] = [name for name, digest in watched.items() if sha(Path(name)) != digest]
    result['Passed'] = result['Passed'] and not result['InputDrift']
    result['ElapsedSeconds'] = round(time.monotonic() - started, 3)
    with (output / 'simulation.json').open('x', encoding='utf-8') as target:
        json.dump(result, target, indent=2); target.write('\n')
    print(json.dumps({k: result.get(k) for k in ('Passed', 'Error', 'ElapsedSeconds', 'InputDrift')}))
    raise SystemExit(0 if result['Passed'] else 1)


if __name__ == '__main__':
    main()
