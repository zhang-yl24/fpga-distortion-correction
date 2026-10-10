"""Evidence boundaries and failure cases for paired tone measurements."""
from pathlib import Path
import importlib.util
import unittest
import numpy as np

path = Path(__file__).resolve().parents[1] / 'tools/evaluate-tone-pair.py'
spec = importlib.util.spec_from_file_location('tone_pair', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TonePairTests(unittest.TestCase):
    def setUp(self):
        self.image = np.array([[0, 65535], [31727, 0]], dtype=np.uint16)
        self.mask = np.array([[False, False], [False, True]])
        self.meta = dict(source_kind='synthetic_same_source', source_frame_identity='frame-1', before_source_frame_identity='frame-1', after_source_frame_identity='frame-1', angle_deg=13.7, mode=0)

    def test_geometry_excluded_but_real_black_counted(self):
        result = module.evaluate(self.image, self.image, self.mask, self.meta)
        self.assertEqual(result['valid_samples'], 3)
        self.assertAlmostEqual(result['before']['all_channels_at_zero_fraction'], 1/3)
        self.assertAlmostEqual(result['before']['all_channels_at_max_fraction'], 1/3)
        self.assertTrue(result['exact_tone_pixels_passed'])

    def test_mismatched_source_rejected(self):
        with self.assertRaises(ValueError):
            module.evaluate(self.image, self.image, self.mask, dict(self.meta, after_source_frame_identity='frame-2'))

    def test_masked_corruption_rejected(self):
        corrupt = self.image.copy();corrupt[1, 1] = 1
        with self.assertRaises(ValueError):
            module.evaluate(self.image, corrupt, self.mask, self.meta)

    def test_wrong_pixel_fails_exact_check(self):
        corrupt = self.image.copy();corrupt[1, 0] ^= 1
        self.assertFalse(module.evaluate(self.image, corrupt, self.mask, self.meta)['exact_tone_pixels_passed'])

    def test_empty_and_bad_shape_rejected(self):
        for mask in (np.ones_like(self.mask), self.mask[:, :1]):
            with self.assertRaises(ValueError):
                module.evaluate(self.image, self.image, mask, self.meta)

    def test_brighten_preserves_white_black_endpoints(self):
        image = np.array([[0, 65535]], dtype=np.uint16)
        result = module.evaluate(image, image, np.zeros_like(image, dtype=bool), dict(self.meta, mode=1))
        self.assertTrue(result['exact_tone_pixels_passed'])
        self.assertFalse(result['provenance_independently_verified'])


if __name__ == '__main__':
    unittest.main()
