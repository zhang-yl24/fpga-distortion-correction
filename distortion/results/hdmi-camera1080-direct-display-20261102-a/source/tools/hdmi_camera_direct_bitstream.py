"""Source-bound HDMI camera direct diagnostic bitstream; preparation never runs PDS.

Only a recomputed current physical proof plus the exact direct sampler/control
regressions can authorize fresh STA, CPU gate, then bit generation. External
AC, input pixels, display and full CDC/MTBF acceptance remain separate.
"""
import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

SITE=Path(__file__).resolve().parents[2]/'.venv/Lib/site-packages'
sys.path.insert(0,str(SITE))
import hdmi_camera_direct_build as build
import hdmi_camera_direct_native as native


SELF = Path(__file__).resolve()
TARGET, ROOT, WORK = build.TARGET, build.ROOT, build.WORK
PYTHON = Path('D:/anaconda3/python.exe')
REQUEST_SCHEMA = 'hdmi-camera-direct-bitstream-request-v1'
PLAN_SCHEMA = 'hdmi-camera-direct-bitstream-plan-v1'
EXEC_SCHEMA = 'hdmi-camera-direct-bitstream-execution-v1'
PROOF_SCHEMA = 'hdmi-camera-direct-final-physical-proof-v1'
GATE_SCHEMA = 'hdmi-camera-direct-pre-bit-gate-v1'
GATE = 'HDMI_CAMERA_DIRECT_PRE_BIT_GATE_PASS'
COMPLETE = 'HDMI_CAMERA_DIRECT_BITSTREAM_COMPLETE'
FIELDS = {'Schema', 'Target', 'PhysicalProof', 'ControlSimulation'}
REPORT = 'report_timing/' + TARGET + '.rtr'
EXCEPTIONS = 'report_timing/' + TARGET + '_exception.rtr'
BIT = 'generate_bitstream/' + TARGET + '.sbit'
BGR = 'generate_bitstream/' + TARGET + '.bgr'
STAGES = ['Report Timing', 'Generate Bitstream']
EXPECTED_BIT_BYTES = 3791112
require, sha, read, write = build.require, build.sha, build.read, build.write
_AUTHORITY_CACHE = {}


def utc():
    return datetime.now(timezone.utc).isoformat()


def ref(path):
    path = Path(path).resolve()
    return {'Path': str(path), 'SHA256': sha(path)}


def add(watched, path, expected=None):
    path = Path(path).absolute()
    require(path == path.resolve() and path.is_file(), 'canonical existing input required: ' + str(path))
    digest = sha(path)
    require(expected is None or isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected)
            and digest == expected, 'input SHA differs: ' + str(path))
    require(str(path) not in watched or watched[str(path)] == digest, 'conflicting input SHA')
    watched[str(path)] = digest
    return path


def merge(watched, inputs):
    for path, digest in inputs.items():
        add(watched, path, digest)


def binding(value, watched):
    require(isinstance(value, dict) and set(value) == {'Path', 'SHA256'}, 'exact Path/SHA256 reference required')
    return add(watched, value['Path'], value['SHA256'])


def drift(watched):
    return [str(p) for p, h in watched.items() if not Path(p).is_file() or sha(p) != h]


def physical_provider():
    module = importlib.import_module('hdmi_camera_direct_final')
    require(Path(module.__file__).resolve() == SELF.with_name('hdmi_camera_direct_final.py'), 'physical provider location differs')
    return module


def physical_flags(proof):
    require(proof.get('Schema')==PROOF_SCHEMA and proof.get('Target')==TARGET,'current direct physical proof required')
    for name in ('Passed','STAAllTenPassed','NativeWarningsReviewed','NetlistEquivalent',
                 'AllFFPlacementsEquivalent','RoutesUnchanged','ResetAccepted','SourceSamplingIsolatedVerified'):
        require(proof.get(name) is True,'direct physical proof incomplete: '+name)
    pins,cdc=proof.get('Pins',{}),proof.get('CDC',{})
    declared=pins.get('DeclaredTopPorts')
    require(type(declared) is int and declared>0 and pins.get('NativeActivePorts')==declared and
            pins.get('UnusedPads')==[] and pins.get('NativeElectricalParametersVerified') is True,
            'complete direct pin/electrical disposition required')
    require(cdc.get('InterstageTimingAccepted') is True and cdc.get('Missing')==[] and
            cdc.get('Violations')==[],'complete direct CDC acceptance required')


