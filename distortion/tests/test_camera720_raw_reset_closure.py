import copy
import json
import re
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_raw_reset_apply as apply
import camera720_raw_reset_inspect as inspect
import camera720_raw_reset_effect as effect

class ResetApplyTests(unittest.TestCase):
    def queries(self):
        rows=[]
        for source,targets in [('startup/power_ready/opit_0/CLK',['ddr/entry_sync[0]/RS']),
                               ('ddr/reset/opit_0/CLK',['ddr/data[0]/RST','ddr/data[1]/RST'])]:
            rows.append({'Source':source,'Targets':targets,
                'FromRegex':'^('+re.escape(source)+')$',
                'ToRegex':'^('+'|'.join(re.escape(n) for n in targets)+')$',
                'ExpectedFromCount':1,'ExpectedTargetCount':len(targets),
                'ExpectedNativeFromNames':['t:'+source],
                'ExpectedNativeToNames':['t:'+n for n in targets]})
        return rows

    def clean(self):
        return {'Schema':apply.SCHEMA,'Target':apply.prep.TARGET,'ExitCode':0,'EDAExecuted':True,
            'TimedOut':False,'StoppedForUnexpectedStage':False,'InputDrift':[],'Diagnostics':[],
            'ActualEvents':[],'CompletionMarker':True,'InitializationPreservedADF':True,
            'SavedADFReadbackMatches':True,'ResultADFChanged':True,'NativeApplicationNamesVerified':True,
            'Cleanup':{'Complete':True}}

    def test_only_exact_false_paths_between_init_and_single_save(self):
        q=self.queries()
        commands=apply.current.commands.exact_commands(q)
        text=apply.render(commands,apply.prep.WORK/'fixture-reset')
        self.assertEqual(text.count(apply.INIT),1)
        self.assertEqual(text.count('set_false_path '),len(q))
        self.assertEqual(text.count('save_adif'),1)
        self.assertLess(text.index(apply.INIT),text.index('post-init.adf'))
        self.assertLess(text.index('post-init.adf'),text.index('set_false_path '))
        self.assertLess(text.index('save_adif'),text.index('saved-reset.adf'))
        for forbidden in ('manual_route','unroute','gen_bitstream','gen_netlist','set_clock_groups'):
            self.assertNotIn(forbidden,text)

    def test_exit_zero_requires_exact_names_and_zero_critical(self):
        self.assertTrue(apply.execution_ok(self.clean()))
        for k,v in [('NativeApplicationNamesVerified',False),('Diagnostics',['C:STA-3006 bad']),
                    ('InitializationPreservedADF',False),('ResultADFChanged',False),
                    ('SavedADFReadbackMatches',False),('InputDrift',['vendor']),
                    ('ActualEvents',[['Route','started']]),('TimedOut',True)]:
            value=self.clean();value[k]=v
            with self.subTest(field=k):self.assertFalse(apply.execution_ok(value))

    def test_extra_target_cannot_match_native_pin_inventory(self):
        q=self.queries()
        q=copy.deepcopy(q);q[0]['Targets'].append('camera/unsafe/opit_0/RS')
        with self.assertRaises(ValueError):apply.current.commands.exact_commands(q)

    def test_exit_zero_critical_mock_never_executes_real_pds(self):
        with tempfile.TemporaryDirectory(prefix='reset-execution-',dir=apply.prep.WORK) as folder:
            w=Path(folder);stage=w/'stage-plan.json';stage.write_text('{}')
            (w/'input.adf').write_bytes(b'new');(w/'saved-reset.adf').write_bytes(b'new')
            (w/'post-init.adf').write_bytes(b'old')
            value={**self.clean(),'WorkDirectory':str(w),'Command':['mock'],'MaximumSeconds':300,
                   'NativeQueries':[],'ExpectedNativeNameProof':[]}
            class Process:
                pid=42
                def poll(self):return 0
            def popen(*args,**kw):
                kw['stdout'].write(('C:STA-3006 bad\n'+apply.MARKER+'\n').encode());kw['stdout'].flush()
                return Process()
            with (patch.object(apply,'validate_prepared',return_value=(value,{})),
                  patch.object(apply.subprocess,'Popen',side_effect=popen)):
                result=apply.execute(stage)
            self.assertFalse(result['ExecutionPassed'])
            self.assertEqual(len(result['Diagnostics']),1)

class InspectionTests(unittest.TestCase):
    def test_readonly_report_has_no_mutation(self):
        text=inspect.render('report','',apply.prep.WORK,apply.prep.WORK/'new')
        self.assertEqual(text.count(apply.INIT),1)
        for command in ('save_adif','set_false_path','manual_route','unroute','gen_bitstream'):
            self.assertNotIn(command,text)

    def test_reserved_new_marker_and_report_body_rejected(self):
        with self.assertRaises(ValueError):
            inspect.render('query','',apply.prep.WORK,apply.prep.WORK,'puts {'+inspect.MARKER+'}')
        with self.assertRaises(ValueError):
            inspect.render('report','',apply.prep.WORK,apply.prep.WORK,'puts safe')

    def test_old_raw_route_receipt_is_not_reset_application(self):
        with tempfile.TemporaryDirectory(prefix='old-route-',dir=apply.prep.WORK) as folder:
            p=Path(folder)/'result.json';p.write_text(json.dumps({'Schema':'camera720-current-raw-route-application-v1',
                'Target':apply.prep.TARGET,'ExecutionPassed':True,'ExitCode':0}))
            with self.assertRaises(ValueError):apply.bind_completed(p,{})

class EffectTests(unittest.TestCase):
    def tables(self):
        row={'WorstSlackNS':1.0,'TotalNegativeSlackNS':0.0,'FailingChecks':0,'TotalChecks':10}
        tables={(c,k):{('normal','normal'):dict(row)} for c in ('slow','fast') for k in effect.semantics.native.KINDS}
        groups=[]
        for c in ('slow','fast'):
            groups.append({'Corner':c,'LaunchClock':'reset','CaptureClock':'destination','Complete':True,'ObservedLogicalChecks':2})
            for k in ('recovery','removal'):tables[c,k][('reset','destination')]={**row,'TotalChecks':2}
        new=copy.deepcopy(tables)
        for c in ('slow','fast'):
            for k in ('recovery','removal'):del new[c,k][('reset','destination')]
        return tables,new,{'Groups':groups}

    def test_exact_reset_removal_preserves_data_counts_and_slack(self):
        before,after,inventory=self.tables()
        totals,_=effect.semantics.compare_timing(before,after,inventory)
        self.assertTrue(all(v['FailingChecks']==0 for v in totals.values()))
        for field,value in [('TotalChecks',9),('WorstSlackNS',0.9),('FailingChecks',1)]:
            mutated=copy.deepcopy(after);mutated['slow','setup']['normal','normal'][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                effect.semantics.compare_timing(before,mutated,inventory)

    def test_old_top_graph_rejected_before_parser(self):
        with self.assertRaisesRegex(ValueError,'current720'):
            effect.graph('module raw_camera_capture_cam2_delay(input a); endmodule')

    def test_any_unrelated_route_change_rejected(self):
        before={'NetAnnotations':{'a':'1','b':'2'},'TargetConnectivity':{},'RouteCount':2}
        after=copy.deepcopy(before);after['NetAnnotations']['b']='3'
        scope={'NonConstraintNonRouteSHA256':'same'}
        with self.assertRaisesRegex(ValueError,'changed routing'):
            effect.semantics.compare_routes(before,after,scope,scope)

if __name__=='__main__':unittest.main()
