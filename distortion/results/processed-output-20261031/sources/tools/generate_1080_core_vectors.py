"""Independent synthetic 1920x1080 Brown/RGB565 vectors; no RTL/CAD/device execution.

The output directory must already exist under approved scratch. Nothing in the
stable calibration, RTL, or board helpers is edited. Both texture variants use
the same explicitly unaccepted synthetic model and exact zero-degree rotation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
APPROVED = ROOT / "build/offline-20261024"
sys.path.insert(0, str(ROOT))
from model.reference import remap_fixed

WIDTH, HEIGHT = 1920, 1080
Q = 1 << 22
COEFFICIENTS = (Fraction(2, 25), Fraction(-3, 200), Fraction(1, 500),
                Fraction(1, 1000), Fraction(-7, 10000))
NAMES = ("OUT_CX", "OUT_CY", "SRC_CX", "SRC_CY", "SRC_FX", "SRC_FY",
         "INV_FX", "INV_FY", "K1", "K2", "K3", "P1", "P2")
OUTPUTS = ("source.mem", "expected.mem", "masks.mem", "crcs.mem", "config.vh", "vectors.json")
REFERENCES = ("tools/generate-brown-vectors.py", "model/reference.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def quant(value, scale):
    return math.floor(Fraction(value) * scale + Fraction(1, 2))


def parameters(width=WIDTH, height=HEIGHT):
    """Hand-chosen stress intrinsics, never a calibration of an actual lens."""
    if type(width) is not int or type(height) is not int or not 4 <= width <= WIDTH or not 4 <= height <= HEIGHT:
        raise ValueError("bounded integer dimensions required")
    cx, cy = Fraction(width - 1, 2), Fraction(height - 1, 2)
    fx, fy = Fraction(width, 2), Fraction(width, 2) * Fraction(81, 80)
    return ([quant(v, 256) for v in (cx, cy, cx, cy, fx, fy)]
            + [quant(1 / v, 1 << 30) for v in (fx, fy)]
            + [quant(v, Q) for v in COEFFICIENTS])


def texture(width, height, variant):
    if type(variant) is not int or variant not in (0, 1):
        raise ValueError("only fixed texture variant 0 or 1 is supported")
    y, x = np.indices((height, width), dtype=np.int64)
    # Mixed two-dimensional ramps, small tiles and an x*y term. This is not
    # uniform fill or a pure color-bar image; variants are distinct source banks.
    mix = (73*x + 151*y + 7*((x*y + 0x1080 + 137*variant) & 1023)
           + 29*((x//17) ^ (y//13)) + 53*variant) & 255
    r = (3*x + 5*y + mix + 71*variant) & 255
    g = (7*x + 11*y + (mix ^ ((x+y) & 255)) + 37*variant) & 255
    b = (13*x + 3*y + ((mix*5) & 255) + 113*variant) & 255
    return (((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)).astype(np.uint16)


def project_integer(u, v, c):
    """Full radial+tangential integer Brown math, with scalar-oracle saturation.

    This computes expected coordinates directly from input coordinates/model.
    It neither parses RTL nor reads a simulator/FPGA result.
    """
    def rs(a, n):
        return (a + (1 << (n-1))) >> n
    bad = np.zeros(np.broadcast_shapes(u.shape, v.shape), dtype=bool)
    def s32(a):
        nonlocal bad
        bad |= (a < -(1 << 31)) | (a >= (1 << 31))
        return np.clip(a, -(1 << 31), (1 << 31)-1)
    nx, ny = rs((u-c[0])*c[6], 16), rs((v-c[1])*c[7], 16)
    bad |= (np.abs(nx) > 2*Q) | (np.abs(ny) > 2*Q)
    nx, ny = s32(nx), s32(ny)
    xx, yy, xy = rs(nx*nx, 22), rs(ny*ny, 22), rs(nx*ny, 22)
    r2 = xx + yy
    xx, yy, xy, r2 = s32(xx), s32(yy), s32(xy), s32(r2)
    txf, tyf = s32(r2 + 2*xx), s32(r2 + 2*yy)
    tx = s32(rs(2*c[11]*xy + c[12]*txf, 22))
    ty = s32(rs(c[11]*tyf + 2*c[12]*xy, 22))
    h5 = s32(c[9] + rs(c[10]*r2, 22))
    h7 = s32(c[8] + rs(h5*r2, 22))
    radial = s32(Q + rs(h7*r2, 22))
    xd, yd = s32(rs(nx*radial, 22) + tx), s32(rs(ny*radial, 22) + ty)
    sx, sy = rs(xd*c[4], 22) + c[2], rs(yd*c[5], 22) + c[3]
    bad |= (sx < -(1 << 23)) | (sx >= (1 << 23)) | (sy < -(1 << 23)) | (sy >= (1 << 23))
    return np.where(bad, -(1 << 23), sx), np.where(bad, -(1 << 23), sy), bad, r2


def expand565(words):
    r, g, b = (words >> 11) & 31, (words >> 5) & 63, words & 31
    return np.stack(((r << 3) | (r >> 2), (g << 2) | (g >> 4),
                     (b << 3) | (b >> 2)), axis=-1).astype(np.uint8)


def pack565(rgb):
    rgb = np.asarray(rgb, dtype=np.uint16)
    return (((rgb[..., 0] >> 3) << 11) | ((rgb[..., 1] >> 2) << 5)
            | (rgb[..., 2] >> 3)).astype(np.uint16)


def gamma_table(bits, mode):
    if bits not in (5, 6) or mode not in (0, 1, 2):
        raise ValueError("RGB565 Gamma bits/mode invalid")
    maximum = (1 << bits) - 1
    exponent = (1., .65, 1.45)[mode]
    return np.asarray([round((v/maximum)**exponent*maximum)
                       for v in range(maximum+1)], dtype=np.uint16)


def tone(words, masked, mode=0):
    r, g, b = (words >> 11) & 31, (words >> 5) & 63, words & 31
    result = ((gamma_table(5, mode)[r] << 11) | (gamma_table(6, mode)[g] << 5)
              | gamma_table(5, mode)[b]).astype(np.uint16)
    return np.where(masked, 0, result).astype(np.uint16)


def scalar_oracle():
    path = ROOT / "tools/generate-brown-vectors.py"
    spec = importlib.util.spec_from_file_location("core1080_brown_reference", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_frame(width, height, variant, *, chunk_rows=48):
    """CPU-only full integer reference; small dimensions are for focused tests."""
    if type(chunk_rows) is not int or not 1 <= chunk_rows <= HEIGHT:
        raise ValueError("bounded chunk size required")
    c = parameters(width, height)
    source = texture(width, height, variant)
    rgb = expand565(source)
    expected = np.empty_like(source)
    masks = np.empty(source.shape, dtype=bool)
    partial = bad_total = radius_total = outside_total = crosschecks = 0
    oracle = scalar_oracle()
    sample_x = np.unique(np.linspace(0, width-1, min(17, width), dtype=int))
    sample_y = set(np.unique(np.linspace(0, height-1, min(13, height), dtype=int)).tolist())
    for first in range(0, height, chunk_rows):
        last = min(height, first+chunk_rows)
        y, x = np.indices((last-first, width), dtype=np.int64)
        y += first
        sx, sy, bad, r2 = project_integer(x*256, y*256, c)
        radius = r2 > 2*Q
        outside = (sx <= -256) | (sy <= -256) | (sx >= width*256) | (sy >= height*256)
        masked = bad | radius | outside
        ix, iy = sx >> 8, sy >> 8
        partial += int((~masked & ((ix < 0) | (iy < 0) | (ix+1 >= width) | (iy+1 >= height))).sum())
        bad_total += int(bad.sum()); radius_total += int(radius.sum()); outside_total += int(outside.sum())
        for gy in sorted(sample_y.intersection(range(first, last))):
            for gx in sample_x:
                px, py, pb = oracle.project(int(gx)*256, gy*256, c)
                row = gy-first
                if (px, py, bool(pb)) != (int(sx[row, gx]), int(sy[row, gx]), bool(bad[row, gx])):
                    raise ValueError("independent scalar/vector Brown disagreement")
                crosschecks += 1
        # Power-of-two scaled integer coordinates are exactly representable in
        # float64; remap_fixed re-quantizes to the original Q15.8 integers.
        mapped = remap_fixed(rgb, np.where(masked, -(1 << 23), sx)/256.,
                             np.where(masked, -(1 << 23), sy)/256.)
        expected[first:last] = tone(pack565(mapped), masked, mode=0)
        masks[first:last] = masked
    mapped_rgb = expand565(expected)
    lum = (77*mapped_rgb[..., 0].astype(np.uint32)
           + 150*mapped_rgb[..., 1].astype(np.uint32)
           + 29*mapped_rgb[..., 2].astype(np.uint32)) >> 8
    valid = ~masks; samples = int(valid.sum())
    dark = int(((lum < 64) & valid).sum()); bright = int(((lum >= 192) & valid).sum())
    decision = 0 if samples < width*height//4 else 1 if dark >= (samples+1)//2 else 2 if bright >= (samples+1)//2 else 0
    stats = {"MaskedPixels": int(masks.sum()), "UnmaskedPixels": samples,
             "PartialBorderPixels": partial, "ArithmeticInvalidPixels": bad_total,
             "RadiusGuardPixels": radius_total, "FullyOutsidePixels": outside_total,
             "UnmaskedBlackPixels": int(((expected == 0) & valid).sum()),
             "ScalarCoordinateCrosschecks": crosschecks,
             "GammaDecisionAfterFrame": decision, "GammaDarkSamples": dark,
             "GammaBrightSamples": bright}
    return source, expected, masks, stats


def write_mem(path, values, digits):
    with Path(path).open("x", encoding="ascii", newline="\n") as out:
        flat = values.ravel()
        for first in range(0, flat.size, 65536):
            out.write("".join(f"{int(v):0{digits}x}\n" for v in flat[first:first+65536]))


def pixel_crc(words):
    return f"{zlib.crc32(np.asarray(words, dtype='<u2').tobytes()):08X}"


def generate_vectors(output_dir, *, variant=0, _test_size=None):
    """Write new files only. _test_size is private CPU-test support, never CLI."""
    if type(variant) is not int or variant not in (0, 1):
        raise ValueError("only fixed texture variant 0 or 1 is supported")
    work = Path(output_dir).resolve()
    if not work.is_dir() or work == APPROVED.resolve() or not work.is_relative_to(APPROVED.resolve()):
        raise ValueError("existing approved scratch child directory required; no mkdir")
    if any((work/name).exists() for name in OUTPUTS):
        raise ValueError("output already exists; no overwrite or cleanup")
    width, height = _test_size or (WIDTH, HEIGHT)
    helper_paths = (Path(__file__), *(ROOT/name for name in REFERENCES))
    watched = {str(p.relative_to(ROOT)): sha(p) for p in helper_paths}
    source, expected, masks, stats = render_frame(width, height, variant)
    c = parameters(width, height)
    write_mem(work/"source.mem", source, 4)
    write_mem(work/"expected.mem", expected, 4)
    write_mem(work/"masks.mem", masks.astype(np.uint8), 1)
    crc = pixel_crc(expected)
    with (work/"crcs.mem").open("x", encoding="ascii", newline="\n") as out:
        out.write(crc.lower()+"\n")
    config = ["// SYNTHETIC DEVELOPMENT ONLY: not accepted camera/lens parameters.",
              f"localparam integer VEC_WIDTH={width},VEC_HEIGHT={height},VEC_PIXELS={width*height};"]
    for name, value, bits in zip(NAMES, c, [24]*6+[32]*7):
        config.append(f"localparam signed [{bits-1}:0] VEC_{name}={bits}'sh{value & ((1 << bits)-1):0{bits//4}x};")
    config += [f"localparam integer VEC_RADIUS_GUARD_Q22={2*Q};",
               f"localparam signed [23:0] VEC_ROT_CX=24'sd{c[0]},VEC_ROT_CY=24'sd{c[1]};",
               "localparam signed [31:0] VEC_ROT_COS=32'sd1073741824,VEC_ROT_SIN=32'sd0;",
               "localparam [1:0] VEC_GAMMA_MODE=2'd0;",
               f"localparam [31:0] VEC_EXPECTED_CRC32=32'h{crc};"]
    with (work/"config.vh").open("x", encoding="ascii", newline="\n") as out:
        out.write("\n".join(config)+"\n")
    after = {str(p.relative_to(ROOT)): sha(p) for p in helper_paths}
    if watched != after:
        raise ValueError("reference helper changed during generation; partial outputs remain unsealed")
    files = {name: {"Path": str(work/name), "SHA256": sha(work/name), "Bytes": (work/name).stat().st_size}
             for name in OUTPUTS if name != "vectors.json"}
    report = {"Schema": 1, "VectorsGenerated": True, "CreatedUtc": datetime.now(timezone.utc).isoformat(),
              "Width": width, "Height": height, "PixelCount": width*height, "TextureVariant": variant,
              "PixelFormat": "RGB565", "WordOrder": "row-major y*width+x; one four-digit 16bit hex word per line",
              "CRCByteOrder": "RGB565 low byte then high byte, row-major; IEEE CRC32/zlib",
              "SourcePixelCRC32": pixel_crc(source), "ExpectedPixelCRC32": crc,
              "MaskByteCRC32": f"{zlib.crc32(masks.astype(np.uint8).tobytes()):08X}",
              "MaskFormat": "one hex bit per line; 1=geometry-masked; valid black is not inferred as masked",
              "IntegerConfigNames": list(NAMES), "IntegerConfig": c, "RadiusGuardQ22": 2*Q,
              "FixedPoint": {"PixelAndFocalFractionBits": 8, "InverseFocalFractionBits": 30,
                             "BrownFractionBits": 22, "Rounding": "nearest, ties toward positive infinity"},
              "Model": {"Type": "Brown-Conrady", "Provenance": "hand-chosen synthetic development stress model",
                        "K": [[width/2, 0, (width-1)/2], [0, width/2*81/80, (height-1)/2], [0, 0, 1]],
                        "KOutputEqualsK": True,
                        "DOrder": ["k1", "k2", "p1", "p2", "k3"],
                        "D": [float(COEFFICIENTS[i]) for i in (0, 1, 3, 4, 2)]},
              "Rotation": {"AngleDegrees": 0, "CosQ30": 1 << 30, "SinQ30": 0, "CORDICApproximationUsed": False},
              "Gamma": {"ExpectedMode": 0, "FirstCompleteFrameAfterReset": True,
                        "InitialPreviousDecision": 0, "InitialNextMode": 0,
                        "NextModeAfterFrame": stats["GammaDecisionAfterFrame"] if stats["GammaDecisionAfterFrame"] == 0 else 0,
                        "LumaWeights": [77, 150, 29], "AdaptiveModesOneTwoExercisedByThisFrame": False},
              "Statistics": stats, "Files": files, "ReferenceSHA256": watched, "ReferenceSHA256After": after,
              "IndependentScalarCoordinateChecksPassed": True, "RTLResultUsedForGolden": False,
              "SyntheticInput": True, "DevelopmentOnly": True, "CalibrationAccepted": False,
              "HardwareReleaseAllowed": False, "NewLensCorrectionVerified": False,
              "HardwareAccessed": False, "PDSAccessed": False, "SimulationExecuted": False,
              "Limits": "CPU-generated stimulus/oracle only. Nonzero synthetic Brown coefficients are not a fit or acceptance of any lens. No optical, full-system 1080p30, actual fps, source capture, final timing or board acceptance. Scalar-coordinate crosschecks are sampled; the pixel golden itself covers the complete declared frame."}
    with (work/"vectors.json").open("x", encoding="utf-8", newline="\n") as out:
        json.dump(report, out, ensure_ascii=False, indent=2, allow_nan=False)
        out.write("\n")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True, help="existing child of approved scratch; no overwrite")
    parser.add_argument("--variant", type=int, choices=(0, 1), default=0)
    args = parser.parse_args()
    try:
        record = generate_vectors(args.output_dir, variant=args.variant)
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc)+"\n")
    print(json.dumps({"Metadata": str(args.output_dir.resolve()/"vectors.json"),
                      "Pixels": record["PixelCount"], "Variant": record["TextureVariant"],
                      "ExpectedCRC32": record["ExpectedPixelCRC32"], "Statistics": record["Statistics"],
                      "CalibrationAccepted": False}, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
