"""Bounded read-only physical queries of the frozen camera VGA routed ADF.

Only fresh direct children of work/camera-vga-output are used. The loaded ADF
is an independent copy; source, compiled inputs, original report and tools are
bound before/after. No compile, synthesis, full PnR, bitstream or hardware.
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
ROOT = PROJECT / 'work/camera-vga-output'
BASE = ROOT / 'pds-20261031-a'
TARGET = 'camera_vga_output_top'
ORIGINAL = BASE / ('place_route/' + TARGET + '_pnr.adf')
REPORT = BASE / ('report_timing/' + TARGET + '.rtr')
BASE_SHA = '32c8aa75c766425765b7cd20bbe26dbee9f9072a069d43a297de07b3e730be3b'
PLAN_SHA = '6e98cb540916da33ce0fd13760a6a5b8f60e9f27b6c0ceaaeecc6ae1529e1050'
REPORT_SHA = '965b8fd4d3efdfc9d24b5782c24df6668d70b5c9d337fddb647f2bcbcebb97d8'
RESULT_SHA = '2fed2b7a87f5002cd61c066ef364c020b305a919728afa033a06ebf26fd16f31'
PDS = Path('D:/pango/PDS_2023.2/bin/pds_shell.exe')
MARKER = 'CAMERA_PHYSICAL_QUERY_COMPLETE'
SCHEMA = 'camera-vga-isolated-query-v1'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def canonical_file(path, parent=PROJECT):
    path = Path(path).absolute()
    require(path == path.resolve() and path.is_relative_to(parent) and path.is_file(),
            'input must be a canonical existing task file: ' + str(path))
    return path


def fresh_work(path):
    path = Path(path).absolute()
    require(path == path.resolve() and path.parent == ROOT and not path.exists()
            and re.fullmatch(r'[A-Za-z0-9_-]+', path.name),
            'work must be a fresh canonical direct camera scratch child')
    return path


def deadline(value):
    require(type(value) is int and 120 <= value <= 300, 'deadline must be 120..300 seconds')
    return value


def check_inputs(watched):
    return [str(p) for p, digest in watched.items() if not p.is_file() or sha(p) != digest]


def bind_inputs(source=ORIGINAL, extra=()):
    source = canonical_file(source, ROOT)
    require(source == ORIGINAL, 'only the exact original camera ADF is accepted for current read-only stages')
    fixed = {ORIGINAL: BASE_SHA, BASE/'plan.json': PLAN_SHA, REPORT: REPORT_SHA,
             BASE/'execution-result.json': RESULT_SHA}
    require(not check_inputs(fixed), 'frozen camera baseline/plan/report/result changed')
    plan = json.loads((BASE/'plan.json').read_text(encoding='utf-8'))
    result = json.loads((BASE/'execution-result.json').read_text(encoding='utf-8'))
    require(plan.get('Target') == TARGET and plan.get('RepoAlias') == 'direct'
            and plan.get('WorkDirectory') == str(BASE), 'wrong camera baseline context')
    require(result.get('NativeExitCode') == 0 and result.get('ExecutionCompletedWithoutError') is True
            and result.get('SourcesStable') is True and result.get('PlanSHA256') == PLAN_SHA
            and result['DatabaseSnapshotAudit'].get('UnchangedAcrossSTA') is True,
            'camera diagnostic has not completed cleanly')
    require(len(plan['InputSHA256']) == 115 and len(plan['CompiledInputs']) == 109,
            'camera source closure differs')
    watched = {canonical_file(PROJECT/name): digest for name, digest in plan['InputSHA256'].items()}
    for row in plan['CompiledInputs']:
        copied = canonical_file(BASE/'compiled'/row['Source'])
        require(row['CompiledPath'] == copied.as_posix(), 'compiled path binding differs')
        watched[copied] = row['CompiledSHA256']
    watched.update(fixed)
    watched[BASE/'timing.tcl'] = plan['Tcl']['SHA256']
    watched[PDS] = plan['PDS']['ExecutableSHA256']
    for path in (Path(__file__).resolve(), *extra):
        path = canonical_file(path)
        watched[path] = sha(path)
    require(not check_inputs(watched), 'camera source/compiled/tool binding drift')
    return plan, watched


def validate_query_body(body):
    """Recognize complete read-only command lines, never execute arbitrary Tcl."""
    require(body and body.isascii(), 'nonempty ASCII query body required')
    # Balanced, single-level braced arguments keep substitution inert. Object
    # names and regular expressions may contain [] and semicolons inside braces.
    brace = r'\{[^{}\r\n]*\}'
    patterns = [
        r'puts ' + brace,
        r'get_pins -hierarchical -regexp ' + brace,
        r'show -(?:design_net|dev_instance) ' + brace,
        r'\.switch_db -route -input \{@WORK@/input\.adf\} -output \{@WORK@/[A-Za-z0-9_-]+\.txt\}',
        r'dump_net -grid_unit ' + brace + r' -print_site -out_file \{@WORK@/[A-Za-z0-9_-]+\.txt\}',
        r'mpnr_report_timing -force_to_run -delay_type min_max -max_path (?:[1-9][0-9]{0,2}|1000) -nworst [1-8] -report_exception TRUE',
        r'report_path_timing -delay_type min_max -max_path (?:[1-9][0-9]{0,2}|1000) -nworst [1-8] -report_exception TRUE -from ' + brace + r' -to ' + brace,
        r'file copy \{@WORK@/input\.adf\} \{@WORK@/pre-sta\.adf\}',
        r'(?:mpnr_report_timing|manual_route|\.show_wire|show_device|report_region) -help',
    ]
    commands = []
    for line in body.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        require(any(re.fullmatch(p, line) for p in patterns), 'unsupported or mutating query command: ' + line[:100])
        commands.append(line)
    require(commands and len(commands) <= 300, 'query command count out of bounds')
    return commands


def render_query(body, work):
    validate_query_body(body)
    aw = work.as_posix()
    return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
            'add_design {' + aw + '/dummy.v}\n'
            'if {[info script] ne {}} {\n'
            '    mpnr -input {' + aw + '/input.adf}\n' + body.replace('@WORK@', aw) + '\n'
            '    puts {' + MARKER + '}\n    flush stdout\n}\n')


def stop_owned(process):
    if process is not None and process.poll() is None:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True,
                           timeout=20, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        else:
            process.kill()
        process.wait(timeout=15)


def run_stage(*, work, source, watched, tcl, maximum, marker, schema, expected_stages,
              executor, dummy=False, prepare_only=False, require_netlist=False):
    work, maximum = fresh_work(work), deadline(maximum)
    require(not check_inputs(watched), 'input drift before preparation')
    work.mkdir()
    clone = work/'input.adf'
    shutil.copyfile(source, clone)
    require(sha(clone) == watched[source], 'ADF copy differs')
    script = work/'stage.tcl'
    script.write_text(tcl, encoding='ascii', newline='\n')
    if dummy:
        (work/'dummy.v').write_text('module physical_dummy(input a, output y); assign y=a; endmodule\n', encoding='ascii')
    snapshot = work/'executor-snapshot.py'
    shutil.copyfile(executor, snapshot)
    for path in (clone, script, snapshot, *([work/'dummy.v'] if dummy else [])):
        watched[path] = sha(path)
    command = [str(PDS), '-file', script.as_posix(), '-work_dir', work.as_posix(), '-project_name', TARGET]
    receipt = {'Schema': schema, 'PreparedUTC': utc(), 'SourceADF': str(source),
               'SourceADFSHA256': watched[source], 'BaselineADFSHA256': BASE_SHA,
               'OriginalPlanSHA256': PLAN_SHA, 'OriginalReportSHA256': REPORT_SHA,
               'Command': command, 'MaximumSeconds': maximum, 'Body': tcl,
               'ExpectedActualStages': expected_stages,
               'InputSHA256': {str(p): h for p, h in watched.items()},
               'HardwareAccessed': False, 'BitstreamRequested': False, 'TimingAccepted': False,
               'HardwareReleaseAllowed': False, 'ExecutionPassed': False, 'EDAExecuted': False,
               'TimedOut': False, 'StoppedForUnexpectedStage': False}
    write_json(work/'stage-plan.json', receipt)
    watched[work/'stage-plan.json'] = sha(work/'stage-plan.json')
    if prepare_only:
        return {'Prepared': True, 'EDAExecuted': False, 'WorkDirectory': str(work), 'Command': command}
    require(os.name == 'nt', 'PDS execution is Windows-only')
    require(not check_inputs(watched), 'input drift before native execution')
    started, process = time.monotonic(), None
    receipt['StartedUTC'] = utc()
    try:
        with (work/'stdout.log').open('xb') as out, (work/'stderr.log').open('xb') as err:
            process = subprocess.Popen(command, cwd=str(work), stdout=out, stderr=err, shell=False,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            receipt.update(EDAExecuted=True, OwnedPID=process.pid)
            while process.poll() is None:
                remaining = maximum - (time.monotonic()-started)
                if remaining <= 0:
                    receipt['TimedOut'] = True
                    stop_owned(process)
                    break
                try:
                    process.wait(timeout=min(2, remaining))
                except subprocess.TimeoutExpired:
                    pass
                log = (work/'stdout.log').read_text(encoding='utf-8', errors='replace')
                stages = re.findall(r'^Process "([^"]+)" started\.', log, re.M)
                if stages != expected_stages[:len(stages)]:
                    receipt['StoppedForUnexpectedStage'] = True
                    stop_owned(process)
                    break
            receipt['ExitCode'] = process.poll()
    except BaseException as error:
        receipt['Error'] = type(error).__name__ + ': ' + str(error)
    finally:
        stop_owned(process)
    log = (work/'stdout.log').read_text(encoding='utf-8', errors='replace') if (work/'stdout.log').exists() else ''
    diagnostics = []
    for p in work.rglob('*.log'):
        diagnostics.extend(str(p.relative_to(work))+': '+line.strip() for line in re.findall(
            r'(?m)^\s*(?:E:|F:|ERROR:|FATAL:).*$', p.read_text(encoding='utf-8', errors='replace')))
    stages = re.findall(r'^Process "([^"]+)" started\.', log, re.M)
    netlist = work/('generate_netlist/'+TARGET+'_sim.v')
    nettext = netlist.read_text(encoding='utf-8', errors='replace') if netlist.is_file() else ''
    # PDS represents placement as inline /* CLM... */ comments on V_* cells,
    # not a literal FFloc attribute. Retain the native location information.
    netvalid = (bool(re.search(r'(?m)^module '+TARGET+r'\s*$', nettext))
                and bool(re.search(r'V_\w+\s*/\*\s*(?:CLMA|CLMS|IOLHR)_\d+_\d+\s*\*/', nettext)))
    receipt.update(FinishedUTC=utc(), ElapsedSeconds=round(time.monotonic()-started, 3),
        InputDrift=check_inputs(watched), Diagnostics=diagnostics, ActualStages=stages,
        CompletionMarker=marker in log, InputADFUnchanged=sha(clone)==watched[source],
        ResultADFSHA256=sha(clone), NativeNetlistWithFFloc=netvalid if require_netlist else None,
        Netlist={'Path': str(netlist), 'SHA256': sha(netlist), 'Bytes': netlist.stat().st_size} if netlist.is_file() else None,
        Artifacts={p.relative_to(work).as_posix(): sha(p) for p in work.rglob('*') if p.is_file()
                   and p.suffix in ('.tcl','.log','.rtr','.v','.gnr','.txt','.fdc')})
    receipt['ExecutionPassed'] = (receipt.get('ExitCode')==0 and not receipt.get('Error')
        and not receipt['TimedOut'] and not receipt['StoppedForUnexpectedStage'] and not receipt['InputDrift']
        and not diagnostics and stages==expected_stages and receipt['CompletionMarker']
        and receipt['InputADFUnchanged'] and (not require_netlist or netvalid))
    write_json(work/'result.json', receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--body', type=Path, required=True)
    parser.add_argument('--maximum-seconds', type=int, default=240)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--validate-only', action='store_true')
    mode.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args(argv)
    work, maximum = fresh_work(ROOT/args.name), deadline(args.maximum_seconds)
    bodypath = canonical_file(args.body, ROOT)
    body = bodypath.read_text(encoding='ascii')
    validate_query_body(body)
    _, watched = bind_inputs(extra=(bodypath,))
    tcl = render_query(body, work)
    if args.validate_only:
        print(json.dumps({'Validated': True, 'EDAExecuted': False, 'WorkDirectory': str(work),
                          'BaselineADFSHA256': BASE_SHA, 'MaximumSeconds': maximum}))
        return 0
    result = run_stage(work=work, source=ORIGINAL, watched=watched, tcl=tcl, maximum=maximum,
        marker=MARKER, schema=SCHEMA, expected_stages=[], executor=Path(__file__).resolve(),
        dummy=True, prepare_only=args.prepare_only)
    print(json.dumps({k: result[k] for k in ('Prepared','ExecutionPassed','ElapsedSeconds','ExitCode',
                     'InputDrift','Diagnostics','WorkDirectory') if k in result}), flush=True)
    return 0 if args.prepare_only or result['ExecutionPassed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
