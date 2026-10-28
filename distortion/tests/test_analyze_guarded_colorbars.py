from pathlib import Path
import copy
import json
import sys
import zlib
import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import analyze_guarded_colorbars as analyzer


def bars():
    words = np.array([0xffff,0xffe0,0x07ff,0x07e0,0xf81f,0xf800,0x001f,0], dtype=np.uint16)
    return np.broadcast_to(np.repeat(words,80), (480,640)).copy()


def test_standard_pattern_and_mirrored_sequence_pass_without_optical_claims():
    for words in (bars(), bars()[:,::-1].copy()):
        result = analyzer.compare(words)
        assert result['digital_pattern_check_passed']
        assert result['byte_order_color_sequence_verified']
        assert not result['optical_color_accuracy_verified'] and not result['lens_calibration_eligible']
        assert not result['all_electrical_lanes_individually_proven']


def test_byte_order_swap_does_not_pass_as_native_rgb565():
    result = analyzer.compare(bars().byteswap())
    assert not result['digital_pattern_check_passed']
    assert result['swapped_byte_order_counterexample']['palette_order_and_levels_accepted']


def test_historical_d5_drop_is_caught_even_within_loose_level_policy():
    dropped = bars() & np.uint16(~((1 << 5) | (1 << 13)) & 0xffff)
    result = analyzer.compare(dropped)
    assert result['normal']['palette_order_and_levels_accepted']
    assert result['normal']['historical_d5_both_byte_bits_constant_zero_signature']
    assert not result['digital_pattern_check_passed']


def test_both_d5_byte_positions_stuck_high_also_fail_despite_40_code_levels():
    result = analyzer.compare(bars() | np.uint16((1 << 5) | (1 << 13)))
    assert result['normal']['palette_order_and_levels_accepted']
    assert result['normal']['d5_both_byte_bits_constant_one_signature']
    assert not result['digital_pattern_check_passed']


def test_sample_only_patches_never_claim_full_frame_pattern_shape():
    pixels = np.zeros((480,640), dtype=np.uint16)
    reference = bars()
    for x in range(40,640,80):
        pixels[120:360,x-12:x+12] = reference[120:360,x-12:x+12]
    result = analyzer.compare(pixels)
    assert result['digital_pattern_check_passed']  # The stated central median diagnostic only.
    assert result['sampled_palette_pixel_fraction'] == .15
    assert not result['full_frame_pattern_shape_verified']


@pytest.mark.parametrize('words', [np.zeros((480,640),dtype=np.uint16),
                                  np.full((480,640),0x20,dtype=np.uint16),
                                  np.full((480,640),0xffff,dtype=np.uint16)])
def test_dark_or_uniform_scene_is_not_a_colorbar_acceptance(words):
    assert not analyzer.compare(words)['digital_pattern_check_passed']


def test_rgb_channel_swap_is_rejected():
    words = bars()
    swapped = ((words & 0xf800) >> 11) | (words & 0x07e0) | ((words & 0x001f) << 11)
    assert not analyzer.compare(swapped)['digital_pattern_check_passed']


def test_native_size_and_word_type_are_required():
    for pixels in (bars()[:479], bars().astype(np.uint32), np.zeros((480,640,3),dtype=np.uint8)):
        with pytest.raises(ValueError):
            analyzer.compare(pixels)


def historical_code_words():
    # Reproduce the observed code levels without loading private physical data.
    rgb = np.array([[255,255,255],[255,255,99],[82,255,222],[66,255,33],
                    [189,0,222],[173,8,33],[0,4,156],[0,4,0]],dtype=np.uint16)
    words = ((rgb[:,0]>>3)<<11) | ((rgb[:,1]>>2)<<5) | (rgb[:,2]>>3)
    return np.broadcast_to(np.repeat(words,80),(480,640)).copy()


def test_historical_exact_compatibility_never_bypasses_original_40_code_policy():
    pixels = historical_code_words()
    result = analyzer.compare(pixels)
    assert result['central_color_sequence_matches_standard']
    assert result['byte_order_color_sequence_verified']
    assert not result['central_code_levels_meet_40_policy']
    assert max(result['normal']['max_channel_code_distance_to_ideal_per_bar']) == 99
    assert not result['digital_pattern_check_passed']
    compatibility = analyzer.compare_historical(pixels, pixels.copy())
    assert compatibility['exact_word_match'] and compatibility['equal_words'] == 307200
    assert not compatibility['affects_40_code_acceptance'] and not compatibility['optical_acceptance']
    pixels[0,0] ^= np.uint16(1)
    assert not analyzer.compare_historical(pixels, historical_code_words())['exact_word_match']


