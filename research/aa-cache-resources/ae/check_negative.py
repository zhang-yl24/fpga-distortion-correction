"""Require the directed checker to reject an intentionally broken AE comparator."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--iverilog', default='iverilog')
    p.add_argument('--vvp', default='vvp')
    p.add_argument('--output', default='rtl-negative-mutation')
    args = p.parse_args()
    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=False)
    original = (ROOT / 'sources/cache_AA.sv').read_text()
    if hashlib.sha256((ROOT / 'sources/cache_AA.sv').read_bytes()).hexdigest() != 'ff5e551c13083cecf9325b6acef0a00b58f7f1776cd7f5dbec341e52f2082088':
        raise ValueError('AA source identity changed')
    baseline = out / 'baseline.sv'
    baseline.write_text(original.replace('module d256_runtime_prefetch_cache #(', 'module cache_baseline #(', 1))
    source = (ROOT / 'sources/cache_AE.sv').read_text()
    if hashlib.sha256((ROOT / 'sources/cache_AE.sv').read_bytes()).hexdigest() != '7a34f75eca6cd8e7eb74ab1adf347572431e26bb8c820b8d2e0032fcc38fed19':
        raise ValueError('AE source identity changed')
    old = 'NATIVE_TAG8 ? head_line[h]==head_line[z]:head_block[h]==head_block[z]'
    assert source.count(old) == 1
    source = source.replace(old, "NATIVE_TAG8 ? 1'b1:head_block[h]==head_block[z]")
    source = source.replace('module d256_runtime_prefetch_cache #(', 'module cache_fallback #(', 1)
    mutant = out / 'INTENTIONALLY_BROKEN_TEST_ONLY.sv'
    mutant.write_text(source)
    executable = out / 'negative.vvp'
    command = [args.iverilog, '-g2012', '-s', 'tb_full_cache_ab', '-o', str(executable),
               'tests/tb_directed_native.sv', str(baseline), str(mutant),
               'deps/sync_token_fifo.sv', 'deps/quad_parity_prefetch_store.sv']
    with (out / 'compile.log').open('w') as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=120)
    if result.returncode:
        raise RuntimeError('Negative test did not compile; this is not a successful rejection')
    with (out / 'run.log').open('w') as log:
        result = subprocess.run([args.vvp, str(executable)], cwd=ROOT,
                                stdout=log, stderr=subprocess.STDOUT, timeout=120)
    text = (out / 'run.log').read_text()
    accepted = result.returncode != 0 and 'native head_unique mismatch' in text
    receipt = {'SyntheticMutationOnly': True, 'Status': 'EXPECTED_REJECTION' if accepted else 'FAILED_CHECKER',
               'SimulatorExit': result.returncode, 'RejectionReason': 'native head_unique mismatch',
               'MutatedSourceSHA256': hashlib.sha256(mutant.read_bytes()).hexdigest(),
               'OriginalSourcesModified': False, 'PDSRun': False, 'BoardRun': False}
    (out / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))
    if not accepted:
        raise RuntimeError('Directed checker did not reject the mutation for the expected reason')


if __name__ == '__main__':
    main()
