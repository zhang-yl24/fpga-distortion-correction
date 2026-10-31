"""Run an isolated, bounded physical inspection/repair of this output candidate.

The original routed baseline and frozen inputs are checked before/after. Each
stage owns a fresh ADF copy, Tcl, logs and receipt. No bitstream or hardware flow.
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
BASE = PROJECT / 'build/processed-output/pds-20261031-a'
ORIGINAL = BASE / 'place_route/processed_output_top_pnr.adf'
BASE_SHA = '97df0e42848650499802b2cf0e4375f420b4c2c98cc55bd9e2dc97fb62a5b980'
PDS = Path('D:/pango/PDS_2023.2/bin/pds_shell.exe')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def write_json(path, data):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--body', required=True, type=Path)
    parser.add_argument('--source-adf', type=Path, default=ORIGINAL)
    parser.add_argument('--maximum-seconds', type=int, default=600)
    args = parser.parse_args()
    require(re.fullmatch(r'[A-Za-z0-9_-]+', args.name), 'invalid stage name')
    require(30 <= args.maximum_seconds <= 1800, 'invalid deadline')
    source = args.source_adf.resolve()
    require(source.is_relative_to(PROJECT / 'build/processed-output') and source.suffix == '.adf',
            'source must belong to isolated processed-output build')
    body_path = args.body.resolve()
    require(body_path.is_relative_to(PROJECT) and body_path.is_file(), 'body must be a project file')
    body = body_path.read_text(encoding='ascii')
    require(not re.search(r'\b(?:exec|download|program|bitgen|gen_bitstream|compile|synthesize|pnr)\b', body),
            'not an isolated physical inspection/repair body')
    require('mpnr ' not in body and 'source ' not in body, 'stage owns input loading; inline reviewed scope')
    work = PROJECT / 'build/processed-output' / args.name
    require(work.resolve() == work and not work.exists(), 'stage directory must be fresh and canonical')
    require(sha(ORIGINAL) == BASE_SHA, 'original baseline changed')
    plan = json.loads((BASE / 'plan.json').read_text(encoding='utf-8'))
    watched = {PROJECT / name: digest for name, digest in plan['InputSHA256'].items()}
    for row in plan['CompiledInputs']:
        watched[BASE / 'compiled' / row['Source']] = row['CompiledSHA256']
    for path in (ORIGINAL, source, body_path, Path(__file__).resolve(), PDS, BASE / 'plan.json'):
        watched[path] = sha(path)
    for path, digest in watched.items():
        require(sha(path) == digest, 'bound input changed: ' + str(path))
    repo = PROJECT.parent
    alias = Path('P:/')
    made_alias = False
    process = None
    try:
        if not alias.exists():
            subprocess.run(['subst', 'P:', str(repo)], check=True, capture_output=True)
            made_alias = True
        require(alias.samefile(repo), 'P: belongs to a different directory')
        work.mkdir()
        clone = work / 'input.adf'
        shutil.copyfile(source, clone)
        (work / 'dummy.v').write_text('module physical_dummy(input a, output y); assign y=a; endmodule\n', encoding='ascii')
        aw = 'P:/distortion/build/processed-output/' + args.name
        body = body.replace('@WORK@', aw)
        tcl = ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
               'add_design {' + aw + '/dummy.v}\n'
               'if {[info script] ne {}} {\n'
               '    mpnr -input {' + aw + '/input.adf}\n' + body + '\n'
               '    puts {PROCESSED_PHYSICAL_STAGE_COMPLETE}\n    flush stdout\n}\n')
        tcl_path = work / 'stage.tcl'
        tcl_path.write_text(tcl, encoding='ascii')
        for path in (tcl_path, work / 'dummy.v'):
            watched[path] = sha(path)
        shutil.copyfile(Path(__file__).resolve(), work / 'executor-snapshot.py')
        command = [str(PDS), '-file', aw + '/stage.tcl', '-work_dir', aw, '-project_name', 'processed_output_top']
        receipt = {'Schema': 'processed-output-isolated-physical-v1',
                   'StartedUTC': datetime.now(timezone.utc).isoformat(),
                   'SourceADF': str(source), 'SourceADFSHA256': sha(source),
                   'BaselineADFSHA256': BASE_SHA, 'Command': command,
                   'InputSHA256': {str(p): h for p, h in watched.items()},
                   'TclSHA256': sha(tcl_path), 'Body': body,
                   'MaximumSeconds': args.maximum_seconds,
                   'HardwareAccessed': False, 'BitstreamRequested': False,
                   'TimingAccepted': False}
        write_json(work / 'start.json', receipt)
        started = time.monotonic()
        timed_out = False
        with (work / 'stdout.log').open('wb') as stdout, (work / 'stderr.log').open('wb') as stderr:
            process = subprocess.Popen(command, cwd=aw, stdout=stdout, stderr=stderr,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            try:
                code = process.wait(timeout=args.maximum_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
                else:
                    process.kill()
                code = process.wait(timeout=30)
        log = (work / 'stdout.log').read_text(encoding='utf-8', errors='replace')
        drift = [str(p) for p, h in watched.items() if not p.is_file() or sha(p) != h]
        diagnostics = []
        for diagnostic_file in work.rglob('*.log'):
            diagnostic_text = diagnostic_file.read_text(encoding='utf-8', errors='replace')
            diagnostics.extend(str(diagnostic_file.relative_to(work)) + ': ' + line.strip()
                               for line in re.findall(r'(?m)^\s*(?:E:|F:|ERROR:|FATAL:).*$', diagnostic_text))
        receipt.update({'FinishedUTC': datetime.now(timezone.utc).isoformat(),
                        'ElapsedSeconds': round(time.monotonic() - started, 3),
                        'ExitCode': code, 'TimedOut': timed_out, 'InputDrift': drift,
                        'Diagnostics': diagnostics, 'CompletionMarker': 'PROCESSED_PHYSICAL_STAGE_COMPLETE' in log,
                        'ResultADFSHA256': sha(clone),
                        'PreSTAEqualsResultADF': (sha(work / 'pre-sta.adf') == sha(clone)
                                                 if (work / 'pre-sta.adf').is_file() else None),
                        'Artifacts': {str(p.relative_to(work)): sha(p) for p in work.rglob('*')
                                      if p.is_file() and p.suffix in ('.tcl', '.log', '.rtr', '.v', '.fdc', '.prr', '.prt')}})
        receipt['ExecutionPassed'] = code == 0 and not timed_out and not drift and not diagnostics and receipt['CompletionMarker']
        write_json(work / 'result.json', receipt)
        print(json.dumps({k: receipt[k] for k in ('ExecutionPassed', 'ElapsedSeconds', 'ExitCode', 'InputDrift', 'Diagnostics', 'ResultADFSHA256')}), flush=True)
        return 0 if receipt['ExecutionPassed'] else 1
    finally:
        if process is not None and process.poll() is None:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
        if made_alias and alias.exists() and alias.samefile(repo):
            subprocess.run(['subst', 'P:', '/D'], check=True, capture_output=True)


if __name__ == '__main__':
    raise SystemExit(main())
