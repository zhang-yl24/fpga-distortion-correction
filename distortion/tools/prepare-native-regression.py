"""Independent integer references for preserved, CRC-checked real camera frames."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys
import zlib
import numpy as np

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from model.reference import remap_fixed
spec = importlib.util.spec_from_file_location('brown_integer', root / 'tools/generate-brown-vectors.py')
brown = importlib.util.module_from_spec(spec)
spec.loader.exec_module(brown)
candidate = root / 'results/calibration-fpga-candidate-20261006'
config = json.loads((candidate / 'candidate.json').read_text())['integer_config']
q = np.empty((480, 640, 2), dtype='<i4')
for y in range(480):
    for x in range(640):
        sx, sy, bad = brown.project(x * 256, y * 256, config)
        assert not bad
        q[y, x] = sx, sy
assert np.array_equal(q, np.fromfile(candidate / 'coordinates-q8.bin', dtype='<i4').reshape(480, 640, 2))
evidence = json.loads((root / 'results/corrected-pair-check-20261006.json').read_text())
assert evidence['passed']
work = root / 'build/native_regression_sim'
work.mkdir(parents=True, exist_ok=True)
manifest = {'dimensions': [640, 480], 'integer_config': config, 'pairs': [],
            'limits': 'RTL transaction simulation using real source frames and independent integer math. Memory stalls are synthetic; cycle counts are not measured hardware FPS or optical accuracy.'}
sources, results, crcs = [], [], []
for pair in evidence['pairs']:
    folder = Path(pair['directory'])
    raw = (folder / 'raw-source.rgb565').read_bytes()
    assert f'{zlib.crc32(raw):08X}' == pair['raw_crc32']
    p = np.frombuffer(raw, dtype='<u2').reshape(480, 640)
    r, g, b = (p >> 11) & 31, (p >> 5) & 63, p & 31
    image = np.stack(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)), axis=-1).astype(np.uint8)
    rgb = remap_fixed(image, q[..., 0] / 256, q[..., 1] / 256).astype(np.uint16)
    golden = (((rgb[..., 0] >> 3) << 11) | ((rgb[..., 1] >> 2) << 5) | (rgb[..., 2] >> 3)).astype('<u2').tobytes()
    assert golden == (folder / 'fpga-corrected.rgb565').read_bytes()
    assert golden == (folder / 'software-reference.rgb565').read_bytes()
    for payload, array in ((raw, sources), (golden, results)):
        array.extend(int.from_bytes(payload[i:i+32], 'little') for i in range(0, len(payload), 32))
    crcs.append(zlib.crc32(golden))
    manifest['pairs'].append({'pair_id': pair['pair_id'], 'source_sha256': hashlib.sha256(raw).hexdigest(),
                              'golden_sha256': hashlib.sha256(golden).hexdigest(), 'crc32': f'{crcs[-1]:08X}'})
for name, array, digits in (('source.mem', sources, 64), ('result.mem', results, 64), ('crcs.mem', crcs, 8)):
    (work / name).write_text(''.join(f'{value:0{digits}x}\n' for value in array))
(work / 'reference.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(f'Prepared {len(crcs)} native real-frame RTL fixtures; independent coordinates and golden pixels match preserved hardware evidence.', flush=True)
