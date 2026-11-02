"""New recovery report dialect coverage; never execute a native process."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import audit_camera720_timing_inventory as parser


BASE = '''Startpoint : power_ready/opit/CLK
Endpoint : camera_configuration/monitor/p_reset[0]/opit/RS
Path Group : camera_pclk
Path Type : max (slow corner)
Path Class : async timing path
{clock}
 Recovery time -0.2 7.8
 Slack (MET) 4.0
'''
EXCEPTION = 'Timing Exception : MaxDelay Path 8.000ns -datapath_only\nException constraint line number: 713'


class RecoveryParserTests(unittest.TestCase):
    def test_clockless_datapath_does_not_invent_clock_or_edge(self):
        value = parser.recovery_record(BASE.format(clock=EXCEPTION).splitlines(keepends=True))
        self.assertTrue(value['DatapathOnly'])
        self.assertFalse(value['ClockEdgesPresent'])
        self.assertIsNone(value['LaunchClock'])
        self.assertIsNone(value['CaptureClock'])
        self.assertIsNone(value['LaunchEdge'])
        self.assertEqual(value['PathGroup'], 'camera_pclk')
        self.assertEqual(value['MaximumDatapathNS'], '8.000')
        self.assertEqual(value['ConstraintLine'], 713)

    def test_normal_recovery_preserves_actual_edges(self):
        text = BASE.format(clock=' Clock board27 (rising edge) 0.0\n Clock camera_pclk (falling edge) 0.0')
        value = parser.recovery_record(text.splitlines(keepends=True))
        self.assertFalse(value['DatapathOnly'])
        self.assertTrue(value['ClockEdgesPresent'])
        self.assertEqual(value['LaunchClock'], 'board27')
        self.assertEqual(value['CaptureEdge'], 'falling')

    def test_missing_or_one_clock_without_exception_rejected(self):
        for clock in ('', ' Clock camera_pclk (rising edge) 0.0'):
            with self.subTest(clock=clock), self.assertRaises(ValueError):
                parser.recovery_record(BASE.format(clock=clock).splitlines(keepends=True))

    def test_unsupported_exception_or_duplicate_exception_rejected(self):
        for clock in (EXCEPTION.replace('-datapath_only', ''),
                      EXCEPTION.replace('MaxDelay Path 8.000ns -datapath_only', 'False Path'),
                      EXCEPTION+'\n'+EXCEPTION):
            with self.subTest(clock=clock), self.assertRaises(ValueError):
                parser.recovery_record(BASE.format(clock=clock).splitlines(keepends=True))

    def test_missing_constraint_identity_rejected(self):
        text = BASE.format(clock=EXCEPTION.replace('Exception constraint line number: 713', ''))
        with self.assertRaises(ValueError):
            parser.recovery_record(text.splitlines(keepends=True))

    def test_partial_or_duplicate_clock_rows_rejected(self):
        for clock in (EXCEPTION+'\n Clock camera_pclk (rising edge) 0.0',
                      EXCEPTION+'\n Clock board27 (rising edge) 0.0\n Clock camera_pclk (rising edge) 0.0'):
            with self.subTest(clock=clock), self.assertRaises(ValueError):
                parser.recovery_record(BASE.format(clock=clock).splitlines(keepends=True))


if __name__ == '__main__':
    unittest.main()
