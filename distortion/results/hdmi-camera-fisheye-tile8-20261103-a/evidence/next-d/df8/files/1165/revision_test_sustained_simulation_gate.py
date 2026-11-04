"""CPU fixtures for the mandatory separate sustained public binding.

These tests do not run HDL. Actual saved HDL evidence is independently checked
by the selected sustained provider when the release/freeze gate is invoked.
"""
import copy
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK.parents[1] / 'tools'))
import hdmi_camera_fisheye_tile8df8v2_bitstream as bit


@pytest.fixture
def sustained(tmp_path, monkeypatch):
    root = tmp_path / 'candidate'
    work = root / 'work/selected'
    path = work / 'system-sustained-native-a/simulation.json'
    path.parent.mkdir(parents=True)
    monkeypatch.setattr(bit, 'ROOT', root)
    monkeypatch.setattr(bit, 'WORK', work)
    production = ('rtl/selected.v',)
    headers = ('rtl/selected.vh',)
    sources = {}
    plan = {'InputSHA256': {}, 'PreparedSHA256': {}, 'CompiledInputs': []}
    watched = {}
    for name in (*production, *headers):
        original = root / name
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_text('source fixture ' + name)
        compiled = work / 'build-a/compiled' / name
        compiled.parent.mkdir(parents=True, exist_ok=True)
        compiled.write_text('prepared fixture ' + name)
        sources[name] = bit.sha(original)
        plan['InputSHA256'][str(original)] = bit.sha(original)
        plan['PreparedSHA256'][str(compiled)] = bit.sha(compiled)
        plan['CompiledInputs'].append({'Source': name, 'OriginalSHA256': bit.sha(original),
                                      'CompiledPath': str(compiled), 'CompiledSHA256': bit.sha(compiled)})
        watched[original] = bit.sha(original)
    artifact = path.parent / 'actual-checked.csv'
    artifact.write_text('bound provider evidence fixture')
    watched[artifact] = bit.sha(artifact)
    summary = {'passed': True, 'frames_input': 16, 'frames_committed': 4, 'frames_processed': 4,
               'frames_published': 4, 'frames_unique_scanned': 4, 'unique_scanned_pixels': 8294400,
               'source_beats': 518400, 'result_beats': 518400, 'output_underflows': 0,
               'output_crc_mismatches': 0, 'dropped_frames': 0, 'overflow_frames': 0,
               'final_drain': True, 'key_toggles': 0, 'mode_changes_while_processing': 0, 'frame_mode_latches': 4,
               **{k: 2 for k in ('aw_stall', 'w_stall', 'physical_ar_stall',
                                'read_contention', 'write_contention', 'no_free_frames')}}
    frames = []
    metrics = []
    for index in range(4):
        frames.append({k: str(v) for k, v in {
            'frame_id': index + 1, 'input_source_index': index, 'fills': 3, 'scatter_cycles': 0,
            'cache_ram_write_cycles': 24, 'cache_fill_valid_commits': 3, 'input_pixels': 2073600,
            'source_beats': 129600, 'result_beats': 129600, 'commits': 1, 'releases': 1,
            'publishes': 1, 'unique_scans': 1, 'hardware_process_cycles': 100,
            'future_capture_write_overlap_cycles': 1}.items()})
        metrics.append({k: str(v) for k, v in {'frame_id': index + 1, 'corrected': 1,
            'coordinates_issued': 2073600, 'scatter_cycles': 0, 'cache_ram_write_cycles': 24,
            'cache_fill_valid_commits': 3, 'hardware_process_cycles': 100}.items()})
    value = {'Schema': 'hdmi-camera-fisheye-tile8df8-sustained-simulation-v1', 'Mode': 'native',
             'Passed': True, 'FunctionalPassed': True, 'ActualDERGBScanned': True,
             'HardwareAccessed': False, 'PDSAccessed': False, 'InputDrift': [],
             'SourceFrames': 16, 'AcceptedCompleteFrames': 4, 'DDRFirstBeatLatencyCycles': 40,
             'AdmissionDisabledOnlyAfterCompleteSources': 4, 'CacheIndexBits': 8,
             'ScatterCyclesPerFill': 0, 'CacheRAMWriteCyclesPerFill': 8, 'InputClockHz': 148500000,
             'OutputClockHz': 74250000, 'SystemClockHz': 125000000, 'ContinuousUnthrottledInput': True,
             'ActualPixelSamplerInstantiated': True, 'DirectFillCache': True, 'CacheKind': 'directfill',
             'InputDDRPreloaded': False, 'RealOutputAsyncFIFO': True, 'CorrectedCoordinatesTiled8x8': True,
             'ActualDDRReadContentionExercised': True, 'ActualDDRWriteContentionExercised': True,
             'FutureSourceWriteOverlapCycles': 4, 'Summary': summary, 'Frames': frames,
             'PerformanceBreakdown': metrics, 'SourceSHA256': sources,
             'Fixture': {'Width': 1920, 'Height': 1080, 'InputSourceFrames': 16,
                         'Frames': [{'Corrected': True} for _ in range(3)]}}
    for field, module in [('CandidateEngine', 'hdmi_camera_fisheye_engine_tile8'),
                           ('CandidateWriter', 'ddr_adaptive_result_writer_dualstripe'),
                           ('CandidateCache', 'ddr_neighbour_cache_scatter16_rowpipe'),
                           ('CandidateArbiter', 'ddr_read_arbiter')]:
        value[field] = bit.build.REQUIRED_MODULES[module]
    name = 'run_hdmi_camera_fisheye_tile8df8_sustained_sim'
    provider = ModuleType(name)
    provider.__file__ = str(bit.SELF.with_name(name + '.py'))
    provider.BENCH = 'tests/selected-bench.sv'
    provider.closure = lambda: ((*production, provider.BENCH), headers, (), {})
    provider.verify = lambda source: (json.loads(Path(source).read_text()), dict(watched))
    monkeypatch.setitem(sys.modules, name, provider)
    save = lambda: path.write_text(json.dumps(value))
    save()
    return SimpleNamespace(value=value, plan=plan, path=path, save=save,
                           provider=provider, artifact=artifact, watched=watched)


