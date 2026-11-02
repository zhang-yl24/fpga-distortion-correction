import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_delay_reset as audit


def inventory():
    ip='u_ddr3_test_h/u_ddrphy_top/'
    slice_=ip+'ddrphy_slice_top/i_dqs_group[3].ddrphy_data_slice/'
    rows=[
      ('power_ready/opit_0','board27','rst_clk',ip+'u_ddrphy_rst_seq_rstn_sync/sig_async_r1[0]/opit_0/RS'),
      (ip+'ddrphy_cpd_ctrl/ddrphy_cpd_rstn/opit_0','rst_clk','phy_dq_sysclk_0',ip+'u_ddrphy_cpd/cpd_inst/RST'),
      (ip+'ddrphy_reset_ctrl/ddrphy_dqs_rst/opit_0','rst_clk','phy_dq_sysclk_1',slice_+'dq_loop[7].u_iobuf_dq/opit_1/ISR_IOLHR'),
      (ip+'ddrphy_reset_ctrl/ddrphy_iol_rst/opit_0','rst_clk','phy_dq_sysclk_1',slice_+'dq_loop[7].u_iobuf_dq/opit_1/TSR'),
      (ip+'ddrphy_training_ctrl/ddrphy_dqs_training_rstn/opit_0','ddrphy_sysclk','phy_dq_sysclk_1',slice_+'u_ddc_x/opit_0/RST_TRAINING_N')]
    checks=[]
    for source,launch,capture,target in rows:
        value={'Source':source+'/CLK','Endpoint':target,'LaunchClock':launch,'CaptureClock':capture}
        value['Family']=audit.scope.classify(value);checks.append(value)
    return {'Complete':True,'Corners':{'slow':{'Checks':checks}}}


