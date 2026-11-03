"""Final evidence uses actual launch slots and exact exception inventories."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path('D:\\GravityLRT\\thu\\semester_4.5\\FPGAchina\\fpga-distortion-correction\\distortion')/'tools'))
import hdmi_camera_fisheye_fill8r3s3v2_final as final


def all_sections():
    return {(c,f'{s}({k})'):[] for c in ('slow','fast') for s,kinds in
        (('set_max_delay',('setup','recovery')),('set_min_delay',('hold','removal')),
         ('set_multicycle_path',('setup','hold','recovery','removal')),
         ('set_false_path',('setup','hold','recovery','removal'))) for k in kinds}


def path_block(corner='slow',transition='r',exception='MaxDelay Path 6.666ns -datapath_only',source='source/CLK'):
    return ('Startpoint : '+source+'\nEndpoint : destination/D\nPath Type : max ('+corner+' corner)\n'
        'Timing Exception : '+exception+'\n CLMA_1_2/CLK r '+source+'\n'
        ' CLMA_1_2/Q1 tco 0.100 0.100 '+transition+' source/Q\n Slack (MET) 1.000\n')


def report(path,sections):
    text=''
    for (corner,kind),blocks in sections.items():
        text+='| Exception type : '+kind+'\n| '+corner.capitalize()+' Corner\n'
        text+=''.join(blocks) or 'No such exception path.\n'
    path.write_text(text,encoding='gb18030');return path


@pytest.fixture
def evidence(tmp_path,monkeypatch):
    empty=all_sections();current=all_sections()
    for corner in ('slow','fast'):
        current[corner,'set_max_delay(setup)']=[path_block(corner)]
        current[corner,'set_false_path(hold)']=[path_block(corner,t,'False Path') for t in ('r','f')]
    scope={'ResetScopes':[],'DataScopes':[{'FromCLK':'source/CLK','LaunchQ':'source/Q','Endpoint':'destination/D','MaximumNS':6.6667,
        'NativeObjects':{'SourcePhysicalQ':['CLMA_1_2/Q1'],'SourceCLKNet':['nativeclock']}}]}
    route={'Pins':{('source','CLK'):'nativeclock'}};places={'source':{'Site':'CLMA_1_2'}}
    monkeypatch.setattr(final,'actual_source_bindings',lambda *a:(route,places))
    return {'Before':report(tmp_path/'before.rtr',empty),'After':report(tmp_path/'after.rtr',current),
        'Current':current,'Scope':scope,'Route':route,'Places':places}


def test_parser_requires_all24_sections_and_preserves_strict_codepage(tmp_path):
    sections=all_sections();sections['slow','set_max_delay(setup)']=[path_block()+'# 娉ㄩ噴\n']
    path=report(tmp_path/'exceptions.rtr',sections);value=final.exception_paths(path)
    assert len(value)==24 and value['slow','set_max_delay(setup)'][0]['LaunchOutput']=='source/Q'
    path.write_text(path.read_text(encoding='gb18030').replace(' Slack (MET) 1.000\n',''),encoding='gb18030')
    with pytest.raises(ValueError):final.exception_paths(path)


def test_complete_two_corner_actual_launch_scope_is_accepted_without_old_counts(evidence):
    e=evidence;value=final.validate_exceptions(e['Scope'],e['Before'],e['After'])
    assert value['Complete'] and value['AllVendorExceptionsPreserved'] and not value['CompanionQLeakage']
    assert value['PerSection']['slow_set_false_path(hold)']['ActualLaunchPairs']==1


def matrix_evidence(e):
    from test_hdmi_camera_fisheye_physical import group_scope
    s=e['Scope'];s.update(Schema=final.application.AUDIT_SCHEMA,Target=final.build.TARGET,
        ProposalReady=True,Blockers=[],ConstraintsApplied=False,TimingAccepted=False,HardwareReleaseAllowed=False)
    s['ForeignRelationships']=[]
    original=copy.deepcopy(s['DataScopes'][0]);s['DataScopes']=[]
    for i in range(3):
        row=copy.deepcopy(original);row.update(Endpoint='destination'+(str(i)if i else'')+'/D',Role='held_bundle',
            BoundBasis='one destination period',RelationshipIndexes=[i])
        row['NativeObjects'].update(SourceFFs=['source/FF'],DestinationFFs=['dest'+str(i)+'/FF'])
        s['DataScopes'].append(row)
        s['ForeignRelationships'].append({'SourceFF':'source/FF','DestinationFF':'dest'+str(i)+'/FF',
            'SourceNativeClockPin':row['FromCLK'],'SourceNativeOutputPin':row['LaunchQ'],
            'SourcePhysicalQ':row['NativeObjects']['SourcePhysicalQ'][0],'SourceNativeCLKNet':'nativeclock',
            'NativeBoundaries':[{'Endpoint':row['Endpoint']}]})
    group_scope(s)
    return {'ConstraintsApplied':True,'NativeQueriesVerified':True,'RoutesAndPlacementUnchanged':True,
        'ConstraintGroups':copy.deepcopy(s['ConstraintGroups']),
        'DataExecutionChunks':final.application.data_execution_chunks(s),
        'ExactCommands':final.application.application_commands(s)[0]}


def test_truncated_reports_use_verified_executed_complete_matrix_and_admit_no_unlisted_pairs(evidence):
    e=evidence;applied=matrix_evidence(e)
    value=final.validate_exceptions(e['Scope'],e['Before'],e['After'],applied)
    assert value['Complete']and value['MatrixConstraintCoverageComplete']and value['MatrixNativePairs']==3
    assert value['ReportedEnumerationComplete']is False and value['AllActualLaunchPairsCovered']is False
    assert value['PerSection']['fast_set_max_delay(setup)']['ObservedConstraintGroups']==[0]
    e['Current']['slow','set_max_delay(setup)'][0]=path_block().replace('destination/D','unlisted/D')
    report(e['After'],e['Current'])
    with pytest.raises(ValueError,match='unrequested'):final.validate_exceptions(e['Scope'],e['Before'],e['After'],applied)


@pytest.mark.parametrize('change',['no_executed_authority','missing_native_names','changed_command',
    'dropped_chunk','no_fast_group_evidence'])
def test_matrix_proposal_alone_cannot_claim_executed_coverage_or_missing_corner_effect(evidence,change):
    e=evidence;applied=matrix_evidence(e)
    if change=='no_executed_authority':applied=None
    elif change=='missing_native_names':applied['NativeQueriesVerified']=False
    elif change=='changed_command':applied['ExactCommands'][0]+=' 100'
    elif change=='dropped_chunk':applied['DataExecutionChunks']=[]
    else:e['Current']['fast','set_max_delay(setup)']=[];report(e['After'],e['Current'])
    with pytest.raises(ValueError):final.validate_exceptions(e['Scope'],e['Before'],e['After'],applied)


def test_synchronous_D_reset_has_both_corner_setup_hold_effect_and_no_fictitious_recovery_removal(evidence):
    from test_hdmi_camera_fisheye_physical import add_synchronous_reset
    e=evidence;s=e['Scope'];row=s['DataScopes'][0]
    row['NativeObjects'].update(SourceFFs=['source/FF'],DestinationFFs=['target/FF'])
    s['ForeignRelationships']=[{'SourceFF':'source/FF','DestinationFF':'target/FF','SourceNativeClockPin':row['FromCLK'],
        'SourceNativeOutputPin':row['LaunchQ'],'SourcePhysicalQ':'CLMA_1_2/Q1','SourceNativeCLKNet':'nativeclock',
        'NativeBoundaries':[{'Endpoint':row['Endpoint']}]}]
    sync=add_synchronous_reset(s)
    for corner in('slow','fast'):
        block=path_block(corner,exception='False Path').replace('destination/D',sync['Endpoint'])
        e['Current'][corner,'set_false_path(setup)']=[block]
        e['Current'][corner,'set_false_path(hold)'].append(block)
    report(e['After'],e['Current']);value=final.validate_exceptions(s,e['Before'],e['After'])
    assert value['SynchronousResetFunctions']==1 and value['SynchronousResetSetupHoldCoverageComplete']
    assert value['PerSection']['slow_set_false_path(recovery)']['AddedPaths']==0
    e['Current']['fast','set_false_path(setup)']=[];report(e['After'],e['Current'])
    with pytest.raises(ValueError,match='coverage'):final.validate_exceptions(s,e['Before'],e['After'])


@pytest.mark.parametrize('change',['missing_hold','wrong_q','wrong_slot','wrong_clk_site','new_reset_cut',
    'budget_too_loose','violating_max','duplicate_path'])
def test_missing_paths_companion_q_reset_waivers_and_budget_or_physical_drift_are_rejected(evidence,change):
    e=evidence;current=e['Current']
    if change=='missing_hold':current['fast','set_false_path(hold)'].clear()
    elif change=='new_reset_cut':current['slow','set_false_path(recovery)']=[path_block(exception='False Path')]
    elif change=='duplicate_path':current['slow','set_max_delay(setup)']*=2
    else:
        old=current['slow','set_max_delay(setup)'][0]
        replacements={'wrong_q':('source/Q','companion/Q'),'wrong_slot':('CLMA_1_2/Q1','CLMA_1_2/Q2'),
            'wrong_clk_site':('CLMA_1_2/CLK','CLMA_1_3/CLK'),
            'budget_too_loose':('6.666ns','6.667ns'),'violating_max':('Slack (MET)','Slack (VIOLATED)')}
        current['slow','set_max_delay(setup)'][0]=old.replace(*replacements[change])
    report(e['After'],current)
    with pytest.raises(ValueError):final.validate_exceptions(e['Scope'],e['Before'],e['After'])


def test_printed_packed_clock_alias_needs_both_native_same_site_and_exact_clock_net(evidence):
    e=evidence
    for key,rows in e['Current'].items():e['Current'][key]=[text.replace('source/CLK','companion/CLK') for text in rows]
    report(e['After'],e['Current'])
    e['Places']['companion']={'Site':'CLMA_1_2'};e['Route']['Pins']['companion','CLK']='nativeclock'
    assert final.validate_exceptions(e['Scope'],e['Before'],e['After'])['ClockAliasesVerified']==1
    e['Route']['Pins']['companion','CLK']='otherclock'
    with pytest.raises(ValueError,match='same native CLK net'):final.validate_exceptions(e['Scope'],e['Before'],e['After'])
    e['Route']['Pins']['companion','CLK']='nativeclock';e['Places']['companion']['Site']='CLMA_1_3'
    with pytest.raises(ValueError,match='same-site'):final.validate_exceptions(e['Scope'],e['Before'],e['After'])


def test_baseline_vendor_exceptions_cannot_disappear_or_change(evidence):
    e=evidence;before=all_sections();before['slow','set_multicycle_path(setup)']=[path_block(exception='MultiCycle Path Setup -end 2')]
    report(e['Before'],before)
    with pytest.raises(ValueError,match='vendor exception'):final.validate_exceptions(e['Scope'],e['Before'],e['After'])
    e['Current']['slow','set_multicycle_path(setup)']=copy.deepcopy(before['slow','set_multicycle_path(setup)'])
    report(e['After'],e['Current'])
    assert final.validate_exceptions(e['Scope'],e['Before'],e['After'])['AllVendorExceptionsPreserved']


def test_distinct_native_variants_may_share_the_same_launch_transition(evidence):
    e=evidence
    for corner in ('slow','fast'):
        blocks=e['Current'][corner,'set_false_path(hold)']
        blocks[1]=blocks[1].replace('0.100 f source/Q','0.100 r source/Q').replace('0.100 0.100','0.101 0.101')
    report(e['After'],e['Current'])
    value=final.validate_exceptions(e['Scope'],e['Before'],e['After'])
    assert value['PerSection']['slow_set_false_path(hold)']['ReportedLaunchTransitions']=={'["source/Q", "destination/D"]':['r']}


def test_proposal_ready_cannot_stand_in_for_reset_protocol_io_acceptance():
    with pytest.raises(ValueError,match='explicit'):final.native_acceptance({'ProposalReady':True,'Blockers':[]})


def test_fresh_report_requires_same_complete_paths_not_just_passing_summaries(evidence,monkeypatch):
    e=evidence;monkeypatch.setattr(final.application,'compare_final_summaries',lambda *a:{'STAAllTenPassed':True,'ClockAndSummaryIdentityPreserved':True})
    proof={'FreshSTAReport':{'Path':'unused'},'FreshSTAExceptions':{'Path':str(e['After'])}}
    assert final.compare_fresh_sta(proof,'unused',e['After'])['AllExceptionPathsPreserved']
    report(e['Before'],e['Current']);e['Current']['fast','set_max_delay(setup)'][0]=path_block('fast',exception='MaxDelay Path 9.000ns -datapath_only')
    report(e['Before'],e['Current'])
    with pytest.raises(ValueError,match='paths changed'):final.compare_fresh_sta(proof,'unused',e['Before'])


def test_fresh_compare_does_not_inherit_summary_only_false_coverage_flag(evidence,monkeypatch):
    e=evidence
    monkeypatch.setattr(final.application,'compare_final_summaries',lambda *a:{'STAAllTenPassed':True,
        'ClockAndSummaryIdentityPreserved':True,'ExceptionPathCoverageAccepted':False})
    result=final.compare_fresh_sta({'FreshSTAReport':{'Path':'unused'},'FreshSTAExceptions':{'Path':str(e['After'])}},'unused',e['After'])
    assert result=={'STAAllTenPassed':True,'ClockAndSummaryIdentityPreserved':True,'AllExceptionPathsPreserved':True}



def test_fresh_printed_clock_must_be_in_verified_native_alias_union_with_each_parent_rebound(evidence):
    e=evidence;row=e['Scope']['DataScopes'][0]
    row['FromCLKVariants']=['companion/CLK','source/CLK']
    row['FromCLKVariantProof']={'Verified':True,'PhysicalCLK':'CLMA_1_2/CLK','CLKNet':'nativeclock',
        'Parents':[{'Instance':name,'CLKPin':name+'/CLK','Site':'CLMA_1_2','CLKNet':'nativeclock'}for name in ('companion','source')]}
    e['Places']['companion']={'Site':'CLMA_1_2'};e['Route']['Pins']['companion','CLK']='nativeclock'
    for key,rows in e['Current'].items():e['Current'][key]=[text.replace('source/CLK','companion/CLK')for text in rows]
    report(e['After'],e['Current'])
    assert final.validate_exceptions(e['Scope'],e['Before'],e['After'])['Complete']
    # A physically nearby clock is still forbidden unless it belongs to the exact proven union.
    e['Places']['unlisted']={'Site':'CLMA_1_2'};e['Route']['Pins']['unlisted','CLK']='nativeclock'
    for key,rows in e['Current'].items():e['Current'][key]=[text.replace('companion/CLK','unlisted/CLK')for text in rows]
    report(e['After'],e['Current'])
    with pytest.raises(ValueError,match='outside exact'):final.validate_exceptions(e['Scope'],e['Before'],e['After'])


@pytest.fixture
def pipeline_scope(tmp_path,monkeypatch):
    profile={'Calibration':{'Path':'current C','SHA256':'bound'},'FullGridError':{'NativeCoordinatesChecked':2073600}}
    scope={'BuildPlan':{'Path':str(tmp_path/'plan.json')},'NativeAcceptance':{k:True for k in
        ('VendorDDRClockResetAccepted','FrameBoundaryViewSelectionAccepted','FisheyeProfileAccepted','UserCDCAccepted')},
        'NativeClockReview':{'CoreClock':{'Domain':'ddrphy_sysclk','FrequencyHz':125000000,'PeriodNS':8.0,
            'CurrentGeneratedClockVerified':True,'PLLParametersVerified':True,
            'ConstrainedCoreMHz':125,'InputParameterMetadataMHz':50,'PhysicalFrequencyMeasured':False,
            'FrequencyBasis':'current_constraint_and_native_1_to_1_clock_trace','NativeRatioNumerator':16,
            'NativeRatioDenominator':16,'NativeRoot':'current/GPLL/CLKOUT0',
            'Trace':[{'Cell':'current/GPLL','ParametersVerified':True}]}},
        'SourcePartitions':{'NativeEvidenceComplete':True,'SourceBytesAloneClaimNativeSafety':False,'Missing':[],
            'Violations':[],'VendorDDR':{'ActualInstances':123,'CurrentNativeClockModesVerified':True}}}
    scope.update(PrimitiveBoundaries=[],NonFFSequentialSupport={'AllNonFFSourceTokensRetained':True,
        'UnknownsNotConvertedToPrimaryInputs':True,'SourceSets':{},'Consumers':[]})
    monkeypatch.setattr(final.build,'validate',lambda *a:{'FisheyeProfile':copy.deepcopy(profile)})
    monkeypatch.setattr(final.build,'fisheye_profile_binding',lambda *a:(copy.deepcopy(profile),{}))
    return scope


def test_current_native_core_clock_is_the_fps_tick_basis_and_profile_is_same_compiled_C(pipeline_scope):
    value,watched=final.pipeline_evidence(pipeline_scope)
    assert value['FPSClockBasis']['FrequencyHz']==125000000 and value['FisheyeProfile']['Calibration']['Path']=='current C'
    assert all(value[k]for k in('VendorDDRClockResetAccepted','FrameBoundaryViewSelectionAccepted',
        'FisheyeProfileAccepted','UserCDCAccepted'))


@pytest.mark.parametrize('change',['125_name_without_trace','wrong_pll','wrong_frequency','bool_frequency',
    'wrong_period','old_ddr_proof','unknown_user_cdc','wrong_C','no_partitions','source_only_partition','missing_native_partition'])
def test_source_clock_name_or_old_acceptance_cannot_replace_actual_fresh_partition_evidence(pipeline_scope,change,monkeypatch):
    s=pipeline_scope;c=s['NativeClockReview']['CoreClock']
    if change=='125_name_without_trace':c['Trace']=[]
    elif change=='wrong_pll':c['PLLParametersVerified']=False
    elif change=='wrong_frequency':c['FrequencyHz']=74250000
    elif change=='bool_frequency':c['FrequencyHz']=True
    elif change=='wrong_period':c['PeriodNS']=6.6667
    elif change=='old_ddr_proof':s['NativeAcceptance']['VendorDDRClockResetAccepted']=False
    elif change=='unknown_user_cdc':s['NativeAcceptance']['UserCDCAccepted']=False
    elif change=='wrong_C':monkeypatch.setattr(final.build,'validate',lambda *a:{'FisheyeProfile':{'Calibration':'old lens'}})
    elif change=='no_partitions':s['SourcePartitions']={}
    elif change=='source_only_partition':s['SourcePartitions']['SourceBytesAloneClaimNativeSafety']=True
    elif change=='missing_native_partition':s['SourcePartitions']['NativeEvidenceComplete']=False
    with pytest.raises(ValueError):final.pipeline_evidence(s)