def simulation_provider():
    module=importlib.import_module('run_hdmi_camera_direct_sim')
    require(Path(module.__file__).resolve()==SELF.with_name('run_hdmi_camera_direct_sim.py'),
            'direct simulation provider location differs')
    return module


def bind_physical_core(proof, verified_inputs, proof_path, watched):
    """Retain the complete saved proof core, independently of importing callers.

    The provider already rederived all facts and verified its full current
    closure. Additional caller modules must not change an otherwise identical
    bit recipe; every saved core input and the proof itself remain mandatory.
    """
    core = proof.get('InputSHA256')
    require(isinstance(core, dict) and core, 'physical proof input core required')
    verified = {}
    for name, digest in verified_inputs.items():
        path = Path(name).absolute()
        require(path == path.resolve() and
                (str(path) not in verified or verified[str(path)] == digest),
                'ambiguous verified physical input')
        verified[str(path)] = digest
    require(all(verified.get(name) == digest for name, digest in core.items()),
            'verified physical inputs omit or change saved proof core')
    proof_path = Path(proof_path).resolve()
    require(verified.get(str(proof_path)) == sha(proof_path), 'verified physical proof file unbound')
    merge(watched, core)
    add(watched, proof_path, verified[str(proof_path)])


def bind_log_group(path, hashes, watched):
    require(isinstance(hashes, dict) and 'simulation.log' in hashes, 'simulation log closure required')
    for name, digest in hashes.items():
        p = path.parent / name
        require(p.resolve().is_relative_to(path.parent), 'simulation artifact path escapes directory')
        add(watched, p, digest)
    text = (path.parent / 'simulation.log').read_text(encoding='utf-8', errors='replace')
    require('$finish called' in text and not re.search(r'(?im)^\s*(?:fatal|error):', text), 'simulation did not finish cleanly')
    return text


def audit_request(path, *, use_cache=True):
    watched = {}
    path = add(watched, path)
    require(path.parent == WORK.resolve(), 'bit request must be in direct work root')
    cache_key = (str(path), watched[str(path)])
    cached = _AUTHORITY_CACHE.get(cache_key) if use_cache else None
    if cached is not None:
        require(not drift(cached['Watched']), 'cached direct bit authority input drift')
        return copy.deepcopy(cached)
    request = read(path)
    require(set(request) == FIELDS and request['Schema'] == REQUEST_SCHEMA and request['Target'] == TARGET,
            'exact direct diagnostic bit request required')
    paths = {k: binding(request[k], watched) for k in FIELDS - {'Schema', 'Target'}}
    provider = physical_provider()
    proof, inputs = provider.verify(paths['PhysicalProof'])
    physical_flags(proof)
    require(proof == read(paths['PhysicalProof']), 'verified physical proof differs from stored proof')
    bind_physical_core(proof, inputs, paths['PhysicalProof'], watched)
    plan_path = binding(proof['BuildPlan'], watched)
    plan = build.validate(plan_path)
    for key in ('InputSHA256', 'PreparedSHA256'):
        merge(watched, plan[key])
    adf = binding(proof['FinalADF'], watched)
    require(adf.suffix == '.adf' and adf.is_relative_to(WORK.resolve()), 'final direct candidate ADF required')
    for key in ('FreshSTAReport', 'FreshSTAExceptions'):
        binding(proof[key], watched)
    simulations=simulation_provider()
    sim,sim_inputs=simulations.verify(paths['ControlSimulation'])
    require(sim['Passed'] is True and sim['HardwareAccessed'] is False and sim['SourceDrift']==[],
            'direct actual-top sampler/control regression required')
    merge(watched,sim_inputs)
    require(proof['Pins']['DeclaredTopPorts']==len(plan['Pins']['PinInventory']),
            'direct actual physical pins differ from frozen build')
    for name in (build.TOP,build.SAMPLER):
        original=str((ROOT/name).resolve())
        require(sim['SourceSHA256'][original]==plan['InputSHA256'][original],
                'direct regression compiled different top/sampler RTL')
    for p in (SELF,PYTHON,Path(provider.__file__),Path(build.__file__),Path(simulations.__file__),
              Path(native.__file__),Path(build.cleanup.__file__),Path(plan['Command'][0])):
        add(watched,p)
    for name in ('cv2','numpy','numpy._core._multiarray_umath'):
        module=sys.modules.get(name)
        if module is not None and getattr(module,'__file__',None):
            add(watched,Path(module.__file__))
            if name=='cv2':
                for p in Path(module.__file__).parent.glob('*.pyd'):add(watched,p)
    require(not drift(watched), 'direct bit authority input drift')
    context = {'Request': request, 'RequestPath': path, 'Proof': proof, 'BuildPlan': plan_path,
               'Build': plan, 'FinalADF': adf, 'FinalADFSHA256': sha(adf), 'Watched': watched}
    # Only immutable authority facts are reused within this interpreter. Fresh
    # STA, runtime gate, generation receipt and time-order checks stay outside.
    _AUTHORITY_CACHE[cache_key] = copy.deepcopy(context)
    return context


