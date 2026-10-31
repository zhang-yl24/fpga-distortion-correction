"""Prepare native CPU reference images for identifying the diagnostic on screen.

These are reference pixels, never a hardware capture or native RTL run.
"""
from pathlib import Path
import hashlib
import json
import zlib
import argparse
import numpy as np
from PIL import Image
import generate_1080_core_vectors as cpu
import run_processed_output_pattern_sim as pattern

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.absolute()
    if output.resolve() != output or output.parent != ROOT / 'results' or output.exists():
        raise ValueError('fresh canonical results child required')
    sources = {str(p): sha(p) for p in (
        Path(__file__).resolve(), Path(cpu.__file__), Path(pattern.__file__),
        ROOT / 'tools/generate_continuous1080_vectors.py',
        ROOT / 'tools/generate-brown-vectors.py', ROOT / 'model/reference.py',
        ROOT / 'board/processed_output_top.v', ROOT / 'rtl/experimental/processed_output_pattern.v',
        ROOT / 'board/board1080-synthetic.vh')}
    width, height = 1920, 1080
    y, x = np.indices((height, width), dtype=np.int64)
    cx, cy, fx, fy = (width-1)*128, (height-1)*128, width*128, height*1152//5
    config = [cx, cy, cx, cy, fx, fy, ((1 << 38)+fx//2)//fx, ((1 << 38)+fy//2)//fy,
              0x51eb8, -0xf5c3, 0x20c5, 0x1062, -0xb78]
    # Scalar source oracle already checked against every native RTL source pixel.
    source = np.fromiter((pattern.pixel565(xx, yy, width, height)
                          for yy in range(height) for xx in range(width)),
                         dtype=np.uint16, count=width*height).reshape(height, width)
    crc = lambda a: f'{zlib.crc32(a.astype("<u2").tobytes()):08X}'
    if crc(source) != 'C58CBE14':
        raise ValueError('source differs from completed native source simulation')
    sx, sy, bad, radius = cpu.project_integer(x*256, y*256, config)
    mask = bad | (radius > 2*cpu.Q) | (sx <= -256) | (sy <= -256) | (sx >= width*256) | (sy >= height*256)
    oracle = cpu.scalar_oracle()
    points = {(int(xx), int(yy)) for yy in np.linspace(0, height-1, 33)
              for xx in np.linspace(0, width-1, 65)}
    for xx, yy in points:
        expected = oracle.project(xx*256, yy*256, config)
        if expected != (int(sx[yy, xx]), int(sy[yy, xx]), bool(bad[yy, xx])):
            raise ValueError('scalar/vector integer coordinate mismatch')
    result = cpu.tone(cpu.pack565(cpu.remap_fixed(cpu.expand565(source),
        np.where(mask, -(1 << 23), sx)/256., np.where(mask, -(1 << 23), sy)/256.)), mask, 0)
    output.mkdir()
    for name, pixels in (('source-reference', source), ('processed-reference', result)):
        Image.fromarray(cpu.expand565(pixels)).save(output / (name + '.png'))
    report = {'Schema': 'processed-output-native-cpu-preview-v1', 'Width': width, 'Height': height,
              'SourceCRC32': crc(source), 'ProcessedReferenceCRC32': crc(result),
              'IntegerConfig': config, 'GammaEnabled': False, 'MaskedPixels': int(mask.sum()),
              'ScalarCoordinateCrosschecks': len(points), 'SourceHashes': sources,
              'HardwareCapture': False, 'NativeProcessingRTLExecuted': False,
              'Limits': 'CPU expectation for visual identification. Synthetic geometry; not camera calibration or hardware proof.',
              'Images': {p.name: sha(p) for p in output.glob('*.png')}}
    if any(sha(p) != digest for p, digest in sources.items()):
        raise ValueError('source changed during preview preparation')
    (output / 'reference.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
