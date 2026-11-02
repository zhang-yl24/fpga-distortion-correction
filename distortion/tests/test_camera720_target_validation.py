"""Fixed-target pose metrics and strict provenance, without physical claims."""
import copy
import json
from pathlib import Path
import sys

import cv2
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools import camera720_target_validation as target
from tools import camera720_geometry_transfer as transfer
from test_camera720_geometry_transfer import profile, manifest as pair_manifest, capture_fixture


def points(index=0):
    world=transfer.board_points(pair_manifest()['board'])
    k=np.array([[2,0,0],[0,2,-120],[0,0,1]])@np.asarray(profile()['K'])
    r=np.array([.10+index*.11,-.20+index*.07,.05-index*.04])
    t=np.array([-70.+index*35,-95.+index*12,350.+index*40])
    return cv2.fisheye.projectPoints(world,r,t,k,np.asarray(profile()['D']))[0].reshape(-1,2)


def frozen():
    candidate=transfer.candidate(profile(),[[2,0,0],[0,2,-120],[0,0,1]],pair_manifest()['target_identity'])
    evidence=lambda h:{'image':{'sha256':h},'raw_sha256':h}
    return {'schema':target.FREEZE_SCHEMA,'image_size':[1280,720],
        'target_identity':candidate['target_identity'],'candidate_parameters':candidate['candidate_parameters'],
        'board':pair_manifest()['board'],'fixed_diagnostic_thresholds':{'rms_px':.5,'maximum_px':1.5},
        'source_profile_training_image_sha256':['4'*64],
        'fit_exclusions':[{'pose_id':'fit-pose','source':evidence('1'*64),'target':evidence('2'*64),'target_corners':points(0).tolist()}],
        'known_transfer_held_out':[{'pose_id':'known-pose','target':evidence('3'*64)}]}


def manifest(origin='new_target_held_out'):
    f=frozen()
    return {'schema':target.MANIFEST_SCHEMA,'image_size':f['image_size'],'target_identity':f['target_identity'],
        'board':f['board'],'candidate_unchanged_since_freeze_declared':True,
        'thresholds':copy.deepcopy(f['fixed_diagnostic_thresholds']),'thresholds_predeclared':True,
        'views':[{'view_id':'v1','pose_id':'new-pose' if origin=='new_target_held_out' else 'known-pose',
            'origin':origin,'split':'held_out','not_used_to_fit_or_choose_candidate_declared':True,
            'sha256':'5'*64 if origin=='new_target_held_out' else '3'*64}]}


def observation(m=None,xy=None):
    m=manifest() if m is None else m
    return [{'view_id':m['views'][0]['view_id'],'image_sha256':m['views'][0]['sha256'],
             'corners':points(1) if xy is None else xy}]


def test_one_heldout_pose_is_reported_without_fabricated_quota_or_acceptance(monkeypatch):
    def forbidden(*args,**kwargs):raise AssertionError('unbounded inverse or intrinsic fit called')
    monkeypatch.setattr(cv2.fisheye,'undistortPoints',forbidden)
    monkeypatch.setattr(cv2.fisheye,'calibrate',forbidden)
    f=frozen();original=copy.deepcopy(f)
    result=target.evaluate_observations(f,manifest(),observation())
    assert f==original and result['candidate_parameters']==f['candidate_parameters']
    assert result['observed_view_count']==result['observed_new_target_held_out_count']==1
    assert result['numeric_observed_views_passed'] and result['maximum_corner_error_px']<1e-6
    assert result['coverage_passed'] is None and result['sample_count_acceptance_rule'] is None
    assert sum(map(sum,result['target_corner_coverage_3x3']))==54
    assert result['pose_only_optimization'] and not result['intrinsics_refitted']
    for key in ('optical_calibration_accepted','hardware_release_allowed','image_pixel_orientation_verified',
                'physical_pose_identity_verified','fpga_mapping_verified','native_physical_observed_views_passed'):
        assert result[key] is False


def test_pose_error_matches_existing_vga_bounded_metric_and_retains_maximum():
    f=frozen();k,d,angle=target.model(f);xy=points(1)
    xy[3]+=[.4,-.3];world=transfer.board_points(f['board'])
    old,_=target.inverse.validate_pose(world,xy,k,d,angle)
    actual=target.pose_metrics(world,xy,k,d,angle)
    assert actual['rms_px']==pytest.approx(old,abs=1e-12)
    errors=np.array(actual['per_corner_error_px'])
    assert actual['maximum_px']==errors.max()
    assert actual['rms_px']==pytest.approx(np.sqrt(np.mean(errors**2)))
    assert 0<actual['maximum_model_ray_angle_deg']<angle


