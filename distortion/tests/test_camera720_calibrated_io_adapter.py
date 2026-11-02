"""CPU-only interface/adaptation tests; no native stage or old evidence used."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_calibrated_io_adapter as adapter
import prepare_camera720_calibrated as prep

ROOT = Path(__file__).resolve().parents[1]


class CalibratedIOAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Same deterministic source transform; no machine-local work is needed.
        cls.top = prep.render_top((ROOT/'board/camera720_transport_top.v').read_text())
        cls.fdc = (ROOT/'board/camera720-output-diagnostic.fdc').read_text()

    def test_actual_source_inventory(self):
        value = adapter.source_inventory(self.top, self.fdc)
        self.assertEqual(value['PortCount'], 128)
        self.assertEqual(len(value['DVPInputs']), 10)
        self.assertEqual(len(value['TXOutputs']), 28)
        self.assertFalse(value['PhysicalEvidenceVerified'])
        self.assertFalse(value['HardwareReleaseAllowed'])

    def test_wrong_top_or_second_module_is_rejected(self):
        for text in (self.top.replace(adapter.TARGET, 'camera720_transport_top'),
                     self.top+'\nmodule surprise(); endmodule\n'):
            with self.subTest(text=text[-50:]), self.assertRaises(ValueError):
                adapter.source_inventory(text, self.fdc)

    def test_port_direction_and_clock_drift_fail(self):
        for fdc in (self.fdc.replace('{p:cam_data[0]} {PAP_IO_DIRECTION} {INPUT}',
                                     '{p:cam_data[0]} {PAP_IO_DIRECTION} {OUTPUT}'),
                    self.fdc.replace('-period 20.833 [get_ports cam_pclk]', '-period 10.0 [get_ports cam_pclk]'),
                    self.fdc+'\nset_output_delay 1 [get_ports r_out[0]]\n'):
            with self.subTest(fdc=fdc[-50:]), self.assertRaises(ValueError):
                adapter.source_inventory(self.top, fdc)

    def test_adaptation_changes_only_unique_module_token(self):
        rewritten = adapter.module_as(self.top, 'camera_vga_output_top')
        self.assertEqual(rewritten.replace('module camera_vga_output_top', 'module '+adapter.TARGET), self.top)
        self.assertEqual(adapter.structure.prep.TARGET, 'camera720_transport_top')

    def query_fixture(self):
        pins = {'PinInventory': [{'Site':'IOB_X1_Y2'}, {'Site':'IOB_X1_Y3'}]}
        pairs = [(p, 'system/input_link/input_dma/capture/cell/I0') for p in sorted(adapter.native_io.PORTS)]
        launches = {p:['system/output_video/current_launch/CLK'] for p in adapter.native_io.tx.PORTS-{'pix_clk'}}
        return pins, pairs, launches

    def test_query_requires_current_complete_membership(self):
        pins,pairs,launches = self.query_fixture()
        body = adapter.query_body(pins,pairs,launches)
        self.assertEqual(body.count('report_path_timing '), 3)
        self.assertIn('-from {clk_27m} -to {pix_clk}', body)
        with self.assertRaises(ValueError): adapter.query_body(pins,pairs[:-1],launches)
        with self.assertRaises(ValueError): adapter.query_body(pins,pairs,{})

    def test_query_rejects_injection_and_unrelated_launch(self):
        pins,pairs,launches = self.query_fixture()
        bad = list(pairs);bad[0] = (bad[0][0], bad[0][1]+'}; exec anything; #')
        with self.assertRaises(ValueError): adapter.query_body(pins,bad,launches)
        badlaunch = dict(launches);badlaunch['r_out[0]'] = ['wrong_block/CLK']
        with self.assertRaises(ValueError): adapter.query_body(pins,pairs,badlaunch)


if __name__ == '__main__': unittest.main()
