"""Describe an explicitly paired RGB565 tone capture; never infer optical recovery.

Inputs are .npy uint16 HxW frames and a bool HxW geometry mask.
Manifest must identify same source frame, rotation, mode, and physical/synthetic origin.
Use before/after frames from one source, rather than separate live scenes.
"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np


def expand(pixel):
    pixel = pixel.astype(np.uint32)
    r, g, b = pixel >> 11, (pixel >> 5) & 63, pixel & 31
    return np.stack(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)), axis=-1)


def evaluate(before, after, mask, provenance):
    if before.dtype != np.uint16 or after.dtype != np.uint16 or mask.dtype != np.bool_:
        raise ValueError('Require uint16 RGB565 frames and explicit bool geometry mask')
    if before.ndim != 2 or before.shape != after.shape or before.shape != mask.shape:
        raise ValueError('All frame and mask dimensions must agree')
    if not np.any(~mask):
        raise ValueError('No valid image samples')
    if provenance.get('source_kind') not in ('physical_same_source', 'synthetic_same_source'):
        raise ValueError('Source kind must explicitly distinguish physical from synthetic')
    source = provenance.get('source_frame_identity')
    if not isinstance(source, str) or not source.strip() or provenance.get('before_source_frame_identity') != source or provenance.get('after_source_frame_identity') != source:
        raise ValueError('Both captures must identify the same input frame')
    angle = provenance.get('angle_deg')
    if not isinstance(angle, (int, float)) or not np.isfinite(angle):
        raise ValueError('Finite common rotation angle required')
    mode = provenance.get('mode')
    if mode not in (0, 1, 2):
        raise ValueError('Captured frame mode must be 0, 1 or 2')
    if np.any(after[mask]):
        raise ValueError('Geometry-masked output must remain black')
    # Independent exact curve check; physical identity pairing remains a provenance claim.
    exponent = (1.0, 0.65, 1.45)[mode]
    table5 = np.array([round((v / 31) ** exponent * 31) for v in range(32)], dtype=np.uint16)
    table6 = np.array([round((v / 63) ** exponent * 63) for v in range(64)], dtype=np.uint16)
    expected = (table5[before >> 11] << 11) | (table6[(before >> 5) & 63] << 5) | table5[before & 31]
    expected[mask] = 0
    mismatches = int(np.count_nonzero(after != expected))

    def stats(pixel):
        rgb = expand(pixel)[~mask]
        y = ((77 * rgb[:, 0] + 150 * rgb[:, 1] + 29 * rgb[:, 2]) >> 8).astype(float)
        p05, p50, p95 = np.percentile(y, [5, 50, 95])
        return {
            'mean_luminance_code': float(y.mean()),
            'p05_p50_p95': [float(p05), float(p50), float(p95)],
            'luminance_std_code': float(y.std()),
            'percentile_contrast_code_p95_minus_p05': float(p95 - p05),
            'dark_fraction_y_lt_64': float(np.mean(y < 64)),
            'bright_fraction_y_ge_192': float(np.mean(y >= 192)),
            'any_channel_at_max_fraction': float(np.mean(np.any(rgb == 255, axis=1))),
            'all_channels_at_max_fraction': float(np.mean(np.all(rgb == 255, axis=1))),
            'all_channels_at_zero_fraction': float(np.mean(np.all(rgb == 0, axis=1))),
        }
    return {
        'exact_tone_pixels_passed': mismatches == 0,
        'mismatched_pixels': mismatches,
        'shape': list(before.shape),
        'valid_samples': int(np.count_nonzero(~mask)),
        'excluded_geometry_samples': int(np.count_nonzero(mask)),
        'provenance': provenance,
        'provenance_independently_verified': False,
        'before': stats(before), 'after': stats(after),
        'limits': 'Single same-source tone comparison. Distribution contrast is not resolution, MTF or temporal noise. An endpoint code is not proof of sensor saturation. Metadata alone does not independently prove capture provenance. Tone mapping cannot recover lost highlights or establish low-light detail recovery.'
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('before', 'after', 'mask', 'manifest', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    paths = (args.before, args.after, args.mask, args.manifest)
    if args.output.resolve() in {path.resolve() for path in paths}:
        raise ValueError('Output must not overwrite an input')
    metadata = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    report = evaluate(np.load(args.before, allow_pickle=False), np.load(args.after, allow_pickle=False), np.load(args.mask, allow_pickle=False), metadata)
    report['input_sha256'] = {str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'exact_tone_pixels_passed': report['exact_tone_pixels_passed'], 'mismatches': report['mismatched_pixels'], 'output': str(args.output.resolve())}))
    if not report['exact_tone_pixels_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
