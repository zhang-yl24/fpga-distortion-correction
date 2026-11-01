"""Synthetic negative cases for raw-specific reset inventory and graph gates."""
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import prepare_raw_camera_reset_scope as scope
import audit_raw_camera_reset_netlist as graph


def scope_fixture():
    source = 'startup/power_ready/opit_0/CLK'
    target = scope.IP + 'u_ddrphy_rst_seq_rstn_sync/sig_async_r1[0]/opit_0/RS'
    paths, summaries = [], {}
    for corner in ('slow', 'fast'):
        summaries[(corner, 'board27', 'rst_clk')] = {'WNS': '-1.000', 'TNS': '-1.000', 'Failing': 1, 'Total': 1}
        paths.append({'Source': source, 'Endpoint': target, 'LaunchClock': 'board27', 'CaptureClock': 'rst_clk',
                      'Corner': corner, 'Family': 'entry_rdc', 'LaunchEdge': 'rising', 'CaptureEdge': 'rising',
                      'LaunchDataTransition': 'f', 'SlackNS': '-1.000', 'SlackState': 'VIOLATED',
                      'NativeReportLine': 1, 'NativePathSHA256': hashlib.sha256(corner.encode()).hexdigest()})
    return paths, summaries


def graph_fixture():
    syntax = graph.syntax
    cells = []
    nets = {'board_input', 'board_clock', 'power_clock_leaf', 'registered_ready', 'raw_clear',
            'pll_clock', 'rst_clock_leaf', 'entry_middle', 'reset_load', 'iol_net',
            syntax.LOCK, syntax.OUTPUT, syntax.RST_CLOCK}

    def cell(primitive, name, ports, params=None):
        parameter = '' if not params else '#(' + ', '.join('.' + k + '(' + v + ')' for k, v in params.items()) + ') '
        body = ', '.join('.' + k + ' (' + v + ' )' for k, v in ports.items())
        cells.append(primitive + ' ' + parameter + '\\' + name + ' (' + body + ');')

    ff = {'GRS_EN': '"TRUE"', 'SET_RESET': '"RESET"', 'LRS_EN': '"TRUE"', 'INIT': "1'b0"}
    cell('V_IBUF', 'board_ibuf', {'O': 'board_input', 'I': 'clk_27m'})
    cell('V_USCM', 'board_clock_buffer', {'CLKOUT': 'board_clock', 'CLK0': 'board_input', 'CLK1': '', 'SEL': ''}, {'USCM_MODE': '"BUF_A"'})
    cell('V_BUF', 'board_leaf', {'Z': 'power_clock_leaf', 'I': 'board_clock'})
    cell('V_FFSYN', 'startup/power_ready/opit_0/FF0/FF', {'Q': 'registered_ready', 'CE': "1'b1", 'CK': 'power_clock_leaf', 'D': "1'b1", 'SR': "1'b0"}, ff)
    cell('V_INV', 'ready_inverse', {'Z': 'raw_clear', 'I': 'registered_ready'})
    cell('V_GPLL', 'ddr_pll', {'LOCK': syntax.LOCK, 'CLKOUT0': 'pll_clock', 'RST': 'raw_clear'})
    cell('V_USCM', 'ddr_clock_buffer', {'CLKOUT': syntax.RST_CLOCK, 'CLK0': 'pll_clock', 'CLK1': '', 'SEL': ''}, {'USCM_MODE': '"BUF_A"'})
    cell('V_BUF', 'ddr_leaf', {'Z': 'rst_clock_leaf', 'I': syntax.RST_CLOCK})
    cell('V_FFASYN', syntax.SYNC + 'sig_async_r1[0]/opit_0/FF0/FF', {'Q': 'entry_middle', 'CE': "1'b1", 'CK': 'rst_clock_leaf', 'D': syntax.LOCK, 'SR': 'raw_clear'}, ff)
    cell('V_FFASYN', syntax.SYNC + 'sig_async_r2[0]/opit_0/FF0/FF', {'Q': syntax.OUTPUT, 'CE': "1'b1", 'CK': 'rst_clock_leaf', 'D': 'entry_middle', 'SR': 'raw_clear'}, ff)
    cell('V_INV', syntax.PREFIX + 'ddrphy_reset_ctrl/output_inverse', {'Z': 'reset_load', 'I': syntax.OUTPUT})
    iol = syntax.PREFIX + 'ddrphy_reset_ctrl/ddrphy_iol_rst/opit_0'
    target = scope.SLICE + 'i_ca_group[0].u_tserdes_ca0/oserdes'
    cell('V_FFASYN', iol + '/FF0/FF', {'Q': 'iol_net', 'CE': "1'b1", 'CK': 'rst_clock_leaf', 'D': "1'b1", 'SR': 'raw_clear'}, ff)
    cell('V_OSERDES_E2', target + '/body', {'RST': 'iol_net'})
    declarations = ['wire ' + n + ' ;' for n in sorted(nets)]
    text = '\n'.join(['module ' + graph.TARGET + ';', 'input clk_27m;', *declarations, *cells, 'endmodule'])
    queries = [{'Source': 'startup/power_ready/opit_0/CLK', 'Targets': [syntax.SYNC + 'sig_async_r1[0]/opit_0/RS'],
                'Family': 'entry_rdc', 'EntryRDC': True, 'ExpectedFromCount': 1, 'ExpectedTargetCount': 1},
               {'Source': iol + '/CLK', 'Targets': [target + '/TSR'], 'Family': 'iol_reset', 'EntryRDC': False,
                'ExpectedFromCount': 1, 'ExpectedTargetCount': 1}]
    return text, queries


