"""Prepare, gate, execute and verify an offline bitstream from this exact ADF.

Only execute mode runs PDS. It requests fresh STA on a copied final ADF, an
independent runtime comparison, then bit generation from that same copy.
No mode opens a programmer, UART or board. Hardware readiness is separate.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import time

import audit_processed_output_physical as comparison
import run_processed_output_export as export

PROJECT, BUILD, BASE = export.PROJECT, export.ROOT, export.BASE
SELF = Path(__file__).resolve()
TARGET = 'processed_output_top'
FINAL = BUILD / 'physical-final-report-20261031-a'
ADF = FINAL / 'input.adf'
ADF_SHA = '1d19936ede917ea1268a17a11fb3b0b34ff84753abefb062ae26d8a2c7c7550b'
AUDIT = BUILD / 'physical-comparison-20261031-a.json'
AUDIT_SHA = 'a2748a74291c296689845720aa54d9a513bf8520189466e9c4b76caefa1b871d'
ARCHIVE = PROJECT / 'results/processed-output-physical-20261031/manifest.json'
ARCHIVE_SHA = '0957abf4a93067a96d844d34d46fa7744ea214fcb3cba5d8131f7dc8fbf74b28'
PYTHON = PROJECT.parent / '.venv/Scripts/python.exe'
MARKER = 'PROCESSED_OUTPUT_PRE_BIT_AUDIT_PASS ' + ADF_SHA
COMPLETE = 'PROCESSED_OUTPUT_BITSTREAM_COMPLETE'
STAGES = ['Report Timing', 'Generate Bitstream']
REPORT = 'report_timing/' + TARGET + '.rtr'
EXCEPTIONS = 'report_timing/' + TARGET + '_exception.rtr'
BIT = 'generate_bitstream/' + TARGET + '.sbit'
require, sha, write_json = export.require, export.sha, export.write_json


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def utc():
    return datetime.now(timezone.utc).isoformat()


def work_path(value, *, exists=True):
    work = Path(value).absolute()
    require(work.resolve() == work and work.parent == BUILD
            and re.fullmatch(r'bit-[A-Za-z0-9_-]+', work.name),
            'canonical bit-* direct child of processed-output required')
    require(work.is_dir() if exists else not work.exists(), 'work directory existence differs')
    return work


def authority():
    """Re-anchor source identity rather than accepting arbitrary plan hashes."""
    require(sha(ADF) == ADF_SHA and sha(AUDIT) == AUDIT_SHA and sha(ARCHIVE) == ARCHIVE_SHA,
            'fixed final ADF/audit/archive changed')
    original_plan, watched = export.bind_inputs(ADF)
    audited = load(AUDIT)
    require(audited.get('Schema') == 'processed-output-physical-comparison-v1'
            and audited.get('AuditPassed') is True
            and audited.get('AllReportedInternalTimingChecksMet') is True
            and audited.get('AllTenNativeTimingTablesChecked') is True
            and audited.get('NoDataSetupOrHoldFalsePaths') is True
            and audited.get('CandidateSnapshotMatchesADF') is True,
            'complete passing internal native comparison required')
    graph = audited['FunctionalAndFFPlacementComparison']
    require(graph.get('FunctionalGraphIdentical') is True
            and graph.get('AllFFPlacementsIdentical') is True
            and graph.get('PrimitiveCellCount') == 38007 and graph.get('FFCount') == 18600,
            'final functional graph/placement evidence differs')
    require(Path(audited['CandidateADF']['Path']).resolve() == ADF
            and audited['CandidateADF']['SHA256'] == ADF_SHA, 'audit final ADF differs')
    for group in ('InputSHA256', 'ToolsSHA256'):
        for name, digest in audited[group].items():
            path = export.canonical_file(name)
            require(sha(path) == digest, 'bound native audit input changed: ' + name)
            watched[path] = digest
    for path in (SELF, PYTHON, AUDIT, ARCHIVE, Path(comparison.__file__), Path(export.__file__),
                 FINAL / (TARGET + '.rtr'), FINAL / (TARGET + '_exception.rtr')):
        watched[path] = sha(path)
    require(not export.check_inputs(watched), 'authority inputs changed')
    return original_plan, watched


def render_tcl(original, original_alias, alias):
    rendered = export.render_tcl(original, original_alias, alias)
    boundary = 'report_timing -force_to_run -input_db_file '
    require(rendered.count(boundary) == 1, 'single explicit STA context required')
    prefix = rendered[:rendered.index(boundary)]
    return (prefix + boundary + '{' + alias + '/audited-final.adf}'
            ' -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n'
            'if {[info script] ne {}} {\n'
            '    set checked [exec {P:/.venv/Scripts/python.exe} '
            '{P:/distortion/tools/processed_output_bitstream.py} --gate {' + alias + '}]\n'
            '    puts $checked\n'
            '    if {[string first {' + MARKER + '} $checked] < 0} {error {Missing pre-bit gate}}\n'
            '    gen_bit_stream -force_to_run -input_db_file {' + alias + '/audited-final.adf}'
            ' -scbv {High Voltage} -unused_io_status UNUSED\n'
            '    puts {' + COMPLETE + '}\n    flush stdout\n}\n')


def prepare(work):
    work = work_path(work, exists=False)
    original_plan, watched = authority()
    alias = 'P:/distortion/build/processed-output/' + work.name
    tcl = render_tcl((BASE / 'timing.tcl').read_text(encoding='ascii'),
                     original_plan['AliasWorkDirectory'], alias)
    work.mkdir()
    shutil.copyfile(ADF, work / 'audited-final.adf')
    shutil.copyfile(SELF, work / 'tool-snapshot.py')
    (work / 'export.tcl').write_text(tcl, encoding='ascii', newline='\n')
    plan = {'Schema': 'processed-output-offline-bitstream-plan-v1', 'PreparedUTC': utc(),
            'ProjectRoot': str(PROJECT), 'WorkDirectory': str(work), 'Target': TARGET,
            'FinalADFSHA256': ADF_SHA, 'PhysicalAuditSHA256': AUDIT_SHA,
            'Command': [str(export.PDS), '-file', alias + '/export.tcl',
                        '-work_dir', alias, '-project_name', TARGET],
            'ProjectInputSHA256': {str(p): h for p, h in watched.items()},
            'WorkInputSHA256': {name: sha(work / name) for name in
                               ('audited-final.adf', 'tool-snapshot.py', 'export.tcl')},
            'ExpectedActualStages': STAGES, 'MaximumSeconds': 900,
            'PreparedOnly': True, 'EDAExecutedByPreparer': False,
            'HardwareAccessed': False, 'BitstreamRequested': True,
            'HardwareReleaseAllowed': False, 'ExternalIOAccepted': False,
            'CDCPhysicalAccepted': False,
            'Limits': 'Offline diagnostic artifact only; board power and a separate hardware check are required.'}
    require(not export.check_inputs(watched), 'authority changed while preparing')
    write_json(work / 'bitstream-plan.json', plan)
    return plan


def validate(work):
    work = work_path(work)
    plan = load(work / 'bitstream-plan.json')
    original, watched = authority()
    require(plan.get('Schema') == 'processed-output-offline-bitstream-plan-v1'
            and plan.get('WorkDirectory') == str(work) and plan.get('ProjectRoot') == str(PROJECT)
            and plan.get('Target') == TARGET and plan.get('FinalADFSHA256') == ADF_SHA,
            'bitstream plan identity differs')
    require(plan.get('HardwareAccessed') is False and plan.get('HardwareReleaseAllowed') is False,
            'offline plan must not claim board access or release')
    require(plan.get('ProjectInputSHA256') == {str(p): h for p, h in watched.items()},
            'plan is not bound to complete current source/audit closure')
    alias = 'P:/distortion/build/processed-output/' + work.name
    expected = render_tcl((BASE / 'timing.tcl').read_text(encoding='ascii'),
                         original['AliasWorkDirectory'], alias)
    require((work / 'export.tcl').read_bytes() == expected.encode('ascii'), 'Tcl recipe changed')
    require(plan.get('Command') == [str(export.PDS), '-file', alias + '/export.tcl',
                                   '-work_dir', alias, '-project_name', TARGET],
            'command differs from exact offline export')
    require(set(plan['WorkInputSHA256']) == {'audited-final.adf', 'tool-snapshot.py', 'export.tcl'},
            'prepared file inventory differs')
    for name, digest in plan['WorkInputSHA256'].items():
        require(sha(work / name) == digest, 'prepared input changed: ' + name)
    require(sha(work / 'audited-final.adf') == ADF_SHA and sha(work / 'tool-snapshot.py') == sha(SELF),
            'copied final ADF or tool snapshot differs')
    return plan


def compare_native(report, exceptions):
    baseline = comparison.summaries(FINAL / (TARGET + '.rtr'))
    current = comparison.summaries(report)
    require(current == baseline, 'fresh native clock or any timing summary differs')
    for rows in current[0].values():
        require(all(r['FailingChecks'] == 0 and r['WorstSlackNS'] >= 0
                    and r['TotalNegativeSlackNS'] == 0 for r in rows.values()), 'fresh timing failure')
    def false(path):
        with Path(path).open(encoding='gb18030', errors='strict') as stream:
            values = comparison.native.parse_false_paths(stream)
        return {key: Counter(json.dumps(r, sort_keys=True) for r in rows) for key, rows in values.items()}
    require(false(exceptions) == false(FINAL / (TARGET + '_exception.rtr')),
            'fresh false-path identities, transitions or delays differ')
    require(comparison.other_exceptions(exceptions) ==
            comparison.other_exceptions(FINAL / (TARGET + '_exception.rtr')),
            'fresh non-false timing exceptions differ')
    return {'AllTenNativeTimingTablesPassed': True, 'AllNativeSummariesAndClocksUnchanged': True,
            'AllExceptionPathsUnchanged': True, 'NoDataSetupOrHoldFalsePaths': True}


def gate(work):
    # PDS invokes this through the validated P: alias; resolve it to the real
    # workspace identity before applying canonical-directory checks.
    work = work_path(Path(work).resolve())
    plan = validate(work)
    result = compare_native(work / REPORT, work / EXCEPTIONS)
    validate(work)
    result.update(Schema='processed-output-pre-bit-gate-v1', GatePassed=True,
                  CheckedUTC=utc(), FinalADFSHA256=ADF_SHA, HardwareAccessed=False,
                  HardwareReleaseAllowed=False,
                  EvidenceSHA256={name: sha(work / name) for name in
                                  ('bitstream-plan.json', 'audited-final.adf', 'export.tcl', REPORT, EXCEPTIONS)})
    write_json(work / 'pre-bit-audit.json', result)
    return result


def actual_events(text):
    events = []
    for line in text.splitlines():
        match = re.fullmatch(r'Process "([^"]+)" (started|done)\.', line.strip())
        if match:
            events.append((match[1], match[2]))
        elif line.strip().startswith('PROCESSED_OUTPUT_PRE_BIT_AUDIT_PASS'):
            require(line.strip() == MARKER, 'incorrect runtime gate marker')
            events.append(('Runtime gate', 'passed'))
        elif line.strip() == COMPLETE:
            events.append(('Bitstream', 'complete'))
    require(events == [('Report Timing', 'started'), ('Report Timing', 'done'),
                       ('Runtime gate', 'passed'), ('Generate Bitstream', 'started'),
                       ('Generate Bitstream', 'done'), ('Bitstream', 'complete')],
            'actual execution order is not STA, gate, bit generation, completion')
    return events


def bit_header(data):
    prefix = bytes.fromhex('00090ff00ff00ff00ff000') + b'PANGO MICROSYSTEMS, INC.\0\1'
    require(data.startswith(prefix), 'wrong native bitstream prefix')
    offset, result = len(prefix), {}
    for tag, name in zip(b'abcdef', ('Design','Device','Date','Time','Generator','Version')):
        require(offset + 3 <= len(data) and data[offset] == tag, 'missing bitstream header field')
        count = int.from_bytes(data[offset + 1:offset + 3], 'big')
        require(count > 0 and offset + 3 + count <= len(data), 'truncated bitstream field')
        raw = data[offset + 3:offset + 3 + count]
        require(raw[-1:] == b'\0' and b'\0' not in raw[:-1], 'invalid bitstream text field')
        result[name] = raw[:-1].decode('ascii')
        offset += 3 + count
    require(data[offset:offset + 3] == b'ghi', 'bitstream header terminator differs')
    for name, expected in {'Design': TARGET, 'Device': 'Logos2-PG2L100H--6-FBG676',
                           'Generator': 'Fabric Compiler', 'Version': '2023.2-SP3<154097>'}.items():
        require(result[name] == expected, 'bitstream identity differs: ' + name)
    require(len(data) > 1000000, 'empty/truncated programming payload')
    return result


def verify(work):
    work = work_path(work)
    plan = validate(work)
    receipt = load(work / 'execution-result.json')
    require(receipt.get('Schema') == 'processed-output-bitstream-execution-v1'
            and receipt.get('ExitCode') == 0 and receipt.get('TimedOut') is False
            and receipt.get('StoppedForUnexpectedStage') is False
            and receipt.get('InputDrift') == [] and receipt.get('Diagnostics') == []
            and receipt.get('Command') == plan['Command']
            and receipt.get('FinalADFSHA256') == ADF_SHA, 'native execution did not complete cleanly')
    for name, digest in receipt['Artifacts'].items():
        path = export.canonical_file(work / name, work)
        require(sha(path) == digest, 'native artifact changed: ' + name)
    text = (work / 'stdout.log').read_text(encoding='gb18030', errors='strict')
    events = actual_events(text)
    result = compare_native(work / REPORT, work / EXCEPTIONS)
    audited = load(work / 'pre-bit-audit.json')
    require(all(audited.get(k) == v for k, v in result.items())
            and audited.get('GatePassed') is True and audited.get('FinalADFSHA256') == ADF_SHA,
            'runtime audit claim differs')
    require(audited['EvidenceSHA256'] == {name: sha(work / name) for name in
            ('bitstream-plan.json', 'audited-final.adf', 'export.tcl', REPORT, EXCEPTIONS)},
            'runtime audit evidence differs')
    commands = re.findall(r'(?m)^Executing : (gen_bit_stream .+)$', text)
    commands = [c for c in commands if not c.endswith(' successfully.')]
    expected_input = 'P:/distortion/build/processed-output/' + work.name + '/audited-final.adf'
    require(len(commands) == 1 and '-input_db_file ' + expected_input in commands[0],
            'native generation did not use the exact final ADF')
    bgr = work / 'generate_bitstream' / (TARGET + '.bgr')
    require(bgr.is_file() and 'Generating Programming File done.' in bgr.read_text(encoding='gb18030'),
            'native bit generation report lacks completion')
    data = (work / BIT).read_bytes()
    header = bit_header(data)
    validate(work)
    return {'Schema': 'processed-output-offline-bitstream-verification-v1', 'Verified': True,
            'CheckedUTC': utc(), 'FinalADFSHA256': ADF_SHA, 'RuntimeGateBeforeGeneration': True,
            'ActualEvents': events, 'NativeTiming': result,
            'Bitstream': {'Path': str(work / BIT), 'SHA256': hashlib.sha256(data).hexdigest(),
                          'Bytes': len(data), 'Header': header},
            'EvidenceSHA256': {name: sha(work / name) for name in
                              ('bitstream-plan.json','pre-bit-audit.json','execution-result.json',
                               'stdout.log','stderr.log',REPORT,EXCEPTIONS,BIT)},
            'VerifierSHA256': sha(SELF), 'HardwareAccessed': False, 'HardwareReleaseAllowed': False,
            'CDCPhysicalAccepted': False, 'ExternalIOAccepted': False}


def execute(work, maximum_seconds=900):
    work = work_path(work)
    plan = validate(work)
    require(30 <= maximum_seconds <= plan['MaximumSeconds'], 'invalid bounded deadline')
    require(set(p.name for p in work.iterdir()) ==
            {'audited-final.adf','tool-snapshot.py','export.tcl','bitstream-plan.json'},
            'execution requires a fresh prepared work directory')
    watched = {Path(p): h for p, h in plan['ProjectInputSHA256'].items()}
    watched.update({work / n: h for n, h in plan['WorkInputSHA256'].items()})
    watched[work / 'bitstream-plan.json'] = sha(work / 'bitstream-plan.json')
    alias, made_alias, process = Path('P:/'), False, None
    receipt = {'Schema': 'processed-output-bitstream-execution-v1', 'StartedUTC': utc(),
               'Command': plan['Command'], 'FinalADFSHA256': ADF_SHA,
               'HardwareAccessed': False, 'HardwareReleaseAllowed': False, 'TimedOut': False,
               'StoppedForUnexpectedStage': False, 'MaximumSeconds': maximum_seconds}
    try:
        if not alias.exists():
            subprocess.run(['subst','P:',str(PROJECT.parent)], check=True, capture_output=True, timeout=15)
            made_alias = True
        require(alias.samefile(PROJECT.parent), 'P: identifies a different directory')
        require((alias / '.venv/Scripts/python.exe').samefile(PYTHON), 'runtime Python alias differs')
        write_json(work / 'execution-start.json', receipt)
        started = time.monotonic()
        with (work / 'stdout.log').open('xb') as out, (work / 'stderr.log').open('xb') as err:
            process = subprocess.Popen(plan['Command'], cwd=plan['Command'][4], stdout=out, stderr=err,
                                       creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            while process.poll() is None:
                remaining = maximum_seconds - (time.monotonic() - started)
                if remaining <= 0:
                    receipt['TimedOut'] = True
                    export.stop_owned(process)
                    break
                try:
                    process.wait(timeout=min(5,remaining))
                except subprocess.TimeoutExpired:
                    pass
                text = (work / 'stdout.log').read_text(encoding='gb18030', errors='strict')
                stages = re.findall(r'^Process "([^"]+)" started\.',text,re.M)
                if stages != STAGES[:len(stages)]:
                    receipt['StoppedForUnexpectedStage'] = True
                    export.stop_owned(process)
                    break
        diagnostics = []
        for path in work.rglob('*.log'):
            diagnostics.extend(str(path.relative_to(work)) + ': ' + line.strip() for line in
                re.findall(r'(?m)^\s*(?:E:|F:|ERROR:|FATAL:|Traceback).*$',path.read_text(encoding='gb18030',errors='strict')))
        receipt.update(FinishedUTC=utc(),ElapsedSeconds=round(time.monotonic()-started,3),
                       ExitCode=process.poll(),InputDrift=export.check_inputs(watched),
                       Diagnostics=diagnostics,
                       Artifacts={str(p.relative_to(work)):sha(p) for p in work.rglob('*') if p.is_file()
                                  and p.suffix in ('.log','.rtr','.sbit','.bgr','.tcl')})
        write_json(work / 'execution-result.json',receipt)
        result = verify(work)
        write_json(work / 'verification.json',result)
        return result
    finally:
        export.stop_owned(process)
        if made_alias and alias.exists() and alias.samefile(PROJECT.parent):
            subprocess.run(['subst','P:','/D'],check=True,capture_output=True,timeout=15)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--prepare',type=Path)
    mode.add_argument('--execute',type=Path)
    mode.add_argument('--gate',type=Path)
    mode.add_argument('--verify',type=Path)
    args = parser.parse_args()
    if args.prepare:
        result = prepare(args.prepare)
        print(json.dumps({'PreparedOnly':True,'Command':result['Command']}))
    elif args.gate:
        gate(args.gate)
        print(MARKER)
    elif args.execute:
        result = execute(args.execute)
        print(json.dumps({'Verified':result['Verified'],'Bitstream':result['Bitstream']}))
    else:
        result = verify(args.verify)
        print(json.dumps({'Verified':result['Verified'],'Bitstream':result['Bitstream']}))


if __name__ == '__main__':
    main()
