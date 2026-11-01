"""A bounded CDC audit must not hide missing paths or native gate changes."""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import audit_raw_camera_io_cdc as audit


class BooleanTests(unittest.TestCase):
    def test_unknown_gate_is_not_assumed_safe(self):
        self.assertEqual(audit.BooleanCone.evaluate(('variable', 'unknown'), {}), {0, 1})

    def test_all_truth_rows_reduce_when_gate_is_disabled(self):
        # I0 AND I1, independent of the other four LUT inputs.
        init = sum(1 << bit for bit in range(64) if (bit & 3) == 3)
        expression = ('lut', init, {}, {0:('variable', 'flag'), 1:('variable', 'other')})
        self.assertEqual(audit.BooleanCone.evaluate(expression, {'flag':0}), {0})
        self.assertEqual(audit.BooleanCone.evaluate(expression, {'flag':1}), {0, 1})

    def test_inversion_preserves_unknownness(self):
        self.assertEqual(audit.BooleanCone.evaluate(('not', ('variable', 'v')), {}), {0, 1})
        self.assertEqual(audit.BooleanCone.evaluate(('not', ('variable', 'v')), {'v':1}), {0})


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.row = {'Label':'gray[0]', 'Source':'fifo/source/FF3/FF', 'NativeEndpoint':'fifo/meta/D',
                    'SourceClock':'camera_pclk', 'DestinationClock':'ddrphy_sysclk'}
        self.constraints = {'PeriodsNS':{'camera_pclk':20.833, 'ddrphy_sysclk':8.0}}
        self.pairs = {('camera_pclk', 'ddrphy_sysclk'):{'BoundNS':8.0}}
        self.paths = [{'Source':'fifo/source/CLK', 'Endpoint':'fifo/meta/D', 'Corner':corner,
                       'BoundNS':8.0, 'SlackNS':5.0, 'ArrivalNS':3.0} for corner in ('slow', 'fast')]

    def check(self, gray=True):
        with patch.object(audit.cdc, 'max_delay_paths', return_value=(self.paths, {})):
            return audit.coverage([self.row], Path('unused'), self.constraints, self.pairs, gray)

    def test_two_corners_are_required(self):
        paths, missing, _ = self.check()
        self.assertEqual(len(paths), 2)
        self.assertEqual(missing, [])
        self.paths.pop()
        _, missing, _ = self.check()
        self.assertEqual(missing[0]['Corner'], 'fast')

    def test_another_source_cannot_fill_missing_path(self):
        self.paths[0]['Source'] = 'unrelated/CLK'
        with self.assertRaisesRegex(ValueError, 'source/budget'):
            self.check()

    def test_duplicate_path_is_not_full_coverage(self):
        self.paths.append(copy.deepcopy(self.paths[0]))
        with self.assertRaisesRegex(ValueError, 'source/budget'):
            self.check()

    def test_weakened_budget_rejected(self):
        self.pairs[('camera_pclk', 'ddrphy_sysclk')]['BoundNS'] = 30
        with self.assertRaisesRegex(ValueError, 'exact 8ns'):
            self.check()

    def test_held_bundle_window_uses_destination_period(self):
        paths, missing, _ = self.check(gray=False)
        self.assertEqual(paths[0]['ConservativeWindowNS'], 16.0)
        self.paths[0]['ArrivalNS'] = 16.0
        with self.assertRaisesRegex(ValueError, 'propagation window'):
            self.check(gray=False)


if __name__ == '__main__': unittest.main()
