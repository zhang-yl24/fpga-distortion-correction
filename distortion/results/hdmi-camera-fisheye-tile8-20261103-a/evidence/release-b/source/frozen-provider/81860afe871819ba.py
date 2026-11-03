"""Typed native cuts never turn unknown circuitry into primary inputs."""
import copy
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import hdmi_camera_fisheye_tile8_audit as a


def graph(cells,ports=None):
    models={kind:{'Ports':directions,'Reference':{'Path':kind+'.v','SHA256':'model-bound'}}for kind,directions in {
        'V_FFSYN':{'Q':'OUTPUT','D':'INPUT','CK':'INPUT','CE':'INPUT','SR':'INPUT'},
        'V_APM_E2':{'P':'OUTPUT','X':'INPUT','CLK':'INPUT'},
        'V_RAM32X2':{'RDO':'OUTPUT','RADDR':'INPUT','WCLK':'INPUT'},
        'V_MUX2':{'Z':'OUTPUT','I0':'INPUT','I1':'INPUT','SEL':'INPUT'},
        'V_LUT6CARRY':{**{f'I{i}':'INPUT'for i in range(6)},'CIN':'INPUT','Z':'OUTPUT','Z5':'OUTPUT','COUT':'OUTPUT'},
        }.items()}
    clocks={'core':{'Generated':False,'Target':'core','Name':'core','PeriodNS':8.,'Master':'core'}}
    return a.Graph({'Cells':cells,'FFPlacement':{}},ports or{},clocks,models)


def ff(q):
    return {'Primitive':'V_FFSYN','Parameters':{'LRS_EN':'"TRUE"','SET_RESET':'"RESET"','INIT':"1'b0"},
        'Ports':{'Q':q,'D':"1'b0",'CE':"1'b1",'SR':"1'b0",'CK':'core'}}


def test_dsp_bypass_is_typed_macro_not_foreign_ff_or_primary_fallback():
    g=graph({'s':ff('source'),
        'dsp':{'Primitive':'V_APM_E2','Parameters':{'P_REG':'0'},
            'Ports':{'P':'product','X':'source','CLK':'core'}}})
    assert g.support('product')=={'macro:dsp/P'}
    assert g.expression('product')==('variable','macro:dsp/P')
    assert g.support('source')=={'ff:s'}


def test_asynchronous_lutram_keeps_read_address_dependency():
    g=graph({'address':ff('address_q'),
        'ram':{'Primitive':'V_RAM32X2','Parameters':{},
            'Ports':{'RDO':'data','RADDR':'address_q','WCLK':'core'}}})
    assert g.support('data')=={'macro:ram/RDO','ff:address'}


def test_unknown_internal_net_is_rejected():
    g=graph({'s':ff('source')})
    with pytest.raises(ValueError,match='undriven internal'):g.support('missing')
    with pytest.raises(ValueError,match='unknown Boolean'):g.expression('missing')


def test_only_declared_primary_input_can_be_external_leaf():
    g=graph({},ports={'pad':'INPUT'})
    assert g.support('pad')=={'primary:pad'}
    assert g.expression('pad')==('variable','primary:pad')


def test_mux_tied_select_does_not_follow_unconnected_input():
    g=graph({'s':ff('source'),'mux':{'Primitive':'V_MUX2','Parameters':{},
        'Ports':{'I0':'source','I1':'undriven_inactive','SEL':"1'b0",'Z':'selected'}}})
    assert g.support('selected')=={'ff:s'}
    assert g.expression('selected')==('variable','ff:s')


def test_lut_unused_empty_carry_pin_is_not_a_fake_boolean_leaf():
    g=graph({'s':ff('source'),'lut':{'Primitive':'V_LUT6CARRY',
        'Parameters':{'INIT':"64'hAAAAAAAAAAAAAAAA",'I5_TO_LUT':'"FALSE"'},
        'Ports':{'I0':'source',**{f'I{i}':"1'b0"for i in range(1,6)},'CIN':'','Z':'copy','Z5':'','COUT':''}}})
    assert g.support('copy')=={'ff:s'}
    expr=g.expression('copy')
    for bit in (0,1):assert a.boolean.boolean.evaluate(expr,{'ff:s':bit})==bit


