"""Offline analysis only. No serial port, hardware, reset or timing access."""
from pathlib import Path
import argparse,json,statistics,re
from stats_protocol import MixedParser,window


def analyze(raw,manifest,*,uninterrupted_reset_epoch):
    if manifest.get('fixed_mode')!=1 or manifest.get('gamma_enable')!=0:
        raise ValueError('requires source-bound fixed correction, gamma-off build manifest')
    if not re.fullmatch(r'[0-9a-fA-F]{64}',manifest.get('firmware_sha256','')):
        raise ValueError('requires an actual built fixed-mode firmware SHA256, not a source-only template')
    parser=MixedParser();packets=parser.feed(raw);parser.finish()
    snapshots=[v for k,v in packets if k=='PGSTAT02']
    if len(snapshots)<2:raise ValueError('need at least two requested hardware snapshots')
    if not snapshots[0]['last_process_valid'] or not snapshots[-1]['last_process_valid']:
        raise ValueError('steady processing window requires completed-frame validity at both endpoints')
    if any(v['state_flags'] & 0xC0 for v in snapshots):
        raise ValueError('failed pipeline or unexpected static snapshot is not a steady pure-correction window')
    if any(v['last_process_valid'] and v['completed_mode']!=1 for v in snapshots):
        raise ValueError('capture contains a completed raw/Gamma/other mode')
    if any(v['completed_param_id']!=manifest['param_id'] for v in snapshots if v['last_process_valid']):
        raise ValueError('parameter identity does not match build manifest')
    w=window(snapshots[0],snapshots[-1],uninterrupted_reset_epoch=uninterrupted_reset_epoch)
    distinct={}
    for v in snapshots:
        if v['last_process_valid']:distinct[(v['completed_frame_id'],v['completed_param_id'])]=v['last_process_cycles_including_final_edge']
    values=list(distinct.values())
    return dict(kind='internal_core_hardware_window_for_attested_fixed_mode',window=w,
        sampled_distinct_completed_frames=len(values),sampled_process_cycles_including_final_edge=values,
        sampled_process_cycles_median=statistics.median(values) if values else None,
        nominal_core_hz=snapshots[0]['nominal_core_hz'],
        limitations=['Last-cycle samples are not a complete per-frame latency distribution.',
            'PGSTAT02 dropped_frames is DMA rejected completion; unadmitted no-grant frames are not exported.',
            'This is internal processing/new-presentation timing, not exposure/input-pixel-to-monitor E2E.',
            'A fixed-mode build identity is required; matching first/last mode alone cannot prove a mixed AB window is pure.',
            'Calibration identity is provenance, not proof that K/D belongs to the new camera.'],
        firmware_sha256=manifest.get('firmware_sha256','NOT_BUILT'),external_E2E='UNMEASURED')


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--wire',type=Path,required=True)
    ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--uninterrupted-reset-epoch',action='store_true')
    a=ap.parse_args();print(json.dumps(analyze(a.wire.read_bytes(),json.loads(a.manifest.read_text()),
        uninterrupted_reset_epoch=a.uninterrupted_reset_epoch),indent=2))


if __name__=='__main__':main()
