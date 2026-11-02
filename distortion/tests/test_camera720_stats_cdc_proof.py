"""Statistics-only receipt/filter/UART acceptance tests; native calls mocked."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_cdc_proof as proof


class StatsProofTests(unittest.TestCase):
    def test_old_target_rejected_before_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'r.json';path.write_text(json.dumps({'Schema':proof.inspect.SCHEMA,'Target':'camera720_calibrated_top'}))
            with patch.object(proof.importlib,'import_module') as module,self.assertRaises(ValueError):proof.bind_native(path,{'query'},{})
            module.assert_not_called()

    def test_final_dispatch_and_candidate_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'r.json';path.write_text(json.dumps({'Schema':'camera720-calibrated-stats-final-inspection-v1','Target':proof.TARGET}))
            actual={'Mode':'query','ExecutionPassed':True,'SourceADF':'new.adf','SourceADFSHA256':'a'*64}
            with (patch.object(proof.importlib,'import_module') as module,
                  patch.object(proof.inspect,'scan_diagnostics',return_value=[]),
                  patch.object(proof.adapter.structure,'local_helpers',return_value=[])):
                module.return_value.bind_receipt.return_value=(actual,{})
                proof.bind_native(path,{'query'},{},{'Path':'new.adf','SHA256':'a'*64})
                module.assert_called_with('camera720_stats_final_inspect')
                with self.assertRaises(ValueError):proof.bind_native(path,{'query'},{},{'Path':'old.adf','SHA256':'a'*64})

    def test_uart_coverage_has_no_external_acceptance(self):
        launch={'Source':'core_statistics/tx/CLK','LaunchOutput':'core_statistics/tx/L6Q'}
        plan={'UARTSourceOutputs':[launch]};electrical={'Passed':True,'Rows':[{'Port':'uart_txd'}]}
        slow={**launch,'Corner':'slow'}
        value=proof.uart_summary(plan,[slow],electrical)
        self.assertEqual(value['ExpectedMaximumCases'],2);self.assertEqual(value['ObservedMaximumCases'],1)
        self.assertFalse(value['LaunchCoverageComplete'])
        value=proof.uart_summary(plan,[slow,{**slow,'Corner':'fast'}],electrical)
        self.assertTrue(value['LaunchCoverageComplete']);self.assertFalse(value['ExternalACAccepted'])
        self.assertFalse(value['ReceiverSamplingBudgetSpecified'])
        with self.assertRaises(ValueError):proof.uart_summary(plan,[{**slow,'LaunchOutput':'other/L5Q'}],electrical)

    def query_fixture(self,tmp,change=lambda x:x):
        source='core_statistics/tx/CLK';out='core_statistics/tx/L6Q';pattern='^(core_statistics/tx/CLK|core_statistics/tx/L6Q)$'
        command=f'report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE -from {{{source}}} -through {{{out}}} -to {{uart_txd}}'
        path=Path(tmp);body=path/'body.tcl';body.write_text('get_pins -hierarchical -regexp {'+pattern+'}\n'+command+'\n')
        (path/'stdout.log').write_text("Timing-5001: The pattern '"+pattern+"' match 2 objects below: t:"+source+' t:'+out+'\n')
        rel='report_path_timing/report_path_timing_1/report_timing/report_path_timing_1.rtr'
        report=path/rel;report.parent.mkdir(parents=True)
        report.write_text('| Design : '+proof.TARGET+'\n| Tcl Command : '+change(command)+'\n')
        return path,{'QueryBody':str(body),'Artifacts':{rel:'actual-native-binder'}},[{'Source':source,'LaunchOutput':out}]

    def test_uart_exact_through_and_query_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,value,uart=self.query_fixture(tmp)
            reports,issues,_=proof.query_reports(path/'result.json',value,[],uart)
            self.assertEqual(len(reports),1);self.assertEqual(issues,[])

    def test_uart_dropped_through_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,value,uart=self.query_fixture(tmp,lambda s:s.replace(' -through {core_statistics/tx/L6Q}',''))
            with self.assertRaises(ValueError):proof.query_reports(path/'result.json',value,[],uart)

    def test_uart_record_requires_actual_tco_and_core_clock(self):
        launch={'Source':'core_statistics/tx/CLK','LaunchOutput':'core_statistics/tx/L6Q'}
        text='''Startpoint : core_statistics/tx/CLK
Endpoint : uart_txd (port)
Path Type : max (slow corner)
Path Class : combinational timing path
 Clock ddrphy_sysclk (rising edge)
 CLMA_1_1/CR0 tco 0.250 0.750 r core_statistics/tx/L6Q
 Data arrival time 1.250 Logic Levels: 1
'''
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'r.rtr';path.write_text(text)
            rows=proof.uart_records([path],[launch])
            self.assertEqual(rows[0]['Source'],launch['Source'])
            self.assertEqual(rows[0]['ReportedPadArrivalNS'],1.25)
            for altered in (text.replace('/L6Q','/L5Q'),text.replace('ddrphy_sysclk','pixel_clk'),
                            text+'Timing Exception : FALSE PATH\n'):
                path.write_text(altered)
                with self.subTest(altered=altered[-60:]),self.assertRaises(ValueError):proof.uart_records([path],[launch])

    def test_uart_multiple_reports_keep_worst_without_duplication(self):
        launch={'Source':'core_statistics/tx/CLK','LaunchOutput':'core_statistics/tx/L6Q'}
        rows=[{**launch,'Corner':'slow','ReportedPadArrivalNS':delay} for delay in (1.,2.)]
        rows.append({**launch,'Corner':'fast','ReportedPadArrivalNS':.5})
        value=proof.uart_summary({'UARTSourceOutputs':[launch]},rows,{'Passed':True,'Rows':[{'Port':'uart_txd'}]})
        self.assertEqual(len(value['NativeMaximumPaths']),2)
        self.assertEqual(max(r['ReportedPadArrivalNS'] for r in value['NativeMaximumPaths']),2.)


if __name__=='__main__':unittest.main()
