"""Native-only aliases never invent functional RAMs or broaden support."""
import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path('D:\\GravityLRT\\thu\\semester_4.5\\FPGAchina\\fpga-distortion-correction\\distortion')/'tools'))
import hdmi_camera_fisheye_fill8r3s3_macro_we_aliases as m


def fixture():
    placements={p:{'Site':'CLMS_1_2','Implementation':'impl_'+p+'_S','LocationLine':i}
        for i,p in enumerate(('a','b','d'),1)}
    params={'CP_IMPL_LOC':'"NA"','MODE':'"RAM"','CLK_POL':'"FALSE"','WCK_SEL':'"LOCAL"',
        'RAM_MODE':'"LRAM"','RAM32_EN':'"TRUE"'}
    route={'Instances':{p:{'Cell':p,'Operator':'gopRAM32X2S'}for p in placements},
        'Cells':{},'Pins':{(p,pin):net for p in placements for pin,net in(('CLK','clock'),('WE','enable'))}}
    for p in placements:
        selected={**params,'CP_IMPL_LOC':'"D"'if p=='d'else'"NA"'}
        route['Cells'][p]={'Operator':'gopRAM32X2S','Ports':{'CLK':'INPUT','WE':'INPUT'},
            'Parameters':[['PARAMETER',k,['DATATYPE','STRING'],['STRING',v]]for k,v in selected.items()]}
    consumers=[];supports={}
    for p in ('a','b'):
        endpoint=p+'/WE';supports[endpoint]={'SourceFFs':['source','local'],
            'TypedBoundaryCuts':[],'SourceSupportComplete':True,'AllActualSourceFFsRetained':True}
        consumers.append({'Cell':p+'/FYA/RAM32X2','Primitive':'V_RAM32X2',
            'ClockBindings':[{'Pin':'WCLK','Domain':'pixel','Root':'pll/CLK','PeriodNS':13.,'Master':'board',
                'Trace':[{'Net':'clock'}]}],
            'NativeWEConnection':{'NativeWE':'enable','NativeInstance':route['Instances'][p],
                'NativeActiveWriteValue':1,'NativeInactiveValue':0}})
    timing={'CLMS_1_2':{p+'/WE':{'Endpoint':p+'/WE','PhysicalTimingPin':'CLMS_1_2/WE',
        'Contexts':{'max slow':{'DestinationClockDomain':'pixel'}}}for p in placements}}
    return consumers,route,placements,timing,supports


def prove(values):return m.prove_site('CLMS_1_2',*values)


def test_native_only_timing_alias_keeps_both_original_matrix_obligations():
    value=prove(fixture())
    assert value['Passed']is True
    assert value['EquivalentFunctionalEndpoints']==['a/WE','b/WE']
    assert value['NativeTimingAliases']==['a/WE','b/WE','d/WE']
    assert value['NativeTimingAliasEvidence'][2]['NativeOnlyImplementationAlias']is True
    assert value['NativeTimingAliasEvidence'][2]['FunctionalRAMInvented']is False
    assert value['RoleBudgetAndDomainEquivalenceStillRequiredForMatrixCanonicalization']is True


def test_native_only_alias_with_uninventoried_data_output_is_rejected():
    values=fixture();values[1]['Pins']['d','DOH']='business_data'
    with pytest.raises(ValueError,match='data consumers/inputs'):prove(values)


def test_native_only_alias_with_uninventoried_data_input_is_rejected():
    values=fixture();values[1]['Pins']['d','DIL']='business_data'
    with pytest.raises(ValueError,match='data consumers/inputs'):prove(values)


@pytest.mark.parametrize('pin',['WE','CLK'])
def test_different_actual_control_or_write_clock_net_is_rejected(pin):
    values=fixture();values[1]['Pins']['d',pin]='different'
    with pytest.raises(ValueError,match='another actual WE/WCLK'):prove(values)


def test_different_native_mode_is_rejected():
    values=fixture();values[1]['Cells']['d']['Parameters'][1][3]=['STRING','"LUT"']
    with pytest.raises(ValueError,match='native modes'):prove(values)


