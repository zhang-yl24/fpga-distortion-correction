"""New C profile, OpenCV reference, exact bypass and bounded table contract."""
from pathlib import Path
import re
import sys
import numpy as np
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import generate_hdmi_fisheye_profile as p
import run_hdmi_camera_fisheye_mapper_sim as sim


def test_all_1080_coordinates_match_independent_opencv_fisheye_map():
    value=p.metrics()
    assert value['Passed']and value['NativeCoordinatesChecked']==2073600
    assert value['ArithmeticMaskedCoordinates']==0
    assert value['FixedVsOpenCVMaxNativePixels']<.125
    assert value['FixedVsOpenCVMaxNativePixels']<.007
    assert value['MaximumNormalizedR2']>5


def test_preview_projection_uses_exact_half_pixel_native_transform():
    c,k,d,out=p.read_calibration();small=np.asarray(c['preview']['new_K_snapshot'])
    assert out[0,0]==2*small[0,0]and out[1,1]==2*small[1,1]
    assert out[0,2]==2*small[0,2]+.5 and out[1,2]==2*small[1,2]+.5
    assert len(d)==4 and c['source_fit']['path'].endswith('new-lens-calibration-c.json')


def test_generated_header_and_every_signed_rom_segment_equal_bound_C_model():
    cfg=p.config();assert (p.ROOT/p.PROFILE_HEADER).read_bytes()==p.header_bytes(cfg)
    actual=(p.ROOT/p.TABLE_HEADER).read_bytes();assert actual==p.table_bytes(cfg)
    rows=re.findall(rb"10'd(\d+): fisheye_radial_pair=64'h([0-9a-f]{16});",actual)
    assert len(rows)==1024
    nodes=cfg['LUTQ30']
    for number,word in rows:
        i=int(number);packed=int(word,16);delta=packed>>32
        if delta&(1<<31):delta-=1<<32
        assert packed&0xffffffff==int(nodes[i])and delta==int(nodes[i+1]-nodes[i])
    assert nodes[0]==1<<30 and np.all(np.diff(nodes)<0)


def test_identity_is_exact_for_signed_fractional_negative_and_extreme_coordinates():
    rng=np.random.default_rng(72);u=rng.integers(-(1<<23),1<<23,10000);v=rng.integers(-(1<<23),1<<23,10000)
    x,y,b=p.fixed_map(u,v,False)
    assert np.array_equal(x,u)and np.array_equal(y,v)and not b.any()
    x,y,b=p.fixed_map(u,v,False,in_black=True)
    assert b.all()and np.all(x==-(1<<23))and np.all(y==-(1<<23))


def test_new_fisheye_does_not_inherit_brown_plus_minus_two_crop():
    cfg=p.config();c=cfg['Constants'];nx=(1919*256-c['OUT_CX'])*c['INV_FX']/2**16/2**22
    assert nx>2
    x,y,b=p.fixed_map(1919*256,0,config=cfg)
    assert not b and x>0 and y>0


def test_outside_declared_radius_is_masked_and_centre_is_well_defined():
    cfg=p.config();c=cfg['Constants'];x,y,b=p.fixed_map(c['OUT_CX'],c['OUT_CY'],config=cfg)
    assert not b and int(x)==c['SRC_CX']and int(y)==c['SRC_CY']
    x,y,b=p.fixed_map((1<<23)-1,-(1<<23),config=cfg)
    assert b and int(x)==int(y)==-(1<<23)


@pytest.mark.parametrize('width,height',[(32,16),(1920,1080),(640,360)])
def test_small_and_native_geometry_share_pixel_centre_resized_profile(width,height):
    cfg=p.config(width=width,height=height);base=p.config()['Constants'];c=cfg['Constants']
    assert c['OUT_CX']==((base['OUT_CX']+128)*width+960)//1920-128
    assert c['OUT_CY']==((base['OUT_CY']+128)*height+540)//1080-128
    assert np.array_equal(cfg['LUTQ30'],p.config()['LUTQ30'])


@pytest.mark.parametrize('width,height',[(0,1080),(1920,0),(True,16),(8193,16)])
def test_unbounded_or_invalid_geometry_is_rejected(width,height):
    with pytest.raises(ValueError):p.config(width=width,height=height)


def test_ties_round_toward_positive_infinity_for_positive_and_negative_values():
    assert p.round_shift(np.array([-384,-128,128,384]),8).tolist()==[-1,0,1,2]


def test_rtl_compilation_explicitly_binds_both_profile_headers_and_real_multiplier():
    assert sim.HEADERS==(p.PROFILE_HEADER,p.TABLE_HEADER)
    assert 'rtl/mul32_pipe.v'in sim.COMPILE
    assert 'rtl/experimental/hdmi_camera_fisheye_mapper.v'in sim.COMPILE


@pytest.mark.parametrize('change',['none','short','no_config','notII1','fatal'])
def test_log_coverage_requires_full_pixel_count_stalls_config_drain_and_II1(change):
    text='FISHEYE_MAPPER_PASS native=1 corrected=2073600 identity=4096 domain=1024 matched=2078720 stalls=200 stable_holds=200 rejected_busy_configs=2 longest_input_run=64 enabled_latency=23\n'
    if change=='short':text=text.replace('2073600','512')
    elif change=='no_config':text=text.replace('rejected_busy_configs=2','rejected_busy_configs=0')
    elif change=='notII1':text=text.replace('longest_input_run=64','longest_input_run=1')
    elif change=='fatal':text+='Fatal: data changed\n'
    if change=='none':assert sim.validate_log('native',text)['InitiationInterval']==1
    else:
        with pytest.raises(ValueError):sim.validate_log('native',text)