def test_bad_target_observation_fails_without_refitting_or_relaxing_budgets():
    f=frozen();m=manifest();xy=points(1);xy[9]+=[12,-8]
    r=target.evaluate_observations(f,m,observation(m,xy))
    assert not r['numeric_observed_views_passed']
    assert r['maximum_corner_error_px']>1.5
    assert r['candidate_parameters']==f['candidate_parameters'] and r['thresholds']==m['thresholds']


def test_wrong_fixed_distortion_cannot_be_hidden_by_pose_only_solve():
    f=frozen();k,d,angle=target.model(f);world=transfer.board_points(f['board'])
    xy=cv2.fisheye.projectPoints(world,np.array([.30,-.35,.10]),np.array([-60.,-100.,170.]),k,d)[0].reshape(-1,2)
    correct=target.evaluate_observations(f,manifest(),observation(xy=xy))
    assert correct['numeric_observed_views_passed'] and correct['maximum_corner_error_px']<1e-6
    wrong=copy.deepcopy(f);wrong['candidate_parameters']['D']=[0.,0.,0.,0.]
    changed=target.evaluate_observations(wrong,manifest(),observation(xy=xy))
    assert not changed['numeric_observed_views_passed'] and changed['maximum_corner_error_px']>3
    assert changed['candidate_parameters']['D']==[0.,0.,0.,0.]


@pytest.mark.parametrize('fault',['fit_pose','fit_hash','old_training_hash','wrong_split','missing_declaration',
    'changed_target','changed_board','widened_budget','nan_budget','unknown_origin','missing_predeclaration'])
def test_manifest_leakage_and_budget_changes_rejected(fault):
    f=frozen();m=manifest();v=m['views'][0]
    if fault=='fit_pose':v['pose_id']='fit-pose'
    elif fault=='fit_hash':v['sha256']='2'*64
    elif fault=='old_training_hash':v['sha256']='4'*64
    elif fault=='wrong_split':v['split']='fit'
    elif fault=='missing_declaration':v['not_used_to_fit_or_choose_candidate_declared']=False
    elif fault=='changed_target':m['target_identity']['capture_mode_id']='other'
    elif fault=='changed_board':m['board']['square_mm']=20
    elif fault=='widened_budget':m['thresholds']['maximum_px']=2
    elif fault=='nan_budget':m['thresholds']['rms_px']=float('nan')
    elif fault=='unknown_origin':v['origin']='unspecified'
    else:m['thresholds_predeclared']=False
    with pytest.raises(ValueError):target.evaluate_observations(f,m,observation(m))


@pytest.mark.parametrize('order',transfer.ORDERS)
def test_renaming_noisy_fit_pose_and_chessboard_order_does_not_make_heldout(order):
    m=manifest();xy=transfer.order_points(points(0),m['board'],order)+[.2,-.1]
    with pytest.raises(ValueError,match='repeat a fit pose'):
        target.evaluate_observations(frozen(),m,observation(m,xy))


def test_known_transfer_heldout_is_labeled_reuse_not_new_independent_capture():
    m=manifest('transfer_held_out');r=target.evaluate_observations(frozen(),m,observation(m))
    assert r['observed_transfer_held_out_count']==1 and r['observed_new_target_held_out_count']==0
    m['views'][0]['origin']='new_target_held_out'
    with pytest.raises(ValueError,match='relabeled new'):
        target.evaluate_observations(frozen(),m,observation(m))


@pytest.mark.parametrize('fault',['nan','outside','missing','line','duplicate_view','wrong_observation_hash'])
def test_bad_observations_not_silently_dropped(fault):
    m=manifest();o=observation(m)
    if fault=='nan':o[0]['corners'][0,0]=np.nan
    elif fault=='outside':o[0]['corners'][0,0]=1280
    elif fault=='missing':o[0]['corners']=o[0]['corners'][:-1]
    elif fault=='line':o[0]['corners'][:,0]=300
    elif fault=='duplicate_view':o.append(copy.deepcopy(o[0]))
    else:o[0]['image_sha256']='6'*64
    with pytest.raises(ValueError):target.evaluate_observations(frozen(),m,o)


