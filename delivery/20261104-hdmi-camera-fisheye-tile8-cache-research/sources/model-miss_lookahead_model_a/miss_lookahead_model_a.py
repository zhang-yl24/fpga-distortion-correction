"""Isolated cycle scheduling probe for one known-demand lookahead descriptor.

No RTL is modified or simulated here. Frozen mapper integers/ROM produce the
8x8 query sequence; replay must reproduce the actual INDEX8 fill count first.
The optional descriptor only pulls forward a remaining neighbour of the SAME
held query after a preceding fill's final RAM commit. It never has two DDR
bursts in flight and never writes concurrently with a modeled RAM read.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import ast
import csv
import hashlib
import importlib.util
import json
import re
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOT = REPO / 'distortion'
WORK = ROOT / 'work/hdmi-camera-fisheye-tile8df8-20261103-a'
CACHE = ROOT / 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v'
CACHE_SHA = 'd4730a733bc8f84886d268fcc90bb702db035a41867c812d6119694fbbf35b1e'
ENGINE = ROOT / 'rtl/experimental/hdmi_camera_fisheye_engine_tile8df8.v'
HEADER = ROOT / 'board/hdmi-camera-fisheye-profile.vh'
ROM = ROOT / 'board/hdmi-camera-fisheye-radial-table.vh'
MAPPER_ORACLE = ROOT / 'tools/generate_hdmi_fisheye_profile.py'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def frozen_configuration():
    constants = {name: int(value, 16) for name, value in re.findall(
        r"FISHEYE_([A-Z_]+)=32'sh([0-9a-fA-F]{8});", HEADER.read_text(encoding='ascii'))}
    require(len(constants) == 8, 'eight exact frozen mapper constants required')
    constants = {k: v - (1 << 32) if v >= 1 << 31 else v for k, v in constants.items()}
    pairs = [(int(index), int(word, 16)) for index, word in re.findall(
        r"10'd(\d+): fisheye_radial_pair=64'h([0-9a-fA-F]{16});", ROM.read_text(encoding='ascii'))]
    require([index for index, word in pairs] == list(range(1024)), 'complete exact1024 ROM segments required')
    nodes = []
    for index, word in pairs:
        base = word & 0xffffffff
        delta = word >> 32
        if delta >= 1 << 31:
            delta -= 1 << 32
        if index:
            require(nodes[-1] == base, 'ROM segment continuity differs')
        else:
            nodes.append(base)
        nodes.append(base + delta)
    return {'Constants': constants, 'LUTQ30': np.asarray(nodes, dtype=np.int64)}


def trace(width=1920, height=1080):
    """Source-derived trace, not a captured per-query RTL/hardware trace."""
    require(width == 1920 and height == 1080, 'this probe uses only exact frozen native geometry')
    require(sha(CACHE) == CACHE_SHA, 'frozen selected cache changed')
    origin = ROOT / 'work/hdmi-camera-fisheye-tile8df9tp-20261103-a/trace-map-screen-a'
    coordinates = np.fromfile(origin / 'mapped-cache-input-tile8-q8.i32', dtype='<i4').reshape(-1, 2)
    require(coordinates.shape == (2073600, 2), 'complete existing source-derived native coordinate trace required')
    x0, y0 = coordinates[:, 0].astype(np.int64) >> 8, coordinates[:, 1].astype(np.int64) >> 8
    numbers = np.full((width * height, 4), -1, dtype=np.int32)
    for neighbour in range(4):
        nx, ny = x0 + neighbour % 2, y0 + neighbour // 2
        valid = (nx >= 0) & (nx < width) & (ny >= 0) & (ny < height)
        numbers[:, neighbour] = np.where(valid, ny * width + nx, -1)
    blocks = np.where(numbers >= 0, numbers >> 7, -1).astype(np.int32)
    require(np.array_equal(blocks, np.fromfile(origin / 'blocks-tile8.i32', dtype='<i4').reshape(-1, 4)),
            'independent Q8 block decode differs from saved trace')
    return numbers, blocks


class Replay:
    """Cache service model with explicit shared read/write-port contention.

    It excludes mapper/backpressure, shared read arbitration, writer drain,
    acquisition/bank scheduling and HDMI presentation. All cycle totals are
    modeled cache-service cycles, never a board FPS result.
    """
    def __init__(self, first_latency, lookahead=False, beat_holes=True, ar_stalls=True, phase=0):
        self.latency = first_latency
        self.lookahead = lookahead
        self.beat_holes = beat_holes
        self.ar_stalls = ar_stalls
        self.phase = phase
        self.tags = [-1] * 256
        self.pending = None
        self.cycle = 0
        self.fast = self.slow = self.fills = self.early = self.port_stalls = self.demand_wait = 0
        self.ar_wait = self.r_gap = self.prefetch_waited_on = self.collision_skips = 0
        self.reads = self.commits = self.published = self.current_slow = 0
        self.previous_fast = False
        self.events = []

    def advance(self, cycle):
        self.cycle = max(self.cycle, cycle)
        if self.pending is not None and self.pending['last'] <= self.cycle:
            transaction = self.pending
            self.tags[transaction['line']] = transaction['block']
            self.commits += 8
            self.published += 1
            self.pending = None

    def hit(self, block):
        return block < 0 or self.tags[block & 255] == block

    def issue(self, block, kind):
        require(self.pending is None and block >= 0, 'only one owned outstanding DDR burst allowed')
        start = self.cycle
        ar = start + 1
        while self.ar_stalls and (ar + self.phase) % 7 < 2:
            ar += 1
        self.ar_wait += ar - start - 1
        first = ar + self.latency + 1
        rx = []
        cursor = first
        while len(rx) < 8:
            if not self.beat_holes or (cursor + self.phase) % 5 != 0:
                rx.append(cursor)
            cursor += 1
        commits = tuple(edge + 1 for edge in rx)
        self.r_gap += rx[-1] - first + 1 - 8
        line = block & 255
        self.tags[line] = -1
        self.pending = {'block': block, 'line': line, 'ar': ar, 'commits': commits,
                        'last': commits[-1], 'kind': kind}
        self.fills += 1
        if kind == 'lookahead':
            self.early += 1
        if len(self.events) < 32:
            self.events.append({'query': self.current_slow, 'kind': kind, 'block': block,
                'line': line, 'issue': start, 'AR': ar, 'RAMCommits': commits})

    def await_fill(self, block):
        if self.pending is not None:
            if self.pending['block'] == block and self.pending['kind'] == 'lookahead':
                self.prefetch_waited_on += 1
            last = self.pending['last']
            self.demand_wait += max(0, last - self.cycle)
            self.advance(last)
        if not self.hit(block):
            self.issue(block, 'demand')
            last = self.pending['last']
            self.demand_wait += last - self.cycle
            self.advance(last)
        require(self.hit(block), 'needed line is not published after final commit')

    def early_remaining_demand(self, blocks, neighbour):
        if not self.lookahead or self.pending is not None:
            return False
        # Protect every not-yet-saved pixel. No direct-mapped replacement may
        # evict an earlier required line or a currently loaded result word.
        remaining = [block for block in blocks[neighbour:] if block >= 0]
        for candidate in blocks[neighbour + 1:]:
            if candidate < 0 or self.hit(candidate):
                continue
            if any(other != candidate and (other & 255) == (candidate & 255) for other in remaining):
                self.collision_skips += 1
                continue
            self.issue(candidate, 'lookahead')
            return True
        return False

    def load(self, block):
        while self.pending is not None and self.cycle in self.pending['commits']:
            self.port_stalls += 1
            self.advance(self.cycle + 1)
        require(self.hit(block), 'RAM read sampled a wrong/stale line')
        # LOAD and PICK are one cycle each. The registered RAM output remains
        # held if a subsequent DDR write steals the physical read port.
        self.reads += 1
        self.advance(self.cycle + 2)

    def run(self, blocks):
        for index, raw in enumerate(blocks):
            q = tuple(map(int, raw))
            self.advance(self.cycle)
            if all(self.hit(block) for block in q):
                require(self.pending is None, 'prefetch must drain before this model accepts another query')
                self.fast += 1
                self.reads += sum(block >= 0 for block in q)
                self.cycle += 1
                self.previous_fast = True
                continue
            self.slow += 1
            self.current_slow = index
            if self.previous_fast:
                self.advance(self.cycle + 2)  # existing two-stage fast output drain
            self.previous_fast = False
            self.advance(self.cycle + 1)  # lock slow query
            early_used = False
            for neighbour, block in enumerate(q):
                self.advance(self.cycle + 1)  # SELECT, including masked neighbours
                if block < 0:
                    continue
                self.advance(self.cycle + 1)  # CHECK
                had_miss = not self.hit(block)
                if had_miss:
                    self.await_fill(block)
                    # A registered descriptor can present AR only after the
                    # preceding actual last RAM commit. No second outstanding.
                    if not early_used:
                        early_used = self.early_remaining_demand(q, neighbour)
                    self.advance(self.cycle + 1)
                self.load(block)
            self.advance(self.cycle + 1)  # stable RESULT transfer
            require(self.pending is None, 'same-query demand descriptor must be consumed/drained')
        self.advance(self.cycle + 2)
        require(self.pending is None and self.commits == self.fills * 8 and self.published == self.fills,
                'fill/RAMcommit/tag publication bookkeeping differs')
        return {'Cycles': self.cycle, 'FastQueries': self.fast, 'SlowQueries': self.slow,
            'Fills': self.fills, 'EarlyKnownDemandIssues': self.early, 'RAMReadSamples': self.reads,
            'RAMWriteCommitCycles': self.commits, 'TagPublications': self.published,
            'DemandWaitCycles': self.demand_wait, 'ReadWritePortStallCycles': self.port_stalls,
            'ARPeriodicWaitCycles': self.ar_wait, 'RPeriodicGapCycles': self.r_gap,
            'EarlyLineDemandArrivedBeforeFillComplete': self.prefetch_waited_on,
            'ProtectedIndexConflictSkips': self.collision_skips, 'MaximumOutstandingBursts': 1,
            'ExampleEvents': self.events}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--latencies', default='0,8,40')
    parser.add_argument('--prefix-queries', type=int, default=0, help='0 uses full2073600; positive is a partial probe only')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    require(output.parent == HERE and not output.exists(), 'fresh isolated output required')
    started = time.monotonic()
    numbers, blocks = trace()
    count = len(blocks) if args.prefix_queries == 0 else min(args.prefix_queries, len(blocks))
    blocks = blocks[:count]
    recorded = list(csv.DictReader((WORK / 'system-native-a/performance.csv').open()))[0]
    runs = []
    for latency in map(int, args.latencies.split(',')):
        a = Replay(latency, False).run(blocks)
        b = Replay(latency, True).run(blocks)
        require((a['Fills'], a['FastQueries'], a['SlowQueries'], a['RAMReadSamples']) ==
                (b['Fills'], b['FastQueries'], b['SlowQueries'], b['RAMReadSamples']),
                'single-variable scheduler changed demand/replacement semantics')
        if count == len(numbers):
            require(a['Fills'] == int(recorded['cache_fills']) == 37483, 'full frozen-system fill count mismatch')
        runs.append({'FirstResponseLatencyCycles': latency, 'Baseline': a, 'OneKnownDemandLookahead': b,
                     'CycleDifference': a['Cycles'] - b['Cycles'],
                     'ModelServiceImprovementPercent': (a['Cycles'] - b['Cycles']) / a['Cycles'] * 100})
    inputs = {str(path): sha(path) for path in (Path(__file__), CACHE, ENGINE, HEADER, ROM, MAPPER_ORACLE,
        WORK / 'system-native-a/performance.csv', WORK / 'system-sustained-native-a/performance.csv',
        WORK / 'system-native-a/simulation.json', WORK / 'system-sustained-native-a/simulation.json',
        ROOT / 'work/hdmi-camera-fisheye-tile8df9tp-20261103-a/trace-map-screen-a/mapped-cache-input-tile8-q8.i32',
        ROOT / 'work/hdmi-camera-fisheye-tile8df9tp-20261103-a/trace-map-screen-a/blocks-tile8.i32')}
    value = {'Schema': 'tile8df8-next-known-demand-lookahead-cycle-probe-v1', 'CreatedUTC': datetime.now(timezone.utc).isoformat(),
        'SourceDerivedCoordinateTrace': True, 'CapturedPerQueryTrace': False, 'Queries': count,
        'FullNativeQuerySequence': count == len(numbers), 'AddressTraceSHA256': hashlib.sha256(numbers.tobytes()).hexdigest(),
        'BlockTraceSHA256': hashlib.sha256(blocks.tobytes()).hexdigest(), 'INDEX_BITS': 8, 'BlockPixels': 128,
        'OneVariableChanged': 'known later-neighbour demand AR scheduling; all other service costs identical',
        'Runs': runs, 'ReferenceActualSystemCounters': recorded, 'ElapsedSeconds': time.monotonic() - started,
        'Limits': ['Cycle model only; no new RTL simulation or implementation.',
            'Fixed latency and periodic AR/R schedule are assumptions, not measured board DDR timing.',
            'Mapper/writer/arbiter/bank/admission/HDMI overlap are excluded from service totals.',
            'No speculative next-query traffic, new cache storage or multiple outstanding bursts.',
            'RAMread stalls on actual modeled write commit; tags publish only after last commit.',
            'Address-tag correctness is asserted; full pixel/interpolation CRC is not recomputed here.',
            'No board FPS or end-to-end latency improvement is claimed.'],
        'FrozenRTLModified': False, 'NewRTLExecuted': False, 'EDAExecuted': False, 'HardwareAccessed': False,
        'InputDrift': [], 'InputSHA256': inputs}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')
    print(json.dumps({'Output': str(output), 'SHA256': sha(output), 'Queries': count,
        'Runs': [{'Latency': r['FirstResponseLatencyCycles'], 'A': r['Baseline']['Cycles'],
                  'B': r['OneKnownDemandLookahead']['Cycles'], 'Delta': r['CycleDifference'],
                  'Fills': r['Baseline']['Fills']} for r in runs], 'NewRTLOrBoardPerformanceClaimed': False}))


if __name__ == '__main__':
    main()
