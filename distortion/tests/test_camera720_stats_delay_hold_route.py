"""Current DDR dual-output path coverage and exact metadata boundaries."""
import copy
from pathlib import Path
import sys
import unittest
from unittest import mock
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_delay_hold_route as physical


@pytest.fixture
def fixture(tmp_path):
    full=tmp_path/'full.rtr'
    full.write_text('| Design : '+physical.prep.TARGET+chr(10))
    source,endpoint='source/opit/CLK','sink/opit/TX_DATA[1]'
    row={'Source':source,'Endpoint':endpoint,'LaunchClock':'ddrphy_sysclk','CaptureClock':'phy_dq_sysclk_1',
        'Cases':[],'Margins':{'slow':{'HoldSlackNS':.261,'ExactSetupSlackNS':3.755,'ExactSetupFound':True},
        'fast':{'HoldSlackNS':-.022,'ExactSetupSlackNS':5.158,'ExactSetupFound':True}},
        'PhysicalRepairCandidate':{'Net':'_N112','FromRoutePin':'CR2:CLMA_357_756',
        'ToRoutePin':'TX_DATA[1]:IOLHR_364_750','Fanout':1,'TimingWaiverAllowed':False}}
    reports=[];by_report={}
    for q,slacks in [('L5Q',[3.755,.391,5.158,.069]),('L6Q',[4.038,.261,5.273,-.022])]:
        launch='source/opit/'+q
        p=tmp_path/(q+'.rtr');reports.append(p)
        p.write_text('| Design : '+physical.prep.TARGET+chr(10)+'| Tcl Command : report_path_timing '
            '-from {t:'+source+'} -through {t:'+launch+'} -to {t:'+endpoint+'}'+chr(10))
        cases=[]
        for (corner,kind),slack in zip([('slow','setup'),('slow','hold'),('fast','setup'),('fast','hold')],slacks):
            c={k:row[k] for k in ('Source','Endpoint','LaunchClock','CaptureClock')}
            c.update(LaunchEdge='rising',CaptureEdge='rising',Corner=corner,Kind=kind,SlackNS=slack,
                TimingExceptions=['MultiCycle Path Setup -end 2'],ExceptionConstraintLines=[700],
                PathSHA256=q+corner+kind,DataTrace=[{'DelayType':'tco','LogicalResource':launch},
                {'Name':'_N112','FromRoutePin':'CR2:CLMA_357_756','ToRoutePin':'TX_DATA[1]:IOLHR_364_750','Fanout':1},
                {'LogicalResource':endpoint}])
            cases.append(c);row['Cases'].append({**c,'Excerpt':'synthetic-unit-only'})
        by_report[p]=cases
    all_cases=[c for p in reports for c in by_report[p]]
    record={'Schema':'camera720-calibrated-stats-delay-exact-hold-analysis-v1','Target':physical.prep.TARGET,
        'ExtractionComplete':True,'HoldFailingPathCount':1,'MissingExactSetup':[],
        'TimingClosed':False,'HardwareAccessed':False,'Paths':[row]}
    return full,reports,by_report,all_cases,record


def run_target(f,record=None,reports=None):
    full,default_reports,by_report,cases,saved=f
    def reader(path,identities=None):
        if identities is None:return [cases[-1]],[],{}
        return cases if path==full else by_report[path],[],{}
    with mock.patch.object(physical.hold.common,'read_report',side_effect=reader), mock.patch.object(
            physical.hold,'detailed',side_effect=lambda p:{**p,'_Text':'fixture'}):
        return physical.measured_target(saved if record is None else record,full,default_reports if reports is None else reports)


def test_both_launch_outputs_have_all_four_cases(fixture):
    assert run_target(fixture)[0]['Net']=='_N112'
    assert len(fixture[3])==8


def test_missing_positive_companion_rejected(fixture):
    with pytest.raises(ValueError,match='one exact targeted report'):
        run_target(fixture,reports=fixture[1][1:])


@pytest.mark.parametrize('exception,line',[
    (['False Path'],[700]),(['MultiCycle Path Setup -end 3'],[700]),(['MultiCycle Path Setup -end 2'],[701])])
def test_changed_original_exception_rejected(fixture,exception,line):
    fixture[3][0]['TimingExceptions']=exception;fixture[3][0]['ExceptionConstraintLines']=line
    with pytest.raises(ValueError,match='original path exception'):run_target(fixture)


