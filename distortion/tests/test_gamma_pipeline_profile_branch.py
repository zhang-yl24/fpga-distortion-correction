"""Synthetic JSON contract fixtures only; no lens fit/acceptance or hardware."""
from pathlib import Path
import hashlib
import json
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import prepare_gamma_pipeline_d5 as prepared
import run_gamma_pipeline_d5_sim as simulation


@pytest.fixture
def inputs(tmp_path):
    profile={"model":"fisheye","provenance":"real_chessboard_captures","image_size":[640,480],
             "K":[[400,0,319.5],[0,400,239.5],[0,0,1]],"D":[0,0,0,0],
             "passed":True,"candidate_ready_for_profile_review":True,"independent_spatial_coverage_passed":True,
             "camera_id":"UNIT-CONTRACT-CAM","lens_id":"UNIT-CONTRACT-LENS","profile_id":"UNIT-CONTRACT-PROFILE",
             "capture_mode_id":"UNIT-CONTRACT-MODE","unit_test_fixture_not_real_lens":True}
    audit={"passed":True,"candidate_ready_for_profile_review":True,"synthetic_input":False,
           "provenance":"real_chessboard_captures","sample_stride":1,"full_requested_frames_checked":True,
           "source_image_size":[640,480],"output_size":[640,480],"camera_id":profile["camera_id"],"profile_id":profile["profile_id"],
           "existing_board_radius_guard_applied":False,"criteria":{"maximum_coordinate_error_px":.25},
           "integer_config":[81792,61312,81792,61312,102400,102400,2684355,2684355,0,0,0,0,0],
           "required_radius_guard_q22_for_checked_rays":4000002,
           "frames":[{"angle_deg":a,"coordinates_checked":307200,"numerical_gates_passed":True,
                      "fixed_point_invalid_coordinates":0,"fixed_point_folded_samples":0,"reference_folded_samples":0,
                      "maximum_normalized_radius_squared_q22":4000000} for a in range(0,360,30)]}
    p,a=tmp_path/"profile.json",tmp_path/"audit.json"
    def write():
        p.write_text(json.dumps(profile));audit["source_profile_file_sha256"]=prepared.sha(p)
        audit["profile_sha256"]=hashlib.sha256(json.dumps(profile,sort_keys=True,allow_nan=False).encode()).hexdigest()
        a.write_text(json.dumps(audit));return p,a
    return profile,audit,write


def test_integer_header_and_new_guard_are_bound(inputs):
    profile,audit,write=inputs;p,a=write();headers,binding=prepared.real_parameters(p,a)
    assert b"CAL_INV_FX" in headers[prepared.CALIBRATION]
    assert b"4000002" in headers[prepared.ROTATION_DOMAIN] and b"1976439" not in headers[prepared.ROTATION_DOMAIN]
    assert binding["HardwareReleaseAllowed"] is False and binding["CalibrationAccepted"] is True
    assert binding["DevelopmentOnly"] is False


def test_incomplete_fit_needs_explicit_development_both_sides(inputs):
    profile,audit,write=inputs
    profile.update(passed=False,candidate_ready_for_profile_review=False,independent_spatial_coverage_passed=False)
    p,a=write()
    with pytest.raises(ValueError):prepared.real_parameters(p,a)
    with pytest.raises(ValueError):prepared.real_parameters(p,a,True)
    profile["development_only"]=True
    audit.update(candidate_ready_for_profile_review=False,source_profile_development_only=True)
    p,a=write()
    with pytest.raises(ValueError):prepared.real_parameters(p,a)
    headers,binding=prepared.real_parameters(p,a,True)
    assert binding["DevelopmentOnly"] is True and binding["CalibrationAccepted"] is False
    assert binding["HardwareReleaseAllowed"] is False and b"DEVELOPMENT ONLY" in headers[prepared.CALIBRATION]
    assert binding["ParameterOrigin"].startswith("actual_data_exploratory_")


def test_development_numeric_pass_cannot_claim_profile_ready(inputs):
    profile,audit,write=inputs
    profile["development_only"]=True
    audit["source_profile_development_only"]=True
    p,a=write()
    with pytest.raises(ValueError):prepared.real_parameters(p,a)
    with pytest.raises(ValueError):prepared.real_parameters(p,a,True)


@pytest.mark.parametrize("fault",["synthetic","sampled","angle","loose","oldguard","overflow","tangential"])
def test_wrong_model_scope_or_mapping_cannot_stage(inputs,fault):
    profile,audit,write=inputs
    if fault=="synthetic":profile["provenance"]="synthetic"
    if fault=="sampled":audit["sample_stride"]=8
    if fault=="angle":audit["frames"].pop()
    if fault=="loose":audit["criteria"]["maximum_coordinate_error_px"]=2.
    if fault=="oldguard":audit["required_radius_guard_q22_for_checked_rays"]=1976439
    if fault=="overflow":audit["integer_config"][0]=1<<23
    if fault=="tangential":audit["integer_config"][-1]=1
    p,a=write()
    with pytest.raises(ValueError):prepared.real_parameters(p,a)


def test_profile_file_sha_change_rejected(inputs):
    profile,audit,write=inputs;p,a=write();profile["D"][3]=.01;p.write_text(json.dumps(profile))
    with pytest.raises(ValueError):prepared.real_parameters(p,a)


def test_bars_never_generate_real_native_golden(inputs,tmp_path):
    profile,audit,write=inputs;p,a=write()
    meta=tmp_path/"bars.json";meta.write_text(json.dumps({"calibration_scene_eligible":False}))
    with pytest.raises(ValueError,match="internal bars"):
        simulation.real_native_oracle(tmp_path,{"Profile":str(p)},[meta])
    assert not (tmp_path/"source.mem").exists()