def test_source_partition_is_not_native_acceptance():
    plan=a.build.WORK/'build-a/plan.json'
    if not plan.is_file():pytest.skip('current independent fisheye plan absent')
    value,watched=a.source_inventory(plan)
    assert value['ExactSourceRoleCoverage']is True
    assert value['NativeEvidenceComplete']is False
    assert value['SourceBytesAloneClaimNativeSafety']is False
    assert len(value['Sources'])==len(a.read(plan)['SourceFiles'])
    assert len({r['Source']for r in value['Sources']})==len(value['Sources'])
    assert all(r['Compiled']['Path']in{str(p)for p in watched}for r in value['Sources'])


def test_actual_source_partition_binds_both_fill8r2_replacements_and_no_frozen_cache():
    value,watched=a.source_inventory(a.build.WORK/'build-a/plan.json')
    byname={r['Source']:r for r in value['Sources']}
    for name in ('ddr_neighbour_cache_scatter16_rowpipe_fill8r3.v','ddr_remap_sample_scatter16_rowpipe.v','ddr_read_arbiter_fill8r2.v'):
        source='rtl/experimental/'+name;row=byname[source]
        assert row['Role']=='explicit_design'
        assert row['Original']['SHA256']==a.sha(a.build.ROOT/source)
        assert row['Compiled']['SHA256']==a.sha(row['Compiled']['Path'])
        assert row['Compiled']['Path']in{str(p)for p in watched}
    assert 'rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v'not in byname
    assert 'rtl/experimental/ddr_remap_sample_scatter4_rowpipe.v'not in byname
    assert 'rtl/ddr_read_arbiter.v'not in byname
    assert 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe.v'not in byname


def test_functional_adapter_changes_only_this_design_module_token():
    with pytest.raises(ValueError,match='one actual flat'):
        a.functional('module another_top;endmodule\n')


@pytest.mark.parametrize('value',['plain_net','path/a[31]','path/a[2]/b[10]',
    '{a[3:0],b,c[0:2]}',"{1'b0,1'b1,data[7:0]}"])
def test_new_scalar_lexer_agrees_with_old_valid_scalar_language(value):
    assert a.atoms(value)==a.typed.atoms(value)


def test_multiline_long_native_bus_preserves_all_tokens():
    name='system/bank_core/engine/buffer_rgb_with_native_packed_suffix_'+'x'*1000
    value='{'+name+'[3],\n   '+name+'[2],\r\n\t'+name+'[1], '+name+'[0]}'
    assert a.atoms(value)==[name+f'[{i}]'for i in range(3,-1,-1)]


def test_actual_b_escaped_scalar_with_nonterminal_range_spelling():
    name='hdmi_configuration/tx_controller/dri_cnt[4:0]_4'
    assert a.atoms('\\'+name+' ')==[name]


def test_invalid_long_scalar_fails_without_exponential_backtracking():
    started=time.monotonic()
    with pytest.raises(ValueError,match='unsupported scalar'):
        a.atoms('system/'+'identifier_'*5000+'@')
    assert time.monotonic()-started<1


def alias_mapper(native_init=None,native_input='source',invert_input=False):
    cells={'source/FF0/FF':ff('source'),'p/FYA/LUT6CARRY':{
        'Primitive':'V_LUT6CARRY','Parameters':{'INIT':"64'hAAAAAAAAAAAAAAAA",'I5_TO_LUT':'"TRUE"'},
        'Ports':{'Z':'internal','Z5':'','COUT':'','CIN':"1'b0",'I0':'source',
            **{f'I{i}':"1'b0"for i in range(1,6)}}}}
    if invert_input:
        cells['inv/FYA/LUT6CARRY']={'Primitive':'V_LUT6CARRY',
            'Parameters':{'INIT':"64'h5555555555555555",'I5_TO_LUT':'"TRUE"'},
            'Ports':{'Z':'native_not_source','Z5':'','COUT':'','CIN':"1'b0",'I0':'source',
                **{f'I{i}':"1'b0"for i in range(1,6)}}}
    g=graph(cells);init=native_init or '1010'*16
    route={'Pins':{('p','I0'):native_input,('p','L6'):'renamed',**{('p',f'I{i}'):"1'b0"for i in range(1,6)}},
        'Instances':{'p':{'Cell':'lut'}},'Cells':{'lut':{'Operator':'gopLUT6',
            'Ports':{'L6':'OUTPUT',**{f'I{i}':'INPUT'for i in range(6)}},
            'Parameters':[['PARAMETER','INIT',['DATATYPE','BITVEC'],['BITVEC',['B','64','"'+init+'"']]]]}}}
    return a.Mapper(g,route,{'p/FYA/LUT6CARRY':{'Site':'SITE','Attributes':'(* PAP_BLE_DEF="A" *)'}})


