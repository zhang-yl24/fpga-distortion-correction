"""New control-delay separation faults; no synthesis or prior board evidence."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_control_delay as proof
import test_calibrated_camera_input_delay as data_fixture


def cell(kind,ports,parameters=None):return {'Primitive':kind,'Ports':ports,'Parameters':parameters or {}}


def fixture():
    cells={}
    for pad,bit in proof.CONTROL_SIGNALS.items():
        raw='raw_'+pad;delayed='delayed_'+pad
        cells[pad+'_ibuf']=cell('V_IBUF',{'I':pad,'O':raw},{'IOSTANDARD':'"LVCMOS33"','TERM_DDR':'"ON"'})
        cells[f'camera_control_delay/control_bit[{bit}].input_delay']=cell('V_ZEROHOLDDELAY',{'DI':raw,'DO':delayed},{'ZHOLD_SET':'"1500ps"'})
        for prefix,net in ((proof.MONITOR,raw),(proof.CAP,delayed)):
            cells[prefix+pad+'/FF0/FF']=cell('V_FFSYN',{'D':net,'Q':prefix+pad+'_q','CK':'cam_pclk','CE':"1'b1",'SR':"1'b0"})
    names=[]
    for bit in range(8):
        name=f'camera_data_delay/data_bit[{bit}].input_delay';names.append(name)
        cells[name]=cell('V_ZEROHOLDDELAY',{'DI':f'data_raw{bit}','DO':f'data_delayed{bit}'},{'ZHOLD_SET':'"1500ps"'})
    graph=proof.monitor.Graph({'Cells':cells,'FFPlacement':{},'ModuleDeclarations':''})
    return graph,names


class ControlDelayTests(unittest.TestCase):
    def audit(self,graph,names):
        def data_scope(g):
            self.assertEqual(set(g.cells),set(graph.cells)-{
                'camera_control_delay/control_bit[0].input_delay','camera_control_delay/control_bit[1].input_delay'})
            return {'Passed':True,'Bits':[{'DelayCell':n} for n in names],'NativeDelayCells':8}
        with patch.object(proof.data,'audit',side_effect=data_scope):return proof.audit(graph)

    def test_ten_cells_partition_capture_and_raw_monitor(self):
        graph,names=fixture();before=deepcopy(graph.g);value=self.audit(graph,names)
        self.assertTrue(value['Passed']);self.assertEqual(value['NativeDelayCells'],10)
        self.assertTrue(value['RawMonitorPathPreserved'])
        self.assertTrue(value['AllCaptureControlConsumersTraverseOwnDelay'])
        self.assertEqual(len(value['Signals']),2);self.assertEqual(graph.g,before)
        self.assertFalse(value['ActualPVTDelayFromSettingAloneProven'])

    def test_missing_extra_or_changed_delay_fail(self):
        for change in ('missing','extra','setting','mapping'):
            graph,names=fixture();name='camera_control_delay/control_bit[0].input_delay'
            if change=='missing':graph.cells.pop(name)
            if change=='extra':graph.cells['extra']=deepcopy(graph.cells[name])
            if change=='setting':graph.cells[name]['Parameters']['ZHOLD_SET']='"1000ps"'
            if change=='mapping':graph.cells[name]['Ports']['DI']='raw_cam_vsync'
            with self.subTest(change=change),self.assertRaises(ValueError):self.audit(graph,names)

    def test_raw_capture_bypass_rejected(self):
        graph,names=fixture();graph.cells[proof.CAP+'cam_href/FF0/FF']['Ports']['D']='raw_cam_href'
        with self.assertRaises(ValueError):self.audit(graph,names)

    def test_monitor_delayed_or_foreign_domain_rejected(self):
        for mode in ('delayed','wrong_clock'):
            graph,names=fixture();ports=graph.cells[proof.MONITOR+'cam_vsync/FF0/FF']['Ports']
            if mode=='delayed':ports['D']='delayed_cam_vsync'
            else:ports['CK']='clk_27m'
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.audit(graph,names)

    def test_unreviewed_output_or_hidden_vector_bypass_rejected(self):
        for consumer in (cell('V_OBUF',{'I':'delayed_cam_href','O':'other_pad'}),
                         cell('UNKNOWN',{'I':'{raw_cam_href}','O':'other'})):
            graph,names=fixture();graph.cells['unexpected']=consumer
            with self.assertRaises(ValueError):self.audit(graph,names)

    def test_data_proof_must_cover_exact_remaining_eight(self):
        graph,names=fixture()
        with patch.object(proof.data,'audit',return_value={'Bits':[{'DelayCell':n} for n in names[:-1]]}),self.assertRaises(ValueError):
            proof.audit(graph)

    def test_full_unmocked_ten_cell_data_and_control_audit(self):
        graph,_=fixture();cells={**graph.cells,**data_fixture.fixture()}
        actual=proof.monitor.Graph({**graph.g,'Cells':cells})
        result=proof.audit(actual)
        self.assertEqual(result['DataDelayProof']['UniqueFirstSequentialSinkCount'],36)
        self.assertEqual(result['NativeDelayCells'],10)
        self.assertTrue(result['RawMonitorPathPreserved'])
        cells[proof.CAP+'capture0_0']['Ports']['D']='b0'
        with self.assertRaises(ValueError):proof.audit(proof.monitor.Graph({**graph.g,'Cells':cells}))


if __name__=='__main__':unittest.main()