class ScopeTests(unittest.TestCase):
    def test_registered_entry_uses_current_names(self):
        paths, summaries = scope_fixture()
        inventory = scope.audit_inventory(paths, summaries)
        queries, body, proposal = scope.query_scope(inventory)
        self.assertEqual(queries[0]['Source'], paths[0]['Source'])
        self.assertIn('RAW_CAMERA_RESET_QUERY', body)
        self.assertNotIn('set_clock_groups', proposal)

    def test_old_combinational_counter_is_rejected(self):
        paths, summaries = scope_fixture()
        paths[0]['Source'] = 'power_count[8]/opit_0/CLK'
        with self.assertRaisesRegex(ValueError, 'entry reset path'):
            scope.audit_inventory(paths, summaries)

    def test_display_power_source_is_not_implicitly_reused(self):
        paths, summaries = scope_fixture()
        paths[0]['Source'] = 'power_ready/opit_0/CLK'
        with self.assertRaises(ValueError):
            scope.audit_inventory(paths, summaries)

    def test_missing_corner_and_wrong_summary_rejected(self):
        paths, summaries = scope_fixture()
        with self.assertRaises(ValueError):
            scope.audit_inventory(paths[:-1], summaries)
        summaries[('fast', 'board27', 'rst_clk')]['TNS'] = '-0.999'
        with self.assertRaises(ValueError):
            scope.audit_inventory(paths, summaries)

    def test_data_pin_cannot_enter_reset_exception(self):
        paths, summaries = scope_fixture()
        paths[0]['Endpoint'] = paths[0]['Endpoint'].replace('/RS', '/D')
        with self.assertRaises(ValueError):
            scope.audit_inventory(paths, summaries)


class GraphTests(unittest.TestCase):
    def test_raw_registered_structure_passes_without_release(self):
        text, queries = graph_fixture()
        result = graph.audit_text(text, queries)
        self.assertTrue(result['RegisteredStickyPropertyVerified'])
        self.assertFalse(result['ExternalResetPortAssumed'])
        self.assertFalse(result['TimingExceptionApproved'])
        self.assertFalse(result['FullStartupDelayNetlistEquivalenceProven'])
        self.assertEqual(result['InternalFunctionalTargetsVerified'], 1)

    def test_nonsticky_data_rejected(self):
        text, queries = graph_fixture()
        text = text.replace(".CK (power_clock_leaf ), .D (1'b1 )", ".CK (power_clock_leaf ), .D (registered_ready )")
        with self.assertRaisesRegex(ValueError, 'constant-one D'):
            graph.audit_text(text, queries)

    def test_uninitialized_power_ready_rejected(self):
        text, queries = graph_fixture()
        text = text.replace(".INIT(1'b0)", ".INIT(1'b1)", 1)
        with self.assertRaisesRegex(ValueError, 'initialization'):
            graph.audit_text(text, queries)

    def test_wrong_clear_polarity_rejected(self):
        text, queries = graph_fixture()
        text = text.replace('V_INV \\ready_inverse', 'V_BUF \\ready_inverse')
        with self.assertRaisesRegex(ValueError, 'exact inversion'):
            graph.audit_text(text, queries)

    def test_old_external_reset_dependency_rejected(self):
        text, queries = graph_fixture()
        text = text.replace('input clk_27m;', 'input clk_27m;\ninput reset_n;')
        with self.assertRaisesRegex(ValueError, 'external reset_n'):
            graph.audit_text(text, queries)

    def test_first_stage_fanout_rejected(self):
        text, queries = graph_fixture()
        text = text.replace(".Q (registered_ready ), .CE (1'b1 )", '.Q (registered_ready ), .CE (entry_middle )')
        with self.assertRaisesRegex(ValueError, 'first-stage functional fanout'):
            graph.audit_text(text, queries)

    def test_incorrect_lock_clock_pair_rejected(self):
        text, queries = graph_fixture()
        text = text.replace('.CLK0 (pll_clock )', '.CLK0 (board_clock )')
        with self.assertRaisesRegex(ValueError, 'different PLLs'):
            graph.audit_text(text, queries)

    def test_extra_alias_to_clear_rejected(self):
        text, queries = graph_fixture()
        text = text.replace('endmodule', 'assign hidden_alias = raw_clear;\nendmodule')
        with self.assertRaisesRegex(ValueError, 'unparsed alias'):
            graph.audit_text(text, queries)

    def test_wrong_internal_target_net_rejected(self):
        text, queries = graph_fixture()
        text = text.replace('(.RST (iol_net ));', '(.RST (raw_clear ));')
        with self.assertRaises(ValueError):
            graph.audit_text(text, queries)


class PackedLutSupportTests(unittest.TestCase):
    def test_actual_packed_upper_half_depends_only_on_ready(self):
        self.assertEqual(graph.lut_support(0x00FF00FFE2E20000, {5: 1}), [3])

    def test_other_output_truth_table_is_not_assumed_constant(self):
        self.assertNotEqual(graph.lut_support(0x00FF00FFE2E20000, {5: 0}), [3])

    def test_a_new_dependency_in_selected_rows_is_detected(self):
        self.assertIn(0, graph.lut_support(0x00FF00FFE2E20000 ^ (1 << 32), {5: 1}))


if __name__ == '__main__':
    unittest.main()