def context_prefix(plan_path):
    return native.context_prefix(plan_path)


def tcl_path(path):
    value = Path(path).resolve().as_posix()
    require(not any(c in value for c in '{}\r\n'), 'unsafe Tcl path')
    return '{' + value + '}'


def native_work(path):
    # Stable textual alias; only native execution requires its live mapping.
    return build.paths.alias_path(ROOT, 'P:/', Path(path))


def native_tcl(path):
    value=path if isinstance(path,str) else native_work(path)
    require(not any(c in value for c in '{}\r\n'), 'unsafe native Tcl path')
    return '{'+value+'}'


def render(context,work):
    w=Path(work)
    return (context_prefix(context['BuildPlan'])+'report_timing -force_to_run -input_db_file '+
        native_tcl(w/'audited-final.adf')+' -delay_type min_max -max_path 10000 -nworst 4 -report_exception TRUE\n'
        'if {[info script] ne {}} {\n    set checked [exec '+tcl_path(PYTHON)+' -B '+tcl_path(SELF)+
        ' --gate '+tcl_path(w)+']\n    puts $checked\n    if {[string first {'+GATE+' '+
        context['FinalADFSHA256']+'} $checked] < 0} {error {Missing exact direct pre-bit gate}}\n'
        '    gen_bit_stream -force_to_run -input_db_file '+native_tcl(w/'audited-final.adf')+
        ' -scbv {High Voltage} -unused_io_status UNUSED\n    puts {'+COMPLETE+'}\n    flush stdout\n}\n')


def recipe(request, work, maximum=900, *, fresh_authority=False):
    work = build.work_path(work)
    require(work.name.startswith('bit-') and type(maximum) is int and 60 <= maximum <= 900, 'bit-* stage and60..900s limit required')
    context = audit_request(request, use_cache=not fresh_authority)
    tcl = render(context, work)
    plan = {'Schema': PLAN_SCHEMA, 'Target': TARGET, 'Request': ref(request), 'WorkDirectory': str(work),
            'BuildPlan': ref(context['BuildPlan']), 'PhysicalProof': context['Request']['PhysicalProof'],
            'FinalADF': ref(context['FinalADF']), 'FinalADFSHA256': context['FinalADFSHA256'],
            'InputSHA256': context['Watched'], 'MaximumSeconds': maximum, 'ExpectedStages': STAGES,
            'TclSHA256': hashlib.sha256(tcl.encode('ascii')).hexdigest(),
            'Command': [context['Build']['Command'][0], '-file', native_work(work / 'bitstream.tcl'),
                        '-work_dir', native_work(work), '-project_name', TARGET],
            'HardwareAccessed': False, 'BitstreamRequested': True, 'EDAExecutedByPreparer': False,
            'HardwareReleaseAllowed': False, 'ExternalACAccepted': False, 'PixelsVerified': False}
    return plan, tcl, context