@pytest.mark.parametrize('blue_code,accepted', [(4,True),(5,False)])
def test_original_40_code_threshold_is_fixed_at_rgb565_quantization_boundary(blue_code,accepted):
    assert analyzer.MAX_CHANNEL_DISTANCE == 40
    pixels=bars()
    pixels[:,80:160]=(pixels[:,80:160] & np.uint16(0xffe0)) | np.uint16(blue_code)
    result=analyzer.compare(pixels)
    assert result['central_code_levels_meet_40_policy'] is accepted
    assert result['digital_pattern_check_passed'] is accepted


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    """Synthetic files matching actual host metadata shape, never live evidence."""
    monkeypatch.setattr(analyzer, 'ROOT', tmp_path)
    raw, png, meta, manifest, bit, source, summary, historical = [tmp_path/name for name in
        ('frame.rgb565','frame.png','frame.json','validated-build.json','candidate.sbit','source.v','summary.json','historical.npy')]
    pixels = bars()
    raw.write_bytes(pixels.astype('<u2').tobytes())
    # Known ideal palette encodes the native RGB565 primary colors exactly.
    rgb = np.broadcast_to(np.repeat(analyzer.PALETTE.astype(np.uint8),80,axis=0)[None,:,:],(480,640,3)).copy()
    ok, encoded = cv2.imencode('.png',rgb[:,:,::-1]);assert ok;png.write_bytes(encoded.tobytes())
    bit.write_bytes(b'SYNTHETIC_NOT_A_REAL_BITSTREAM');source.write_text('synthetic test source\n')
    np.save(historical, pixels)
    context = {'source_kind':'physical_sensor_internal_test_pattern',
        'input_origin':analyzer.SENSOR_OUTPUT_CONTRACT['input_origin'],
        'sensor_output_contract':copy.deepcopy(analyzer.SENSOR_OUTPUT_CONTRACT),
        'calibration_scene_eligible':False,'lens_optical_acceptance_eligible':False,
        'guarded_target':analyzer.TARGET,'guarded_build_tag':analyzer.BUILD_TAG,'guarded_mode':'sensor-internal-bars'}
    m = {'Target':analyzer.TARGET,'SensorOutputContract':copy.deepcopy(analyzer.SENSOR_OUTPUT_CONTRACT),
         'RawCaptureContract':copy.deepcopy(analyzer.RAW_CONTRACT),'GuardedControlContract':{'build_tag':analyzer.BUILD_TAG},
         'Bitstream':str(bit),'SHA256':analyzer.sha(bit),'SourceSHA256':{'source.v':analyzer.sha(source)}}
    metadata = {**context,'raw_path':str(raw),'image_path':str(png),'raw_sha256':analyzer.sha(raw),'image_sha256':analyzer.sha(png),
        'width':640,'height':480,'pixel_format':'RGB565_LE','payload_bytes':614400,'frame_id':1,
        'source_crc32':f'{zlib.crc32(raw.read_bytes()):08X}','received_crc32':f'{zlib.crc32(raw.read_bytes()):08X}',
        'geometry_applied':False,'geometry_applied_by_receiver':False,'photometric_processing_applied_by_receiver':False,
        'upstream_raw_contract_hash_bound':True,'upstream_payload_role':'native_raw',
        'build_binding':{'validated_build':str(manifest),'validated_build_sha256':'',
                         'bitstream_sha256':analyzer.sha(bit),'raw_capture_contract':copy.deepcopy(analyzer.RAW_CONTRACT),'bound_source_count':1}}
    s = {**context,'passed':True,'saved_frames':1,'frames':[{'metadata_path':str(meta),'metadata_sha256':''}]}
    def save():
        manifest.write_text(json.dumps(m),encoding='utf-8')
        metadata['build_binding']['validated_build_sha256']=analyzer.sha(manifest)
        meta.write_text(json.dumps(metadata),encoding='utf-8')
        s['frames'][0]['metadata_sha256']=analyzer.sha(meta)
        summary.write_text(json.dumps(s),encoding='utf-8')
    save()
    return {'summary':summary,'metadata':metadata,'manifest':m,'state':s,'save':save,'raw':raw,'png':png,'historical':historical}


def test_actual_metadata_field_shape_and_full_png_payload_chain(bundle):
    result = analyzer.analyze_summary(bundle['summary'], historical_path=bundle['historical'])
    assert result['digital_pattern_checks_passed'] and result['historical_digital_compatibility_observed']
    assert result['hardware_accessed_by_analyzer'] is False
    assert result['physical_programming_event_verified_by_analyzer'] is False
    assert result['calibration_scene_eligible'] is False


@pytest.mark.parametrize('key,value', [('pixel_format','RGB565_BE'),('received_crc32','00000000'),
    ('source_crc32',123),('geometry_applied',True),('geometry_applied_by_receiver',True),
    ('photometric_processing_applied_by_receiver',True),('upstream_raw_contract_hash_bound',False),
    ('upstream_payload_role','corrected'),('guarded_build_tag',0x52473201),('guarded_mode','native'),
    ('source_kind','offline_uart_replay'),('calibration_scene_eligible',True),('lens_optical_acceptance_eligible',True)])
def test_metadata_role_format_and_native_contract_cannot_be_relabelled(bundle,key,value):
    bundle['metadata'][key]=value;bundle['save']()
    with pytest.raises(ValueError):analyzer.analyze_summary(bundle['summary'])


@pytest.mark.parametrize('change', [
    lambda b:b['state'].update(saved_frames=2),
    lambda b:b['state'].update(passed=1),
    lambda b:b['state'].update(guarded_target='raw_camera_capture_cam2_guarded'),
    lambda b:b['manifest'].update(SourceSHA256={}),
    lambda b:b['manifest']['RawCaptureContract'].update(geometry_applied=True),
    lambda b:b['manifest']['GuardedControlContract'].update(build_tag=0x52473201),
    lambda b:b['metadata']['build_binding'].update(bitstream_sha256='0'*64),
    lambda b:b['metadata']['build_binding'].update(bound_source_count=107),
    lambda b:b['metadata']['build_binding']['raw_capture_contract'].update(payload_role='unknown'),
])
def test_summary_and_hash_bound_build_contract_must_agree(bundle,change):
    change(bundle);bundle['save']()
    with pytest.raises(ValueError):analyzer.analyze_summary(bundle['summary'])


def test_png_with_updated_sha_still_must_equal_every_raw_pixel(bundle):
    image=cv2.imread(str(bundle['png']));image[0,0]=0
    ok,encoded=cv2.imencode('.png',image);assert ok;bundle['png'].write_bytes(encoded.tobytes())
    bundle['metadata']['image_sha256']=analyzer.sha(bundle['png']);bundle['save']()
    with pytest.raises(ValueError,match='PNG differs'):analyzer.analyze_summary(bundle['summary'])
