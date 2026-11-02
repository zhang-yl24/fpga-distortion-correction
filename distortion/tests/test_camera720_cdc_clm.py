"""Independent structural regression tests for physical-CLM carry boundaries."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_cdc_clm as subject


def fixture():
    e = subject.endpoints
    def ff(q, d):
        return {'Primitive': 'V_FFASYN', 'Parameters': {},
                'Ports': {'Q': q, 'D': d, 'CK': 'clock', 'CE': "1'b1", 'SR': "1'b0"}}
    def placement(site, b):
        return {'Site': site, 'Attributes': '(* PAP_BLE_DEF="'+b+'" *)'}
    cells = {'source/FF0/FF': ff('request', 'unused'),
             'external_buffer': {'Primitive': 'V_BUF', 'Parameters': {},
                                 'Ports': {'I': 'request', 'Z': 'external_carry'}}}
    lut_placements, ff_placements = {}, {'source/FF0/FF': placement('CLMS_0_0', 'A')}
    dirs = {'CLK': 'INPUT', 'D': 'INPUT', 'CE': 'INPUT', 'RS': 'INPUT',
            **{'I'+str(i): 'INPUT' for i in range(6)}, 'CIN': 'INPUT', 'COUT': 'OUTPUT', 'Q': 'OUTPUT'}
    params = [['PARAMETER', 'INIT', ['DATATYPE', 'BITVEC'],
               ['BITVEC', ['B', '64', '"'+format(0x55555555AAAAAAAA, '064b')+'"']]]]
    route = {'Cells': {'c': {'Operator': 'gop', 'Ports': dirs, 'Parameters': params}},
             'Instances': {'source': {'Cell': 'c', 'Operator': 'gop'}},
             'Pins': {('source', 'CLK'): 'clock', ('source', 'Q'): 'request'}}
    for i, b in enumerate('ABC'):
        parent = 'stage_'+b
        name = parent+'/FY'+b+'/LUT6CARRY'
        cin = 'external_carry' if i == 0 else 'local_carry_'+str(i-1)
        cells[name] = {'Primitive': 'V_LUT6CARRY',
            'Parameters': {'INIT': "64'h55555555AAAAAAAA", 'I5_TO_LUT': '"FALSE"', 'I5_TO_CARRY': '"TRUE"'},
            'Ports': {'I0': 'request', 'I1': "1'b0", 'I2': "1'b0", 'I3': "1'b0",
                      'I4': "1'b0", 'I5': "1'b0", 'CIN': cin,
                      'COUT': 'local_carry_'+str(i), 'Z': 'z_'+b, 'Z5': ''}}
        target = parent+'/FF'+str(i)+'/FF'
        cells[target] = ff('out_'+b, 'z_'+b)
        lut_placements[name] = placement('CLMS_1_1', b)
        ff_placements[target] = placement('CLMS_1_1', b)
        route['Instances'][parent] = {'Cell': 'c', 'Operator': 'gop'}
        route['Pins'].update({(parent, 'CLK'): 'clock', (parent, 'Q'): 'out_'+b,
            (parent, 'I0'): 'request', (parent, 'CIN'): cin, (parent, 'COUT'): 'local_carry_'+str(i)})
    graph = e.monitor.Graph({'Cells': cells, 'FFPlacement': ff_placements})
    return graph, route, lut_placements


def relation(target='stage_C/FF2/FF'):
    return {'SourceFF': 'source/FF0/FF', 'DestinationFF': target, 'DestinationPin': 'D'}


def inventory(graph, route):
    old = subject.endpoints.Mapper(graph, route)
    rows = [old.map(relation('stage_'+b+'/FF'+str(i)+'/FF')) for i, b in enumerate('ABC')]
    queries = []
    for i, row in enumerate(rows):
        for boundary in row['NativeBoundaries']:
            queries.append({'Source': row['SourceNativeClockPin'], 'LaunchOutput': row['SourceNativeOutputPin'],
                'Endpoint': boundary['Endpoint'], 'Requirements': {'Clock': 'board27',
                    'CheckKinds': ['setup', 'hold'], 'Corners': ['slow', 'fast']}, 'LogicalRelationships': [i]})
    return {'Schema': 'camera720-native-endpoints-v1', 'CandidateADF': {'SHA256': 'a'*64},
            'BuildPlanSHA256': 'b'*64, 'LogicalRelationships': rows, 'Queries': queries}


class PhysicalCLM(unittest.TestCase):
    def test_all_causal_inputs_of_preceding_ble_are_preserved(self):
        graph, route, placements = fixture()
        mapped = subject.Mapper(graph, route, placements).map(relation())
        self.assertEqual([b['Endpoint'] for b in mapped['NativeBoundaries']],
            ['stage_A/CIN', 'stage_A/I0', 'stage_B/I0', 'stage_C/I0'])
        cin = mapped['NativeBoundaries'][0]
        self.assertEqual([s['Input'] for s in cin['BoundaryToLogicalFF'][0]], ['CIN', 'CIN', 'CIN'])
        self.assertEqual([s['Output'] for s in cin['BoundaryToLogicalFF'][0]], ['Z', 'COUT', 'COUT'])
        self.assertEqual(cin['PhysicalCLMSite'], 'CLMS_1_1')

    def test_merging_preserves_every_actual_target_ff(self):
        graph, route, placements = fixture()
        original = inventory(graph, route)
        result = subject.derive(graph, route, original, placements)
        self.assertEqual(len(result['LogicalRelationships']), 3)
        self.assertEqual(len(result['Queries']), 4)
        by_pin = {q['Endpoint']: q['LogicalRelationships'] for q in result['Queries']}
        self.assertEqual(by_pin['stage_A/CIN'], [0, 1, 2])
        self.assertEqual(by_pin['stage_A/I0'], [0, 1, 2])
        self.assertEqual(by_pin['stage_B/I0'], [1, 2])
        self.assertEqual(by_pin['stage_C/I0'], [2])
        self.assertFalse(result['PhysicalTimingAggregationProved'])
        self.assertFalse(result['NativeTimingAccepted'])
        self.assertFalse(result['HardwareReleaseAllowed'])

    def test_wrong_native_carry_connection_rejected(self):
        graph, route, placements = fixture()
        route['Pins']['stage_B', 'COUT'] = 'unrelated'
        with self.assertRaisesRegex(ValueError, 'COUT/CIN connection differs'):
            subject.Mapper(graph, route, placements).map(relation())

    def test_internal_carry_rename_requires_actual_driver_and_consumer(self):
        graph, route, placements = fixture()
        for parent, next_parent, name in [('stage_A', 'stage_B', 'native_ab'),
                                         ('stage_B', 'stage_C', 'native_bc')]:
            route['Pins'][parent, 'COUT'] = name
            route['Pins'][next_parent, 'CIN'] = name
        mapper = subject.Mapper(graph, route, placements)
        mapped = mapper.map(relation())
        self.assertEqual([b['Endpoint'] for b in mapped['NativeBoundaries']],
                         ['stage_A/CIN', 'stage_A/I0', 'stage_B/I0', 'stage_C/I0'])
        self.assertEqual(mapper.carry_links['stage_C/CIN']['NativeNet'], 'native_bc')
        self.assertEqual(mapper.carry_links['stage_C/CIN']['NetAliasProof']['NativeDriver'], 'stage_B/COUT')
        route['Pins']['stage_C', 'CIN'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'does not reach destination CIN'):
            subject.Mapper(graph, route, placements).map(relation())

    def test_internal_carry_driver_must_be_native_output(self):
        graph, route, placements = fixture()
        route['Cells']['c']['Ports']['COUT'] = 'INPUT'
        with self.assertRaisesRegex(ValueError, 'driver direction differs'):
            subject.Mapper(graph, route, placements).map(relation())

    def test_wrong_native_input_connection_rejected(self):
        graph, route, placements = fixture()
        route['Pins']['stage_B', 'I0'] = 'unrelated'
        with self.assertRaisesRegex(ValueError, 'input connectivity differs'):
            subject.Mapper(graph, route, placements).map(relation())

    def test_cross_site_internal_carry_rejected(self):
        graph, route, placements = fixture()
        placements['stage_B/FYB/LUT6CARRY']['Site'] = 'CLMS_9_9'
        with self.assertRaisesRegex(ValueError, 'preceding BLE carry'):
            subject.Mapper(graph, route, placements).map(relation())

    def test_nonadjacent_ble_internal_carry_rejected(self):
        graph, route, placements = fixture()
        placements['stage_B/FYB/LUT6CARRY']['Attributes'] = '(* PAP_BLE_DEF="A" *)'
        with self.assertRaisesRegex(ValueError, 'preceding BLE carry'):
            subject.Mapper(graph, route, placements).map(relation())

    def test_external_cin_stops_at_site_boundary(self):
        graph, route, placements = fixture()
        mapped = subject.Mapper(graph, route, placements).map(relation('stage_A/FF0/FF'))
        self.assertEqual([b['Endpoint'] for b in mapped['NativeBoundaries']], ['stage_A/CIN', 'stage_A/I0'])

    def test_selected_lut_mux_controls_internal_carry_dependency(self):
        graph, route, placements = fixture()
        graph.cells['stage_C/FYC/LUT6CARRY']['Parameters']['I5_TO_LUT'] = '"TRUE"'
        graph = subject.endpoints.monitor.Graph(graph.g)
        mapped = subject.Mapper(graph, route, placements).map(relation())
        self.assertEqual([b['Endpoint'] for b in mapped['NativeBoundaries']], ['stage_C/I0'])

    def test_source_filtered_out_of_unrelated_preceding_inputs(self):
        graph, route, placements = fixture()
        other = copy.deepcopy(graph.ff['source/FF0/FF'])
        other['Ports']['Q'] = 'other'
        graph.cells['other/FF0/FF'] = other
        graph.g['FFPlacement']['other/FF0/FF'] = {'Site': 'CLMS_2_2', 'Attributes': '(* PAP_BLE_DEF="A" *)'}
        graph.cells['stage_B/FYB/LUT6CARRY']['Ports']['I0'] = 'other'
        route['Pins']['stage_B', 'I0'] = 'other'
        graph = subject.endpoints.monitor.Graph(graph.g)
        mapped = subject.Mapper(graph, route, placements).map(relation())
        self.assertEqual([b['Endpoint'] for b in mapped['NativeBoundaries']],
                         ['stage_A/CIN', 'stage_A/I0', 'stage_C/I0'])

    def test_merging_conflicting_requirements_rejected(self):
        graph, route, placements = fixture()
        original = inventory(graph, route)
        for q in original['Queries']:
            if q['LogicalRelationships'] == [2]: q['Requirements']['Clock'] = 'other_clock'
        with self.assertRaisesRegex(ValueError, 'conflicting timing requirements'):
            subject.derive(graph, route, original, placements)

    def test_logical_relationship_omission_rejected(self):
        graph, route, placements = fixture()
        original = inventory(graph, route)
        original['Queries'] = [q for q in original['Queries'] if q['LogicalRelationships'] != [2]]
        with self.assertRaisesRegex(ValueError, 'lacks logical relationship coverage'):
            subject.derive(graph, route, original, placements)

    def test_changed_native_lut_truth_rejected(self):
        graph, route, placements = fixture()
        original = inventory(graph, route)
        route['Cells']['c']['Parameters'][0][3][1][2] = '"'+'0'*64+'"'
        with self.assertRaisesRegex(ValueError, 'INIT differs'):
            subject.derive(graph, route, original, placements)

    def test_placement_parser_compares_complete_primitive(self):
        graph, _, _ = fixture()
        cell = graph.cells['stage_A/FYA/LUT6CARRY']
        graph = subject.endpoints.monitor.Graph({'Cells': {'stage_A/FYA/LUT6CARRY': cell}, 'FFPlacement': {}})
        params = ','.join('.'+p+'('+v+')' for p,v in cell['Parameters'].items())
        ports = ','.join('.'+p+'('+v+')' for p,v in cell['Ports'].items())
        text = '(* PAP_BLE_DEF="A" *) V_LUT6CARRY /* CLMS_1_1 */ #('+params+') \\stage_A/FYA/LUT6CARRY ('+ports+');'
        self.assertEqual(subject.placed_luts(text, graph)['stage_A/FYA/LUT6CARRY']['Site'], 'CLMS_1_1')
        with self.assertRaisesRegex(ValueError, 'differs from functional graph'):
            subject.placed_luts(text.replace('external_carry', 'wrong'), graph)
        with self.assertRaisesRegex(ValueError, 'incomplete placed LUT evidence'):
            subject.placed_luts('', graph)


if __name__ == '__main__':
    unittest.main()
