"""Independent Python integer oracle plus continuous-angle geometric check."""
from pathlib import Path
import json
import math
import numpy as np

root = Path(__file__).resolve().parents[1]
work = root / 'build/rotation_sim'
work.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(20261006)
angles = [0, 5, -5, 17.5, -30, 45, -45, 90, -90, 179, 180, -180]
points = [(0, 0), (639*256, 0), (0, 479*256), (639*256, 479*256), (319*256+128, 239*256+128)]
points += [(int(x), int(y)) for x, y in rng.integers([-256, -256], [640*256+256, 480*256+256], size=(1019, 2))]
configs, rows = [], []
max_error = 0.0
def bits(n, width): return n & ((1 << width) - 1)
def rotate(u, v, cx, cy, c, s):
    x = ((c*(u-cx) + s*(v-cy) + (1 << 29)) >> 30) + cx
    y = ((-s*(u-cx) + c*(v-cy) + (1 << 29)) >> 30) + cy
    bad = not (-(1 << 23) <= x < (1 << 23) and -(1 << 23) <= y < (1 << 23))
    return (-(1 << 23), -(1 << 23), 1) if bad else (x, y, 0)
for angle in angles:
    a = math.radians(angle)
    cx, cy = 319*256+128, 239*256+128
    c, s = math.floor(math.cos(a)*(1 << 30)+.5), math.floor(math.sin(a)*(1 << 30)+.5)
    configs.append((cx, cy, c, s))
    for u, v in points:
        x, y, bad = rotate(u, v, cx, cy, c, s)
        assert not bad
        float_x = math.cos(a)*(u-cx)+math.sin(a)*(v-cy)+cx
        float_y = -math.sin(a)*(u-cx)+math.cos(a)*(v-cy)+cy
        max_error = max(max_error, abs(x-float_x)/256, abs(y-float_y)/256)
        rows.append((u, v, bad, x, y))
# Exercise signed full-range arithmetic and explicit overflow black output.
configs.append((-(1 << 23), (1 << 23)-1, 0, 1 << 30))
extreme = [(-(1 << 23), -(1 << 23)), ((1 << 23)-1, (1 << 23)-1), (0, 0), (-1, 1)]
for i in range(len(points)):
    u, v = extreme[i % len(extreme)]
    x, y, bad = rotate(u, v, *configs[-1])
    rows.append((u, v, bad, x, y))
assert any(r[2] for r in rows)
(work / 'configs.mem').write_text(''.join(f'{bits(cx,24):06x}{bits(cy,24):06x}{bits(c,32):08x}{bits(s,32):08x}\n' for cx, cy, c, s in configs))
(work / 'vectors.mem').write_text(''.join(f'{bits(u,24):06x}{bits(v,24):06x}{bad:x}{bits(x,24):06x}{bits(y,24):06x}\n' for u, v, bad, x, y in rows))
(work / 'counts.vh').write_text(f'`define ROT_N {len(points)}\n`define ROT_PHASES {len(configs)}\n`define ROT_TOTAL {len(rows)}\n')
(work / 'reference.json').write_text(json.dumps({'angles_deg': angles, 'pixels_per_angle': len(points),
    'total_vectors': len(rows), 'floating_geometric_max_error_px': max_error,
    'overflow_vectors': sum(r[2] for r in rows),
    'limits': 'Output-image inverse rotation prototype. Does not extend the calibration surrogate valid radius, certify rotated optical quality, or prove board timing. Compose with camera projection before one interpolation.'}, indent=2) + '\n')
print(f'Generated {len(rows)} rotation/overflow vectors; max geometric error {max_error:.8f}px.')
