"""Only the new actual direct-fill counters can authorize this candidate."""
import copy
import importlib.util
import json
from pathlib import Path
import sys

import pytest

WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK.parents[1] / 'tools'))
import hdmi_camera_fisheye_tile8df8v3_bitstream as bit

spec = importlib.util.spec_from_file_location('df9_release_fixture_owner',
                                             WORK / 'physical-release-tests-v3-a/release_test_fill8_release.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
simulations = owner.simulations


@pytest.mark.parametrize('field', ['DirectFillCache', 'CacheIndexBits', 'ScatterCyclesPerFill',
                                  'CacheRAMWriteCyclesPerFill'])
@pytest.mark.parametrize('mutation', ['missing', 'incorrect'])
def test_directfill_identity_and_index_are_mandatory(simulations, field, mutation):
    evidence = simulations.values['SystemSimulation']
    if mutation == 'missing':
        del evidence[field]
    else:
        evidence[field] = {'DirectFillCache': False, 'CacheIndexBits': 9,
                           'ScatterCyclesPerFill': 8, 'CacheRAMWriteCyclesPerFill': 16}[field]
    simulations.paths['SystemSimulation'].write_text(json.dumps(evidence))
    with pytest.raises(ValueError, match='direct-fill INDEX8'):
        bit.bind_simulation('SystemSimulation', simulations.paths['SystemSimulation'], simulations.plan, {})


@pytest.mark.parametrize('field', ['fills', 'scatter_cycles', 'cache_ram_write_cycles', 'cache_fill_valid_commits'])
@pytest.mark.parametrize('invalid', [None, True, -1, 0.0, '', '-1', '1.0', '+1', ' 1', '01'])
def test_perframe_counts_are_canonical_real_nonnegative_counters(field, invalid):
    row = {'fills': '3', 'scatter_cycles': '0', 'cache_ram_write_cycles': '24', 'cache_fill_valid_commits': '3'}
    frames = [dict(row), dict(row)]
    frames[0][field] = invalid
    with pytest.raises(ValueError):
        bit.directfill_frame_counts(frames)


@pytest.mark.parametrize('frame_index', [0, 1])
@pytest.mark.parametrize('field,value', [('scatter_cycles', '24'), ('cache_ram_write_cycles', '23'),
                                       ('cache_ram_write_cycles', '25'), ('cache_fill_valid_commits', '2'),
                                       ('cache_fill_valid_commits', '4')])
def test_each_frame_must_publish_only_complete_direct_writes(frame_index, field, value):
    row = {'fills': '3', 'scatter_cycles': '0', 'cache_ram_write_cycles': '24', 'cache_fill_valid_commits': '3'}
    frames = [dict(row), dict(row)]
    frames[frame_index][field] = value
    with pytest.raises(ValueError, match='eight RAM writes'):
        bit.directfill_frame_counts(frames)


def test_both_int_and_parsed_decimal_string_counter_rows_are_retained():
    row = {'fills': 3, 'scatter_cycles': 0, 'cache_ram_write_cycles': 24, 'cache_fill_valid_commits': 3}
    frames = [row, {key: str(value) for key, value in row.items()}]
    saved = copy.deepcopy(frames)
    bit.directfill_frame_counts(frames)
    assert frames == saved


def test_no_prior_schema_or_candidate_cache_is_treated_as_new_identity():
    assert bit.PROOF_SCHEMA == 'hdmi-camera-fisheye-tile8df8v3-final-physical-proof-v1'
    assert bit.REQUEST_SCHEMA == 'hdmi-camera-fisheye-tile8df8v3-bitstream-request-v1'
    assert bit.SIMULATIONS['SystemSimulation'] == 'run_hdmi_camera_fisheye_tile8df8_system_sim'
    assert bit.build.REQUIRED_MODULES['ddr_neighbour_cache_scatter16_rowpipe'] == \
        'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v'
    assert bit.build.REQUIRED_MODULES['hdmi_camera_fisheye_engine_tile8'] == \
        'rtl/experimental/hdmi_camera_fisheye_engine_tile8df8.v'
