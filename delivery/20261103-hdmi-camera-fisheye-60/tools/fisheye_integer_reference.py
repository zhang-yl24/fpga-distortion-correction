"""Integer C-profile mapping reference for whole-frame and small system tests.

The source model and calibration remain the released C fisheye profile. Width
and height apply its documented pixel-centre scaling, without recropping a
native map. Requires NumPy; does not access FPGA hardware.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import numpy as np


def integer_map(width, height, profile_header, radial_header):
    profile_text = Path(profile_header).read_text(encoding="utf-8")
    radial_text = Path(radial_header).read_text(encoding="utf-8")
    p = {name: int(value, 16) for name, value in re.findall(r"FISHEYE_(\w+)=32'sh([0-9a-f]+)", profile_text)}
    for key, value in tuple(p.items()):
        if value >= 1 << 31:
            p[key] = value - (1 << 32)
    required = {"OUT_CX", "OUT_CY", "SRC_CX", "SRC_CY", "SRC_FX", "SRC_FY", "INV_FX", "INV_FY"}
    if set(p) != required or width < 1 or height < 1:
        raise ValueError("Unexpected calibration constants or frame dimensions")
    bases = np.zeros(1024, dtype=np.int64)
    deltas = bases.copy()
    entries = re.findall(r"10'd(\d+): fisheye_radial_pair=64'h([0-9a-f]+)", radial_text)
    if len(entries) != 1024 or {int(i) for i, _ in entries} != set(range(1024)):
        raise ValueError("Expected all 1024 calibrated radial segments")
    for address, word in entries:
        value = int(word, 16)
        high = value >> 32
        bases[int(address)] = value & 0xFFFFFFFF
        deltas[int(address)] = high - (1 << 32) if high >> 31 else high
    # All published pixel-centre/focal constants are positive; integer division
    # therefore matches Verilog truncation for the supported image dimensions.
    ocx = ((p["OUT_CX"] + 128) * width + 960) // 1920 - 128
    ocy = ((p["OUT_CY"] + 128) * height + 540) // 1080 - 128
    scx = ((p["SRC_CX"] + 128) * width + 960) // 1920 - 128
    scy = ((p["SRC_CY"] + 128) * height + 540) // 1080 - 128
    sfx = (p["SRC_FX"] * width + 960) // 1920
    sfy = (p["SRC_FY"] * height + 540) // 1080
    ifx = (p["INV_FX"] * 1920 + width // 2) // width
    ify = (p["INV_FY"] * 1080 + height // 2) // height

    def rnd(x, n):
        return (x >> n) + ((x >> (n - 1)) & 1)

    def bound(x):
        return np.clip(x, -(1 << 31), (1 << 31) - 1)

    def ov32(x):
        return (x < -(1 << 31)) | (x >= (1 << 31))

    u, v = np.meshgrid(np.arange(width, dtype=np.int64) * 256, np.arange(height, dtype=np.int64) * 256)
    nx0 = rnd((u - ocx) * ifx, 16)
    ny0 = rnd((v - ocy) * ify, 16)
    black = ov32(nx0) | ov32(ny0)
    nx, ny = bound(nx0), bound(ny0)
    xx0, yy0 = rnd(nx * nx, 22), rnd(ny * ny, 22)
    black |= ov32(xx0) | ov32(yy0)
    r20 = bound(xx0) + bound(yy0)
    black |= ov32(r20) | (r20 < 0) | (r20 > 33554432)
    r2 = bound(r20)
    address = np.clip(r2 >> 15, 0, 1023)
    fraction = np.where(r2 >= 33554432, 32768, np.where(r2 < 0, 0, r2 & 32767))
    radial0 = bases[address] + rnd(deltas[address] * fraction, 15)
    black |= ov32(radial0) | (radial0 < 0) | (radial0 > 1073741824)
    radial = bound(radial0)
    xd0, yd0 = rnd(nx * radial, 30), rnd(ny * radial, 30)
    black |= ov32(xd0) | ov32(yd0)
    x = rnd(bound(xd0) * sfx, 22) + scx
    y = rnd(bound(yd0) * sfy, 22) + scy
    black |= (x < -(1 << 23)) | (x >= (1 << 23)) | (y < -(1 << 23)) | (y >= (1 << 23))
    x, y = np.where(black, -(1 << 23), x), np.where(black, -(1 << 23), y)
    return np.stack((x, y), axis=-1).astype("<i4"), black


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--radial", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    coords, black = integer_map(args.width, args.height, args.profile, args.radial)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.suffix == ".npy":
        np.save(args.output, coords)
    else:
        coords.tofile(args.output)
    print(json.dumps({"shape": list(coords.shape), "numeric_black": int(black.sum()),
                      "raw_sha256": hashlib.sha256(coords.tobytes()).hexdigest(), "output": str(args.output)}))


if __name__ == "__main__":
    main()
