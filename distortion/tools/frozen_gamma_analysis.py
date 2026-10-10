"""Independent integer geometry and tone checks for frozen camera triplets."""
from pathlib import Path
import importlib.util
import sys
import numpy as np
from gamma_triplets import GammaTripletAssembler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model.reference import remap_fixed

spec = importlib.util.spec_from_file_location('tone_pair_metrics', ROOT/'tools/evaluate-tone-pair.py')
metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(metrics)


def geometry(parameters, width=640, height=480, radius_bound=1976439):
    if len(parameters) != 13 or not 0 <= radius_bound < 1 << 24:
        raise ValueError('Require all 13 calibrated parameters and a 24-bit radius bound')
    c = parameters
    y, x = np.indices((height, width), dtype=np.int64)
    rounded = lambda value, shift: (value + (1 << (shift - 1))) >> shift
    nx = rounded((x*256-c[0])*c[6], 16)
    ny = rounded((y*256-c[1])*c[7], 16)
    xx, yy, xy = rounded(nx*nx, 22), rounded(ny*ny, 22), rounded(nx*ny, 22)
    r2 = xx + yy
    radial = (1 << 22) + rounded((c[8]+rounded((c[9]+rounded(c[10]*r2, 22))*r2, 22))*r2, 22)
    tx = rounded(2*c[11]*xy+c[12]*(r2+2*xx), 22)
    ty = rounded(c[11]*(r2+2*yy)+2*c[12]*xy, 22)
    sx = rounded((rounded(nx*radial, 22)+tx)*c[4], 22)+c[2]
    sy = rounded((rounded(ny*radial, 22)+ty)*c[5], 22)+c[3]
    domain = r2 > radius_bound if radius_bound else np.zeros_like(r2, dtype=bool)
    sx, sy = np.where(domain, -(1 << 23), sx), np.where(domain, -(1 << 23), sy)
    mask = domain | (sx <= -256) | (sy <= -256) | (sx >= width*256) | (sy >= height*256)
    return np.stack((sx, sy), axis=-1), mask


def analyze(triplet, coordinates, mask, source_kind):
    assembler = GammaTripletAssembler()
    result = None
    for frame in (triplet.raw, triplet.before, triplet.after):
        result = assembler.feed(frame)
    if result is None or (result.group_id, result.mode) != (triplet.group_id, triplet.mode):
        raise ValueError('Triplet labels differ from validated packet identities')
    height, width = triplet.raw.height, triplet.raw.width
    if coordinates.shape != (height, width, 2) or mask.shape != (height, width):
        raise ValueError('Packet shape differs from reference geometry')
    raw, before, after = [np.frombuffer(frame.payload, dtype='<u2').reshape(height, width)
                          for frame in (triplet.raw, triplet.before, triplet.after)]
    rgb = metrics.expand(raw).astype(np.uint8)
    remapped = remap_fixed(rgb, coordinates[..., 0]/256, coordinates[..., 1]/256).astype(np.uint16)
    expected = ((remapped[..., 0] >> 3) << 11) | ((remapped[..., 1] >> 2) << 5) | (remapped[..., 2] >> 3)
    mismatches = int(np.count_nonzero(before != expected))
    if np.any(before[mask]):
        raise ValueError('Bypass geometry-masked samples are not black')
    identity = f'group:{triplet.group_id}:raw-crc:{triplet.raw.source_crc:08X}'
    provenance = {'source_kind': source_kind, 'source_frame_identity': identity,
                  'before_source_frame_identity': identity, 'after_source_frame_identity': identity,
                  'angle_deg': 0.0, 'mode': triplet.mode}
    tone = metrics.evaluate(before, after, mask, provenance)
    stats = tone['before']
    enough = tone['valid_samples'] >= width*height//4
    decision = (1 if stats['dark_fraction_y_lt_64'] >= .5 else
                2 if stats['bright_fraction_y_ge_192'] >= .5 else 0) if enough else 0
    # The board repeats this immutable source twice to settle the mode. This
    # checks steady-state decision, not live scene adaptation latency.
    decision_matches = decision == triplet.mode
    record = {'group_id': triplet.group_id, 'mode': triplet.mode,
              'expected_mode_after_frozen_warmup': decision,
              'mode_matches_frozen_statistics': decision_matches,
              'packet_ids': [frame.frame_id for frame in (triplet.raw, triplet.before, triplet.after)],
              'crc32': [f'{frame.source_crc:08X}' for frame in (triplet.raw, triplet.before, triplet.after)],
              'pixels_per_image': width*height, 'bypass_mismatched_pixels': mismatches,
              'tone': tone, 'passed': mismatches == 0 and tone['exact_tone_pixels_passed'] and decision_matches,
              'limits': 'One immutable source and two bypass warmup passes. Protocol/RTL evidence supports pairing; CRC alone is not proof of source provenance. No realtime rate, optical resolution, temporal noise or recovered highlight claim.'}
    return record, {'raw': raw, 'before': before, 'after': after, 'reference': expected, 'mask': mask}
