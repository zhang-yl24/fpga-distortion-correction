import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_delay_reset_apply as apply
import camera720_stats_delay_reset_effect as effect


def tables():
    row={'TotalChecks':7,'FailingChecks':0,'WorstSlackNS':1.2,'TotalNegativeSlackNS':0}
    result={(corner,kind):{('data','data'):dict(row)}
        for corner in ('slow','fast') for kind in apply.timing.native.KINDS}
    inv={'Groups':[]}
    for corner in ('slow','fast'):
        pair=('rst_clk','phy_dq_sysclk_0')
        for kind in ('recovery','removal'):
            result[corner,kind][pair]={'TotalChecks':3,'FailingChecks':3 if kind=='recovery' else 0,
                'WorstSlackNS':-.8 if kind=='recovery' else .5,'TotalNegativeSlackNS':-1.2 if kind=='recovery' else 0}
        inv['Groups'].append({'Corner':corner,'LaunchClock':pair[0],'CaptureClock':pair[1],
                             'Complete':True,'ObservedLogicalChecks':3})
    return result,inv


def success():
    return {'Schema':apply.SCHEMA,'Target':apply.prep.TARGET,'ExitCode':0,'EDAExecuted':True,
        'TimedOut':False,'StoppedForUnexpectedStage':False,'InputDrift':[],'Diagnostics':[],
        'ActualEvents':[],'CompletionMarker':True,'InitializationPreservedADF':True,
        'SavedADFReadbackMatches':True,'ResultADFChanged':True,'NativeApplicationNamesVerified':True,
        'RoutesAndPlacementUnchanged':True,'Cleanup':{'Complete':True}}


