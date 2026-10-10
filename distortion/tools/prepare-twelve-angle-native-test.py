"""Extend native adaptive RTL regression without changing any board sources."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import zlib
import numpy as np

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from model.rotation import cordic, phase_from_degrees, inverse_rotate
from model.reference import remap_fixed
spec = importlib.util.spec_from_file_location('brown', root / 'tools/generate-brown-vectors.py')
brown = importlib.util.module_from_spec(spec)
spec.loader.exec_module(brown)
c = json.loads((root / 'results/calibration-fpga-candidate-20261006/candidate.json').read_text())['integer_config']
bound = json.loads((root / 'results/rotation-domain-20261006.json').read_text())['guard_radius_squared_q22']
pairs = json.loads((root / 'results/corrected-pair-check-20261006.json').read_text())['pairs']
sealed = json.loads((root / 'build/rotated_native_sim/reference.json').read_text())['frames']
sealed_by_angle = {f['angle_deg'] % 360: (i % 2, f['crc32']) for i, f in enumerate(sealed)}
work = root / 'build/adaptive_twelve_native_sim'
work.mkdir(parents=True, exist_ok=True)
y, x = np.indices((480, 640), dtype=np.int64)
Q = 1 << 22
rs = lambda v, n: (v + (1 << (n - 1))) >> n
sources, goldens, crcs, rotations, frames = [], [], [], [], []
rng = np.random.default_rng(20261007)
for i, angle in enumerate(range(0, 360, 30)):
    co, si = cordic(phase_from_degrees(angle))
    ru = rs(co * (x * 256 - 81792) + si * (y * 256 - 61312), 30) + 81792
    rv = rs(-si * (x * 256 - 81792) + co * (y * 256 - 61312), 30) + 61312
    nx, ny = rs((ru - c[0]) * c[6], 16), rs((rv - c[1]) * c[7], 16)
    r2 = rs(nx * nx, 22) + rs(ny * ny, 22)
    valid = r2 <= bound
    radial = Q + rs((c[8] + rs((c[9] + rs(c[10] * r2, 22)) * r2, 22)) * r2, 22)
    sx = rs(rs(nx * radial, 22) * c[4], 22) + c[2]
    sy = rs(rs(ny * radial, 22) * c[5], 22) + c[3]
    indices = set(map(int, rng.choice(307200, 2048, replace=False))) | {0, 639, 306560, 307199}
    for idx in indices:
        yy, xx = divmod(idx, 640)
        pu, pv, bad = inverse_rotate(xx * 256, yy * 256, 81792, 61312, co, si)
        assert not bad and (pu, pv) == (ru[yy, xx], rv[yy, xx])
        px, py, bad = brown.project(pu, pv, c)
        assert not bad and (px, py) == (sx[yy, xx], sy[yy, xx])
    sx, sy = np.where(valid, sx, -(1 << 23)), np.where(valid, sy, -(1 << 23))
    raw_index = sealed_by_angle.get(angle, (i % 2, None))[0]
    raw_path = Path(pairs[raw_index]['directory']) / 'raw-source.rgb565'
    raw = raw_path.read_bytes()
    p = np.frombuffer(raw, dtype='<u2').reshape(480, 640)
    r, g, b = (p >> 11) & 31, (p >> 5) & 63, p & 31
    rgb = np.stack(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)), axis=-1).astype(np.uint8)
    out = remap_fixed(rgb, sx / 256, sy / 256).astype(np.uint16)
    golden = (((out[..., 0] >> 3) << 11) | ((out[..., 1] >> 2) << 5) | (out[..., 2] >> 3)).astype('<u2').tobytes()
    crc = zlib.crc32(golden)
    if angle in sealed_by_angle:
        assert f'{crc:08X}' == sealed_by_angle[angle][1].upper(), angle
    for payload, array in ((raw, sources), (golden, goldens)):
        array.extend(int.from_bytes(payload[j:j + 32], 'little') for j in range(0, len(payload), 32))
    crcs.append(crc)
    rotations.append((co & 0xffffffff) << 32 | (si & 0xffffffff))
    frames.append({'angle_deg': angle, 'pixels': 307200, 'crc32': f'{crc:08X}',
                   'source_sha256': hashlib.sha256(raw).hexdigest(), 'scalar_coordinate_spotchecks': len(indices),
                   'masked_pixels': int((~valid).sum()), 'matches_previous_six_angle_oracle': angle in sealed_by_angle})
for name, array, digits in (('source.mem', sources, 64), ('result.mem', goldens, 64), ('crcs.mem', crcs, 8), ('rotations.mem', rotations, 16)):
    (work / name).write_text(''.join(f'{n:0{digits}x}\n' for n in array))
(work / 'reference.json').write_text(json.dumps({'frames': frames, 'pixels': 3686400,
    'scope': 'Real camera captures and independent integer software interpolation; no optical or physical throughput claim.'}, indent=2) + '\n')
tb = (root / 'tests/tb_adaptive_native_regression.sv').read_text()
tb = tb.replace('tb_adaptive_native_regression', 'tb_adaptive_twelve_native_regression')
tb = tb.replace('[0:5]', '[0:11]').replace('[0:115199]', '[0:230399]').replace('phase<6', 'phase<12')
tb = tb.replace('1843200', '3686400').replace('#900000000', '#1800000000')
(root / 'tests/tb_adaptive_twelve_native_regression.sv').write_text(tb)
runner = (root / 'tools/run-adaptive-native-sim.ps1').read_text()
runner = runner.replace('adaptive_native_sim', 'adaptive_twelve_native_sim').replace('tb_adaptive_native_regression', 'tb_adaptive_twelve_native_regression')
(root / 'tools/run-adaptive-twelve-native-sim.ps1').write_text(runner)
snapshot = work / 'source-snapshot'
snapshot.mkdir(exist_ok=True)
files = [root / 'rtl' / (n + '.v') for n in ('bilinear_rgb', 'ddr_remap_sample', 'mul32_pipe', 'pixel_inverse_rotation', 'bounded_brown_inverse_mapper', 'rotated_remap_core')]
files += [root / 'rtl/experimental' / (n + '.v') for n in ('ddr_adaptive_cache', 'adaptive_tiled_frame_engine', 'ddr_adaptive_result_writer')]
files += [root / 'tests/tb_adaptive_twelve_native_regression.sv', root / 'board/calibration-trial.vh', root / 'board/rotation-domain.vh']
hashes = {}
for path in files:
    rel = path.relative_to(root)
    target = snapshot / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(path.read_bytes())
    hashes[str(rel)] = hashlib.sha256(path.read_bytes()).hexdigest()
(snapshot / 'files-sha256.json').write_text(json.dumps(hashes, indent=2) + '\n')
print('Prepared 12-angle / 3,686,400-pixel adaptive RTL regression; six prior CRCs preserved, board sources unchanged.')
