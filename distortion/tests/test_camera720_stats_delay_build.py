"""Exact isolated build preparation and bounded mocked native lifecycle."""
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import prepare_camera720_stats_delay_build as prep
import run_camera720_stats_delay_build as runner

SOURCE_PLAN = prep.WORK/'source-a/source-plan.json'


def test_fixed_profile_and_header_are_distinct_exact_sha():
    assert len(prep.HEADER_SHA) == len(prep.PROFILE_SHA) == 64
    assert prep.HEADER_SHA != prep.PROFILE_SHA


@pytest.mark.parametrize('maximum', [True, 0, 59, 1801, 999999])
def test_bound_cannot_be_disabled_or_expanded(maximum):
    with pytest.raises(ValueError, match='60..1800'):
        prep.recipe(SOURCE_PLAN, prep.SOURCE_SHA, prep.WORK/'unused-test', maximum)


def test_exact_reviewed_source_sha_required():
    with pytest.raises(ValueError, match='explicit frozen'):
        prep.recipe(SOURCE_PLAN, '0'*64, prep.WORK/'unused-test')


@pytest.mark.skipif(not SOURCE_PLAN.is_file(), reason='local isolated source fixture unavailable')
def test_actual_build_preparation_validation_and_native_injection_rejection():
    # Match the short production stage name; old Windows native paths are long.
    with tempfile.TemporaryDirectory(prefix='', dir=prep.WORK) as name:
        work = Path(name).resolve()
        assert work.parent == prep.WORK.resolve()
        work.rmdir()
        path = prep.prepare(SOURCE_PLAN, prep.SOURCE_SHA, work)
        with mock.patch.object(runner.subprocess, 'Popen') as popen:
            context = runner.validate_plan(path)
            popen.assert_not_called()
            plan = context['Plan']
            assert plan['Target'] == prep.TARGET
            assert plan['ExpectedLiteralPinCount'] == 129
            assert len(plan['ExplicitDesigns']) == 34
            assert plan['HeaderSHA256'] == prep.HEADER_SHA
            assert plan['SourcePreparation']['SHA256'] == prep.SOURCE_SHA
            assert not plan['HardwareReleaseAllowed'] and not plan['InheritedRoutedTiming']
            tcl = work/'timing.tcl'
            original = tcl.read_bytes()
            tcl.write_bytes(original + b'gen_bit_stream\n')
            with pytest.raises(ValueError, match='Tcl recipe drift'):
                runner.validate_plan(path)
            tcl.write_bytes(original)
            value = json.loads(path.read_text())
            value['CommandToRunSeparately'].append('-extra')
            path.write_text(json.dumps(value), encoding='utf-8')
            with pytest.raises(ValueError, match='deterministic recipe'):
                runner.validate_plan(path)
            popen.assert_not_called()


@pytest.mark.parametrize('field,value', [
    ('ProfileSHA256', '0'*64), ('AddedClockDomainCrossings', 1),
    ('StatusAvailable', True), ('UnderflowsAvailable', True),
    ('InheritedRoutedTiming', True), ('IDsAreBitstreamHashes', True),
    ('CaptureControlDelayPS', 0), ('CaptureControlDelayLanes', 1), ('CaptureDataDelayLanes', 10),
    ('MonitorInputPath', 'delayed'), ('SensorRegisterSettingsChanged', True), ('PixelClockOrFrameProcessingChanged', True),
])
def test_source_contract_cannot_add_cross_domain_status_or_reuse_acceptance(field, value):
    plan = {'UARTPin': dict(prep.source.UART_ATTRIBUTES)}
    manifest = {'Target': prep.TARGET,
        'SourceSHA256': {prep.HEADER: prep.HEADER_SHA, prep.source.STATS: prep.source.STATS_SHA, prep.source.CONTROL_DELAY: prep.source.CONTROL_DELAY_SHA},
        'ProfileSHA256': prep.PROFILE_SHA, 'AddedSources': [prep.source.STATS, prep.source.UART, prep.source.CONTROL_DELAY],
        'CaptureControlDelayPS':1500, 'CaptureControlDelayLanes':2, 'CaptureDataDelayLanes':8,
        'MonitorInputPath':'raw controls and raw pixel clock; monitor has no data port',
        'SensorRegisterSettingsChanged':False, 'PixelClockOrFrameProcessingChanged':False,
        'CounterDomain': 'core_clk', 'CounterReset': 'core_reset[1]', 'AddedClockDomainCrossings': 0,
        'StatusAvailable': False, 'UnderflowsAvailable': False, 'IDsAreBitstreamHashes': False,
        'InheritedRoutedTiming': False, 'HardwareReleaseAllowed': False, 'OpticalCorrectionAccepted': False}
    manifest[field] = value
    with pytest.raises(ValueError):
        prep.fixed_source_contract(plan, manifest)


def mock_context(work):
    watched_file = work/'source.txt'
    watched_file.write_text('bound source')
    return {'Plan': {'CommandToRunSeparately': ['INERT-NOT-EXECUTED'],
                     'ExpectedActualStages': prep.STAGES},
            'PlanPath': work/'plan.json', 'PlanSHA256': '1'*64,
            'Work': work, 'MaximumSeconds': 60,
            'Watched': {watched_file: prep.sha(watched_file)}}


class FakeProcess:
    pid = 987654321

    def __init__(self, work, *, critical=False, wrong_stage=False, drift=False):
        events = ''.join(f'Process "{s}" {e}.\n' for s in prep.STAGES for e in ('started', 'done'))
        if wrong_stage:
            events = 'Process "Generate Bitstream" started.\n'
        (work/'execution-stdout.log').write_text(events)
        (work/'native.log').write_text('C:Sdm-3003 actual warning retained\n' if critical else '')
        if drift:
            (work/'source.txt').write_text('changed')
        (work/'pre-sta-final.adf').write_bytes(b'SAME-ADF')
        final = work/'place_route'/(prep.TARGET+'_pnr.adf')
        final.parent.mkdir()
        final.write_bytes(b'SAME-ADF')

    def poll(self):
        return 0


@pytest.mark.parametrize('case,passed', [('clean', True), ('critical', False), ('wrong_stage', False), ('drift', False)])
@pytest.mark.skipif(os.name != 'nt', reason='native lifecycle supports Windows only; no platform spoofing')
def test_native_exit_zero_does_not_override_diagnostics_stage_or_source_drift(tmp_path, case, passed):
    context = mock_context(tmp_path)
    fake = lambda *a, **k: FakeProcess(tmp_path, critical=case == 'critical', wrong_stage=case == 'wrong_stage', drift=case == 'drift')
    with mock.patch.object(runner, 'validate_plan', return_value=context), mock.patch.object(runner.subprocess, 'Popen', side_effect=fake):
        value = runner.execute(tmp_path/'plan.json')
    assert value['ExecutionCompletedWithoutError'] is passed
    assert value['HardwareReleaseAllowed'] is False and value['BitstreamRequested'] is False
    if case == 'critical':
        assert value['Diagnostics'] == ['native.log: C:Sdm-3003 actual warning retained']


def test_validation_failure_cannot_start_native():
    with mock.patch.object(runner, 'validate_plan', side_effect=ValueError('source drift')), mock.patch.object(runner.subprocess, 'Popen') as popen:
        with pytest.raises(ValueError, match='source drift'):
            runner.execute(Path('plan.json'))
        popen.assert_not_called()
