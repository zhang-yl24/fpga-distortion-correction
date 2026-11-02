"""CPU-only nonidentity fixture/parser/evidence tests. No EDA or device launch."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import run_camera720_corrected_system_sim as sim


class HeaderTest(unittest.TestCase):
    def setUp(self):
        self.config, self.guard = sim.synthetic_config(32, 16)
        self.header = sim.render_header(self.config, self.guard)

    def test_negative_radial_and_tangential_coefficients_round_trip(self):
        parsed, guard = sim.parse_header(self.header)
        self.assertEqual((parsed, guard), (self.config, self.guard))
        self.assertLess(parsed[9], 0)
        self.assertLess(parsed[12], 0)
        self.assertIn("C720_K2=-32'sd", self.header)
        actual = sim.geometry(32, 16, parsed, guard)
        wrong_sign = parsed.copy()
        wrong_sign[9], wrong_sign[12] = -wrong_sign[9], -wrong_sign[12]
        wrong = sim.geometry(32, 16, wrong_sign, guard)
        self.assertTrue(np.any(actual[0] != wrong[0]) or np.any(actual[1] != wrong[1]))

    def test_negative_center_and_signed_limits_round_trip(self):
        values = self.config.copy()
        values[0] = -(1 << 23)
        values[8] = -(1 << 31)
        values[9] = (1 << 31)-1
        self.assertEqual(sim.parse_header(sim.render_header(values, self.guard))[0], values)

    def test_duplicate_missing_or_executable_content_is_rejected(self):
        lines = self.header.splitlines()
        for text in (self.header+lines[1]+'\n', '\n'.join(lines[2:]),
                     self.header+'initial $finish;\n', self.header+chr(96)+'include "other.vh"\n'):
            with self.subTest(text=text[-60:]), self.assertRaises(ValueError):
                sim.parse_header(text)

    def test_bad_width_range_and_nonfinite_are_rejected(self):
        wrong_width = self.header.replace("C720_K2=-32'sd", "C720_K2=-24'sd")
        for text in (wrong_width, self.header.replace(str(abs(self.config[9])), str(1 << 31 | 1)),
                     self.header.replace("C720_K2=-32'sd", "C720_K2=NaN; //"),
                     self.header.replace('C720_RADIUS_Q22=8388608', 'C720_RADIUS_Q22=2147483648')):
            with self.subTest(text=text[-150:]), self.assertRaises(ValueError):
                sim.parse_header(text)
        for value in (float('nan'), float('inf'), True):
            values = self.config.copy(); values[8] = value
            with self.assertRaises(ValueError):
                sim.render_header(values, self.guard)

    def test_geometry_prevents_numpy_overflow_outside_mapper_domain(self):
        values = self.config.copy(); values[6] = (1 << 31)-1
        with self.assertRaisesRegex(ValueError, 'normalized mapper domain'):
            sim.geometry(32, 16, values, self.guard)


class DualReferenceTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='camera720-corrected-')
        self.addCleanup(self.scratch.cleanup)
        self.work = Path(self.scratch.name)
        self.header = sim.render_header(*sim.synthetic_config(32, 16))
        self.expected, self.records, self.model = sim.fixtures(self.work, self.header, width=32, height=16)
        self.sources = [sim.cpu.texture(32, 16, i) for i in (0, 1)]
        self.summary = {'unique_scans': 2, 'repeat_scans': 0}
        self.write_scans(self.expected)
        self.write_events()

    def write_scans(self, frames):
        text = ''.join(f'{i+1} {int(v):04x}\n' for i, frame in enumerate(frames) for v in frame.ravel())
        (self.work/'scan-pixels.mem').write_text(text, encoding='ascii')

    def write_events(self):
        rows = ['event,id,core_cycle,crc32']
        for i, record in enumerate(self.records):
            rows.extend([f"commit,{i+1},{10*i+1},{record['SourceCRC32']}",
                         f"release,{i+1},{10*i+2},{record['CorrectedCRC32']}"])
        (self.work/'events.csv').write_text('\n'.join(rows)+'\n', encoding='ascii')

    def verify(self):
        return sim.validate_outputs(self.work, self.expected, self.records, self.summary)

    def test_nonidentity_source_result_pixels_beats_and_crc_are_distinct(self):
        self.assertEqual(len(self.verify()), 2)
        self.assertGreater(self.model['NonidentityCoordinateCount'], 32*16//2)
        self.assertEqual(self.model['ScalarCoordinateCrosschecks'], 221)
        self.assertFalse(self.model['LensCalibrationAccepted'])
        for i, record in enumerate(self.records):
            self.assertNotEqual(record['SourceCRC32'], record['CorrectedCRC32'])
            self.assertGreater(record['ChangedPixels'], 32*16//2)
            self.assertEqual(record['SourceCRC32'], sim.crc(self.sources[i]))
            self.assertEqual(record['CorrectedCRC32'], sim.crc(self.expected[i]))
        for filename, frames in (('source-beats.mem', self.sources), ('corrected-beats.mem', self.expected)):
            reconstructed = b''.join(int(line, 16).to_bytes(32, 'little') for line in (self.work/filename).read_text().splitlines())
            self.assertEqual(reconstructed, b''.join(np.asarray(v, dtype='<u2').tobytes() for v in frames))
        for filename, frames in (('source-pixels.mem', self.sources), ('expected.mem', self.expected)):
            words = [int(line, 16) for line in (self.work/filename).read_text().splitlines()]
            self.assertEqual(words, np.concatenate(frames).ravel().tolist())
        self.assertNotEqual((self.work/'source-crcs.mem').read_bytes(), (self.work/'corrected-crcs.mem').read_bytes())

    def test_old_identity_crc_assumption_is_rejected_at_capture(self):
        path = self.work/'events.csv'
        path.write_text(path.read_text().replace(self.records[0]['SourceCRC32'], self.records[0]['CorrectedCRC32']), encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'source completion CRC'):
            self.verify()

    def test_source_crc_cannot_substitute_corrected_result_crc(self):
        path = self.work/'events.csv'
        path.write_text(path.read_text().replace(self.records[0]['CorrectedCRC32'], self.records[0]['SourceCRC32']), encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'corrected completion CRC'):
            self.verify()

    def test_unprocessed_source_pixels_cannot_pass_corrected_scan(self):
        self.write_scans(self.sources)
        with self.assertRaisesRegex(ValueError, 'independent corrected oracle'):
            self.verify()

    def test_single_pixel_corruption_is_rejected(self):
        frames = [v.copy() for v in self.expected]; frames[0][3, 7] ^= 1
        self.write_scans(frames)
        with self.assertRaisesRegex(ValueError, 'independent corrected oracle'):
            self.verify()

    def test_forged_reference_crc_is_rejected(self):
        self.records[0]['CorrectedCRC32'] = self.records[0]['SourceCRC32']
        with self.assertRaisesRegex(ValueError, 'reference CRC'):
            self.verify()

    def test_release_before_commit_is_rejected(self):
        path = self.work/'events.csv'
        path.write_text(path.read_text().replace('release,1,2,', 'release,1,0,'), encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'released before processing'):
            self.verify()

    def test_scan_epoch_change_is_rejected(self):
        path = self.work/'scan-pixels.mem'; lines = path.read_text().splitlines()
        lines[23] = '2 '+lines[23].split()[1]
        path.write_text('\n'.join(lines)+'\n', encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'epoch changed'):
            self.verify()

    def test_missing_or_extra_scan_pixel_is_rejected(self):
        path = self.work/'scan-pixels.mem'; original = path.read_text()
        path.write_text('\n'.join(original.splitlines()[:-1])+'\n', encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'incomplete actual scan'):
            self.verify()
        path.write_text(original+'2 0000\n', encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'extra actual HDMI'):
            self.verify()


class PreparationTest(unittest.TestCase):
    def test_default_preparation_cannot_launch_simulator_or_claim_pass(self):
        with tempfile.TemporaryDirectory(prefix='camera720-prepare-') as scratch:
            base = Path(scratch)
            fixtures = sim.fixtures
            def small(work, header):
                return fixtures(work, sim.render_header(*sim.synthetic_config(32, 16)), width=32, height=16)
            with mock.patch.object(sim, 'BASE', base), mock.patch.object(sim, 'fixtures', side_effect=small), \
                 mock.patch.object(sim, 'resolve_vivado_bin', side_effect=AssertionError('EDA resolver invoked')), \
                 mock.patch.object(sim, 'tool', side_effect=AssertionError('EDA invoked')):
                self.assertEqual(sim.run(base/'prepared', synthetic=True), 0)
            report = json.loads((base/'prepared'/sim.REPORT).read_text())
            self.assertTrue(report['Prepared'])
            self.assertFalse(report['Passed'])
            self.assertFalse(report['SimulationExecuted'])
            self.assertFalse(report['OpticalCalibrationAccepted'])
            self.assertEqual(report['Commands'], [])
            self.assertEqual(report['InputSHA256'], report['InputSHA256After'])
            self.assertEqual(report['FixtureSHA256'], report['FixtureSHA256After'])


if __name__ == '__main__':
    unittest.main()
