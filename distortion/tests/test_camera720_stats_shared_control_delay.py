"""Unmocked ten-delay graph with both control consumers after the delay."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_shared_control_delay as proof
import test_camera720_stats_control_delay as old_fixture
import test_calibrated_camera_input_delay as data_fixture


def fixture():
    old,_=old_fixture.fixture()
    cells={**old.cells,**data_fixture.fixture()}
    for pad in proof.CONTROL_SIGNALS:
        cells[proof.MONITOR+pad+'/FF0/FF']['Ports']['D']='delayed_'+pad
    return cells


def audit(cells):return proof.audit(proof.monitor.Graph({'Cells':cells,'FFPlacement':{},'ModuleDeclarations':''}))


class SharedControlDelayTests(unittest.TestCase):
    def test_full_native_partition_and_shared_consumers(self):
        cells=fixture();before=deepcopy(cells);value=audit(cells)
        self.assertEqual(value['Schema'],proof.SCHEMA)
        self.assertEqual(value['NativeDelayCells'],10)
        self.assertEqual(value['DataDelayProof']['UniqueFirstSequentialSinkCount'],36)
        self.assertTrue(value['MonitorAfterControlDelay'])
        self.assertTrue(value['AllControlConsumersDelayed'])
        self.assertFalse(value['RawMonitorPathPreserved'])
        self.assertFalse(value['TimingAccepted'])
        self.assertEqual(cells,before)
        for row in value['Signals']:
            self.assertEqual(len(row['DelayedMonitor']['FirstSequentialSinks']),1)
            self.assertEqual(len(row['DelayedCapture']['FirstSequentialSinks']),1)

    def test_any_pre_delay_fanout_is_rejected(self):
        for prefix in (proof.MONITOR,proof.CAP):
            cells=fixture();cells[prefix+'cam_href/FF0/FF']['Ports']['D']='raw_cam_href'
            with self.subTest(prefix=prefix),self.assertRaises(ValueError):audit(cells)
        cells=fixture();cells['raw_tap']=old_fixture.cell('V_INV',{'I':'raw_cam_vsync','O':'orphan'})
        with self.assertRaises(ValueError):audit(cells)

    def test_direct_pad_bypass_is_rejected(self):
        cells=fixture();cells[proof.MONITOR+'cam_vsync/FF0/FF']['Ports']['D']='cam_vsync'
        with self.assertRaises(ValueError):audit(cells)

    def test_delayed_control_requires_both_roles(self):
        for prefix in (proof.MONITOR,proof.CAP):
            cells=fixture();cells.pop(prefix+'cam_href/FF0/FF')
            with self.subTest(prefix=prefix),self.assertRaises(ValueError):audit(cells)

    def test_foreign_domain_sink_and_clock_input_rejected(self):
        for bad in ('clock_domain','outside_scope','clock_pin'):
            cells=fixture();name=proof.MONITOR+'cam_href/FF0/FF'
            if bad=='clock_domain':cells[name]['Ports']['CK']='clk_27m'
            if bad=='outside_scope':cells['unrelated/FF0/FF']=cells.pop(name)
            if bad=='clock_pin':cells[name]['Ports'].update({'D':"1'b0",'CK':'delayed_cam_href'})
            with self.subTest(bad=bad),self.assertRaises(ValueError):audit(cells)

    def test_delay_setting_extra_cell_and_bit_swaps_rejected(self):
        for bad in ('setting','extra','input_swap','output_alias'):
            cells=fixture();name='camera_control_delay/control_bit[0].input_delay'
            if bad=='setting':cells[name]['Parameters']['ZHOLD_SET']='"1000ps"'
            if bad=='extra':cells['another_delay']=deepcopy(cells[name])
            if bad=='input_swap':cells[name]['Ports']['DI']='raw_cam_vsync'
            if bad=='output_alias':cells[name]['Ports']['DO']='delayed_cam_vsync'
            with self.subTest(bad=bad),self.assertRaises(ValueError):audit(cells)

    def test_data_scope_still_checks_actual_data_bypass(self):
        cells=fixture();cells[proof.CAP+'capture0_0']['Ports']['D']='b0'
        with self.assertRaises(ValueError):audit(cells)


if __name__=='__main__':unittest.main()
