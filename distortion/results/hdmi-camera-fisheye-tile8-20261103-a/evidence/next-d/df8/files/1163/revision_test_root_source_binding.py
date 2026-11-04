"""Independently reject source/index drift across the root candidate adapters."""
import copy
from pathlib import Path
import sys

import pytest

WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK.parents[1] / 'tools'))
import hdmi_camera_fisheye_tile8df8_build as build
import hdmi_camera_fisheye_tile8df8_native as native
import hdmi_camera_fisheye_tile8df8_protocol as protocol


def test_root_module_edges_and_exact_source_roles_select_only_this_candidate():
    assert native.build is protocol.build is build
    assert protocol.native is native
    assert build.WORK == WORK
    cache = 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v'
    engine = 'rtl/experimental/hdmi_camera_fisheye_engine_tile8df8.v'
    assert build.REQUIRED_MODULES['ddr_neighbour_cache_scatter16_rowpipe'] == cache
    assert build.REQUIRED_MODULES['hdmi_camera_fisheye_engine_tile8'] == engine
    assert build.REPLACEMENTS['rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v'] == cache
    assert build.REPLACEMENTS['rtl/experimental/pipeline_gamma_frame_engine_1080_scatter4.v'] == engine
    assert protocol.CONTRACTS['Engine']['Source'] == engine


def test_engine_bytes_change_only_explicit_index7_to_index8():
    old = build.ROOT / 'rtl/experimental/hdmi_camera_fisheye_engine_tile8.v'
    new = build.ROOT / build.REQUIRED_MODULES['hdmi_camera_fisheye_engine_tile8']
    original = old.read_bytes()
    assert original.count(b'.INDEX_BITS(7)') == 1
    assert new.read_bytes() == original.replace(b'.INDEX_BITS(7)', b'.INDEX_BITS(8)', 1)
    value = protocol.contract('Engine', new.read_text(encoding='utf-8-sig'))
    assert value['CompleteNormalizedSourceSHA256'] == protocol.CONTRACTS['Engine']['NormalizedSHA256']
    for replacement in ('.INDEX_BITS(9)', '.INDEX_BITS(7)', '.INDEX_BITS(10)'):
        with pytest.raises(ValueError, match='unreviewed complete source'):
            protocol.contract('Engine', new.read_text(encoding='utf-8-sig').replace('.INDEX_BITS(8)', replacement))


def test_existing_bank_and_engine_transformation_is_replayed_without_control_changes():
    watched = {}
    result = protocol.reviewed_candidate_changes(watched)
    assert result['Passed'] is True and result['SourceOnly'] is True
    assert len(result['BankAndEngineChanges']) == 2
    assert all(row['ExactNormalizedTransformationReplayed'] for row in result['BankAndEngineChanges'])
    assert all(build.sha(path) == digest for path, digest in watched.items())


def test_full110_source_names_and_directfill_difference_are_bound_to_frozen_c():
    names = build.source_names(build.read(build.ROOT / build.BASE_MANIFEST))
    assert len(names) == 110
    hashes = {name: build.sha(build.ROOT / name) for name in names if name != build.FDC}
    fdc = (build.ROOT / build.C_FDC).read_bytes()
    hashes[build.FDC] = build.digest(fdc)
    result = build.c_source_difference(names, hashes, fdc)
    assert result['RetainedSourceHashesEqual'] is True
    assert result['PhysicalProofInherited'] is False
    assert result['DirectFillCache'] is True and result['CacheIndexBits'] == 8
    assert result['CacheLogicalBytes'] == 65536 and result['ScatterCyclesPer256ByteFill'] == 0
    assert result['RegisteredIngressBeforeCacheRAM'] is True
    changed = copy.deepcopy(hashes)
    changed[build.MAPPER] = '0' * 64
    with pytest.raises(ValueError, match='retained C source changed'):
        build.c_source_difference(names, changed, fdc)


def test_actual_cache_unit_receipt_binds_current_cache_and_native_index8_case():
    path = WORK.with_name('hdmi-camera-fisheye-tile8df9-20261103-a') / 'cache-unit-a/simulation.json'
    receipt = build.read(path)
    cache = build.ROOT / build.REQUIRED_MODULES['ddr_neighbour_cache_scatter16_rowpipe']
    assert receipt['Passed'] is True and receipt['InputDrift'] == []
    assert receipt['HardwareAccessed'] is False and receipt['PDSAccessed'] is False
    assert receipt['FullFrameSimulated'] is False
    assert receipt['SourceSHA256'][str(cache)] == build.sha(cache)
    assert receipt['PostReceiveScatterCycles'] == 0 and receipt['SingleRegisteredBeatPerWrite'] is True
    case = receipt['Cases']['1920-i8']
    assert case['passed'] is True and case['index_bits'] == 8 and case['commits_per_fill'] == 8
    assert case['same_cycle_first_beats'] > 0 and case['delayed_first_beats'] > 0
    assert case['reset_before_last_commit'] > 0 and case['fault_cases'] == 6
    assert case['IndependentTrace']['ActualMatchesIndependentPixelOracle'] is True
