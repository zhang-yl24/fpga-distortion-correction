"""Same-frame straightness check on complete detected physical checkerboards."""
from pathlib import Path
import argparse,hashlib,json
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parents[1];lab=root/'results/lab-20261007'
parser=argparse.ArgumentParser()
parser.add_argument('--capture',type=Path,default=lab/'optical-pair-check.json')
parser.add_argument('--output-prefix',default='physical-checkerboard-straightness')
args=parser.parse_args()
assert Path(args.output_prefix).name==args.output_prefix,'Output prefix must be a filename stem'
capture=json.loads(args.capture.read_text(encoding='utf-8-sig'));assert capture['passed']
cv2.setNumThreads(1)
def line_residuals(points):
    centered=points-points.mean(axis=0)
    _,_,vectors=np.linalg.svd(centered,full_matrices=False)
    return np.abs(centered@vectors[-1])
def measure(path):
    image=cv2.imread(str(path));assert image is not None
    found,corners=cv2.findChessboardCornersSB(cv2.cvtColor(image,cv2.COLOR_BGR2GRAY),(9,6),flags=cv2.CALIB_CB_NORMALIZE_IMAGE)
    if not found:return {'complete_board_detected':False},None
    grid=corners.reshape(6,9,2).astype(np.float64)
    distances=np.concatenate([line_residuals(row) for row in grid]+[line_residuals(column) for column in grid.transpose(1,0,2)])
    spacing=np.concatenate([np.linalg.norm(np.diff(grid,axis=1),axis=2).ravel(),np.linalg.norm(np.diff(grid,axis=0),axis=2).ravel()])
    return {'complete_board_detected':True,'corners':54,'line_count':15,'point_line_distances':108,
            'line_residual_rms_px':float(np.sqrt(np.mean(distances**2))),
            'line_residual_p95_px':float(np.percentile(distances,95)),'line_residual_max_px':float(distances.max()),
            'median_neighbor_spacing_px':float(np.median(spacing)),
            'corner_centroid_xy':grid.reshape(-1,2).mean(axis=0).tolist(),
            'corner_bounds_xyxy':[float(grid[...,0].min()),float(grid[...,1].min()),float(grid[...,0].max()),float(grid[...,1].max())],
            'normalized_rms_percent_spacing':float(100*np.sqrt(np.mean(distances**2))/np.median(spacing))},grid
records=[];panels=[]
for pair in capture['pairs']:
    folder=Path(pair['directory']);entry={'pair_id':pair['pair_id'],'source_packet_id':pair['source_packet_id'],'result_packet_id':pair['result_packet_id'],'mismatched_pixels':pair['mismatched_pixels']}
    for label,file in (('raw','raw-source.png'),('corrected','fpga-corrected.png')):
        path=folder/file;metrics,corners=measure(path);entry[label]=metrics
        metrics['image_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        panels.append((label,path,metrics,corners))
    if all(entry[k]['complete_board_detected'] for k in ('raw','corrected')):
        before=entry['raw']['line_residual_rms_px'];after=entry['corrected']['line_residual_rms_px']
        entry['rms_straightness_change_percent']=100*(1-after/before) if before else None
    records.append(entry)
result={'all_complete_boards_detected':all(p[k]['complete_board_detected'] for p in records for k in ('raw','corrected')),
        'hardware_accessed_by_analyzer':False,'fresh_physical_same_frame_pairs':len(records),'records':records,
        'source_capture_bitstream_sha256':capture['bitstream_sha256'],
        'method':'OpenCV findChessboardCornersSB, fixed 9x6 inner-corner topology; independent total-least-squares fit to each of 6 rows and 9 columns. 108 point-to-line distances per image. Native-pixel and spacing-normalized results are both reported.',
        'final_optical_accuracy_verified':False,
        'limits':'A limited fresh physical pose, not a multi-pose or cross-lens optical acceptance. Corner localization, printed-board flatness, low resolution and resampling affect this straightness metric. New images are not automatically independent of the calibration pose distribution. This capture uses the previously validated zero-rotation corrected_capture binary, not the new overlap/adaptive board candidates.'}
(lab/(args.output_prefix+'.json')).write_text(json.dumps(result,indent=2)+'\n')
plt.rcParams.update({'font.family':'Microsoft YaHei','text.color':'black'})
fig,axes=plt.subplots(1,len(panels),figsize=(6*len(panels),4.9),layout='constrained');axes=np.atleast_1d(axes)
for ax,(label,path,metrics,corners) in zip(axes,panels):
    image=cv2.cvtColor(cv2.imread(str(path)),cv2.COLOR_BGR2RGB);ax.imshow(image)
    name='同帧原图' if label=='raw' else 'FPGA矫正图'
    if corners is not None:
        ax.scatter(corners[...,0],corners[...,1],s=12,facecolors='none',edgecolors='#FFCC00',linewidths=.8)
        name+=f"：直线残差RMS {metrics['line_residual_rms_px']:.3f} px"
    else:name+='：完整9×6棋盘未检测到'
    ax.set_title(name);ax.set_axis_off()
fig.suptitle('实板读回图像：完整棋盘直线性检查',fontsize=16)
fig.supxlabel('单一新姿态的有限核查；不能替代多姿态光学精度、锐度或高分辨率验收。',fontsize=10)
fig.savefig(lab/(args.output_prefix+'.png'),dpi=150);plt.close(fig)
print(json.dumps(result,indent=2))
