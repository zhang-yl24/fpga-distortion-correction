"""Negative checks for the full-system evidence verifier; no simulator launch."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import run_camera720_system_sim as sim


class Full720EvidenceTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='camera720-system-check-')
        self.addCleanup(self.scratch.cleanup)
        self.work = Path(self.scratch.name)
        for name, value in (('WIDTH', 2), ('HEIGHT', 2), ('PIXELS', 4), ('FRAMES', 3)):
            patcher = mock.patch.object(sim, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.sources = [np.array([[i, i+1], [i+2, i+3]], dtype=np.uint16) for i in (10, 20, 30)]
        self.records = [{'FrameID': i+1, 'ExpectedCRC32': sim.crc(v)} for i, v in enumerate(self.sources)]
        lines = [f'{i+1} {int(value):04x}' for i, frame in enumerate(self.sources) for value in frame.ravel()]
        (self.work/'scan-pixels.mem').write_text('\n'.join(lines)+'\n', encoding='ascii')
        lines = ['event,id,core_cycle,crc32']
        for i, record in enumerate(self.records):
            lines += [f"commit,{i+1},{10*i+1},{record['ExpectedCRC32']}",
                      f"release,{i+1},{10*i+2},{record['ExpectedCRC32']}"]
        (self.work/'events.csv').write_text('\n'.join(lines)+'\n', encoding='ascii')
        self.summary = {'unique_scans': 3, 'repeat_scans': 0}

    def verify(self):
        return sim.validate_outputs(self.work, self.sources, self.records, self.summary)

    def test_complete_actual_pixels_and_epochs_are_accepted(self):
        self.assertEqual(len(self.verify()), 3)

    def test_corrupted_actual_rgb_is_rejected(self):
        path = self.work/'scan-pixels.mem'
        path.write_text(path.read_text().replace('1 000a', '1 000b'), encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'actual HDMI RGB differs'):
            self.verify()

    def test_epoch_change_inside_picture_is_rejected(self):
        path = self.work/'scan-pixels.mem'
        path.write_text(path.read_text().replace('1 000b', '2 000b'), encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'epoch changed'):
            self.verify()

    def test_truncated_or_extra_pixels_are_rejected(self):
        path = self.work/'scan-pixels.mem'
        original = path.read_text()
        path.write_text('\n'.join(original.splitlines()[:-1])+'\n', encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'incomplete actual scan'):
            self.verify()
        path.write_text(original+'3 0021\n', encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'extra actual HDMI pixels'):
            self.verify()

    def test_release_before_commit_is_rejected(self):
        path = self.work/'events.csv'
        path.write_text(path.read_text().replace('release,1,2,', 'release,1,0,'), encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'released before processing'):
            self.verify()

    def test_forged_publication_crc_is_rejected(self):
        path = self.work/'events.csv'
        path.write_text(path.read_text().replace(self.records[0]['ExpectedCRC32'], '00000000'), encoding='ascii')
        with self.assertRaisesRegex(ValueError, 'completion CRC differs'):
            self.verify()


if __name__ == '__main__':
    unittest.main()