def test_out_of_forward_domain_is_rejected_without_clipping():
    f=frozen();f['candidate_parameters']['maximum_ray_angle_deg']=10
    with pytest.raises(ValueError,match='outside declared forward inverse domain'):
        target.evaluate_observations(f,manifest(),observation())


def test_zero_views_has_explicit_zero_coverage_and_no_vacuous_pass():
    m=manifest();m['views']=[]
    r=target.evaluate_observations(frozen(),m,[])
    assert r['observed_view_count']==0 and r['mean_rms_px'] is None
    assert not r['numeric_observed_views_passed'] and sum(map(sum,r['target_corner_coverage_3x3']))==0


def test_predeclared_coverage_reports_unobserved_regions_without_invented_view_count():
    m=manifest();m['coverage_policy']={'required_cells':[[0,0],[1,1]],'minimum_corners_per_cell':1,'predeclared':True}
    r=target.evaluate_observations(frozen(),m,observation(m))
    assert r['numeric_observed_views_passed'] and r['coverage_passed'] is False
    assert {'cell':[0,0],'observed':0,'required':1} in r['missing_coverage']


@pytest.mark.parametrize('cells',[[1],[[0,0],[0,0]],[[0,3]]])
def test_invalid_coverage_is_value_error(cells):
    m=manifest();m['coverage_policy']={'required_cells':cells,'minimum_corners_per_cell':1,'predeclared':True}
    with pytest.raises(ValueError,match='coverage cells'):target.validate_manifest(frozen(),m)


def replay_report(tmp_path):
    m=capture_fixture(tmp_path);p=profile()
    profile_path=tmp_path/'profile.json';profile_path.write_text(json.dumps(p))
    manifest_path=tmp_path/'pairs.json';manifest_path.write_text(json.dumps(m))
    obs,evidence=transfer.load_observations(p,m,tmp_path)
    report=transfer.evaluate_observations(p,m,obs)
    report.update(pair_manifest=target.ref(manifest_path),capture_evidence=evidence,
        all_captures_recorded_physical=False,source_profile=target.ref(profile_path),tool=target.ref(transfer.__file__))
    path=tmp_path/'report.json';path.write_text(json.dumps(report))
    return path


def test_replayed_pairs_cannot_freeze_as_measured_physical_candidate(tmp_path):
    report=replay_report(tmp_path)
    with pytest.raises(ValueError,match='physical paired capture'):
        target.freeze_value(report)


def test_altered_saved_candidate_is_rejected_by_full_recomputation(tmp_path):
    path=replay_report(tmp_path);r=target.read(path);r['candidate_parameters']['K'][0][0]+=.01
    path.write_text(json.dumps(r))
    with pytest.raises(ValueError,match='differs from full paired-image recomputation'):
        target.freeze_value(path)


def test_partial_json_or_overwrite_never_replaces_diagnostic(tmp_path):
    p=tmp_path/'result.json'
    with pytest.raises(ValueError):target.save(p,{'bad':float('inf')})
    assert not p.exists()
    target.save(p,{'ok':True});old=p.read_bytes()
    with pytest.raises(ValueError,match='fresh output'):target.save(p,{'ok':False})
    assert p.read_bytes()==old


