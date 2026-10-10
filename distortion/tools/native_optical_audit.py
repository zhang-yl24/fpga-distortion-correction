"""Audit corrected-D5 physical triplets; numerical and optical evidence stay separate."""
from pathlib import Path
import hashlib,json,importlib.util,zlib
import cv2
import numpy as np
from frozen_gamma_analysis import metrics

ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()
spec=importlib.util.spec_from_file_location('grid_metrics',ROOT/'tools/check-grid-straightness.py')
grid=importlib.util.module_from_spec(spec);spec.loader.exec_module(grid)
cv2.setNumThreads(1);cv2.ocl.setUseOpenCL(False)

def load_group(folder):
    folder=Path(folder).resolve()
    if not folder.is_relative_to(ROOT):raise ValueError('Capture outside workspace')
    summary=read(folder.parent/'summary.json');comparison=read(folder/'comparison.json')
    if not summary.get('passed') or not summary.get('hardware_accessed') or summary.get('input_origin')!='optical_camera_scene' or summary.get('target')!='gamma_capture_settled_d5':
        raise ValueError('Need corrected-D5 physical optical data')
    if not comparison['passed'] or comparison['bypass_mismatched_pixels'] or comparison['tone']['mismatched_pixels']:
        raise ValueError('Same-source numerical regression failed')
    transfers=summary['capture_transfer'],summary['idle_transfer']
    if not all(t['Done'] for t in transfers) or transfers[0]['Target']!=summary['target'] or transfers[1]['Target']!='heartbeat':
        raise ValueError('Actual finite capture/idle proof missing')
    build_dir=ROOT/'build/gamma_capture_settled_d5'
    if not (build_dir/'validated-build.json').is_file():
        build_dir=ROOT.parent/'handoff/baseline/gamma_capture_settled_d5'
    build=read(build_dir/'validated-build.json')
    bitstream=build_dir/'generate_bitstream/gamma_capture_settled_d5.sbit'
    if transfers[0]['SHA256']!=build['SHA256'] or sha(bitstream)!=build['SHA256']:
        raise ValueError('Capture not bound to corrected bitstream')
    if not any(g['group_id']==comparison['group_id'] and g['passed'] for g in summary['groups']):
        raise ValueError('Group missing from completed capture')
    images={}
    for index,name in enumerate(('raw','before','after','mask')):
        path=folder/(name+'.npy')
        if sha(path)!=comparison['files_sha256'][path.name].upper():raise ValueError('Pixels/mask changed: '+name)
        image=np.load(path,allow_pickle=False)
        if image.shape!=(480,640):raise ValueError('Not native VGA')
        if name!='mask':
            if image.dtype!=np.uint16:raise ValueError('Not RGB565 words')
            if f'{zlib.crc32(image.astype("<u2").tobytes()):08X}'!=comparison['crc32'][index].upper():raise ValueError('Pixel CRC differs from UART')
            png=folder/(name+'.png')
            if sha(png)!=comparison['files_sha256'][png.name].upper():raise ValueError('PNG changed')
            actual=cv2.imdecode(np.fromfile(png,dtype=np.uint8),cv2.IMREAD_COLOR)
            expected=metrics.expand(image).astype(np.uint8)[...,::-1]
            if actual is None or not np.array_equal(actual,expected):raise ValueError('PNG differs from RGB565')
        images[name]=image
    return summary,comparison,images

def color_stats(words):
    rgb=metrics.expand(words).reshape(-1,3).astype(float)
    means=rgb.mean(axis=0);medians=np.median(rgb,axis=0)
    return {'samples':len(rgb),'mean_rgb_code':means.tolist(),'median_rgb_code':medians.tolist(),
        'green_minus_red_code':float(means[1]-means[0]),'green_minus_blue_code':float(means[1]-means[2]),
        'any_channel_at_max_fraction':float(np.mean(np.any(rgb==255,axis=1))),
        'all_channels_zero_fraction':float(np.mean(np.all(rgb==0,axis=1)))}

def corners_in_valid_domain(corners, exclusion_mask):
    rounded=np.rint(np.asarray(corners)).astype(int)
    h,w=exclusion_mask.shape
    if np.any(rounded[:,0]<0) or np.any(rounded[:,0]>=w) or np.any(rounded[:,1]<0) or np.any(rounded[:,1]>=h):
        return False
    # Frozen capture mask is True for excluded geometry, not valid pixels.
    return not bool(exclusion_mask[rounded[:,1],rounded[:,0]].any())

def analyze(folder,kind,output):
    output=Path(output).resolve()
    if not output.is_relative_to(ROOT):raise ValueError('Output outside workspace')
    output.parent.mkdir(parents=True,exist_ok=True)
    folder=Path(folder).resolve();summary,comparison,images=load_group(folder)
    result={'hardware_accessed_by_analyzer':False,'input_origin':summary['input_origin'],'target':summary['target'],
        'scene_label':summary['scene_label'],'group_id':comparison['group_id'],'source_crc32':comparison['crc32'][0],
        'summary_sha256':sha(folder.parent/'summary.json'),'comparison_sha256':sha(folder/'comparison.json'),
        'capture_transfer':summary['capture_transfer'],'idle_transfer':summary['idle_transfer'],
        'kind':kind,'numerical_regression_passed':True,'full_optical_acceptance':False}
    if kind=='neutral':
        result['roi_xywh']=[160,120,320,240]
        result['statistics']={name:color_stats(images[name][120:360,160:480]) for name in ('raw','before','after')}
        result['limits']='Descriptive channel code differences on user-positioned white paper. Not calibrated color error or proof that a ROI is entirely neutral. Lighting spectrum, exposure and quantization matter; Gamma is not white-balance correction.'
    elif kind=='grid':
        overlays=[];rows={}
        for name in ('raw','before'):
            row,overlay=grid.measure(folder/(name+'.png'));rows[name]=row
            if overlay is not None:overlays.append(overlay)
        result['grid']=rows;complete=all(r['all_54_corners_detected'] for r in rows.values())
        result['measurement_complete']=complete
        if complete:
            corners=np.array(rows['before']['corners_px'])
            if not corners_in_valid_domain(corners,images['mask']):raise ValueError('Detected corners outside valid mapping domain')
            for key in ('equal_line_rms_px','equal_line_rms_fraction_of_span'):
                raw=rows['raw'][key];corrected=rows['before'][key]
                result[key+'_reduction_percent']=100*(raw-corrected)/raw if raw>1e-12 else None
            path=output.with_suffix('.png');cv2.imencode('.png',np.hstack(overlays))[1].tofile(path)
            result['corner_overlay']=str(path)
        result['limits']='Independent grid collinearity, no lens refit. One pose does not establish all-field calibration. Pixel and span-normalized residuals are both reported; perspective, print flatness and interpolation affect the result.'
    else:raise ValueError('Unknown audit kind')
    result['source_sha256']={name:sha(ROOT/name) for name in ('tools/native_optical_audit.py','tools/check-grid-straightness.py')}
    output.write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--group',type=Path,required=True)
    p.add_argument('--kind',choices=('neutral','grid'),required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=analyze(a.group,a.kind,a.output)
    print(json.dumps({k:r[k] for k in ('numerical_regression_passed','measurement_complete','statistics','equal_line_rms_px_reduction_percent','equal_line_rms_fraction_of_span_reduction_percent') if k in r}))
