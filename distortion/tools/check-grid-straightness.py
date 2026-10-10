"""Measure planar grid collinearity without fitting the distortion model.

Corner localization and print flatness remain limitations; this is not a
calibrated optical accuracy or resolution acceptance test.
"""
from pathlib import Path
import argparse, hashlib, json, zlib
import cv2
import numpy as np
cv2.setNumThreads(1)
cv2.ocl.setUseOpenCL(False)
ROOT=Path(__file__).resolve().parents[1]

def line_residual(points):
    points=np.asarray(points,dtype=np.float64)
    if len(points)<3 or not np.isfinite(points).all():raise ValueError('Invalid line points')
    center=points.mean(axis=0)
    _,s,v=np.linalg.svd(points-center,full_matrices=False)
    if s[0]<1e-6:raise ValueError('Degenerate grid line')
    distances=np.abs((points-center)@v[-1])
    span=np.linalg.norm(points[-1]-points[0])
    if span<1e-6:raise ValueError('Degenerate grid span')
    return {'rms_px':float(np.sqrt(np.mean(distances**2))),
        'max_px':float(distances.max()),'span_px':float(span),
        'rms_fraction_of_span':float(np.sqrt(np.mean(distances**2))/span)}

def grid_residual(corners):
    grid=np.asarray(corners,dtype=np.float64).reshape(6,9,2)
    rows=[line_residual(row) for row in grid]
    cols=[line_residual(grid[:,c]) for c in range(9)]
    all_lines=rows+cols
    return {'rows':rows,'columns':cols,
        'equal_line_rms_px':float(np.sqrt(np.mean([l['rms_px']**2 for l in all_lines]))),
        'equal_line_rms_fraction_of_span':float(np.sqrt(np.mean([l['rms_fraction_of_span']**2 for l in all_lines]))),
        'max_corner_line_deviation_px':max(l['max_px'] for l in all_lines)}

def measure(path):
    image=cv2.imdecode(np.fromfile(path,dtype=np.uint8),cv2.IMREAD_COLOR)
    if image is None or image.shape[:2]!=(480,640):raise ValueError('Expected native 640x480 image')
    gray=cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    ok,corners=cv2.findChessboardCornersSB(gray,(9,6),cv2.CALIB_CB_NORMALIZE_IMAGE|cv2.CALIB_CB_EXHAUSTIVE|cv2.CALIB_CB_ACCURACY)
    result={'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest().upper(),
        'all_54_corners_detected':bool(ok),'image_shape':[480,640]}
    if not ok:return result,None
    result.update(grid_residual(corners));result['corners_px']=corners.reshape(54,2).tolist()
    overlay=image.copy();cv2.drawChessboardCorners(overlay,(9,6),corners,ok)
    return result,overlay

def validate_pair(folder):
    comparison=folder/'comparison.json'
    check=json.loads(comparison.read_text())
    for name,key in (('raw-source','raw_crc32'),('fpga-corrected','fpga_crc32')):
        binary=(folder/(name+'.rgb565')).read_bytes()
        if len(binary)!=614400 or f'{zlib.crc32(binary):08X}'!=check[key].upper():raise ValueError('Historical pixel CRC changed')
        p=np.frombuffer(binary,dtype='<u2').reshape(480,640).astype(np.uint32)
        r=(p>>11)&31;g=(p>>5)&63;b=p&31
        bgr=np.stack(((b<<3)|(b>>2),(g<<2)|(g>>4),(r<<3)|(r>>2)),axis=-1).astype(np.uint8)
        image=cv2.imdecode(np.fromfile(folder/(name+'.png'),dtype=np.uint8),cv2.IMREAD_COLOR)
        if not np.array_equal(image,bgr):raise ValueError('Historical PNG differs from sensor pixels')
    return {'path':str(comparison),'sha256':hashlib.sha256(comparison.read_bytes()).hexdigest().upper(),
        'raw_crc32':check['raw_crc32'],'fpga_crc32':check['fpga_crc32'],
        'raw_and_fpga_png_match_original_rgb565':True}

def main():
    p=argparse.ArgumentParser();p.add_argument('--pair',action='append',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve()
    if not out.is_relative_to(ROOT):raise ValueError('Output outside project')
    out.parent.mkdir(parents=True,exist_ok=True)
    report={'hardware_accessed':False,'method':'SVD total least squares, separate 6 rows and 9 columns; no lens model fitted',
        'opencv_version':cv2.__version__,'grid_inner_corners':[9,6],
        'limits':'Subpixel detector, print flatness, sensor noise and interpolation affect residuals. Perspective preserves planar straight lines. This measures visible grid collinearity only, not absolute geometric accuracy, MTF, peripheral scene lines, or independent full optical acceptance.',
        'pairs':[]}
    for n,folder in enumerate(a.pair):
        folder=folder.resolve()
        if not folder.is_relative_to(ROOT):raise ValueError('Pair outside project')
        evidence=validate_pair(folder)
        raw,raw_overlay=measure(folder/'raw-source.png')
        corrected,corrected_overlay=measure(folder/'fpga-corrected.png')
        pair={'folder':str(folder),'raw':raw,'fpga':corrected,
            'historical_pixel_evidence':evidence,
            'measurement_complete':raw['all_54_corners_detected'] and corrected['all_54_corners_detected']}
        if pair['measurement_complete']:
            before=raw['equal_line_rms_px'];after=corrected['equal_line_rms_px']
            pair['rms_reduction_percent']=100*(before-after)/before if before>1e-12 else None
            panel=np.hstack((raw_overlay,corrected_overlay))
            path=out.parent/f'grid-straightness-pair{n:02d}.png'
            cv2.imencode('.png',panel)[1].tofile(path)
            pair['corner_overlay']=str(path)
        report['pairs'].append(pair)
    report['measured_pairs']=sum(p['measurement_complete'] for p in report['pairs'])
    report['source_sha256']={str(Path(__file__).resolve().relative_to(ROOT)):hashlib.sha256(Path(__file__).read_bytes()).hexdigest().upper()}
    out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'measured_pairs':report['measured_pairs'],'pairs':[{'folder':p['folder'],'complete':p['measurement_complete'],'rms_reduction_percent':p.get('rms_reduction_percent')} for p in report['pairs']]}))

if __name__=='__main__':main()
