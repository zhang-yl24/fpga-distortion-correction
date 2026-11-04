"""Finite scheduler checks only; not new RTL/fault/physical acceptance."""
import numpy as np
import pytest

import miss_bulk_read_screen_c as bulk
from miss_lookahead_model_a import Replay


def variants(trace):
    return [bulk.replay(trace, False), bulk.replay(trace, True),
            bulk.replay(trace, False, snapshot=True), bulk.replay(trace, True, snapshot=True)]


@pytest.mark.parametrize('trace', [
    [(0, 0, 0, 0)], [(0, 0, 15, 15)], [(0, 256, 0, 256)],
    [(-1, 0, -1, 15)], [(-1, -1, -1, -1)],
    [(0, 0, 15, 15)] * 64, [(0, 0, 15, 15), (256, 256, 271, 271), (0, 0, 15, 15)],
])
def test_every_variant_preserves_direct_mapping_fill_hit_and_final_metadata(trace):
    values = variants(np.asarray(trace, dtype=np.int32))
    for key in ('FastQueries', 'SlowQueries', 'Fills', 'ValidNeighbourHits', 'InBoundsNeighbourSamples', 'FinalTagsSHA256'):
        assert len({v[key] for v in values}) == 1


def test_one_cold_block_bulk_saves_eleven_not_twelve_after_actual_check_penalty():
    a,b,s,c = variants(np.asarray([(0, 0, 0, 0)], dtype=np.int32))
    assert a['Fills'] == 1 and a['ValidNeighbourHits'] == 3
    assert a['DifferentialStateCycleTotal'] - b['DifferentialStateCycleTotal'] == 11
    assert a['DifferentialStateCycleTotal'] - s['DifferentialStateCycleTotal'] == 7
    assert a['DifferentialStateCycleTotal'] - c['DifferentialStateCycleTotal'] == 12
    assert c['GrossOldStateCyclesSkipped'] == 6 and c['AddedBulkCheckCycles'] == 1


def test_two_cold_blocks_pay_failed_check_before_last_fill_and_overlap_is_not_added_twice():
    a,b,s,c = variants(np.asarray([(0, 0, 15, 15)], dtype=np.int32))
    assert b['BulkSuccessQueries'] == 1 and b['BulkRejectedFillChecks'] == 1
    assert a['DifferentialStateCycleTotal'] - b['DifferentialStateCycleTotal'] == 2
    assert a['DifferentialStateCycleTotal'] - s['DifferentialStateCycleTotal'] == 6
    assert s['DifferentialStateCycleTotal'] == c['DifferentialStateCycleTotal']


def test_same_index_different_tags_never_use_bulk_and_preserve_saved_neighbour_order():
    a,b,s,c = variants(np.asarray([(0, 256, 0, 256)], dtype=np.int32))
    assert a['Fills'] == 4 and a['ValidNeighbourHits'] == 0
    assert b['BulkSuccessQueries'] == c['BulkSuccessQueries'] == 0
    assert b['BulkRejectedFillChecks'] == 3 and b['SameIndexDifferentTagChecks'] == 3
    assert a['DifferentialStateCycleTotal'] - b['DifferentialStateCycleTotal'] == -3


def test_actual_last_neighbour_miss_bypasses_bulk_check_entirely():
    a,b,s,c = variants(np.asarray([(-1,-1,-1,1)], dtype=np.int32))
    assert a['Fills']==1 and b['AddedBulkCheckCycles']==0
    assert a['DifferentialStateCycleTotal']==b['DifferentialStateCycleTotal']
    assert s['DifferentialStateCycleTotal']==c['DifferentialStateCycleTotal']


def test_deterministic_random_index_collisions_preserve_all_four_variant_semantics():
    rng = np.random.default_rng(20261104)
    trace = rng.integers(-1, 4096, size=(1000, 4), dtype=np.int32)
    trace[::5, 1] = trace[::5, 0]
    trace[::7, 2] = -1
    values = variants(trace)
    for key in ('FastQueries', 'SlowQueries', 'Fills', 'ValidNeighbourHits', 'FinalTagsSHA256'):
        assert len({v[key] for v in values}) == 1


@pytest.mark.parametrize('latency', [0, 1, 8, 40])
@pytest.mark.parametrize('phase', [0, 1, 4])
def test_demand_lookahead_preserves_one_owner_final_commit_and_protected_index(latency, phase):
    trace = np.asarray([(0, 0, 15, 15)] * 64 + [(256, 0, 256, 0), (-1, 1, -1, 16)], dtype=np.int32)
    a = Replay(latency, False, phase=phase).run(trace)
    b = Replay(latency, True, phase=phase).run(trace)
    for key in ('FastQueries', 'SlowQueries', 'Fills', 'RAMReadSamples', 'RAMWriteCommitCycles', 'TagPublications'):
        assert a[key] == b[key]
    assert b['MaximumOutstandingBursts'] == 1
    assert b['RAMWriteCommitCycles'] == 8 * b['Fills']
    assert b['TagPublications'] == b['Fills']