def test_selected_native_stress_binds_all_provider_inputs_and_actual_build_snapshots(sustained):
    watched = {}
    result = bit.bind_sustained(sustained.plan, watched)
    assert result == sustained.value
    assert watched[str(sustained.path)] == bit.sha(sustained.path)
    assert watched[str(sustained.artifact)] == bit.sha(sustained.artifact)
    assert watched[str(Path(sustained.provider.__file__))] == bit.sha(sustained.provider.__file__)
    for row in sustained.plan['CompiledInputs']:
        assert watched[row['CompiledPath']] == row['CompiledSHA256']


def test_missing_selected_stress_receipt_is_never_optional(sustained):
    sustained.path.unlink()
    with pytest.raises(FileNotFoundError):
        bit.bind_sustained(sustained.plan, {})


def test_stored_stress_receipt_cannot_differ_from_verified_value(sustained):
    old = copy.deepcopy(sustained.value)
    sustained.provider.verify = lambda path: (old, dict(sustained.watched))
    sustained.value['FutureSourceWriteOverlapCycles'] += 1
    sustained.save()
    with pytest.raises(ValueError, match='completed selected native sustained'):
        bit.bind_sustained(sustained.plan, {})


@pytest.mark.parametrize('field,wrong', [
    ('Mode', 'small'), ('Schema', 'prior-schema'), ('SourceFrames', 8), ('AcceptedCompleteFrames', 3),
    ('DDRFirstBeatLatencyCycles', 39), ('CacheIndexBits', 9), ('ScatterCyclesPerFill', 8),
    ('CacheRAMWriteCyclesPerFill', 7), ('ContinuousUnthrottledInput', False), ('DirectFillCache', False),
    ('InputDDRPreloaded', True), ('FunctionalPassed', False), ('HardwareAccessed', True),
    ('FutureSourceWriteOverlapCycles', 0), ('FutureSourceWriteOverlapCycles', 5),
    ('ActualDDRReadContentionExercised', False), ('ActualDDRWriteContentionExercised', False),
    ('CandidateEngine', 'prior-engine.v')])
