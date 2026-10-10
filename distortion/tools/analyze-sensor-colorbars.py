"""Classify internal OV5640 bars independently of the frozen remap/Gamma reference."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from frozen_gamma_analysis import metrics
ROOT=Path(__file__).resolve().parents[1]
names=('white','yellow','cyan','green','magenta','red','blue','black')
palette=np.array([[255,255,255],[255,255,0],[0,255,255],[0,255,0],
    [255,0,255],[255,0,0],[0,0,255],[0,0,0]],dtype=float)

def main():
    p=argparse.ArgumentParser();p.add_argument('capture',type=Path);a=p.parse_args()
    folder=a.capture.resolve()
    if not folder.is_relative_to(ROOT.resolve()):raise ValueError('Capture outside project')
    summary=json.loads((folder/'summary.json').read_text())
    if not(summary['passed'] and summary['hardware_accessed'] and summary['target'] in ('gamma_capture_colorbars','gamma_capture_colorbars_d5')
        and summary['input_origin']=='sensor_internal_test_pattern'):
        raise ValueError('Need completed sensor-generated physical capture with idle proof')
    group=folder/'group-00000001';check=json.loads((group/'comparison.json').read_text())
    raw=group/'raw.npy'
    if hashlib.sha256(raw.read_bytes()).hexdigest()!=check['files_sha256']['raw.npy']:
        raise ValueError('Raw capture SHA changed')
    pixels=np.load(raw,allow_pickle=False)
    if pixels.shape!=(480,640):raise ValueError('Expected native VGA')
    def describe(frame):
        rgb=metrics.expand(frame).astype(float)
        medians=np.stack([np.median(rgb[120:360,x-12:x+12].reshape(-1,3),axis=0) for x in range(40,640,80)])
        distance=np.max(np.abs(medians[:,None,:]-palette[None,:,:]),axis=2)
        labels=distance.argmin(axis=1)
        errors=distance[np.arange(8),labels]
        row_spread=np.stack([np.percentile(rgb[120:360,x-12:x+12].reshape(-1,3),[5,95],axis=0)
            for x in range(40,640,80)])
        order=[names[i] for i in labels]
        order_matches=order==list(names) or order==list(reversed(names))
        accepted=order_matches and np.max(errors)<=40
        return {'central_bar_rgb_medians':medians.tolist(),'observed_order':order,
            'max_channel_distance_to_ideal_per_bar':errors.tolist(),
            'within_bar_p05_p95_rgb':row_spread.tolist(),'order_matches_expected':order_matches,
            'levels_within_40_codes_of_ideal':bool(np.max(errors)<=40),'accepted':bool(accepted)}
    normal=describe(pixels)
    swapped=describe(((pixels.astype(np.uint32)&255)<<8 | pixels.astype(np.uint32)>>8).astype(np.uint16))
    report={'hardware_accessed_by_analysis':False,'sensor_generated_input':True,'normal_byte_order':normal,
        'swapped_byte_order_counterexample':swapped,'passed':normal['accepted'] and not swapped['accepted'],
        'byte_order_color_sequence_check_passed':normal['order_matches_expected'] and not swapped['order_matches_expected'],
        'ideal_level_color_check_passed':normal['levels_within_40_codes_of_ideal'],
        'capture_summary_sha256':hashlib.sha256((folder/'summary.json').read_bytes()).hexdigest().upper(),
        'limits':'Classifies central regions of 8 internal sensor bars against known colors. Supports DVP/DDR/UART decoding, not optical AWB, illumination fidelity, HDMI transmitter colorimetry or monitor calibration. Synthetic sensor data is not a physical bright-light acceptance.'}
    output=folder/'sensor-colorbars-check.json'
    if output.exists() and not (folder/'sensor-colorbars-first-check.json').exists():
        (folder/'sensor-colorbars-first-check.json').write_bytes(output.read_bytes())
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'normal_order':normal['observed_order'],
        'median_rgb':normal['central_bar_rgb_medians'],
        'byte_order_sequence_passed':report['byte_order_color_sequence_check_passed'],
        'ideal_level_color_check_passed':report['ideal_level_color_check_passed']}))
    if not report['passed']:raise SystemExit('Sensor bar colors not accepted; retain diagnostic evidence')

if __name__=='__main__':main()
