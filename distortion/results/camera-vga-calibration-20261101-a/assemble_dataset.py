"""Assemble selected real source-bound views; fit no K/D and access no hardware."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / 'distortion/tools'))
import calibrate_fisheye_profile as calibrator
import native_camera_capture as native


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_reference(reference):
    path = Path(reference['Path']).resolve(strict=True)
    if sha(path) != reference['SHA256']:
        raise ValueError('scope evidence SHA256 mismatch: ' + str(path))
    return path


def load_visibility_scope(path, *, plan_path, progress):
    """Only the reviewed fixed lower-right obstruction is accepted here."""
    path = path.resolve(strict=True)
    frozen = progress.get('VisibilityScope', {})
    if Path(frozen.get('Path', '')).resolve() != path or frozen.get('SHA256') != sha(path):
        raise ValueError('visibility scope differs from the frozen capture-progress reference')
    scope = native.load_json(path)
    plan = native.load_json(plan_path)
    nine = [[r, c] for r in range(3) for c in range(3)]
    eight = [cell for cell in nine if cell != [2, 2]]
    expected = {'Schema': 'current-vga-physical-visibility-scope-v1',
        'ImageSize': [640, 480], 'Identity': plan['identity'],
        'OriginalRequiredCoverageCells': nine, 'RequiredCoverageCells': eight,
        'ExcludedCoverageCells': [[2, 2]],
        'MinimumTrainingCornersPerRequiredCell': 15, 'MinimumHeldCornersPerRequiredCell': 3}
    for key, value in expected.items():
        if scope.get(key) != value:
            raise ValueError('unsupported visibility scope field: ' + key)
    for key in ('OtherQualityThresholdsChanged', 'RenderingMaskApplied', 'PixelGeometryChanged',
                'FullFrameCoverageClaimAllowed', 'ExcludedRegionOpticalValidationClaimAllowed'):
        if scope.get(key) is not False:
            raise ValueError('scope must retain false flag: ' + key)
    if scope.get('DecisionAnnouncedToUser') is not True:
        raise ValueError('scope decision must have been announced to the user')
    for key in ('UserReport', 'Reason', 'ExcludedCellDefinition', 'Limits'):
        if not isinstance(scope.get(key), str) or not scope[key].strip():
            raise ValueError('scope explanation required: ' + key)
    if checked_reference(scope['SessionPlan']) != plan_path.resolve():
        raise ValueError('scope belongs to a different session plan')
    requirements = plan['minimum_tool_requirements']
    if (plan['required_coverage_cells'] != nine or plan['image_size'] != [640, 480]
            or requirements['training_corners_per_required_cell'] != 15
            or requirements['held_out_corners_per_required_cell'] != 3):
        raise ValueError('original plan or coverage thresholds changed')
    metadata_path = checked_reference(scope['EvidenceMetadata'])
    image_path = checked_reference(scope['EvidenceImage'])
    metadata = native.load_json(metadata_path)
    if (metadata.get('identity_binding') != plan['identity']
            or [metadata.get('width'), metadata.get('height')] != [640, 480]
            or metadata.get('geometry_applied') is not False
            or metadata.get('source_kind') != 'physical_native_camera'
            or metadata.get('hardware_accessed') is not True
            or metadata.get('pixel_format') != 'RGB565_LE'
            or metadata.get('image_sha256') != scope['EvidenceImage']['SHA256']):
        raise ValueError('scope image metadata does not bind this physical native camera')
    bound_image = Path(metadata['image_path'])
    if not bound_image.is_absolute():
        bound_image = metadata_path.parent / bound_image
    if bound_image.resolve() != image_path:
        raise ValueError('scope image path differs from metadata')
    return {'source_path': str(path), 'source_sha256': sha(path), 'record': scope}


def validate_selected_check(check, report, progress):
    selected = [v for v in progress['SelectedViews'] if Path(v['QualityPath']).resolve() == check.resolve()]
    if len(selected) != 1 or selected[0]['QualitySHA256'] != sha(check):
        raise ValueError('quality check is not the exact explicitly selected attempt')
    if report.get('warnings') != []:
        raise ValueError('selected quality check has unresolved warnings')
    if (selected[0]['ViewID'] != report['manifest_view_candidate']['view_id']
            or selected[0]['Split'] != report['manifest_view_candidate']['split']
            or selected[0].get('ImageSHA256', report['image_sha256']) != report['image_sha256']):
        raise ValueError('selected view identity/image differs from quality check')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checks', type=Path, nargs='+', required=True,
                   help='explicit selected quality.json files, one per physical pose')
    p.add_argument('--maximum-ray-angle-deg', type=float, required=True,
                   help='reviewed forward model domain request below 90 degrees, not measured FOV')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--visibility-scope', type=Path,
                   help='explicit hash-bound physical visibility decision; default remains all nine cells')
    p.add_argument('--inverse-method', choices=['opencv', 'bounded_monotone_bisection_v1'], default='opencv',
                   help='explicit opt-in to audited bounded inversion; default OpenCV remains unchanged')
    a = p.parse_args()
    output = a.output.resolve()
    if not output.parent.is_dir() or output.exists() or not output.is_relative_to(HERE):
        p.error('fresh output inside this session is required')
    plan = native.load_json(HERE / 'session-plan.json')
    progress = native.load_json(HERE / 'capture-progress.json')
    physical_scope = (load_visibility_scope(a.visibility_scope, plan_path=HERE / 'session-plan.json',
                      progress=progress) if a.visibility_scope else None)
    by_id = {row['view_id']: row for row in plan['planned_views']}
    identity = {k: v for k, v in plan['identity'].items() if k != 'eye'}
    views, inputs = [], []
    for check in a.checks:
        check = check.resolve()
        if not check.is_relative_to(HERE / 'captures'):
            raise ValueError('only this session capture checks are accepted')
        report = native.load_json(check)
        validate_selected_check(check, report, progress)
        if report.get('complete_board_detected') is not True or report.get('image_size') != [640, 480]:
            raise ValueError('complete VGA chessboard required: ' + str(check))
        if report.get('inner_corners') != [6, 9] or report.get('identity_binding') != plan['identity']:
            raise ValueError('board or lens/mode identity changed')
        view = report['manifest_view_candidate']
        pose = by_id.get(view['view_id'])
        if pose is None or any(view[k] != pose[k] for k in ('view_id', 'pose_id', 'split')):
            raise ValueError('view split/physical pose differs from the predeclared plan')
        if not report.get('capture_pixel_binding', {}).get('physical_capture_record'):
            raise ValueError('offline or unverified pixels cannot become physical calibration data')
        views.append(view)
        inputs.append({'path': str(check), 'sha256': sha(check), 'warnings': report.get('warnings', [])})
    manifest = {'schema': 1, **identity, 'provenance': 'real_sensor_captures',
        'image_size': [640, 480], 'board': {'cols': 6, 'rows': 9, 'square_mm': 25.0},
        'model_scope': {'projection': 'forward_rectilinear', 'maximum_ray_angle_deg': a.maximum_ray_angle_deg,
                        'inverse_method': a.inverse_method},
        'required_coverage_cells': [[r, c] for r in range(3) for c in range(3)], 'views': views,
        'recorded_utc': datetime.now(timezone.utc).isoformat(),
        'session_plan_sha256': sha(HERE / 'session-plan.json'), 'selected_corner_checks': inputs,
        'hardware_accessed_by_assembler': False, 'calibration_fitted': False,
        'model_note': 'Fisheye candidate must be assessed for this current lens; no historic model or measured FOV is inferred.'}
    if physical_scope:
        manifest['required_coverage_cells'] = physical_scope['record']['RequiredCoverageCells']
        manifest['model_scope']['physical_visibility'] = physical_scope
    # Revalidate all native metadata/raw bytes/PNG corners using existing code.
    audit, _ = calibrator.load_dataset(manifest, base_dir=output.parent)
    if not audit['all_physical_capture_records']:
        raise ValueError('all selected images must have real native capture provenance')
    for item in inputs:
        if sha(Path(item['path'])) != item['sha256']:
            raise ValueError('selected check changed during dataset assembly')
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'dataset': str(output), 'views': len(views), 'sha256': sha(output),
        'raw_pixel_binding_checked': True, 'calibration_fitted': False, 'hardware_accessed': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
