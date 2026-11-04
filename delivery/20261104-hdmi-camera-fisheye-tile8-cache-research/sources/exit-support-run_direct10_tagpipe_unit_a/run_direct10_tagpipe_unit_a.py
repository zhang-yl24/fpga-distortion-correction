"""Check the unchanged tag-pipelined cache at INDEX10 with its full oracle."""
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
import run_directfill_tagpipe_cache_sim as oracle


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    work = HERE / 'direct10-tagpipe-unit-a'
    if work.exists():
        raise ValueError('fresh independent INDEX10 unit required')
    source = ROOT / 'distortion/rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill_tagpipe.v'
    bench_original = ROOT / 'distortion/tests/tb_directfill_tagpipe_cache.sv'
    if sha(source) != 'cc47c00bf2458491c1def0c5be3a2f8d209269a57dc2259d46ce7ce1054486a1' or sha(bench_original) != 'b1c1888674f13f64ca988811a67ed6a54faa90d8946e94aa223c063720decaf8':
        raise ValueError('frozen tagpipe source/oracle differs')
    text = bench_original.read_text()
    start = text.index('module tb_directfill_tagpipe_cache;')
    text = text[:start] + '''module tb_directfill_tagpipe_cache;
    wire odd_done,i10_done;
    directfill_tagpipe_cache_case odd_case(odd_done);
    directfill_tagpipe_cache_case #(.WIDTH(1920),.HEIGHT(1080),.INDEX_BITS(10)) i10_case(i10_done);
    initial begin wait(odd_done&&i10_done);$display("PASS TAGPIPE complete independent cache regression; INDEX10 plus odd-width case, no PDS/hardware");$finish;end
endmodule
'''
    work.mkdir()
    bench = work / 'tb_direct10_tagpipe_unit_a.sv'
    bench.write_text(text, encoding='utf-8')
    watched = {str(path): sha(path) for path in (source, bench_original, bench, Path(__file__),
               Path(oracle.__file__), ROOT / 'distortion/tools/run_fill8_rowpipe_cache_sim.py',
               ROOT / 'distortion/tools/simulation_tools.py')}
    result = {'Schema': 'tile8-direct10-tagpipe-unit-research-v1', 'Passed': False,
              'StartedUTC': datetime.now(timezone.utc).isoformat(), 'InputSHA256': watched,
              'CacheSourceUnchanged': True, 'CacheIndexBits': 10, 'CapacityBytes': 262144,
              'OriginalCaseAssertionsUnchanged': True, 'NativeEDAExecuted': False, 'HardwareAccessed': False}
    started = time.monotonic()
    try:
        binary = resolve_vivado_bin(ROOT)
        deadline = started + 300
        run_tool(binary, 'xvlog.bat', ['--sv', str(source), str(bench)], work, deadline, 'compile')
        run_tool(binary, 'xelab.bat', ['tb_directfill_tagpipe_cache', '-s', 'direct10_unit_a'], work, deadline, 'elaborate')
        run_tool(binary, 'xsim.bat', ['direct10_unit_a', '-runall', '-log', 'simulation.log'], work, deadline, 'simulate')
        # Run the original validator's exact code over the explicitly selected cases.
        original = Path(oracle.__file__).read_text()
        clause = 'CASES = ((639, 480, 3), (1920, 1080, 7), (1920, 1080, 8), (1920, 1080, 9))'
        if original.count(clause) != 1:
            raise ValueError('original finite case inventory differs')
        scoped = original.replace(clause, 'CASES = ((639, 480, 3), (1920, 1080, 10))')
        namespace = {'__file__': oracle.__file__, '__name__': 'direct10_frozen_oracle'}
        exec(compile(scoped, oracle.__file__, 'exec'), namespace)
        result['Cases'] = namespace['validate'](work)
        result['Passed'] = True
    except Exception as error:
        result['Error'] = type(error).__name__ + ': ' + str(error)
    result['InputDrift'] = [path for path, digest in watched.items() if sha(path) != digest]
    result['Passed'] = result['Passed'] and not result['InputDrift']
    result['ElapsedSeconds'] = time.monotonic() - started
    with (work / 'simulation.json').open('x', encoding='utf-8') as target:
        json.dump(result, target, indent=2); target.write('\n')
    print(json.dumps({key: result.get(key) for key in ('Passed', 'Error', 'InputDrift', 'ElapsedSeconds')}))
    raise SystemExit(0 if result['Passed'] else 1)


if __name__ == '__main__':
    main()
