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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checks', type=Path, nargs='+', required=True,
                   help='explicit selected quality.json files, one per physical pose')
    p.add_argument('--maximum-ray-angle-deg', type=float, required=True,
                   help='reviewed forward model domain request below 90 degrees, not measured FOV')
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    output = a.output.resolve()
    if not output.parent.is_dir() or output.exists() or not output.is_relative_to(HERE):
        p.error('fresh output inside this session is required')
    plan = native.load_json(HERE / 'session-plan.json')
    by_id = {row['view_id']: row for row in plan['planned_views']}
    identity = {k: v for k, v in plan['identity'].items() if k != 'eye'}
    views, inputs = [], []
    for check in a.checks:
        check = check.resolve()
        if not check.is_relative_to(HERE / 'captures'):
            raise ValueError('only this session capture checks are accepted')
        report = native.load_json(check)
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
        'model_scope': {'projection': 'forward_rectilinear', 'maximum_ray_angle_deg': a.maximum_ray_angle_deg},
        'required_coverage_cells': [[r, c] for r in range(3) for c in range(3)], 'views': views,
        'recorded_utc': datetime.now(timezone.utc).isoformat(),
        'session_plan_sha256': sha(HERE / 'session-plan.json'), 'selected_corner_checks': inputs,
        'hardware_accessed_by_assembler': False, 'calibration_fitted': False,
        'model_note': 'Fisheye candidate must be assessed for this current lens; no historic model or measured FOV is inferred.'}
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