class StatisticsResetTests(unittest.TestCase):
    def test_scope_counts_are_derived_not_inherited_127(self):
        queries,body,commands=audit.exact_scope(inventory())
        self.assertEqual(len(queries),5)
        self.assertEqual(sum(q['ExpectedTargetCount'] for q in queries),5)
        self.assertEqual(len(commands),5)
        self.assertIn('CAMERA720_STATS_DELAY_RESET_QUERY_',body)
        self.assertNotIn('set_clock_groups',body)
        self.assertNotIn('set_clock_groups','\n'.join(commands))

    def test_rejects_data_pin_while_keeping_reset_family_claim(self):
        inv=inventory();inv['Corners']['slow']['Checks'][2]['Endpoint']=inv['Corners']['slow']['Checks'][2]['Endpoint'].rsplit('/',1)[0]+'/D'
        with self.assertRaisesRegex(ValueError,'non-reset target'):audit.exact_scope(inv)

    def test_missing_reset_family_rejected(self):
        inv=inventory();inv['Corners']['slow']['Checks'].pop()
        with self.assertRaisesRegex(ValueError,'families'):audit.exact_scope(inv)

    def test_unexpected_source_clock_rejected(self):
        inv=inventory();inv['Corners']['slow']['Checks'][2]['LaunchClock']='camera_pclk'
        with self.assertRaisesRegex(ValueError,'source clock'):audit.exact_scope(inv)

    def test_wrong_source_ff_clock_pin_rejected(self):
        inv=inventory();inv['Corners']['slow']['Checks'][0]['Source']='power_ready/opit_0/D'
        with self.assertRaisesRegex(ValueError,'clock pin'):audit.exact_scope(inv)

    def test_only_top_token_is_adapted(self):
        text='module camera720_calibrated_stats_delay_top (input clk);\n// camera720_calibrated_stats_delay_top\nwire camera720_calibrated_stats_delay_top_signal;\nendmodule\n'
        result=audit.adapt_netlist(text)
        self.assertEqual(result,text.replace('module camera720_calibrated_stats_delay_top','module camera_vga_output_top',1))

    def test_wrong_multiple_and_missing_top_rejected(self):
        for text in ('module camera720_transport_top (); endmodule','module camera720_calibrated_stats_delay_top (); endmodule\nmodule other(); endmodule','wire x;'):
            with self.subTest(text=text),self.assertRaises(ValueError):audit.adapt_netlist(text)

    def test_report_adapter_does_not_rewrite_names_or_lines(self):
        text='intro\n| Design : camera720_calibrated_stats_delay_top\nStartpoint : camera720_calibrated_stats_delay_top/path/CLK\n'
        seen={}
        def parse(path):seen['text']=Path(path).read_text();return ['raw'],{'summary':1}
        with tempfile.TemporaryDirectory() as tmp:
            report=Path(tmp)/'a.rtr';report.write_text(text)
            with patch.object(audit.scope,'parse_report',side_effect=parse),patch.object(audit.scope,'audit_inventory',return_value={'Complete':True}):
                _,adapter=audit.inventory(report)
        self.assertEqual(seen['text'],text.replace('| Design : camera720_calibrated_stats_delay_top','| Design : camera_vga_output_top'))
        self.assertTrue(adapter['NativeNamesAndLineNumbersUnchanged'])

    def test_wrong_missing_duplicate_design_headers_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'a.rtr'
            for text in ('| Design : camera720_transport_top\n','Startpoint : x\n','| Design : camera720_calibrated_stats_delay_top\n'*2):
                path.write_text(text)
                with self.subTest(text=text),self.assertRaises(ValueError):audit.inventory(path)

    def test_exact_binding_rejects_hash_drift_and_extra_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'x';path.write_text('source')
            watched={};reference=audit.ref(path)
            self.assertEqual(audit.binding(reference,watched),path)
            with self.assertRaises(ValueError):audit.binding({**reference,'Passed':True},{})
            path.write_text('changed')
            with self.assertRaises(ValueError):audit.binding(reference,{})

    def test_merge_rejects_conflicting_closure(self):
        path=Path('a.py')
        with self.assertRaises(ValueError):audit.merge({path:'a'},{path:'b'})

    def test_verify_does_not_accept_saved_boolean(self):
        saved={'Schema':audit.SCHEMA,'Target':audit.prep.TARGET,'ExportReceipt':{},'QueryReceipt':{},'Complete':True}
        with patch.object(audit,'read',return_value=saved),patch.object(audit,'binding',return_value=Path('native.json')),patch.object(audit,'audit_value',return_value=({**saved,'Complete':False},{})):
            with self.assertRaisesRegex(ValueError,'actual recomputation'):audit.verify('proof.json')

    def test_vendor_generated_target_must_match(self):
        export={'BuildPlan':str(Path.cwd()/'build/plan.json')}
        with patch.object(audit,'add',side_effect=lambda w,p,e=None:Path(p)),patch.object(audit,'read',return_value={'Target':'camera720_transport_top'}):
            with self.assertRaisesRegex(ValueError,'manifest target'):audit.vendor_basis(export,{})

    def test_native_query_wrong_target_count_is_rejected(self):
        queries,_,_=audit.exact_scope(inventory())
        lines=[]
        for query in queries:
            for regex,names in ((query['FromRegex'],query['ExpectedNativeFromNames']),(query['ToRegex'],query['ExpectedNativeToNames'])):
                lines.append("I: Timing-5001: The pattern '"+regex+"' in command 'get_pins -hierarchical -regexp {"+regex+"}' match "+str(len(names))+" objects below: "+' '.join(names))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'native.log';path.write_text('\n'.join(lines))
            self.assertEqual(len(audit.queries_parser.exact_queries(queries,path)),10)
            path.write_text('\n'.join(lines).replace('match 1 objects','match 2 objects',1))
            with self.assertRaises(ValueError):audit.queries_parser.exact_queries(queries,path)


    def test_scope_preparation_remains_unapplied_until_native_query(self):
        base={'Schema':audit.SCOPE_SCHEMA,'NativeQueriesVerified':False,
              'TimingExceptionApproved':False,'ConstraintsApplied':False,
              'HardwareReleaseAllowed':False,'ExactResetCommands':['set_false_path exact']}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();out=root/'scope'
            with patch.object(audit.prep,'WORK',root),patch.object(audit,'derive_scope_value',return_value=(base,{},'get_pins exact\n')),patch.object(audit.inspect,'drift',return_value=[]):
                result=audit.prepare_scope('export.json',out)
            self.assertFalse(result['NativeQueriesVerified'])
            self.assertFalse(result['TimingExceptionApproved'])
            self.assertFalse(result['ConstraintsApplied'])
            self.assertEqual(audit.sha(out/'query-body.tcl'),result['FilesSHA256']['query-body.tcl'])
            with patch.object(audit.prep,'WORK',root),self.assertRaisesRegex(ValueError,'fresh'):
                audit.prepare_scope('export.json',out)

    def test_scope_cannot_pass_as_native_proof(self):
        with patch.object(audit,'read',return_value={'Schema':audit.SCOPE_SCHEMA,'Target':audit.prep.TARGET,'Complete':True}):
            with self.assertRaisesRegex(ValueError,'wrong reset proof'):audit.verify('scope.json')

    def test_native_query_must_use_same_actual_adf(self):
        base={'BuildPlan':'plan','BuildPlanSHA256':'b','SourceADF':{'Path':'actual.adf','SHA256':'a'}}
        query={'Mode':'query','Target':audit.prep.TARGET,'BuildPlan':'plan','BuildPlanSHA256':'b',
               'SourceADF':'other.adf','SourceADFSHA256':'a'}
        with patch.object(audit,'derive_scope_value',return_value=(base,{},'get_pins exact\n')),patch.object(audit.inspect,'bind_receipt',return_value=(query,{})):
            with self.assertRaisesRegex(ValueError,'different candidates'):audit.audit_value('export.json','query.json')

    def test_native_body_cannot_broaden_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            body=Path(tmp)/'query.tcl';body.write_text('get_pins *\n')
            base={'BuildPlan':'plan','BuildPlanSHA256':'b','SourceADF':{'Path':'actual.adf','SHA256':'a'}}
            query={'Mode':'query','Target':audit.prep.TARGET,'BuildPlan':'plan','BuildPlanSHA256':'b',
                   'SourceADF':'actual.adf','SourceADFSHA256':'a','QueryBody':str(body)}
            with patch.object(audit,'derive_scope_value',return_value=(base,{},'get_pins exact\n')),patch.object(audit.inspect,'bind_receipt',return_value=(query,{})):
                with self.assertRaisesRegex(ValueError,'selector body differs'):audit.audit_value('export.json','query.json')


if __name__=='__main__':unittest.main()
