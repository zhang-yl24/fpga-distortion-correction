"""Offline, diagnostic slanted-edge SFR. No ISO compliance or optical acceptance claim.

Reference: https://www.imatest.com/imaging/sharpness/
Reference: https://www.imatest.com/2015/04/lsf-correction-factor-for-slanted-edge-mtf-measurements/
"""
from pathlib import Path
import argparse, hashlib, json
import numpy as np

ROOT=Path(__file__).resolve().parents[1]

def measure(gray):
    a=np.asarray(gray,dtype=float)
    if a.ndim!=2 or min(a.shape)<64 or not np.isfinite(a).all():
        raise ValueError('Need a finite ROI at least 64 pixels in both dimensions')
    if a.min()<0 or a.max()>255:raise ValueError('ROI must use 0..255 luminance codes')
    # Near-horizontal edges are transposed, never resampled.
    transposed=np.mean(np.abs(np.diff(a,axis=0)))>np.mean(np.abs(np.diff(a,axis=1)))
    if transposed:a=a.T
    h,w=a.shape
    left=a[:,:8].mean();right=a[:,-8:].mean()
    if abs(right-left)<16:raise ValueError('Low contrast or no single edge')
    if np.mean((a<=0)|(a>=255))>.05:raise ValueError('Too many endpoint codes; recapture without clipping')
    rising=right>left
    if not rising:a=255-a
    derivative=np.diff(a,axis=1)
    weight=np.maximum(derivative,0)
    weight[weight<weight.max(axis=1,keepdims=True)*.1]=0
    if np.any(weight.sum(axis=1)<=0):raise ValueError('Edge missing on a scan line')
    centers=(weight*(np.arange(w-1)+.5)).sum(axis=1)/weight.sum(axis=1)
    y=np.arange(h);slope,intercept=np.polyfit(y,centers,1)
    slant=float(np.degrees(np.arctan(abs(slope))))
    if not 1.5<=slant<=10:raise ValueError('Slant must be 1.5..10 degrees from the sampling axis')
    fit=slope*y+intercept;rms=float(np.sqrt(np.mean((centers-fit)**2)))
    if rms>.35:raise ValueError('Edge is curved, multiple or unstable; choose a straighter ROI')
    if fit.min()<34 or fit.max()>w-35:raise ValueError('Edge too near ROI boundary; enlarge the ROI')
    d=(np.arange(w)[None,:]-fit[:,None])/np.sqrt(1+slope*slope)
    step=.25;half=32;count=int(2*half/step)
    bins=np.floor((d+half)/step).astype(int);valid=(bins>=0)&(bins<count)
    populations=np.bincount(bins[valid],minlength=count)
    if populations.min()<8:raise ValueError('Insufficient oversampled edge coverage')
    esf=np.bincount(bins[valid],weights=a[valid],minlength=count)/populations
    x=(np.arange(count)+.5)*step-half
    # Central differences require the sinc correction below.
    lsf=(esf[2:]-esf[:-2])/(2*step)
    window=np.hamming(lsf.size)
    frequency=np.fft.rfftfreq(4096,d=step)
    spectrum=np.abs(np.fft.rfft(lsf*window,n=4096))
    if spectrum[0]<=1e-9:raise ValueError('Degenerate DC response')
    z=2*np.pi*frequency*step
    correction=np.ones_like(z);nz=z!=0
    correction[nz]=np.minimum(10,np.abs(z[nz]/np.sin(z[nz])))
    mtf=spectrum/spectrum[0]*correction
    keep=frequency<=.5;frequency=frequency[keep];mtf=mtf[keep]
    crossings=np.flatnonzero(mtf<=.5)
    mtf50=None
    if crossings.size:
        i=int(crossings[0])
        if i>0:mtf50=float(np.interp(.5,mtf[i-1:i+1][::-1],frequency[i-1:i+1][::-1]))
    return {'mtf50_cycles_per_pixel':mtf50,'mtf50_below_nyquist':mtf50 is not None,
        'slant_deg':slant,'edge_fit_rms_px':rms,'transposed':bool(transposed),
        'contrast_code':float(abs(right-left)),'edge_rising_original':bool(rising),
        'min_bin_samples':int(populations.min()),'frequency_cycles_per_pixel':frequency.tolist(),
        'sfr':mtf.tolist(),'edge_distance_px':x.tolist(),'edge_spread_code':esf.tolist(),
        'method':'4x distance binning, straight edge fit, central derivative correction, Hamming window',
        'limits':'Diagnostic SFR of supplied pixel codes. Not an ISO 12233 implementation or calibrated lens MTF. ISP response, sharpening, print quality, curvature and magnification affect results. A null MTF50 means no crossing below Nyquist, not a pass.'}

def capture_pixels(folder,kind,roi,exponent=1):
    folder=Path(folder).resolve()
    if not folder.is_relative_to(ROOT):raise ValueError('Capture outside project')
    summary=json.loads((folder.parent/'summary.json').read_text(encoding='utf-8-sig'))
    if summary.get('target')!='gamma_capture_settled_d5' or summary.get('input_origin')!='optical_camera_scene' or not summary['passed']:
        raise ValueError('Need a complete corrected-D5 optical capture; historical or internal patterns are excluded')
    comparison=json.loads((folder/'comparison.json').read_text(encoding='utf-8-sig'))
    path=folder/(kind+'.npy')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if comparison['files_sha256'][path.name].lower()!=digest:raise ValueError('Capture pixels changed')
    words=np.load(path,allow_pickle=False)
    if words.shape!=(480,640) or words.dtype!=np.uint16:raise ValueError('Expected native RGB565 words')
    x,y,w,h=roi
    if min(x,y)<0 or min(w,h)<64 or x+w>640 or y+h>480:raise ValueError('Invalid native ROI')
    if kind!='raw':
        mask_path=folder/'mask.npy'
        if hashlib.sha256(mask_path.read_bytes()).hexdigest()!=comparison['files_sha256']['mask.npy'].lower():raise ValueError('Geometry mask changed')
        if not np.load(mask_path,allow_pickle=False)[y:y+h,x:x+w].all():raise ValueError('ROI intersects invalid geometry')
    if not np.isfinite(exponent) or not 1<=exponent<=4:raise ValueError('Response exponent must be 1..4')
    r=(words>>11)&31;g=(words>>5)&63;b=words&31
    rgb=np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),axis=-1).astype(float)/255
    gray=255*((rgb**exponent)@np.array([.2126,.7152,.0722]))
    return gray[y:y+h,x:x+w],{'file':str(path),'sha256':digest,'roi_xywh':roi,
        'group_id':comparison['group_id'],'source_crc32':comparison['crc32'][0],
        'response_exponent_assumption':exponent,'hardware_accessed':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--group',type=Path,required=True)
    p.add_argument('--kind',choices=('raw','before','after'),required=True)
    p.add_argument('--roi',type=int,nargs=4,required=True);p.add_argument('--response-exponent',type=float,default=1)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve()
    if not out.is_relative_to(ROOT):raise ValueError('Output outside project')
    image,provenance=capture_pixels(a.group,a.kind,a.roi,a.response_exponent)
    result=measure(image);result['provenance']=provenance
    result['optical_acceptance_complete']=False
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('mtf50_cycles_per_pixel','slant_deg','edge_fit_rms_px','optical_acceptance_complete')}))

if __name__=='__main__':main()
