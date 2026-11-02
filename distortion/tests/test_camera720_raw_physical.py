"""Focused CPU route-only scope, readback and native-failure checks."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_raw_physical as physical
import camera720_raw_derived_inspect as derived


class RouteScopeTests(unittest.TestCase):
    def setUp(self):
        self.targets=[{'Net':'_N46','ToRoutePin':'A4:CLMA_219_594'},
                      {'Net':'_N174','ToRoutePin':'TX_DATA[3]:IOLHR_364_744'}]
        self.rows=[{'Net':'_N46','Branch':'A4:CLMA_219_594','Pins':'ZDNE[0]:SRB_12_180>IDNE[0]:SRB_18_186;'},
                   {'Net':'_N174','Branch':'TX_DATA[3]:IOLHR_364_744','Pins':'ZDNE[1]:SRB_342_720>IDNE[1]:SRB_348_726;'}]

    def test_route_only_always_initializes_once_before_edits_and_save(self):
        commands=physical.route_helpers.route_commands(self.rows,self.targets,{})
        text=physical.render(commands,physical.prep.WORK/'fixture-only')
        self.assertEqual(text.count(physical.INIT),1)
        self.assertEqual(text.count('save_adif'),1)
        self.assertLess(text.index(physical.INIT),text.index('post-init.adf'))
        self.assertLess(text.index('post-init.adf'),text.index('unroute -branch'))
        self.assertLess(text.index('save_adif'),text.index('saved-route.adf'))
        for forbidden in ('set_false_path','\npnr -','gen_bitstream','gen_netlist'):
            self.assertNotIn(forbidden,text)

    def test_unknown_branch_occupied_shared_waypoint_and_injection_rejected(self):
        for kind in ('branch','occupied','shared','injection'):
            rows=copy.deepcopy(self.rows);occupied={}
            if kind=='branch':rows[0]['Branch']='A3:CLMA_219_594'
            if kind=='occupied':occupied['ZDNE[0]:SRB_12_180']=['other']
            if kind=='shared':rows[1]['Pins']=rows[0]['Pins']
            if kind=='injection':rows[0]['Pins']+=';exec {bad}'
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                physical.route_helpers.route_commands(rows,self.targets,occupied)

    def request(self):
        fields=('BuildPlan','BuildDiagnosticsReview','HoldAudit','ExactTimingReceipt','DiscoveryReceipt','RouteDump','WaypointEvidence')
        return {'Schema':physical.REQUEST_SCHEMA,'Target':physical.prep.TARGET,
                **{field:{} for field in fields},'SourceADF':{'Path':'fixture.adf','SHA256':physical.ORIGINAL_ADF},
                'Routes':self.rows,'ResetProof':None}

    def test_no_reset_exception_even_if_structure_proof_exists(self):
        value=self.request();physical.validate_request_shape(value)
        value['ResetProof']={'ResetConnectivityVerified':True,'NativeQueriesVerified':True}
        with self.assertRaisesRegex(ValueError,'does not authorize reset'):
            physical.validate_request_shape(value)

    def test_other_candidate_and_old_schema_rejected(self):
        for key,value in (('Schema','raw-camera-delay-route-reset-request-v1'),('Target','camera720_transport_top')):
            request=self.request();request[key]=value
            with self.assertRaises(ValueError):physical.validate_request_shape(request)
        request=self.request();request['SourceADF']['SHA256']='0'*64
        with self.assertRaisesRegex(ValueError,'original reviewed raw'):
            physical.validate_request_shape(request)

    def test_exact_header_cannot_drop_launch_filter(self):
        text='| Tcl Command : report_path_timing -from {t:a/CLK} -through {t:a/L6Q} -to {t:b/I0}\n'
        physical.exact_report_fields(text,'a/CLK','a/L6Q','b/I0')
        for bad in (text.replace(' -through {t:a/L6Q}',''),text.replace('t:a/L6Q','t:a/L5Q'),text.replace('t:b/I0','t:b/I0 t:c/I0')):
            with self.assertRaisesRegex(ValueError,'selector differs'):
                physical.exact_report_fields(bad,'a/CLK','a/L6Q','b/I0')

    def test_external_inputs_only_allowed_when_already_bound(self):
        executable=Path(sys.executable).resolve()
        with self.assertRaisesRegex(ValueError,'already bound exact'):
            physical.add({},executable,physical.sha(executable))
        watched={executable:physical.sha(executable)}
        self.assertEqual(physical.add(watched,executable),executable)
        with self.assertRaisesRegex(ValueError,'SHA differs'):
            physical.add(watched,executable,'0'*64)

    def test_existing_multicycle_requires_exact_original_fdc_line(self):
        case={'TimingExceptions':['MultiCycle Path Setup -end 2'],'ExceptionConstraintLines':[2],
              'LaunchClock':'ddrphy_sysclk','CaptureClock':'phy_dq_sysclk_1'}
        lines=['# original bound FDC','set_multicycle_path 2 -from [get_clocks ddrphy_sysclk] -to [get_clocks phy_dq_sysclk_1]']
        physical.validate_existing_exception(case,lines)
        for changed in (['# missing'],[lines[0],lines[1].replace('path 2','path 3')]):
            with self.assertRaises(ValueError):physical.validate_existing_exception(case,changed)
        case['TimingExceptions']=['False Path']
        with self.assertRaises(ValueError):physical.validate_existing_exception(case,lines)


class ExecutionFlagsTests(unittest.TestCase):
    def clean(self):
        return {'Schema':physical.SCHEMA,'Target':physical.prep.TARGET,'ExitCode':0,'EDAExecuted':True,
            'TimedOut':False,'StoppedForUnexpectedStage':False,'InputDrift':[],'Diagnostics':[],
            'ActualEvents':[],'CompletionMarker':True,'InitializationPreservedADF':True,
            'SavedADFReadbackMatches':True,'ResultADFChanged':True,'Cleanup':{'Complete':True}}

    def test_native_zero_cannot_hide_critical_or_changed_initialization(self):
        self.assertTrue(physical.execution_ok(self.clean()))
        for field,value in (('Diagnostics',['C:STA-3006 invalid endpoint']),('InitializationPreservedADF',False),
                            ('ActualEvents',[['Route','started']]),('InputDrift',['source.adf']),
                            ('SavedADFReadbackMatches',False),('ResultADFChanged',False)):
            record=self.clean();record[field]=value
            with self.subTest(field=field):self.assertFalse(physical.execution_ok(record))

    def test_mock_exit_zero_critical_is_not_clean_save(self):
        with tempfile.TemporaryDirectory(prefix='raw-route-execute-',dir=physical.prep.WORK) as folder:
            work=Path(folder).resolve();stage=work/'stage-plan.json';stage.write_text('{}')
            (work/'input.adf').write_bytes(b'changed')
            value={**self.clean(),'WorkDirectory':str(work),'Command':['fake-only'],'MaximumSeconds':300}
            class Process:
                pid=4242
                def poll(self):return 0
            def popen(*args,**kwargs):
                kwargs['stdout'].write(('C:STA-3006 invalid endpoint\n'+physical.MARKER+'\n').encode());kwargs['stdout'].flush()
                return Process()
            with patch.object(physical,'validate_prepared',return_value=(value,{})),patch.object(physical.subprocess,'Popen',side_effect=popen):
                result=physical.execute(stage)
            self.assertFalse(result['ExecutionPassed'])
            self.assertEqual(len(result['Diagnostics']),1)
            self.assertFalse(result['InitializationPreservedADF'])


class DerivedTests(unittest.TestCase):
    def test_report_mode_uses_one_sta_and_route_export_without_mutation(self):
        text=derived.render('report','',physical.prep.WORK/'base',physical.prep.WORK/'derived')
        self.assertEqual(text.count(physical.INIT),1)
        self.assertIn('.switch_db -route',text)
        for command in ('manual_route','unroute','save_adif','set_false_path','\npnr -'):
            self.assertNotIn(command,text)

    def test_old_physical_receipt_cannot_enter_derived_recipe(self):
        fake=physical.prep.WORK/'not-created/result.json'
        with patch.object(physical,'add',return_value=fake),patch.object(physical,'bind_completed',side_effect=ValueError('wrong current raw identity')) as binder:
            with self.assertRaisesRegex(ValueError,'wrong current raw'):
                derived.recipe(fake,'0'*64,physical.prep.WORK/'not-created-derived','report')
            binder.assert_called_once()

    def test_invalid_derived_mode_and_body_are_rejected(self):
        with self.assertRaises(ValueError):derived.render('route','',physical.prep.WORK,physical.prep.WORK)
        with self.assertRaises(ValueError):derived.render('report','',physical.prep.WORK,physical.prep.WORK,'set_false_path')
        with self.assertRaisesRegex(ValueError,'reserved derived'):
            derived.render('query','',physical.prep.WORK,physical.prep.WORK,'puts {'+derived.MARKER+'}')


if __name__=='__main__':unittest.main()
