"""Reject physical input delay bypasses, bit swaps and stale timing evidence."""
from collections import defaultdict
import copy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import audit_raw_camera_delay_io_cdc as audit


class DelayMappingTests(unittest.TestCase):
    def setUp(self):
        self.cells = {}
        self.declarations = 'module raw_camera_capture_cam2_delay; endmodule'
        self.domain = 'camera_pclk'
        for bit in range(8):
            middle, output = f'input_buffer_{bit}', f'capture_data[{bit}]'
            self.cells[f'buffer{bit}'] = {'Primitive':'V_IBUF',
                'Parameters':{'IOSTANDARD':'"LVCMOS33"', 'TERM_DDR':'"ON"'},
                'Ports':{'I':f'cam_data[{bit}]', 'O':middle}}
            self.cells[f'delay{bit}'] = {'Primitive':'V_ZEROHOLDDELAY',
                'Parameters':{'ZHOLD_SET':'"1500ps"'}, 'Ports':{'DI':middle, 'DO':output}}
            for prefix in ('picture/receiver', 'pipeline/bridge/capture'):
                for kind,index in (('first_byte',bit), ('pixel',bit+8)):
                    self.cells[f'{prefix}/{kind}[{index}]/FF'] = {'Primitive':'V_FFSYN',
                        'Parameters':{}, 'Ports':{'D':output, 'Q':f'{prefix}_{kind}_{index}', 'CK':'cam_clock'}}

    def check(self):
        refs = defaultdict(list)
        for name, cell in self.cells.items():
            for pin, value in cell['Ports'].items(): refs[value].append((name, pin))
        graph = SimpleNamespace(cells=self.cells, refs=refs,
            ff={n:c for n,c in self.cells.items() if c['Primitive'] == 'V_FFSYN'},
            g={'ModuleDeclarations':self.declarations}, clock=lambda _: {'Domain':self.domain})
        return audit.input_delay_structures(graph)

    def test_exact_eight_bit_chain_passes(self):
        result = self.check()
        self.assertEqual(result['ReceiverEndpoints'], 32)
        self.assertTrue(result['AllConsumersUseDelayedData'])
        self.assertFalse(result['ActualPVTDelayFromSettingAloneProven'])

    def test_wrong_physical_delay_rejected(self):
        self.cells['delay0']['Parameters']['ZHOLD_SET'] = '"NODELAY"'
        with self.assertRaisesRegex(ValueError, 'setting'): self.check()

    def test_missing_delay_rejected(self):
        del self.cells['delay7']
        with self.assertRaisesRegex(ValueError, 'eight'): self.check()

    def test_pad_bypass_rejected(self):
        self.cells['bypass'] = {'Primitive':'V_BUF','Parameters':{},'Ports':{'I':'cam_data[3]','Z':'bad'}}
        with self.assertRaisesRegex(ValueError, 'pad bypasses'): self.check()

    def test_buffer_bypass_rejected(self):
        self.cells['bypass'] = {'Primitive':'V_BUF','Parameters':{},'Ports':{'I':'input_buffer_2','Z':'bad'}}
        with self.assertRaisesRegex(ValueError, 'buffer bypasses'): self.check()

    def test_bit_swapped_delay_rejected(self):
        self.cells['delay0']['Ports']['DO'], self.cells['delay1']['Ports']['DO'] = 'capture_data[1]', 'capture_data[0]'
        with self.assertRaises(ValueError): self.check()

    def test_extra_delayed_data_consumer_rejected(self):
        self.cells['bypass'] = {'Primitive':'V_BUF','Parameters':{},'Ports':{'I':'capture_data[2]','Z':'bad'}}
        with self.assertRaisesRegex(ValueError, 'unexpected drivers or consumers'): self.check()

    def test_bus_expression_cannot_hide_from_scalar_refs(self):
        self.cells['bypass'] = {'Primitive':'V_BUF','Parameters':{},'Ports':{'I':'{cam_data[2]}','Z':'bad'}}
        with self.assertRaisesRegex(ValueError, 'exact scalar'): self.check()

    def test_whole_bus_reference_rejected(self):
        self.cells['bypass'] = {'Primitive':'V_BUF','Parameters':{},'Ports':{'I':'cam_data','Z':'bad'}}
        with self.assertRaisesRegex(ValueError, 'exact scalar'): self.check()

    def test_hidden_alias_rejected(self):
        self.declarations += ' assign bad = cam_data[1];'
        with self.assertRaisesRegex(ValueError, 'aliases'): self.check()

    def test_sampled_clock_must_be_camera(self):
        self.domain = 'pixel_clk'
        with self.assertRaisesRegex(ValueError, 'another domain'): self.check()


class TimingCoverageTests(unittest.TestCase):
    def test_absent_corner_stays_pending(self):
        rows = [{'Label':'gray[0]', 'Source':'fifo/source/FF3/FF', 'NativeEndpoint':'fifo/meta/D',
                 'SourceClock':'camera_pclk', 'DestinationClock':'ddrphy_sysclk'}]
        paths = [{'Source':'fifo/source/CLK','Endpoint':'fifo/meta/D','Corner':'slow',
                  'BoundNS':8.0,'SlackNS':5.0,'ArrivalNS':3.0}]
        with patch.object(audit.cdc, 'max_delay_paths', return_value=(paths, {})):
            _, missing, _ = audit.coverage(rows, Path('unused'),
                {'PeriodsNS':{'camera_pclk':20.833,'ddrphy_sysclk':8.0}},
                {('camera_pclk','ddrphy_sysclk'):{'BoundNS':8.0}}, gray=True)
        self.assertEqual(missing[0]['Corner'], 'fast')


class PackedControlTests(unittest.TestCase):
    def test_buffered_enable_keeps_exact_boolean_identity(self):
        cells = {
            'flag':{'Primitive':'V_FFSYN', 'Ports':{'Q':'flag'}},
            'buffer':{'Primitive':'V_BUF', 'Ports':{'I':'flag','Z':'buffered'}},
            'inverter':{'Primitive':'V_INV', 'Ports':{'I':'flag','Z':'inverted'}},
        }
        drivers = {'flag':('flag','Q'),'buffered':('buffer','Z'),'inverted':('inverter','Z')}
        graph = SimpleNamespace(cells=cells, driver=lambda net:drivers[net])
        cone = audit.BooleanCone(graph)
        self.assertEqual(cone.expression('flag'), cone.expression('buffered'))
        self.assertNotEqual(cone.expression('flag'), cone.expression('inverted'))

    def test_constant_lut_is_one_without_assuming_arbitrary_signal(self):
        graph = audit.cdc.Graph({'Cells':{'vcc':{'Primitive':'V_LUT6CARRY',
            'Parameters':{'INIT':"64'hFFFFFFFFFFFFFFFF"}, 'Ports':{'Z':'supply'}}}, 'FFPlacement':{}})
        self.assertTrue(graph.constant_one('supply'))
        graph.cells['vcc']['Parameters']['INIT'] = "64'h0000000000000000"
        self.assertFalse(graph.constant_one('supply'))


if __name__ == '__main__': unittest.main()
