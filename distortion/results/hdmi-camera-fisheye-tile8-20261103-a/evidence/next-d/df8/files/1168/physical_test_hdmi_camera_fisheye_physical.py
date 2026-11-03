"""Pixel-only planning stays fail-closed without native command/reset proof."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0,str(Path('D:\\GravityLRT\\thu\\semester_4.5\\FPGAchina\\fpga-distortion-correction\\distortion')/'tools'))
import hdmi_camera_fisheye_tile8df8v3_physical as physical


@pytest.fixture
def scope():
    relationship={'SourceFF':'opaque/source/FF','DestinationFF':'opaque/target/FF',
        'SourceNativeClockPin':'opaque/source/CLK','SourceNativeOutputPin':'opaque/source/Q',
        'SourcePhysicalQ':'CLMA_1_2/Q1','SourceNativeCLKNet':'native_clk1',
        'NativeBoundaries':[{'Endpoint':'opaque/target/D'}]}
    row={'FromCLK':'opaque/source/CLK','LaunchQ':'opaque/source/Q','Endpoint':'opaque/target/D',
        'Role':'held_bundle','MaximumNS':6.6667,'BoundBasis':'independently reviewed destination period',
        'RelationshipIndexes':[0],'NativeObjects':{'SourceFFs':['opaque/source/FF'],
            'DestinationFFs':['opaque/target/FF'],'SourcePhysicalQ':['CLMA_1_2/Q1'],'SourceCLKNet':['native_clk1']}}
    return {'Schema':physical.AUDIT_SCHEMA,'Target':physical.build.TARGET,'ProposalReady':True,'Blockers':[],
        'ConstraintsApplied':False,'TimingAccepted':False,'HardwareReleaseAllowed':False,
        'ForeignRelationships':[relationship],'DataScopes':[row],'ResetScopes':[]}


def test_actual_launch_triples_generate_only_readonly_queries_never_executable_constraints(scope):
    value=physical.scope_plan(scope)
    assert value['ActualDataScopeCount']==1 and len(value['NativeSelectors'])==3
    assert value['ExactLaunchTriples'][0]['LaunchQ']=='opaque/source/Q'
    assert value['ConstraintsApplicable'] is False and value['ExecutableFDCCommands']==[]
    assert value['TimingAccepted'] is False and value['BitstreamAllowed'] is False
    assert 'set_max_delay' not in value['PreflightQueryBody']
    assert 'Native launch-Q-qualified' in value['RequiredBeforeApplication'][0]


@pytest.mark.parametrize('key,value',[('ProposalReady',False),('Blockers',[{'Code':'UnknownPrimitive'}]),
    ('ConstraintsApplied',True),('TimingAccepted',True),('HardwareReleaseAllowed',True),('Target','old_raw_top')])
def test_unknown_or_preaccepted_audit_never_becomes_constraint_authority(scope,key,value):
    scope[key]=value
    with pytest.raises(ValueError):physical.scope_plan(scope)


@pytest.mark.parametrize('field,value',[('LaunchQ','opaque/companion/Q'),('Endpoint','opaque/unmapped/D'),
    ('FromCLK','another/CLK'),('RelationshipIndexes',[1]),('MaximumNS',float('nan')),
    ('MaximumNS',float('inf')),('MaximumNS',True),('MaximumNS',0),('Role','unknown crossing')])
def test_source_q_endpoint_budget_and_relationship_identity_cannot_expand(scope,field,value):
    scope['DataScopes'][0][field]=value
    with pytest.raises(ValueError):physical.scope_plan(scope)


def test_shared_clock_does_not_erase_distinct_actual_launch_q(scope):
    other=copy.deepcopy(scope['ForeignRelationships'][0]);other.update(SourceFF='opaque/companion/FF',
        SourceNativeOutputPin='opaque/companion/Q',SourcePhysicalQ='CLMA_1_2/Q2')
    row=copy.deepcopy(scope['DataScopes'][0]);row.update(LaunchQ='opaque/companion/Q',RelationshipIndexes=[1])
    row['NativeObjects'].update(SourceFFs=['opaque/companion/FF'],SourcePhysicalQ=['CLMA_1_2/Q2'])
    scope['ForeignRelationships'].append(other);scope['DataScopes'].append(row)
    value=physical.scope_plan(scope)
    assert value['ActualDataScopeCount']==2 and value['ConstraintsApplicable'] is False
    assert all(len(q['Names'])==1 for q in value['NativeSelectors'])
    assert {'opaque/source/Q','opaque/companion/Q'}<={n for q in value['NativeSelectors'] for n in q['Names']}
    row['NativeObjects']['SourcePhysicalQ']=['CLMA_1_2/Q1']
    with pytest.raises(ValueError,match='physical Q'):physical.scope_plan(scope)


def native_result(q,names=None,count=None):
    names=names if names is not None else ['t:'+n for n in q['Names']]
    return "I: Timing-5001: The pattern '"+q['Pattern']+"' in command '"+q['Command']+"' match "+str(len(names) if count is None else count)+" objects below: "+' '.join(names)


def group_scope(scope):
    rows=scope['DataScopes']
    for row in rows:row.update(SourceDomain='board27',DestinationDomain='input_pixel')
    pairs={}
    for i,row in enumerate(rows):pairs.setdefault((row['LaunchQ'],row['Endpoint']),[]).append(i)
    support={}
    for q,end in pairs:
        entry=support.setdefault(end,{'SourceFFs':[],'LaunchQs':[],'FunctionalBoundaryNet':'functional/'+end,
            'NativeBoundaryNet':'native/'+end,'SourceSupportComplete':True})
        entry['LaunchQs'].append(q)
        entry['SourceFFs']+=rows[pairs[q,end][0]]['NativeObjects']['SourceFFs']
    for entry in support.values():
        for key in('SourceFFs','LaunchQs'):entry[key]=sorted(set(entry[key]))
    group={'Role':rows[0]['Role'],'MaximumNS':rows[0]['MaximumNS'],
        'SourceDomain':'board27','DestinationDomain':'input_pixel','ScopeIndexes':list(range(len(rows))),
        'FromCLKs':sorted({n for row in rows for n in physical.clock_variants(row)}),
        'LaunchQs':sorted({row['LaunchQ']for row in rows}),'Endpoints':sorted({row['Endpoint']for row in rows}),
        'AllowedPairs':[{'LaunchQ':q,'Endpoint':end,'ScopeIndexes':ix}for(q,end),ix in sorted(pairs.items())],
        'FunctionalNativeSupportMatrixComplete':True,'ReportedEnumerationComplete':False,
        'MatrixConstraintCoverageComplete':False,'ConstraintsApplied':False,
        'NativeSupportMatrixProof':{'AllAxisCrossProductsCheckedAgainstCompleteNativeEndpointSupport':True,
            'SourceDomain':'board27','DestinationDomain':'input_pixel','SupportedAxisPairs':len(pairs),
            'MissingPairs':[],'UnexpectedPairs':[]}}
    scope.update(ConstraintGroups=[group],NativeEndpointSupport=support);return scope


def test_exact_collection_matrix_keeps_full_support_and_uses_bounded_native_commands(scope):
    base=copy.deepcopy(scope['DataScopes'][0]);relation=copy.deepcopy(scope['ForeignRelationships'][0])
    scope['DataScopes']=[];scope['ForeignRelationships']=[]
    for index in range(80):
        row=copy.deepcopy(base);r=copy.deepcopy(relation)
        row.update(Endpoint='opaque/'+('long_native_parent_'*8)+str(index)+'/D',RelationshipIndexes=[index])
        r['NativeBoundaries']=[{'Endpoint':row['Endpoint']}]
        scope['DataScopes'].append(row);scope['ForeignRelationships'].append(r)
    group_scope(scope);commands,selectors,_=physical.application_commands(scope)
    chunks=physical.data_execution_chunks(scope)
    assert len(chunks)>1 and len(commands)==2*len(chunks)<2*80
    assert sorted(i for chunk in chunks for i in chunk['ScopeIndexes'])==list(range(80))
    assert all(len(q['Pattern'])<=4096 for q in selectors)
    assert all('get_clocks'not in c and ' -through ['in c for c in commands)


def test_unaccepted_candidate_can_only_generate_exact_readonly_query_bodies(scope):
    scope.update(ProposalReady=False,Blockers=[{'Code':'OwnershipNotComplete'}])
    bodies=physical.candidate_query_bodies(scope)
    assert len(bodies)==1 and 'set_max_delay'not in bodies[0]and 'get_clocks'not in bodies[0]
    assert all(physical.native.query_commands(body)for body in bodies)
    with pytest.raises(ValueError):physical.application_commands(scope)
    scope['DataScopes'][0]['LaunchQ']='some;command'
    with pytest.raises(ValueError):physical.candidate_query_bodies(scope)


def test_large_dense_matrix_partitions_both_source_clock_Q_axis_and_endpoints_without_pair_loss(scope):
    base=copy.deepcopy(scope['DataScopes'][0]);relation=copy.deepcopy(scope['ForeignRelationships'][0])
    scope['DataScopes']=[];scope['ForeignRelationships']=[]
    for source in range(40):
        parent='actual/'+('long_register_parent_'*7)+str(source)
        for target in range(28):
            index=len(scope['DataScopes']);end='destination/'+('long_input_parent_'*10)+str(target)+'/D'
            row=copy.deepcopy(base);r=copy.deepcopy(relation)
            row.update(FromCLK=parent+'/CLK',LaunchQ=parent+'/Q',Endpoint=end,RelationshipIndexes=[index])
            row['NativeObjects'].update(SourceFFs=[parent+'/FF'],DestinationFFs=['destination'+str(target)+'/FF'],
                SourcePhysicalQ=['CLMA_'+str(source)+'_2/Q1'])
            r.update(SourceFF=parent+'/FF',DestinationFF='destination'+str(target)+'/FF',SourceNativeClockPin=parent+'/CLK',
                SourceNativeOutputPin=parent+'/Q',SourcePhysicalQ=row['NativeObjects']['SourcePhysicalQ'][0],
                NativeBoundaries=[{'Endpoint':end}])
            scope['DataScopes'].append(row);scope['ForeignRelationships'].append(r)
    group_scope(scope);chunks=physical.data_execution_chunks(scope);commands,selectors,_=physical.application_commands(scope)
    assert len({tuple(c['LaunchQs'])for c in chunks})>1
    assert all(len(c['Endpoints'])<28 for c in chunks)
    assert len(commands)==2*len(chunks)<2*len(scope['DataScopes'])
    assert sorted(i for c in chunks for i in c['ScopeIndexes'])==list(range(40*28))
    assert all(len(q['Pattern'])<=4096 for q in selectors)


@pytest.mark.parametrize('change',['drop_pair','extra_pair','wrong_budget','wrong_role','wrong_domain',
    'extra_Q','unknown_endpoint_support','extra_supported_pair','unlisted_timed_relationship','preaccepted','unverified_matrix'])
def test_collection_counts_cannot_replace_complete_actual_native_support_or_role_budget_proof(scope,change):
    group_scope(scope);g=scope['ConstraintGroups'][0];row=scope['DataScopes'][0]
    if change=='drop_pair':g['AllowedPairs']=[]
    elif change=='extra_pair':g['AllowedPairs'].append({'LaunchQ':'companion/Q','Endpoint':row['Endpoint'],'ScopeIndexes':[0]})
    elif change=='wrong_budget':g['MaximumNS']=99
    elif change=='wrong_role':g['Role']='another_reviewed_role'
    elif change=='wrong_domain':g['SourceDomain']='input_pixel'
    elif change=='extra_Q':g['LaunchQs'].append('companion/Q')
    elif change=='unknown_endpoint_support':scope['NativeEndpointSupport'][row['Endpoint']]['SourceSupportComplete']=False
    elif change=='extra_supported_pair':scope['NativeEndpointSupport'][row['Endpoint']]['LaunchQs']=[]
    elif change=='unlisted_timed_relationship':
        other=copy.deepcopy(scope['ForeignRelationships'][0]);other['NativeBoundaries']=[{'Endpoint':'other/D'}]
        scope['ForeignRelationships'].append(other);g['Endpoints'].append('other/D')
    elif change=='preaccepted':g['MatrixConstraintCoverageComplete']=True
    else:g['NativeSupportMatrixProof']['AllAxisCrossProductsCheckedAgainstCompleteNativeEndpointSupport']=False
    with pytest.raises(ValueError):physical.scope_plan(scope)


def test_complete_support_keeps_unselected_local_FF_without_requiring_a_separate_native_Q(scope):
    group_scope(scope);entry=scope['NativeEndpointSupport'][scope['DataScopes'][0]['Endpoint']]
    entry['SourceFFs']=sorted(entry['SourceFFs']+['unselected_local_ff_without_native_Q'])
    assert physical.scope_plan(scope)['ConstraintGroups']
    entry['SourceFFs']=['unselected_local_ff_without_native_Q']
    with pytest.raises(ValueError,match='launch projection'):physical.scope_plan(scope)


def add_synchronous_reset(scope):
    r=copy.deepcopy(scope['ForeignRelationships'][0]);row=copy.deepcopy(scope['DataScopes'][0])
    row.update(Endpoint='reset_target/D',TargetKind='FFSynchronousResetFunction',FunctionalDestinationPin='D',
        GuardAccepted=True,GuardProof={'NativeNextQInactiveGuardVerified':True,'LocalReleaseChainVerified':True,
            'OnlyResetFunctionProven':True,'BusinessDataPathWaiver':False},RelationshipIndexes=[len(scope['ForeignRelationships'])])
    row['NativeObjects']['DestinationFFs']=['actual/reset_target/FF']
    r.update(DestinationFF='actual/reset_target/FF',DestinationPin='D',NativeBoundaries=[{'Endpoint':row['Endpoint']}])
    scope['ForeignRelationships'].append(r);scope['UserSynchronousResetScopes']=[row];return row


def add_macro_WE(scope):
    row=copy.deepcopy(scope['DataScopes'][0]);r=copy.deepcopy(scope['ForeignRelationships'][0])
    target={'Cell':'actual/words/ram32','Primitive':'V_RAM32X2','Pin':'WE','Endpoint':'actual/native_words/WE'}
    row.update(TargetKind='MacroFunctionalInput',DestinationDomain='input_pixel',Endpoint=target['Endpoint'],
        RelationshipIndexes=[len(scope['ForeignRelationships'])])
    row['NativeObjects'].update(DestinationFFs=[],DestinationObjects=[target])
    r.update(TargetKind='MacroFunctionalInput',DestinationObject=copy.deepcopy(target),DestinationPin='WE',
        DestinationClock='input_pixel',NativeBoundaries=[{'Endpoint':target['Endpoint']}])
    r.pop('DestinationFF',None);scope['ForeignRelationships'].append(r);scope['DataScopes'].append(row)
    scope['PrimitiveBoundaries']=[{'Cell':target['Cell'],'Primitive':target['Primitive'],
        'ClockBindings':[{'Pin':'WCLK','Domain':'input_pixel','Root':'actual/pixel_clock','Trace':[]}]}]
    return row


def test_macro_WE_held_control_uses_exact_native_target_and_real_write_clock_without_fake_FF(scope):
    row=add_macro_WE(scope);commands,_,body=physical.application_commands(scope)
    assert len(commands)==4 and row['NativeObjects']['DestinationFFs']==[]
    assert physical.exact_selector([row['Endpoint']])['Command']in commands[2]
    assert row['Endpoint']in body


@pytest.mark.parametrize('change',['no_clock','wrong_clock_domain','wrong_primitive','wrong_port',
    'wrong_endpoint','fake_destination_FF','unmatched_relationship'])
def test_macro_data_scope_needs_typed_actual_memory_WE_and_clock_bound_relationship(scope,change):
    row=add_macro_WE(scope);target=row['NativeObjects']['DestinationObjects'][0]
    if change=='no_clock':scope['PrimitiveBoundaries'][0]['ClockBindings']=[]
    elif change=='wrong_clock_domain':scope['PrimitiveBoundaries'][0]['ClockBindings'][0]['Domain']='board27'
    elif change=='wrong_primitive':target['Primitive']='V_APM_E2'
    elif change=='wrong_port':target['Pin']='DIA'
    elif change=='wrong_endpoint':target['Endpoint']='another/WE'
    elif change=='fake_destination_FF':row['NativeObjects']['DestinationFFs']=['pretend_FF']
    else:scope['ForeignRelationships'][-1]['DestinationObject']['Cell']='other/memory'
    with pytest.raises(ValueError):physical.application_commands(scope)


def test_macro_reset_encoded_in_WE_needs_separate_inactive_WE_zero_guard(scope):
    row=add_macro_WE(scope);scope['DataScopes'].pop();scope['UserSynchronousResetScopes']=[row]
    row.update(TargetKind='MacroWriteEnableResetFunction',FunctionalDestinationPin='WE',GuardAccepted=True,
        GuardProof={'NativeNextQInactiveGuardVerified':True,'LocalReleaseChainVerified':True,
            'OnlyResetFunctionProven':True,'BusinessDataPathWaiver':False,'NativeWEInactiveGuardVerified':True})
    commands,_,_=physical.application_commands(scope)
    assert len(commands)==3 and 'set_false_path'in commands[-1]
    row['GuardProof']['NativeWEInactiveGuardVerified']=False
    with pytest.raises(ValueError,match='WE=0'):physical.application_commands(scope)


def test_D_encoded_synchronous_reset_is_separate_from_SR_arcs_and_requires_native_guard(scope):
    row=add_synchronous_reset(scope);commands,selectors,body=physical.application_commands(scope)
    assert len(commands)==3 and commands[-1].startswith('set_false_path -from ')
    assert physical.exact_selector([row['Endpoint']])['Command']in commands[-1]
    assert physical.reset_rows(scope)==[]and physical.all_reset_rows(scope)==[row]
    assert row['Endpoint']in body


@pytest.mark.parametrize('missing',[None,'NativeResetStateEstablishedVerified','NativeIdleResetValueInvariantVerified',
    'SourceAdmissionGuardVerified','GuardedDeassertionVerified','OnlyResetFunctionProven','false_arbitrary_claim','bool_reset_value'])
def test_encoded_reset_value_invariant_needs_establishment_and_real_consumer_admission_not_arbitrary_self_cofactor(scope,missing):
    row=add_synchronous_reset(scope)
    row['GuardProof']={'ProofKind':'established_reset_state_stable_through_guarded_deassertion',
        'NativeResetStateEstablishedVerified':True,'NativeIdleResetValueInvariantVerified':True,
        'SourceAdmissionGuardVerified':True,'GuardedDeassertionVerified':True,'OnlyResetFunctionProven':True,
        'EstablishedPhysicalQ':1,'ArbitrarySelfInactiveConstantClaimed':False,'BusinessDataPathWaiver':False}
    if missing is None:
        assert physical.synchronous_reset_rows(scope)==[row];return
    if missing=='false_arbitrary_claim':row['GuardProof']['NativeNextQInactiveGuardVerified']=True
    elif missing=='bool_reset_value':row['GuardProof']['EstablishedPhysicalQ']=True
    else:row['GuardProof'][missing]=False
    with pytest.raises(ValueError,match='guarded-deassertion'):physical.synchronous_reset_rows(scope)


@pytest.mark.parametrize('change',['no_nextQ_guard','no_local_release_chain','business_waiver','wrong_function',
    'wrong_relationship_pin','wrong_target_type','data_overlap'])
def test_synchronous_reset_classification_cannot_waive_ordinary_business_D_or_claim_SR_recovery(scope,change):
    row=add_synchronous_reset(scope)
    if change=='no_nextQ_guard':row['GuardProof']['NativeNextQInactiveGuardVerified']=False
    elif change=='no_local_release_chain':row['GuardProof']['LocalReleaseChainVerified']=False
    elif change=='business_waiver':row['GuardProof']['BusinessDataPathWaiver']=True
    elif change=='wrong_function':row['FunctionalDestinationPin']='SR'
    elif change=='wrong_relationship_pin':scope['ForeignRelationships'][-1]['DestinationPin']='CE'
    elif change=='wrong_target_type':row['TargetKind']='ordinary_business_data'
    else:
        row['Endpoint']=scope['DataScopes'][0]['Endpoint']
        scope['ForeignRelationships'][-1]['NativeBoundaries']=[{'Endpoint':row['Endpoint']}]
    with pytest.raises(ValueError):physical.application_commands(scope)


def test_native_query_count_is_insufficient_without_exact_actual_names(scope):
    queries=physical.scope_plan(scope)['NativeSelectors'];text='\n'.join(native_result(q) for q in queries)
    assert physical.exact_names(queries,text)['ExactNativeNamesVerified'] is True
    for changed in (text.replace('t:opaque/source/Q','t:opaque/companion/Q'),text+'\n'+native_result(queries[0]),
        '\n'.join(text.splitlines()[:-1]),text.replace('match 1 objects','match 2 objects')):
        with pytest.raises(ValueError):physical.exact_names(queries,changed)


@pytest.mark.parametrize('name',['raw; save_adif','bad}name','t:source/Q','contains space','bad\\path'])
def test_tcl_metacharacters_or_noncanonical_pins_are_rejected(name):
    with pytest.raises(ValueError):physical.exact_selector([name])


def good_tables():
    return {(corner,kind):{('new_clock_'+kind,):{'WorstSlackNS':0.1,'TotalNegativeSlackNS':0.0,
        'FailingChecks':0,'TotalChecks':7}} for corner in ('slow','fast') for kind in physical.timing.KINDS}


def test_all_ten_tables_use_current_candidate_counts():
    tables=good_tables();assert physical.all_ten_pass(tables)['CandidateCountsInherited'] is False
    tables.pop(('fast','mpw'))
    with pytest.raises(ValueError):physical.all_ten_pass(tables)


@pytest.mark.parametrize('field,value',[('WorstSlackNS',-0.001),('WorstSlackNS',float('nan')),
    ('TotalNegativeSlackNS',-0.1),('FailingChecks',1),('FailingChecks',False),('TotalChecks',0)])
def test_any_remaining_native_failure_or_empty_check_is_rejected(field,value):
    tables=good_tables();tables[('slow','hold')][('new_clock_hold',)][field]=value
    with pytest.raises(ValueError):physical.all_ten_pass(tables)


def test_applied_commands_qualify_every_exact_actual_q_and_never_cut_a_clock_group(scope):
    commands,selectors,body=physical.application_commands(scope)
    assert len(commands)==2 and commands[0].startswith('set_max_delay -datapath_only')
    assert commands[1].startswith('set_false_path -hold')
    assert all(' -from [get_pins ' in c and ' -through [get_pins ' in c and ' -to [get_pins ' in c for c in commands)
    assert all('clock_groups' not in c and 'get_clocks' not in c for c in commands)
    assert body==physical.scope_plan(scope)['PreflightQueryBody']
    scope['ResetScopes']=[{'Source':'guessed/reset'}]
    with pytest.raises(ValueError):physical.application_commands(scope)


def test_static_helper_closure_is_determined_by_source_imports_not_loaded_callers(tmp_path,monkeypatch):
    main=tmp_path/'main.py';nested=tmp_path/'nested.py';other=tmp_path/'newcaller.py'
    main.write_text('import nested\n');nested.write_text('VALUE=1\n');other.write_text('VALUE=2\n')
    monkeypatch.setattr(physical,'SELF',main)
    watched=physical.static_helpers({},main)
    assert set(watched)=={main,nested} and other not in watched


def test_saved_scope_requires_complete_recomputation_and_actual_hashes(tmp_path,scope,monkeypatch):
    own=tmp_path/'hdmi_camera_fisheye_tile8df8v3_physical.py';own.write_text('bound helper')
    producer_path=tmp_path/'hdmi_camera_fisheye_tile8df8_audit.py';producer_path.write_text('bound provider')
    monkeypatch.setattr(physical,'SELF',own)
    dependency=tmp_path/'actual-source.v';dependency.write_text('original')
    scope.update(InputSHA256={str(dependency):physical.sha(dependency)},
        BuildPlan={'Path':'current-plan'},ExportReceipt={'Path':'current-export'},RouteReceipt={'Path':'current-route'})
    current=copy.deepcopy(scope);path=tmp_path/'audit.json';path.write_text(json.dumps(scope))
    producer=SimpleNamespace(__file__=str(physical.SELF.with_name('hdmi_camera_fisheye_tile8df8_audit.py')),
        derive=lambda *args:(current,{dependency:physical.sha(dependency)}))
    monkeypatch.setattr(physical.importlib,'import_module',lambda name:producer)
    _,watched=physical._bind_audit(path);assert dependency in watched and path in watched
    current['DataScopes'][0]['MaximumNS']=99
    with pytest.raises(ValueError,match='facts differ'):physical._bind_audit(path)
    current['DataScopes'][0]['MaximumNS']=6.6667;dependency.write_text('changed')
    with pytest.raises(ValueError,match='SHA'):physical._bind_audit(path)


@pytest.mark.parametrize('change',['drift','missing','caller_mutation'])
def test_process_authority_cache_rehashes_entire_closure_and_deepcopies_returns(tmp_path,change):
    path=tmp_path/'authority.json';path.write_text('bound receipt')
    dependency=tmp_path/'input.v';dependency.write_text('original');calls=[]
    def derive(p):
        calls.append(str(p));return {'Fields':{'Passed':True}},{dependency:physical.sha(dependency)}
    value,watched=physical.authority('regression',path,derive)
    value['Fields']['Passed']=False;watched.clear()
    if change=='drift':dependency.write_text('changed')
    elif change=='missing':dependency.unlink()
    if change!='caller_mutation':
        with pytest.raises(ValueError,match='cached fisheye authority input drift'):physical.authority('regression',path,derive)
    else:
        again,bound=physical.authority('regression',path,derive)
        assert again['Fields']['Passed'] is True and dependency in bound and path in bound
        assert len(calls)==1



def test_large_fisheye_held_bundle_preflight_uses_small_exact_groups_without_exceeding_native_command_bound():
    rows=[{'FromCLK':'source'+str(n)+'/CLK','LaunchQ':'source'+str(n)+'/Q',
        'Endpoint':'dest'+str(n)+'/D'}for n in range(160)]
    queries=physical.selectors_for(rows)
    assert len(queries)<160 and all(1<=len(q['Names'])<=70 and len(q['Pattern'])<=4096 for q in queries)
    assert physical.native.query_commands('\n'.join(q['Command']for q in queries))
    assert physical.exact_names(queries,'\n'.join(native_result(q)for q in queries))['Objects']==480



def add_clock_variants(row):
    names=sorted([row['FromCLK'],'opaque/clock_buddy/CLK'])
    row['FromCLKVariants']=names
    row['FromCLKVariantProof']={'Verified':True,'PhysicalCLK':'CLMA_1_2/CLK','CLKNet':'native_clk1',
        'Parents':[{'Instance':name.rsplit('/',1)[0],'CLKPin':name,'Site':'CLMA_1_2','CLKNet':'native_clk1'}for name in names]}
    return row


def test_shared_physical_clock_alias_union_keeps_single_exact_q_and_endpoint(scope):
    row=add_clock_variants(scope['DataScopes'][0]);commands,selectors,body=physical.application_commands(scope)
    from_selector=physical.exact_selector(row['FromCLKVariants'])['Command']
    assert all(' -from ['+from_selector+'] -through ['+physical.exact_selector([row['LaunchQ']])['Command']+']'in cmd for cmd in commands)
    assert all(' -to ['+physical.exact_selector([row['Endpoint']])['Command']+']'in cmd for cmd in commands)
    assert 'opaque/clock_buddy/CLK'in body and not any('get_clocks'in cmd or'clock_groups'in cmd for cmd in commands)
    assert physical.scope_plan(scope)['ActualDataScopeCount']==1


@pytest.mark.parametrize('change',[None,'missing_shared_key','changed_reference','wrong_parent','nested_reference'])
def test_shared_source_clock_proofs_remain_exact_without_expanding_or_mutating_saved_rows(scope,change):
    row=add_clock_variants(scope['DataScopes'][0]);proof=row['FromCLKVariantProof']
    scope['SharedSourceClockProofs']={'actual_source':copy.deepcopy(proof)}
    row['FromCLKVariantProof']={k:v for k,v in proof.items()if k!='Parents'}
    row['FromCLKVariantProof']['SharedSourceClockProofKey']='actual_source'
    before=copy.deepcopy(row)
    if change=='missing_shared_key':scope['SharedSourceClockProofs'].clear()
    elif change=='changed_reference':row['FromCLKVariantProof']['CLKNet']='different'
    elif change=='wrong_parent':scope['SharedSourceClockProofs']['actual_source']['Parents'][0]['Site']='CLMA_other'
    elif change=='nested_reference':scope['SharedSourceClockProofs']['actual_source']['SharedSourceClockProofKey']='again'
    if change is None:
        assert physical.scope_plan(scope)['ActualDataScopeCount']==1 and row==before and 'Parents'not in row['FromCLKVariantProof']
    else:
        with pytest.raises(ValueError):physical.application_commands(scope)


@pytest.mark.parametrize('change',['wrong_site','wrong_net','different_clock_pin','missing_original',
    'extra_clock_without_proof','unverified','wrong_physical','too_many','unsorted'])
def test_clock_alias_scope_requires_every_actual_parent_in_same_site_and_net(scope,change):
    row=add_clock_variants(scope['DataScopes'][0]);proof=row['FromCLKVariantProof']
    if change=='wrong_site':proof['Parents'][0]['Site']='CLMA_2_3'
    elif change=='wrong_net':proof['Parents'][0]['CLKNet']='differentclk'
    elif change=='different_clock_pin':proof['Parents'][0]['CLKPin']='unproven/CLK'
    elif change=='missing_original':row['FromCLKVariants'].remove(row['FromCLK'])
    elif change=='extra_clock_without_proof':row['FromCLKVariants'].append('unproven/CLK')
    elif change=='unverified':proof['Verified']=False
    elif change=='wrong_physical':proof['PhysicalCLK']='CLMA_2_3/CLK'
    elif change=='too_many':row['FromCLKVariants']=[row['FromCLK']]+['other'+str(i)+'/CLK'for i in range(8)]
    else:row['FromCLKVariants'].reverse()
    with pytest.raises(ValueError):physical.application_commands(scope)



def vendor_reset(scope):
    row=copy.deepcopy(scope['DataScopes'][0]);row.update(FromCLK='power_ready/native/CLK',LaunchQ='power_ready/native/Q',
        Endpoint='u_ddr3_test_h/u_ddrphy_top/u_ddrphy_rst_seq_rstn_sync/sig_async_r1[0]/native/RS',
        Family='entry_rdc',LaunchClock='board27',CaptureClock='rst_clk',TargetKind='DDRPrimitiveReset',GuardAccepted=True,
        GuardProof={'NativeVendorResetGraphPassed':True,'CurrentReportCoverageVerified':True,'HistoricalEndpointCountsInherited':False})
    row['NativeObjects']={'SourceFFs':['power_ready/native/FF0/FF'],'SourcePhysicalQ':['CLMA_1_2/Q0'],
        'SourceCLKNet':['boardnet'],'DestinationObjects':[{'Cell':'ddr/entry/FF0/FF','Primitive':'V_FFASYN',
            'Pin':'SR','Endpoint':row['Endpoint']}]}
    return row


def test_vendor_reset_is_an_exact_typed_macro_or_entry_path_with_current_graph_and_report_proof(scope):
    row=vendor_reset(scope);scope['VendorResetScopes']=[row]
    commands,selectors,body=physical.application_commands(scope)
    assert len(commands)==3 and commands[-1].startswith('set_false_path -from [get_pins ')
    assert physical.exact_selector([row['Endpoint']])['Command']in commands[-1]and 'get_clocks'not in commands[-1]
    assert physical.reset_rows(scope)==[row]


@pytest.mark.parametrize('change',['wrongclock','wrongfamily','wrongpin','no_graph','oldcounts','wrongtypedcell'])
def test_vendor_prefix_or_old_720_counts_cannot_authorize_a_current_reset_cut(scope,change):
    row=vendor_reset(scope);scope['VendorResetScopes']=[row]
    if change=='wrongclock':row['CaptureClock']='core_clk'
    elif change=='wrongfamily':row['Family']='iol_reset'
    elif change=='wrongpin':row['NativeObjects']['DestinationObjects'][0]['Pin']='D'
    elif change=='no_graph':row['GuardProof']['NativeVendorResetGraphPassed']=False
    elif change=='oldcounts':row['GuardProof']['HistoricalEndpointCountsInherited']=True
    elif change=='wrongtypedcell':row['NativeObjects']['DestinationObjects'][0]['Primitive']='V_APM_E2'
    with pytest.raises(ValueError):physical.application_commands(scope)



def test_preflight_partition_retains_every_exact_native_object_in_bounded_shards(scope):
    base=scope['ForeignRelationships'][0];row=scope['DataScopes'][0]
    scope['DataScopes']=[];scope['ForeignRelationships']=[]
    for index in range(330):
        r=copy.deepcopy(base);s=copy.deepcopy(row)
        source='a'*1000+'/source'+str(index);dest='b'*1000+'/dest'+str(index)
        r.update(SourceFF=source+'/FF',DestinationFF=dest+'/FF',
            SourceNativeClockPin=source+'/CLK',SourceNativeOutputPin=source+'/Q',
            NativeBoundaries=[{'Endpoint':dest+'/D'}])
        s.update(FromCLK=r['SourceNativeClockPin'],LaunchQ=r['SourceNativeOutputPin'],Endpoint=dest+'/D',RelationshipIndexes=[index])
        s['NativeObjects'].update(SourceFFs=[r['SourceFF']],DestinationFFs=[r['DestinationFF']])
        scope['ForeignRelationships'].append(r);scope['DataScopes'].append(s)
    value=physical.scope_plan(scope);bodies=value['PreflightQueryBodies']
    assert len(bodies)==2 and ''.join(bodies)==value['PreflightQueryBody']
    assert all(1<=len(physical.native.query_commands(body))<=240 for body in bodies)
    assert len(value['NativeSelectors'])>240 and sum(len(q['Names'])for q in value['NativeSelectors'])==990


@pytest.mark.parametrize('change',['none','wrong_source','body_drift','wrong_name','missing_receipt','duplicate_receipt'])
def test_each_preflight_shard_requires_exact_current_source_body_and_actual_names(tmp_path,scope,monkeypatch,change):
    scope.update(BuildPlan={'SHA256':'plan-sha'},SourceADF={'Path':'current.adf','SHA256':'adf-sha'})
    proposal=physical.scope_plan(scope);body=proposal['PreflightQueryBody'];path=tmp_path/'result.json'
    path.write_text('bound receipt');query=tmp_path/'body.tcl';query.write_text(body,encoding='ascii')
    log=tmp_path/'stdout.log';log.write_text('\n'.join(native_result(q)for q in proposal['NativeSelectors']))
    value={'Mode':'query','BuildPlanSHA256':'plan-sha','SourceADF':'current.adf','SourceADFSHA256':'adf-sha','QueryBody':str(query)}
    monkeypatch.setattr(physical.native,'bind_receipt',lambda *a:(value,{}))
    paths=[path]
    if change=='wrong_source':value['SourceADFSHA256']='other'
    elif change=='body_drift':query.write_text(body+'puts {extra}\n')
    elif change=='wrong_name':log.write_text(log.read_text().replace('t:opaque/source/Q','t:another/Q'))
    elif change=='missing_receipt':paths=[]
    elif change=='duplicate_receipt':paths*=2
    if change=='none':assert physical.preflight_receipts(scope,paths,{})==paths
    else:
        with pytest.raises(ValueError):physical.preflight_receipts(scope,paths,{})


@pytest.fixture
def fragments(tmp_path,scope,monkeypatch):
    scope.update(BuildPlan={'SHA256':'current-plan'},SourceADF={'Path':'current.adf','SHA256':'current-adf'})
    names=sorted({n for q in physical.scope_plan(scope)['NativeSelectors']for n in q['Names']})
    parts=[sorted(names[:2]+['unused/exploratory/Q']),names[2:]];paths=[];values={}
    for i,part in enumerate(parts):
        work=tmp_path/str(i);work.mkdir();path=work/'result.json';path.write_text('bound')
        q=physical.exact_selector(part);body=work/'body.tcl';body.write_text(q['Command']+'\n')
        (work/'stdout.log').write_text(native_result(q)+'\n')
        values[path]={'Mode':'query','BuildPlanSHA256':'current-plan','SourceADF':'current.adf',
            'SourceADFSHA256':'current-adf','QueryBody':str(body)};paths.append(path)
    monkeypatch.setattr(physical.native,'bind_receipt',lambda path:(values[path],{}))
    return scope,paths,values


def test_verified_name_fragments_cover_new_scope_without_claiming_original_body_identity(fragments):
    scope,paths,_=fragments;actual,review=physical.preflight_qualification(scope,paths,{})
    assert actual==paths and review['PreflightMode']=='verified-native-name-fragments'
    assert review['ExactCurrentQueryBodiesIdentical']is False and review['RequiredNativeObjectCount']==3
    assert review['UnusedExploratoryNames']==['unused/exploratory/Q']
    assert review['ExploratoryNamesGrantConstraintAuthority']is False
    assert physical.supplemental_query_bodies(scope,paths)==[]


def test_fresh_candidate_inventory_batches_thousands_of_exact_pins_into_one_bounded_stage(tmp_path):
    plan=tmp_path/'plan.json';plan.write_text(json.dumps({'Target':physical.build.TARGET}))
    names=sorted('currentC/parent'+str(i)+'/Q'for i in range(3433))
    inventory={'CandidateOnly':True,'AuthorityIssued':False,'BuildPlan':physical.ref(plan),
        'RequiredNativeObjects':names,'Count':len(names)}
    bodies=physical.candidate_query_bodies(inventory)
    assert len(bodies)==1
    selectors=physical.literal_query_selectors(bodies[0])
    assert len(selectors)<100 and sorted(n for q in selectors for n in q['Names'])==names
    assert all(len(q['Pattern'])<=4096 and len(q['Names'])<=70 for q in selectors)
    assert physical.exact_names(selectors,'\n'.join(native_result(q)for q in selectors))['Objects']==3433
    inventory['AuthorityIssued']=True
    with pytest.raises(ValueError):physical.candidate_query_bodies(inventory)


@pytest.mark.parametrize('change',['missing_name','wrong_source','altered_actual_name','add_STA',
    'too_many_literals','too_long_selector','wildcard','ambiguous_duplicate_name'])
def test_fragment_coverage_rejects_missing_or_ambiguous_names_and_extra_executable_grammar(fragments,change):
    scope,paths,values=fragments;path=paths[-1];body=Path(values[path]['QueryBody'])
    if change=='missing_name':paths=paths[:-1]
    elif change=='wrong_source':values[path]['SourceADFSHA256']='other'
    elif change=='altered_actual_name':(path.parent/'stdout.log').write_text((path.parent/'stdout.log').read_text().replace('t:','t:wrong/'))
    elif change=='add_STA':body.write_text(body.read_text()+'report_path_timing -help\n')
    elif change=='too_many_literals':body.write_text(physical.exact_selector(sorted('source'+str(i)+'/Q'for i in range(71)))['Command']+'\n')
    elif change=='too_long_selector':body.write_text(physical.exact_selector(['a'*4096+'/Q'])['Command']+'\n')
    elif change=='wildcard':body.write_text('get_pins -hierarchical -regexp {^(anything.*)$}\n')
    else:
        q=physical.exact_selector(['unused/exploratory/Q']);body.write_text(q['Command']+'\n')
        (path.parent/'stdout.log').write_text(native_result(q)+'\n')
    with pytest.raises(ValueError):physical.preflight_qualification(scope,paths,{})



def multiple_vendor_contexts(scope):
    row=vendor_reset(scope)
    parent='u_ddr3_test_h/u_ddrphy_top/ddrphy_reset_ctrl/ddrphy_dqs_rst/native'
    endpoint='u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/ddc/native/RST'
    row.update(FromCLK=parent+'/CLK',LaunchQ=parent+'/Q',Endpoint=endpoint,Family='dqs_reset',LaunchClock='rst_clk')
    row['NativeObjects']['DestinationObjects']=[{'Cell':'ddr/ddc/DDC_E2','Primitive':'V_DDC_E2','Pin':'RST','Endpoint':endpoint}]
    row['NativeObjects']['SourceFFs']=[parent+'/FF0/FF']
    rows=[]
    for capture in ('phy_dq_clk_0','phy_dq_sysclk_0'):
        other=copy.deepcopy(row);other['CaptureClock']=capture
        identity={'Source':other['FromCLK'],'Endpoint':endpoint,'LaunchClock':'rst_clk','CaptureClock':capture,'Family':'dqs_reset'}
        other['GuardProof']['NativeReportCheck']={**identity,'CaptureEdgesComplete':True,'NativeVariants':[
            {**identity,'Corner':'slow','LaunchEdge':'rising','CaptureEdge':'falling','LaunchDataTransition':'r',
                'NativeReportLine':17,'NativePathSHA256':'a'*64}]}
        rows.append(other)
    scope['VendorResetScopes']=rows
    scope['PrimitiveBoundaries']=[{'Cell':'ddr/ddc/DDC_E2','Primitive':'V_DDC_E2','ClockBindings':[
        {'Pin':pin,'Domain':capture,'Root':'actual/'+pin,'Trace':[{'Actual':'clocktrace'}]}
        for pin,capture in zip(('CLKA','CLKB'),('phy_dq_clk_0','phy_dq_sysclk_0'))]}]
    return rows


def test_identical_unqualified_reset_command_retains_all_distinct_internal_capture_proofs(scope):
    original=multiple_vendor_contexts(scope);saved=copy.deepcopy(scope)
    rows=physical.reset_rows(scope);assert len(rows)==1 and scope==saved
    evidence=rows[0]['ResetConstraintEvidence']
    assert rows[0]['CaptureClocks']==['phy_dq_clk_0','phy_dq_sysclk_0'] and 'CaptureClock'not in rows[0]
    assert evidence['DistinctInternalCaptureClocksAreAliases']is False
    assert [r['Index']for r in evidence['OriginalRows']]==[0,1]
    assert [r['GuardProof']for r in evidence['OriginalRows']]==[r['GuardProof']for r in original]
    commands,_,_=physical.application_commands(scope)
    assert len(commands)==3 and commands[-1].count('set_false_path')==1
    assert '-rise'not in commands[-1]and '-fall'not in commands[-1]and 'get_clocks'not in commands[-1]
    summary=physical.reset_constraint_evidence(scope)
    assert summary['OriginalVendorRows']==2 and summary['CanonicalNativeConstraints']==1


@pytest.mark.parametrize('change',['physicalQ','net','family','reportclock','pathhash','targetclock','samecapture','guardkind'])
def test_multi_capture_reset_normalization_rejects_any_physical_guard_or_context_conflict(scope,change):
    rows=multiple_vendor_contexts(scope);r=rows[1]
    if change=='physicalQ':r['NativeObjects']['SourcePhysicalQ']=['CLMA_1_2/Q2']
    elif change=='net':r['NativeObjects']['SourceCLKNet']=['othernet']
    elif change=='family':r['Family']='iol_reset'
    elif change=='reportclock':r['GuardProof']['NativeReportCheck']['CaptureClock']='other'
    elif change=='pathhash':r['GuardProof']['NativeReportCheck']['NativeVariants'][0]['NativePathSHA256']='not-a-hash'
    elif change=='targetclock':scope['PrimitiveBoundaries'][0]['ClockBindings'].pop()
    elif change=='guardkind':r['GuardProof']['DifferentProofKind']=True
    else:
        r['CaptureClock']=rows[0]['CaptureClock'];r['GuardProof']['NativeReportCheck']=copy.deepcopy(rows[0]['GuardProof']['NativeReportCheck'])
    with pytest.raises(ValueError):physical.application_commands(scope)
