"""Cold-frame full-tag direct/LRU capacity screen from the frozen Q8 query order.

Only a cache-address and serial service-cycle model; no RTL, EDA or hardware.
Run compression skips repeated identical four-block queries only after proving
all four blocks remain resident. Their repeated LRU touches are idempotent.
"""
import argparse
import collections
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOT = REPO / 'distortion'
TRACE = ROOT / 'work/hdmi-camera-fisheye-tile8df9tp-20261103-a/trace-map-screen-a'
BODY = TRACE / 'blocks-tile8.i32'
COORDS = TRACE / 'mapped-cache-input-tile8-q8.i32'
CACHE = ROOT / 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v'
ENGINE = ROOT / 'rtl/experimental/hdmi_camera_fisheye_engine_tile8df8.v'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def serial_cycles(events, trailing_fast, latency, periodic):
    """Original slow SELECT/CHECK/LOAD/PICK; single burst and last RAM commit.

    AR earliest next edge; firstR=AR+latency+1; eight beats; each RAM commit one
    edge after accepted R. Optional schedules match the earlier isolated model:
    AR blocked at cycle%7<2, R holes at cycle%5==0. No shared-system arbitration.
    """
    c = ar_wait = r_gap = 0
    for fast_before, valid_mask, miss_mask in events:
        c += fast_before
        if fast_before:
            c += 2  # existing fast-pipeline drain before slow ownership
        c += 1  # held slow query admission
        for n in range(4):
            c += 1  # SELECT, including out-of-bounds masked neighbours
            if not valid_mask & (1 << n):
                continue
            c += 1  # CHECK
            if miss_mask & (1 << n):
                ar = c + 1
                while periodic and ar % 7 < 2:
                    ar += 1
                ar_wait += ar - c - 1
                first = ar + latency + 1
                cursor, accepted, last = first, 0, None
                while accepted < 8:
                    if not periodic or cursor % 5 != 0:
                        accepted += 1
                        last = cursor
                    cursor += 1
                r_gap += last - first + 1 - 8
                c = last + 1  # final actual RAM commit publishes tag/valid
                c += 1  # wait-commit ownership transition
            c += 2  # LOAD, PICK
        c += 1  # stable RESULT transfer
    c += trailing_fast + 2
    return dict(Cycles=c, MillisecondsAt125MHz=c / 125000,
                PeriodicARWaitCycles=ar_wait, PeriodicRGapCycles=r_gap)


def replay(groups, runs, index_bits, ways):
    lines = 1 << index_bits
    require(ways in (1, 2, 4) and lines % ways == 0, 'supported equal-capacity associativity required')
    sets_count = lines // ways
    sets = [[] for _ in range(sets_count)]  # full block IDs, MRU -> LRU
    fast = slow = fills = valid_samples = 0
    fast_pending = 0
    events = []
    histogram = collections.Counter()
    conflict_queries = 0
    for raw, count in zip(groups, runs):
        q = tuple(int(b) for b in raw)
        count = int(count)
        valid = [b for b in q if b >= 0]
        valid_mask = sum(1 << n for n, b in enumerate(q) if b >= 0)
        valid_samples += count * len(valid)
        # First query is processed in exact neighbour order. Lookup for the
        # query's fast path occurs before any of these four demand touches.
        for repetition in range(count):
            all_hit = all(b in sets[b & (sets_count - 1)] for b in valid)
            miss_mask = query_fills = 0
            if all_hit:
                fast += 1
                fast_pending += 1
            else:
                slow += 1
            for n, b in enumerate(q):
                if b < 0:
                    continue
                bank = sets[b & (sets_count - 1)]
                if b in bank:
                    bank.remove(b)
                else:
                    fills += 1
                    query_fills += 1
                    miss_mask |= 1 << n
                    if len(bank) == ways:
                        bank.pop()
                bank.insert(0, b)
            if not all_hit:
                events.append((fast_pending, valid_mask, miss_mask))
                fast_pending = 0
                histogram[str(query_fills)] += 1
            remaining = count - repetition - 1
            if remaining and all(b in sets[b & (sets_count - 1)] for b in valid):
                # Repeating the same ordered touches leaves the same MRU order.
                fast += remaining
                fast_pending += remaining
                break
            if remaining:
                conflict_queries += 1
    models = []
    for latency in (0, 8, 40):
        models.append(dict(FirstResponseLatencyCycles=latency,
                           NoArbitrationNoBeatHolesLowerBound=serial_cycles(events, fast_pending, latency, False),
                           PeriodicARAndBeatHoleServiceModel=serial_cycles(events, fast_pending, latency, True)))
    tags = [value for bank in sets for value in bank]
    return dict(IndexBits=index_bits, CapacityLines=lines, CapacityKiB=lines // 4,
                Ways=ways, Sets=sets_count, ReplacementPolicy='full-tag sequential neighbour demand LRU; MRU on every in-bounds reference; lowest empty way before LRU victim',
                Queries=fast + slow, FastQueries=fast, SlowQueries=slow, Fills=fills,
                InBoundsNeighbourSamples=valid_samples, InBoundsNeighbourHits=valid_samples - fills,
                DemandHitRate=(valid_samples - fills) / valid_samples,
                DDRReadPayloadBytes=fills * 256, DDRReadBeats=fills * 8,
                ActualRAMCommitEventsRequired=fills * 8,
                QueryReturnedInBoundsSampleBytes=valid_samples * 2,
                SlowQueriesByFillCount=dict(histogram),
                RepeatedQueryConflictFallbackIterations=conflict_queries,
                FinalResidentBlocks=len(tags), FinalResidentFullTagsSHA256=hashlib.sha256(np.asarray(tags, dtype='<i4').tobytes()).hexdigest(),
                MaximumOutstandingBursts=1, Models=models)