def native_record_fixture(tmp_path):
    # These are synthetic checkerboard pixels and synthetic metadata records
    # in pytest's temporary directory, never real board measurements. Exercise
    # the recorded-physical provenance branch without claiming independent ID.
    report_path=replay_report(tmp_path);old=target.read(report_path)
    pair_path=Path(old['pair_manifest']['path']);pairs=target.read(pair_path)
    for row in pairs['pairs']:
        for side in ('source','target'):
            view=row[side];meta_path=tmp_path/view['metadata_path'];meta=target.read(meta_path)
            meta.update(source_kind='physical_native_camera',hardware_accessed=True,
                upstream_raw_contract_hash_bound=True,upstream_payload_role='native_raw',
                build_binding={'raw_capture_contract':{'protocol':'PGFRAME1','payload_role':'native_raw',
                    'geometry_applied':False,'image_size':[meta['width'],meta['height']]}})
            meta_path.write_text(json.dumps(meta));view['metadata_sha256']=target.sha(meta_path)
    pair_path.write_text(json.dumps(pairs))
    obs,evidence=transfer.load_observations(profile(),pairs,tmp_path)
    report=transfer.evaluate_observations(profile(),pairs,obs)
    report.update(pair_manifest=target.ref(pair_path),capture_evidence=evidence,
        all_captures_recorded_physical=True,source_profile=old['source_profile'],tool=target.ref(transfer.__file__))
    report_path.write_text(json.dumps(report))
    f,_=target.freeze_value(report_path);freeze_path=tmp_path/'freeze.json';target.save(freeze_path,f)
    view=copy.deepcopy(pairs['pairs'][1]['target'])
    view.update(view_id='heldout',pose_id=pairs['pairs'][1]['pose_id'],origin='transfer_held_out',
        split='held_out',not_used_to_fit_or_choose_candidate_declared=True)
    budget_path=tmp_path/'predeclared-budget.json';budget_path.write_text(json.dumps({'thresholds':report['thresholds']}))
    m={'schema':target.MANIFEST_SCHEMA,'image_size':[1280,720],'target_identity':f['target_identity'],
        'board':f['board'],'candidate_freeze':target.ref(freeze_path),
        'candidate_unchanged_since_freeze_declared':True,'thresholds':report['thresholds'],
        'thresholds_predeclared':True,'threshold_declaration':target.ref(budget_path),'views':[view]}
    manifest_path=tmp_path/'target-manifest.json';manifest_path.write_text(json.dumps(m))
    return freeze_path,manifest_path


def test_native_record_validation_and_pure_verify_recompute_full_pixels(tmp_path):
    freeze_path,manifest_path=native_record_fixture(tmp_path)
    original={p:target.sha(p) for p in (freeze_path,manifest_path)}
    result,watched=target.audit_value(freeze_path,manifest_path)
    assert result['observed_view_count']==result['physical_capture_record_count']==1
    assert result['observed_transfer_held_out_count']==1 and result['observed_new_target_held_out_count']==0
    assert result['all_views_recorded_physical'] and not result['physical_pose_identity_verified']
    assert result['observation_source']=='hash_bound_native_rgb565_captures'
    assert not result['optical_calibration_accepted'] and not result['hardware_accessed']
    output=tmp_path/'validation.json';target.save(output,result)
    actual,recomputed=target.verify(output)
    assert actual==result and all(recomputed[p]==h for p,h in watched.items())
    assert all(target.sha(p)==h for p,h in original.items())
    tampered=target.read(output);tampered['observed_view_count']=7
    output.write_text(json.dumps(tampered))
    with pytest.raises(ValueError,match='differs from full native-image recomputation'):target.verify(output)


def test_mutating_frozen_intrinsics_cannot_bypass_source_recomputation(tmp_path):
    path,_=native_record_fixture(tmp_path);value=target.read(path)
    value['candidate_parameters']['K'][0][0]+=.1;path.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='freeze differs from recomputed'):target.bind_freeze(path)


def test_budget_binding_does_not_accept_a_different_threshold_document(tmp_path):
    f,m=native_record_fixture(tmp_path);value=target.read(m)
    p=Path(value['threshold_declaration']['path']);p.write_text(json.dumps({'thresholds':{'rms_px':1,'maximum_px':3}}))
    value['threshold_declaration']=target.ref(p);m.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='threshold declaration differs'):target.audit_value(f,m)


def test_reencoded_known_raw_cannot_be_called_a_new_target_holdout(tmp_path):
    f,m=native_record_fixture(tmp_path);value=target.read(m);view=value['views'][0]
    # Preserve frozen original image/metadata. Re-encode identical raw pixels
    # to new PNG/metadata files, change both the pose and declared view origin.
    meta=target.read(tmp_path/view['metadata_path']);image=cv2.imread(str(tmp_path/view['path']))
    png=tmp_path/'new-encoding.png';png.write_bytes(cv2.imencode('.png',image,[cv2.IMWRITE_PNG_COMPRESSION,9])[1].tobytes())
    meta['image_path']=png.name;meta['image_sha256']=target.sha(png)
    meta_path=tmp_path/'new-metadata.json';meta_path.write_text(json.dumps(meta))
    view.update(path=png.name,sha256=target.sha(png),metadata_path=meta_path.name,
        metadata_sha256=target.sha(meta_path),pose_id='renamed-pose',origin='new_target_held_out')
    m.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='known transfer raw content'):target.audit_value(f,m)
