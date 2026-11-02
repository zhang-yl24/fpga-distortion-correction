"""Pure stats-adapter faults: no EDA, UART, receipts or historical acceptance."""
from contextlib import ExitStack
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_io_cdc as adapter
import prepare_camera720_calibrated as calibrated
import prepare_camera720_calibrated_stats as source

ROOT = Path(__file__).resolve().parents[1]


def ff(d,q,clk='core'):
    return {'Primitive':'V_FFSYN','Parameters':{},'Ports':{'D':d,'Q':q,'CK':clk,'CE':"1'b1",'SR':"1'b0"}}


def fixture_graph():
    cells = {'system/counter/FF0/FF':ff("1'b0",'count'),
        'core_statistics/state/FF0/FF':ff('count','state'),
        'core_statistics/tx/FF0/FF':ff('state','tx'),
        'uart_pad/obuf':{'Primitive':'V_OBUF','Parameters':{},'Ports':{'I':'tx','O':'uart_txd'}}}
    graph = adapter.structure.monitor.Graph({'Cells':cells,'FFPlacement':{}})
    graph.clock_cache = {'core':{'Domain':'ddrphy_sysclk'},'pixel':{'Domain':'pixel_clk'}}
    return graph


class StatsAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = calibrated.render_top((ROOT/'board/camera720_transport_top.v').read_text())
        cls.top = source.render_top(base,'a'*16,'b'*16)
        cls.camref = (ROOT/'board/raw_camera_capture_cam2_ref.fdc').read_text()
        cls.fdc = source.render_fdc((ROOT/'board/camera720-output-diagnostic.fdc').read_text(),cls.camref)
        cls.official = (ROOT/'platform/video_base/HDMI_IN_DDR3_HDMI_OUT_top.fdc').read_text()
        cls.campins = json.loads((ROOT/'board/raw_camera_capture_cam2_ref-pins.json').read_text())

    def test_actual_source_129_and_uart_direction_provenance(self):
        value = adapter.source_inventory(self.top,self.fdc)
        self.assertEqual(value['PortCount'],129)
        self.assertEqual(value['UART']['Attributes'],adapter.UART_ATTRIBUTES)
        self.assertFalse(value['UART']['FDCDirectionExplicit'])
        self.assertFalse(value['UART']['ExternalACAccepted'])
        self.assertFalse(value['HardwareReleaseAllowed'])

    def test_source_target_pin_direction_and_external_budget_faults(self):
        bad = [(self.top.replace(adapter.TARGET,'camera720_calibrated_top'),self.fdc),
            (self.top+'\nmodule injected(); endmodule',self.fdc),
            (self.top.replace('output uart_txd','input uart_txd'),self.fdc),
            (self.top,self.fdc.replace('{PAP_IO_LOC} {C24}','{PAP_IO_LOC} {C25}')),
            (self.top,self.fdc+'\nset_output_delay 1 [get_ports uart_txd]\n'),
            (self.top,self.fdc+'\ndefine_attribute {p:uart_txd} {PAP_IO_DIRECTION} {INPUT}\n')]
        for top,fdc in bad:
            with self.subTest(top=top[-30:],fdc=fdc[-50:]),self.assertRaises(ValueError):
                adapter.source_inventory(top,fdc)

    def pin_fixture(self):
        ports,attrs = adapter.declared_inventory(self.top,self.fdc)
        generated = {p:{k:v for k,v in a.items() if k!='DIRECTION'} for p,a in attrs.items()}
        routed = {p:dict(Pad=a['LOC'],Site='IO_'+str(i),Bank=a['VCCIO'],Function='IO',Direction=ports[p])
                  for i,(p,a) in enumerate(attrs.items())}
        cells = [SimpleNamespace(name=p+'/pad',primitive='V_OBUF' if ports[p]=='OUTPUT' else 'V_IBUF',
                 ports={'O' if ports[p]=='OUTPUT' else 'I':p},parameters={}) for p in ports]
        export = 'module '+adapter.TARGET+'();\n(* '+','.join('PAP_IO_'+k+'="'+v+'"' for k,v in adapter.UART_ATTRIBUTES.items())+' *) output uart_txd;\nendmodule\n'
        return ports,generated,routed,cells,export

    def run_pin(self, transform=lambda value:None):
        values = self.pin_fixture();transform(values)
        ports,generated,routed,cells,export = values
        with ExitStack() as stack:
            stack.enter_context(patch.object(adapter.io.pin_parser,'pcf_pins',return_value=generated))
            stack.enter_context(patch.object(adapter.io.pin_parser,'routed_pads',return_value=({},routed)))
            stack.enter_context(patch.object(adapter.io,'netlist_ports',return_value=ports))
            stack.enter_context(patch.object(adapter.io.net_parser,'parse',return_value=('',cells)))
            return adapter.pin_audit(self.top,self.fdc,'pcf','prt',export,self.official,self.camref,self.campins)

    def test_native_uart_direction_derived_from_three_actual_roles(self):
        value = self.run_pin()
        self.assertEqual(value['TopPortCount'],129)
        self.assertEqual(value['DDRMemoryPins'],71)
        self.assertEqual(value['CAM2Pins'],14)
        uart = next(p for p in value['PinInventory'] if p['Port']=='uart_txd')
        self.assertEqual(uart['DIRECTION'],'OUTPUT')
        self.assertFalse(value['FinalNativeElectricalAttributesVerified'])
        self.assertFalse(value['UARTExternalACAccepted'])

    def test_missing_uart_native_electrical_or_direction_rejected(self):
        mutations = [lambda v:v[1].pop('uart_txd'),
            lambda v:v[1]['uart_txd'].update(DRIVE='8'),
            lambda v:v[2]['uart_txd'].update(Direction='INPUT'),
            lambda v:v[2]['uart_txd'].update(Pad='C25'),
            lambda v:v[0].update(uart_txd='INPUT')]
        for mutation in mutations:
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):self.run_pin(mutation)

    def test_statistics_actual_domain_and_launch(self):
        graph = fixture_graph();value = adapter.stats_domain(graph)
        self.assertEqual(value['ActualStatisticsFFs'],2)
        self.assertTrue(value['NoStatisticsFeedbackToVideoRegistersOrOtherPads'])
        self.assertEqual(adapter.uart_launches(graph),['core_statistics/tx/CLK'])

    def test_statistics_foreign_data_reset_enable_and_clock_fail(self):
        for pin in ('D','CE','SR','CK'):
            graph = fixture_graph()
            if pin=='CK':graph.ff['core_statistics/state/FF0/FF']['Ports'][pin]='pixel'
            else:
                graph.ff['system/counter/FF0/FF']['Ports']['CK']='pixel'
                graph.ff['core_statistics/state/FF0/FF']['Ports'][pin]='count'
            with self.subTest(pin=pin),self.assertRaises(ValueError):adapter.stats_domain(graph)

    def test_statistics_primary_and_feedback_fail(self):
        graph = fixture_graph();graph.ff['core_statistics/state/FF0/FF']['Ports']['D']='unreviewed_primary'
        with self.assertRaises(ValueError):adapter.stats_domain(graph)
        graph = fixture_graph();graph.refs['state'].append(('system/counter/FF0/FF','CE'))
        with self.assertRaises(ValueError):adapter.stats_domain(graph)
        graph = fixture_graph();graph.cells['uart_pad/obuf']['Ports']['O']='another_pad'
        with self.assertRaises(ValueError):adapter.stats_domain(graph)

    def test_uart_buffer_and_launch_faults(self):
        graph = fixture_graph();graph.cells['uart_pad/obuf']['Ports']['I']='count'
        with self.assertRaises(ValueError):adapter.uart_launches(graph)
        graph = fixture_graph();graph.cells['uart_pad/obuf'].update(Primitive='V_OBUFT')
        graph.cells['uart_pad/obuf']['Ports']['T']="1'b1"
        with self.assertRaises(ValueError):adapter.uart_launches(graph)

    def test_queries_are_observations_without_uart_budget(self):
        ports = adapter.source_ports(self.top)
        pins = {'TopPortCount':129,'PinInventory':[{'Port':p,'Site':'IO_'+str(i)} for i,p in enumerate(ports)]}
        pairs = [(p,'system/input_link/input_dma/capture/cell/I0') for p in sorted(adapter.native_io.PORTS)]
        tx = {p:['system/output_video/launch/CLK'] for p in adapter.native_io.tx.PORTS-{'pix_clk'}}
        body = adapter.io_query_body(pins,pairs,tx,['core_statistics/tx/CLK'])
        self.assertEqual(body.count('report_path_timing '),4)
        self.assertIn('-to {uart_txd}',body)
        self.assertNotIn('set_output_delay',body)
        self.assertNotIn('set_max_delay',body)
        with self.assertRaises(ValueError):adapter.io_query_body(pins,pairs,tx,['other/CLK'])
        pins['PinInventory'].pop()
        with self.assertRaises(ValueError):adapter.io_query_body(pins,pairs,tx,['core_statistics/tx/CLK'])

    def test_cdc_grouping_reuses_actual_missing_not_old_counts(self):
        def q(source,endpoint):
            return dict(Source=source+'/CLK',LaunchOutput=source+'/L5Q',Endpoint=endpoint,
                Clock='board27',Corners=['slow','fast'],CheckKinds=['setup','hold'],LogicalRelationships=[0])
        queries = [q('a','x/I0'),q('b','x/I0'),q('c','y/I1')]
        groups,bodies = adapter.cdc_query_bodies(queries,queries,8)
        self.assertEqual(sum(len(g['ExpectedIdentities']) for g in groups),3)
        self.assertEqual(len(groups),2)
        self.assertEqual(len(bodies),1)
        self.assertFalse(any(len(g['SourceLaunches'])>1 and g['Endpoints']==['x/I0'] for g in groups))

    def test_old_report_target_rejected_even_when_no_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'report.rtr'
            path.write_text('2023.2-SP3 <build 154097>\n| Design : camera720_calibrated_top\n')
            with self.assertRaises(ValueError):adapter.collect([], [path])
            path.write_text('2023.2-SP3 <build 154097>\n| Design : '+adapter.TARGET+'\n')
            self.assertEqual(adapter.collect([], [path]),([],[],[]))

    def test_no_old_global_target_changed(self):
        adapter.module_as(self.top,'camera720_calibrated_top')
        self.assertEqual(adapter.video.TARGET,'camera720_calibrated_top')
        self.assertEqual(adapter.cdc.TARGET,'camera720_calibrated_top')
        self.assertEqual(adapter.structure.prep.TARGET,'camera720_transport_top')


if __name__=='__main__':unittest.main()