def test_combinational_alias_uses_actual_owner_init_and_input_bindings():
    m=alias_mapper()
    assert m.native_functional_net('renamed')=='internal'
    assert m.signal_alias('internal','renamed')['BooleanCofactorVerified']is True
    assert m.alias_proofs['renamed']['NativeDriver']=='p/L6'


def test_combinational_alias_rejects_changed_native_function():
    m=alias_mapper(native_init='0'*64)
    with pytest.raises(ValueError,match='INIT'):m.native_functional_net('renamed')


def test_alias_cannot_be_inferred_from_an_unbound_native_signal():
    m=alias_mapper(native_input='missing')
    with pytest.raises(ValueError,match='actual output owner'):m.native_functional_net('renamed')


def test_native_lut_input_inversion_is_composed_with_its_actual_init():
    m=alias_mapper(native_init='0101'*16,native_input='native_not_source',invert_input=True)
    assert m.native_functional_net('renamed')=='internal'
    assert m.alias_inversions['renamed']is False
    assert m.signal_alias('internal','renamed')['Inverted']is False


def test_native_lut_output_inversion_is_retained_for_write_enable_polarity():
    m=alias_mapper(native_input='native_not_source',invert_input=True)
    assert m.signal_alias('internal','renamed')['Inverted']is True
    native=m.native_expression('renamed')
    for bit in(0,1):
        assert a.boolean.boolean.evaluate(native,{'ff:source/FF0/FF':bit})==1-bit


def test_clock_source_proof_is_interned_without_an_endpoint_invariant():
    class G:pass
    g=G();scope={'FromCLK':'a/CLK','LaunchQ':'a/Q','Endpoint':'e0'}
    proof={'Verified':True,'PhysicalCLK':'SITE/CLK','CLKNet':'clock',
        'CompanionQLaunchesAdmitted':False,'LaunchQUnchanged':'a/Q','EndpointUnchanged':'e0','Parents':[]}
    first=a.compact_clock_proof(g,scope,['a/CLK'],proof)
    second=a.compact_clock_proof(g,{**scope,'Endpoint':'e1'},['a/CLK'],{**proof,'EndpointUnchanged':'e1'})
    assert first==second
    full=g.native_source_clock_proofs[first['SharedSourceClockProofKey']]
    assert 'EndpointUnchanged'not in full and 'Parents'not in first
    assert all(full[k]==v for k,v in first.items()if k!='SharedSourceClockProofKey')


def native_constant_mapper(bits='1'*64):
    route={'Pins':{('arbitrary_instance','Z'):'arbitrary_net'},
        'Instances':{'arbitrary_instance':{'Cell':'const'}},
        'Cells':{'const':{'Operator':'gopVCC','Ports':{'Z':'OUTPUT'},
            'Parameters':[['PARAMETER','INIT',['DATATYPE','BITVEC'],['BITVEC',['B','64','"'+bits+'"']]]]}}}
    return a.Mapper(graph({}),route,{})


def test_route_only_constant_is_bound_by_driver_and_init_without_a_name_guess():
    m=native_constant_mapper()
    assert m.native_functional_net('arbitrary_net')=="1'b1"
    assert m.alias_proofs['arbitrary_net']['NetNameUsedToInferValue']is False


def test_route_constant_with_changed_init_is_rejected():
    with pytest.raises(ValueError,match='INIT disagree'):
        native_constant_mapper('0'*64).native_functional_net('arbitrary_net')


