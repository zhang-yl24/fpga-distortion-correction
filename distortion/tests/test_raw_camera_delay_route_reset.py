"""Bind only the measured d3 branch and independently proved constraints."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import run_raw_camera_delay_route_reset as route
import run_raw_camera_delay_derived_inspect as derived


class RouteScopeTests(unittest.TestCase):
    def setUp(self):
        self.target = {'Net':'_N199', 'ToRoutePin':'M2:CLMS_351_709'}
        self.row = {'Net':'_N199', 'Branch':'M2:CLMS_351_709',
                    'Pins':'ZDNE[0]:SRB_288_660>IDNE[0]:SRB_294_666;'}

    def test_measured_branch_emits_only_local_route_commands(self):
        commands = route.route_commands([self.row], [self.target], {})
        self.assertEqual(len(commands), 4)
        self.assertEqual(commands[1], 'unroute -branch {_N199:M2:CLMS_351_709;}')
        self.assertNotIn('save_adif', '\n'.join(commands))
        self.assertNotIn('set_false_path', '\n'.join(commands))

    def test_missing_current_failure_rejected(self):
        with self.assertRaisesRegex(ValueError, 'all current failing'):
            route.route_commands([], [self.target], {})

    def test_unmeasured_branch_rejected(self):
        self.row['Branch'] = 'M0:CLMA_1_2'
        with self.assertRaisesRegex(ValueError, 'unmeasured'):
            route.route_commands([self.row], [self.target], {})

    def test_occupied_waypoint_rejected(self):
        with self.assertRaisesRegex(ValueError, 'occupied'):
            route.route_commands([self.row], [self.target], {'IDNE[0]:SRB_294_666':['other']})

    def test_duplicate_failure_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate measured'):
            route.route_commands([self.row, self.row], [self.target, self.target], {})

    def test_command_injection_is_not_a_waypoint(self):
        self.row['Pins'] += '\nset_false_path -from [all_clocks]'
        with self.assertRaisesRegex(ValueError, 'invalid waypoint'):
            route.route_commands([self.row], [self.target], {})

    def test_one_pre_save_sta_and_no_post_save_sta(self):
        resets = ['set_false_path -from [get_pins {source/CLK}] -to [get_pins {sink/RS}]']
        text = route.render(route.route_commands([self.row], [self.target], {}), resets,
                            route.prep.WORK / 'not-created-route-render-test')
        self.assertEqual(text.count(route.physical.INIT), 1)
        self.assertEqual(text.count('save_adif'), 1)
        self.assertLess(text.index(route.physical.INIT), text.index('manual_route'))
        self.assertLess(text.index(resets[0]), text.index('save_adif'))
        self.assertLess(text.index('save_adif'), text.index('.switch_db'))
        self.assertNotIn('generate_bitstream', text)


class WaypointProofTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.wire = Path(temp.name) / 'wirepattern.txt'
        rule = 'ZDNE[0] : vertical { h1 9 : 10 : 1 1 { vertical [ IDNE[0] ] } }'
        self.wire.write_text(rule + '\n')
        self.target = {'Net':'_N199', 'ToRoutePin':'M2:CLMS_351_709'}
        self.proof = {'From':'ZDNE[1]:SRB_288_660', 'To':'IDNE[1]:SRB_294_666', 'Owner':'other', 'Line':100}
        pins = ['ZDNE[0]:SRB_288_660', 'IDNE[0]:SRB_294_666']
        self.row = {'Net':'_N199', 'Branch':'M2:CLMS_351_709', 'Pins':'>'.join(pins)+';'}
        self.evidence = {'Schema':'raw-camera-waypoint-selection-v1',
                         'WirePattern':{'Path':str(self.wire.resolve()), 'SHA256':route.sha(self.wire)},
                         'Selections':[{'Target':self.target, 'Selected':{'Pins':pins,
                             'CoordinateProof':self.proof, 'OfficialWireRule':{'Line':1, 'Text':rule}}}]}
        self.parsed = {'_ObservedNE':{(288,660,294,666):[self.proof]}, '_Occupied':{}}

    def check(self):
        with patch.object(route.routes.common, 'WIRE_DEFAULT', self.wire):
            route.validate_waypoint_evidence(self.evidence, [self.row], [self.target], self.parsed)

    def test_actual_coordinate_and_official_rule_required(self):
        self.check()
        self.parsed['_ObservedNE'].clear()
        with self.assertRaisesRegex(ValueError, 'coordinate edge'):
            self.check()

    def test_rule_cannot_be_replaced(self):
        self.evidence['Selections'][0]['Selected']['OfficialWireRule']['Text'] = 'fabricated'
        with self.assertRaisesRegex(ValueError, 'official NE rule'):
            self.check()


class DerivedBindingTests(unittest.TestCase):
    def test_old_raw_route_receipt_rejected(self):
        path = route.prep.WORK / 'not-created-receipt/result.json'
        with patch.object(derived.inspect, 'canonical', return_value=path), patch.object(
                derived, 'read', return_value={'Schema':'raw-camera-route-reset-application-v1'}):
            with self.assertRaisesRegex(ValueError, 'unsupported input-delay mutation'):
                derived.bind_source_receipt(path, {})

    def test_new_route_requires_completed_rebind(self):
        path = route.prep.WORK / 'not-created-receipt/result.json'
        with patch.object(derived.inspect, 'canonical', return_value=path), patch.object(
                derived, 'read', return_value={'Schema':route.SCHEMA}), patch.object(
                route, 'bind_completed', side_effect=ValueError('incomplete native evidence')) as rebound:
            with self.assertRaisesRegex(ValueError, 'incomplete native evidence'):
                derived.bind_source_receipt(path, {})
            rebound.assert_called_once_with(path, {})


if __name__ == '__main__': unittest.main()
