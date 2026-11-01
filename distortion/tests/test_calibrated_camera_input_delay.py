"""Synthetic native graph positives and bypass/clock/parameter negatives."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import audit_calibrated_camera_input_delay as audit


def fixture():
    cells={}
    for i in range(8):
        cells[f'ib{i}']={'Primitive':'V_IBUF','Parameters':{'IOSTANDARD':'"LVCMOS33"','TERM_DDR':'"ON"'},'Ports':{'I':f'cam_data[{i}]','O':f'b{i}'}}
        cells[f'camera_data_delay/data_bit[{i}].input_delay']={'Primitive':'V_ZEROHOLDDELAY','Parameters':{'ZHOLD_SET':'"1500ps"'},'Ports':{'DI':f'b{i}','DO':f'd{i}'}}
        for j in range(i+1):
            cells[audit.cdc.CAP+f'capture{i}_{j}']={'Primitive':'V_FFSYN','Parameters':{},'Ports':{'D':f'd{i}','CK':'cam_pclk','Q':f'q{i}_{j}'}}
    return cells


def graph(cells):return audit.cdc.Graph({'Cells':cells,'FFPlacement':{},'ModuleDeclarations':'module camera_vga_calibrated_top; endmodule'})


def test_varying_fanout_is_enumerated_not_historical_count():
    result=audit.audit(graph(fixture()))
    assert result['Passed'] and result['UniqueFirstSequentialSinkCount']==36
    assert [len(r['FirstSequentialSinks']) for r in result['Bits']]==list(range(1,9))
    assert not result['ExternalACTimingAccepted']


def test_combinational_capture_fanout():
    c=fixture();sink=audit.cdc.CAP+'capture0_0';c[sink]['Ports']['D']='after_buffer'
    c[audit.cdc.CAP+'buffer']={'Primitive':'V_BUF','Parameters':{},'Ports':{'I':'d0','Z':'after_buffer'}}
    result=audit.audit(graph(c))
    assert result['Bits'][0]['CombinationalFanoutCells']==[audit.cdc.CAP+'buffer']


@pytest.mark.parametrize('case',['pad_bypass','buffer_bypass','wrong_clock','control_pin','wrong_delay','wrong_electrical','expression','foreign_sink','output_driver'])
def test_rejects_unsafe_native_graph(case):
    c=fixture();sink=c[audit.cdc.CAP+'capture0_0']
    if case=='pad_bypass':sink['Ports']['D']='cam_data[0]'
    elif case=='buffer_bypass':sink['Ports']['D']='b0'
    elif case=='wrong_clock':sink['Ports']['CK']='clk_27m'
    elif case=='control_pin':sink['Ports']['SR']=sink['Ports'].pop('D')
    elif case=='wrong_delay':c['camera_data_delay/data_bit[0].input_delay']['Parameters']['ZHOLD_SET']='"0ps"'
    elif case=='wrong_electrical':c['ib0']['Parameters']['TERM_DDR']='"OFF"'
    elif case=='expression':sink['Ports']['D']='{d0,d1}'
    elif case=='foreign_sink':c['other/capture']=c.pop(audit.cdc.CAP+'capture0_0')
    else:sink['Ports']['Q']='d0'
    with pytest.raises(ValueError):audit.audit(graph(c))


def drm_fixture():
    c=fixture();name=audit.cdc.CAP+'pixels/memory_3/gopdrm_36k/DRM36K'
    bits=["1'b0"]*36
    for i in range(8):bits[27+i]=f'd{i}'
    c[name]={'Primitive':'V_DRM36K_E1','Parameters':dict(audit.DRM_PARAMETERS),
             'Ports':{'DIB':'{'+', '.join(reversed(bits))+'}',
                      'CLKA':'cam_pclk','CLKB':'clk_27m'}}
    return c,name,bits


def test_sdp64_dib_bits_use_write_clock_a_and_keep_ff_sinks():
    c,name,_=drm_fixture();result=audit.audit(graph(c))
    assert result['UniqueFFSinkCount']==36 and result['UniqueDRMDataBitSinkCount']==8
    assert result['UniqueFirstSequentialSinkCount']==44
    for bit,row in enumerate(result['Bits']):
        sink=next(s for s in row['FirstSequentialSinks'] if s['Primitive']=='V_DRM36K_E1')
        assert sink=={'Cell':name,'Pin':f'DIB[{27+bit}]','Primitive':'V_DRM36K_E1',
                      'Clock':'camera_pclk','ClockPin':'CLKA','SamplingEdge':'rising'}


@pytest.mark.parametrize('case',['pad_bypass','buffer_bypass','wrong_write_clock','wrong_mode','wrong_width',
    'ecc','cascade','control_pin','foreign_sink','parity_bit','wrong_concat_width','nested_concat',
    'expression','whole_bus','bit_range','second_output_driver'])
def test_rejects_unproved_memory_fanout(case):
    c,name,bits=drm_fixture();cell=c[name]
    if case=='pad_bypass':bits[27]='cam_data[0]'
    elif case=='buffer_bypass':bits[27]='b0'
    elif case=='wrong_write_clock':cell['Ports']['CLKA']='clk_27m'
    elif case=='wrong_mode':cell['Parameters']['RAM_MODE']='"TRUE_DUAL_PORT"'
    elif case=='wrong_width':cell['Parameters']['DATA_WIDTH_A']='32'
    elif case=='ecc':cell['Parameters']['ECC_WRITE_EN']='"TRUE"'
    elif case=='cascade':cell['Parameters']['RAM_CASCADE']='"UPPER"'
    elif case=='control_pin':cell['Ports']['WEA']='d0'
    elif case=='foreign_sink':c['other/memory']=c.pop(name)
    elif case=='parity_bit':bits[35],bits[27]=bits[27],bits[35]
    elif case=='wrong_concat_width':bits.pop(0)
    elif case=='nested_concat':bits[27]='{d0}'
    elif case=='expression':bits[27]='d0 ^ d1'
    elif case=='whole_bus':bits[27]='cam_data'
    elif case=='bit_range':bits[27]='cam_data[1:0]'
    elif case=='second_output_driver':cell['Ports']['DOB']='d0'
    cell['Ports']['DIB']='{'+', '.join(reversed(bits))+'}'
    with pytest.raises(ValueError):audit.audit(graph(c))


def test_explicit_unused_lut_output_is_recorded_and_not_a_sequential_sink():
    c=fixture();name=audit.cdc.CAP+'lut'
    c[name]={'Primitive':'V_LUT6CARRY','Parameters':{},
             'Ports':{'I0':'d0','Z':'used','Z5':'unused'}}
    c[audit.cdc.CAP+'capture0_0']['Ports']['D']='used'
    result=audit.audit(graph(c));assert result['UniqueFirstSequentialSinkCount']==36
    assert result['Bits'][0]['UnusedCombinationalOutputs']==[{'Cell':name,'Pin':'Z5','Net':'unused'}]


def test_expression_on_downstream_net_cannot_hide_a_bypass():
    c=fixture();name=audit.cdc.CAP+'buffer'
    c[name]={'Primitive':'V_BUF','Parameters':{},'Ports':{'I':'d0','Z':'later'}}
    c[audit.cdc.CAP+'capture0_0']['Ports']['D']='later ^ d1'
    with pytest.raises(ValueError):audit.audit(graph(c))
