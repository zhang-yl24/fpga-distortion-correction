"""Execute the actual-AA HEAD0/TAG25 cache differential test; no EDA/hardware."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
HASHES = {'AA': 'ff5e551c13083cecf9325b6acef0a00b58f7f1776cd7f5dbec341e52f2082088',
          'AE': '7a34f75eca6cd8e7eb74ab1adf347572431e26bb8c820b8d2e0032fcc38fed19'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iverilog', default='iverilog')
    parser.add_argument('--vvp', default='vvp')
    parser.add_argument('--output', default='rtl-result')
    parser.add_argument('--testbench', choices=('actual_head0', 'directed_native'), default='actual_head0')
    args = parser.parse_args()
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=False)
    receipt = {'Schema': 'AA_AE_HEAD0_RTL_1', 'Status': 'running', 'Case': args.testbench, 'PDSRun': False,
               'BoardRun': False, 'SourceSHA256': HASHES,
               'ActualConfiguration': {'WIDTH': 1920, 'HEIGHT': 1080, 'INDEX_BITS': 7,
                   'TAG_W': 25, 'QUERY_DEPTH': 4096, 'LOOKAHEAD': 512,
                   'CACHE_ROW_STRIDE': 2, 'HEAD_PREDECODE': 0, 'COMPACT_COORDS': 1,
                   'CANDIDATE_KEY_PIPE': 2, 'AREA_PROFILE': 2, 'TIMEOUT_BITS': 26,
                   'ExpectedTokenWidth': 63},
               'MeasuredResourceOrTimingGainClaim': False}
    try:
        for name, expected in HASHES.items():
            source = ROOT / 'sources' / f'cache_{name}.sv'
            text = source.read_text()
            if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                raise ValueError(f'{name} source hash mismatch')
            renamed = text.replace('module d256_runtime_prefetch_cache #(',
                                  f'module {"cache_baseline" if name == "AA" else "cache_fallback"} #(', 1)
            target = out / f'cache_{name}.sv'
            target.write_text(renamed)
        executable = out / 'actual_head0.vvp'
        testbench = 'tests/tb_' + args.testbench + '.sv'
        command = [args.iverilog, '-g2012', '-s', 'tb_full_cache_ab', '-o', str(executable),
                   testbench, str(out / 'cache_AA.sv'), str(out / 'cache_AE.sv'),
                   'deps/sync_token_fifo.sv', 'deps/quad_parity_prefetch_store.sv']
        start = time.monotonic()
        with (out / 'compile.log').open('w') as log:
            run = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=120)
        receipt['CompileExit'] = run.returncode
        if run.returncode:
            raise RuntimeError('HDL compile failed; inspect compile.log')
        with (out / 'run.log').open('w') as log:
            run = subprocess.run([args.vvp, str(executable)], cwd=ROOT, stdout=log,
                                 stderr=subprocess.STDOUT, timeout=600)
        receipt['RunExit'] = run.returncode
        receipt['ElapsedSeconds'] = time.monotonic() - start
        text = (out / 'run.log').read_text()
        if run.returncode or 'PASS_FULL_CACHE_AB' not in text:
            raise RuntimeError('HDL comparison failed or did not finish')
        receipt['PassMarkers'] = [line for line in text.splitlines() if line.startswith('PASS_')]
        final = next(line for line in receipt['PassMarkers'] if line.startswith('PASS_FULL_CACHE_AB'))
        receipt['Metrics'] = {k: int(v) for k, v in re.findall(r'(queries|frames|outputs|ar|max_fifo|triple_overlap|cycles)=(\d+)', final)}
        receipt['RunLogSHA256'] = hashlib.sha256((out / 'run.log').read_bytes()).hexdigest()
        receipt['TestbenchSHA256'] = hashlib.sha256((ROOT / testbench).read_bytes()).hexdigest()
        receipt['Status'] = 'PASS_ACTUAL_HEAD0_TAG25_FIFO63_RTL_DIFFERENTIAL'
    except Exception as error:
        receipt['Status'] = 'FAILED_OR_BLOCKED'
        receipt['Error'] = f'{type(error).__name__}: {error}'
        raise
    finally:
        (out / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
