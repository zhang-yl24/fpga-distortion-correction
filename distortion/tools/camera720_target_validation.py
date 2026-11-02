"""Freeze a measured mode-transfer candidate; validate native target poses only.

No camera access, intrinsic refit, default sample quota or optical acceptance.
The fixed K/D are derived from a fully replayed paired transfer report.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools import camera720_geometry_transfer as transfer
from tools import calibrate_fisheye_profile as calibration
from tools import fisheye_forward_inverse as inverse
from tools.stereo_fisheye_calibrate import board_points

SELF=Path(__file__).resolve()
FREEZE_SCHEMA='camera720-fixed-target-candidate-freeze-v1'
MANIFEST_SCHEMA='camera720-fixed-target-validation-manifest-v1'
REPORT_SCHEMA='camera720-fixed-target-validation-report-v1'
NEAR_FIT_RMS_PX=2.0
require=transfer.require
cv2.setNumThreads(1)
cv2.ocl.setUseOpenCL(False)


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ref(path):return {'path':str(Path(path).resolve()),'sha256':sha(path)}


def bind(watched,path,expected=None):
    path=Path(path).resolve();require(path.is_file(),'missing bound input '+str(path))
    digest=sha(path);require(expected is None or digest==expected,'input hash mismatch '+str(path))
    require(str(path) not in watched or watched[str(path)]==digest,'conflicting input hash')
    watched[str(path)]=digest;return path


def tools(watched):
    for module in (sys.modules[__name__],transfer,calibration,inverse,
                   sys.modules[board_points.__module__]):bind(watched,module.__file__)


def unchanged(watched):
    require(all(sha(p)==h for p,h in watched.items()),'input changed during offline validation')


def save(path,value):
    path=Path(path).resolve();require(path.parent.is_dir() and not path.exists(),'fresh output in an existing directory required')
    payload=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    with path.open('x',encoding='utf-8',newline='\n') as stream:stream.write(payload)


def rebuild_transfer(report_path):
    watched={};report_path=bind(watched,report_path);saved=read(report_path)
    require(saved.get('schema')==transfer.SCHEMA and saved.get('method')=='fit_axis_aligned',
            'measured fitted mode-transfer report required')
    profile_path=bind(watched,saved['source_profile']['path'],saved['source_profile']['sha256'])
    pair_path=bind(watched,saved['pair_manifest']['path'],saved['pair_manifest']['sha256'])
    require(saved['tool']==ref(transfer.__file__),'transfer producer differs')
    profile,manifest=read(profile_path),read(pair_path)
    observed,evidence=transfer.load_observations(profile,manifest,pair_path.parent)
    actual=transfer.evaluate_observations(profile,manifest,observed)
    actual.update(pair_manifest=ref(pair_path),capture_evidence=evidence,
        all_captures_recorded_physical=all(e['physical_capture_record'] for e in evidence),
        source_profile=ref(profile_path),tool=ref(transfer.__file__))
    require(actual==saved,'saved transfer differs from full paired-image recomputation')
    require(actual['numeric_pair_checks_passed'] and actual['all_captures_recorded_physical'],
            'physical paired capture records and passing coordinate checks required; hypotheses/replays cannot freeze a measured candidate')
    for e in evidence:
        bind(watched,e['image']['path'],e['image']['sha256'])
        for prefix in ('metadata','raw'):bind(watched,e[prefix+'_path'],e[prefix+'_sha256'])
    tools(watched);unchanged(watched)
    return actual,manifest,observed,profile,watched


def freeze_value(report_path):
    report,manifest,observed,profile,watched=rebuild_transfer(report_path)
    lookup={r['pair_id']:r for r in observed};fit=[];known=[]
    evidence={(r['pair_id'],r['side']):r for r in report['capture_evidence']}
    for p in manifest['pairs']:
        row={'pair_id':p['pair_id'],'pose_id':p['pose_id'],
             'source':evidence[p['pair_id'],'source'],'target':evidence[p['pair_id'],'target'],
             'target_corners':np.asarray(lookup[p['pair_id']]['target']).tolist()}
        (fit if p['split']=='fit' else known).append(row)
    require(fit and known,'fit and held-out transfer provenance required')
    value={'schema':FREEZE_SCHEMA,'created_utc':datetime.now(timezone.utc).isoformat(),
        'transfer_report':ref(report_path),'target_identity':copy.deepcopy(report['target_identity']),
        'image_size':[1280,720],'board':copy.deepcopy(manifest['board']),
        'A_source_to_target':copy.deepcopy(report['A_source_to_target']),
        'candidate_parameters':copy.deepcopy(report['candidate_parameters']),
        'fixed_diagnostic_thresholds':copy.deepcopy(report['thresholds']),
        'fit_exclusions':fit,'known_transfer_held_out':known,
        'source_profile_training_image_sha256':profile.get('calibration_image_sha256',[]),
        'producer':ref(SELF),'input_sha256':watched,'intrinsics_refitted':False,
        'numeric_runtime':{'opencv':cv2.__version__,'numpy':np.__version__},
        'image_pixel_orientation_verified':False,'physical_pose_identity_verified':False,
        'optical_calibration_accepted':False,'hardware_release_allowed':False,'hardware_accessed':False,
        'limits':'Frozen measured coordinate-transfer candidate, not an accepted optical profile. Source camera/lens and physical pose remain operator declarations. Known transfer-heldout images are explicitly identified when reused for target checks.'}
    return value,watched


def bind_freeze(path):
    watched={};path=bind(watched,path);saved=read(path)
    require(saved.get('schema')==FREEZE_SCHEMA and saved.get('producer')==ref(SELF),'wrong or changed freeze producer')
    for p,h in saved['input_sha256'].items():bind(watched,p,h)
    bind(watched,saved['transfer_report']['path'],saved['transfer_report']['sha256'])
    actual,recomputed=freeze_value(saved['transfer_report']['path'])
    clean=lambda v:{k:x for k,x in v.items() if k!='created_utc'}
    require(clean(actual)==clean(saved),'freeze differs from recomputed measured transfer')
    watched.update(recomputed);return saved,watched


def model(frozen):
    require(frozen.get('schema')==FREEZE_SCHEMA and frozen.get('image_size')==[1280,720],'target candidate mode differs')
    p=frozen['candidate_parameters'];k=transfer.axis_matrix(p['K']);d=np.asarray(p['D'],dtype=np.float64)
    require(p.get('model')=='fisheye' and p.get('projection')=='forward_rectilinear'
            and p.get('inverse_method')==inverse.METHOD,'bounded forward fisheye inverse required')
    inverse.domain(d,p['maximum_ray_angle_deg']);return k,d,p['maximum_ray_angle_deg']


def validate_manifest(frozen,manifest):
    model(frozen)
    require(manifest.get('schema')==MANIFEST_SCHEMA and manifest.get('target_identity')==frozen['target_identity']
            and manifest.get('image_size')==[1280,720] and manifest.get('board')==frozen['board'],'manifest target/board differs')
    require(manifest.get('candidate_unchanged_since_freeze_declared') is True,'candidate independence declaration required')
    thresholds=manifest['thresholds'];rms=transfer.positive(thresholds['rms_px'],'rms_px')
    maximum=transfer.positive(thresholds['maximum_px'],'maximum_px');require(maximum>=rms,'maximum budget must be at least RMS budget')
    require(thresholds==frozen['fixed_diagnostic_thresholds'],'validation budgets must equal the frozen transfer budgets; no retrospective widening')
    require(manifest.get('thresholds_predeclared') is True,'thresholds must be declared before evaluation')
    views=manifest['views'];require(isinstance(views,list) and len(views)<=256,'at most256 explicit views required')
    fit_poses={p['pose_id'] for p in frozen['fit_exclusions']}
    fit_hashes=set(frozen['source_profile_training_image_sha256'])|{p[s]['image']['sha256'] for p in frozen['fit_exclusions'] for s in ('source','target')}
    names=set();poses=set();hashes=set()
    for v in views:
        require(v.get('split')=='held_out','only held-out target views allowed; no fit or model-selection rows')
        require(v.get('not_used_to_fit_or_choose_candidate_declared') is True,'view must be unused for fitting or choosing this candidate')
        require(v.get('origin') in ('transfer_held_out','new_target_held_out'),'explicit validation origin required')
        for field,seen in (('view_id',names),('pose_id',poses)):
            x=v.get(field);require(isinstance(x,str) and x.strip() and x not in seen,'distinct nonempty '+field+' required');seen.add(x)
        require(v['pose_id'] not in fit_poses,'fit pose cannot become target held-out')
        digest=v.get('sha256');require(calibration._valid_digest(digest),'explicit image hash required');digest=digest.lower()
        require(digest not in hashes and digest not in fit_hashes,'duplicate image or fit-image leakage');hashes.add(digest)
    policy=manifest.get('coverage_policy')
    if policy is not None:
        cells=policy['required_cells'];minimum=policy['minimum_corners_per_cell']
        require(isinstance(cells,list) and cells
                and all(isinstance(c,list) and len(c)==2 and all(type(v) is int and v in (0,1,2) for v in c) for c in cells)
                and len({tuple(c) for c in cells})==len(cells),
                'explicit distinct 3x3 coverage cells required')
        require(type(minimum) is int and minimum>0,'positive declared coverage minimum required')
        require(policy.get('predeclared') is True,'coverage policy must be predeclared')
    return views


def pose_metrics(world,measured,k,d,angle):
    # Same fixed-intrinsic method as inverse.validate_pose; retain the solved
    # projection as well so max/per-corner errors can be reported, not just RMS.
    measured=np.asarray(measured,dtype=np.float64).reshape(-1,2)
    rays=inverse.undistort_points(measured,k,d,angle)
    world=np.asarray(world,dtype=np.float64).reshape(-1,3)
    ok,r,t=cv2.solvePnP(world,rays.reshape(-1,1,2),np.eye(3),None)
    require(ok and np.isfinite(r).all() and np.isfinite(t).all(),'held-out pose solve failed')
    rotation,_=cv2.Rodrigues(r);require(np.all((world@rotation.T+t.reshape(1,3))[:,2]>0),'board behind camera')
    projected=cv2.fisheye.projectPoints(world.reshape(1,-1,3),r,t,k,d)[0].reshape(-1,2)
    error=np.linalg.norm(projected-measured,axis=1)
    require(np.isfinite(error).all(),'nonfinite reprojection error')
    return {'rms_px':float(np.sqrt(np.mean(error**2))),'maximum_px':float(error.max()),
        'per_corner_error_px':error.tolist(),'rvec':r.reshape(-1).tolist(),'tvec_mm':t.reshape(-1).tolist(),
        'maximum_model_ray_angle_deg':float(np.degrees(np.arctan(np.linalg.norm(rays,axis=1))).max())}


def evaluate_observations(frozen,manifest,observations):
    views=validate_manifest(frozen,manifest);k,d,angle=model(frozen);world=board_points(manifest['board'])
    lookup={o['view_id']:o for o in observations};require(len(lookup)==len(observations) and set(lookup)=={v['view_id'] for v in views},'exact explicit view observations required')
    counts=np.zeros((3,3),dtype=int);rows=[];known={r['pose_id']:r for r in frozen['known_transfer_held_out']}
    for v in views:
        o=lookup[v['view_id']];require(o['image_sha256']==v['sha256'].lower(),'observations not bound to declared image')
        xy=np.asarray(o['corners'],dtype=np.float64).reshape(-1,2)
        require(xy.shape==(world.shape[1],2) and np.isfinite(xy).all() and np.all(xy>=0)
                and np.all(xy<[1280,720]),'complete finite in-frame target corners required')
        require(np.linalg.matrix_rank(xy-xy.mean(axis=0))==2,'degenerate target pose')
        distances=[]
        for fit in frozen['fit_exclusions']:
            dist=min(float(np.sqrt(np.mean(np.sum((xy-transfer.order_points(fit['target_corners'],manifest['board'],order))**2,axis=1)))) for order in transfer.ORDERS)
            distances.append(dist)
        require(not distances or min(distances)>=NEAR_FIT_RMS_PX,'target corners repeat a fit pose despite changed IDs')
        known_view=known.get(v['pose_id'])
        if v['origin']=='transfer_held_out':
            require(known_view is not None and v['sha256'].lower()==known_view['target']['image']['sha256'],'declared transfer-heldout identity differs')
        else:
            require(known_view is None and all(v['sha256'].lower()!=r['target']['image']['sha256'] for r in known.values()),'known transfer view cannot be relabeled new')
        metrics=pose_metrics(world,xy,k,d,angle)
        for x,y in xy:counts[min(2,int(y/240)),min(2,int(x*3/1280))]+=1
        rows.append({'view_id':v['view_id'],'pose_id':v['pose_id'],'origin':v['origin'],**metrics,
            'within_declared_thresholds':metrics['rms_px']<=manifest['thresholds']['rms_px'] and metrics['maximum_px']<=manifest['thresholds']['maximum_px'],
            'nearest_fit_corner_rms_px':min(distances) if distances else None})
    policy=manifest.get('coverage_policy');missing=[]
    if policy:
        missing=[{'cell':c,'observed':int(counts[tuple(c)]),'required':policy['minimum_corners_per_cell']} for c in policy['required_cells'] if counts[tuple(c)]<policy['minimum_corners_per_cell']]
    return {'schema':REPORT_SCHEMA,'target_identity':copy.deepcopy(frozen['target_identity']),'image_size':[1280,720],
        'candidate_parameters':copy.deepcopy(frozen['candidate_parameters']),'intrinsics_refitted':False,
        'numeric_runtime':{'opencv':cv2.__version__,'numpy':np.__version__},
        'pose_only_optimization':True,'source_observations_used_for_pose_solve':False,
        'observation_source':'synthetic_or_unverified_api',
        'thresholds':copy.deepcopy(manifest['thresholds']),'observed_view_count':len(rows),
        'observed_transfer_held_out_count':sum(r['origin']=='transfer_held_out' for r in rows),
        'observed_new_target_held_out_count':sum(r['origin']=='new_target_held_out' for r in rows),
        'views':rows,'mean_rms_px':float(np.mean([r['rms_px'] for r in rows])) if rows else None,
        'worst_view_rms_px':max((r['rms_px'] for r in rows),default=None),'maximum_corner_error_px':max((r['maximum_px'] for r in rows),default=None),
        'numeric_observed_views_passed':bool(rows) and all(r['within_declared_thresholds'] for r in rows),
        'native_physical_observed_views_passed':False,
        'target_corner_coverage_3x3':counts.tolist(),'coverage_policy':copy.deepcopy(policy),
        'coverage_passed':None if policy is None else bool(rows) and not missing,'missing_coverage':missing,
        'sample_count_acceptance_rule':None,'required_sample_count_invented':False,
        'physical_pose_identity_verified':False,'image_pixel_orientation_verified':False,
        'optical_calibration_accepted':False,'hardware_release_allowed':False,'drop_in_calibration_profile':False,
        'hardware_accessed':False,'fpga_mapping_verified':False,
        'limits':'Only listed target poses are checked against fixed measured-transfer K/D. No intrinsic fit or automatic lens acceptance. Actual counts/coverage are reported; no six-view quota. Pose/orientation/operator declarations and optical behavior outside observed points are not proved. API-only observations are synthetic/unverified until native capture loading is bound.'}


def audit_value(freeze_path,manifest_path):
    frozen,watched=bind_freeze(freeze_path);manifest_path=bind(watched,manifest_path);manifest=read(manifest_path)
    require(manifest.get('candidate_freeze')==ref(freeze_path),'manifest freeze binding differs')
    declaration=manifest.get('threshold_declaration')
    require(isinstance(declaration,dict) and calibration._valid_digest(declaration.get('sha256')),
            'hash-bound predeclared threshold source required')
    budget_path=calibration._file(manifest_path.parent,declaration.get('path'),'threshold declaration')
    bind(watched,budget_path,declaration['sha256'].lower())
    require(read(budget_path).get('thresholds')==manifest.get('thresholds'),
            'threshold declaration differs from evaluation budgets')
    views=validate_manifest(frozen,manifest);observations=[];evidence=[];raw_hashes=set()
    fit_raw={r[s]['raw_sha256'] for r in frozen['fit_exclusions'] for s in ('source','target')}
    known_raw={r['target']['raw_sha256']:r for r in frozen['known_transfer_held_out']}
    for v in views:
        path=calibration._file(manifest_path.parent,v['path'],'target image');bind(watched,path,v['sha256'].lower())
        image=cv2.imdecode(np.fromfile(path,dtype=np.uint8),cv2.IMREAD_COLOR)
        require(image is not None and image.shape[:2]==(720,1280),'native1280x720 image required')
        cap=calibration._decode_bound_capture(v,{**frozen['target_identity'],'image_size':[1280,720]},manifest_path.parent,image,path)
        require(cap['raw_sha256'] not in fit_raw|raw_hashes,'raw fit leakage or duplicate target content');raw_hashes.add(cap['raw_sha256'])
        if v['origin']=='new_target_held_out':
            require(cap['raw_sha256'] not in known_raw,'known transfer raw content cannot be relabeled new')
        for prefix in ('metadata','raw'):bind(watched,cap[prefix+'_path'],cap[prefix+'_sha256'])
        found,corners=cv2.findChessboardCornersSB(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),(manifest['board']['cols'],manifest['board']['rows']))
        require(found and corners is not None,'complete declared chessboard missing; no silent image dropping')
        observations.append({'view_id':v['view_id'],'image_sha256':v['sha256'].lower(),'corners':corners.reshape(-1,2)})
        evidence.append({'view_id':v['view_id'],'image':ref(path),**cap})
    result=evaluate_observations(frozen,manifest,observations)
    result.update(candidate_freeze=ref(freeze_path),manifest=ref(manifest_path),capture_evidence=evidence,
        threshold_declaration=ref(budget_path),threshold_predeclaration_time_independently_verified=False,
        observation_source='hash_bound_native_rgb565_captures',
        physical_capture_record_count=sum(e['physical_capture_record'] for e in evidence),
        all_views_recorded_physical=bool(evidence) and all(e['physical_capture_record'] for e in evidence),
        producer=ref(SELF),input_sha256=watched)
    result['native_physical_observed_views_passed']=result['numeric_observed_views_passed'] and result['all_views_recorded_physical']
    tools(watched);unchanged(watched);return result,watched


def verify(path):
    """Recompute a saved diagnostic in memory; never modify inputs or output."""
    path=Path(path).resolve();saved=read(path)
    require(saved.get('schema')==REPORT_SCHEMA and saved.get('producer')==ref(SELF),
            'wrong or changed target-validation producer')
    watched={};bind(watched,path)
    for p,h in saved['input_sha256'].items():bind(watched,p,h)
    for key in ('candidate_freeze','manifest','threshold_declaration'):
        bind(watched,saved[key]['path'],saved[key]['sha256'])
    actual,recomputed=audit_value(saved['candidate_freeze']['path'],saved['manifest']['path'])
    require(actual==saved,'saved target validation differs from full native-image recomputation')
    watched.update(recomputed);unchanged(watched);return actual,watched


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('freeze','validate'))
    p.add_argument('--transfer-report',type=Path);p.add_argument('--freeze',type=Path);p.add_argument('--manifest',type=Path)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.mode=='freeze':
        require(a.transfer_report is not None,'measured transfer report required');value,_=freeze_value(a.transfer_report.resolve())
    else:
        require(a.freeze is not None and a.manifest is not None,'freeze and target manifest required')
        value,_=audit_value(a.freeze.resolve(),a.manifest.resolve())
    save(a.output,value)
    print(json.dumps({k:value[k] for k in ('schema','observed_view_count','numeric_observed_views_passed','coverage_passed','optical_calibration_accepted') if k in value}))
    return 0 if a.mode=='freeze' or (value['native_physical_observed_views_passed'] and value['coverage_passed'] is not False) else 1


if __name__=='__main__':raise SystemExit(main())
