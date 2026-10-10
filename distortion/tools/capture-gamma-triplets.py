"""Finite physical capture, or offline replay, of raw/bypass/Gamma triplets."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import subprocess
import time
import cv2
import numpy as np
from frame_protocol import FrameParser
from gamma_triplets import GammaTripletAssembler
from frozen_gamma_analysis import analyze, geometry, metrics

ROOT = Path(__file__).resolve().parents[1]
read = lambda path: json.loads(path.read_text(encoding='utf-8-sig'))


def program(target, log_path):
    env = {k: v for k, v in os.environ.items() if k.upper() != 'PSMODULEPATH'}
    with log_path.open('w', encoding='utf-8') as log:
        result = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            str(ROOT/'tools/program-heartbeat.ps1'), '-Target', target, '-Frequency', '5MHz'],
            stdout=log, stderr=subprocess.STDOUT, timeout=120, env=env)
    if result.returncode:
        raise RuntimeError(f'{target} transfer failed; see {log_path}')
    status = read(ROOT/'status.json')
    if status['current_sram_target'] != target:
        raise RuntimeError('Fresh SRAM target confirmation is missing')
    evidence = sorted((ROOT/'build'/target).glob('program-evidence-*/transfer.json'), key=lambda p: p.stat().st_mtime)
    proof = read(evidence[-1])
    if not proof['Done'] or proof['Target'] != target or proof['CheckedOn'] != status['current_connection']['checked_on']:
        raise RuntimeError('Fresh DONE transfer proof differs from current state')
    return proof


def save_group(out, triplet, coordinates, mask, kind):
    record, images = analyze(triplet, coordinates, mask, kind)
    folder = out/f'group-{triplet.group_id:08d}'
    folder.mkdir()
    for name, image in images.items():
        np.save(folder/(name+'.npy'), image, allow_pickle=False)
        if name != 'mask':
            rgb = metrics.expand(image).astype(np.uint8)
            ok, encoded = cv2.imencode('.png', rgb[..., ::-1])
            if not ok:
                raise RuntimeError('Failed to encode capture preview')
            encoded.tofile(folder/(name+'.png'))
    record['files_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir()}
    (folder/'comparison.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'group': triplet.group_id, 'mode': triplet.mode, 'passed': record['passed'],
                      'bypass_mismatches': record['bypass_mismatched_pixels'],
                      'tone_mismatches': record['tone']['mismatched_pixels']}), flush=True)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replay', type=Path)
    parser.add_argument('--reference', type=Path, default=ROOT/'build/gamma_frozen_native_20261008_sim/reference.json')
    parser.add_argument('--port', default='COM5')
    parser.add_argument('--target',default='gamma_capture',choices=('gamma_capture','gamma_capture_settled','gamma_capture_colorbars','gamma_capture_settled_d5','gamma_capture_colorbars_d5'))
    parser.add_argument('--groups', type=int, default=1)
    parser.add_argument('--seconds', type=float, default=24)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--scene-label', default='unspecified', help='Preparation label; classification comes from captured pixels')
    args = parser.parse_args()
    if not 1 <= args.seconds <= 24 or not 1 <= args.groups <= 3:
        raise ValueError('Capture must finish within 24 seconds; require 1-3 groups')
    if not args.replay and args.groups!=1:
        raise ValueError('One physical VGA triplet per thermal window; replay may contain three groups')
    ref = read(args.reference)
    if ref['shape'] != [480, 640] or ref.get('radius_guard') != 1976439:
        raise ValueError('Use the board-matched native 640x480 bounded reference')
    coordinates, mask = geometry(ref['parameters'], radius_bound=ref['radius_guard'])
    out = args.output or ROOT/'captures/gamma-triplets'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    out = out.resolve()
    # Output is append-only and must stay in this project.
    if not out.is_relative_to(ROOT.resolve()):
        raise ValueError('Capture output must stay in the project')
    out.mkdir(parents=True, exist_ok=False)
    stream_parser, assembler, groups = FrameParser(), GammaTripletAssembler(), []
    result = {'recorded_utc': datetime.now(timezone.utc).isoformat(), 'passed': False,
              'source_kind': 'synthetic_same_source' if args.replay or args.target.startswith('gamma_capture_colorbars') else 'physical_same_source',
              'hardware_accessed': not bool(args.replay), 'groups': groups,
              'target': args.target,
              'input_origin': 'sensor_internal_test_pattern' if args.target.startswith('gamma_capture_colorbars') else ('offline_replay' if args.replay else 'optical_camera_scene'),
              'scene_label': args.scene_label,
              'reference_sha256': hashlib.sha256(args.reference.read_bytes()).hexdigest()}
    error = None
    def receive(data):
        for frame in stream_parser.feed(data):
            triple = assembler.feed(frame)
            if triple:
                groups.append(save_group(out, triple, coordinates, mask, result['source_kind']))
                if len(groups) >= args.groups:
                    return True
        return False
    try:
        if args.replay:
            result['replay_sha256'] = hashlib.sha256(args.replay.read_bytes()).hexdigest()
            with args.replay.open('rb') as source:
                while data := source.read(65536):
                    if receive(data):
                        break
        else:
            import serial
            # Open before programming: opening after download loses the first
            # raw packet and would exceed the finite thermal window.
            with serial.Serial(args.port, 921600, timeout=.25, dsrdtr=False, rtscts=False, xonxoff=False) as port:
                port.set_buffer_size(rx_size=4194304, tx_size=4096)
                port.reset_input_buffer()
                try:
                    result['capture_transfer'] = program(args.target, out/'program-capture.log')
                    deadline = time.monotonic()+args.seconds
                    with (out/'received-stream.bin').open('wb') as stream:
                        while time.monotonic() < deadline:
                            data = port.read(min(max(port.in_waiting, 1), 65536))
                            stream.write(data)
                            if receive(data):
                                break
                finally:
                    # Release COM5 before the cooling transaction.
                    port.close()
                    result['idle_transfer'] = program('heartbeat', out/'idle-after-capture.log')
    except Exception as exc:
        error = exc
        result['error'] = f'{type(exc).__name__}: {exc}'
    finally:
        assembler.finish()
        result.update({'rejected_packets': stream_parser.rejected, 'discarded_stream_bytes': stream_parser.discarded,
                       'incomplete_groups': assembler.incomplete_groups, 'orphan_packets': assembler.orphan_packets,
                       'passed': error is None and len(groups) == args.groups and stream_parser.rejected == 0
                           and assembler.incomplete_groups == 0 and assembler.orphan_packets == 0
                           and all(g['passed'] for g in groups)})
        (out/'summary.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'passed': result['passed'], 'groups': len(groups), 'directory': str(out)}), flush=True)
    if error is not None:
        raise error
    if not result['passed']:
        raise SystemExit('Incomplete or mismatched triplet capture; retained diagnostic files')


if __name__ == '__main__':
    main()
