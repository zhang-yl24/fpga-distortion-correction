import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('coverage',Path(__file__).resolve().parents[1]/'tools/check-d5-video-session.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class CoverageTests(unittest.TestCase):
    def lines(self):
        return [f'RA={int(angle*(1<<32)/360):08X}' for angle in range(0,360,30)]
    def test_complete(self):
        self.assertEqual(m.canonical_angles(self.lines())[1],list(range(0,360,30)))
    def test_accumulator_wrap(self):
        lines=self.lines()+['RA=FFFFFFFC']
        raw,canonical=m.canonical_angles(lines)
        self.assertGreater(raw[-1],359.9999)
        self.assertEqual(canonical,list(range(0,360,30)))
    def test_missing_angle(self):
        with self.assertRaises(ValueError):m.canonical_angles(self.lines()[:-1])
    def test_unexpected_angle(self):
        with self.assertRaises(ValueError):m.canonical_angles(self.lines()+['RA=01000000'])
    def test_invalid_phase(self):
        for value in ('RA=100000000','RA=00 RA=01','NO_ANGLE'):
            with self.subTest(value=value),self.assertRaises(ValueError):m.canonical_angles(self.lines()+[value])

if __name__=='__main__':unittest.main()
