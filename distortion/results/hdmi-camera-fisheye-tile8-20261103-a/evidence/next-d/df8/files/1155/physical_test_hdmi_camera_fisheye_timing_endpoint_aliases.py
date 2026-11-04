import copy,importlib.util,sys
from pathlib import Path
import pytest
ROOT=Path('D:\\GravityLRT\\thu\\semester_4.5\\FPGAchina\\fpga-distortion-correction\\distortion')
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT/'tests'))
import hdmi_camera_fisheye_tile8df8v2_physical as p
import hdmi_camera_fisheye_tile8df8v2_final as f
from physical_test_hdmi_camera_fisheye_physical import scope as original_scope,group_scope
@pytest.fixture
def current():
    s=original_scope.__wrapped__();r=s['DataScopes'][0];r['Endpoint']='opaque/target/CE'
    s['ForeignRelationships'][0]['NativeBoundaries'][0]['Endpoint']=r['Endpoint']
    s['BaselineTimingReport']={'Path':'current/native.rtr','SHA256':'a'*64}
    signature={'LCE_POL':['STRING','"FALSE"'],'LCE_EN':['STRING','"TRUE"'],'CEMUX_SEL':['STRING','"LOCAL"']}
    controlled=[{'FF':parent+'/FF0/FF','NativeParent':parent,'Placement':{'Site':'CLMA_4_5'},
        'NativeControlNet':'same-net','NativeControlSignature':signature,
        'Clock':{'Domain':'destination','Root':'same-clock','Trace':[{'Actual':'clock'}]}}for parent in ['opaque/target','opaque/sibling']]
    proof={'Verified':True,'PhysicalTimingPin':'CLMA_4_5/CE','CanonicalTimingEndpoint':r['Endpoint'],
        'NativeControlNet':'same-net','NativeControlSignature':signature,'CurrentBaselineReport':s['BaselineTimingReport'],
        'OtherObservedCanonicalNames':['opaque/sibling/CE','opaque/target/CE'],'ControlledFFs':controlled,
        'CompleteControlledFFInventoryVerified':True,'SourceSupportEqualityVerified':True,
        'ClockRootAndPolarityAndMuxVerified':True,'GetPinsExistenceAloneAccepted':False,
        'ArbitrarySameClockOrHierarchyPrefixAliasAccepted':False}
    s['QualifiedTimingControlEndpointProofs']={'CLMA_4_5/CE':proof};return s

def test_valid_observed_arc_union_is_explicit_and_preserves_original_canonical_matrix(current):
    s=current;before=copy.deepcopy(s);a=p.timing_endpoint_aliases(s)
    assert p.endpoint_variants(s['DataScopes'][0],a)==['opaque/sibling/CE','opaque/target/CE']
    commands,selectors,_=p.application_commands(s)
    assert 'opaque/sibling/CE' in commands[0]and 'opaque/target/CE'in commands[0]
    assert 'get_clocks'not in commands[0]and s==before
    group_scope(s);chunks=p.data_execution_chunks(s)
    assert chunks[0]['CanonicalEndpoints']==['opaque/target/CE']and chunks[0]['Endpoints']==a['opaque/target/CE']['Names']

@pytest.mark.parametrize('change',['unseen_parent','site','net','polarity','root','no_proof','other_report','duplicate','wildcard'])
def test_unqualified_control_aliases_never_expand_selector(current,change):
    v=current['QualifiedTimingControlEndpointProofs']['CLMA_4_5/CE']
    if change=='unseen_parent':v['OtherObservedCanonicalNames'].insert(0,'another/CE')
    elif change=='site':v['ControlledFFs'][0]['Placement']['Site']='CLMA_7_8'
    elif change=='net':v['ControlledFFs'][0]['NativeControlNet']='other'
    elif change=='polarity':v['ControlledFFs'][0]['NativeControlSignature']=dict(v['NativeControlSignature'],LCE_POL=['STRING','"TRUE"'])
    elif change=='root':v['ControlledFFs'][0]['Clock']['Root']='other'
    elif change=='no_proof':v['SourceSupportEqualityVerified']=False
    elif change=='other_report':v['CurrentBaselineReport']={'Path':'other','SHA256':'b'*64}
    elif change=='duplicate':v['OtherObservedCanonicalNames'].append(v['OtherObservedCanonicalNames'][0])
    else:v['OtherObservedCanonicalNames'][0]='opaque/.*/CE'
    with pytest.raises(ValueError):p.application_commands(current)


def test_reported_valid_alias_requires_same_exact_physical_pin_and_source_Q(current):
    target=current['DataScopes'][0];aliases=p.timing_endpoint_index(current)
    row={'LaunchOutput':target['LaunchQ'],'Endpoint':'opaque/sibling/CE','PhysicalTimingEndpoint':'CLMA_4_5/CE',
        'PhysicalQ':'CLMA_1_2/Q1','PhysicalCLK':'CLMA_1_2/CLK','Source':target['FromCLK']}
    route={'Pins':{('opaque/source','CLK'):'native_clk1'}};places={'opaque/source':{'Site':'CLMA_1_2'}}
    assert f.launch_identity(row,target,route,places,current,aliases)is False
    row['PhysicalTimingEndpoint']='CLMA_8_9/CE'
    with pytest.raises(ValueError,match='physical endpoint'):f.launch_identity(row,target,route,places,current,aliases)


@pytest.fixture
def macro(current,monkeypatch):
    ends=['macro/'+x+'/WE'for x in('A','B','C')];names=ends+['macro/D/WE']
    rows=[]
    for end in ends:
        row=copy.deepcopy(current['DataScopes'][0]);row.update(Endpoint=end,TargetKind='MacroFunctionalInput',SourceDomain='source',DestinationDomain='destination');rows.append(row)
    current['DataScopes']=rows
    value={'ByPhysicalPin':{'CLMS_4_5/WE':{'Passed':True,'CompleteFunctionalSupportIdentical':True,
        'NativeModeClockAndPolarityIdentical':True,'AllOriginalFunctionalEndpointMatrixObligationsRetained':True,
        'EquivalentCanonicalEndpoints':ends,'EquivalentFunctionalEndpoints':ends,'NativeTimingAliases':names}}}
    monkeypatch.setattr(p,'supplemental_reviews',lambda s:(value,{},{}));return current


def test_native_only_RAM_arc_maps_only_to_proven_equivalent_original_functional_matrix(macro):
    index=p.timing_endpoint_index(macro)
    assert index['macro/D/WE']['Endpoint']=='macro/A/WE'
    lookup=p.canonical_scope_lookup(macro,macro['DataScopes']);assert len(lookup)==1
    r=next(iter(lookup.values()));assert len(r['OriginalScopeObligations'])==3
    assert [x['Endpoint']for x in r['OriginalScopeObligations']]==['macro/A/WE','macro/B/WE','macro/C/WE']


@pytest.mark.parametrize('change',['budget','role','domain','source','missing_original','mixed_reset_partition'])
def test_shared_RAM_WE_never_merges_incompatible_scope_obligations(macro,change):
    r=macro['DataScopes'][1]
    if change=='budget':r['MaximumNS']+=1
    elif change=='role':r['Role']='another_role'
    elif change=='domain':r['DestinationDomain']='another_clock'
    elif change=='source':r['NativeObjects']['SourceFFs']=['another/FF']
    elif change=='missing_original':macro['DataScopes'].pop()
    else:
        macro['DataScopes'].remove(r);macro['UserSynchronousResetScopes']=[r]
    with pytest.raises(ValueError):p.timing_endpoint_aliases(macro)
