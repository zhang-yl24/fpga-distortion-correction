"""Hash-bound handoff of a completed full upright bit authority.

This adapter consumes a successful owned full-prepare completion receipt.
It rechecks every frozen authority input at each boundary without reparsing
the same functional/route proofs. Fresh native STA, its exception gate, bit
identity, stage order, deadline and owned cleanup remain mandatory.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import camera_vga_upright_bitstream as bit

prep, inspect = bit.prep, bit.inspect
require, sha = bit.require, bit.sha
SELF = Path(__file__).resolve()
original = bit
read = bit.read
SEED_SCHEMA = 'camera-vga-upright-authority-seed-v1'
COMPLETION_SCHEMA = 'camera-vga-upright-full-prepare-completion-v1'
PLAN_SCHEMA = 'camera-vga-upright-fast-bitstream-plan-v1'
EXEC_SCHEMA = 'camera-vga-upright-fast-bitstream-execution-v1'
VERIFY_SCHEMA = 'camera-vga-upright-fast-bitstream-verification-v1'
GATE_SCHEMA = 'camera-vga-upright-fast-pre-bit-gate-v1'
PREPARED = {'audited-final.adf', 'tool-snapshot.py', 'bitstream.tcl', 'bitstream-plan.json'}
REPORT, EXCEPTIONS, BIT = bit.REPORT, bit.EXCEPTIONS, bit.BIT


def binding(path):
    path = Path(path).absolute()
    return {'Path': str(path), 'SHA256': sha(path)}


def original_plan(c, work, maximum):
    """Reconstruct only the deterministic plan envelope; no authority call."""
    script = bit.render(c, work)
    value = {'Schema': bit.PLAN_SCHEMA, 'Target': prep.TARGET,
        'Request': binding(c['RequestPath']), 'WorkDirectory': str(work),
        'CandidateADFSHA256': c['CandidateSHA256'], 'MaximumSeconds': maximum,
        'InputSHA256': c['AuthorityInputSHA256'], 'ExpectedActualStages': bit.STAGES,
        'TclSHA256': prep.baseline.paths.sha_bytes(script.encode('ascii')),
        'Command': [c['Build']['PDS']['Executable'], '-file', (work/'bitstream.tcl').as_posix(),
                    '-work_dir', work.as_posix(), '-project_name', prep.TARGET],
        'HardwareAccessed': False, 'HardwareReleaseAllowed': False, 'ExternalACTimingAccepted': False,
        'DiagnosticOnly': True, 'BitstreamRequested': True, 'EDAExecutedByPreparer': False}
    return value, script


def bind_seed(seed_path, seed_sha256):
    watched = {}
    seed_path = bit.ref({'Path': str(Path(seed_path).absolute()), 'SHA256': seed_sha256}, watched)
    seed = bit.read(seed_path)
    require(seed.get('Schema') == SEED_SCHEMA and seed.get('Target') == prep.TARGET
            and seed.get('FullPrepareCompleted') is True and seed.get('HardwareAccessed') is False,
            'completed full-authority seed required')
    completion_path = bit.ref(seed['FullPrepareCompletion'], watched)
    completed = bit.read(completion_path)
    require(completed.get('Schema') == COMPLETION_SCHEMA and completed.get('Target') == prep.TARGET
            and type(completed.get('OwnedExecSession')) is int and completed['OwnedExecSession'] > 0
            and completed.get('ExitCode') == 0 and completed.get('Prepared') is True
            and completed.get('FullPrepareCompleted') is True and completed.get('EDAExecuted') is False
            and isinstance(completed.get('Result'), dict) and completed['Result'].get('Prepared') is True,
            'successful owned full prepare completion required')
    plan_path = bit.ref(seed['BitPlan'], watched)
    original = bit.read(plan_path)
    work = prep.work_path(plan_path.parent)
    require(plan_path.name == 'bitstream-plan.json' and work.name.startswith('bit-')
            and original.get('Schema') == bit.PLAN_SCHEMA and original.get('Target') == prep.TARGET,
            'seed must bind the original full-authority bit plan')
    request_path = bit.ref(seed['Request'], watched)
    request = bit.read(request_path)
    require(request.get('Schema') == bit.REQUEST_SCHEMA and request.get('Target') == prep.TARGET
            and original.get('Request') == seed['Request'], 'original request binding differs')
    build_path = bit.ref(request['BuildPlan'], watched)
    build = bit.read(build_path)
    pds = Path(build['PDS']['Executable'])
    inputs = seed.get('InputSHA256')
    require(isinstance(inputs, dict) and inputs and inputs == original.get('InputSHA256'),
            'seed must preserve the entire full-authority input closure')
    tools = {p: h for p, h in inputs.items() if Path(p).suffix.lower() in ('.py', '.exe')}
    require(tools and seed.get('ToolSHA256') == tools, 'complete original helper/executable closure required')
    for key in ('Request', 'BitPlan', 'InputSHA256', 'ToolSHA256', 'WorkInputSHA256'):
        require(completed.get(key) == seed.get(key), 'completion/seed binding differs: '+key)
    for path, digest in inputs.items():
        bit.add(watched, path, digest, pds)
    for path in (request_path, build_path, bit.SELF, bit.PYTHON, Path(inspect.__file__).resolve()):
        require(inputs.get(str(path)) == sha(path), 'required authority input missing: '+str(path))
    require(seed['CandidateADF'] == request['CandidateADF'], 'candidate differs from audited request')
    candidate = bit.ref(seed['CandidateADF'], watched, pds)
    report = bit.ref(seed['FinalReport'], watched, pds)
    exceptions = bit.ref(seed['FinalExceptions'], watched, pds)
    for path in (candidate, report, exceptions):
        require(inputs.get(str(path)) == sha(path), 'context evidence missing from authority closure')
    final_path = bit.ref(request['FinalInspectionReceipt'], watched, pds)
    final = bit.read(final_path)
    require(report == bit.interfaces.artifact(final_path, final, prep.TARGET+'.rtr')
            and exceptions == bit.interfaces.artifact(final_path, final, prep.TARGET+'_exception.rtr'),
            'seed timing context differs from full-authority final export')
    c = {'Request': request, 'RequestPath': request_path, 'Build': build, 'PlanPath': build_path,
         'Candidate': candidate, 'CandidateSHA256': sha(candidate), 'FinalReport': report,
         'FinalExceptions': exceptions, 'Watched': watched, 'AuthorityInputSHA256': inputs,
         'AuthoritySeed': binding(seed_path), 'OriginalBitPlan': binding(plan_path)}
    maximum = original['MaximumSeconds']
    require(type(maximum) is int and 60 <= maximum <= 900, 'invalid original deadline')
    expected, script = original_plan(c, work, maximum)
    require(set(original) == set(expected)|{'PreparedUTC'}
            and {k: v for k, v in original.items() if k != 'PreparedUTC'} == expected,
            'original completed plan envelope differs')
    require(completed['Command'] == {'Function': 'camera_vga_upright_bitstream.prepare',
            'Request': str(request_path), 'Work': str(work), 'MaximumSeconds': maximum},
            'completion does not identify the original prepare invocation')
    require(completed['Result'] == {'Prepared': True, 'Work': str(work), 'PlanSHA256': sha(plan_path),
            'CandidateADFSHA256': c['CandidateSHA256'], 'BoundInputs': len(inputs),
            'Command': original['Command'], 'EDAExecuted': False, 'HardwareAccessed': False},
            'completion result differs from successful original CLI output')
    require(seed.get('WorkInputSHA256') == {str(work/n): sha(work/n) for n in PREPARED},
            'all four original prepared artifacts must be frozen')
    for path, digest in seed['WorkInputSHA256'].items():
        bit.add(watched, path, digest, pds)
    require((work/'bitstream.tcl').read_bytes() == script.encode('ascii')
            and sha(work/'audited-final.adf') == c['CandidateSHA256']
            and sha(work/'tool-snapshot.py') == sha(bit.SELF), 'original prepared artifacts differ')
    for path in (SELF, bit.SELF, Path(inspect.diagnostic.__file__).resolve(),
                 Path(inspect.diagnostic.cleanup.__file__).resolve()):
        bit.add(watched, path, pds=pds)
    return c, original


def render(c, work):
    text = bit.render(c, work)
    old = '-B {'+bit.SELF.as_posix()+'} --gate {'
    new = '-B {'+SELF.as_posix()+'} --gate {'
    require(text.count(old) == 1, 'one exact original CPU gate invocation required')
    return text.replace(old, new, 1)


def recipe(seed_path, seed_sha256, work):
    work = prep.work_path(work)
    require(work.name.startswith('bit-fast-'), 'fresh direct bit-fast-* stage required')
    c, original = bind_seed(seed_path, seed_sha256)
    require(work != Path(original['WorkDirectory']), 'original prepared stage is immutable')
    script = render(c, work)
    plan = {'Schema': PLAN_SCHEMA, 'Target': prep.TARGET, 'AuthoritySeed': c['AuthoritySeed'],
        'OriginalBitPlan': c['OriginalBitPlan'], 'Request': binding(c['RequestPath']),
        'WorkDirectory': str(work), 'CandidateADFSHA256': c['CandidateSHA256'],
        'MaximumSeconds': original['MaximumSeconds'], 'ExpectedActualStages': bit.STAGES,
        'InputSHA256': {str(p): h for p, h in c['Watched'].items()},
        'TclSHA256': prep.baseline.paths.sha_bytes(script.encode('ascii')),
        'Command': [c['Build']['PDS']['Executable'], '-file', (work/'bitstream.tcl').as_posix(),
                    '-work_dir', work.as_posix(), '-project_name', prep.TARGET],
        'FullAuthorityReused': True, 'AllAuthorityInputsRehashed': True,
        'HardwareAccessed': False, 'HardwareReleaseAllowed': False, 'ExternalACTimingAccepted': False,
        'DiagnosticOnly': True, 'BitstreamRequested': True, 'EDAExecutedByPreparer': False}
    return plan, script, c


def prepare(seed_path, work, seed_sha256):
    plan, script, c = recipe(seed_path, seed_sha256, work)
    work = Path(plan['WorkDirectory'])
    require(not work.exists(), 'fresh fast bit stage required')
    work.mkdir()
    shutil.copyfile(c['Candidate'], work/'audited-final.adf')
    shutil.copyfile(SELF, work/'tool-snapshot.py')
    (work/'bitstream.tcl').write_bytes(script.encode('ascii'))
    plan['PreparedUTC'] = prep.utc()
    inspect.diagnostic.write(work/'bitstream-plan.json', plan)
    validate(work)
    return plan


def validate(work):
    work = prep.work_path(work)
    plan = bit.read(work/'bitstream-plan.json')
    require(plan.get('Schema') == PLAN_SCHEMA and plan.get('Target') == prep.TARGET, 'fast bit plan required')
    seed = plan['AuthoritySeed']
    expected, script, c = recipe(seed['Path'], seed['SHA256'], work)
    require(set(plan) == set(expected)|{'PreparedUTC'}
            and {k: v for k, v in plan.items() if k != 'PreparedUTC'} == expected, 'fast bit plan drift')
    require((work/'bitstream.tcl').read_bytes() == script.encode('ascii')
            and sha(work/'audited-final.adf') == c['CandidateSHA256']
            and sha(work/'tool-snapshot.py') == sha(SELF), 'fast prepared artifact drift')
    return plan, c


def gate_evidence(work):
    return {n: sha(work/n) for n in ('bitstream-plan.json', 'audited-final.adf', 'bitstream.tcl', REPORT, EXCEPTIONS)}


def gate(work):
    plan, c = validate(work)
    work = Path(work)
    before = gate_evidence(work)
    checks = bit.compare_native(c, work/REPORT, work/EXCEPTIONS)
    validate(work)
    require(gate_evidence(work) == before, 'fresh STA artifacts changed during CPU gate')
    value = {'Schema': GATE_SCHEMA, 'GatePassed': True, 'Target': prep.TARGET,
        'AuthoritySeed': plan['AuthoritySeed'], 'CandidateADFSHA256': c['CandidateSHA256'],
        'CheckedUTC': prep.utc(), **checks, 'EvidenceSHA256': before}
    inspect.diagnostic.write(work/'pre-bit-audit.json', value)
    return value


def verify(work):
    plan, c = validate(work)
    work = Path(work)
    receipt = bit.read(work/'execution-result.json')
    receipt_hash = sha(work/'execution-result.json')
    require(receipt.get('Schema') == EXEC_SCHEMA and receipt.get('Target') == prep.TARGET
            and receipt.get('EDAExecuted') is True and receipt.get('HardwareAccessed') is False
            and receipt.get('ExitCode') == 0
            and receipt.get('InputDrift') == [] and receipt.get('Diagnostics') == []
            and not receipt.get('Error') and receipt.get('TimedOut') is False
            and receipt.get('StoppedForUnexpectedStage') is False and receipt.get('Command') == plan['Command']
            and receipt.get('CandidateADFSHA256') == c['CandidateSHA256']
            and receipt.get('AuthoritySeed') == plan['AuthoritySeed']
            and receipt.get('PlanSHA256') == sha(work/'bitstream-plan.json')
            and receipt.get('ExecutorSHA256') == sha(SELF)
            and receipt.get('Cleanup', {}).get('Complete') is True, 'unclean fast bit execution')
    needed = {'stdout.log', 'stderr.log', REPORT, EXCEPTIONS, BIT, 'bitstream.tcl',
              'generate_bitstream/'+prep.TARGET+'.bgr'}
    require(isinstance(receipt.get('Artifacts'), dict) and needed <= set(receipt['Artifacts']),
            'complete native bit artifact inventory required')
    def recheck_artifacts():
        require(sha(work/'execution-result.json') == receipt_hash, 'execution receipt changed')
        for name, digest in receipt['Artifacts'].items():
            require(sha(inspect.canonical(work/name, work)) == digest, 'native bit artifact drift')
    recheck_artifacts()
    text = (work/'stdout.log').read_text(encoding='gb18030')
    actual = bit.events(text, c['CandidateSHA256'])
    checks = bit.compare_native(c, work/REPORT, work/EXCEPTIONS)
    proof = bit.read(work/'pre-bit-audit.json')
    proof_hash = sha(work/'pre-bit-audit.json')
    require(proof.get('Schema') == GATE_SCHEMA and proof.get('GatePassed') is True
            and proof.get('CandidateADFSHA256') == c['CandidateSHA256']
            and proof.get('AuthoritySeed') == plan['AuthoritySeed']
            and all(proof.get(k) == v for k, v in checks.items()), 'fast runtime gate differs')
    require(proof.get('EvidenceSHA256') == gate_evidence(work), 'pre-bit evidence drift')
    commands = [s for s in re.findall(r'(?m)^Executing : (gen_bit_stream .+)$', text) if not s.endswith(' successfully.')]
    require(len(commands) == 1 and '-input_db_file '+(work/'audited-final.adf').as_posix() in commands[0],
            'bit generation input differs')
    bgr = work/'generate_bitstream'/(prep.TARGET+'.bgr')
    require('Generating Programming File done.' in bgr.read_text(encoding='gb18030'), 'programming report not complete')
    data = (work/BIT).read_bytes()
    header = bit.bit_header(data)
    validate(work)
    recheck_artifacts()
    require(sha(work/'pre-bit-audit.json') == proof_hash, 'runtime gate changed during verification')
    return {'Schema': VERIFY_SCHEMA, 'Verified': True, 'Target': prep.TARGET, 'CheckedUTC': prep.utc(),
        'AuthoritySeed': plan['AuthoritySeed'], 'InputSHA256': plan['InputSHA256'],
        'CandidateADFSHA256': c['CandidateSHA256'], 'NativeTiming': checks, 'ActualEvents': actual,
        'Bitstream': {'Path': str(work/BIT), 'SHA256': sha(work/BIT), 'Bytes': len(data), 'Header': header},
        'EvidenceSHA256': {n: sha(work/n) for n in ('bitstream-plan.json', 'pre-bit-audit.json',
            'execution-result.json', 'stdout.log', 'stderr.log', REPORT, EXCEPTIONS, BIT)},
        'VerifierSHA256': sha(SELF), 'HardwareAccessed': False, 'HardwareReleaseAllowed': False,
        'ExternalACTimingAccepted': False, 'DiagnosticOnly': True}


def execute(work):
    plan, c = validate(work)
    work = Path(work)
    require(os.name == 'nt', 'native fast bit execution requires Windows')
    require({p.name for p in work.iterdir()} == PREPARED, 'fresh prepared fast bit directory required')
    watched = dict(c['Watched'])
    watched.update({p: sha(p) for p in work.iterdir()})
    value = {'Schema': EXEC_SCHEMA, 'StartedUTC': prep.utc(), 'Target': prep.TARGET,
        'Command': plan['Command'], 'CandidateADFSHA256': c['CandidateSHA256'],
        'AuthoritySeed': plan['AuthoritySeed'], 'PlanSHA256': sha(work/'bitstream-plan.json'),
        'ExecutorSHA256': sha(SELF), 'MaximumSeconds': plan['MaximumSeconds'], 'HardwareAccessed': False,
        'TimedOut': False, 'StoppedForUnexpectedStage': False, 'ExitCode': None, 'EDAExecuted': False}
    inspect.diagnostic.write(work/'execution-start.json', value)
    process = None
    started = time.monotonic()
    expected = [(stage, event) for stage in bit.STAGES for event in ('started', 'done')]
    try:
        with (work/'stdout.log').open('xb') as out, (work/'stderr.log').open('xb') as err:
            process = subprocess.Popen(plan['Command'], cwd=work, stdout=out, stderr=err, shell=False,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            value.update(EDAExecuted=True, OwnedPID=process.pid)
            while process.poll() is None:
                remaining = plan['MaximumSeconds']-(time.monotonic()-started)
                if remaining <= 0:
                    value['TimedOut'] = True
                    break
                try:
                    process.wait(timeout=min(3, remaining))
                except subprocess.TimeoutExpired:
                    pass
                actual = inspect.diagnostic.stage_events((work/'stdout.log').read_text(encoding='gb18030', errors='replace'))
                if actual != expected[:len(actual)]:
                    value['StoppedForUnexpectedStage'] = True
                    break
    except BaseException as error:
        value['Error'] = type(error).__name__+': '+str(error)
    finally:
        if process is not None:
            if process.poll() is None:
                value['Cleanup'] = inspect.diagnostic.cleanup.stop_owned_tree(process, work, 'bounded fast upright bit')
            else:
                value['Cleanup'] = {'Complete': True, 'OwnedPID': process.pid, 'ParentExited': True,
                    'DescendantLivenessIndependentlyVerified': False}
            value['ExitCode'] = process.poll()
        else:
            value['Cleanup'] = {'Complete': True, 'Required': False}
    diagnostics = []
    for path in work.rglob('*.log'):
        diagnostics += [path.relative_to(work).as_posix()+': '+line.strip() for line in re.findall(
            r'(?m)^\s*(?:E:|F:|ERROR:|FATAL:|Traceback).*$', path.read_text(encoding='gb18030', errors='replace'))]
    value.update(FinishedUTC=prep.utc(), ElapsedSeconds=round(time.monotonic()-started, 3),
        InputDrift=inspect.drift(watched), Diagnostics=diagnostics,
        Artifacts={p.relative_to(work).as_posix(): sha(p) for p in work.rglob('*') if p.is_file()
                   and p.suffix in ('.log', '.rtr', '.sbit', '.bgr', '.tcl')})
    inspect.diagnostic.write(work/'execution-result.json', value)
    verified = verify(work)
    inspect.diagnostic.write(work/'verification.json', verified)
    return verified


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    for name in ('prepare', 'validate', 'execute', 'gate', 'verify'):
        mode.add_argument('--'+name, type=Path)
    parser.add_argument('--authority-seed', type=Path)
    parser.add_argument('--seed-sha256')
    args = parser.parse_args()
    if args.prepare:
        require(args.authority_seed is not None and args.seed_sha256 is not None, 'explicit seed path/hash required')
        value = prepare(args.authority_seed, args.prepare, args.seed_sha256)
        print(json.dumps({'Prepared': True, 'Command': value['Command'], 'EDAExecuted': False}))
    elif args.gate:
        value = gate(args.gate)
        print('CAMERA_VGA_UPRIGHT_GATE_PASS '+value['CandidateADFSHA256'])
    elif args.validate:
        validate(args.validate)
        print(json.dumps({'Validated': True, 'Target': prep.TARGET, 'EDAExecuted': False}))
    else:
        value = execute(args.execute) if args.execute else verify(args.verify)
        print(json.dumps({'Verified': value['Verified'], 'Bitstream': value['Bitstream']}))


if __name__ == '__main__':
    main()
