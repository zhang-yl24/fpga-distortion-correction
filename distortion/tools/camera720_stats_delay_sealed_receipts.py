"""Exact derived receipt checks using one explicit fully audited source seal.

Only repeated upstream route parsing is replaced by its verified byte closure.
Actual native stages, logs, Tcl, artifact inventory and fresh outputs stay exact.
"""
import json
from pathlib import Path
import camera720_stats_delay_fast_derived as fast
original=fast.original
physical,inspect,prep=fast.physical,fast.inspect,fast.prep
require,sha=fast.require,fast.sha
canonical,drift=inspect.canonical,inspect.drift
scan_diagnostics,native_netlist_valid=inspect.scan_diagnostics,inspect.native_netlist_valid
diagnostic=inspect.diagnostic
SCHEMA=original.SCHEMA
MARKER=original.MARKER
SELF=Path(__file__).resolve()


def bind_receipt(path,authority,authority_sha):
    """Rebind a finished read-only inspection for downstream CPU audits.

    Unlike validate_prepared this permits generated artifacts, but every
    original input, stage command and artifact is checked against the receipt.
    Neither this function nor the receipt approves a timing exception.
    """
    path = canonical(path, prep.WORK)
    work = prep.work_path(path.parent)
    require(path.name == 'result.json', 'exact finished inspection result required')
    value = json.loads(path.read_text(encoding='utf-8'))
    require(value.get('Schema') == SCHEMA and value.get('Target') == prep.TARGET, 'wrong calibrated derived inspection identity')
    expected,tcl,watched = fast.recipe(authority,authority_sha,work,
                                value['Mode'],value['QueryBody'],value['MaximumSeconds'])
    runtime_inputs=dict(watched)
    initial_files={'input.adf','stage.tcl','executor-snapshot.py','stage-plan.json'}
    if value['Mode']!='export':initial_files.add('dummy.v')
    for name in initial_files:physical.add(runtime_inputs,work/name)
    fast_fields={'ExecutionProvider','SourceAuthority','SealedValidationClosure'}
    if fast_fields & set(value):
        require(fast_fields <= set(value) and value['ExecutionProvider']==fast.ref(fast.SELF)
            and value['SourceAuthority']=={'Path':str(Path(authority).resolve()),'SHA256':authority_sha}
            and value['SealedValidationClosure']=={str(p):h for p,h in runtime_inputs.items()},
            'sealed native execution provider or runtime closure differs')
    stage_path = canonical(work/'stage-plan.json', work)
    stage = json.loads(stage_path.read_text(encoding='utf-8'))
    require(set(stage) == set(expected)|{'PreparedUTC'} and isinstance(stage['PreparedUTC'], str)
            and stage['PreparedUTC'] and {k:v for k,v in stage.items() if k!='PreparedUTC'} == expected,
            'finished inspection stage differs from exact recipe')
    require(all(value.get(k) == v for k,v in stage.items()) and value.get('StagePlanSHA256') == sha(stage_path),
            'finished inspection receipt differs from its stage plan')
    require(value.get('EDAExecuted') is True and value.get('ExecutionPassed') is True
            and value.get('ExitCode') == 0 and value.get('TimedOut') is False
            and value.get('StoppedForUnexpectedStage') is False and not value.get('Error')
            and value.get('InputDrift') == [] and value.get('Diagnostics') == []
            and value.get('CompletionMarker') is True and value.get('InputADFUnchanged') is True
            and value.get('Cleanup', {}).get('Complete') is True, 'finished inspection was not clean')
    for flag in ('HardwareAccessed', 'BitstreamRequested', 'TimingAccepted',
                 'HardwareReleaseAllowed', 'OpticalCorrectionAccepted'):
        require(value.get(flag) is False, 'finished inspection exceeds read-only scope: '+flag)
    require((work/'stage.tcl').read_bytes() == tcl.encode('ascii')
            and sha(work/'executor-snapshot.py') == sha(original.SELF)
            and sha(work/'input.adf') == value['SourceADFSHA256'], 'finished inspection input copy drift')
    if value['Mode'] != 'export':
        require((work/'dummy.v').read_bytes() == b'module physical_dummy(input a, output y); assign y=a; endmodule\n',
                'finished query dummy context drift')
    require(inspect.timing_report(work,value['Mode']) is not None
            and value.get('TimingReport')==inspect.timing_report(work,value['Mode']),
            'fresh native current-target timing report missing or changed')
    stages = ['Report Timing', 'Generate Netlist'] if value['Mode']=='export' else []
    events = [[s,e] for s in stages for e in ('started','done')]
    log = (work/'stdout.log').read_text(encoding='gb18030', errors='replace')
    require(value['ExpectedActualStages'] == stages and value.get('ActualEvents') == events
            and [list(item) for item in diagnostic.stage_events(log)] == events and MARKER in log,
            'finished native stages or completion marker differ')
    artifacts = value.get('Artifacts')
    require(isinstance(artifacts, dict) and {'stage.tcl', 'stdout.log', 'stderr.log'} <= set(artifacts),
            'finished native artifact bindings missing')
    actual = {p.relative_to(work).as_posix() for p in work.rglob('*') if p.is_file()
              and p.suffix in ('.tcl', '.log', '.rtr', '.v', '.gnr', '.txt', '.fdc')}
    require(actual == set(artifacts), 'finished native artifact inventory differs')
    require(scan_diagnostics(work) == [], 'finished native critical/error diagnostics present')
    for name, digest in artifacts.items():
        artifact = canonical(work/name, work)
        require(sha(artifact) == digest, 'finished native artifact drift: '+name)
        watched[artifact] = digest
    if value['Mode'] == 'export':
        netlist = canonical(work/'generate_netlist'/(prep.TARGET+'_sim.v'), work)
        require(native_netlist_valid(netlist) and value.get('NativeNetlistWithFFloc') is True and value.get('Netlist') == {
            'Path': str(netlist), 'SHA256': sha(netlist), 'Bytes': netlist.stat().st_size}, 'native placed export binding differs')
    for item in (path, stage_path, work/'executor-snapshot.py', work/'input.adf'):
        watched[item] = sha(item)
    require(not drift(watched), 'finished inspection input or artifact drift')
    physical.add(watched,SELF)
    return value, watched


