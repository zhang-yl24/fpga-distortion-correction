"""Synthetic CPU fixtures only; no test artifact certifies a real FPGA build."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import json
import os
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import audit_checked_build as tool
from test_audit_hdmi30_build import synthetic_timing  # Deliberately failing native-table fixture.


def put(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) if isinstance(data, dict) else data, encoding='utf-8', newline='\n')
    return path


@pytest.fixture
def synthetic(tmp_path, monkeypatch):
    project = tmp_path / 'distortion'
    work = project / 'build/board1080-timing/checked-synthetic'
    alias = 'P:/distortion/build/board1080-timing/checked-synthetic'
    original, header = tool.profile.INCLUDE_BINDINGS[tool.TOP]
    names = [tool.TOP, header, tool.profile.FDC] + [f'rtl/synthetic_{i}.v' for i in range(106)]
    for name in names:
        text = '// Synthetic CPU fixture only\n'
        if name == tool.TOP: text += chr(96) + f'include "{original}"\n'
        put(project / name, text)
        put(work / 'compiled' / name, text.replace(original, alias + '/compiled/' + header)
            if name == tool.TOP else text)
    rcf = 'board/synthetic.rcf'
    put(project / rcf, '# Synthetic CPU fixture only\n')
    put(project / tool.profile.MANIFEST, {'Synthetic': True})
    roles = dict(Sources=names, SourceSHA256={n: tool.sha(project / n) for n in names},
        Constraint=tool.profile.FDC, RouteConstraint=rcf, ExplicitDesigns=[tool.TOP] + names[3:33],
        ConstraintSHA256={n: tool.sha(project / n) for n in (tool.profile.FDC, rcf)},
        AuxiliarySHA256={tool.profile.MANIFEST: tool.sha(project / tool.profile.MANIFEST)})
    inputs = {**roles['SourceSHA256'], **roles['ConstraintSHA256'], **roles['AuxiliarySHA256']}
    monkeypatch.setattr(tool.profile, 'expected_inputs', lambda p, r: dict(inputs))
    exe = put(project / 'synthetic-pds.exe', 'Synthetic, never executable')
    explicit = [alias + '/compiled/' + n for n in roles['ExplicitDesigns']]
    tcl = tool.profile.timing.make_tcl(explicit, 'P:/distortion/' + tool.profile.FDC,
        'P:/distortion/' + rcf, alias, alias + '/pre-sta-final.adf', 200)
    put(work / 'timing.tcl', tcl)
    now = time.time()
    iso = lambda t: datetime.fromtimestamp(t, timezone.utc).isoformat()
    command = [str(exe.resolve()), '-file', alias + '/timing.tcl', '-work_dir', alias, '-project_name', 'board1080_top']
    plan = dict(Synthetic=True, Schema='board1080-checked-timing-preparation-v1', Manifest=tool.profile.MANIFEST,
        ProjectRoot=str(project), WorkDirectory=str(work), CheckedI2CProfileVerified=True,
        SCLDirectionOnlyConstraintChange=True, PreviousCandidateTimingReused=False,
        PreviousCandidateBitstreamReused=False, HardwareReleaseAllowed=False, PhysicalTimingReady=False,
        TimingAccepted=False, HardwareAccessed=False, BitstreamRequested=False, EDAExecuted=False,
        RepoAlias='P:/', AliasWorkDirectory=alias, PreparedUTC=iso(now-20), InputSHA256=inputs,
        EDAStageCommands=list(tool.common.STAGES), ExplicitDesigns=explicit,
        CompiledInputs=[dict(Source=n, OriginalSHA256=inputs[n], CompiledPath=alias+'/compiled/'+n,
                            CompiledSHA256=tool.sha(work/'compiled'/n)) for n in names],
        IncludeRewrites=[dict(Source=tool.TOP, OriginalInclude=original, CompiledInclude=alias+'/compiled/'+header,
                             Header=header, HeaderSHA256=inputs[header], ReplacementCount=1)],
        Constraints=dict(FDC=tool.profile.FDC, RCF=rcf, SHA256=roles['ConstraintSHA256']),
        PreSTAFinalDatabase=alias+'/pre-sta-final.adf', Tcl=dict(Path=alias+'/timing.tcl', SHA256=tool.sha(work/'timing.tcl')),
        PDS=dict(Executable=str(exe), ExecutableSHA256=tool.sha(exe), ExpectedVersion=tool.profile.timing.PDS_VERSION),
        CommandToRunSeparately=command)
    put(work / 'plan.json', plan)
    start = dict(Synthetic=True, Executable=str(exe), Arguments=command[1:], StartedUTC=iso(now-10))
    end = dict(Synthetic=True, StartedUTC=start['StartedUTC'], EndedUTC=iso(now+10), NativeReturnCode=0, HardwareAccessed=False)
    put(work / 'execution-start.json', start); put(work / 'execution-complete.json', end)
    for name in tool.common.ARTIFACTS: put(work / name, 'Synthetic CPU fixture only\n')
    put(work / 'native-console.log', ''.join('Executing : '+s+'\nExecuting : '+s+' successfully.\n' for s in tool.common.STAGES))
    put(work / 'run.log', '#Build: Fabric Compiler 2023.2-SP3, Build 154097, Synthetic CPU fixture\n')
    return project, work, plan, roles, start, end


def test_synthetic_plan_preserves_checked_include_transformation(synthetic):
    project, work, plan, roles, start, end = synthetic
    watched = {}
    assert tool.check_plan(project.resolve(), work.resolve(), roles, watched) == plan
    assert tool.common.check_execution(work, plan, watched) == (start, end)
    assert plan['Synthetic'] is True and len(plan['InputSHA256']) != 115
    assert not list(work.glob('*audit*.json'))


@pytest.mark.parametrize('mutation', ('input', 'copy', 'tcl', 'schema', 'manifest', 'missing_input',
    'duplicate_copy', 'include', 'old_fdc', 'unverified', 'timing_reuse'))
def test_wrong_checked_plan_or_input_rejected(synthetic, mutation):
    project, work, plan, roles, _, _ = synthetic
    if mutation == 'input': put(project/tool.TOP, '// Synthetic drift')
    elif mutation == 'copy': put(work/'compiled'/tool.TOP, '// Synthetic copy drift')
    elif mutation == 'tcl': put(work/'timing.tcl', '# Synthetic Tcl drift')
    else:
        if mutation == 'schema': plan['Schema'] = 'board1080-hdmi30-timing-preparation-v1'
        elif mutation == 'manifest': plan['Manifest'] = 'board/board1080-checked-sources.json'
        elif mutation == 'missing_input': plan['InputSHA256'] = dict(plan['InputSHA256']); plan['InputSHA256'].pop(tool.TOP)
        elif mutation == 'duplicate_copy': plan['CompiledInputs'][1] = copy.deepcopy(plan['CompiledInputs'][0])
        elif mutation == 'include': plan['IncludeRewrites'][0]['CompiledInclude'] = 'P:/old/header.vh'
        elif mutation == 'old_fdc': plan['Constraints']['FDC'] = tool.profile.BASE_FDC
        elif mutation == 'unverified': plan['SCLDirectionOnlyConstraintChange'] = False
        else: plan['PreviousCandidateTimingReused'] = True
        put(work/'plan.json', plan)
    with pytest.raises(ValueError): tool.check_plan(project.resolve(), work.resolve(), roles, {})


@pytest.mark.parametrize('mutation', ('exit', 'incomplete', 'stale_adf', 'missing_snapshot', 'mismatched_adf', 'identity'))
def test_shared_execution_validation_is_candidate_bound(synthetic, mutation):
    _, work, plan, _, start, end = synthetic
    if mutation == 'exit': end['NativeReturnCode'] = 1; put(work/'execution-complete.json', end)
    elif mutation == 'incomplete': put(work/'native-console.log', 'Synthetic unfinished build\n')
    elif mutation == 'stale_adf': os.utime(work/'place_route/board1080_top_pnr.adf', (1, 1))
    elif mutation == 'missing_snapshot': (work/'pre-sta-final.adf').unlink()
    elif mutation == 'mismatched_adf': put(work/'pre-sta-final.adf', 'Synthetic old ADF')
    else: start['Arguments'][1] = 'P:/old/timing.tcl'; put(work/'execution-start.json', start)
    with pytest.raises(ValueError): tool.common.check_execution(work, plan, {})


@pytest.fixture
def synthetic_pins(tmp_path):
    project, work = tmp_path/'distortion', tmp_path/'native'
    ports = {'hd_scl': 'INOUT', 'hd_sda': 'INOUT'}
    ports.update({f'{c}_in[{i}]':'INPUT' for c in 'rgb' for i in range(8)})
    ports.update({f'synthetic_{i}':'INPUT' for i in range(116)})
    top = 'module board1080_top(inout hd_scl,inout hd_sda,input [7:0] r_in,input [7:0] g_in,input [7:0] b_in,'
    top += ','.join('input synthetic_'+str(i) for i in range(116)) + '); endmodule\n'
    put(project/tool.TOP, '// Synthetic CPU fixture only\n'+top)
    fdc, pcf, prt = [], ['# Synthetic CPU fixture only'], []
    for i,(name,direction) in enumerate(ports.items()):
        loc = 'K22' if name == 'hd_scl' else 'K23' if name == 'hd_sda' else 'A'+str(i+1)
        attrs = dict(DIRECTION=direction, LOC=loc, VCCIO='3.3', STANDARD='LVCMOS33', DRIVE='4', SLEW='SLOW')
        fdc.extend('define_attribute {p:'+name+'} {PAP_IO_'+k+'} {'+v+'}' for k,v in attrs.items())
        pcf.append('def_port {'+name+'} '+' '.join(('IOSTANDARD' if k=='STANDARD' else k)+'='+v
            for k,v in attrs.items() if k!='DIRECTION'))
        suffix = '|||' if name in tool.common.pins.OMITTED_RGB565 else '|'+name+'|'+direction.lower()+'|YES'
        prt.append(loc+'|SYNTHETIC_SITE|BANKL4|SYNTHETIC_FUNCTION'+suffix)
    put(project/tool.profile.FDC, '# Synthetic CPU fixture only\n'+'\n'.join(fdc)+'\n')
    put(work/'device_map/board1080_top.pcf', '\n'.join(pcf)+'\n')
    put(work/'place_route/board1080_top_prr_route_optimize.prt', '\n'.join(prt)+'\n')
    return project, work, dict(Constraint=tool.profile.FDC)


def test_pin_direction_does_not_claim_physical_readback_or_pullup(synthetic_pins):
    result = tool.pin_result(*synthetic_pins)
    assert result['DeclaredPins'] == 142 and result['RoutedPins'] == 134
    assert result['HDMIControlPads']['hd_scl']['Direction'] == 'INOUT'
    assert result['SCLReadbackAndTristatePhysicalImplementationVerified'] is False
    assert result['ExternalSCLPullupVerified'] is False


@pytest.mark.parametrize('mutation', ('fdc_output', 'prt_output', 'all_output', 'extra_missing', 'wrong_bank', 'duplicate_loc', 'wrong_voltage'))
def test_invalid_checked_pin_evidence_rejected(synthetic_pins, mutation):
    project, work, roles = synthetic_pins
    if mutation == 'all_output':
        top = project/tool.TOP
        put(top, top.read_text().replace('inout hd_scl','output hd_scl'))
        fdc = project/tool.profile.FDC
        put(fdc, fdc.read_text().replace('{p:hd_scl} {PAP_IO_DIRECTION} {INOUT}',
                                       '{p:hd_scl} {PAP_IO_DIRECTION} {OUTPUT}'))
    if mutation in ('fdc_output','wrong_voltage'):
        path = project/tool.profile.FDC
        text = path.read_text()
        text = text.replace('{p:hd_scl} {PAP_IO_DIRECTION} {INOUT}', '{p:hd_scl} {PAP_IO_DIRECTION} {OUTPUT}') if mutation=='fdc_output' else text.replace('{p:hd_scl} {PAP_IO_VCCIO} {3.3}', '{p:hd_scl} {PAP_IO_VCCIO} {1.8}')
    elif mutation == 'duplicate_loc':
        path = work/'device_map/board1080_top.pcf'; text = path.read_text().replace('LOC=K23','LOC=K22')
    else:
        path = work/'place_route/board1080_top_prr_route_optimize.prt'; text = path.read_text()
        if mutation in ('prt_output','all_output'): text = text.replace('|hd_scl|inout|YES','|hd_scl|output|YES')
        elif mutation == 'extra_missing': text = text.replace('|synthetic_0|input|YES','|||')
        else: text = text.replace('K22|SYNTHETIC_SITE|BANKL4','K22|SYNTHETIC_SITE|BANKL3')
    put(path,text)
    with pytest.raises(ValueError): tool.pin_result(project, work, roles)


def test_shared_native_tables_keep_all_ten_and_preserve_failure(synthetic_timing):
    result = tool.common.timing_result(synthetic_timing)
    assert len(result['CornerTotals']) == 10
    assert result['CornerTotals']['slow_recovery']['FailingChecks'] == 1
    assert result['FullCoverageAndTimingGate'] is False


def test_existing_result_is_never_overwritten(tmp_path):
    path = put(tmp_path/'existing.json', {'Synthetic': True})
    before = path.read_bytes()
    with pytest.raises(ValueError, match='new'):
        tool.main(['--work-dir',str(tmp_path),'--output',str(path)])
    assert path.read_bytes() == before
