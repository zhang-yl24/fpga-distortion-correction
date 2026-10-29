"""Synthetic graph fixtures only; no fixture establishes a real FPGA implementation."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import audit_checked_io_netlist as tool


def instance(typ, name, ports, params=None):
    parameters='' if params is None else '#('+','.join('.'+p+'('+n+')' for p,n in params.items())+') '
    return typ+' '+parameters+chr(92)+name+' ('+','.join('.'+p+'('+n+')' for p,n in ports.items())+');\n'


def synthetic_text():
    text='// Synthetic CPU fixture only. 2023.2-SP3<build 154097>\n'
    text+='module board1080_top(hd_scl,hd_sda,clk,reset);\n'
    text+='inout hd_scl; inout hd_sda; input clk; input reset;\n'
    for bus in ('scl','sda'):
        pad='hd_'+bus
        text+=instance('V_IBUF',bus+'_ibuf',{'O':bus+'_read','I':pad})
        text+=instance('V_BUF',bus+'_read_buf',{'Z':bus+'_input','I':bus+'_read'})
        for role,d in (('meta',bus+'_input'),('sampled',bus+'_meta_q'),('low',"1'b0")):
            text+=instance('V_FFASYN','hdmi_configuration/driver/'+bus+'_'+role+'/opit_0/FF',
                {'Q':bus+'_'+role+'_q','D':d,'CK':'clk','CE':"1'b1",'SR':'reset'},
                {'SET_RESET':'"RESET"' if role=='low' else '"SET"','LRS_EN':'"TRUE"',
                 'INIT':"1'b0" if role=='low' else "1'b1"})
        text+=instance('V_INV',bus+'_invert',{'Z':bus+'_disable','I':bus+'_low_q'})
        text+=instance('V_BUF',bus+'_data_buf',{'Z':bus+'_zero','I':"1'b0"})
        text+=instance('V_OBUFT',bus+'_obuf',{'O':pad,'I':bus+'_zero','T':bus+'_disable'})
    return text+'endmodule\n'


@pytest.fixture
def synthetic(tmp_path,monkeypatch):
    library=tmp_path/'synthetic-library';library.mkdir()
    definitions={
        'V_IBUF':'output O,input I', 'V_OBUFT':'output O,input I,input T',
        'V_BUF':'output Z,input I','V_INV':'output Z,input I',
        'V_FFASYN':'output Q,input D,input CK,input CE,input SR',
        'V_UNKNOWN':'output O,input I',
        'V_LUT6CARRY':'output COUT,Z,Z5,input CIN,I0,I1,I2,I3,I4,I5'}
    for name,ports in definitions.items():
        (library/(name+'.v')).write_text('// Synthetic interface only\nmodule '+name+'('+ports+');endmodule\n')
    # CPU fixture substitutes the exact bound primitive fixtures, never native evidence.
    monkeypatch.setattr(tool,'SEMANTICS_SHA256',
                        {n:tool.sha(library/(n+'.v')) for n in definitions})
    netlist=tmp_path/'synthetic.v';netlist.write_text(synthetic_text())
    return netlist,library


def test_graph_traces_real_edges_without_approving_provenance(synthetic):
    result=tool.analyze(*synthetic)
    assert result['NativeConnectivityVerified'] is True
    assert result['ParsedCells']==16
    for bus in ('scl','sda'):
        row=result['Buses']['hd_'+bus]
        assert row['MetaFF'].endswith('/'+bus+'_meta/opit_0/FF')
        assert row['NativeQToDisableTruthTable']==[1,0]
        assert row['OutputDataConstant']==0
        assert row['NativeControlRegisterPolarityRelativeToRTLVerified'] is False
    assert result['ExportADFProvenanceVerified'] is False
    assert result['PhysicalImplementationAccepted'] is False
    assert result['HardwareReleaseAllowed'] is False


@pytest.mark.parametrize('mutation',['readback','bypass_meta','output_one','stuck_enable','wrong_low',
    'duplicate_driver','wrong_clock','gated_meta','source_output','unknown_cell','combinational_assign',
    'duplicate_cell','comment_only','buffer_cycle','truncated','bad_version'])
def test_wrong_connections_fail_even_when_expected_register_names_exist(synthetic,mutation):
    path,library=synthetic;text=path.read_text()
    if mutation=='readback':text=text.replace('.I(hd_scl)','.I(hd_sda)',1)
    elif mutation=='bypass_meta':text=text.replace('.D(scl_meta_q)','.D(scl_input)')
    elif mutation=='output_one':text=text.replace('.Z(scl_zero),.I(1\x27b0)', '.Z(scl_zero),.I(1\x27b1)')
    elif mutation=='stuck_enable':text=text.replace('.T(scl_disable)',".T(1'b0)")
    elif mutation=='wrong_low':text=text.replace('.I(scl_low_q)','.I(sda_low_q)')
    elif mutation=='duplicate_driver':text=text.replace('endmodule',instance('V_BUF','extra',{'Z':'scl_input','I':'sda_read'})+'endmodule')
    elif mutation=='wrong_clock':text=text.replace('.D(scl_meta_q),.CK(clk)','.D(scl_meta_q),.CK(reset)')
    elif mutation=='gated_meta':text=text.replace('.CE(1\x27b1)', '.CE(1\x27b0)',1)
    elif mutation=='source_output':text=text.replace('inout hd_scl','output hd_scl')
    elif mutation=='unknown_cell':text=text.replace('V_IBUF','V_UNKNOWN',1)
    elif mutation=='combinational_assign':text=text.replace('endmodule','assign scl_input=scl_read; endmodule')
    elif mutation=='duplicate_cell':text=text.replace('sda_ibuf','scl_ibuf')
    elif mutation=='comment_only':text=text.replace('V_IBUF '+chr(92)+'scl_ibuf','// V_IBUF '+chr(92)+'scl_ibuf')
    elif mutation=='buffer_cycle':text=text.replace('.Z(scl_input),.I(scl_read)','.Z(scl_input),.I(scl_input)')
    elif mutation=='truncated':text=text.replace('endmodule','')
    else:text=text.replace('build 154097','build 1')
    path.write_text(text)
    with pytest.raises(ValueError):tool.analyze(path,library)


def test_native_control_inversion_is_required(synthetic):
    path,library=synthetic
    path.write_text(path.read_text().replace('.T(scl_disable)','.T(scl_low_q)'))
    with pytest.raises(ValueError,match='inverse low FF Q'):tool.analyze(path,library)


def test_distinct_escaped_scalar_and_vector_bit_are_not_conflated():
    assert tool.scalar(chr(92)+'foo[0] ')==chr(92)+'foo[0]'
    assert tool.scalar(chr(92)+'foo [0]')==chr(92)+'foo::[0]'
    assert tool.scalar('foo[0]')=='foo[0]'


def test_existing_output_is_never_overwritten(synthetic,tmp_path):
    path,_=synthetic;out=tmp_path/'existing.json';out.write_text('preserve')
    with pytest.raises(ValueError,match='new'):
        tool.main(['--netlist',str(path),'--output',str(out)])
    assert out.read_text()=='preserve'


def test_changed_primitive_model_rejected(synthetic):
    path,library=synthetic
    model=library/'V_OBUFT.v'
    model.write_text(model.read_text()+'// Synthetic modification\n')
    with pytest.raises(ValueError,match='semantics changed'):tool.analyze(path,library)


def packed_luts(text):
    for bus in ('scl','sda'):
        text=text.replace('driver/'+bus+'_sampled/opit_0/FF','driver/'+bus+'_meta/opit_0/FFAPP/FF')
        inverter=instance('V_INV',bus+'_invert',{'Z':bus+'_disable','I':bus+'_low_q'})
        text=text.replace(inverter,'')
        buffer=instance('V_BUF',bus+'_data_buf',{'Z':bus+'_zero','I':"1'b0"})
        zero=instance('V_LUT6CARRY',bus+'_GND',
            {'COUT':'','Z':bus+'_zero','Z5':'','CIN':"1'b0",**{'I'+str(i):"1'b1" for i in range(6)}},
            {'INIT':"64'h0000000000000000",'I5_TO_CARRY':'"TRUE"','I5_TO_LUT':'"TRUE"'})
        text=text.replace(buffer,zero)
    shared=instance('V_LUT6CARRY','shared_control',
        {'COUT':'','Z':'sda_disable','Z5':'scl_disable','CIN':"1'b0",'I0':"1'b1",'I1':"1'b1",'I2':"1'b1",
         'I3':'sda_low_q','I4':'scl_low_q','I5':"1'b1"},
        {'INIT':"64'h00FF00FF0000FFFF",'I5_TO_CARRY':'"TRUE"','I5_TO_LUT':'"TRUE"'})
    return text.replace('endmodule',shared+'endmodule')


def test_packed_synchronizers_and_dual_output_lut_are_connected(synthetic):
    path,library=synthetic;path.write_text(packed_luts(path.read_text()))
    result=tool.analyze(path,library)
    assert result['Buses']['hd_scl']['SampledFF'].endswith('/scl_meta/opit_0/FFAPP/FF')
    assert len(result['Buses']['hd_sda']['TristateControlTruthTable'])==4
    assert result['Buses']['hd_scl']['OutputDataTruthTable']==[{'Inputs':{},'Output':0}]


@pytest.mark.parametrize('mutation',['constant_one','wrong_shared_function','extra_dependency','wrong_select','reset_off'])
def test_native_lut_and_reset_variants_fail_closed(synthetic,mutation):
    path,library=synthetic;text=packed_luts(path.read_text())
    if mutation=='constant_one':text=text.replace("64'h0000000000000000","64'hFFFFFFFFFFFFFFFF",1)
    elif mutation=='wrong_shared_function':text=text.replace("64'h00FF00FF0000FFFF","64'h0000FFFF00FF00FF")
    elif mutation=='extra_dependency':text=text.replace("64'h00FF00FF0000FFFF","64'h00FF007F0000FFFF")
    elif mutation=='wrong_select':text=text.replace('.I5_TO_LUT("TRUE")','.I5_TO_LUT("FALSE")')
    else:text=text.replace('.LRS_EN("TRUE")','.LRS_EN("FALSE")',1)
    path.write_text(text)
    with pytest.raises(ValueError):tool.analyze(path,library)