class ResetApplyTests(unittest.TestCase):
    def test_render_initializes_before_constraints_and_saves_once(self):
        command='set_false_path -from [get_pins -hierarchical -regexp {^(src/CLK)$}] -to [get_pins -hierarchical -regexp {^(dst/RS)$}]'
        text=apply.render([command],Path('D:/stage'))
        self.assertLess(text.index(apply.INIT),text.index(command))
        self.assertLess(text.index('post-init.adf'),text.index(command))
        self.assertEqual(text.count('save_adif'),1)
        self.assertNotIn('manual_route',text)
        self.assertNotIn('set_clock_groups',text)
        self.assertNotIn('generate_bit',text)
        self.assertTrue(apply.DUMMY.endswith('\n'))
        self.assertNotIn('\\n',apply.DUMMY)

    def test_native_success_flags_cannot_omit_any_check(self):
        value=success();self.assertTrue(apply.execution_ok(value))
        for key in ('EDAExecuted','CompletionMarker','InitializationPreservedADF','SavedADFReadbackMatches',
                    'ResultADFChanged','NativeApplicationNamesVerified','RoutesAndPlacementUnchanged'):
            with self.subTest(key=key):self.assertFalse(apply.execution_ok({**value,key:False}))
        for key,val in [('TimedOut',True),('StoppedForUnexpectedStage',True),('InputDrift',['source']),
                        ('Diagnostics',['C: diagnostic']),('ActualEvents',[['Bitgen','started']]),
                        ('Error','failure'),('ExitCode',1),('Cleanup',{'Complete':False})]:
            with self.subTest(key=key):self.assertFalse(apply.execution_ok({**value,key:val}))

    def test_only_current_exact_recovery_failures_can_remain_before_apply(self):
        current,inv=tables();apply.nonreset_checks(current,inv)
        current['slow','hold']['data','data']['FailingChecks']=1
        with self.assertRaisesRegex(ValueError,'non-proposed'):apply.nonreset_checks(current,inv)

    def test_non_ddr_recovery_failure_cannot_be_hidden(self):
        current,inv=tables();current['fast','recovery']['data','data']['WorstSlackNS']=-.1
        with self.assertRaisesRegex(ValueError,'non-proposed'):apply.nonreset_checks(current,inv)

    def test_missing_timing_table_rejected(self):
        current,inv=tables();current.pop(('slow','setup'))
        with self.assertRaisesRegex(ValueError,'ten native'):apply.nonreset_checks(current,inv)

    def test_native_mpw_single_clock_keys_are_checked(self):
        current,inv=tables()
        for corner in ('slow','fast'):
            current[corner,'mpw']={'board27':{'TotalChecks':4,'FailingChecks':0,'WorstSlackNS':.035,'TotalNegativeSlackNS':0}}
        apply.nonreset_checks(current,inv)
        current['fast','mpw']['board27']['WorstSlackNS']=-.001
        with self.assertRaisesRegex(ValueError,'non-proposed'):apply.nonreset_checks(current,inv)

    def test_exact_removed_counts_derived_not_old_490(self):
        before,inv=tables();after=copy.deepcopy(before)
        for corner in ('slow','fast'):
            for kind in ('recovery','removal'):after[corner,kind].pop(('rst_clk','phy_dq_sysclk_0'))
        result,_=effect.semantics.compare_timing(before,after,inv)
        self.assertEqual(result['slow_recovery']['RemovedResetChecks'],3)
        self.assertEqual(result['fast_removal']['RemovedResetChecks'],3)
        self.assertEqual(result['slow_hold']['RemovedResetChecks'],0)

    def test_data_count_reduction_after_reset_rejected(self):
        before,inv=tables();after=copy.deepcopy(before)
        for corner in ('slow','fast'):
            for kind in ('recovery','removal'):after[corner,kind].pop(('rst_clk','phy_dq_sysclk_0'))
        after['fast','setup']['data','data']['TotalChecks']=6
        with self.assertRaisesRegex(ValueError,'removed'):effect.semantics.compare_timing(before,after,inv)

    def test_unexpected_setup_slack_change_after_reset_rejected(self):
        before,inv=tables();after=copy.deepcopy(before)
        for corner in ('slow','fast'):
            for kind in ('recovery','removal'):after[corner,kind].pop(('rst_clk','phy_dq_sysclk_0'))
        after['slow','setup']['data','data']['WorstSlackNS']=2.3
        with self.assertRaisesRegex(ValueError,'non-reset timing'):effect.semantics.compare_timing(before,after,inv)

    def test_incorrect_reset_count_rejected(self):
        before,inv=tables();after=copy.deepcopy(before)
        for corner in ('slow','fast'):
            for kind in ('recovery','removal'):after[corner,kind].pop(('rst_clk','phy_dq_sysclk_0'))
        inv['Groups'][0]['ObservedLogicalChecks']=2
        with self.assertRaisesRegex(ValueError,'count differs'):effect.semantics.compare_timing(before,after,inv)

    def test_reset_save_rejects_any_changed_route(self):
        before={'NetAnnotations':{'a':'1'},'TargetRoutes':{},'TargetConnectivity':{},'ExcludedBlockSHA256':{'FILETABLE':'same','CDB':'old'}}
        after={**before,'NetAnnotations':{'a':'2'}}
        separated={'NonConstraintNonRouteSHA256':'same','ConstraintPinReferences':[],'SourceLocations':{}}
        with patch.object(apply.routes,'inspect',side_effect=[before,after]),patch.object(apply.separated,'constraint_separated',return_value=separated),patch.object(apply,'filetable_tokens',return_value=['(','FILETABLE',')']):
            with self.assertRaisesRegex(ValueError,'route inventory'):apply.compare_routes('a','b')

    def test_reset_save_rejects_filetable_loss(self):
        before={'ExcludedBlockSHA256':{'FILETABLE':'old'}};after={'ExcludedBlockSHA256':{'FILETABLE':'new'}}
        with patch.object(apply.routes,'inspect',side_effect=[before,after]),patch.object(apply.separated,'constraint_separated',return_value={'SourceLocations':{'Counts':{}}}),patch.object(apply,'filetable_tokens',side_effect=[['(','FILETABLE','(','FILEMAP','2','"actual.v"',')',')'],['(','FILETABLE',')']]):
            with self.assertRaisesRegex(ValueError,'source file table'):apply.compare_routes('a','b')

    def test_maximum_bound_is_checked_before_binding_any_candidate(self):
        with patch.object(apply.prep,'work_path',return_value=Path('D:/stage')),patch.object(apply,'bind_request') as bind:
            for maximum in (0,119,301,True):
                with self.subTest(maximum=maximum),self.assertRaises(ValueError):apply.recipe('none',Path('D:/stage'),maximum)
            bind.assert_not_called()

    def test_effect_verify_rejects_claimed_pass_different_from_actual(self):
        saved={'Schema':effect.SCHEMA,'Target':effect.prep.TARGET,'ApplicationReceipt':{},'CandidateExportReceipt':{},'AuditPassed':True}
        with patch.object(effect,'read',return_value=saved),patch.object(effect.physical,'binding',return_value=Path('native.json')),patch.object(effect,'audit_value',return_value=({**saved,'AuditPassed':False},{})):
            with self.assertRaisesRegex(ValueError,'recomputation'):effect.verify('proof.json')

    def test_false_path_union_keeps_actual_variants_without_old_count(self):
        row={'Source':'reset_ff/CLK','Endpoint':'entry_ff/RS','LaunchClock':'board27','CaptureClock':'rst_clk',
             'LaunchEdge':'rising','CaptureEdge':'rising','LaunchDataTransition':'r','NativePathSignature':'timed'}
        inv={'Corners':{c:{'Checks':[{'NativeVariants':[dict(row)]}]} for c in ('slow','fast')}}
        before={(c,k):[] for c in ('slow','fast') for k in ('setup','hold','recovery','removal')}
        after=copy.deepcopy(before)
        for c in ('slow','fast'):
            for k in ('recovery','removal'):
                after[c,k]=[{**row,'CaptureEdge':'falling','NativePathSignature':c+k}]
        value=effect.semantics.compare_false_paths(before,after,inv)
        self.assertEqual(value['slow_recovery']['UniqueClockAndPinChecks'],1)
        self.assertEqual(value['slow_recovery']['ReportedPathVariants'],1)
        after['fast','setup']=[row]
        with self.assertRaisesRegex(ValueError,'unexpected or missing'):effect.semantics.compare_false_paths(before,after,inv)

    def test_false_path_union_rejects_missing_or_other_reset_pin(self):
        row={'Source':'reset_ff/CLK','Endpoint':'entry_ff/RS','LaunchClock':'board27','CaptureClock':'rst_clk',
             'LaunchEdge':'rising','CaptureEdge':'rising','LaunchDataTransition':'r','NativePathSignature':'native'}
        inv={'Corners':{c:{'Checks':[{'NativeVariants':[dict(row)]}]} for c in ('slow','fast')}}
        before={(c,k):[] for c in ('slow','fast') for k in ('setup','hold','recovery','removal')}
        after={key:([dict(row)] if key[1] in ('recovery','removal') else []) for key in before}
        for bad in ([],[{**row,'Endpoint':'other_ff/RS'}]):
            changed=copy.deepcopy(after);changed['fast','recovery']=bad
            with self.subTest(bad=bad),self.assertRaisesRegex(ValueError,'unexpected or missing'):
                effect.semantics.compare_false_paths(before,changed,inv)

    def test_existing_unapproved_false_paths_rejected(self):
        with self.assertRaisesRegex(ValueError,'baseline contains'):
            effect.semantics.compare_false_paths({('slow','hold'):[{'Source':'unexpected'}]}, {}, {})