def prepare(request, work, maximum=900):
    build.paths.validate_repo_alias(ROOT,'P:/')
    plan, tcl, context = recipe(request, work, maximum)
    work = Path(plan['WorkDirectory'])
    require(not work.exists(), 'fresh bit directory required')
    work.mkdir()
    shutil.copyfile(context['FinalADF'], work / 'audited-final.adf')
    shutil.copyfile(SELF, work / 'tool-snapshot.py')
    (work / 'bitstream.tcl').write_text(tcl, encoding='ascii', newline='\n')
    write(work / 'bitstream-plan.json', plan)
    return plan


def validate(work, *, fresh_authority=False):
    work = build.work_path(work)
    plan = read(work / 'bitstream-plan.json')
    require(plan.get('Schema') == PLAN_SCHEMA and plan.get('Target') == TARGET, 'exact direct bit plan required')
    expected, tcl, context = recipe(plan['Request']['Path'], work, plan['MaximumSeconds'],
                                    fresh_authority=fresh_authority)
    require(plan == expected, 'direct bit plan differs from full recipe')
    require((work / 'bitstream.tcl').read_bytes() == tcl.encode('ascii')
            and sha(work / 'audited-final.adf') == context['FinalADFSHA256']
            and sha(work / 'tool-snapshot.py') == sha(SELF), 'prepared bit input drift')
    return plan, context


def compare_fresh(context, report, exceptions):
    value = physical_provider().compare_fresh_sta(context['Proof'], Path(report), Path(exceptions))
    require(all(value.get(k) is True for k in ('STAAllTenPassed', 'ClockAndSummaryIdentityPreserved',
                                              'AllExceptionPathsPreserved')), 'fresh physical STA or exceptions differ')
    return value


def gate(work):
    # Tcl starts a fresh Python process, but callers can also invoke this gate
    # in a long-lived interpreter. Recompute physical and simulation authority
    # in either case; only ordinary preparation/verification may reuse cache.
    plan, context = validate(work, fresh_authority=True)
    work = Path(work)
    require(build.diagnostics(work) == [], 'native critical/error diagnostics before bit')
    before = {name: sha(work / name) for name in ('bitstream-plan.json', 'audited-final.adf', 'bitstream.tcl', REPORT, EXCEPTIONS)}
    checks = compare_fresh(context, work / REPORT, work / EXCEPTIONS)
    require(not drift(plan['InputSHA256']) and before == {n: sha(work / n) for n in before}, 'pre-bit gate evidence drift')
    result = {'Schema': GATE_SCHEMA, 'Target': TARGET, 'GatePassed': True, 'FinalADFSHA256': context['FinalADFSHA256'],
              'CheckedUTC': utc(), 'Checks': checks, 'EvidenceSHA256': before, 'HardwareAccessed': False}
    write(work / 'pre-bit-audit.json', result)
    return result


def actual_events(text, digest):
    rows = []
    for line in text.splitlines():
        line = line.strip()
        match = re.fullmatch(r'Process "([^"]+)" (started|done)\.', line)
        if match:
            rows.append(list(match.groups()))
        elif line.startswith(GATE):
            require(line == GATE + ' ' + digest, 'wrong runtime gate ADF')
            rows.append(['Runtime gate', 'passed'])
        elif line == COMPLETE:
            rows.append(['Bitstream', 'complete'])
    require(rows == [['Report Timing', 'started'], ['Report Timing', 'done'], ['Runtime gate', 'passed'],
                     ['Generate Bitstream', 'started'], ['Generate Bitstream', 'done'], ['Bitstream', 'complete']],
            'fresh STA/gate/generation event order differs')
    return rows