def test_local_reset_forced_native_one_does_not_get_replaced_by_grs_zero():
    target=ff('target_q');target['Ports']['D']='reset_data'
    cells={'local':ff('local_q'),'data':ff('data_q'),'target':target,
        'guard':{'Primitive':'V_LUT6CARRY','Parameters':{'INIT':"64'hDDDDDDDDDDDDDDDD",'I5_TO_LUT':'"TRUE"'},
            'Ports':{'Z':'reset_data','Z5':'','COUT':'','CIN':"1'b0",'I0':'local_q','I1':'data_q',
                **{f'I{i}':"1'b0"for i in range(2,6)}}}}
    g=graph(cells)
    assert target['Parameters']['INIT']=="1'b0"
    assert a.next_q_possibilities(g,'target',{'ff:local':0})=={1}
    assert a.next_q_possibilities(g,'target',{'ff:local':1})=={0,1}


def test_native_sr_priority_is_preserved_even_with_ce_disabled():
    target=ff('q');target['Parameters'].update(SET_RESET='"SET"',INIT="1'b0")
    target['Ports'].update(SR='local_q',CE="1'b0",D="1'b0")
    g=graph({'local':ff('local_q'),'target':target})
    assert a.next_q_possibilities(g,'target',{'ff:local':1,'ff:target':0})=={1}
    assert a.next_q_possibilities(g,'target',{'ff:local':0,'ff:target':0})=={0}


@pytest.mark.parametrize('output,init,selector,expected',[('Z',"64'hFFFFFFFFAAAAAAAA","1'b1",1),
    ('Z5',"64'hAAAAAAAA00000000","1'b0",0),('COUT',"64'hAAAAAAAAFFFFFFFF","1'b0",0)])
def test_only_the_selected_lut_output_and_constant_branch_are_expanded(output,init,selector,expected):
    ports={p:''for p in ('Z','Z5','COUT')};ports[output]='result'
    g=graph({'lut':{'Primitive':'V_LUT6CARRY','Parameters':{'INIT':init,
            'I5_TO_LUT':'"TRUE"','I5_TO_CARRY':'"FALSE"'},
        'Ports':{**ports,'I0':'result',**{f'I{i}':"1'b0"for i in range(1,5)},
            'I5':selector,'CIN':"1'b0"}}})
    assert a.boolean.possible(g.expression('result'),{})=={expected}


def test_relevant_lut_cycle_is_still_rejected():
    g=graph({'lut':{'Primitive':'V_LUT6CARRY','Parameters':{
            'INIT':"64'hAAAAAAAAAAAAAAAA",'I5_TO_LUT':'"TRUE"'},
        'Ports':{'Z':'result','Z5':'','COUT':'','I0':'result',
            **{f'I{i}':"1'b0"for i in range(1,6)},'CIN':"1'b0"}}})
    with pytest.raises(ValueError,match='Boolean expression cycle'):
        g.expression('result')


def control_mapper():
    cells={'a/FF0/FF':ff('qa'),'b/FF1/FF':ff('qb')}
    for cell in cells.values():cell['Ports']['CE']='control'
    g=graph(cells,{'control':'INPUT','clear':'INPUT'})
    g.g['FFPlacement']={n:{'Site':'SITE','Attributes':'(* PAP_BLE_DEF="'+ble+'" *)'}for n,ble in zip(cells,'AB')}
    params=[['PARAMETER',k,['DATATYPE','STRING'],['STRING',v]]for k,v in {
        'LCE_POL':'"FALSE"','LCE_EN':'"TRUE"','CEMUX_SEL':'"LOCAL"'}.items()]
    route={'Pins':{('a','CE'):'control',('b','CE'):'control'},
        'Instances':{p:{'Cell':p}for p in('a','b')},'Cells':{p:{'Operator':'gopAQ','Ports':{'CE':'INPUT'},
            'Parameters':copy.deepcopy(params)}for p in('a','b')}}
    timing={'Report':{'Path':'baseline.rtr','SHA256':'bound'},'ByPhysicalPin':{('SITE','CE'):{'b/CE':{
        'Endpoint':'b/CE','PhysicalTimingPin':'SITE/CE','ObservedPaths':2,'Contexts':{}}}}}
    m=a.Mapper(g,route,{},timing)
    row={'Endpoint':'a/CE','FunctionalBoundaryNet':'control','NativeBoundaryNet':'control'}
    return m,row