if __name__=='__main__':unittest.main()


class DelayBaselineBindingTests(unittest.TestCase):
    def test_rejects_older_target_before_functional_parser(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'net.v';path.write_text('module camera720_calibrated_stats_top(); endmodule')
            with patch.object(apply.io.structure,'functional') as parser:
                with self.assertRaisesRegex(ValueError,'exact delay'):apply.functional(path)
                parser.assert_not_called()

    def test_functional_adapter_changes_only_exact_declaration(self):
        import tempfile
        text='module camera720_calibrated_stats_delay_top();\n// camera720_calibrated_stats_delay_top\nwire x; endmodule'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'net.v';path.write_text(text)
            with patch.object(apply.io.structure,'functional',return_value={'Cells':{}}) as parser:
                apply.functional(path)
            self.assertEqual(parser.call_args.args[0],text.replace('module '+apply.prep.TARGET,'module '+apply.io.structure.prep.TARGET,1))

    def test_original_baseline_receipts_must_match_every_identity(self):
        import tempfile,json
        for field,bad in [('Mode','export'),('Target','camera720_calibrated_stats_top'),
                          ('SourceADF','other.adf'),('SourceADFSHA256','b'*64),('BuildPlan','other.json'),
                          ('BuildPlanSHA256','c'*64)]:
            with self.subTest(field=field),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp).resolve()
                for name in ('proof','export','report'):(root/(name+'.json')).write_text('{}')
                request={'Schema':apply.REQUEST_SCHEMA,'Target':apply.prep.TARGET,
                    'ResetProof':apply.ref(root/'proof.json'),'BaselineExport':apply.ref(root/'export.json'),
                    'BaselineReport':apply.ref(root/'report.json')}
                path=root/'request.json';path.write_text(json.dumps(request))
                base={'Target':apply.prep.TARGET,'SourceADF':'actual.adf','SourceADFSHA256':'a'*64,
                      'BuildPlan':'actual-plan.json','BuildPlanSHA256':'d'*64}
                original={'ExportReceipt':request['BaselineExport'],'SourceADF':{'Path':'actual.adf','SHA256':'a'*64},
                    'BuildPlan':'actual-plan.json','BuildPlanSHA256':'d'*64}
                report={**base,'Mode':'report',field:bad}
                with patch.object(apply.prep,'WORK',root),patch.object(apply.proof,'verify',return_value=(original,{})),\
                     patch.object(apply.inspect,'bind_receipt',side_effect=[({**base,'Mode':'export'},{}),(report,{})]),\
                     patch.object(apply,'functional') as graph:
                    with self.assertRaisesRegex(ValueError,'another delay candidate'):apply.bind_request(path)
                    graph.assert_not_called()

    def test_no_historical_route_application_can_be_injected(self):
        import tempfile,json
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();path=root/'request.json'
            path.write_text(json.dumps({'Schema':apply.REQUEST_SCHEMA,'Target':apply.prep.TARGET,
                'ResetProof':{},'BaselineExport':{},'BaselineReport':{},'RouteApplication':{}}))
            with patch.object(apply.prep,'WORK',root),patch.object(apply.proof,'verify') as verify:
                with self.assertRaisesRegex(ValueError,'exact reset-only'):apply.bind_request(path)
                verify.assert_not_called()


