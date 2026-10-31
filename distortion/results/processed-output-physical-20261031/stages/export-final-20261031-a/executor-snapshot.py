"""Export this candidate's routed functional netlist without rerunning PnR.

Use the exact original source/stage context and an explicit copied input ADF.
The original compiled absolute paths (including rewritten includes) stay bound
and read-only. Actual native stages must be Report Timing, Generate Netlist.
No bitstream generation, download, source edit or timing acceptance is included.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / 'build/processed-output'
BASE = ROOT / 'pds-20261031-a'
ORIGINAL = BASE / 'place_route/processed_output_top_pnr.adf'
BASE_SHA = '97df0e42848650499802b2cf0e4375f420b4c2c98cc55bd9e2dc97fb62a5b980'
PLAN_SHA = '7c8ef42fc811275f8add3dbc929b1309212ddc6882a79e4593230b6a56513c1b'
PDS = Path('D:/pango/PDS_2023.2/bin/pds_shell.exe')
MARKER = 'PROCESSED_FUNCTIONAL_EXPORT_COMPLETE'
STAGES = ['Report Timing', 'Generate Netlist']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def canonical_file(path, parent=PROJECT):
    path = Path(path).absolute()
    require(path == path.resolve() and path.is_relative_to(parent) and path.is_file(),
            'input must be a canonical existing task file: ' + str(path))
    return path


def check_inputs(watched):
    return [str(path) for path, digest in watched.items()
            if not path.is_file() or sha(path) != digest]


def bind_inputs(source):
    require(sha(ORIGINAL) == BASE_SHA, 'original routed baseline changed')
    require(sha(BASE / 'plan.json') == PLAN_SHA, 'original frozen plan changed')
    plan = json.loads((BASE / 'plan.json').read_text(encoding='utf-8'))
    result = json.loads((BASE / 'execution-result.json').read_text(encoding='utf-8'))
    require(result.get('NativeExitCode') == 0 and result.get('ExecutionCompletedWithoutError') is True
            and result.get('PlanSHA256') == PLAN_SHA, 'baseline native build did not complete')
    require(plan.get('Target') == 'processed_output_top' and plan.get('RepoAlias') == 'P:/',
            'unexpected original candidate or alias')
    watched = {canonical_file(PROJECT / name): digest for name, digest in plan['InputSHA256'].items()}
    require(len(watched) == 111 and len(plan['CompiledInputs']) == 107, 'source closure differs')
    for row in plan['CompiledInputs']:
        watched[canonical_file(BASE / 'compiled' / row['Source'])] = row['CompiledSHA256']
    require(sha(BASE / 'timing.tcl') == plan['Tcl']['SHA256'], 'original Tcl changed')
    require(sha(PDS) == plan['PDS']['ExecutableSHA256'], 'PDS executable changed')
    for path in (ORIGINAL, BASE / 'plan.json', BASE / 'execution-result.json',
                 BASE / 'timing.tcl', Path(__file__).resolve(), source, PDS):
        watched[path] = sha(path)
    if source != ORIGINAL:
        require(source.name == 'input.adf', 'derived ADF must be an isolated physical stage input.adf')
        receipt_path = canonical_file(source.parent / 'result.json', ROOT)
        receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
        require(receipt.get('Schema') == 'processed-output-isolated-physical-v1'
                and receipt.get('ExecutionPassed') is True
                and receipt.get('BaselineADFSHA256') == BASE_SHA
                and receipt.get('ResultADFSHA256') == sha(source),
                'derived ADF lacks a completed matching physical stage receipt')
        watched[receipt_path] = sha(receipt_path)
    require(not check_inputs(watched), 'bound source or compiled inputs changed')
    return plan, watched


def render_tcl(original, original_alias, work_alias):
    suffix = ('if {[file exists {' + original_alias + '/place_route/processed_output_top_pnr.adf}]} {\n'
              '    file copy {' + original_alias + '/place_route/processed_output_top_pnr.adf} {'
              + original_alias + '/pre-sta-final.adf}\n}\n'
              'report_timing -force_to_run -delay_type min_max -max_path 20\n')
    require(original.endswith(suffix) and original.count(suffix) == 1,
            'original diagnostic stage suffix differs')
    prefix = original[:-len(suffix)]
    require(prefix.endswith('pnr -optimize_multi_corner_timing -fix_hold_violation\n'),
            'original placement context differs')
    return (prefix + 'report_timing -force_to_run -input_db_file {' + work_alias
            + '/input.adf} -delay_type min_max -max_path 5\n'
            'if {[info script] ne {}} {\n'
            '    gen_netlist -force_to_run -input_db_file {' + work_alias + '/input.adf} -func_sim_only\n'
            '    puts {' + MARKER + '}\n    flush stdout\n}\n')


def stop_owned(process):
    if process is not None and process.poll() is None:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           capture_output=True, timeout=20,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        else:
            process.kill()
        process.wait(timeout=15)


def execute(source, work, maximum_seconds):
    source = canonical_file(source, ROOT)
    require(source.suffix == '.adf', 'source must be a routed ADF')
    work = Path(work).absolute()
    require(work == work.resolve() and work.parent == ROOT and not work.exists()
            and re.fullmatch(r'[A-Za-z0-9_-]+', work.name), 'export work must be a fresh direct task child')
    require(30 <= maximum_seconds <= 1800, 'invalid execution deadline')
    original_plan, watched = bind_inputs(source)
    alias, repo = Path('P:/'), PROJECT.parent
    made_alias, process = False, None
    receipt = None
    try:
        if not alias.exists():
            subprocess.run(['subst', 'P:', str(repo)], check=True, capture_output=True, timeout=15)
            made_alias = True
        require(alias.samefile(repo), 'P: belongs to a different directory')
        for row in original_plan['CompiledInputs']:
            require(Path(row['CompiledPath']).samefile(BASE / 'compiled' / row['Source']),
                    'aliased compiled path does not identify the bound file')
        work.mkdir()
        work_alias = 'P:/distortion/build/processed-output/' + work.name
        clone = work / 'input.adf'
        shutil.copyfile(source, clone)
        require(sha(clone) == watched[source], 'ADF copy differs')
        tcl = render_tcl((BASE / 'timing.tcl').read_text(encoding='ascii'),
                         original_plan['AliasWorkDirectory'], work_alias)
        tcl_path = work / 'export.tcl'
        tcl_path.write_text(tcl, encoding='ascii', newline='\n')
        snapshot = work / 'executor-snapshot.py'
        shutil.copyfile(Path(__file__).resolve(), snapshot)
        watched.update({path: sha(path) for path in (clone, tcl_path, snapshot)})
        command = [str(PDS), '-file', work_alias + '/export.tcl', '-work_dir', work_alias,
                   '-project_name', 'processed_output_top']
        receipt = {'Schema': 'processed-output-functional-export-v1', 'StartedUTC': utc(),
                   'SourceADF': str(source), 'SourceADFSHA256': sha(source),
                   'BaselineADFSHA256': BASE_SHA, 'OriginalPlanSHA256': PLAN_SHA,
                   'Command': command, 'MaximumSeconds': maximum_seconds,
                   'InputSHA256': {str(path): digest for path, digest in watched.items()},
                   'OriginalSourceInputs': 111, 'OriginalCompiledInputs': 107,
                   'CompiledCopiesReferencedReadOnly': True, 'ExpectedActualStages': STAGES,
                   'HardwareAccessed': False, 'BitstreamRequested': False,
                   'TimingAccepted': False, 'HardwareReleaseAllowed': False,
                   'ExecutionPassed': False, 'EDAExecuted': False, 'TimedOut': False,
                   'StoppedForUnexpectedStage': False}
        write_json(work / 'export-plan.json', receipt)
        watched[work / 'export-plan.json'] = sha(work / 'export-plan.json')
        require(not check_inputs(watched), 'input changed before native execution')
        started = time.monotonic()
        try:
            with (work / 'stdout.log').open('xb') as out, (work / 'stderr.log').open('xb') as err:
                process = subprocess.Popen(command, cwd=work_alias, stdout=out, stderr=err,
                                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                receipt.update(EDAExecuted=True, OwnedPID=process.pid)
                while process.poll() is None:
                    remaining = maximum_seconds - (time.monotonic() - started)
                    if remaining <= 0:
                        receipt['TimedOut'] = True
                        stop_owned(process)
                        break
                    try:
                        process.wait(timeout=min(5, remaining))
                    except subprocess.TimeoutExpired:
                        pass
                    log = (work / 'stdout.log').read_text(encoding='utf-8', errors='replace')
                    stages = re.findall(r'^Process "([^"]+)" started\.', log, re.M)
                    if stages != STAGES[:len(stages)]:
                        receipt['StoppedForUnexpectedStage'] = True
                        stop_owned(process)
                        break
                receipt['ExitCode'] = process.poll()
        except BaseException as error:
            receipt['Error'] = type(error).__name__ + ': ' + str(error)
            stop_owned(process)
        log = (work / 'stdout.log').read_text(encoding='utf-8', errors='replace')
        diagnostics = []
        for logfile in work.rglob('*.log'):
            diagnostics.extend(str(logfile.relative_to(work)) + ': ' + line.strip() for line in re.findall(
                r'(?m)^\s*(?:E:|F:|ERROR:|FATAL:).*$', logfile.read_text(encoding='utf-8', errors='replace')))
        stages = re.findall(r'^Process "([^"]+)" started\.', log, re.M)
        netlist = work / 'generate_netlist/processed_output_top_sim.v'
        valid_netlist = netlist.is_file() and bool(re.search(r'(?m)^module processed_output_top\s*$',
                                                                           netlist.read_text(encoding='utf-8')))
        receipt.update(FinishedUTC=utc(), ElapsedSeconds=round(time.monotonic() - started, 3),
                       InputDrift=check_inputs(watched), Diagnostics=diagnostics, ActualStages=stages,
                       CompletionMarker=MARKER in log, AliasStable=alias.exists() and alias.samefile(repo),
                       InputADFUnchanged=sha(clone) == watched[source],
                       NativeNetlistPresent=valid_netlist,
                       Netlist={'Path': str(netlist), 'SHA256': sha(netlist), 'Bytes': netlist.stat().st_size}
                       if netlist.is_file() else None,
                       Artifacts={str(path.relative_to(work)): sha(path) for path in work.rglob('*')
                                  if path.is_file() and path.suffix in ('.tcl', '.log', '.rtr', '.v', '.gnr')})
        receipt['ExecutionPassed'] = (receipt.get('ExitCode') == 0 and not receipt.get('Error')
            and not receipt['TimedOut'] and not receipt['StoppedForUnexpectedStage']
            and not receipt['InputDrift'] and not diagnostics and stages == STAGES
            and receipt['CompletionMarker'] and receipt['AliasStable']
            and receipt['InputADFUnchanged'] and valid_netlist)
        write_json(work / 'export-result.json', receipt)
        print(json.dumps({key: receipt[key] for key in ('ExecutionPassed', 'ElapsedSeconds', 'ActualStages',
                         'InputDrift', 'Diagnostics', 'Netlist')}), flush=True)
        return 0 if receipt['ExecutionPassed'] else 1
    finally:
        stop_owned(process)
        if made_alias and alias.exists() and alias.samefile(repo):
            subprocess.run(['subst', 'P:', '/D'], check=True, capture_output=True, timeout=15)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument('--name')
    target.add_argument('--work-dir', type=Path)
    parser.add_argument('--source-adf', type=Path, default=ORIGINAL)
    parser.add_argument('--maximum-seconds', type=int, default=600)
    args = parser.parse_args()
    return execute(args.source_adf, args.work_dir if args.work_dir is not None else ROOT / args.name,
                   args.maximum_seconds)


if __name__ == '__main__':
    raise SystemExit(main())
