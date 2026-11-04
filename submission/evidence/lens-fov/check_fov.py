"""Read-only KB4 source-camera FOV calculation; writes only sibling results.

Invert rho=theta*(1+k1 theta^2+...+k4 theta^8), reconstruct unit rays,
then measure ray-pair angles. Do not use pinhole FOV or twice a maximum angle.
Run with the repository .venv/Scripts/python.exe from any working directory.
"""
from pathlib import Path
import hashlib
import json
import math
import platform

import cv2
import numpy as np
import scipy
from scipy.optimize import brentq


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROFILE = ROOT / 'distortion/work/hdmi-camera-snapshot-20261102-a/new-lens-fisheye-1080-c.json'
MANIFEST = PROFILE.with_name('new-lens-calibration-c.json')
CORNERS = ROOT / 'distortion/work/hdmi-kb-tangential-20261104-a/corners.npz'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(path):
    return {'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)}


def ray_angle(a, b):
    # atan2(cross length, dot) is robust both near zero and near 180 degrees.
    return math.degrees(math.atan2(float(np.linalg.norm(np.cross(a, b))), float(np.dot(a, b))))


def main():
    profile = json.loads(PROFILE.read_text(encoding='utf-8'))
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    assert sha(MANIFEST) == profile['source_fit']['sha256']
    assert profile['model'] == 'opencv_fisheye' and profile['native_size'] == [1920, 1080]
    k, d = np.asarray(profile['K_native'], float), np.asarray(profile['D_normalized'], float)
    fx, fy, cx, cy = k[0, 0], k[1, 1], k[0, 2], k[1, 2]

    def radial(theta):
        return theta * (1 + sum(d[i] * theta**(2*i+2) for i in range(4)))

    def inverse(pixels):
        pixels = np.asarray(pixels, dtype=float)
        normalized = (pixels - [cx, cy]) / [fx, fy]
        rho = np.linalg.norm(normalized, axis=-1)
        theta = np.array([brentq(lambda t: radial(t)-r, 0, np.pi/2, xtol=1e-14)
                          if r else 0 for r in rho.ravel()]).reshape(rho.shape)
        scale = np.divide(np.sin(theta), rho, out=np.ones_like(rho), where=rho != 0)
        rays = np.concatenate((normalized*scale[..., None], np.cos(theta)[..., None]), axis=-1)
        return rays, theta

    angles = np.linspace(0, np.pi/2, 10001)
    derivative = 1 + sum((2*i+3)*d[i]*angles**(2*i+2) for i in range(4))
    assert derivative.min() > 0, 'KB radial inversion is not unique in the checked interval'
    rows = {}
    validation_pixels = []
    for name, extent in [
        ('native_pixel_centers', [0., 0., 1919., 1079.]),
        ('native_pixel_boundaries', [-.5, -.5, 1919.5, 1079.5]),
        ('snapshot_box_centers_in_native', [.5, .5, 1918.5, 1078.5]),
    ]:
        left, top, right, bottom = extent
        pixels = np.array([[left, cy], [right, cy], [cx, top], [cx, bottom],
                           [left, top], [right, top], [right, bottom], [left, bottom]])
        rays, theta = inverse(pixels)
        rows[name] = {
            'extent_left_top_right_bottom': extent,
            'point_order': ['left_at_cy', 'right_at_cy', 'top_at_cx', 'bottom_at_cx',
                            'top_left', 'top_right', 'bottom_right', 'bottom_left'],
            'pixel_coordinates': pixels.tolist(),
            'unit_rays': rays.tolist(),
            'theta_deg': np.degrees(theta).tolist(),
            'horizontal_through_principal_point_deg': ray_angle(rays[0], rays[1]),
            'vertical_through_principal_point_deg': ray_angle(rays[2], rays[3]),
            'diagonal_top_left_to_bottom_right_deg': ray_angle(rays[4], rays[6]),
            'diagonal_top_right_to_bottom_left_deg': ray_angle(rays[5], rays[7]),
        }
        validation_pixels.extend(pixels)

    loaded = np.load(CORNERS)
    corners = loaded['corners'] * 2 + .5
    train, held = loaded['train_indices'], loaded['held_out_indices']
    assert corners.shape == (35, 54, 2)
    assert train.tolist() == manifest['train_indices'] and held.tolist() == manifest['held_out_indices']
    assert len(train) == 28 and len(held) == 7 and not set(train) & set(held)
    assert sorted(list(train)+list(held)) == list(range(35))
    coverage = {}
    for label, indices in [('all', np.arange(35)), ('training', train), ('held_out', held)]:
        pixels = corners[indices].reshape(-1, 2)
        rays, theta = inverse(pixels)
        degrees = np.degrees(theta)
        hull = cv2.convexHull(pixels.astype(np.float32))
        coverage[label] = {
            'views': len(indices), 'corner_count': len(pixels),
            'bbox_native_xy_min_max': [pixels.min(axis=0).tolist(), pixels.max(axis=0).tolist()],
            'convex_hull_area_fraction_of_sensor_rectangle': float(cv2.contourArea(hull)/(1920*1080)),
            'max_theta_deg': float(degrees.max()),
            'theta_percentiles': {'quantiles': [50, 90, 95, 99, 100],
                                  'degrees': np.percentile(degrees, [50, 90, 95, 99, 100]).tolist()},
            'corners_above_70deg': int((degrees > 70).sum()),
            'corners_above_75deg': int((degrees > 75).sum()),
        }
    validation_pixels = np.concatenate((np.asarray(validation_pixels), corners.reshape(-1, 2), [[cx, cy]]))
    rays, _ = inverse(validation_pixels)
    projected = cv2.fisheye.projectPoints(rays.reshape(1, -1, 3), np.zeros(3), np.zeros(3), k, d)[0].reshape(-1, 2)
    roundtrip = float(np.max(np.linalg.norm(projected-validation_pixels, axis=1)))
    normalized_cv = cv2.fisheye.undistortPoints(validation_pixels.reshape(1, -1, 2), k, d).reshape(-1, 2)
    rays_cv = np.column_stack((normalized_cv, np.ones(len(normalized_cv))))
    rays_cv /= np.linalg.norm(rays_cv, axis=1)[:, None]
    ray_difference = float(np.max(np.linalg.norm(rays-rays_cv, axis=1)))
    assert roundtrip < 1e-7 and ray_difference < 1e-9
    assert abs(np.linalg.norm(rays, axis=1)-1).max() < 1e-12

    result = {
        'schema': 'kb4-source-camera-fov-check-v1',
        'analysis_date_Asia_Shanghai': '2026-11-04',
        'camera_profile': 'deployed KB4 ed59f83e3cfbc77b; not KB4-T2 experimental refit',
        'sources': {'profile': source(PROFILE), 'calibration_manifest': source(MANIFEST),
                    'corners': source(CORNERS), 'script': source(Path(__file__))},
        'versions': {'python': platform.python_version(), 'numpy': np.__version__,
                     'scipy': scipy.__version__, 'opencv': cv2.__version__},
        'K_native': k.tolist(), 'D_order': ['k1', 'k2', 'k3', 'k4'], 'D': d.tolist(),
        'method': 'Invert KB angular polynomial on [0,pi/2], construct unit ray, atan2(norm(cross),dot) for ray-pair angle',
        'fov': rows,
        'observed_corner_coverage': coverage,
        'checks': {'radial_min_derivative_0_to_90deg': float(derivative.min()),
                   'independent_opencv_roundtrip_max_native_px': roundtrip,
                   'independent_opencv_unit_ray_max_difference': ray_difference,
                   'validation_point_count': len(validation_pixels)},
        'interpretation': {
            'source_image_not_output_projection': True,
            'seller_160_axis_unspecified': True,
            'horizontal_160_supported_by_this_fit': False,
            'diagonal_160_class_is_plausible_but_not_verified': True,
            'corner_ray_fov_uses_extrapolation_beyond_training_angles': True,
            'precision_is_numerical_not_measurement_uncertainty': True,
        },
        'hardware_accessed': False, 'formal_calibration_or_report_modified': False,
    }
    (HERE/'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    current = rows['native_pixel_centers']
    bounds = rows['native_pixel_boundaries']
    text = f'''# 原始鱼眼镜头视场核对（KB4）

日期：2026-11-04。使用现部署的 `ed59f83e3cfbc77b` 四参数KB鱼眼标定，未使用新试验KB4-T2参数，未修改正式参数、报告或硬件。

## 计算结果

以下是1920×1080原始源画面的模型估计，区别于校正输出约125°的透视视场。

| 口径 | 水平（穿主点） | 垂直（穿主点） | 左上—右下对角 | 右上—左下对角 |
|---|---:|---:|---:|---:|
| 原生像素中心0..1919、0..1079 | {current['horizontal_through_principal_point_deg']:.3f}° | {current['vertical_through_principal_point_deg']:.3f}° | {current['diagonal_top_left_to_bottom_right_deg']:.3f}° | {current['diagonal_top_right_to_bottom_left_deg']:.3f}° |
| 原生像素边界−0.5..1919.5、−0.5..1079.5 | {bounds['horizontal_through_principal_point_deg']:.3f}° | {bounds['vertical_through_principal_point_deg']:.3f}° | {bounds['diagonal_top_left_to_bottom_right_deg']:.3f}° | {bounds['diagonal_top_right_to_bottom_left_deg']:.3f}° |

实用表述：**源画面水平约142°、垂直约77°、对角约167°（依当前标定模型估计）。**

计算先对每个边缘像素做归一化，再反解 `rho=theta*(1+k1*theta²+k2*theta⁴+k3*theta⁶+k4*theta⁸)`，构造三维单位射线；视场取两条相应射线的实际夹角。没有套用针孔公式 `2atan(W/2f)`，也没有把最大角点半角简单乘2。四角半角约81.4°–85.5°，因主点偏移等原因，两对角夹角并非最大半角的两倍。

## 与卖家约160°的关系

- 若160°指对角视场，它与当前模型估计的约167°属于相近的超广角量级，但这不是对卖家精确规格的独立验收。
- 若160°指这一路1920×1080画面的水平视场，当前拟合的约142°不支持该说法。传感器比例、实际输出裁剪及卖家的视场定义仍需对应。
- 现有对角计算超出了标定角点实际覆盖的角度范围，不能给出精确实测视场或有统计意义的误差条。

## 拟合覆盖与外推限制

使用用户确认的2026-11-03凌晨原始HDMI棋盘图：35张有效视图，28张训练、7张留出，每张54角点；原图960×540为2×2灰度平均，原生坐标为 `2*corner+0.5`。

- 训练角点最大离轴角 **{coverage['training']['max_theta_deg']:.3f}°**；1512角点中仅{coverage['training']['corners_above_70deg']}个超过70°，没有角点超过75°。
- 留出角点最大离轴角 **{coverage['held_out']['max_theta_deg']:.3f}°**。
- 原生四角需要约81.4°–85.5°离轴角，均高于训练数据覆盖；因此对角FOV对高阶多项式外推敏感。
- 训练角点凸包覆盖传感器矩形面积约{100*coverage['training']['convex_hull_area_fraction_of_sensor_rectangle']:.1f}%；全35张角点凸包约{100*coverage['all']['convex_hull_area_fraction_of_sensor_rectangle']:.1f}%。凸包只是分布摘要，不代表覆盖区域内每处均有观测。

## 数值核验

- KB角度多项式在0–90°最小导数为{float(derivative.min()):.6f}>0，反解在该区间唯一。
- 独立OpenCV正向投影往返最大误差：{roundtrip:.3g}原生像素。
- 与OpenCV反投影单位射线最大差：{ray_difference:.3g}。
- 完整输入SHA、射线、两套像素边界口径、角点覆盖和软件版本保存在 `result.json`。上述小数位只表示数值计算精度，不代表标定或镜头规格精度。

复现：从仓库根目录执行

```powershell
.venv/Scripts/python.exe distortion/work/fisheye-fov-check-20261104-a/check_fov.py
```

脚本只读取现有标定和角点，在本目录重写 `result.json`、`README.md`。
'''
    (HERE/'README.md').write_text(text, encoding='utf-8')
    print(json.dumps({'native_pixel_centers': {key: value for key, value in current.items() if key.endswith('_deg')},
                      'coverage_max_theta_deg': {key: value['max_theta_deg'] for key, value in coverage.items()},
                      'checks': result['checks']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