def load_trace():
    require(sha(BODY) == '709df4ad4a38d55265bdd218cfd352d13f591e85e5551e3c97dc0f80442a2e13', 'block trace identity differs')
    require(sha(COORDS) == '32527599feaecf2db6a0e1ab83270e5ad530fb88f51b30c543158362d6c700fc', 'Q8 trace identity differs')
    require(sha(CACHE) == 'd4730a733bc8f84886d268fcc90bb702db035a41867c812d6119694fbbf35b1e', 'frozen INDEX8 cache differs')
    blocks = np.fromfile(BODY, dtype='<i4').reshape(-1, 4)
    coords = np.fromfile(COORDS, dtype='<i4').reshape(-1, 2)
    require(blocks.shape == (2073600, 4) and coords.shape == (2073600, 2), 'complete native trace required')
    numbers = np.full_like(blocks, -1)
    for n in range(4):
        x = (coords[:, 0].astype(np.int64) >> 8) + n % 2
        y = (coords[:, 1].astype(np.int64) >> 8) + n // 2
        valid = (x >= 0) & (x < 1920) & (y >= 0) & (y < 1080)
        numbers[:, n] = np.where(valid, y * 1920 + x, -1)
    require(np.array_equal(blocks, np.where(numbers >= 0, numbers >> 7, -1)), 'independent Q8 neighbour decode differs')
    start = np.r_[True, np.any(blocks[1:] != blocks[:-1], axis=1)]
    indexes = np.flatnonzero(start)
    runs = np.diff(np.r_[indexes, len(blocks)])
    return blocks, numbers, blocks[indexes], runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(args.output.resolve().parent == HERE and not args.output.exists(), 'fresh isolated screen output required')
    started = time.monotonic()
    blocks, numbers, groups, runs = load_trace()
    results = []
    # Direct results are emitted immediately, without waiting for associativity.
    for ways in (1, 2, 4):
        for index_bits in (8, 9, 10):
            result = replay(groups, runs, index_bits, ways)
            require(result['Queries'] == 2073600 and result['InBoundsNeighbourSamples'] == 7453946, 'query/sample count differs')
            if ways == 1 and index_bits in (8, 9):
                expected = (37483, 34705) if index_bits == 8 else (31110, 28809)
                require(result['Fills'] == expected[0], 'known direct fill count not reproduced')
                if index_bits == 8:
                    require(result['SlowQueries'] == expected[1] and result['FastQueries'] == 2038895, 'known INDEX8 slow count not reproduced')
            result['FillsSavedVsIndex8Direct'] = 37483 - result['Fills']
            result['PayloadSavedVsIndex8DirectBytes'] = result['FillsSavedVsIndex8Direct'] * 256
            result['MinimumUniqueBlocks'] = int(len(np.unique(blocks[blocks >= 0])))
            result['RepeatedBlockRefillPayloadBytes'] = (result['Fills'] - result['MinimumUniqueBlocks']) * 256
            if results:
                for baseline, variant in zip(results[0]['Models'], result['Models']):
                    for kind in ('NoArbitrationNoBeatHolesLowerBound', 'PeriodicARAndBeatHoleServiceModel'):
                        variant[kind]['CyclesSavedVsIndex8Direct'] = baseline[kind]['Cycles'] - variant[kind]['Cycles']
                        variant[kind]['MillisecondsSavedVsIndex8DirectAt125MHz'] = variant[kind]['CyclesSavedVsIndex8Direct'] / 125000
            results.append(result)
            print(json.dumps(dict(IndexBits=index_bits, Ways=ways, Fills=result['Fills'], SlowQueries=result['SlowQueries'],
                                  Hits=result['InBoundsNeighbourHits'], PayloadBytes=result['DDRReadPayloadBytes'],
                                  Latency40ServiceCycles=result['Models'][2]['PeriodicARAndBeatHoleServiceModel']['Cycles'],
                                  ElapsedSeconds=round(time.monotonic() - started, 3))), flush=True)
    files = [Path(__file__), BODY, COORDS, CACHE, ENGINE, TRACE / 'screening.json', TRACE / 'screen_full_tile8_cache_maps.py']
    inputs = {str(path): sha(path) for path in files}
    value = dict(Schema='tile8df8-cold-full-query-capacity-associativity-screen-v1', CreatedUTC=datetime.now(timezone.utc).isoformat(),
                 SourceDerivedTrace=True, CapturedRTLOrHardwarePerQueryTrace=False,
                 FullFrameQueries=2073600, RunLengthGroups=len(groups), ColdFrameForEveryConfiguration=True,
                 IndependentQ8BlockDecodePassed=True, PixelBlockBytes=256, PixelsPerBlock=128,
                 TotalValidNeighbourSamples=7453946, TotalOOBNeighbourSamples=int((blocks < 0).sum()),
                 UniqueRequestedBlocks=int(len(np.unique(blocks[blocks >= 0]))),
                 UniqueRequestedSourcePixels=int(len(np.unique(numbers[numbers >= 0]))),
                 FastPathHitSnapshotBeforeDemandTouches=True,
                 Replacement='Set = fullBlockID mod(number of sets); retain full block ID; touch in neighbour0..3 order; exact LRU demand policy; OOB no cache or DDR action',
                 IdenticalBlockQueryCompression='After one query only, skip repetitions iff every valid block remains resident; repeated identical LRU demand order is idempotent; otherwise replay each query',
                 Variants=results, ElapsedSeconds=time.monotonic() - started,
                 Limits=[
                     'Finite address/service model only; no new RTL, tag-port, pixel/CRC, queue, reset, fault, or read/write collision validation.',
                     'Associative cache requires a new physical bank/tag/read selection design; model LRU work and way selection have zero additional cost.',
                     'No-arbitration variant is a same-service-architecture lower bound, not a rigorous lower bound for all possible architectures.',
                     'Periodic AR/R schedules are declared synthetic assumptions; latency40 is not measured board DDR.',
                     'Mapper, writer, shared DDR arbitration, frame admission, bank ownership, scanout and presentation overlap are excluded.',
                     'No FPS, board processing time, physical timing or release acceptance is predicted.',
                     'Payload bytes are actual modeled fetched bytes; repeated block refill payload is not invalid pixel data or measured bus efficiency.',
                 ], FrozenRTLModified=False, NewRTLExecuted=False, EDAExecuted=False, HardwareAccessed=False,
                 InputSHA256=inputs, InputDrift=[])
    require(all(sha(path) == digest for path, digest in inputs.items()), 'input drift')
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(Output=str(args.output.resolve()), SHA256=sha(args.output), Variants=len(results))), flush=True)


if __name__ == '__main__':
    main()
