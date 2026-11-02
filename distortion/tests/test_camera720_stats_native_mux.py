"""Vendor-mux cone faults; no EDA or hardware."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_native_mux as mux
from test_camera720_stats_io_cdc import fixture_graph


class StatsMuxTests(unittest.TestCase):
    def test_vendor_boolean_support(self):
        cell={'Primitive':'V_MUX2','Parameters':{},'Ports':{'I0':'a','I1':'b','SEL':'s','Z':'z'}}
        self.assertEqual(mux.inputs(cell,'Z'),{'a','b','s'})
        cell['Ports']['SEL']="1'b1";self.assertEqual(mux.inputs(cell,'Z'),{'b'})
        cell['Ports']['SEL']="1'b0";self.assertEqual(mux.inputs(cell,'Z'),{'a'})
        cell['Ports'].update(I1='a',SEL='s');self.assertEqual(mux.inputs(cell,'Z'),{'a'})

    def graph(self):
        base=fixture_graph();cells=deepcopy(base.g['Cells'])
        cells['core_statistics/mux']={'Primitive':'V_MUX2','Parameters':{},'Ports':{'I0':'state','I1':'count','SEL':'tx','Z':'selected'}}
        cells['core_statistics/tx/FF0/FF']['Ports']['D']='selected'
        graph=mux.Graph({'Cells':cells,'FFPlacement':{}});graph.clock_cache=base.clock_cache
        return graph

    def test_actual_mux_outputs_indexed_without_changing_graph(self):
        graph=self.graph();before=deepcopy(graph.g)
        self.assertEqual(graph.outputs['selected'],[('core_statistics/mux','Z')])
        self.assertEqual(mux.support(graph,'selected'),{('ff','core_statistics/state/FF0/FF'),
            ('ff','system/counter/FF0/FF'),('ff','core_statistics/tx/FF0/FF')})
        self.assertEqual(graph.g,before)

    def test_foreign_selector_is_visible_in_support(self):
        graph=self.graph();graph.cells['core_statistics/mux']['Ports']['SEL']='foreign'
        self.assertIn(('primary','foreign'),mux.support(graph,'selected'))

    def test_mux_cycle_and_unknown_parameter_rejected(self):
        graph=self.graph();graph.cells['core_statistics/mux']['Ports']['I0']='selected'
        with self.assertRaises(ValueError):mux.support(graph,'selected')
        graph=self.graph();graph.cells['core_statistics/mux']['Parameters']['UNKNOWN']='1'
        with self.assertRaises(ValueError):mux.Graph(graph.g)


if __name__=='__main__':unittest.main()
