"""Independent uncompressed OrderedDict oracle for the finite LRU screen."""
import collections
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import unittest

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('capacity_screen', HERE / 'capacity_associativity_screen_a.py')
screen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(screen)


def oracle(groups, runs, bits, ways):
    sets = [collections.OrderedDict() for _ in range((1 << bits) // ways)]
    fast = slow = fills = samples = 0
    histogram = collections.Counter()
    for raw, run in zip(groups, runs):
        q = tuple(map(int, raw))
        for _ in range(int(run)):
            valid = [b for b in q if b >= 0]
            samples += len(valid)
            all_hit = all(b in sets[b % len(sets)] for b in valid)
            fast += all_hit
            slow += not all_hit
            misses = 0
            for b in valid:
                bank = sets[b % len(sets)]
                if b in bank:
                    bank.move_to_end(b)
                else:
                    if len(bank) == ways:
                        bank.popitem(last=False)
                    bank[b] = None
                    fills += 1
                    misses += 1
            if not all_hit:
                histogram[str(misses)] += 1
    tags = [b for bank in sets for b in reversed(bank)]
    return dict(FastQueries=fast, SlowQueries=slow, Fills=fills,
                InBoundsNeighbourSamples=samples, InBoundsNeighbourHits=samples - fills,
                SlowQueriesByFillCount=dict(histogram),
                FinalResidentFullTagsSHA256=hashlib.sha256(np.asarray(tags, dtype='<i4').tobytes()).hexdigest())


class CapacityScreenTests(unittest.TestCase):
    def compare(self, groups, runs, bits, ways):
        a = oracle(groups, runs, bits, ways)
        b = screen.replay(groups, runs, bits, ways)
        for key in a:
            self.assertEqual(a[key], b[key], (bits, ways, key))

    def test_lru_victim_and_full_tag(self):
        # Same low set bits; a truncated-tag implementation would falsely hit.
        groups = np.asarray([[0, 8, 0, 16], [8, 24, 0, 16], [0, 8, 16, 24]], dtype=np.int32)
        for ways in (1, 2, 4):
            with self.subTest(ways=ways):
                self.compare(groups, [3, 2, 4], 3, ways)

    def test_out_of_bounds_does_not_allocate_or_touch_lru(self):
        groups = np.asarray([[-1, -1, -1, -1], [2, -1, 18, -1], [-1, 2, -1, 18]], dtype=np.int32)
        for ways in (1, 2, 4):
            self.compare(groups, [100, 4, 3], 3, ways)

    def test_same_query_repetition_conflict_cannot_be_collapsed(self):
        groups = np.asarray([[0, 8, 16, 24]], dtype=np.int32)
        for ways in (1, 2, 4):
            a = screen.replay(groups, [20], 3, ways)
            self.compare(groups, [20], 3, ways)
            self.assertEqual(a['Fills'], 4 if ways == 4 else 80)
            self.assertEqual(a['SlowQueries'], 1 if ways == 4 else 20)

    def test_random_repeated_conflicting_queries_against_uncompressed_oracle(self):
        rng = random.Random(20261104)
        groups = np.asarray([[rng.randrange(-1, 80) for _ in range(4)] for _ in range(200)], dtype=np.int32)
        runs = [rng.randrange(1, 17) for _ in groups]
        for bits in (3, 4, 5):
            for ways in (1, 2, 4):
                with self.subTest(bits=bits, ways=ways):
                    self.compare(groups, runs, bits, ways)

    def test_native_prefix_uncompressed_oracle(self):
        blocks = np.fromfile(screen.BODY, dtype='<i4').reshape(-1, 4)[:20000]
        indexes = np.flatnonzero(np.r_[True, np.any(blocks[1:] != blocks[:-1], axis=1)])
        groups, runs = blocks[indexes], np.diff(np.r_[indexes, len(blocks)])
        for bits in (8, 9, 10):
            for ways in (1, 2, 4):
                with self.subTest(bits=bits, ways=ways):
                    self.compare(groups, runs, bits, ways)

    def test_no_stall_cycle_cost_independent_closed_form(self):
        events = [(5, 15, 1), (0, 3, 2), (10, 0, 0), (2, 5, 4)]
        trailing = 7
        for latency in (0, 8, 40):
            expected = sum(n for n, _, _ in events) + trailing + 2
            expected += sum(6 + 3 * v.bit_count() + (2 if n else 0) + m.bit_count() * (latency + 11)
                            for n, v, m in events)
            self.assertEqual(screen.serial_cycles(events, trailing, latency, False)['Cycles'], expected)

    def test_saved_fullscreen_direct_baseline_matches_prior_independent_model(self):
        saved = json.loads((HERE / 'full-capacity-associativity-screen-a.json').read_text())
        older = json.loads((HERE / 'full-lookahead-cycle-model-a.json').read_text())
        first = saved['Variants'][0]
        self.assertEqual((first['Fills'], first['SlowQueries'], first['InBoundsNeighbourHits']), (37483, 34705, 7416463))
        self.assertEqual(saved['UniqueRequestedBlocks'], 14762)
        for before, now in zip(older['Runs'], first['Models']):
            self.assertEqual(before['FirstResponseLatencyCycles'], now['FirstResponseLatencyCycles'])
            self.assertEqual(before['Baseline']['Cycles'], now['PeriodicARAndBeatHoleServiceModel']['Cycles'])

    def test_cold_frame_replay_does_not_reuse_previous_run(self):
        groups = np.asarray([[1, 1, 2, 2], [2, 2, 3, 3]], dtype=np.int32)
        a = screen.replay(groups, [3, 4], 8, 2)
        b = screen.replay(groups, [3, 4], 8, 2)
        self.assertEqual(a, b)
        self.assertEqual(a['Fills'], 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
