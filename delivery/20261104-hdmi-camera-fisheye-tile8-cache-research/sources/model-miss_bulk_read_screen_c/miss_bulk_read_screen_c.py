"""Exact frozen native address replay: existing slow path versus post-fill bulk.

No prototype, provider, EDA, simulator or hardware is invoked. The only changed
scheduler rule is the root's proposed last-commit -> BULK_CHECK -> BULK_LOAD ->
BULK_PICK -> RESULT fast return, otherwise original LOAD with one check-cycle
penalty. Cache capacity/mapping/replacement/DDR requests remain unchanged.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import collections
import csv
import hashlib
import json
import re
import time

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOT = REPO / 'distortion'
TRACE = ROOT / 'work/hdmi-camera-fisheye-tile8df9tp-20261103-a/trace-map-screen-a'
WORK = ROOT / 'work/hdmi-camera-fisheye-tile8df8-20261103-a'
CACHE = ROOT / 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v'
ENGINE = ROOT / 'rtl/experimental/hdmi_camera_fisheye_engine_tile8df8.v'
PROTOTYPE_WORK = REPO / 'output/tile8_next15h_20261103/new-next-probe-20261104'
BULK_PROTOTYPE = PROTOTYPE_WORK / 'bulk-cache-probe-a.v'
SNAPSHOT_PROTOTYPE = PROTOTYPE_WORK / 'decoded-slow-probe-b.v'
BODY = TRACE / 'blocks-tile8.i32'
COORDINATES = TRACE / 'mapped-cache-input-tile8-q8.i32'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inputs():
    require(sha(CACHE) == 'd4730a733bc8f84886d268fcc90bb702db035a41867c812d6119694fbbf35b1e', 'frozen cache drift')
    blocks = np.fromfile(BODY, dtype='<i4').reshape(-1, 4)
    coords = np.fromfile(COORDINATES, dtype='<i4').reshape(-1, 2)
    require(blocks.shape == (2073600, 4) and coords.shape == (2073600, 2), 'complete native trace required')
    numbers = np.full_like(blocks, -1)
    for n in range(4):
        x = (coords[:, 0].astype(np.int64) >> 8) + n % 2
        y = (coords[:, 1].astype(np.int64) >> 8) + n // 2
        valid = (x >= 0) & (x < 1920) & (y >= 0) & (y < 1080)
        numbers[:, n] = np.where(valid, y * 1920 + x, -1)
    require(np.array_equal(blocks, np.where(numbers >= 0, numbers >> 7, -1)), 'independent Q8 neighbour/address decode differs')
    return blocks, numbers


def replay(blocks, bulk, extra_check=1, snapshot=False):
    tags = [-1] * 256
    fast = slow = misses = hits = valid_samples = 0
    cycles = 0
    bulk_success = bulk_fail = 0
    saved_gross = paid_check = 0
    hist_last_miss = collections.Counter()
    hist_bulk_neighbour = collections.Counter()
    hist_slow_miss_count = collections.Counter()
    conflicts = 0
    eliminated_valid_select = eliminated_hit_load = 0
    before_crc = hashlib.sha256()
    examples = []
    for query, raw in enumerate(blocks):
        q = tuple(map(int, raw))
        valid_samples += sum(b >= 0 for b in q)
        if all(b < 0 or tags[b & 255] == b for b in q):
            fast += 1
            hits += sum(b >= 0 for b in q)
            cycles += 1
            continue
        slow += 1
        # Fixed slow admission/drain costs are equal in both variants and are
        # deliberately omitted; report only exact differing slow state edges.
        cycles += 1  # IDLE lock -> SELECT
        query_misses = 0
        last_miss = -1
        bulk_taken = False
        for n, b in enumerate(q):
            cycles += 1  # original SELECT or snapshot CHECK, both handle OOB
            if b < 0:
                continue
            if not snapshot:
                cycles += 1  # original extra CHECK after SELECT
            else:
                eliminated_valid_select += 1
            was_hit = tags[b & 255] == b
            if tags[b & 255] == b:
                hits += 1
            else:
                misses += 1
                query_misses += 1
                last_miss = n
                tags[b & 255] = b  # conceptual final valid/tag commit
                # DDR service itself is identical and not included here.
                if bulk and n < 3:
                    paid_check += extra_check
                    cycles += extra_check  # actual proposed BULK_CHECK
                    resident = all(other < 0 or tags[other & 255] == other for other in q)
                    indices = [other & 255 for other in q if other >= 0]
                    alias_conflict = any(a != c and (a & 255) == (c & 255)
                        for i, a in enumerate(q) if a >= 0 for c in q[i + 1:] if c >= 0)
                    if alias_conflict:
                        conflicts += 1
                    if n < 3 and resident and not alias_conflict:
                        # BULK_LOAD/BULK_PICK consume the same two cycles as
                        # current LOAD/PICK, then skip only remaining SELECT/
                        # CHECK/LOAD/PICK work. All bounds are snapshotted.
                        cycles += 2
                        remaining_hit_events = sum(other >= 0 for other in q[n + 1:])
                        hits += remaining_hit_events
                        gross = sum((2 if snapshot else 4) if other >= 0 else 1 for other in q[n + 1:])
                        saved_gross += gross
                        bulk_success += 1
                        hist_bulk_neighbour[str(n)] += 1
                        if len(examples) < 20:
                            examples.append({'Query': query, 'Blocks': q, 'CommittedMissNeighbour': n,
                                'GrossOldStateCyclesSkipped': gross, 'BulkCheckCyclesPaid': extra_check,
                                'RemainingHitEventsPreserved': remaining_hit_events})
                        bulk_taken = True
                        break
                    bulk_fail += 1
            cycles += 1 if snapshot and was_hit else 2  # hit CHECK reads RAM -> PICK; miss keeps LOAD/PICK
            if snapshot and was_hit:
                eliminated_hit_load += 1
        cycles += 1  # original RESULT
        hist_last_miss[str(last_miss)] += 1
        hist_slow_miss_count[str(query_misses)] += 1
        # Cache metadata must be independent of return scheduling. Its final
        # value and all requested line events are compared with the control.
    return {'FastQueries': fast, 'SlowQueries': slow, 'Fills': misses, 'ValidNeighbourHits': hits,
        'InBoundsNeighbourSamples': valid_samples, 'DifferentialStateCycleTotal': cycles,
        'BulkSuccessQueries': bulk_success, 'BulkRejectedFillChecks': bulk_fail,
        'BulkSuccessByCommittedMissNeighbour': dict(hist_bulk_neighbour),
        'SlowQueriesByLastMissNeighbour': dict(hist_last_miss), 'SlowQueriesByFillCount': dict(hist_slow_miss_count),
        'GrossOldStateCyclesSkipped': saved_gross, 'AddedBulkCheckCycles': paid_check,
        'SameIndexDifferentTagChecks': conflicts, 'FinalTagsSHA256': hashlib.sha256(np.asarray(tags, dtype='<i4').tobytes()).hexdigest(),
        'SnapshotValidSELECTCyclesEliminated': eliminated_valid_select,
        'SnapshotHitLOADCyclesEliminated': eliminated_hit_load,
        'Examples': examples}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    target = a.output.resolve()
    require(target.parent == HERE and not target.exists(), 'fresh isolated output required')
    started = time.monotonic()
    require(sha(BULK_PROTOTYPE) == '0d0f85ed5391e942f0310efbd39e0c57dce991bbd9e09d855adf8b13f8a70b92', 'actual bulk prototype source differs')
    require('state<=neighbour==3 ? LOAD:BULK_CHECK;' in BULK_PROTOTYPE.read_text(encoding='utf-8'), 'actual n3 skip changed')
    require(sha(SNAPSHOT_PROTOTYPE) == 'f2c16c15c7f73f93d792e63c80494c40b57522885e47c1d0e28cb7ebaaf9c1d2', 'actual snapshot prototype source differs')
    blocks, numbers = inputs()
    base, bulk = replay(blocks, False), replay(blocks, True)
    snapshot, combined = replay(blocks, False, snapshot=True), replay(blocks, True, snapshot=True)
    require((base['FastQueries'], base['SlowQueries'], base['Fills'], base['ValidNeighbourHits']) ==
        (2038895, 34705, 37483, 7416463), 'original exact full-frame counts not reproduced')
    for key in ('FastQueries', 'SlowQueries', 'Fills', 'ValidNeighbourHits', 'InBoundsNeighbourSamples', 'FinalTagsSHA256'):
        require(base[key] == bulk[key] == snapshot[key] == combined[key], 'scheduler changed actual cache semantics: ' + key)
    delta = base['DifferentialStateCycleTotal'] - bulk['DifferentialStateCycleTotal']
    require(delta == bulk['GrossOldStateCyclesSkipped'] - bulk['AddedBulkCheckCycles'], 'exact state-edge delta inconsistent')
    normal = list(csv.DictReader((WORK / 'system-native-a/performance.csv').open()))[0]
    sustained = list(csv.DictReader((WORK / 'system-sustained-native-a/performance.csv').open()))
    source_inputs = {str(p): sha(p) for p in (Path(__file__), CACHE, ENGINE, BODY, COORDINATES,
        TRACE / 'screen_full_tile8_cache_maps.py', TRACE / 'screening.json',
        WORK / 'system-native-a/performance.csv', WORK / 'system-sustained-native-a/performance.csv',
        BULK_PROTOTYPE, SNAPSHOT_PROTOTYPE)}
    snapshot_delta = base['DifferentialStateCycleTotal'] - snapshot['DifferentialStateCycleTotal']
    combined_delta = base['DifferentialStateCycleTotal'] - combined['DifferentialStateCycleTotal']
    require(snapshot_delta == snapshot['SnapshotValidSELECTCyclesEliminated'] + snapshot['SnapshotHitLOADCyclesEliminated'],
            'snapshot exact skipped edges differ')
    incremental_bulk = snapshot['DifferentialStateCycleTotal'] - combined['DifferentialStateCycleTotal']
    require(incremental_bulk == combined['GrossOldStateCyclesSkipped'] - combined['AddedBulkCheckCycles'],
            'nonoverlapping incremental bulk cost differs')
    value = {'Schema': 'tile8df8-exact-prototype-aligned-snapshot-hitread-and-bulk-state-screen-v1', 'CreatedUTC': datetime.now(timezone.utc).isoformat(),
        'ActualPrototypeN3SkipsBulkCheck': True,
        'SupersedesConservativeEveryFillCheckReports': ['full-bulk-state-screen-a.json','full-snapshot-and-bulk-state-screen-b.json'],
        'FullQueryCount': len(blocks), 'IndexBits': 8, 'Original128PixelBlocks': True,
        'TraceOrigin': 'existing source-derived frozen mapper Q8/native8x8 trace, not a captured per-cycle or board trace',
        'IndependentQ8NeighbourBlockDecodePassed': True, 'FrozenActualCountsReproduced': True,
        'Baseline': base, 'ActualProposedBulkCheckOneCycle': bulk,
        'ExactDifferentialStateCyclesSaved': delta, 'DifferentialTimeAt125MHzMS': delta / 125000,
        'SnapshotSELECTAndHitLOAD': snapshot, 'SnapshotPlusActualBulk': combined,
        'SnapshotExactLocalCyclesSaved': snapshot_delta, 'SnapshotLocalMSAt125MHz': snapshot_delta / 125000,
        'CombinedExactLocalCyclesSaved': combined_delta, 'CombinedLocalMSAt125MHz': combined_delta / 125000,
        'BulkIncrementBeyondSnapshotCyclesSaved': incremental_bulk,
        'CombinedMeets266000CycleScreeningThreshold': combined_delta >= 266000,
        'Meets266000CycleScreeningThreshold': delta >= 266000,
        'ReferenceOriginalSystemPerformance': normal, 'ReferenceSustainedSystemPerformance': sustained,
        'ActualDDRTransactionsUnchanged': True, 'RAMCommitCountExpectedBoth': base['Fills'] * 8,
        'NewStateRule': 'WAIT_COMMIT actuallastwrite -> if n3 oldLOAD; otherwise BULK_CHECK1 -> allresident BULK_LOAD/BULK_PICK/RESULT, else oldLOAD',
        'SnapshotRule': 'accept_slow preloads snapshot neighbour0; PICK preloads next; valid CHECK replaces SELECT/CHECK, hit CHECK reads RAM then PICK; misses keep postcommitLOAD/PICK; OOB stays one cycle',
        'Limits': ['Finite address and state-edge accounting only; no new RTL or EDA run.',
            'DDR service, pipeline drains, mapper, writer, shared arbitration and bank/scan phases are not recomputed.',
            'Exact local skipped state edges need not equal final end-to-end savings under contention/backpressure.',
            'No physical timing, RAM mapping or output-pixel CRC proof for the new implementation.',
            'No new board FPS, 30FPS or unique-presentation improvement claim.'],
        'FrozenRTLModified': False, 'NewRTLExecuted': False, 'EDAExecuted': False, 'HardwareAccessed': False,
        'ElapsedSeconds': time.monotonic() - started, 'InputDrift': [], 'InputSHA256': source_inputs}
    with target.open('x', encoding='utf-8') as f:json.dump(value, f, indent=2);f.write('\n')
    print(json.dumps({'Output': str(target), 'SHA256': sha(target), 'Counts': {k:base[k] for k in ('FastQueries','SlowQueries','Fills','ValidNeighbourHits')},
        'BulkSuccess': bulk['BulkSuccessQueries'], 'ByNeighbour': bulk['BulkSuccessByCommittedMissNeighbour'],
        'AddedCheckCycles': bulk['AddedBulkCheckCycles'], 'GrossSkipped': bulk['GrossOldStateCyclesSkipped'],
        'BulkOnlyNetLocalCyclesSaved': delta, 'SnapshotOnlyNetLocalCyclesSaved': snapshot_delta,
        'CombinedNetLocalCyclesSaved': combined_delta, 'IncrementalBulkBeyondSnapshot': incremental_bulk,
        'CombinedLocalMSAt125MHz': combined_delta / 125000, 'NewRTLOrBoardClaimed': False}))


if __name__ == '__main__':main()