def test_forged_case_and_wrong_worst_margin_rejected(fixture):
    bad=copy.deepcopy(fixture[4]);bad['Paths'][0]['Cases'][0]['SlackNS']=999
    with pytest.raises(ValueError,match='native report bytes'):run_target(fixture,bad)
    bad=copy.deepcopy(fixture[4]);bad['Paths'][0]['Margins']['slow']['ExactSetupSlackNS']=4.038
    with pytest.raises(ValueError,match='margin differs'):run_target(fixture,bad)


def test_through_selector_matches_actual_trace(fixture):
    p=fixture[1][0];p.write_text(p.read_text().replace('/L5Q}','/L6Q}'))
    with pytest.raises(ValueError,match='exact selected launch'):run_target(fixture)


def test_cannot_add_reset_command_to_request():
    value={'Schema':physical.REQUEST_SCHEMA,'Target':physical.prep.TARGET,
        'DiscoveryReceipt':{},'ExportReceipt':{},'HoldAudit':{},'WaypointEvidence':{},'Routes':[]}
    physical.validate_request_shape(value)
    for name in ('ResetProof','Commands','SourceADF'):
        with pytest.raises(ValueError):physical.validate_request_shape({**value,name:[]})


def metadata(tokens,rows):
    return {'ExcludedBlocks':{'FILETABLE':{'Tokens':tokens}},'SourceAnnotationsOutsideCDBEntries':[{'Tokens':r} for r in rows]}


def test_unchanged_source_tokens_ignore_only_line_offsets():
    a=metadata(['(','FILETABLE',')'],[['(','FILEID','2',')']])
    b=copy.deepcopy(a);a['SourceAnnotationsOutsideCDBEntries'][0]['Line']=1;b['SourceAnnotationsOutsideCDBEntries'][0]['Line']=2
    assert physical.metadata_change(a,b)['FileTableUnchanged']
    b['SourceAnnotationsOutsideCDBEntries'][0]['Tokens'][2]='3'
    with pytest.raises(ValueError,match='annotation content'):physical.metadata_change(a,b)


def test_only_complete_empty_filemap_removal_allowed():
    a=metadata(['(','FILETABLE','(','FILEMAP','2','""',')',')'],[['(','FILEID','2',')'],['(','LINENUM','10',')']])
    b=metadata(['(','FILETABLE',')'],[])
    assert physical.metadata_change(a,b)['ExactEmptyFileMapRemoval']
    for change in ('named_file','unpaired','retained'):
        aa=copy.deepcopy(a);bb=copy.deepcopy(b)
        if change=='named_file':aa['ExcludedBlocks']['FILETABLE']['Tokens'][6]='"file.v"'
        if change=='unpaired':aa['SourceAnnotationsOutsideCDBEntries'].pop()
        if change=='retained':bb['SourceAnnotationsOutsideCDBEntries']=copy.deepcopy(aa['SourceAnnotationsOutsideCDBEntries'])
        with pytest.raises(ValueError):physical.metadata_change(aa,bb)


def test_render_changes_only_copy_and_no_constraints():
    text=physical.render(['show -design_net {_N112}'],Path('D:/scratch/stage'))
    assert text.count(physical.INIT)==1
    assert text.index(physical.INIT)<text.index('post-init.adf')<text.index('show -design_net')
    assert 'save_adif' in text and 'saved-route.adf' in text
    assert 'set_false_path' not in text and 'gen_bit_stream' not in text


def test_partial_native_save_rejected():
    value={'Schema':physical.SCHEMA,'Target':physical.prep.TARGET,'ExitCode':0,
        'EDAExecuted':True,'TimedOut':False,'StoppedForUnexpectedStage':False,'InputDrift':[],
        'Diagnostics':[],'ActualEvents':[],'CompletionMarker':True,'InitializationPreservedADF':True,
        'SavedADFReadbackMatches':True,'ResultADFChanged':True,'Cleanup':{'Complete':True},'RouteComparison':{'Passed':True}}
    assert physical.execution_ok(value)
    for key,changed in [('InitializationPreservedADF',False),('RouteComparison',{}),('Diagnostics',['E:']),('InputDrift',['x']),('ResultADFChanged',False)]:
        assert not physical.execution_ok({**value,key:changed})

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
        self.extracted={'ExcludedBlocks':{'CDB':{'TokenSHA256':'c'},'FILETABLE':{'TokenSHA256':'f','Tokens':['(','FILETABLE',')']}},
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


