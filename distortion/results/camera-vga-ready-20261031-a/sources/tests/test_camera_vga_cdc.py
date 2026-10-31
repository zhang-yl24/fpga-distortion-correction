"""Adversarial tests for the candidate-specific bounded CDC checker."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import audit_camera_vga_cdc as c


def ff(q,d,ck='leaf_a',sr='clear_a'):
    return {'Primitive':'V_FFASYN','Parameters':{'SET_RESET':'"RESET"','INIT':"1'b0"},
            'Ports':{'Q':q,'D':d,'CK':ck,'SR':sr,'CE':"1'b1"}}


def buffer(q,d):
    return {'Primitive':'V_BUF','Parameters':{},'Ports':{'Z':q,'I':d}}


def direct_graph():
    cells={'first/FF0/FF':ff('q1','async'), 'second/FF0/FF':ff('q2','q1','leaf_b','clear_b'),
           'clock_a':buffer('leaf_a','root'),'clock_b':buffer('leaf_b','root'),
           'rootbuf':{'Primitive':'V_USCM','Parameters':{'USCM_MODE':'"BUF_A"'},
                      'Ports':{'CLKOUT':'root','CLK0':'clk_27m','CLK1':'','SEL':''}},
           'clear_buf_a':buffer('clear_a','reset'),'clear_buf_b':buffer('clear_b','reset')}
    return {'Cells':cells,'FFPlacement':{n:{'Site':'CLMA_1_2','Attributes':'A'} for n in cells if cells[n]['Primitive'] in c.FF_TYPES}}


def gated_graph(leak=False):
    g=direct_graph();g['Cells']['second/FF0/FF']['Ports']['D']='gated'
    init=0
    for address in range(64):
        i0=(address>>0)&1;i1=(address>>1)&1
        value=i0 if leak and address<32 else i0&i1
        init|=value<<address
    g['Cells']['logic/FYA/LUT6CARRY']={'Primitive':'V_LUT6CARRY','Parameters':{'INIT':f"64'h{init:016X}"},
        'Ports':{'I0':'q1','I1':'release','I2':"1'b0",'I3':"1'b0",'I4':"1'b0",'I5':"1'b1",
                 'Z':'gated','Z5':'other' if leak else '', 'COUT':''}}
    return g


class CameraCDCTest(unittest.TestCase):
    def test_distinct_clock_and_reset_buffers_resolve_equivalent(self):
        r=c.Graph(direct_graph()).chain('first/FF0/FF','second/FF0/FF','test')
        self.assertTrue(r['ClearFunctionsEquivalent'])
        self.assertEqual(r['DestinationClock'],'board27')

    def test_camera_clock_is_derived_from_port_not_global_buffer_number(self):
        g=direct_graph();g['Cells']['rootbuf']['Ports']['CLK0']='cam_pclk'
        self.assertEqual(c.Graph(g).clock('leaf_a')['Domain'],'camera_pclk')

    def test_dynamic_clock_mux_rejected(self):
        g=direct_graph();g['Cells']['rootbuf']['Parameters']['USCM_MODE']='"MUX"'
        with self.assertRaisesRegex(ValueError,'dynamic clock mux'):c.Graph(g).clock('leaf_a')

    def test_extra_first_stage_functional_fanout_rejected(self):
        g=direct_graph();g['Cells']['unexpected']=buffer('extra','q1')
        with self.assertRaisesRegex(ValueError,'fanout escapes'):c.Graph(g).chain('first/FF0/FF','second/FF0/FF','test')

    def test_different_clear_function_rejected(self):
        g=direct_graph();g['Cells']['clear_buf_b']['Ports']['I']='other_reset'
        with self.assertRaisesRegex(ValueError,'clear functions'):c.Graph(g).chain('first/FF0/FF','second/FF0/FF','test')

    def test_reset_gated_interstage_lut_truth_is_proven(self):
        r=c.Graph(gated_graph()).chain('first/FF0/FF','second/FF0/FF','test','release')
        self.assertEqual(r['InterstageLogic']['Truth'],'first_stage AND local_release')

    def test_packed_lut_second_output_cannot_leak_first_stage(self):
        with self.assertRaisesRegex(ValueError,'shared LUT output'):
            c.Graph(gated_graph(True)).chain('first/FF0/FF','second/FF0/FF','test','release')

    def test_nonlocal_query_pin_comes_from_actual_lut_input(self):
        g=gated_graph();g['FFPlacement']['second/FF0/FF']['Site']='CLMA_8_9'
        q=c.Graph(g).chain('first/FF0/FF','second/FF0/FF','test','release')['NativeQueries'][0]
        self.assertEqual((q['Source'],q['Endpoint']),('first/CLK','logic/I0'))

    def test_register_clock_domain_mismatch_rejected(self):
        g=direct_graph();g['Cells']['clock_b']['Ports']['I']='cam_pclk'
        with self.assertRaisesRegex(ValueError,'clock domains'):c.Graph(g).chain('first/FF0/FF','second/FF0/FF','test')

    def test_native_parent_preserves_actual_packed_name(self):
        self.assertEqual(c.native_parent('signal[1]/opit_0/FFAPP3/FF'),'signal[1]/opit_0')
        self.assertEqual(c.native_parent('signal[0]/opit_0/FF2/FF'),'signal[0]/opit_0')


if __name__=='__main__':unittest.main()
