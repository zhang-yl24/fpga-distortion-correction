"""Reject synthetic-only tone modes when summarizing physical optical evidence."""
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('session_record',ROOT/'tools/record-session-20261008.py')
record=importlib.util.module_from_spec(spec);spec.loader.exec_module(record)

def capture(mode=2,origin='optical_camera_scene',kind='physical_same_source',hardware=True,passed=True):
    return {'passed':passed,'hardware_accessed':hardware,'source_kind':kind,'input_origin':origin,
        'groups':[{'mode':mode,'passed':passed}]}

class ScopeTests(unittest.TestCase):
    def test_physical_optical(self):self.assertEqual(record.optical_modes([capture()]),[2])
    def test_sensor_pattern(self):self.assertEqual(record.optical_modes([capture(origin='sensor_internal_test_pattern',kind='synthetic_same_source')]),[])
    def test_replay(self):self.assertEqual(record.optical_modes([capture(origin='offline_replay',hardware=False)]),[])
    def test_failed(self):self.assertEqual(record.optical_modes([capture(passed=False)]),[])
    def test_historical_missing_origin(self):
        c=capture();del c['input_origin'];self.assertEqual(record.optical_modes([c]),[2])
    def test_mixed_does_not_promote_mode2(self):
        self.assertEqual(record.optical_modes([capture(mode=1),capture(origin='sensor_internal_test_pattern',kind='synthetic_same_source')]),[1])

if __name__=='__main__':unittest.main()
