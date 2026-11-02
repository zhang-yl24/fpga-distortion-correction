"""Current-report reset scope boundaries, without EDA or historical totals."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import audit_camera720_reset as audit


def fixture(monitor_failure=False):
    lines = ['| Tool Version : Fabric Compiler (version 2023.2-SP3 <build 154097>)',
             '| Design : camera720_transport_top', '| Device : PG2L100H', '| Speed Grade : -6', '| Package : FBG676',
             ' Clock Summary:', 'board27 37.037 {0 18.5} Declared 1 0 {clk_27m}', ' Clock Groups:']
    for corner in ('Slow', 'Fast'):
        for kind in ('Setup', 'Hold', 'Recovery', 'Removal', 'Minimum Pulse Width'):
            lines.append(f'{kind} Summary({corner} Corner):')
            if kind == 'Minimum Pulse Width':
                lines.append('board27 0.1 0.0 0 1')
            elif kind == 'Recovery':
                lines += ['board27 rst_clk -0.5 -0.5 1 1', 'rst_clk phy_dq_clk_0 -0.5 -0.5 1 1']
                lines.append('board27 camera_pclk '+('-0.5 -0.5 1 1' if monitor_failure else '0.1 0.0 0 1'))
            else:
                lines.append('board27 camera_pclk 0.1 0.0 0 1')
    for corner in ('slow', 'fast'):
        for source, target, launch, capture in (
            ('power_ready/current/CLK', audit.scope.IP+'u_ddrphy_rst_seq_rstn_sync/sig_async_r1[0]/current/RS', 'board27', 'rst_clk'),
            (audit.scope.IP+'ddrphy_reset_ctrl/ddrphy_dqs_rst/current/CLK', audit.scope.SLICE+'lane[0]/cell/ISR_IOLHR', 'rst_clk', 'phy_dq_clk_0')):
            lines += [f'Startpoint : {source}', f'Endpoint : {target}', f'Path Group : {capture}',
                      f'Path Type : max ({corner} corner)', 'Path Class : async timing path',
                      f' Clock {launch} (rising edge) 0.0', ' SOURCE/Q tco 0.1 0.1 f source',
                      f' Clock {capture} (rising edge) 0.0', ' Recovery time 0.1', ' Slack (VIOLATED) -0.5']
    lines += ['Startpoint : power_ready/current/CLK', 'Endpoint : camera_configuration/monitor/p_reset[0]/current/RS',
              'Path Group : camera_pclk', 'Path Type : max (slow corner)', 'Path Class : async timing path',
              'Timing Exception : MaxDelay Path 8.000ns -datapath_only', 'Exception constraint line number: 713',
              ' Recovery time 0.1', ' Slack (MET) 0.1']
    return '\n'.join(lines)+'\n'


class Camera720ResetTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix='camera720-reset-test-')
        self.addCleanup(self.scratch.cleanup)
        self.path = Path(self.scratch.name)/'current.rtr'
        self.path.write_text(fixture(), encoding='utf-8', newline='\n')

    def test_dynamic_inventory_does_not_require_old_245_checks(self):
        inv, adapter = audit.inventory(self.path)
        self.assertTrue(inv['Complete'])
        self.assertEqual(inv['Corners']['slow']['LogicalChecks'], 2)
        self.assertEqual(inv['OtherRecoveryInventory']['MonitorDetailedRecords'], 1)
        queries, body, fdc = audit.query_scope(inv)
        self.assertEqual(len(queries), 2)
        self.assertNotIn('camera_configuration/', body+fdc)
        self.assertIn('CAMERA720_RESET_QUERY_', body)
        self.assertFalse(inv['TimingExceptionApproved'])
        self.assertEqual(adapter['HeaderReplacements'], 1)

    def test_new_monitor_summary_failure_blocks_scope(self):
        self.path.write_text(fixture(True), encoding='utf-8', newline='\n')
        with self.assertRaisesRegex(ValueError, 'outside the proposed reset families'):
            audit.inventory(self.path)

    def test_monitor_datapath_failure_blocks_scope_even_if_summary_is_clean(self):
        text = fixture().replace(' Slack (MET) 0.1', ' Slack (VIOLATED) -0.1')
        self.path.write_text(text, encoding='utf-8', newline='\n')
        with self.assertRaisesRegex(ValueError, 'monitor recovery failure'):
            audit.inventory(self.path)

    def test_old_top_rejected(self):
        self.path.write_text(fixture().replace('camera720_transport_top', 'camera_vga_calibrated_top'), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'not 720p transport'):
            audit.inventory(self.path)

    def test_missing_native_variant_is_not_complete(self):
        text = fixture().replace('Path Type : max (fast corner)', 'Path Type : max (slow corner)', 1)
        self.path.write_text(text, encoding='utf-8')
        with self.assertRaises(ValueError):
            audit.inventory(self.path)

    def test_new_monitor_cannot_masquerade_as_ddr_source(self):
        text = fixture().replace(audit.scope.IP+'ddrphy_reset_ctrl/ddrphy_dqs_rst/current/CLK',
                                 'camera_configuration/monitor/fault/current/CLK')
        self.path.write_text(text, encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'unknown reset source family'):
            audit.inventory(self.path)

    def test_header_adapter_never_rewrites_connections(self):
        text = 'module camera720_transport_top(input a);\nwire camera720_transport_top_suffix;\nendmodule\n'
        result = audit.adapt_netlist(text)
        self.assertEqual(result, text.replace('module camera720_transport_top(', 'module camera_vga_output_top('))
        with self.assertRaises(ValueError):
            audit.adapt_netlist(text+'module extra; endmodule\n')

    def test_native_names_must_match_current_proposal_exactly(self):
        inv, _ = audit.inventory(self.path)
        queries, _, _ = audit.query_scope(inv)
        lines = []
        for q in queries:
            for pattern, names in ((q['FromRegex'], [q['Source']]), (q['ToRegex'], q['Targets'])):
                lines.append(f"I: Timing-5001: The pattern '{pattern}' in command 'get_pins -hierarchical -regexp {pattern}' match {len(names)} objects below: "+' '.join('t:'+n for n in names))
        log = Path(self.scratch.name)/'native.log'
        log.write_text('\n'.join(lines)+'\n', encoding='utf-8')
        self.assertEqual(len(audit.exact_queries(queries, log)), 4)
        log.write_text('\n'.join(lines).replace('t:power_ready/current/CLK', 't:power_ready/other/CLK')+'\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'exact names/count differ'):
            audit.exact_queries(queries, log)


if __name__ == '__main__':
    unittest.main()
