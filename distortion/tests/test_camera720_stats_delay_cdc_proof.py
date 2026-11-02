"""New candidate receipt isolation and actual through-filter safeguards."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_delay_cdc_proof as proof


class DelayProofTests(unittest.TestCase):
    def test_previous_candidates_rejected_before_native_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'r.json'
            for target,schema in (
                ('camera720_calibrated_stats_top','camera720-calibrated-stats-final-inspection-v1'),
                ('camera720_calibrated_top','camera720-calibrated-final-inspection-v1'),
                (proof.TARGET,'camera720-calibrated-stats-final-inspection-v1')):
                path.write_text(json.dumps({'Schema':schema,'Target':target}))
                with patch.object(proof.importlib,'import_module') as module,self.assertRaises(ValueError):
                    proof.bind_native(path,{'query'},{})
                module.assert_not_called()

    def test_explicit_descendant_dispatch_and_exact_adf(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'r.json'
            actual={'Mode':'query','ExecutionPassed':True,'SourceADF':'new.adf','SourceADFSHA256':'a'*64}
            for role,module_name in (('derived','camera720_stats_delay_derived_inspect'),
                                     ('final','camera720_stats_delay_final_inspect'),
                                     ('repaired-final','camera720_stats_delay_repaired_final_inspect')):
                path.write_text(json.dumps({'Schema':f'camera720-calibrated-stats-delay-{role}-inspection-v1','Target':proof.TARGET}))
                with (patch.object(proof.importlib,'import_module') as module,
                      patch.object(proof.inspect,'scan_diagnostics',return_value=[]),
                      patch.object(proof.adapter.structure,'local_helpers',return_value=[])):
                    module.return_value.bind_receipt.return_value=(actual,{})
                    proof.bind_native(path,{'query'},{},{'Path':'new.adf','SHA256':'a'*64})
                    module.assert_called_with(module_name)
                    with self.assertRaises(ValueError):
                        proof.bind_native(path,{'query'},{},{'Path':'old.adf','SHA256':'a'*64})

    def test_exit_zero_receipt_does_not_hide_critical_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'r.json';path.write_text(json.dumps({'Schema':proof.inspect.SCHEMA,'Target':proof.TARGET}))
            actual={'Mode':'query','ExecutionPassed':True}
            with (patch.object(proof.importlib,'import_module') as module,
                  patch.object(proof.inspect,'scan_diagnostics',return_value=['C:STA-3006 invalid endpoint']),
                  self.assertRaises(ValueError)):
                module.return_value.bind_receipt.return_value=(actual,{})
                proof.bind_native(path,{'query'},{})

    def query(self,tmp,change=lambda x:x,target=None):
        source='core_statistics/tx/CLK';out='core_statistics/tx/L6Q'
        pattern='^(core_statistics/tx/CLK|core_statistics/tx/L6Q)$'
        command=f'report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE -from {{{source}}} -through {{{out}}} -to {{uart_txd}}'
        path=Path(tmp);body=path/'body.tcl';body.write_text('get_pins -hierarchical -regexp {'+pattern+'}\n'+command+'\n')
        (path/'stdout.log').write_text("Timing-5001: The pattern '"+pattern+"' match 2 objects below: t:"+source+' t:'+out+'\n')
        rel='report_path_timing/report_path_timing_1/report_timing/report_path_timing_1.rtr'
        report=path/rel;report.parent.mkdir(parents=True)
        report.write_text('| Design : '+(target or proof.TARGET)+'\n| Tcl Command : '+change(command)+'\n')
        return path,{'QueryBody':str(body),'Artifacts':{rel:'bound-by-native-receipt'}},[{'Source':source,'LaunchOutput':out}]

    def test_current_header_and_exact_through_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,value,uart=self.query(tmp)
            reports,issues,_=proof.query_reports(path/'result.json',value,[],uart)
            self.assertEqual(len(reports),1);self.assertEqual(issues,[])

    def test_old_report_target_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,value,uart=self.query(tmp,target='camera720_calibrated_stats_top')
            with self.assertRaises(ValueError):proof.query_reports(path/'result.json',value,[],uart)

    def test_native_through_drop_or_change_rejected(self):
        for change in (lambda s:s.replace(' -through {core_statistics/tx/L6Q}',''),
                       lambda s:s.replace('/L6Q','/L5Q')):
            with tempfile.TemporaryDirectory() as tmp:
                path,value,uart=self.query(tmp,change)
                with self.assertRaises(ValueError):proof.query_reports(path/'result.json',value,[],uart)

    def test_missing_pin_enum_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path,value,uart=self.query(tmp)
            (path/'stdout.log').write_text('')
            _,issues,_=proof.query_reports(path/'result.json',value,[],uart)
            self.assertTrue(issues)

    def test_old_work_root_not_used(self):
        self.assertEqual(proof.WORK,proof.PROJECT/'work/camera720-stats-delay')
        with self.assertRaises(ValueError):
            proof.prepare('not-read','not-read',proof.PROJECT/'work/camera720-calibrated-stats-delay/invalid')


if __name__=='__main__':unittest.main()
