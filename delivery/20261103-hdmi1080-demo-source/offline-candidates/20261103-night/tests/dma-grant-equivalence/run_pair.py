"""Run the preserved real descriptor2 bench twice; no hardware or EDA flow."""
from pathlib import Path
import argparse
import csv
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
CSV_FILES = ('queue_events.csv', 'queue_writes.csv', 'queue_descriptors.csv', 'queue_aw.csv')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    manifest = json.loads((ROOT / 'MANIFEST.json').read_text())
    for row in manifest['files']:
        path = ROOT / row['path']
        assert path.is_file() and path.stat().st_size == row['bytes'], row['path']
        assert digest(path) == row['sha256'], row['path']
    binding = json.loads((ROOT / 'SOURCE_BINDING.json').read_text())
    before = (ROOT / 'baseline/hdmi1080_input_dma.v').read_bytes()
    after = (ROOT / 'candidate/hdmi1080_input_dma.v').read_bytes()
    old = b'if(grant_valid && grant_ready)begin'
    new = b'if(grant_valid)begin'
    assert before.count(old) == 1 and before.replace(old, new) == after
    assert digest(ROOT / 'baseline/hdmi1080_input_dma.v') == binding['baseline_dma_sha256']
    assert digest(ROOT / 'candidate/hdmi1080_input_dma.v') == binding['candidate_dma_sha256']
    return len(manifest['files'])


def stop_tree(process):
    """Terminate only the process tree created by this command; never delete files."""
    if process.poll() is not None:
        return
    if os.name == 'nt':
        try:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=5, creationflags=subprocess.CREATE_NO_WINDOW)
        except subprocess.TimeoutExpired:
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=2)
            return
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    process.wait(timeout=3)


