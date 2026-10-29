"""Synthetic CPU fixtures only: these files never certify an FPGA build."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import json
import os
import sys
import time
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import audit_hdmi30_build as tool


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) if isinstance(data, dict) else data, encoding='utf-8', newline='\n')
    return path


@pytest.fixture
def synthetic(tmp_path):
    project = tmp_path / 'distortion'
    work = project / 'build/board1080-timing/hdmi30-synthetic'
    alias = 'P:/distortion/build/board1080-timing/hdmi30-synthetic'
    names = [f'rtl/synthetic_{i}.v' for i in range(108)] + ['board/synthetic.fdc']
    for name in names:
        put(project / name, '// Synthetic CPU fixture only\n')
        put(work / 'compiled' / name, '// Synthetic CPU fixture only\n')
    for name in ('board/synthetic.rcf', tool.profile.MANIFEST, tool.profile.BASE):
        put(project / name, 'Synthetic CPU fixture only\n')
    roles = dict(Sources=names, SourceSHA256={n: tool.sha(project / n) for n in names},
        Constraint='board/synthetic.fdc', RouteConstraint='board/synthetic.rcf', ExplicitDesigns=names[:31],
        ConstraintSHA256={n: tool.sha(project / n) for n in ('board/synthetic.fdc', 'board/synthetic.rcf')},
        AuxiliarySHA256={n: tool.sha(project / n) for n in (tool.profile.MANIFEST, tool.profile.BASE)})
    inputs = {**roles['SourceSHA256'], **roles['ConstraintSHA256'], **roles['AuxiliarySHA256']}
    for module in (tool.profile.timing, tool.profile, tool.profile.edid):
        source = Path(module.__file__).resolve()
        name = source.relative_to(tool.PROJECT).as_posix()
        target = project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        inputs[name] = tool.sha(target)
    exe = put(project / 'synthetic-pds.exe', 'Synthetic: never executable')
    explicit = [alias + '/compiled/' + n for n in roles['ExplicitDesigns']]
    tcl = tool.profile.timing.make_tcl(explicit, 'P:/distortion/board/synthetic.fdc',
        'P:/distortion/board/synthetic.rcf', alias, alias + '/pre-sta-final.adf', 200)
    put(work / 'timing.tcl', tcl)
    now = time.time()
    iso = lambda seconds: datetime.fromtimestamp(seconds, timezone.utc).isoformat()
    command = [str(exe.resolve()), '-file', alias + '/timing.tcl', '-work_dir', alias, '-project_name', 'board1080_top']
    plan = dict(Synthetic=True, Schema='board1080-hdmi30-timing-preparation-v1', Manifest=tool.profile.MANIFEST,
        ProjectRoot=str(project), WorkDirectory=str(work), RepoAlias='P:/', AliasWorkDirectory=alias,
        HDMIEDIDProfileVerified=True, PreviousCandidateTimingReused=False, PreviousCandidateBitstreamReused=False,
        HardwareReleaseAllowed=False, TimingAccepted=False, HardwareAccessed=False, BitstreamRequested=False,
        PreparedUTC=iso(now-20), InputSHA256=inputs, EDAStageCommands=list(tool.STAGES),
        CompiledInputs=[dict(Source=n, OriginalSHA256=inputs[n], CompiledPath=alias+'/compiled/'+n,
                            CompiledSHA256=tool.sha(work/'compiled'/n)) for n in names],
        IncludeRewrites=[], ExplicitDesigns=explicit, PreSTAFinalDatabase=alias+'/pre-sta-final.adf',
        Tcl=dict(Path=alias+'/timing.tcl', SHA256=tool.sha(work/'timing.tcl')),
        PDS=dict(Executable=str(exe), ExecutableSHA256=tool.sha(exe), ExpectedVersion=tool.profile.timing.PDS_VERSION),
        CommandToRunSeparately=command)
    put(work / 'plan.json', plan)
    start = dict(Synthetic=True, Executable=str(exe), Arguments=command[1:], StartedUTC=iso(now-10))
    end = dict(Synthetic=True, StartedUTC=start['StartedUTC'], EndedUTC=iso(now+10), NativeReturnCode=0, HardwareAccessed=False)
    put(work / 'execution-start.json', start); put(work / 'execution-complete.json', end)
    for name in tool.ARTIFACTS:
        put(work / name, 'Synthetic CPU fixture only\n')
    console = ''.join('Executing : '+s+'\nExecuting : '+s+' successfully.\n' for s in tool.STAGES)
    put(work / 'native-console.log', console)
    put(work / 'run.log', '#Build: Fabric Compiler 2023.2-SP3, Build 154097, Synthetic CPU fixture\n')
    return project, work, plan, roles, start, end


def test_synthetic_execution_is_validated_without_writing_acceptance(synthetic):
    project, work, plan, roles, start, end = synthetic
    watched = {}
    assert tool.check_plan(project.resolve(), work.resolve(), roles, watched) == plan
    assert tool.check_execution(work, plan, watched) == (start, end)
    assert start['Synthetic'] is True
    assert not list(work.glob('*audit*.json'))


@pytest.mark.parametrize('mutation', ('exit', 'bool_exit', 'missing_complete', 'wrong_command', 'wrong_start',
    'missing_stage', 'duplicate_stage', 'stage_order', 'error', 'version', 'missing_snapshot', 'stale_snapshot', 'changed_snapshot'))
def test_bad_execution_evidence_rejected(synthetic, mutation):
    _, work, plan, _, start, end = synthetic
    if mutation == 'exit':
        end['NativeReturnCode'] = 1; put(work/'execution-complete.json', end)
    elif mutation == 'bool_exit':
        end['NativeReturnCode'] = False; put(work/'execution-complete.json', end)
    elif mutation == 'missing_complete': (work/'execution-complete.json').unlink()
    elif mutation == 'wrong_command':
        start['Arguments'][1] = 'P:/old/timing.tcl'; put(work/'execution-start.json', start)
    elif mutation == 'wrong_start':
        end['StartedUTC'] = '2000-01-01T00:00:00Z'; put(work/'execution-complete.json', end)
    elif mutation in ('missing_stage', 'duplicate_stage', 'stage_order', 'error'):
        log = (work/'native-console.log').read_text()
        if mutation == 'missing_stage': log = log.replace('Executing : dev_map successfully.\n', '')
        elif mutation == 'duplicate_stage': log += 'Executing : dev_map successfully.\n'
        elif mutation == 'stage_order': log = '\n'.join(reversed(log.splitlines()))
        else: log += '\nE: Synthetic failure\n'
        put(work/'native-console.log', log)
    elif mutation == 'version': put(work/'run.log', 'Synthetic wrong native version')
    elif mutation == 'missing_snapshot': (work/'pre-sta-final.adf').unlink()
    elif mutation == 'stale_snapshot': os.utime(work/'pre-sta-final.adf', (1, 1))
    else: put(work/'pre-sta-final.adf', 'Synthetic mismatching database')
    with pytest.raises(ValueError): tool.check_execution(work, plan, {})


@pytest.mark.parametrize('mutation', ('input_drift', 'copy_drift', 'tcl_drift', 'manifest', 'count', 'duplicate', 'unsafe'))
def test_bad_source_or_plan_binding_rejected(synthetic, mutation):
    project, work, plan, roles, _, _ = synthetic
    if mutation == 'input_drift': put(project/roles['Sources'][0], 'Synthetic changed source')
    elif mutation == 'copy_drift': put(work/'compiled'/roles['Sources'][0], 'Synthetic changed compiled copy')
    elif mutation == 'tcl_drift': put(work/'timing.tcl', 'Synthetic wrong Tcl')
    else:
        if mutation == 'manifest': plan['Manifest'] = tool.profile.BASE
        elif mutation == 'count': plan['InputSHA256'].pop(next(iter(plan['InputSHA256'])))
        elif mutation == 'duplicate': plan['CompiledInputs'][1] = copy.deepcopy(plan['CompiledInputs'][0])
        else: plan['PreviousCandidateTimingReused'] = True
        put(work/'plan.json', plan)
    with pytest.raises(ValueError): tool.check_plan(project.resolve(), work.resolve(), roles, {})


def add_table(root, name, columns, rows):
    table = ET.SubElement(root, 'table', id=name)
    headers = ET.SubElement(table, 'column_headers')
    for value in columns: ET.SubElement(headers, 'data').text = value
    for values in rows:
        row = ET.SubElement(table, 'row')
        for value in values: ET.SubElement(row, 'data').text = str(value)


@pytest.fixture
def synthetic_timing(tmp_path):
    work = tmp_path
    root = ET.Element('tables', Synthetic='true')
    add_table(root, 'report_timing_settings', ['Name','Value'], [('Part','PG2L100H-6FBG676'),('Top Module','board1080_top')])
    add_table(root, 'report_timing_clock_summary', ['Clock Name'], [('core',)])
    add_table(root, 'report_clock_interaction', ['Inter-Clock Constrains'], [('Timed(unsafe)',)])
    add_table(root, 'check_timing_summary', ['Check','Number of Issues'],
        [('no_clock',0),('no_input_delay',1),('no_output_delay',1),('unexpandable_clocks',0)])
    text = ('Synthetic CPU fixture only\n| Tool Version : Fabric Compiler (version 2023.2-SP3 <build 154097>)\n'
        '| Design       : board1080_top\n| Device       : PG2L100H\n| Speed Grade  : -6\n| Package      : FBG676\n'
        '\n\n\n\nClock Summary:\n core 8.0 Declared 1 1 source\nClock Groups:\n')
    for corner in ('slow','fast'):
        for kind in tool.native.KINDS:
            label = 'Minimum Pulse Width' if kind == 'mpw' else kind.title()
            failed = kind == 'recovery'
            nums = [-0.1 if failed else 0.1, -0.1 if failed else 0, int(failed), 10]
            text += f'{label} Summary({corner.title()} Corner):\n' + (' core ' if kind == 'mpw' else ' core core ') + ' '.join(map(str,nums)) + '\n'
            cols = (['Clock','WPWS','TPWS','Failing End Point','Total End Point'] if kind == 'mpw' else
                ['Launch Clock','Capture Clock','WHS(ns)' if kind in ('hold','removal') else 'WNS(ns)',
                 'THS(ns)' if kind in ('hold','removal') else 'TNS(ns)','Failing Endpoints','Total Endpoints'])
            add_table(root,'report_timing_'+corner+'_'+kind,cols,[(['core'] if kind == 'mpw' else ['core','core'])+nums])
    put(work/'report_timing/board1080_top.rtr', text)
    ET.ElementTree(root).write(work/'report_timing/rtr.db', encoding='utf-8')
    exceptions = ''.join(f'| Exception type  : set_false_path({kind})\n| {corner.title()} Corner\n' for corner in ('slow','fast') for kind in ('setup','hold','recovery','removal'))
    put(work/'report_timing/board1080_top_exception.rtr', exceptions)
    put(work/'native-console.log', "Synthetic CPU fixture only\n"
        "W: Timing-4086: Port 'synthetic_input' is not constrained, synthetic fixture\n"
        "W: Timing-4087: Port 'synthetic_output' is not constrained, synthetic fixture\n")
    return work


def test_all_ten_synthetic_tables_preserve_failure_and_unsafe_status(synthetic_timing):
    result = tool.timing_result(synthetic_timing)
    assert len(result['CornerTotals']) == 10
    assert result['CornerTotals']['slow_recovery']['FailingChecks'] == 1
    assert result['AllReportedNativeTimingChecksMet'] is False
    assert result['FullCoverageAndTimingGate'] is False
    assert result['CheckTimingCounts']['no_input_delay'] == 1


@pytest.mark.parametrize('mutation', ('xml_identity','rtr_identity','xml_mismatch','missing_table'))
def test_mismatched_or_incomplete_native_tables_rejected(synthetic_timing, mutation):
    work = synthetic_timing
    target = work/'report_timing/rtr.db'
    data = target.read_text()
    if mutation == 'xml_identity': data = data.replace('board1080_top','wrong_top')
    elif mutation == 'xml_mismatch': data = data.replace('<data>-0.1</data>','<data>0.2</data>',1)
    elif mutation == 'missing_table': data = data.replace('report_timing_fast_mpw','omitted_fast_mpw')
    else:
        target = work/'report_timing/board1080_top.rtr'
        data = target.read_text().replace('PG2L100H','PG2L200H')
    put(target,data)
    with pytest.raises(ValueError): tool.timing_result(work)


def test_existing_result_is_never_overwritten(tmp_path):
    result = put(tmp_path/'existing.json', {'Synthetic':True})
    before = result.read_bytes()
    with pytest.raises(ValueError, match='new'):
        tool.main(['--work-dir',str(tmp_path), '--output',str(result)])
    assert result.read_bytes() == before