class ExactSourceMetadataTests(unittest.TestCase):
    def test_unchanged_table_cannot_hide_numeric_location_changes(self):
        table=['(','FILETABLE',')']
        a={'Counts':{'FILEID':2,'LINENUM':2},'SHA256':'a'}
        for b in ({'Counts':{},'SHA256':'b'}, {**a,'SHA256':'b'}):
            with self.subTest(b=b),self.assertRaisesRegex(ValueError,'identical outside-CDB'):
                apply.filetable_policy(table,table,a,b)

    def test_only_known_empty_map_removal_is_allowed(self):
        before=['(','FILETABLE','(','FILEMAP','2','""',')',')'];after=['(','FILETABLE',')']
        a={'Counts':{'FILEID':12,'LINENUM':12}};b={'Counts':{}}
        value=apply.filetable_policy(before,after,a,b)
        self.assertTrue(value['ExactEmptyFileMapRemoval'])
        self.assertFalse(value['FunctionalOrTimingExceptionChangePermitted'])
        for field,bad in [(4,'3'),(5,'"source.v"'),(3,'FILEMAP_OTHER')]:
            changed=list(before);changed[field]=bad
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'source file table'):
                apply.filetable_policy(changed,after,a,b)
        for old,new in [({'FILEID':1,'LINENUM':2},{}),({'FILEID':2,'LINENUM':2},{'FILEID':1}),
                        ({'FILEID':2,'LINENUM':2,'FUNCTION':1},{})]:
            with self.subTest(old=old,new=new),self.assertRaisesRegex(ValueError,'paired numeric'):
                apply.filetable_policy(before,after,{'Counts':old},{'Counts':new})

    def test_parser_keeps_full_table_and_rejects_truncation(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'route.txt'
            path.write_text('(ADIF "x"\n (FILETABLE\n  (FILEMAP 2 "")\n )\n)\n')
            self.assertEqual(apply.filetable_tokens(path),['(','FILETABLE','(','FILEMAP','2','""',')',')'])
            path.write_text('(ADIF "x"\n (FILETABLE\n  (FILEMAP 2 "")\n')
            with self.assertRaisesRegex(ValueError,'missing or truncated'):apply.filetable_tokens(path)