def bit_header(data):
    require(len(data) == EXPECTED_BIT_BYTES, 'exact PG2L100H direct diagnostic programming length required')
    prefix = bytes.fromhex('00090ff00ff00ff00ff000') + b'PANGO MICROSYSTEMS, INC.\0\1'
    require(data.startswith(prefix), 'invalid native bit prefix')
    offset, fields = len(prefix), {}
    for tag, name in zip(b'abcdef', ('Design', 'Device', 'Date', 'Time', 'Generator', 'Version')):
        require(offset + 3 <= len(data) and data[offset] == tag, 'missing native bit header field')
        length = int.from_bytes(data[offset + 1:offset + 3], 'big')
        value = data[offset + 3:offset + 3 + length]
        require(length > 0 and len(value) == length and value[-1:] == b'\0' and b'\0' not in value[:-1], 'invalid native header string')
        fields[name] = value[:-1].decode('ascii')
        offset += 3 + length
    require(data[offset:offset + 3] == b'ghi' and len(data) > 1000000, 'truncated native payload')
    for k, v in {'Design': TARGET, 'Device': 'Logos2-PG2L100H--6-FBG676',
                 'Generator': 'Fabric Compiler', 'Version': '2023.2-SP3<154097>'}.items():
        require(fields[k] == v, 'wrong bit identity: ' + k)
    return fields


def verify_generation_evidence(work, text, digest, receipt, gate_proof):
    """Bind actual command/order, native BGR defaults and generation times."""
    work = Path(work)
    expected_command = ('gen_bit_stream -force_to_run -input_db_file ' + native_work(work / 'audited-final.adf')
                        + ' -scbv {High Voltage} -unused_io_status UNUSED')
    launches = [(m.start(), m.group(1).rstrip()) for m in re.finditer(r'(?m)^Executing : (gen_bit_stream .+)$', text)
                if not m.group(1).rstrip().endswith(' successfully.')]
    require(len(launches) == 1 and launches[0][1] == expected_command, 'native bit generation command differs')
    markers = list(re.finditer(r'(?m)^' + re.escape(GATE + ' ' + digest) + r'\s*$', text))
    starts = list(re.finditer(r'(?m)^Process "Generate Bitstream" started\.\s*$', text))
    require(len(markers) == len(starts) == 1 and markers[0].start() < launches[0][0] < starts[0].start(),
            'actual generation command must follow runtime gate and precede native start')
    report = (work / BGR).read_text(encoding='gb18030')
    require('Generating Programming File done.' in report, 'native programming report incomplete')
    flow = re.findall(r'(?m)^Flow Command:\s*(.+?)\s*$', report)
    base_command = ('gen_bit_stream -force_to_run -input_db_file {' +
                    native_work(work / 'audited-final.adf') + '} -scbv {High Voltage}')
    require(flow in ([base_command], [base_command + ' -unused_io_status UNUSED']), 'native BGR flow command differs')
    actual_input = re.findall(r'(?m)^\| Input\s*\|\s*(.*?)\s*$', report)
    require(actual_input == [native_work(work / 'audited-final.adf')], 'native BGR input role differs')
    output = re.findall(r'^The bitstream file is "([^"]+)"\s*$', report, re.M)
    require(output == [native_work(work / BIT)], 'native BGR output role differs')
    script = (work / 'bitstream.tcl').read_text(encoding='ascii')
    emitted = re.findall(r'(?m)^\s*(gen_bit_stream .+)$', script)
    expected_tcl = ('gen_bit_stream -force_to_run -input_db_file {' +
                    native_work(work / 'audited-final.adf') + '} -scbv {High Voltage} -unused_io_status UNUSED')
    require(emitted == [expected_tcl], 'bound Tcl generation controls differ')
    try:
        started, finished, checked = (datetime.fromisoformat(s) for s in
                                    (receipt['StartedUTC'], receipt['FinishedUTC'], gate_proof['CheckedUTC']))
    except (ValueError, TypeError, KeyError) as error:
        raise ValueError('valid execution/gate UTC timestamps required') from error
    require(all(t.tzinfo is not None and t.utcoffset() is not None for t in (started, finished, checked))
            and started <= checked <= finished, 'runtime gate is outside this execution window')
    bit_mtime = (work / BIT).stat().st_mtime
    gate_mtime = (work / 'pre-bit-audit.json').stat().st_mtime
    require(started.timestamp() <= gate_mtime <= bit_mtime <= finished.timestamp(),
            'gate/bit artifact timestamps do not follow this execution')
    return {'ActualGenerationCommand': expected_command, 'ActualCommandAfterGateBeforeNativeStart': True,
            'BGRInputAndOutputRolesVerified': True, 'BGRHighVoltageVerified': True,
            'NativeBGROmittedDefaultUnused': flow == [base_command], 'UnusedIOExplicitInTclAndStdout': True,
            'RuntimeGateWithinExecutionWindow': True, 'BitArtifactNotOlderThanGate': True}


