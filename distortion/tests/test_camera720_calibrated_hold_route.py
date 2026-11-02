"""Focused CPU checks for exact single-branch routing and fresh inspection."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_calibrated_hold_route as physical
import camera720_calibrated_derived_inspect as derived


class ExactHoldTests(unittest.TestCase):
    def setUp(self):
        self.scratch=tempfile.TemporaryDirectory(prefix='calibrated-hold-unit-')
        self.addCleanup(self.scratch.cleanup)
        self.query=Path(self.scratch.name)/'target.rtr'
        source,launch,endpoint='source/opit/ICLKDIV','source/opit/RX_DATA[6]','sink/opit/D'
        self.query.write_text('| Design : '+physical.prep.TARGET+'\n| Tcl Command : report_path_timing '
                             '-from {t:'+source+'} -through {t:'+launch+'} -to {t:'+endpoint+'}\n',encoding='utf-8')
        row={'Source':source,'Endpoint':endpoint,'LaunchClock':'phy_dq_sysclk_1','CaptureClock':'ddrphy_sysclk',
             'LaunchEdge':'rising','CaptureEdge':'rising',
             'Cases':[],'Margins':{},'PhysicalRepairCandidate':{
                 'Net':'_N177','FromRoutePin':'CR0:CLMA_1_1','ToRoutePin':'M2:CLMA_7_7',
                 'Fanout':1,'TimingWaiverAllowed':False}}
        for corner,setup,hold in (('slow',5.132,-.096),('fast',5.983,-.308)):
            row['Margins'][corner]={'HoldSlackNS':hold,'ExactSetupSlackNS':setup,'ExactSetupFound':True}
            for kind,slack in (('setup',setup),('hold',hold)):
                row['Cases'].append({k:v for k,v in row.items() if k in ('Source','Endpoint','LaunchClock','CaptureClock','LaunchEdge','CaptureEdge')}|
                    {'Corner':corner,'Kind':kind,'SlackNS':slack,'TimingExceptions':[],'ExceptionConstraintLines':[],
                     'DataTrace':[{'DelayType':'tco','LogicalResource':launch},
                         {'Name':'_N177','FromRoutePin':'CR0:CLMA_1_1','ToRoutePin':'M2:CLMA_7_7','Fanout':1},
                         {'LogicalResource':endpoint}],'Excerpt':'synthetic-unit-only'})
        self.hold={'Schema':'camera720-calibrated-exact-hold-analysis-v1','Target':physical.prep.TARGET,
                   'ExtractionComplete':True,'HoldFailingPathCount':1,'MissingExactSetup':[],
                   'TimingClosed':False,'HardwareAccessed':False,'Paths':[row]}

    def run_target(self,record=None,negative_extra=False):
        record=self.hold if record is None else record
        row=self.hold['Paths'][0]
        cases=[{k:v for k,v in c.items() if k!='Excerpt'} for c in row['Cases']]
        negative=[c for c in cases if c['Kind']=='hold']
        if negative_extra:
            second=copy.deepcopy(negative[0]);second['Endpoint']+='other';negative.append(second)
        def reader(path,identities=None):
            if identities is None:return negative,[],{}
            return cases,[],{}
        with mock.patch.object(physical.hold.common,'read_report',side_effect=reader), \
             mock.patch.object(physical.hold,'detailed',side_effect=lambda p:{**p,'_Text':'native evidence'}):
            return physical.measured_target(record,self.query,[self.query])

    def test_actual_targeted_dual_corner_slacks_and_launch(self):
        targets=self.run_target()
        self.assertEqual(len(targets),1)
        self.assertEqual(targets[0]['Net'],'_N177')
        self.assertEqual(targets[0]['Fanout'],1)
        self.assertFalse(targets[0]['TimingWaiverAllowed'])
        self.assertEqual(self.hold['Paths'][0]['Margins']['slow']['ExactSetupSlackNS'],5.132)

    def test_more_than_measured_relationship_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'only one measured'):
            self.run_target(negative_extra=True)

    def test_forged_path_slack_terminal_or_metadata_rejected(self):
        for field,value in (('SlackNS',.5),('Endpoint','other/D'),('TimingExceptions',['False Path'])):
            bad=copy.deepcopy(self.hold);bad['Paths'][0]['Cases'][0][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'native report bytes|current native failure'):
                self.run_target(bad)
        bad=copy.deepcopy(self.hold);bad['Paths'][0]['PhysicalRepairCandidate']['Net']='_N999'
        with self.assertRaisesRegex(ValueError,'single-load terminal'):
            self.run_target(bad)

    def test_margin_or_identity_change_rejected(self):
        bad=copy.deepcopy(self.hold);bad['Paths'][0]['Margins']['fast']['ExactSetupSlackNS']=100
        with self.assertRaisesRegex(ValueError,'margin differs'):self.run_target(bad)
        bad=copy.deepcopy(self.hold);bad['Target']='old_raw_top'
        with self.assertRaises(ValueError):self.run_target(bad)

    def test_request_cannot_add_reset_or_unmeasured_command(self):
        r={'Schema':physical.REQUEST_SCHEMA,'Target':physical.prep.TARGET,
           'DiscoveryReceipt':{},'ExportReceipt':{},'HoldAudit':{},'WaypointEvidence':{},'Routes':[]}
        physical.validate_request_shape(r)
        for name in ('ResetProof','Commands','SourceADF'):
            bad={**r,name:[]}
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,'hold-only request'):
                physical.validate_request_shape(bad)


class RoutePreservationTests(unittest.TestCase):
    def setUp(self):
        self.target={'Net':'_N1','FromRoutePin':'CR0:CLMA_1_1','ToRoutePin':'M2:CLMA_7_7'}
        self.row={'Net':'_N1','Branch':'M2:CLMA_7_7','Pins':'ZDNE[0]:SRB_2_2>IDNE[0]:SRB_8_8;'}
        self.old={'NetAnnotations':{'_N1':'old','_N2':'same'},
            'BranchInventory':{'_N1':{'LogicalConnections':[{'Instance':'x','Pin':'D'}],
                'Leaves':{'M2:CLMA_7_7':['CR0:CLMA_1_1','M2:CLMA_7_7'],
                          'M1:CLMA_9_9':['CR0:CLMA_1_1','M1:CLMA_9_9']}}},
            'NonRouteSemanticSHA256':'old','SourceLocationMetadata':{}}
        self.new=copy.deepcopy(self.old)
        self.new['NetAnnotations']['_N1']='new'
        self.new['NonRouteSemanticSHA256']='reordered'
        self.new['BranchInventory']['_N1']['Leaves']['M2:CLMA_7_7']=[
            'CR0:CLMA_1_1','ZDNE[0]:SRB_2_2','IDNE[0]:SRB_8_8','M2:CLMA_7_7']
        self.refs={k:True for k in ('DefinitionsEqual','ParentObjectsEqual',
            'AllFullEntriesEqualWithinParent','AllResolvedEntriesEqualWithinParent','OtherNonRouteTokensEqual')}
        self.refs.update(DefinitionCountBefore=3,EntryCountBefore=4,ParentChecks=[{}])
        self.extracted={'ExcludedBlocks':{'CDB':{'TokenSHA256':'c'},'FILETABLE':{'TokenSHA256':'f'}},
                        'SourceAnnotationsOutsideCDBEntries':[]}

    def compare(self):
        parser=mock.Mock()
        parser.extract.return_value=self.extracted
        parser.reference_comparison.return_value=self.refs
        with mock.patch.object(physical.routes,'inspect',side_effect=[self.old,self.new]), \
             mock.patch.object(physical,'serialization_module',return_value=parser):
            return physical.compare_route_dumps('old','new',[self.target],[self.row])

    def test_only_exact_parent_bound_cdb_reordering_is_permitted(self):
        value=self.compare()
        self.assertTrue(value['Passed'])
        self.assertFalse(value['StrictNonRouteTokensIdentical'])
        self.assertEqual(value['DefinitionsCompared'],3)
        self.assertEqual(value['OtherBranchChecks'][0]['UnrequestedSiblingsPreserved'],1)
        self.assertFalse(value['TimingAcceptanceImplied'])

    def test_any_changed_definition_parent_or_residual_is_rejected(self):
        for key in list(self.refs):
            if type(self.refs[key]) is not bool:continue
            saved=self.refs[key];self.refs[key]=False
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'semantics changed'):self.compare()
            self.refs[key]=saved

    def test_unrequested_route_sibling_or_noncontiguous_waypoint_rejected(self):
        self.new['NetAnnotations']['_N2']='changed'
        with self.assertRaisesRegex(ValueError,'unrequested route'):self.compare()
        self.new['NetAnnotations']['_N2']='same'
        self.new['BranchInventory']['_N1']['Leaves']['M1:CLMA_9_9'].insert(1,'other')
        with self.assertRaisesRegex(ValueError,'sibling'):self.compare()
        self.new['BranchInventory']['_N1']['Leaves']['M1:CLMA_9_9']=self.old['BranchInventory']['_N1']['Leaves']['M1:CLMA_9_9']
        self.new['BranchInventory']['_N1']['Leaves']['M2:CLMA_7_7'].insert(2,'other')
        with self.assertRaisesRegex(ValueError,'contiguous detour'):self.compare()


class LifecycleTests(unittest.TestCase):
    def test_route_script_initializes_once_before_edit_and_saves_only_copy(self):
        text=physical.render(['show -design_net {_N1}'],Path('D:/scratch/current'))
        self.assertEqual(text.count(physical.INIT),1)
        self.assertLess(text.index(physical.INIT),text.index('post-init.adf'))
        self.assertLess(text.index('post-init.adf'),text.index('show -design_net'))
        self.assertIn('save_adif',text)
        self.assertIn('saved-route.adf',text)
        self.assertNotIn('set_false_path',text)
        self.assertNotIn('gen_bit_stream',text)
        self.assertTrue(physical.DUMMY.endswith('\n'))
        self.assertNotIn('\\n',physical.DUMMY)

    def test_partial_native_save_cannot_claim_success(self):
        value={'Schema':physical.SCHEMA,'Target':physical.prep.TARGET,'ExitCode':0,
          'EDAExecuted':True,'TimedOut':False,'StoppedForUnexpectedStage':False,'InputDrift':[],
          'Diagnostics':[],'ActualEvents':[],'CompletionMarker':True,'InitializationPreservedADF':True,
          'SavedADFReadbackMatches':True,'ResultADFChanged':True,'Cleanup':{'Complete':True},
          'RouteComparison':{'Passed':True}}
        self.assertTrue(physical.execution_ok(value))
        for key,changed in (('InitializationPreservedADF',False),('RouteComparison',{}),
                ('Diagnostics',['C: failure']),('InputDrift',['changed']),('ResultADFChanged',False)):
            bad={**value,key:changed}
            with self.subTest(key=key):self.assertFalse(physical.execution_ok(bad))

    def test_derived_report_requires_initializer_and_own_marker(self):
        text=derived.render('report','',Path('D:/build'),Path('D:/next'))
        self.assertEqual(text.count(physical.INIT),1)
        self.assertIn(derived.MARKER,text)
        self.assertNotIn('save_adif',text)
        with self.assertRaises(ValueError):
            derived.render('query','',Path('D:/build'),Path('D:/next'),'puts {'+derived.MARKER+'}')

    def test_unknown_source_schema_cannot_lazy_dispatch(self):
        with mock.patch.object(physical,'read',return_value={'Schema':'old-raw-or-forged'}):
            with self.assertRaisesRegex(ValueError,'only exact calibrated'):
                derived.bind_source('fake',{})


if __name__=='__main__':unittest.main()
