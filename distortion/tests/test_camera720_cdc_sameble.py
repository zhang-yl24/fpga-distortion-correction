import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_cdc_sameble as subject


def fixture(direct=False):
    source, target, release = 'packed/FFAPP0/FF', 'packed/FF0/FF', 'release/FF0/FF'
    def ff(q, d):
        return {'Primitive': 'V_FFASYN', 'Parameters': {'INIT': "1'b0", 'SET_RESET': '"RESET"'},
                'Ports': {'Q': q, 'D': d, 'CK': 'clk_27m', 'CE': "1'b1", 'SR': "1'b0"}}
    cells = {source: ff('request', 'incoming'), target: ff('synced', 'request' if direct else 'z'),
             release: ff('local_release', "1'b1")}
    if not direct:
        cells['packed/FYA/LUT6CARRY'] = {'Primitive': 'V_LUT6CARRY',
            'Parameters': {'INIT': "64'h8888888888888888", 'I5_TO_LUT': '"TRUE"', 'I5_TO_CARRY': '"TRUE"'},
            'Ports': {'I0': 'request', 'I1': 'local_release', 'I2': "1'b1", 'I3': "1'b1",
                      'I4': "1'b1", 'I5': "1'b1", 'CIN': "1'b0", 'Z': 'z', 'Z5': '', 'COUT': ''}}
    placement = {'Site': 'CLMA_1_1', 'Attributes': 'B'}
    graph = subject.endpoints.monitor.Graph({'Cells': cells, 'FFPlacement': {source: placement, target: placement,
                                               release: {'Site': 'CLMA_2_2', 'Attributes': 'A'}}})
    params = [['PARAMETER', 'INIT', ['DATATYPE', 'BITVEC'],
               ['BITVEC', ['B', '64', '"'+format(0x8888888888888888, '064b')+'"']]]]
    native = {'Operator': 'gopPacked', 'Ports': {'CLK': 'INPUT', 'I0': 'INPUT', 'I1': 'INPUT',
                  'L5Q': 'OUTPUT', 'L6Q': 'OUTPUT'}, 'Parameters': params}
    pins = {('packed', 'CLK'): 'clk_27m', ('packed', 'L5Q'): 'request', ('packed', 'L6Q'): 'synced'}
    if not direct:
        pins.update({('packed', 'I0'): 'request', ('packed', 'I1'): 'local_release'})
    route = {'Cells': {'c': native}, 'Instances': {'packed': {'Cell': 'c', 'Operator': 'gopPacked'}}, 'Pins': pins}
    inv = {'Schema': 'camera720-native-endpoints-v1', 'CandidateADF': {'Path': 'candidate', 'SHA256': 'a'},
           'BuildPlanSHA256': 'b', 'Queries': [], 'SameBLEInterstageInventory': [{'SourceFF': source,
           'DestinationFF': target, 'DestinationPin': 'D', 'Label': 'test_chain', 'Placement': placement}]}
    return graph, route, inv


class SameBLEReview(unittest.TestCase):
    def test_direct_internal_pair_stays_separate_without_timing_acceptance(self):
        result = subject.derive(*fixture(direct=True))
        self.assertEqual(result['DirectInternalRelationships'], 1)
        self.assertEqual(result['Queries'], [])
        self.assertFalse(result['NativeTimingAccepted'])

    def test_routed_local_lut_pair_requires_four_ordinary_cases(self):
        result = subject.derive(*fixture())
        self.assertEqual(result['SupplementalApplicableCases'], 4)
        q, = result['Queries']
        self.assertEqual((q['Source'], q['LaunchOutput'], q['Endpoint']), ('packed/CLK', 'packed/L5Q', 'packed/I0'))
        self.assertEqual(q['Requirements'], {'Clock': 'board27', 'CheckKinds': ['setup', 'hold'], 'Corners': ['slow', 'fast']})
        self.assertFalse(result['HardwareReleaseAllowed'])

    def test_incorrect_native_clock_fails(self):
        g, r, v = fixture(); r['Pins']['packed', 'CLK'] = 'wrong_clock'
        with self.assertRaisesRegex(ValueError, 'CLK net'): subject.derive(g, r, v)

    def test_direct_pair_with_native_input_route_is_not_silently_excluded(self):
        g, r, v = fixture(direct=True); r['Pins']['packed', 'I0'] = 'request'
        with self.assertRaisesRegex(ValueError, 'native input route'): subject.derive(g, r, v)

    def test_native_lut_input_must_carry_exact_first_stage(self):
        g, r, v = fixture(); r['Pins']['packed', 'I0'] = 'wrong_request'
        with self.assertRaisesRegex(ValueError, 'connectivity differs'): subject.derive(g, r, v)

    def test_actual_lut_init_drift_fails(self):
        g, r, v = fixture(); r['Cells']['c']['Parameters'][0][3][1][2] = '"'+'0'*64+'"'
        with self.assertRaisesRegex(ValueError, 'INIT differs'): subject.derive(g, r, v)

    def test_duplicate_inventory_pair_fails(self):
        g, r, v = fixture(); v['SameBLEInterstageInventory'] *= 2
        with self.assertRaisesRegex(ValueError, 'duplicate/invalid'): subject.derive(g, r, v)

    def test_existing_native_requirement_is_not_duplicated(self):
        g, r, v = fixture(); v['Queries'] = [{'Source': 'packed/CLK', 'LaunchOutput': 'packed/L5Q', 'Endpoint': 'packed/I0'}]
        with self.assertRaisesRegex(ValueError, 'duplicates existing'): subject.derive(g, r, v)

    def test_foreign_release_domain_fails(self):
        g, r, v = fixture(); g.ff['release/FF0/FF']['Ports']['CK'] = 'cam_pclk'
        with self.assertRaisesRegex(ValueError, 'not local'): subject.derive(g, r, v)

    def test_replicated_reset_direct_branch_preserves_all_inventoried_sinks(self):
        g, r, v = fixture(direct=True)
        g.ff['packed/FFAPP0/FF']['Ports']['D'] = "1'b1"
        other = 'other/FF0/FF'
        g.cells[other] = copy.deepcopy(g.ff['packed/FF0/FF'])
        g.cells[other]['Ports']['Q'] = 'other_release'
        g.g['FFPlacement'][other] = {'Site': 'CLMA_9_9', 'Attributes': 'A'}
        g = subject.endpoints.monitor.Graph(g.g)
        v['LogicalRelationships'] = [{'SourceFF': 'packed/FFAPP0/FF', 'DestinationFF': other, 'DestinationPin': 'D'}]
        result = subject.derive(g, r, v)
        self.assertEqual(result['DirectInternalRelationships'], 1)
        self.assertEqual(result['DirectInternalRows'][0]['ReplicatedResetSecondStages'], [other, 'packed/FF0/FF'])
        v['LogicalRelationships'] = []
        with self.assertRaisesRegex(ValueError, 'complete inventory'): subject.derive(g, r, v)


if __name__ == '__main__':
    unittest.main()
