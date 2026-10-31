"""Reject incomplete native case coverage before bounded CDC completion."""
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import audit_camera_vga_cdc_native as n

class NativeCDCTest(unittest.TestCase):
    def rows(self):
        return [{'Source':'a/CLK','Endpoint':'b/D','Corner':c,'Kind':k,'SlackNS':1.0}
                for c in ('slow','fast') for k in ('setup','hold')]
    def query(self):
        return [{'Source':'a/CLK','Endpoint':'b/D','Label':'q','Clock':'camera_pclk'}]
    def test_requires_all_corners_and_kinds(self):
        rows=self.rows();rows.pop()
        with self.assertRaisesRegex(ValueError,'coverage missing'):n.coverage(rows,self.query())
    def test_rejects_other_source_same_endpoint(self):
        rows=self.rows();rows[0]['Source']='other/CLK'
        with self.assertRaisesRegex(ValueError,'coverage missing'):n.coverage(rows,self.query())
    def test_keeps_worst_native_variant(self):
        rows=self.rows();rows.append({**rows[0],'SlackNS':0.25})
        result=n.coverage(rows,self.query())
        self.assertEqual(result[0]['SetupSlackNS'],0.25)
        self.assertEqual(result[0]['NativeVariantCount'],3)
    def gray_lines(self,state='MET',slack='7.2'):
        return [x+'\n' for x in ['Startpoint : a/CLK','Endpoint : b/D',
            'Path Type : max (fast corner)','Timing Exception : MaxDelay Path 8ns -datapath_only',
            ' Data arrival time 0.8 Logic Levels: 0',' Slack ('+state+') '+slack]]
    def test_gray_actual_corner_and_delay(self):
        r=n.gray_record(self.gray_lines(),'native.rtr',12)
        self.assertEqual((r['BoundNS'],r['ArrivalNS'],r['Corner']),(8.0,0.8,'fast'))
    def test_gray_violation_rejected(self):
        with self.assertRaisesRegex(ValueError,'timing failed'):
            n.gray_record(self.gray_lines('VIOLATED','-0.1'),'native.rtr',12)
    def test_truncated_native_case_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'r.rtr';p.write_text('Startpoint : a/CLK\nEndpoint : b/D\n Data arrival time 1.0\n')
            with self.assertRaisesRegex(ValueError,'truncated'):list(n.blocks(p))
    def test_unconstrained_port_combinational_path_is_skipped(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'r.rtr'
            p.write_text('Startpoint : q/CLK\nEndpoint : cam_scl (port)\nPath Class : combinational timing path\n Data arrival time 1.0\n'
                         +''.join(self.gray_lines()))
            blocks=list(n.blocks(p))
            self.assertEqual(len(blocks),1)
            self.assertEqual(blocks[0][0][0].strip(),'Startpoint : a/CLK')

if __name__=='__main__':unittest.main()
