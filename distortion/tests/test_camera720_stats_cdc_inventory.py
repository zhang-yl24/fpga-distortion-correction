"""CPU glue tests; native receipt operations are explicit mocks, never PDS."""
from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_cdc_inventory as tool


class StatsInventoryTests(unittest.TestCase):
    def test_old_target_receipt_never_enters_stats_binder(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'result.json'
            for value in ({'Schema':'camera720-calibrated-final-inspection-v1','Target':'camera720_calibrated_top'},
                          {'Schema':tool.inspect.SCHEMA,'Target':'camera720_calibrated_top'}):
                path.write_text(json.dumps(value))
                with patch.object(tool.inspect,'bind_receipt') as bind,self.assertRaises(ValueError):
                    tool.bind_native(path,{'export'},{})
                bind.assert_not_called()

    def test_pair_requires_exact_candidate_build_and_route_role(self):
        base={'SourceADF':'current.adf','SourceADFSHA256':'a'*64,'BuildPlan':'current/plan.json',
              'BuildPlanSHA256':'b'*64,'NativeNetlistWithFFloc':True,'Artifacts':{'route-dump.txt':'c'*64}}
        with patch.object(tool,'bind_native',side_effect=[base,dict(base)]):
            export,route,watched=tool.bind_pair('export/result.json','report/result.json')
            self.assertEqual(export,route)
        for key in ('SourceADF','SourceADFSHA256','BuildPlan','BuildPlanSHA256'):
            altered={**base,key:'different'}
            with self.subTest(key=key),patch.object(tool,'bind_native',side_effect=[base,altered]),self.assertRaises(ValueError):
                tool.bind_pair('export/result.json','report/result.json')
        with patch.object(tool,'bind_native',side_effect=[base,{**base,'Artifacts':{}}]),self.assertRaises(ValueError):
            tool.bind_pair('export/result.json','report/result.json')

    def report(self,tmp,missing=None,changed_clock=False):
        path=Path(tmp)/'r.rtr';blocks=[]
        for port in sorted(tool.adapter.native_io.PORTS):
            if port==missing:continue
            blocks.append(f'''Startpoint : {port} (port)
Endpoint : system/input_link/input_dma/capture/current/I0
Path Type : max (slow corner)
Path Class : sequential timing path
 Clock {'pixel_clk' if changed_clock else 'camera_pclk'} (rising edge)
 Clock camera_pclk (rising edge)
 Slack (VIOLATED) -0.100
''')
        path.write_text('\n'.join(blocks))
        return path

    def test_negative_dvp_setup_can_request_diagnosis_but_is_not_passed(self):
        with tempfile.TemporaryDirectory() as tmp:
            pairs,rows=tool.dvp_query_pairs(self.report(tmp))
            self.assertEqual(len(pairs),10)
            self.assertTrue(all(r['State']=='VIOLATED' and r['SlackNS']==-.1 for r in rows))

    def test_missing_dvp_or_changed_clock_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):tool.dvp_query_pairs(self.report(tmp,missing='cam_href'))
            with self.assertRaises(ValueError):tool.dvp_query_pairs(self.report(tmp,changed_clock=True))

    def initial(self):
        q={'Source':'new_source/CLK','LaunchOutput':'new_source/L5Q','Endpoint':'new_target/I0',
           'Clock':'board27','Corners':['slow','fast'],'CheckKinds':['setup','hold'],'LogicalRelationships':[0]}
        return {'Queries':[q],'InitialCoverage':{'MissingCases':[q]},'BuildPlan':{'Path':'build/plan.json'},
                'CandidateADF':{'Path':'new.adf','SHA256':'a'*64},'BuildDiagnosticsReview':None}

    def test_prepare_only_writes_current_queries_no_native_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/'queries'
            with (patch.object(tool,'WORK',Path(tmp)),patch.object(tool,'derive',return_value=(self.initial(),{},'show -dev_instance {UART_SITE}\n')),
                  patch.object(tool.inspect,'execute') as execute):
                result=tool.prepare('export','report',output,8)
            self.assertEqual(len(result['Groups']),1)
            self.assertEqual(set(result['QueryBodies']),{'query-00.tcl','query-io.tcl'})
            self.assertFalse(result['EDAExecuted']);self.assertFalse(result['NativeQueriesExecuted'])
            self.assertFalse(result['HardwareReleaseAllowed'])
            self.assertIn('new_target/I0',(output/'query-00.tcl').read_text())
            execute.assert_not_called()

    def test_optional_stage_preparation_uses_actual_identity_and_never_executes(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);output=work/'queries';calls=[]
            def stage(*args):
                calls.append(args);path=args[3]/'stage-plan.json';path.parent.mkdir();path.write_text('{}');return path
            initial=self.initial();initial['BuildDiagnosticsReview']={'Path':'review.json','SHA256':'b'*64}
            with (patch.object(tool,'WORK',work),patch.object(tool,'derive',return_value=(initial,{},'show -dev_instance {UART_SITE}\n')),
                  patch.object(tool.inspect,'prepare',side_effect=stage),patch.object(tool.inspect,'execute') as execute):
                tool.prepare('export','report',output,8,'native')
            self.assertEqual(len(calls),2)
            for args in calls:
                self.assertEqual(args[:3],('build/plan.json','new.adf','a'*64))
                self.assertEqual(args[4],'query');self.assertEqual(args[6],300)
                self.assertEqual(args[7:],('review.json','b'*64))
            self.assertTrue((output/'prepared-stages.json').is_file())
            execute.assert_not_called()

    def test_invalid_prefix_bounds_or_reused_output_fail_before_derivation(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp)
            for count,prefix,output in ((9,None,work/'new'),(8,'../escape',work/'new'),(8,None,work)):
                with self.subTest(count=count,prefix=prefix),patch.object(tool,'WORK',work),patch.object(tool,'derive') as derive,self.assertRaises(ValueError):
                    tool.prepare('export','report',output,count,prefix)
                derive.assert_not_called()


if __name__=='__main__':unittest.main()
