"""New-target header adapters must preserve reset identities and failures."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_raw_reset as raw
from test_raw_camera_reset_proof import graph_fixture, scope_fixture


def report_fixture():
    paths,_=scope_fixture()
    lines=['| Design : '+raw.prep.TARGET]
    for corner in ('Slow','Fast'):
        lines += ['Recovery Summary('+corner+' Corner):',
                  'board27 rst_clk -1.000 -1.000 1 1']
    for p in paths:
        lines += ['Startpoint : '+p['Source'],'Endpoint : '+p['Endpoint'],
                  'Path Group : rst_clk','Path Type : max ('+p['Corner']+' corner)',
                  'Path Class : async timing path',' Clock board27 (rising edge) 0.0',
                  ' Clock rst_clk (rising edge) 0.0',' launch/L6Q tco 0.1 0.2 f net',
                  ' Recovery time 0.1',' Slack (VIOLATED) -1.000']
    return '\n'.join(lines)+'\n'


class CurrentRawResetTests(unittest.TestCase):
    def setUp(self):
        scratch=tempfile.TemporaryDirectory(prefix='raw720-reset-test-')
        self.addCleanup(scratch.cleanup)
        self.report=Path(scratch.name)/'fixture.rtr'
        self.report.write_text(report_fixture(),encoding='utf-8')

    def test_new_report_keeps_names_rows_slacks_and_original_bytes(self):
        before=self.report.read_bytes()
        paths,summaries=raw.parse_report(self.report)
        self.assertEqual(self.report.read_bytes(),before)
        self.assertEqual(paths[0]['Source'],'startup/power_ready/opit_0/CLK')
        self.assertEqual(paths[0]['NativeReportLine'],6)
        self.assertEqual(paths[0]['SlackNS'],'-1.000')
        inv=raw.scope.audit_inventory(paths,summaries)
        self.assertTrue(inv['Complete'])
        self.assertEqual(inv['Corners']['fast']['FailingChecks'],1)

    def test_wrong_or_duplicate_native_design_rejected(self):
        for text in (report_fixture().replace(raw.prep.TARGET,raw.graph.TARGET),
                     report_fixture()+'| Design : '+raw.prep.TARGET+'\n'):
            self.report.write_text(text,encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'exact current720'):
                raw.parse_report(self.report)

    def test_unknown_recovery_failure_is_not_absorbed_by_ddr_scope(self):
        paths,summaries=raw.parse_report(self.report)
        summaries[('slow','board27','camera_pclk')]={'WNS':'-1.0','TNS':'-1.0','Failing':1,'Total':1}
        with self.assertRaisesRegex(ValueError,'outside the proposed'):
            raw.scope.audit_inventory(paths,summaries)

    def test_missing_current_corner_has_no_proposal(self):
        paths,summaries=raw.parse_report(self.report)
        inv=raw.scope.audit_inventory(paths[:1],summaries,require_complete=False)
        self.assertFalse(inv['Complete'])
        with self.assertRaisesRegex(ValueError,'incomplete inventory'):
            raw.native_scope(inv)

    def test_scope_queries_are_exact_current_paths_and_unapplied(self):
        inv=raw.inventory(self.report)
        queries,body,fdc=raw.native_scope(inv)
        self.assertEqual(queries[0]['ExpectedTargetCount'],1)
        self.assertIn('CAMERA720_RAW_RESET_QUERY_',body)
        self.assertNotIn('RAW_CAMERA_DELAY_RESET_QUERY_',body)
        self.assertIn('# UNAPPLIED',fdc)
        self.assertNotIn('set_clock_groups',fdc)
        self.assertNotIn('set_false_path',body)
        self.assertTrue(raw.inspect.query_commands(body))

    def current_graph(self):
        text,queries=graph_fixture()
        old=recovered_top=text.splitlines()[0].split()[1].rstrip(';')
        return text.replace('module '+old+';','module '+raw.prep.TARGET+';',1),queries

    def test_new_graph_proves_registered_reset_without_approval(self):
        text,queries=self.current_graph()
        result=raw.audit_netlist_text(text,queries)
        self.assertEqual(result['Target'],raw.prep.TARGET)
        self.assertTrue(result['RegisteredStickyPropertyVerified'])
        self.assertEqual(result['InternalFunctionalTargetsVerified'],1)
        self.assertFalse(result['TimingExceptionApproved'])
        self.assertFalse(result['HardwareReleaseAllowed'])

    def test_old_graph_is_rejected_before_frozen_parser(self):
        text,queries=graph_fixture()
        with patch.object(raw.graph,'audit_text',side_effect=AssertionError('must not enter old target')):
            with self.assertRaisesRegex(ValueError,'exact current720'):
                raw.audit_netlist_text(text,queries)

    def test_nonsticky_new_graph_remains_failure(self):
        text,queries=self.current_graph()
        text=text.replace(".CK (power_clock_leaf ), .D (1'b1 )",'.CK (power_clock_leaf ), .D (registered_ready )')
        with self.assertRaisesRegex(ValueError,'constant-one D'):
            raw.audit_netlist_text(text,queries)

    def test_new_graph_rejects_added_first_stage_fanout(self):
        text,queries=self.current_graph()
        text=text.replace(".Q (registered_ready ), .CE (1'b1 )",'.Q (registered_ready ), .CE (entry_middle )')
        with self.assertRaisesRegex(ValueError,'first-stage functional fanout'):
            raw.audit_netlist_text(text,queries)

    def test_frozen_module_globals_unchanged_after_header_adapters(self):
        old_target=raw.graph.TARGET
        old_candidate=raw.scope.candidate
        raw.parse_report(self.report)
        text,queries=self.current_graph()
        raw.audit_netlist_text(text,queries)
        self.assertEqual(raw.graph.TARGET,old_target)
        self.assertIs(raw.scope.candidate,old_candidate)


if __name__ == '__main__': unittest.main()
