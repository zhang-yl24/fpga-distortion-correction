"""Separate transformed raw corners from corners detected after resampling."""
from pathlib import Path
import hashlib
import json
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parents[1]
lab = root / 'results/lab-20261007'
cv2.setNumThreads(1)
candidate = json.loads((root / 'results/calibration-fpga-candidate-20261006/candidate.json').read_text())
k, d = np.array(candidate['K'], dtype=np.float64), np.array(candidate['D'], dtype=np.float64)

def rms(points):
    grid = points.reshape(6, 9, 2).astype(np.float64)
    errors = []
    for line in list(grid) + list(grid.transpose(1, 0, 2)):
        q = line - line.mean(axis=0)
        errors.extend(np.abs(q @ np.linalg.svd(q, full_matrices=False)[2][-1]))
    return float(np.sqrt(np.mean(np.square(errors))))

rows = []
for label, filename in (('中心', 'optical-pair-check.json'), ('左侧', 'optical-left-adjusted-pair-check.json')):
    proof = json.loads((lab / filename).read_text(encoding='utf-8-sig'))
    assert proof['passed']
    for pair in proof['pairs']:
        folder = Path(pair['directory'])
        images = [folder / 'raw-source.png', folder / 'fpga-corrected.png']
        corners = []
        grayscale_sensitivity=[]
        for path in images:
            bgr=cv2.imread(str(path))
            gray=cv2.cvtColor(bgr,cv2.COLOR_BGR2GRAY)
            ok, q = cv2.findChessboardCornersSB(gray, (9, 6),
                                              flags=cv2.CALIB_CB_NORMALIZE_IMAGE)
            assert ok, str(path)
            corners.append(q.astype(np.float64))
            direct=cv2.imread(str(path),cv2.IMREAD_GRAYSCALE)
            alt_ok,alt_q=cv2.findChessboardCornersSB(direct,(9,6),flags=cv2.CALIB_CB_NORMALIZE_IMAGE)
            grayscale_sensitivity.append({'image':path.name,'gray_pixel_max_difference':int(np.abs(gray.astype(np.int16)-direct.astype(np.int16)).max()),
                'alternate_grayscale_complete_board':bool(alt_ok),'alternate_grayscale_corner_rms_px':rms(alt_q) if alt_ok else None})
        transformed = cv2.fisheye.undistortPoints(corners[0], k, d, P=k)
        rows.append({'pose': label, 'directory': str(folder), 'raw_corner_rms_px': rms(corners[0]),
                     'model_transformed_raw_corner_rms_px': rms(transformed),
                     'detected_fpga_output_corner_rms_px': rms(corners[1]),
                     'grayscale_conversion_sensitivity':grayscale_sensitivity,
                     'image_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in images}})
result = {'hardware_accessed': False, 'records': rows, 'final_optical_accuracy_verified': False,
          'method': 'BGR image decode then cvtColor(BGR2GRAY), matching the main straightness evaluator. 54 raw corners are analytically transformed by the fitted fisheye model with P=K, then their row/column straightness is compared with raw corners and independently detected FPGA-output corners. Alternate direct grayscale decoding is reported separately as a localization sensitivity check.',
          'limits': 'Two physical poses only. Transforming raw corners removes image resampling from that diagnostic but retains corner localization and fitted-model error. Differences do not uniquely identify a cause, prove optical accuracy, or validate new overlap/adaptive video binaries. No calibration or coefficients were changed.'}
(lab / 'physical-straightness-diagnostic.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
plt.rcParams.update({'font.family': 'Microsoft YaHei', 'text.color': 'black', 'axes.labelcolor': 'black',
                     'xtick.color': 'black', 'ytick.color': 'black'})
fig, ax = plt.subplots(figsize=(9, 4.5), layout='constrained')
x = np.arange(len(rows))
for offset, key, title, color in ((-.23, 'raw_corner_rms_px', '原图角点', '#5A8AC4'),
                                (0, 'model_transformed_raw_corner_rms_px', '原图角点经镜头模型变换', '#679B8B'),
                                (.23, 'detected_fpga_output_corner_rms_px', '重采样图重新检测角点', '#7544AB')):
    values = [r[key] for r in rows]
    bars = ax.bar(x + offset, values, .23, label=title, color=color)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value, f'{value:.3f}', ha='center', va='bottom')
ax.set_xticks(x, [r['pose'] for r in rows])
ax.set(ylabel='棋盘直线残差 RMS（像素）', title='有限实拍诊断：镜头模型变换与重采样角点检测分别检查')
ax.set_ylim(0, max(r[key] for r in rows for key in ('raw_corner_rms_px', 'model_transformed_raw_corner_rms_px', 'detected_fpga_output_corner_rms_px')) * 1.35)
ax.spines[['top', 'right']].set_visible(False)
ax.legend(frameon=False)
fig.supxlabel('仅两组姿态；不能唯一归因，不能证明最终光学精度。低照度、打印平整度、角点定位与重采样均会影响测量。', fontsize=10)
fig.savefig(lab / 'physical-straightness-diagnostic.png', dpi=150)
plt.close(fig)
print(json.dumps(result, ensure_ascii=False, indent=2))
