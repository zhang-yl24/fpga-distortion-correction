"""Independent dense fixed-point oracle for the new transport configuration."""
from pathlib import Path
import re
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import generate_1080_core_vectors as cpu


class Camera720IdentityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        header = (Path(__file__).resolve().parents[1]/'board/camera720-identity.vh').read_text(encoding='utf-8')
        cls.config = [int(value) for value in re.findall(r"C720_\w+=\d+'sd(\d+)", header)]
        if len(cls.config) != 13:
            raise ValueError('exactly 13 signed transport coefficients required')
        cls.guard = int(re.search(r'C720_RADIUS_Q22=(\d+)', header)[1])
        cls.y, cls.x = np.indices((720, 1280), dtype=np.int64)
        cls.sx, cls.sy, cls.bad, cls.r2 = cpu.project_integer(cls.x*256, cls.y*256, cls.config)

    def test_all_coordinates_equal_original_integer_pixel_positions(self):
        self.assertTrue(np.array_equal(self.sx, self.x*256))
        self.assertTrue(np.array_equal(self.sy, self.y*256))

    def test_no_arithmetic_or_radius_rejection(self):
        self.assertFalse(self.bad.any())
        self.assertLessEqual(int(self.r2.max()), self.guard)

    def test_rgb565_pixels_including_last_row_and_column_are_unchanged(self):
        # Last-row/column footprints contain zero-weight out-of-bounds
        # neighbours. Verify pixel reconstruction, not only coordinate math.
        source = cpu.texture(1280, 720, 1)
        result = cpu.pack565(cpu.remap_fixed(cpu.expand565(source), self.sx/256., self.sy/256.))
        self.assertTrue(np.array_equal(result, source))
        self.assertTrue(np.array_equal(result[-1, :], source[-1, :]))
        self.assertTrue(np.array_equal(result[:, -1], source[:, -1]))


if __name__ == '__main__':
    unittest.main()