def artifacts(work):
    return {p.relative_to(work).as_posix(): sha(p) for p in Path(work).rglob('*') if p.is_file()
            and p.suffix in ('.log', '.rtr', '.sbit', '.bgr', '.tcl')}


def verify(work):
    plan, context = validate(work)
    work = Path(work)
    receipt_sha = sha(work / 'execution-result.json')
    receipt = read(work / 'execution-result.json')
    require(receipt.get('Schema') == EXEC_SCHEMA and receipt.get('Target') == TARGET
            and receipt.get('PlanSHA256') == sha(work / 'bitstream-plan.json') and receipt.get('ExecutorSHA256') == sha(SELF)
            and receipt.get('Command') == plan['Command'] and receipt.get('FinalADFSHA256') == context['FinalADFSHA256']
            and receipt.get('ExitCode') == 0 and receipt.get('TimedOut') is False and not receipt.get('Error')
            and receipt.get('EDAExecuted') is True and receipt.get('HardwareAccessed') is False
            and receipt.get('StoppedForUnexpectedStage') is False and receipt.get('InputDrift') == []
            and receipt.get('Diagnostics') == [] and receipt.get('Cleanup', {}).get('Complete') is True,
            'unclean native direct bit execution')
    expected = artifacts(work)
    require(receipt['Artifacts'] == expected and {'stdout.log', 'stderr.log', REPORT, EXCEPTIONS, BIT, BGR, 'bitstream.tcl'} <= set(expected),
            'native bit artifact inventory differs')
    require(build.diagnostics(work) == [], 'native bit diagnostic failure')
    text = (work / 'stdout.log').read_text(encoding='gb18030', errors='replace')
    events = actual_events(text, context['FinalADFSHA256'])
    checks = compare_fresh(context, work / REPORT, work / EXCEPTIONS)
    proof = read(work / 'pre-bit-audit.json')
    gate_sha = sha(work / 'pre-bit-audit.json')
    generation = verify_generation_evidence(work, text, context['FinalADFSHA256'], receipt, proof)
    evidence = {n: sha(work / n) for n in ('bitstream-plan.json', 'audited-final.adf', 'bitstream.tcl', REPORT, EXCEPTIONS)}
    require(proof.get('Schema') == GATE_SCHEMA and proof.get('Target') == TARGET and proof.get('GatePassed') is True
            and proof.get('FinalADFSHA256') == context['FinalADFSHA256'] and proof['Checks'] == checks
            and proof['EvidenceSHA256'] == evidence, 'actual runtime gate differs')
    data = (work / BIT).read_bytes()
    header = bit_header(data)
    require(not drift(plan['InputSHA256']) and artifacts(work) == expected
            and sha(work / 'execution-result.json') == receipt_sha
            and sha(work / 'pre-bit-audit.json') == gate_sha, 'bit verification input/artifact drift')
    return {'Schema': 'hdmi-camera-direct-bitstream-verification-v1', 'Verified': True, 'Target': TARGET,
            'FinalADFSHA256': context['FinalADFSHA256'], 'Bitstream': {**ref(work / BIT), 'Bytes': len(data), 'Header': header},
            'FreshSTA': checks, 'ActualEvents': events, 'GenerationEvidence': generation, 'CheckedUTC': utc(),
            'EvidenceSHA256': {n: sha(work / n) for n in ('bitstream-plan.json', 'audited-final.adf', 'tool-snapshot.py',
                'execution-result.json', 'pre-bit-audit.json', *sorted(expected))},
            'HardwareAccessed': False, 'ExternalACAccepted': False, 'PixelsVerified': False, 'HardwareReleaseAllowed': False}


