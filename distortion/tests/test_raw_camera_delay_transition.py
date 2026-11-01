"""Native worst-transition changes cannot waive clock/route or numeric checks."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import audit_raw_camera_delay_reset_effect as audit

FIXTURES = Path(__file__).parent / 'fixtures/raw_camera_delay_transition'


def record(name):
    path = FIXTURES / (name + '.txt')
    return audit.hold.common.parse_path(path.read_text(encoding='utf-8').splitlines(True), path, 1, detailed=False)


def evidence():
    return {**{k:True for k in ('FunctionalGraphIdentical', 'AllFFPlacementsIdentical',
        'AllInternalChecksMet', 'OnlyRequestedRoutingChanges', 'ExactNativeConstraintDeltaVerified',
        'ClockDefinitionsAndLoadsUnchanged', 'ExactResetExceptionUnionVerified', 'OtherExceptionsIdentical')},
        'ChangedNets':['_N199']}


class RepresentativeTests(unittest.TestCase):
    def setUp(self):
        self.old, self.new, self.context = record('baseline'), record('candidate'), evidence()

    def compare(self):
        return audit.compare_read_hold_representative(self.old, self.new, '_N199', self.context)

    def replace(self, before, after):
        text = ''.join(self.new['_Lines'])
        self.assertIn(before, text)
        self.new['_Lines'] = text.replace(before, after).splitlines(True)

    def test_real_native_switch_and_explicit_limits(self):
        result = self.compare()
        self.assertTrue(result['NativeWorstTransitionRepresentativeChanged'])
        self.assertFalse(result['SameTransitionVariantProved'])
        self.assertFalse(result['OnlyRepairedNetDelayChanged'])
        self.assertEqual(result['ArrivalDeltaNS'], .425)
        self.assertEqual(result['RequiredTimeDeltaNS'], -.003)
        self.assertEqual(result['SlackDeltaNS'], .428)

    def test_each_independent_proof_required(self):
        for flag in self.context:
            if flag == 'ChangedNets':continue
            with self.subTest(flag=flag):
                modified = copy.deepcopy(self.context); modified[flag] = False
                with self.assertRaisesRegex(ValueError, 'independent'):
                    audit.compare_read_hold_representative(self.old, self.new, '_N199', modified)

    def test_additional_route_rejected(self):
        self.context['ChangedNets'].append('upstream')
        with self.assertRaisesRegex(ValueError, 'independent'):self.compare()

    def test_wrong_target_net_rejected(self):
        with self.assertRaisesRegex(ValueError, 'not the observed'):
            audit.compare_read_hold_representative(self.old, self.new, '_N200', self.context)

    def test_clock_edge_change_rejected(self):
        self.replace('Clock phy_dq_sysclk_1 (rising edge)', 'Clock phy_dq_sysclk_1 (falling edge)')
        with self.assertRaisesRegex(ValueError, 'not the observed'):self.compare()

    def test_clock_numeric_change_rejected(self):
        self.replace('clock uncertainty                                       0.450',
                     'clock uncertainty                                       0.451')
        with self.assertRaisesRegex(ValueError, 'non-data text'):self.compare()

    def test_wrong_endpoint_rejected(self):
        self.replace('rddata_r1[63]', 'rddata_r1[62]')
        with self.assertRaisesRegex(ValueError, 'not the observed'):self.compare()

    def test_changed_physical_data_chain_rejected(self):
        self.replace('CLMA_351_702/CR1', 'CLMA_352_702/CR1')
        with self.assertRaisesRegex(ValueError, 'connectivity'):self.compare()

    def test_unobserved_transition_pattern_rejected(self):
        self.replace('4.194 f', '4.194 r')
        with self.assertRaisesRegex(ValueError, 'transition pattern'):self.compare()

    def test_data_cumulative_error_rejected(self):
        self.replace('4.194 f', '4.204 f')
        with self.assertRaisesRegex(ValueError, 'cumulative'):self.compare()

    def test_logic_total_error_rejected(self):
        self.replace('Logic: 0.279ns', 'Logic: 0.289ns')
        with self.assertRaisesRegex(ValueError, 'logic total'):self.compare()

    def test_route_total_error_rejected(self):
        self.replace('Route: 1.024ns', 'Route: 1.034ns')
        with self.assertRaisesRegex(ValueError, 'route total'):self.compare()

    def test_percentage_error_rejected(self):
        self.replace('21.412%', '22.412%')
        with self.assertRaisesRegex(ValueError, 'percentage'):self.compare()

    def test_required_time_error_rejected(self):
        self.replace('4.681', '4.691')
        with self.assertRaisesRegex(ValueError, 'hold arc cumulative'):self.compare()

    def test_hold_arc_error_rejected(self):
        self.replace('Hold time                                              -0.028',
                     'Hold time                                              -0.038')
        with self.assertRaisesRegex(ValueError, 'hold arc cumulative'):self.compare()

    def test_slack_error_rejected(self):
        self.replace('0.308', '0.408')
        with self.assertRaisesRegex(ValueError, 'hold slack'):self.compare()

    def test_inconsistent_slack_metadata_rejected(self):
        self.new['SlackNS'] = .408
        with self.assertRaisesRegex(ValueError, 'slack metadata'):self.compare()


if __name__ == '__main__':unittest.main()