def test_different_complete_ff_support_is_rejected():
    values=fixture();values[4]['b/WE']['SourceFFs'].append('hidden_foreign')
    with pytest.raises(ValueError,match='different complete FF support'):prove(values)


def test_incomplete_support_inventory_is_rejected():
    values=fixture();values[4]['b/WE']['SourceSupportComplete']=False
    with pytest.raises(ValueError,match='complete original'):prove(values)


def test_different_typed_macro_cut_is_rejected():
    values=fixture();values[4]['b/WE']['TypedBoundaryCuts']=['macro:hidden/P']
    with pytest.raises(ValueError,match='typed boundary cuts'):prove(values)


def test_different_functional_clock_root_is_rejected():
    values=fixture();values[0][1]['ClockBindings'][0]['Root']='other_pll/CLK'
    with pytest.raises(ValueError,match='another clock root'):prove(values)


def test_functional_wclk_trace_must_bind_the_actual_native_clock_net():
    values=fixture();values[0][1]['ClockBindings'][0]['Trace'][0]['Net']='another'
    with pytest.raises(ValueError,match='actual functional WCLK trace'):prove(values)


def test_different_native_active_polarity_is_rejected():
    values=fixture();values[0][1]['NativeWEConnection'].update(NativeActiveWriteValue=0,NativeInactiveValue=1)
    with pytest.raises(ValueError,match='active polarity'):prove(values)


def test_actual_timing_alias_must_be_at_the_same_physical_site():
    values=fixture();values[3]['CLMS_1_2']['d/WE']['PhysicalTimingPin']='CLMS_3_4/WE'
    with pytest.raises(ValueError,match='actual physical site'):prove(values)


def test_actual_timing_capture_clock_must_match_functional_wclk():
    values=fixture();values[3]['CLMS_1_2']['d/WE']['Contexts']['max slow']['DestinationClockDomain']='core'
    with pytest.raises(ValueError,match='timing clock differs'):prove(values)


def test_an_unseen_native_alias_is_not_invented_from_a_parent_name():
    values=fixture();del values[3]['CLMS_1_2']['d/WE']
    assert prove(values)['NativeTimingAliases']==['a/WE','b/WE']


def test_readers_bind_native_primitive_and_matching_sta_physical_endpoint(tmp_path):
    route=tmp_path/'route'
    route.write_text('(INSTANCE arbitrary (VIEWREF OPER (CELLREF c (OPERAREF gopRAM32X2S (LIBRARYREF lib)))))\n'
        '(INSTANNOTATE (INSTREF arbitrary)\n (PLACE impl_D_S (DEVINSTREF CLMS (SITEREF 1 2)))\n')
    wanted,places=m.native_ram_placements(route)
    assert wanted=={'arbitrary'}and places['arbitrary']['Site']=='CLMS_1_2'
    report=tmp_path/'report'
    report.write_text('| Design : '+m.build.TARGET+'\nEndpoint : arbitrary/WE\nPath Group : pixel\nPath Type : max slow\n'
        ' CLMS_1_2/WE r other/WE\n CLMS_1_2/WE r arbitrary/WE\n')
    proof=m.timing_we_endpoints(report)
    assert list(proof['CLMS_1_2'])==['arbitrary/WE']


def test_proof_does_not_mutate_the_original_functional_matrix():
    values=fixture();before=copy.deepcopy(values);prove(values)
    assert values==before


def test_endpoint_selection_keeps_data_and_synchronous_reset_we_partitions():
    scope={'DataScopes':[{'Endpoint':'video/WE','TargetKind':'MacroFunctionalInput'},
        {'Endpoint':'normal/D','TargetKind':'ordinary'}],
        'UserSynchronousResetScopes':[{'Endpoint':'dma/WE','TargetKind':'MacroWriteEnableResetFunction'},
            {'Endpoint':'ff/D','TargetKind':'FFSynchronousResetFunction'}]}
    assert m.selected_functional_endpoints(scope)=={'video/WE','dma/WE'}


def test_endpoint_selection_rejects_other_functions_in_a_macro_we_role():
    with pytest.raises(ValueError,match='another native function'):
        m.selected_functional_endpoints({'DataScopes':[{'Endpoint':'video/CLK','TargetKind':'MacroFunctionalInput'}]})
