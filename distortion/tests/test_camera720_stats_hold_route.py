"""Focused proof-boundary tests; no native processes or physical permission."""
import copy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_hold_route as route


class StatisticsHoldRouteTest(unittest.TestCase):
    def target(self, branch='A0:CLMA_1_1', endpoint='first/I0'):
        return {'Net': 'nt_cam_href', 'FromRoutePin': 'DI_TO_CLK:IOLHR_1_1',
                'ToRoutePin': branch, 'Endpoint': endpoint, 'Fanout': 3}

    def inventories(self):
        targets = [self.target(), self.target('B0:CLMA_1_1', 'second/I0')]
        rows = [
            {'Net': 'nt_cam_href', 'Branch': targets[0]['ToRoutePin'], 'Pins': 'ZDNE[0]:SRB_1_2>IDNE[0]:SRB_3_4;'},
            {'Net': 'nt_cam_href', 'Branch': targets[1]['ToRoutePin'], 'Pins': 'ZDNE[1]:SRB_1_2>IDNE[1]:SRB_3_4;'}]
        before = {'NetAnnotations': {'nt_cam_href': 'old', 'elsewhere': 'unchanged'},
                  'BranchInventory': {'nt_cam_href': {'LogicalConnections': ['same'], 'Leaves': {
                      targets[0]['ToRoutePin']: ['source', 'shared', targets[0]['ToRoutePin']],
                      targets[1]['ToRoutePin']: ['source', 'shared', targets[1]['ToRoutePin']],
                      'C0:CLMA_1_1': ['source', 'shared', 'C0:CLMA_1_1']}}}}
        after = copy.deepcopy(before); after['NetAnnotations']['nt_cam_href'] = 'new'
        for row in rows:
            after['BranchInventory']['nt_cam_href']['Leaves'][row['Branch']] = ['source', *row['Pins'].rstrip(';').split('>'), row['Branch']]
        return before, after, targets, rows

    def test_two_selected_leaves_same_net_preserve_other_sibling(self):
        before, after, targets, rows = self.inventories()
        changed, checks = route.compare_inventory(before, after, targets, rows)
        self.assertEqual(changed, {'nt_cam_href'})
        self.assertEqual(checks[0]['UnrequestedSiblingsPreserved'], 1)

    def test_shared_prefix_change_rejected_when_unselected_leaf_affected(self):
        before, after, targets, rows = self.inventories()
        after['BranchInventory']['nt_cam_href']['Leaves']['C0:CLMA_1_1'][1] = 'different'
        with self.assertRaisesRegex(ValueError, 'sibling'):
            route.compare_inventory(before, after, targets, rows)

    def test_other_net_and_connection_and_leaf_changes_rejected(self):
        for kind in ('other_net', 'connection', 'leaf', 'missing_detour'):
            with self.subTest(kind=kind):
                before, after, targets, rows = self.inventories()
                if kind == 'other_net': after['NetAnnotations']['elsewhere'] = 'changed'
                if kind == 'connection': after['BranchInventory']['nt_cam_href']['LogicalConnections'] = ['different']
                if kind == 'leaf': after['BranchInventory']['nt_cam_href']['Leaves']['D0:CLMA_1_1'] = ['new']
                if kind == 'missing_detour': after['BranchInventory']['nt_cam_href']['Leaves'][rows[0]['Branch']] = ['source', 'shortcut', rows[0]['Branch']]
                with self.assertRaises(ValueError): route.compare_inventory(before, after, targets, rows)

    def test_input_attributes_do_not_hide_connections(self):
        tree = ['NET', 'nt_cam_href', ['FILEID', '25'], ['LINENUM', '12'],
                ['ATTRIBUTE', 'PAP_IO_STANDARD', ['STRING', 'LVCMOS33']],
                ['CONNECT', ['PORTREF', 'I0', ['INSTREF', '\\first']]]]
        self.assertEqual(route.logical_connections(tree), [{'Instance': 'first', 'Pin': 'I0'}])
        for bad in (['EXTRA', 'ignored'], ['FILEID', 'oops'], ['CONNECT']):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                route.logical_connections(tree+[bad])

    def test_multiple_input_leaves_have_unique_unused_waypoints(self):
        _, _, targets, rows = self.inventories()
        commands = route.route_commands(rows, targets, {})
        self.assertEqual(len(commands), 8)
        self.assertIn('unroute -branch {nt_cam_href:B0:CLMA_1_1;}', commands)
        for failure in ('occupied', 'shared', 'injection', 'unknown_net', 'duplicate'):
            altered = copy.deepcopy(rows); occupied = {}
            if failure == 'occupied': occupied['ZDNE[0]:SRB_1_2'] = ['existing']
            if failure == 'shared': altered[1]['Pins'] = altered[0]['Pins']
            if failure == 'injection': altered[0]['Pins'] += '\nexec something'
            if failure == 'unknown_net': altered[0]['Net'] = '_N49'
            if failure == 'duplicate': altered[1] = altered[0]
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                route.route_commands(altered, targets, occupied)

    def carry_graph(self):
        cells = {
            'low/FYA/LUT6CARRY': {'Primitive': 'V_LUT6CARRY', 'Ports': {'I0': 'nt_cam_href', 'COUT': 'carry'}},
            'high/FYB/LUT6CARRY': {'Primitive': 'V_LUT6CARRY', 'Ports': {'I0': 'state', 'CIN': 'carry', 'COUT': 'result'}}}
        graph = SimpleNamespace(cells=cells, outputs={'carry': [('low/FYA/LUT6CARRY', 'COUT')]})
        placements = {'low/FYA/LUT6CARRY': {'Site': 'CLMA_1_1', 'Attributes': 'PAP_BLE_DEF="A"'},
                      'high/FYB/LUT6CARRY': {'Site': 'CLMA_1_1', 'Attributes': 'PAP_BLE_DEF="B"'}}
        return graph, placements

    def test_carry_output_resolves_actual_preceding_control_input(self):
        graph, placements = self.carry_graph()
        def inputs(cell, output):
            self.assertEqual(output, 'COUT')
            return [pin for pin in cell['Ports'] if pin != 'COUT']
        with patch.object(route.graph_tools.cdc.endpoints, 'input_pins', side_effect=inputs):
            result = route.carry_input_leaves(graph, placements, 'high/COUT', 'nt_cam_href', 'CLMA_1_1')
        self.assertEqual(result['Endpoint'], 'low/I0')
        self.assertEqual(result['ToRoutePin'], 'A0:CLMA_1_1')
        self.assertEqual(len(result['Steps']), 2)

    def test_carry_nonadjacent_or_cross_site_or_ambiguous_input_rejected(self):
        for failure in ('nonadjacent', 'cross_site', 'ambiguous'):
            graph, placements = self.carry_graph()
            if failure == 'nonadjacent': placements['high/FYB/LUT6CARRY']['Attributes'] = 'PAP_BLE_DEF="C"'
            if failure == 'cross_site': placements['low/FYA/LUT6CARRY']['Site'] = 'CLMA_2_2'
            if failure == 'ambiguous': graph.cells['high/FYB/LUT6CARRY']['Ports']['I0'] = 'nt_cam_href'
            with patch.object(route.graph_tools.cdc.endpoints, 'input_pins', side_effect=lambda c, _: [k for k in c['Ports'] if k != 'COUT']):
                with self.subTest(failure=failure), self.assertRaises(ValueError):
                    route.carry_input_leaves(graph, placements, 'high/COUT', 'nt_cam_href', 'CLMA_1_1')

    def test_native_recipe_initializes_before_mutation_and_saves_copy(self):
        value = route.render(['unroute -branch {nt_cam_href:A0:CLMA_1_1;}'], Path('D:/isolated'))
        self.assertLess(value.index(route.INIT), value.index('unroute'))
        self.assertLess(value.index('post-init.adf'), value.index('unroute'))
        self.assertLess(value.index('save_adif'), value.index('saved-route.adf'))
        self.assertNotIn('set_false_path', value)
        self.assertNotIn('gen_bitstream', value)

    def test_success_requires_complete_route_and_source_evidence(self):
        value = {'Schema': route.SCHEMA, 'Target': route.prep.TARGET, 'ExitCode': 0, 'EDAExecuted': True,
                 'TimedOut': False, 'StoppedForUnexpectedStage': False, 'InputDrift': [], 'Diagnostics': [],
                 'ActualEvents': [], 'CompletionMarker': True, 'InitializationPreservedADF': True,
                 'SavedADFReadbackMatches': True, 'ResultADFChanged': True, 'Cleanup': {'Complete': True},
                 'RouteComparison': {'Passed': True}}
        self.assertTrue(route.execution_ok(value))
        for key, bad in [('InputDrift', ['drift']), ('Diagnostics', ['critical']), ('RouteComparison', {'Passed': False}),
                         ('InitializationPreservedADF', False), ('SavedADFReadbackMatches', False), ('ResultADFChanged', False)]:
            with self.subTest(key=key): self.assertFalse(route.execution_ok({**value, key: bad}))


if __name__ == '__main__':
    unittest.main()