def test_actual_report_canonical_control_keeps_the_complete_physical_ff_footprint():
    m,row=control_mapper();value=m.qualified_control_boundary('a/FF0/FF','CE',row)
    assert value['Endpoint']=='b/CE'and value['OriginalLogicalEndpoint']=='a/CE'
    assert value['OriginalPhysicalAlias']=='SITE/CE'
    proof=m.control_proofs[value['QualifiedTimingEndpointProofKey']]
    assert [r['FF']for r in proof['ControlledFFs']]==['a/FF0/FF','b/FF1/FF']
    assert proof['GetPinsExistenceAloneAccepted']is False
    assert proof['SourceSupportEqualityVerified']is True


def test_canonical_control_cannot_change_the_actual_connected_net():
    m,row=control_mapper();m.route['Pins']['b','CE']='other'
    with pytest.raises(ValueError,match='another actual net'):
        m.qualified_control_boundary('a/FF0/FF','CE',row)


def test_canonical_control_cannot_change_native_polarity_or_mux():
    m,row=control_mapper();m.route['Cells']['b']['Parameters'][0][3]=['STRING','"TRUE"']
    with pytest.raises(ValueError,match='different polarity/mux/mode'):
        m.qualified_control_boundary('a/FF0/FF','CE',row)


def test_canonical_control_cannot_use_a_reported_parent_at_another_site():
    m,row=control_mapper();m.g.g['FFPlacement']['b/FF1/FF']['Site']='ANOTHER'
    with pytest.raises(ValueError,match='actual physical site'):
        m.qualified_control_boundary('a/FF0/FF','CE',row)


def test_canonical_control_cannot_hide_another_ff_control_support():
    m,row=control_mapper();m.g.ports['other']='INPUT';m.g.ff['a/FF0/FF']['Ports']['CE']='other'
    with pytest.raises(ValueError,match='complete functional source support'):
        m.qualified_control_boundary('a/FF0/FF','CE',row)


def test_timing_control_reader_requires_the_matching_path_endpoint_and_location(tmp_path):
    path=tmp_path/'report.rtr'
    path.write_text('| Design : '+a.TARGET+'\nEndpoint : b/CE\nPath Type : max (slow corner)\n'
        ' CLMA_1_2/CE r another/CE\n CLMA_1_2/CE r b/CE\n')
    value=a.current_timing_control_endpoints(path)
    assert set(value['ByPhysicalPin'])=={('CLMA_1_2','CE')}
    assert value['ByPhysicalPin']['CLMA_1_2','CE']['b/CE']['ObservedPaths']==1


def test_qualified_matrix_does_not_require_unselected_neighbour_to_have_native_q():
    scope={'Role':'held','MaximumNS':8.,'SourceDomain':'a','DestinationDomain':'b',
        'LaunchQ':'source/Q','Endpoint':'sink/I0','FromCLKVariants':['source/CLK']}
    support={'sink/I0':{'SourceFFs':['foreign','local-neighbour'],
        'LaunchQs':['source/Q'],'SourceSupportComplete':True}}
    group=a.constraint_groups([scope],support)[0]
    assert group['FunctionalNativeSupportMatrixComplete']is True
    assert group['NativeSupportMatrixProof']['SupportedAxisPairs']==1


def test_qualified_matrix_rejects_an_extra_supported_axis_pair():
    scopes=[{'Role':'held','MaximumNS':8.,'SourceDomain':'a','DestinationDomain':'b',
        'LaunchQ':q,'Endpoint':end,'FromCLKVariants':[q+'/CLK']}for q,end in [('q0','e0'),('q1','e1')]]
    support={'e0':{'LaunchQs':['q0','q1']},'e1':{'LaunchQs':['q1']}}
    with pytest.raises(ValueError,match='outside this exact'):a.constraint_groups(scopes,support)