def command(argv, directory, name):
    started = time.monotonic()
    options = {'start_new_session': True} if os.name != 'nt' else {
        'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
    with (directory / (name + '.log')).open('w', encoding='utf-8', newline='\n') as log:
        process = subprocess.Popen(argv, cwd=directory, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT, **options)
        try:
            rc = process.wait(timeout=30)
        except BaseException:
            stop_tree(process)
            raise
    assert rc == 0, name + ' failed: see ' + str(directory / (name + '.log'))
    return {'argv': argv, 'returncode': rc, 'seconds': round(time.monotonic() - started, 3),
            'timeout_seconds': 30}


def check_trace(path):
    data = path.read_bytes()
    rows = list(csv.DictReader(io.StringIO(data.decode('ascii'))))
    assert rows and len(rows) % 2 == 0
    assert len(rows[0]) == 36 and all(None not in row and None not in row.values() for row in rows)
    for i in range(0, len(rows), 2):
        pre, post = rows[i:i + 2]
        assert pre['sample'] == 'pre' and post['sample'] == 'post'
        assert int(pre['cycle']) == int(post['cycle']) == i // 2 + 1
        assert int(post['time_ps']) == int(pre['time_ps']) + 1
    return {'rows': len(rows), 'sys_edges': len(rows) // 2,
            'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'columns': list(rows[0])}


def ps_command(directory, name, executable, arguments):
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    path = directory / (name + '.ps1')
    path.write_text('& ' + quote(executable) + ' ' + ' '.join(map(quote, arguments)) +
                    '\nexit $LASTEXITCODE\n', encoding='utf-8')
    return command(['powershell.exe', '-NoProfile', '-NonInteractive', '-File', str(path)], directory, name)


def run_variant(name, out, executables, oracle, backend):
    directory = out / name
    directory.mkdir()
    for path in sorted((ROOT / 'unit/vectors').iterdir()):
        if path.is_file():
            shutil.copyfile(path, directory / path.name)
    sources = [str(ROOT / 'deps/video_async_fifo.v'), str(ROOT / 'deps/hdmi1080_capture_cdc.v'),
               str(ROOT / name / 'hdmi1080_input_dma.v'), str(ROOT / 'unit/tb_dma_descriptor2.sv'),
               str(ROOT / 'unit/dma_public_trace.sv')]
    if backend == 'xsim':
        stages = [ps_command(directory, 'compile', executables['xvlog'], ['--sv', *sources])]
        stages.append(ps_command(directory, 'elaborate', executables['xelab'],
                                  ['tb_dma_descriptor2', 'dma_public_trace', '-s', 'dma_pair', '-mt', 'off']))
        stages.append(ps_command(directory, 'simulate', executables['xsim'],
                                  ['dma_pair', '-runall', '-log', 'simulation.log']))
    else:
        executable = directory / 'unit.vvp'
        compile_argv = [executables['iverilog'], '-g2012', '-s', 'tb_dma_descriptor2',
                        '-s', 'dma_public_trace', '-o', str(executable), *sources]
        stages = [command(compile_argv, directory, 'compile')]
        stages.append(command([executables['vvp'], str(executable)], directory, 'simulate'))
    log = (directory / 'simulate.log').read_text()
    checked = oracle.check(*[(directory / f).read_text() for f in CSV_FILES], log)
    matches = re.findall(r'PAIR_INVARIANTS checked=(\d+) grants=(\d+) reset_edges=(\d+)', log)
    assert len(matches) == 1 and all(int(value) > 0 for value in matches[0]), 'invariant witnesses missing'
    trace = check_trace(directory / 'public_trace.csv')
    return {'status': 'PASS', 'stages': stages, 'original_oracle': checked,
            'invariant_witnesses': dict(zip(('checked', 'grants', 'reset_edges'), map(int, matches[0]))),
            'trace': trace, 'csv_sha256': {f: digest(directory / f) for f in CSV_FILES}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true', help='Verify package and original CPU oracle; no HDL')
    parser.add_argument('--backend', choices=('auto', 'icarus', 'xsim'), default='auto')
    parser.add_argument('--tool-bin', default='E:/Vivado/Vivado/2017.4/bin', help='Official installed XSim bin directory')
    parser.add_argument('--out', help='Fresh result directory inside this package; default results/pair_<timestamp>_<pid>')
    args = parser.parse_args()
    checked = verify()
    spec = importlib.util.spec_from_file_location('descriptor_unit_oracle', ROOT / 'unit/oracle.py')
    oracle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(oracle)
    cpu = oracle.self_test()
    icarus = {name: shutil.which(name) for name in ('iverilog', 'vvp')}
    tool_bin = Path(args.tool_bin)
    xsim = {name: str(tool_bin / (name + '.bat')) if (tool_bin / (name + '.bat')).is_file() else None
            for name in ('xvlog', 'xelab', 'xsim')}
    backend = args.backend
    if backend == 'auto':
        backend = 'icarus' if all(icarus.values()) else 'xsim' if os.name == 'nt' and all(xsim.values()) else 'icarus'
    executables = xsim if backend == 'xsim' else icarus
    if args.check_only:
        print(json.dumps({'status': 'CPU_CHECK_PASS_HDL_NOT_RUN', 'verified_files': checked,
                          'original_oracle_self_test': cpu, 'backend': backend, 'tools': executables}))
        return 0
    out = (ROOT / args.out).resolve() if args.out else ROOT / 'results' / (
        'pair_' + time.strftime('%Y%m%d_%H%M%S', time.gmtime()) + '_' + str(os.getpid()))
    assert out != ROOT and out.is_relative_to(ROOT) and not out.exists(), 'Output must be fresh and inside package'
    out.mkdir(parents=True)
    result = {'status': 'RUNNING', 'hardware_release_allowed': False,
              'commercial_EDA_or_hardware_used': False, 'verified_files': checked,
              'original_oracle_self_test': cpu, 'backend': backend, 'tools': executables, 'output': str(out),
              'source_binding': json.loads((ROOT / 'SOURCE_BINDING.json').read_text())}
    rc = 0
    try:
        if not all(executables.values()):
            result['status'] = 'NOT_RUN_MISSING_' + ('XSIM' if backend == 'xsim' else 'ICARUS')
            result['missing_tools'] = [name for name, path in executables.items() if not path]
        else:
            result['variants'] = {}
            for name in ('baseline', 'candidate'):
                result['variants'][name] = run_variant(name, out, executables, oracle, backend)
            comparisons = {}
            for filename in ('public_trace.csv', *CSV_FILES):
                left = (out / 'baseline' / filename).read_bytes()
                right = (out / 'candidate' / filename).read_bytes()
                assert left == right, 'Baseline/candidate byte mismatch: ' + filename
                comparisons[filename] = {'byte_identical': True, 'bytes': len(left),
                                         'sha256': hashlib.sha256(left).hexdigest()}
            result.update(status='PASS_PAIRED_HDL_AND_ORIGINAL_ORACLES', comparisons=comparisons)
    except BaseException as error:
        result.update(status='FAIL_OR_INCOMPLETE', error=type(error).__name__ + ': ' + str(error))
        rc = 1
    finally:
        try:
            result['postcheck_verified_files'] = verify()
        except BaseException as error:
            result.update(status='FAIL_OR_INCOMPLETE', postcheck_error=str(error))
            rc = 1
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result))
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
