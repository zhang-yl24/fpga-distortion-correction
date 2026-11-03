"""Three synthetic CPU-only frames, with a distinct same-bank new epoch.

Frames 0/1 preserve existing source/golden/mask/CRC bytes. Frame 2 is exactly
source0 XOR 0x5A3C, independently remapped from its new source pixels. No RTL
result is read, no old generator/global is changed, and no directory is made.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import time
import zlib

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import generate_1080_core_vectors as cpu

APPROVED = ROOT / "build/offline-20261024/continuous-input1080-20261027-a"
XOR_WORD = 0x5A3C
REFERENCES = (Path(__file__), ROOT / "tools/generate_1080_core_vectors.py",
              ROOT / "tools/generate-brown-vectors.py", ROOT / "model/reference.py")
MEM_NAMES = ("source", "expected", "masks", "crc", "sourcecrc")
OUTPUTS = tuple(f"{name}{i}.mem" for i in range(3) for name in MEM_NAMES) + (
    "config.vh", "frame0-origin-vectors.json", "frame1-origin-vectors.json", "frame2-vectors.json", "sequence.json")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _deadline(started, maximum_seconds):
    if time.monotonic() - started > maximum_seconds:
        raise ValueError("CPU generation exceeded its declared budget; partial files are not sealed")


def _path(value):
    value = Path(value).resolve()
    return value / "vectors.json" if value.is_dir() else value


def _legacy(path, expected_variant):
    path = _path(path)
    record = json.loads(path.read_text(encoding="utf-8-sig"))
    if type(record.get("TextureVariant")) is not int or record["TextureVariant"] != expected_variant:
        raise ValueError("only exact old TextureVariant0/1 inputs are supported; variant2 is not a legacy input")
    if any(record.get(key) is not True for key in ("VectorsGenerated", "SyntheticInput", "DevelopmentOnly")) or any(
            record.get(key) is not False for key in ("CalibrationAccepted", "HardwareReleaseAllowed", "NewLensCorrectionVerified",
                                                    "HardwareAccessed", "PDSAccessed", "SimulationExecuted", "RTLResultUsedForGolden")):
        raise ValueError("legacy inputs must be explicitly synthetic/development CPU vectors")
    width, height = record.get("Width"), record.get("Height")
    if (width, height) not in ((32, 16), (1920, 1080)) or type(width) is not int or type(height) is not int:
        raise ValueError("only the declared small32x16 or full1920x1080 sequence is supported")
    if record.get("PixelCount") != width*height or record.get("IntegerConfigNames") != list(cpu.NAMES) or record.get("IntegerConfig") != cpu.parameters(width, height) or record.get("RadiusGuardQ22") != 2*cpu.Q:
        raise ValueError("legacy fixed-point model/dimensions/guard differ")
    if record.get("Rotation") != {"AngleDegrees": 0, "CosQ30": 1 << 30, "SinQ30": 0, "CORDICApproximationUsed": False} or record.get("Gamma", {}).get("ExpectedMode") != 0:
        raise ValueError("zero-degree exact rotation and expected GM0 are required")
    before, after = record.get("ReferenceSHA256"), record.get("ReferenceSHA256After")
    required = {p.relative_to(ROOT).as_posix(): sha(p) for p in REFERENCES[1:]}
    if not isinstance(before, dict) or before != after or {k.replace("\\", "/"): v for k, v in before.items()} != required:
        raise ValueError("legacy CPU reference source is not exactly current")
    files = record.get("Files", {})
    for name in ("source.mem", "expected.mem", "masks.mem", "crcs.mem", "config.vh"):
        item = files.get(name, {})
        source = Path(item.get("Path", ""))
        if not source.is_file() or sha(source) != item.get("SHA256") or source.stat().st_size != item.get("Bytes"):
            raise ValueError("legacy fixture file/hash/length differs: " + name)
    return path, record


def _words(path, count):
    result = np.loadtxt(path, dtype=np.uint16, converters={0: lambda value: int(value, 16)}, ndmin=1)
    if result.shape != (count,):
        raise ValueError("source/golden word count differs from the declared frame")
    return result


def third_source(source0):
    source0 = np.asarray(source0)
    if source0.dtype != np.uint16 or source0.ndim != 2:
        raise ValueError("third source requires a two-dimensional uint16 RGB565 source")
    return np.bitwise_xor(source0, np.uint16(XOR_WORD))


def remap_source(source, config, guard, *, maximum_seconds=180., started=None):
    """Pure integer coordinate + independent CPU bilinear oracle, never RTL."""
    if not math.isfinite(maximum_seconds) or maximum_seconds <= 0:
        raise ValueError("finite positive CPU budget required")
    started = time.monotonic() if started is None else started
    source = np.asarray(source)
    if source.dtype != np.uint16 or source.ndim != 2:
        raise ValueError("RGB565 uint16 source image required")
    height, width = source.shape
    if config != cpu.parameters(width, height) or guard != 2*cpu.Q:
        raise ValueError("only the same fixed nonzero synthetic Brown model/guard is supported")
    rgb = cpu.expand565(source)
    expected = np.empty_like(source)
    masks = np.empty(source.shape, dtype=bool)
    scalar = cpu.scalar_oracle()
    xs = np.unique(np.linspace(0, width-1, min(17, width), dtype=int))
    ys = set(np.unique(np.linspace(0, height-1, min(13, height), dtype=int)).tolist())
    partial = bad_count = radius_count = outside_count = crosschecks = 0
    for first in range(0, height, 48):
        _deadline(started, maximum_seconds)
        last = min(height, first+48)
        y, x = np.indices((last-first, width), dtype=np.int64); y += first
        sx, sy, bad, r2 = cpu.project_integer(x*256, y*256, config)
        radius = r2 > guard
        outside = (sx <= -256) | (sy <= -256) | (sx >= width*256) | (sy >= height*256)
        masked = bad | radius | outside
        ix, iy = sx >> 8, sy >> 8
        partial += int((~masked & ((ix < 0) | (iy < 0) | (ix+1 >= width) | (iy+1 >= height))).sum())
        bad_count += int(bad.sum()); radius_count += int(radius.sum()); outside_count += int(outside.sum())
        for gy in sorted(ys.intersection(range(first, last))):
            for gx in xs:
                px, py, pb = scalar.project(int(gx)*256, gy*256, config)
                row = gy-first
                if (px, py, bool(pb)) != (int(sx[row, gx]), int(sy[row, gx]), bool(bad[row, gx])):
                    raise ValueError("scalar/vector coordinate crosscheck differs")
                crosschecks += 1
        # Coordinates are exact Q15.8. Expand565 -> one bilinear round -> pack565.
        sampled = cpu.remap_fixed(rgb, np.where(masked, -(1 << 23), sx)/256.,
                                 np.where(masked, -(1 << 23), sy)/256.)
        expected[first:last] = cpu.tone(cpu.pack565(sampled), masked, 0)
        masks[first:last] = masked
    _deadline(started, maximum_seconds)
    stats = {"MaskedPixels": int(masks.sum()), "UnmaskedPixels": int((~masks).sum()),
             "PartialBorderPixels": partial, "ArithmeticInvalidPixels": bad_count,
             "RadiusGuardPixels": radius_count, "FullyOutsidePixels": outside_count,
             "UnmaskedBlackPixels": int(((expected == 0) & ~masks).sum()),
             "ScalarCoordinateCrosschecks": crosschecks}
    return expected, masks, stats


def _file(path):
    return {"Path": str(path), "SHA256": sha(path), "Bytes": path.stat().st_size}


def _copy(source, destination):
    with destination.open("xb") as stream:
        stream.write(Path(source).read_bytes())


def _json(path, record):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2, allow_nan=False); stream.write("\n")


def generate_sequence(vectors0, vectors1, output_dir, *, maximum_seconds=180.):
    if type(maximum_seconds) not in (int, float) or not math.isfinite(maximum_seconds) or not 0 < maximum_seconds <= 180:
        raise ValueError("maximum_seconds must be finite, >0 and <=180")
    started = time.monotonic()
    work = Path(output_dir).resolve()
    if not work.is_dir() or not work.is_relative_to(APPROVED.resolve()) or work == APPROVED.resolve():
        raise ValueError("an existing approved continuous-input1080 child is required; no mkdir")
    if any((work/name).exists() for name in OUTPUTS):
        raise ValueError("sequence output exists; no overwrite")
    inputs = [_legacy(vectors0, 0), _legacy(vectors1, 1)]
    a, b = (item[1] for item in inputs)
    for key in ("Width", "Height", "IntegerConfig", "RadiusGuardQ22", "Model", "Rotation", "FixedPoint", "MaskByteCRC32"):
        if a.get(key) != b.get(key):
            raise ValueError("legacy frame0/1 model/geometry differ: " + key)
    watched = {str(path): sha(path) for path in REFERENCES}
    for path, record in inputs:
        watched[str(path)] = sha(path)
        watched.update({item["Path"]: item["SHA256"] for item in record["Files"].values()})
    width, height, count = a["Width"], a["Height"], a["PixelCount"]
    source0 = _words(a["Files"]["source.mem"]["Path"], count).reshape(height, width)
    source1 = _words(b["Files"]["source.mem"]["Path"], count).reshape(height, width)
    for source, record in ((source0, a), (source1, b)):
        if cpu.pixel_crc(source) != record["SourcePixelCRC32"]:
            raise ValueError("legacy source payload CRC differs")
    source2 = third_source(source0)
    if np.array_equal(source2, source0) or np.array_equal(source2, source1):
        raise ValueError("third source must differ from both prior frames")
    expected2, mask2, statistics = remap_source(source2, a["IntegerConfig"], a["RadiusGuardQ22"],
                                              maximum_seconds=maximum_seconds, started=started)
    mask_crc = f"{zlib.crc32(mask2.astype(np.uint8).tobytes()):08X}"
    if mask_crc != a["MaskByteCRC32"] or statistics["MaskedPixels"] != a["Statistics"]["MaskedPixels"]:
        raise ValueError("third-frame geometry/mask changed")
    expected0 = _words(a["Files"]["expected.mem"]["Path"], count).reshape(height, width)
    changed_expected = int((expected2 != expected0).sum())
    if changed_expected == 0:
        raise ValueError("third golden failed to distinguish frame0 stale-bank contents")
    _deadline(started, maximum_seconds)
    frames = []
    for index, (origin, record) in enumerate(inputs):
        for old_name, new_name in (("source.mem", "source"), ("expected.mem", "expected"), ("masks.mem", "masks"), ("crcs.mem", "crc")):
            _copy(record["Files"][old_name]["Path"], work/f"{new_name}{index}.mem")
        _copy(origin, work/f"frame{index}-origin-vectors.json")
        with (work/f"sourcecrc{index}.mem").open("x", encoding="ascii", newline="\n") as stream:
            stream.write(record["SourcePixelCRC32"].lower()+"\n")
        frames.append({"Index": index, "FrameID": index+1, "BankExpected": index%2,
                       "PixelCount": count, "Length": 2*count,
                       "SourcePixelCRC32": record["SourcePixelCRC32"], "ExpectedPixelCRC32": record["ExpectedPixelCRC32"],
                       "MaskByteCRC32": record["MaskByteCRC32"],
                       "OriginalMetadata": _file(origin), "CopiedOriginalMetadata": _file(work/f"frame{index}-origin-vectors.json"),
                       "OriginalFixtureBytesPreserved": True})
    _copy(a["Files"]["config.vh"]["Path"], work/"config.vh")
    cpu.write_mem(work/"source2.mem", source2, 4)
    cpu.write_mem(work/"expected2.mem", expected2, 4)
    cpu.write_mem(work/"masks2.mem", mask2.astype(np.uint8), 1)
    for name, value in (("crc2.mem", cpu.pixel_crc(expected2)), ("sourcecrc2.mem", cpu.pixel_crc(source2))):
        with (work/name).open("x", encoding="ascii", newline="\n") as stream:
            stream.write(value.lower()+"\n")
    flags = {"SyntheticInput": True, "DevelopmentOnly": True, "CalibrationAccepted": False,
             "HardwareReleaseAllowed": False, "NewLensCorrectionVerified": False, "PreBitGateExecutionProven": False,
             "HardwareAccessed": False, "PDSAccessed": False, "SimulationExecuted": False, "RTLResultUsedForGolden": False}
    third = {"Schema": 1, "SequenceFrameIndex": 2, "FrameID": 3, "BankExpected": 0,
             "Width": width, "Height": height, "PixelCount": count, "Length": 2*count,
             "TextureKind": "source0_rgb565_word_xor_0x5A3C", "SourceXORConstant": XOR_WORD,
             "SourceBaseMetadata": _file(inputs[0][0]), "EverySourcePixelChangedFromFrame0": bool(np.all(source2 != source0)),
             "ExpectedPixelsChangedFromFrame0": changed_expected,
             "SourcePixelCRC32": cpu.pixel_crc(source2), "ExpectedPixelCRC32": cpu.pixel_crc(expected2),
             "MaskByteCRC32": mask_crc, "IntegerConfig": a["IntegerConfig"], "RadiusGuardQ22": a["RadiusGuardQ22"],
             "Model": a["Model"], "Rotation": a["Rotation"], "ExpectedGammaMode": 0,
             "GammaEnableRequired": False, "FirstCompleteFrameAfterReset": False,
             "Statistics": statistics, "IndependentScalarCoordinateChecksPassed": True, **flags}
    for index, frame in enumerate([*frames, third]):
        frame["Files"] = {name: _file(work/f"{name}{index}.mem") for name in MEM_NAMES}
    _deadline(started, maximum_seconds)
    after = {path: sha(path) for path in watched}
    if watched != after:
        raise ValueError("reference/input source changed; sequence remains unsealed")
    third["ReferenceSHA256"] = watched; third["ReferenceSHA256After"] = after
    _json(work/"frame2-vectors.json", third)
    frames.append({**third, "Metadata": _file(work/"frame2-vectors.json")})
    result = {"Schema": 1, "SequenceGenerated": True, "CreatedUtc": datetime.now(timezone.utc).isoformat(),
              "Width": width, "Height": height, "FrameCount": 3, "FrameIDs": [1, 2, 3], "BankExpected": [0, 1, 0],
              "PixelCounts": [count]*3, "PayloadLengths": [2*count]*3,
              "Frames": frames, "ConfigInclude": _file(work/"config.vh"),
              "IntegerConfigNames": a["IntegerConfigNames"], "IntegerConfig": a["IntegerConfig"],
              "RadiusGuardQ22": a["RadiusGuardQ22"], "FixedPoint": a["FixedPoint"], "Rotation": a["Rotation"],
              "ExpectedGammaMode": 0, "GammaEnableRequired": False,
              "WordOrder": a["WordOrder"], "CRCByteOrder": a["CRCByteOrder"],
              "ReferenceSHA256": watched, "ReferenceSHA256After": after, "InputsAndReferencesUnchanged": True,
              "MaximumSeconds": maximum_seconds, "ElapsedSeconds": time.monotonic()-started, **flags,
              "Limits": "Synthetic fixed-zero-degree GM0 CPU fixtures only. Use each frame's crcN and sourcecrcN; config VEC_EXPECTED_CRC32 still means frame0. Original metadata is preserved as provenance, not relabeled as a continuous RTL result. Frame2 has no legacy TextureVariant=2 claim. New golden was bilinearly remapped from changed source pixels, not XORed from expected0. No sensor, physical fps, PDS, timing, calibration or RTL acceptance."}
    _deadline(started, maximum_seconds)
    _json(work/"sequence.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vectors0", type=Path, required=True)
    parser.add_argument("--vectors1", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--maximum-seconds", type=float, default=180.)
    args = parser.parse_args(argv)
    try:
        record = generate_sequence(args.vectors0, args.vectors1, args.output_dir, maximum_seconds=args.maximum_seconds)
    except (ValueError, OSError) as error:
        parser.exit(1, str(error)+"\n")
    print(json.dumps({"Sequence": str(args.output_dir.resolve()/"sequence.json"), "Width": record["Width"],
                      "Height": record["Height"], "FrameIDs": record["FrameIDs"], "BankExpected": record["BankExpected"],
                      "SourceCRC32": [frame["SourcePixelCRC32"] for frame in record["Frames"]],
                      "ExpectedCRC32": [frame["ExpectedPixelCRC32"] for frame in record["Frames"]],
                      "ElapsedSeconds": record["ElapsedSeconds"], "CalibrationAccepted": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
