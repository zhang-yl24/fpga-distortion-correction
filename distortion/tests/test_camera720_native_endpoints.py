"""Regression checks for packed FF identity and native boundary causality."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_native_endpoints as subject


def fixture():
    def ff(q, d):
        return {'Primitive': 'V_FFASYN', 'Parameters': {},
                'Ports': {'Q': q, 'D': d, 'CK': 'clock', 'CE': "1'b1", 'SR': "1'b0"}}
    cells = {
        'source/FF3/FF': ff('other_q', 'unused'),
        'source/FFAPP3/FF': ff('request', 'unused'),
        'edge4/FF0/FF': ff('edge4_q', 'unused'),
        'edge3/FF0/FF': ff('edge3_q', 'unused'),
        'release/FF0/FF': ff('release_q', 'unused'),
        'target/FF3/FF': ff('request_sync', 'z'),
        'target/FFAPP3/FF': ff('edge_gray', 'z5'),
        'target/FYD/LUT6CARRY': {'Primitive': 'V_LUT6CARRY', 'Parameters': {
            'INIT': "64'hF0F0000050A050A0", 'I5_TO_LUT': '"TRUE"', 'I5_TO_CARRY': '"TRUE"'},
            'Ports': {'I0': 'edge4_q', 'I1': "1'b1", 'I2': 'release_q', 'I3': 'edge3_q',
                      'I4': 'request', 'I5': "1'b1", 'CIN': "1'b0", 'Z': 'z', 'Z5': 'z5', 'COUT': ''}},
    }
    graph = subject.monitor.Graph({'Cells': cells, 'FFPlacement': {n: {'Site': n, 'Attributes': ''}
                                  for n, c in cells.items() if c['Primitive'] == 'V_FFASYN'}})
    portdirs = {'CLK': 'INPUT', 'D': 'INPUT', 'CE': 'INPUT', 'RS': 'INPUT',
                **{'I'+str(i): 'INPUT' for i in range(6)}, 'CIN': 'INPUT',
                'Q': 'OUTPUT', 'L5Q': 'OUTPUT', 'L6Q': 'OUTPUT'}
    route = {'Cells': {'c': {'Operator': 'gop', 'Ports': portdirs, 'Parameters': []}},
             'Instances': {p: {'Cell': 'c', 'Operator': 'gop'} for p in ('source', 'edge4', 'edge3', 'release', 'target')},
             'Pins': {('source', 'CLK'): 'clock', ('source', 'L5Q'): 'request', ('source', 'L6Q'): 'other_q',
                      ('edge4', 'CLK'): 'clock', ('edge4', 'Q'): 'edge4_q',
                      ('edge3', 'CLK'): 'clock', ('edge3', 'Q'): 'edge3_q',
                      ('release', 'CLK'): 'clock', ('release', 'Q'): 'release_q',
                      ('target', 'I0'): 'edge4_q', ('target', 'I2'): 'release_q',
                      ('target', 'I3'): 'edge3_q', ('target', 'I4'): 'request',
                      ('target', 'CLK'): 'clock', ('target', 'L6Q'): 'request_sync', ('target', 'L5Q'): 'edge_gray'}}
    return graph, route


def relation(source='source/FFAPP3/FF', target='target/FF3/FF', pin='D'):
    return {'SourceFF': source, 'DestinationFF': target, 'DestinationPin': pin}


class PackedEndpoints(unittest.TestCase):
    def test_main_and_app_have_different_logical_input_support(self):
        graph, route = fixture()
        mapper = subject.Mapper(graph, route)
        main = mapper.map(relation())
        self.assertEqual(main['SourceNativeOutputPin'], 'source/L5Q')
        self.assertEqual([r['Endpoint'] for r in main['NativeBoundaries']], ['target/I4'])
        app = mapper.map(relation('edge4/FF0/FF', 'target/FFAPP3/FF'))
        self.assertEqual([r['Endpoint'] for r in app['NativeBoundaries']], ['target/I0'])
        with self.assertRaisesRegex(ValueError, 'reaches no selected'):
            mapper.map(relation('edge4/FF0/FF'))

    def test_parent_clock_cannot_substitute_other_packed_launch(self):
        graph, route = fixture()
        with self.assertRaisesRegex(ValueError, 'reaches no selected'):
            subject.Mapper(graph, route).map(relation('source/FF3/FF'))

    def test_connected_lut_input_must_match_native_net(self):
        graph, route = fixture()
        route['Pins']['target', 'I4'] = 'other_q'
        with self.assertRaisesRegex(ValueError, 'connectivity differs'):
            subject.Mapper(graph, route).map(relation())

    def test_tied_inactive_input_cannot_alias_active_main_input(self):
        graph, route = fixture()
        # I0 belongs only to Z5, even if routed to the same request as Z's I4.
        graph.cells['target/FYD/LUT6CARRY']['Ports']['I0'] = 'request'
        route['Pins']['target', 'I0'] = 'request'
        graph = subject.monitor.Graph(graph.g)
        mapped = subject.Mapper(graph, route).map(relation())
        self.assertEqual([r['Endpoint'] for r in mapped['NativeBoundaries']], ['target/I4'])

    def test_ambiguous_launch_output_is_rejected(self):
        graph, route = fixture()
        route['Pins']['source', 'Q'] = 'request'
        with self.assertRaisesRegex(ValueError, 'unique native output'):
            subject.Mapper(graph, route).map(relation())

    def test_native_init_must_match_functional_mux_truth(self):
        graph, route = fixture()
        route['Cells']['c']['Parameters'] = [['PARAMETER', 'INIT', ['DATATYPE', 'BITVEC'],
            ['BITVEC', ['B', '64', '"'+format(0xF0F0000050A050A0, '064b')+'"']]]]
        mapped = subject.Mapper(graph, route).map(relation())
        bindings = subject.native_lut_bindings(graph, route, [mapped])
        self.assertTrue(bindings['target/FYD/LUT6CARRY']['INITMatches'])
        route['Cells']['c']['Parameters'][0][3][1][2] = '"'+'0'*64+'"'
        with self.assertRaisesRegex(ValueError, 'INIT differs'):
            subject.native_lut_bindings(graph, route, [mapped])

    def test_all_reachable_boundary_pins_are_retained(self):
        graph, route = fixture()
        # The same logical request reaches both OR inputs via separate external
        # buffers.  Looking up only one endpoint would leave a real path out.
        graph.cells['target/FYD/LUT6CARRY']['Parameters']['INIT'] = "64'hEEEEEEEEEEEEEEEE"
        graph.cells['target/FYD/LUT6CARRY']['Ports'].update(I0='buffer_a', I1='buffer_b')
        graph.cells.update({n: {'Primitive': 'V_BUF', 'Parameters': {}, 'Ports': {'I': 'request', 'Z': net}}
                            for n, net in [('buffer1', 'buffer_a'), ('buffer2', 'buffer_b')]})
        graph = subject.monitor.Graph(graph.g)
        route['Pins']['target', 'I0'] = 'buffer_a'
        route['Pins']['target', 'I1'] = 'buffer_b'
        mapped = subject.Mapper(graph, route).map(relation())
        self.assertEqual([r['Endpoint'] for r in mapped['NativeBoundaries']], ['target/I0', 'target/I1'])

    def test_enable_consumer_is_separate_from_data(self):
        graph, route = fixture()
        graph.ff['target/FF3/FF']['Ports']['CE'] = 'request'
        route['Pins']['target', 'CE'] = 'request'
        mapped = subject.Mapper(graph, route).map(relation(pin='CE'))
        # Direct FF CE must select CE, not the unrelated tied I4 data input.
        self.assertEqual([r['Endpoint'] for r in mapped['NativeBoundaries']], ['target/CE'])

    def test_carry_mux_and_inactive_input_are_respected(self):
        graph, _ = fixture()
        lut = copy.deepcopy(graph.cells['target/FYD/LUT6CARRY'])
        lut['Parameters']['INIT'] = "64'h00000000FFFFFFFF"
        lut['Ports'].update(CIN='carry', I5='inactive')
        self.assertEqual(subject.input_pins(lut, 'COUT'), ['CIN'])
        lut['Parameters']['I5_TO_LUT'] = '"FALSE"'
        self.assertEqual(subject.input_pins(lut, 'Z'), ['CIN'])

    def test_intra_clm_carry_alias_requires_both_actual_route_pins(self):
        graph, route = fixture()
        carry = copy.deepcopy(graph.cells['target/FYD/LUT6CARRY'])
        carry['Parameters']['INIT'] = "64'h0000000000000000"
        carry['Ports'].update(I5='request', COUT='site/carry', Z='', Z5='')
        graph.cells['carry/FYA/LUT6CARRY'] = carry
        graph.cells['target/FYD/LUT6CARRY']['Parameters'].update(INIT="64'hFFFFFFFF00000000", I5_TO_LUT='"FALSE"')
        graph.cells['target/FYD/LUT6CARRY']['Ports']['CIN'] = 'site/carry'
        graph = subject.monitor.Graph(graph.g)
        route['Instances']['carry'] = {'Cell': 'c', 'Operator': 'gop'}
        route['Cells']['c']['Ports']['COUT'] = 'OUTPUT'
        route['Pins']['carry', 'COUT'] = 'native_carry'
        route['Pins']['target', 'CIN'] = 'native_carry'
        mapped = subject.Mapper(graph, route).map(relation())
        self.assertEqual([r['Endpoint'] for r in mapped['NativeBoundaries']], ['target/CIN'])
        self.assertEqual(mapped['NativeBoundaries'][0]['NetAliasProof']['NativeDriver'], 'carry/COUT')
        route['Pins']['target', 'CIN'] = 'wrong_carry'
        with self.assertRaisesRegex(ValueError, 'does not reach destination CIN'):
            subject.Mapper(graph, route).map(relation())


class NativeDump(unittest.TestCase):
    text = '''(ADIF "fixture"
      (CELL gopCell (OPERAREF gop)
        (VIEW OPER (VIEWTYPE OPERATOR)
          (INTERFACE (PORT I4 (DIRECTION INPUT)) (PORT L5Q (DIRECTION OUTPUT)))))
      (INSTANCE target (VIEWREF OPER (CELLREF gopCell (OPERAREF gop (LIBRARYREF pango_lib)))))
      (NET (ARRAY \\request 1 0)
        (CONNECT (NETREF (INDEXED \\request 0)) (PORTREF I4 (INSTREF target))))
    )
    '''

    def parse(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'dump.txt'
            path.write_text(text, encoding='ascii')
            return subject.route_objects(path, {'target'})

    def test_indexed_route_connect_is_preserved(self):
        self.assertEqual(self.parse(self.text)['Pins'], {('target', 'I4'): 'request[0]'})

    def test_duplicate_pin_binding_is_rejected(self):
        changed = self.text.replace('(PORTREF I4 (INSTREF target))',
                                    '(PORTREF I4 (INSTREF target)) (PORTREF I4 (INSTREF target))')
        with self.assertRaisesRegex(ValueError, 'connected more than once'):
            self.parse(changed)

    def test_truncated_dump_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'incomplete route dump'):
            self.parse(self.text.rsplit(')', 1)[0])


if __name__ == '__main__':
    unittest.main()