def execute(work):
    plan, context = validate(work)
    work = Path(work)
    build.paths.validate_repo_alias(ROOT,'P:/')
    require(os.name == 'nt' and {p.name for p in work.iterdir()} ==
            {'bitstream-plan.json', 'bitstream.tcl', 'audited-final.adf', 'tool-snapshot.py'}, 'fresh Windows bit stage required')
    watched = {**plan['InputSHA256'], **{str(p): sha(p) for p in work.iterdir()}}
    value = {'Schema': EXEC_SCHEMA, 'Target': TARGET, 'PlanSHA256': sha(work / 'bitstream-plan.json'),
             'ExecutorSHA256': sha(SELF), 'Command': plan['Command'], 'FinalADFSHA256': context['FinalADFSHA256'],
             'StartedUTC': utc(), 'EDAExecuted': False, 'HardwareAccessed': False, 'ExitCode': None,
             'TimedOut': False, 'StoppedForUnexpectedStage': False}
    write(work / 'execution-claim.json', value)
    process, start = None, time.monotonic()
    try:
        with (work / 'stdout.log').open('xb') as out, (work / 'stderr.log').open('xb') as err:
            process = subprocess.Popen(plan['Command'], cwd=work, stdout=out, stderr=err, shell=False,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            value.update(EDAExecuted=True, OwnedPID=process.pid)
            expected = [[s, e] for s in STAGES for e in ('started', 'done')]
            while process.poll() is None:
                left = plan['MaximumSeconds'] - (time.monotonic() - start)
                if left <= 0:
                    value['TimedOut'] = True
                    break
                try:
                    process.wait(timeout=min(3, left))
                except subprocess.TimeoutExpired:
                    pass
                current = build.events((work / 'stdout.log').read_text(encoding='gb18030', errors='replace'))
                if current != expected[:len(current)]:
                    value['StoppedForUnexpectedStage'] = True
                    break
    except BaseException as error:
        value['Error'] = type(error).__name__ + ': ' + str(error)
    finally:
        if process is not None and process.poll() is None:
            value['Cleanup'] = build.cleanup.stop_owned_tree(process, work, 'bounded direct bit generation')
        else:
            value['Cleanup'] = {'Complete': True, 'ParentExited': process is not None}
        value.update(ExitCode=process.poll() if process is not None else None, FinishedUTC=utc(),
                     ElapsedSeconds=round(time.monotonic() - start, 3), InputDrift=drift(watched),
                     Diagnostics=build.diagnostics(work), Artifacts=artifacts(work))
        write(work / 'execution-result.json', value)
    checked = verify(work)
    write(work / 'verification.json', checked)
    return checked


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    for name in ('prepare', 'validate', 'execute', 'verify', 'gate', 'audit-request'):
        mode.add_argument('--' + name, type=Path)
    p.add_argument('--request', type=Path)
    p.add_argument('--maximum-seconds', type=int, default=900)
    a = p.parse_args()
    if a.audit_request:
        c = audit_request(a.audit_request)
        print(json.dumps({'AuthorityPassed': True, 'FinalADFSHA256': c['FinalADFSHA256'], 'Inputs': len(c['Watched']), 'HardwareAccessed': False}))
    elif a.prepare:
        require(a.request is not None, '--prepare requires --request')
        value = prepare(a.request, a.prepare, a.maximum_seconds)
        print(json.dumps({'Prepared': True, 'Plan': str(Path(value['WorkDirectory']) / 'bitstream-plan.json')}))
    elif a.validate:
        validate(a.validate)
        print('{"Validated":true,"HardwareAccessed":false}')
    elif a.gate:
        value = gate(a.gate)
        print(GATE + ' ' + value['FinalADFSHA256'])
    else:
        print(json.dumps(execute(a.execute) if a.execute else verify(a.verify)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
