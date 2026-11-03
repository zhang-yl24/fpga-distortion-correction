"""Exact source-counter and finite diagnostic semantics for new fisheye build."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import hdmi_camera_fisheye_tile8_warnings as w


@pytest.mark.parametrize('name',list(w.PUBLIC))
def test_all_current_readable_counter_assignments_guards_and_uses_are_bound(name):
    spec=w.PUBLIC[name];text=(w.build.ROOT/spec['Source']).read_text(encoding='utf-8-sig')
    assert w.counter_contract(text,name)['GuardedIncrementVerified']is True
    with pytest.raises(ValueError):w.counter_contract(text+f'\nwire extra=({name}==0);\n',name)
    guard=text.replace(name+'<',name+'<=',1)if name!='watchdog'else text.replace('watchdog>=TIMEOUT_CYCLES-1','watchdog>TIMEOUT_CYCLES-1')
    with pytest.raises(ValueError):w.counter_contract(guard,name)


def test_unsigned_range_induction_compares_every_reachable_state():
    value=w.enumerate_bound(31,8,5)
    assert value['ReachableMaximum']==31 and value['AllReachableUnsignedValuesEqualAtBothWidths']is True
    with pytest.raises(ValueError):w.enumerate_bound(32,8,5)


@pytest.mark.parametrize('body',[
    "W: Adm-4021: The attribute 'PAP_IO_LOC' of object 'system/example' is overwritten by new value.",
    "W: Public-4008: Instance 'unknown_path/rgb[0]' of 'GTP_DFF_RE' unit is dangling and will be cleaned.",
    'W: New-9999: unexplained functional issue',
    'W: Verilog-2021: unbound source net is not driven'])
def test_unknown_warning_attribute_or_foreign_hierarchy_is_rejected(body):
    with pytest.raises(ValueError):w.body_class(body)


def test_mapper_identity_cleanup_is_a_coordinate_constant_not_pixel_metadata():
    value=w.body_class("W: Public-4008: Instance 'system/bank_core/engine/core/mapper/identity_x[3][7]' of 'bmsWIDEDFFCPE' unit is dangling and will be cleaned.")
    assert value=='BoundedIntegerRasterCoordinateIdentityPipelineConstantBit'
    value=w.body_class("W: Public-4008: Instance 'system/core_reset_sync[1:0]' of 'bmsWIDEDFFCPE' unit is dangling and will be cleaned.")
    assert value=='DuplicateLocalReleaseChainCurrentNativeGuardAliasProofRequired'


def test_official_vendor_range_is_explicitly_limited_not_fabricated_decryption():
    assert w.VENDOR_BASIS=='unchanged official vendor IP and compiler optimization, diagnostic SRAM experiment'
    assert len(w.REDUCTIONS)==5 and len(w.PUBLIC)==3


@pytest.mark.parametrize('bit',range(24))
def test_elastic_buffer_cleanup_accepts_exactly_eight_rgb565_quantization_bits(bit):
    body=f"W: Public-4008: Instance 'system/bank_core/engine/buffer_rgb[{bit}]' of 'bmsWIDEDFFRSE' unit is dangling and will be cleaned."
    if bit in (0,1,2,8,9,16,17,18):
        assert w.body_class(body)=='ExactElasticBufferEightRGB565QuantizationLSBs'
    else:
        with pytest.raises(ValueError,match='retained RGB565'):w.body_class(body)


def test_elastic_buffer_source_consumer_and_quantization_are_bound():
    engine=(w.build.ROOT/'rtl/experimental/hdmi_camera_fisheye_engine_tile8.v').read_text(encoding='utf-8-sig')
    writer=(w.build.ROOT/'rtl/experimental/ddr_adaptive_result_writer_dualstripe.v').read_text(encoding='utf-8-sig')
    proof=w.rgb565_buffer_contract(engine,writer)
    assert proof['ElasticBufferUnusedInputBits']==[0,1,2,8,9,16,17,18]
    assert proof['RemovedBitsClassifiedAsMetadata']is False
    with pytest.raises(ValueError):w.rgb565_buffer_contract(engine,writer.replace('in_rgb[23:19]','in_rgb[22:18]'))
    with pytest.raises(ValueError):w.rgb565_buffer_contract(engine+'\nwire observation=buffer_rgb[0];',writer)
    with pytest.raises(ValueError):w.rgb565_buffer_contract(engine.replace('result_rgb;','result_rgb^24\'d1;'),writer)
