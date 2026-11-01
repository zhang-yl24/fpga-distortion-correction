"""Reject route requests unsupported by the actual chip edge/official rule."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import run_raw_camera_route_reset as route


class WaypointEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.wire = Path(self.temp.name) / 'wirepattern.txt'
        rule = 'ZDNE[0] : vertical { h1 9 : 10 : 1 1 { vertical [ IDNE[0] ] } }'
        self.wire.write_text(rule + '\n')
        self.target = {'Net': '_N12', 'ToRoutePin': 'M0:CLMA_1_2'}
        self.proof = {'From': 'ZDNE[1]:SRB_10_20', 'To': 'IDNE[1]:SRB_16_26', 'Owner': '_N20', 'Line': 34}
        pins = ['ZDNE[0]:SRB_10_20', 'IDNE[0]:SRB_16_26']
        self.row = {'Net': '_N12', 'Branch': 'M0:CLMA_1_2', 'Pins': '>'.join(pins) + ';'}
        self.evidence = {'Schema': 'raw-camera-waypoint-selection-v1',
            'WirePattern': {'Path': str(self.wire.resolve()), 'SHA256': route.sha(self.wire)},
            'Selections': [{'Target': self.target, 'Selected': {'Pins': pins,
                'CoordinateProof': self.proof, 'OfficialWireRule': {'Line': 1, 'Text': rule}}}]}
        self.parsed = {'_ObservedNE': {(10, 20, 16, 26): [self.proof]}, '_Occupied': {}}

    def check(self):
        with patch.object(route.routes.common, 'WIRE_DEFAULT', self.wire):
            route.validate_waypoint_evidence(self.evidence, [self.row], [self.target], self.parsed)

    def test_unused_channel_at_observed_coordinate_is_valid(self):
        self.check()

    def test_unknown_coordinate_edge_rejected(self):
        self.parsed['_ObservedNE'].clear()
        with self.assertRaisesRegex(ValueError, 'coordinate edge'):
            self.check()

    def test_changed_official_rule_rejected(self):
        self.evidence['Selections'][0]['Selected']['OfficialWireRule']['Text'] = 'fabricated'
        with self.assertRaisesRegex(ValueError, 'NE rule'):
            self.check()

    def test_occupied_waypoint_rejected(self):
        self.parsed['_Occupied']['ZDNE[0]:SRB_10_20'] = ['other']
        with self.assertRaisesRegex(ValueError, 'no longer unused'):
            self.check()

    def test_different_requested_branch_rejected(self):
        self.row['Branch'] = 'M0:CLMA_9_9'
        with self.assertRaisesRegex(ValueError, 'target differs'):
            self.check()

    def test_wrong_channel_pair_rejected(self):
        self.evidence['Selections'][0]['Selected']['Pins'][1] = 'IDNE[1]:SRB_16_26'
        self.row['Pins'] = 'ZDNE[0]:SRB_10_20>IDNE[1]:SRB_16_26;'
        with self.assertRaisesRegex(ValueError, 'channel pairs'):
            self.check()


if __name__ == '__main__':
    unittest.main()
