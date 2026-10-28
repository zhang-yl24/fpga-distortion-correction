"""Read-only, exact K320 development triplet replay; no device/program API."""
from __future__ import annotations
import argparse
import base64
import hashlib
import html
import json
from pathlib import Path

import cv2
import numpy as np
from frame_protocol import FrameParser
from gamma_triplets import GammaTripletAssembler
from frozen_gamma_analysis import analyze, geometry, metrics
import prepare_gamma_capture_k320_dev as candidate

cv2.ocl.setUseOpenCL(False)
PACKET_BYTES = 614400 + 44


def check_wire(wire):
    verified = candidate.verify()
    binding = verified["ProfileBinding"]
    if type(wire) is not bytes or len(wire) != 3*PACKET_BYTES:
        raise ValueError("Exactly one complete three-VGA-packet stream required")
    parser, assembler = FrameParser(), GammaTripletAssembler()
    frames = parser.feed(wire)
    if len(frames) != 3 or parser.rejected or parser.discarded or parser.buffer:
        raise ValueError("Triplet wire contains malformed, extra or incomplete bytes")
    triplet = None
    for frame in frames:
        triplet = assembler.feed(frame)
    if (triplet is None or triplet.group_id != candidate.GROUP_SEED or assembler.completed_groups != 1
            or assembler.orphan_packets or assembler.incomplete_groups):
        raise ValueError("Expected this build's one-shot group seed in raw/bypass/Gamma order")
    coordinates, mask = geometry(binding["IntegerConfig"], radius_bound=binding["RadiusGuardQ22"])
    # The legacy numerical evaluator accepts physical/synthetic categories only.
    # Offline bytes have no hardware attestation; never select its physical path.
    record, images = analyze(triplet, coordinates, mask, "synthetic_same_source")
    record.update(Target=candidate.TARGET, DevelopmentOnly=True, CalibrationAccepted=False,
                  HardwareReleaseAllowed=False, HardwareAccessed=False,
                  SourceIsPhysicalReadbackAttested=False,
                  InputOrigin="offline_replay_not_hardware_attested",
                  ProfileBinding=binding, CandidateSourceSHA256=verified["SourceSHA256"],
                  WireSHA256=hashlib.sha256(wire).hexdigest(), WireBytes=len(wire),
                  SameSourceMeaning="Numerical check against the raw packet and source-bound frozen RTL contract; CRC is not hardware identity authentication.",
                  NativePixelsTransformed=False, DisplayRotationClockwiseDegrees=180,
                  Limits=candidate.LIMITS)
    return record, images, triplet


def save_replay(wire, prefix):
    prefix = Path(prefix).resolve()
    approved = (candidate.ROOT / "build/offline-20261024").resolve()
    if not prefix.parent.is_dir() or not prefix.is_relative_to(approved):
        raise ValueError("Output prefix requires existing approved scratch parent")
    record, images, _ = check_wire(wire)
    names = [prefix.with_name(prefix.name+"-"+kind+".png") for kind in ("raw", "before", "after")]
    paths = [*names, prefix.with_suffix(".json"), prefix.with_suffix(".html")]
    if any(p.exists() for p in paths):
        raise ValueError("Refuse to overwrite replay outputs")
    embeds = []
    for name, kind in zip(names, ("raw", "before", "after")):
        rgb = metrics.expand(images[kind]).astype(np.uint8)
        ok, encoded = cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        if not ok:
            raise ValueError("Cannot encode lossless native RGB565 expansion")
        blob = encoded.tobytes()
        with name.open("xb") as out:
            out.write(blob)
        embeds.append("data:image/png;base64,"+base64.b64encode(blob).decode())
    record["Images"] = {kind: {"Path": str(p), "SHA256": candidate.sha(p)} for kind, p in zip(("raw", "before", "after"), names)}
    with paths[-2].open("x", encoding="utf-8") as out:
        json.dump(record, out, indent=2, allow_nan=False); out.write("\n")
    labels = ("原始输入", "同源矫正 / bypass", "同源矫正 + Gamma")
    identity = html.escape(json.dumps(record["ProfileBinding"]["Identity"], ensure_ascii=False))
    page = ('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>K320 开发三联读回</title>'
            '<style>body{font:16px sans-serif;color:#000;background:#fff;margin:24px}main{display:flex;gap:16px;flex-wrap:wrap}section{flex:1;min-width:300px}img{width:100%;image-rendering:auto;transform:rotate(180deg)}code{overflow-wrap:anywhere}</style>'
            '<h1>K320 开发三联读回</h1><p>仅显示层旋转180°；保存的原生像素未转向。开发参数，标定尚未验收。离线回放不证明实板来源。</p>'
            '<p>Gamma mode='+str(record["mode"])+'；逐像素数值校验='+str(record["passed"])+ '</p><code>'+identity+'</code><main>')
    page += ''.join('<section><h2>'+label+'</h2><img alt="'+label+'" src="'+src+'"></section>' for label, src in zip(labels, embeds))
    with paths[-1].open("x", encoding="utf-8") as out:
        out.write(page+'</main></html>')
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args()
    result = save_replay(args.replay.read_bytes(), args.output_prefix)
    print(json.dumps({"passed": result["passed"], "mode": result["mode"], "hardware_accessed": False}))
    raise SystemExit(0 if result["passed"] else 1)
