"""Simulate the frozen HDMI cache and packed candidate against one oracle."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import time


ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT.parent / "20261103-hdmi1080-demo-source"
BASELINE = FROZEN / "native/source/rtl/experimental/ddr_compact_neighbour_cache_scatter4.v"
CANDIDATE = ROOT / "rtl/ddr_compact_neighbour_cache_scatter4.v"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args):
    work = args.workdir.resolve()
    work.mkdir(parents=True, exist_ok=False)
    sources = [BASELINE, CANDIDATE, ROOT / "tests/tb_cache_directed.sv"]
    if (ROOT / "tests/tb_cache_stream.sv").exists():
        sources.append(ROOT / "tests/tb_cache_stream.sv")
    hashes = {str(p.relative_to(ROOT.parent)): sha(p) for p in sources}
    result = dict(passed=False, hardware_accessed=False, pds_accessed=False,
                  source_sha256=hashes, cases=[])
    try:
        for packed, rtl in [(0, BASELINE), (1, CANDIDATE)]:
            for bench in sources[2:]:
                top = bench.stem
                stage = work / (('candidate' if packed else 'baseline') + '-' + top)
                stage.mkdir()
                commands = [
                    ['xvlog.bat', '--sv', *(['-d', 'PACKED32'] if packed else []), str(rtl), str(bench)],
                    ['xelab.bat', top, '-s', 'cache_test'],
                    ['xsim.bat', 'cache_test', '-runall'],
                ]
                case = dict(candidate=bool(packed), bench=top, commands=[], passed=False)
                result['cases'].append(case)
                for command in commands:
                    argv = [str(args.vivado_bin / command[0]), *command[1:]]
                    started = time.monotonic()
                    process = subprocess.run(argv, cwd=stage, capture_output=True,
                                             text=True, errors='replace', timeout=300)
                    output = process.stdout + process.stderr
                    log = stage / (command[0] + '.log')
                    log.write_text(output, encoding='utf-8')
                    case['commands'].append(dict(argv=argv, returncode=process.returncode,
                                                  seconds=time.monotonic()-started,
                                                  log_sha256=sha(log)))
                    if process.returncode or re.search(r'(?im)^\s*(?:fatal|error)(?:\s|:|\[)', output):
                        raise RuntimeError(f'{stage.name}/{command[0]} failed: {output[-4000:]}')
                if 'PASS SCATTER4 independent directed regression:' not in output and 'PASS CACHE STREAM' not in output:
                    raise RuntimeError(f'{stage.name}: required completion marker absent')
                case['pass_lines'] = [line for line in output.splitlines() if line.startswith(('PASS', 'CACHE_METRICS', 'SCATTER4 coverage'))]
                metric = re.search(r'CACHE_METRICS cycles=(\d+) queries=(\d+) bursts=(\d+) scatter=(\d+) hits=(\d+) misses=(\d+)', output)
                if metric:
                    case['metrics'] = dict(zip(('cycles','queries','bursts','scatter','hits','misses'),map(int,metric.groups())))
                case['passed'] = True
                print(stage.name, 'PASS', flush=True)
        if hashes != {str(p.relative_to(ROOT.parent)): sha(p) for p in sources}:
            raise RuntimeError('Source changed during simulation')
        result['passed'] = True
    except Exception as exc:
        result['error'] = str(exc)
        raise
    finally:
        (work / 'cache-results.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--vivado-bin', type=Path, default=Path('D:/Vicado/Vivado/2017.4/bin'))
    print(json.dumps(run(parser.parse_args()), indent=2))
