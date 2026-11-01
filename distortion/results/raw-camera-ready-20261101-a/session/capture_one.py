"""One planned native view, then existing offline corner diagnostics.

Default mode prints commands only. --execute is explicit and still requires
the existing source/bit/timing/connection gate before opening any UART port.
"""
from pathlib import Path
import argparse
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
TOOLS = REPO / 'distortion/tools'
sys.path.insert(0, str(TOOLS))
import native_camera_capture as native


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--view', required=True)
    p.add_argument('--attempt', type=int, required=True)
    p.add_argument('--port', required=True)
    p.add_argument('--binding', type=Path, default=HERE / 'binding.json')
    p.add_argument('--execute', action='store_true')
    a = p.parse_args()
    plan = json.loads((HERE / 'session-plan.json').read_text(encoding='utf-8'))
    poses = {row['view_id']: row for row in plan['planned_views']}
    if a.view not in poses or not 1 <= a.attempt <= 99:
        p.error('choose a planned view and an explicit attempt number 1..99')
    pose = poses[a.view]
    target = HERE / 'captures' / (a.view + f'-a{a.attempt:02d}')
    if target.exists():
        p.error('attempt directory already exists; evidence is never overwritten')
    binding_path = a.binding.resolve()
    sid = 'vga-cal-20261031-' + target.name
    receiver = [sys.executable, '-B', '-X', 'utf8', str(TOOLS / 'native_camera_capture.py'),
        '--port', a.port, '--binding', str(binding_path), '--directory', str(target),
        '--session-id', sid, '--frames', '1', '--baud', '921600', '--seconds', '90',
        '--summary', str(target / 'receive-summary.json')]
    if not a.execute:
        print(json.dumps({'prepared_only': True, 'hardware_accessed': False,
            'pose': pose, 'capture_command': receiver,
            'required_next': 'Use reviewed binding.json for a programmed upright raw-only candidate; hold pose until capture and corner check finish.'},
            ensure_ascii=False, indent=2))
        return 0
    binding = native.load_json(binding_path)
    identity = native.validate_binding(binding)
    for key, expected in plan['identity'].items():
        if identity[key] != expected:
            raise ValueError('binding identity differs from this planned session: ' + key)
    if binding['image_size'] != [640, 480] or binding['pixel_format'] != 'RGB565_LE':
        raise ValueError('only the current upright VGA mode belongs to this session')
    native.validate_live_binding(binding, base_dir=binding_path.parent)
    target.mkdir()
    subprocess.run(receiver, cwd=REPO, check=True)
    summary = native.load_json(target / 'receive-summary.json')
    if not summary['passed'] or summary['saved_frames'] != 1:
        raise ValueError('one successful original frame required')
    metadata = Path(summary['frames'][0]['metadata_path']).resolve()
    if not metadata.is_relative_to(target):
        raise ValueError('metadata escaped this capture attempt')
    checker = [sys.executable, '-B', '-X', 'utf8', str(TOOLS / 'check_calibration_view.py'),
        str(metadata), '--binding', str(binding_path), '--cols', '6', '--rows', '9',
        '--output', str(target / 'quality.json'), '--overlay', str(target / 'corners-overlay.png'),
        '--view-id', pose['view_id'], '--pose-id', pose['pose_id'], '--session-id', sid,
        '--split', pose['split']]
    subprocess.run(checker, cwd=REPO, check=True)
    print(json.dumps({'capture_and_corner_check_completed': True, 'quality': str(target / 'quality.json'),
        'calibration_accepted': False, 'hardware_accessed': True}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