@pytest.mark.parametrize('missing', [False, True])
def test_actual_stress_identity_and_derived_fields_are_mandatory(sustained, field, wrong, missing):
    if missing:
        del sustained.value[field]
    else:
        sustained.value[field] = wrong
    sustained.save()
    with pytest.raises(ValueError):
        bit.bind_sustained(sustained.plan, {})


@pytest.mark.parametrize('field', ['read_contention', 'write_contention', 'no_free_frames',
                                  'aw_stall', 'w_stall', 'physical_ar_stall'])
@pytest.mark.parametrize('bad', [0, True, -1, '2'])
def test_actual_dual_client_contention_and_ungranted_sources_must_be_observed(sustained, field, bad):
    sustained.value['Summary'][field] = bad
    sustained.save()
    with pytest.raises(ValueError, match='contention'):
        bit.bind_sustained(sustained.plan, {})


@pytest.mark.parametrize('mutation', ['only-three', 'duplicate-id', 'unordered-source', 'raw-frame',
                                     'scatter', 'short-write', 'early-valid', 'no-overlap', 'no-drain'])
def test_four_unique_corrected_ids_complete_writes_overlap_and_drain_are_required(sustained, mutation):
    value = sustained.value
    if mutation == 'only-three':
        value['Frames'].pop()
        value['PerformanceBreakdown'].pop()
    elif mutation == 'duplicate-id':
        value['Frames'][3]['frame_id'] = '3'
    elif mutation == 'unordered-source':
        value['Frames'][3]['input_source_index'] = '1'
    elif mutation == 'raw-frame':
        value['PerformanceBreakdown'][2]['corrected'] = '0'
    elif mutation == 'scatter':
        value['Frames'][0]['scatter_cycles'] = '1'
    elif mutation == 'short-write':
        value['Frames'][2]['cache_ram_write_cycles'] = '23'
    elif mutation == 'early-valid':
        value['Frames'][1]['cache_fill_valid_commits'] = '4'
    elif mutation == 'no-overlap':
        for row in value['Frames']:
            row['future_capture_write_overlap_cycles'] = '0'
        value['FutureSourceWriteOverlapCycles'] = 0
    else:
        value['Summary']['final_drain'] = False
    sustained.save()
    with pytest.raises(ValueError):
        bit.bind_sustained(sustained.plan, {})


@pytest.mark.parametrize('field', ['fills', 'scatter_cycles', 'cache_ram_write_cycles',
                                  'cache_fill_valid_commits', 'frame_id', 'future_capture_write_overlap_cycles'])
@pytest.mark.parametrize('bad', [True, -1, '', '01', ' 1', 1.0])
def test_sustained_actual_counters_reject_noncanonical_values(sustained, field, bad):
    sustained.value['Frames'][0][field] = bad
    sustained.save()
    with pytest.raises(ValueError):
        bit.bind_sustained(sustained.plan, {})


@pytest.mark.parametrize('mutation', ['source-sha', 'original-sha', 'prepared-sha', 'compiled-bytes', 'missing-row'])
def test_every_executed_header_and_production_file_must_match_the_actual_build(sustained, mutation):
    row = sustained.plan['CompiledInputs'][1]
    if mutation == 'source-sha':
        sustained.value['SourceSHA256'][row['Source']] = '0' * 64
    elif mutation == 'original-sha':
        row['OriginalSHA256'] = '0' * 64
    elif mutation == 'prepared-sha':
        sustained.plan['PreparedSHA256'][row['CompiledPath']] = '0' * 64
    elif mutation == 'compiled-bytes':
        Path(row['CompiledPath']).write_text('tampered prepared header')
    else:
        sustained.plan['CompiledInputs'].pop()
    sustained.save()
    with pytest.raises(ValueError, match='production RTL/header'):
        bit.bind_sustained(sustained.plan, {})


def test_request_remains_exactly_seven_fields_and_stress_is_a_separate_gate():
    assert bit.FIELDS == {'Schema', 'Target', 'PhysicalProof', 'MapperSimulation',
                          'SystemSimulation', 'IOSimulation', 'Profile'}
    assert set(bit.SIMULATIONS) == {'MapperSimulation', 'SystemSimulation', 'IOSimulation'}
