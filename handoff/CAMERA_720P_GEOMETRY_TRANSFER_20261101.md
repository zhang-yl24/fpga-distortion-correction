# 720p 镜头参数几何转移诊断（2026-11-01）

本次新增离线工具 `distortion/tools/camera720_geometry_transfer.py` 和对应测试。它解决的是：在 VGA 与当前 720p 模式的像素坐标之间，检验是否存在固定的横纵缩放与平移，进而评估既有镜头参数能否作为 720p 候选。它不生成已验收镜头标定文件，不修改已验证 VGA profile，也不下载 FPGA 或访问串口。

截至本记录，工具测试使用合成角点和明确标记为 `offline_uart_replay` 的合成 RGB565/PNG 数据。**尚未取得真实的 VGA/720p 同姿态配对数据；720p 镜头矫正尚未因此完成。** 当前上板 720p transport 的方向、更新和 LED 反馈不能代替光学验证。

## 依据和范围

- 源 profile：`distortion/results/camera-vga-calibration-20261101-a/profiles/fisheye-profile-a.json`。
- 源相机/镜头：`ov5640-cam2-current-20261031` / `current-installed-lens-20261031`。目标必须维持这两个身份，使用新的模式和 profile 身份。
- 当前原生 720p 采图工具约定目标 `capture_mode_id=current720-rgb565-upright-3820-41-3821-07`，`profile_id=current720-current-lens-uncalibrated`。实际输入仍须与采图元数据精确一致。
- 寄存器审查见 `distortion/work/camera720-orientation-crop-review.md`；采图后续依据见 `distortion/work/camera720-optical-capture-next-note.md`。VGA 和 720p 的传感器窗口、采样/偏移存在区别，不能仅按宽高比分别乘 2 和 1.5。

若实际配对证据支持像素中心坐标关系：

```text
[u720, v720, 1]^T = A * [uVGA, vVGA, 1]^T
A = [[sx, 0, tx], [0, sy, ty], [0, 0, 1]], sx > 0, sy > 0
K720_candidate = A * K_VGA
D720_candidate = D_VGA
```

这里保持 D 的前提是同一镜头与同一成像几何，仅图像坐标采样/裁剪改变。工具只允许正轴向缩放和平移，不把旋转、反射、切变拟合进 A。A 使用 OpenCV 检测角点的像素中心坐标；图像重采样可能产生半像素平移，不能仅凭输出尺寸猜测 tx/ty。

## 两种入口

从仓库根目录运行，输出父目录必须已存在，输出文件必须是全新名称。

### 仅计算明确假设的参数

```powershell
.venv/Scripts/python.exe -B -X utf8 distortion/tools/camera720_geometry_transfer.py distortion/results/camera-vga-calibration-20261101-a/profiles/fisheye-profile-a.json --hypothesis 2 2 0 -120 --target-mode current720-rgb565-upright-3820-41-3821-07 --target-profile current720-current-lens-uncalibrated --output distortion/work/camera720-geometry-transfer/unmeasured-math-example-a.json
```

**以上 `2 2 0 -120` 只是演示矩阵乘法与定点表示检查的假设，并非根据当前传感器寄存器或照片确认的 A，不能写入正式矫正参数。** 输出 `method=unmeasured_user_matrix_hypothesis`、`measured_target_images=0`、`numeric_pair_checks_passed=false`。成功退出只代表假设计算完成。

### 检测真实配对图并固定/验证 A

```powershell
.venv/Scripts/python.exe -B -X utf8 distortion/tools/camera720_geometry_transfer.py distortion/results/camera-vga-calibration-20261101-a/profiles/fisheye-profile-a.json --pairs path/to/paired-mode-manifest.json --output path/to/fresh-transfer-report.json
```

清单示意如下，路径相对于清单目录，`REPLACE_...` 必须替换为实际捕获文件的 SHA-256。每个姿态都需要完整 VGA 和 720p 原图、原始 RGB565 及采图元数据。不要拿数小时前的原标定图与新 720p 照片当作同姿态。

```json
{
  "schema": "camera720-paired-mode-geometry-v1",
  "target_identity": {
    "camera_id": "ov5640-cam2-current-20261031",
    "lens_id": "current-installed-lens-20261031",
    "profile_id": "current720-current-lens-uncalibrated",
    "capture_mode_id": "current720-rgb565-upright-3820-41-3821-07"
  },
  "camera_focus_and_mount_unchanged_declared": true,
  "board": {"cols": 6, "rows": 9, "square_mm": 25},
  "method": "fit_axis_aligned",
  "thresholds": {"rms_px": 0.5, "maximum_px": 1.5},
  "pairs": [
    {
      "pair_id": "fit-01", "pose_id": "physical-pose-01",
      "same_stationary_pose_declared": true, "split": "fit", "corner_order": "auto",
      "source": {"path": "fit-01-vga.png", "sha256": "REPLACE_VGA_IMAGE_SHA256", "metadata_path": "fit-01-vga.json", "metadata_sha256": "REPLACE_VGA_METADATA_SHA256"},
      "target": {"path": "fit-01-720.png", "sha256": "REPLACE_720_IMAGE_SHA256", "metadata_path": "fit-01-720.json", "metadata_sha256": "REPLACE_720_METADATA_SHA256"}
    },
    {
      "pair_id": "held-01", "pose_id": "physical-pose-02",
      "same_stationary_pose_declared": true, "split": "held_out", "corner_order": "auto",
      "source": {"path": "held-01-vga.png", "sha256": "REPLACE_VGA_IMAGE_SHA256", "metadata_path": "held-01-vga.json", "metadata_sha256": "REPLACE_VGA_METADATA_SHA256"},
      "target": {"path": "held-01-720.png", "sha256": "REPLACE_720_IMAGE_SHA256", "metadata_path": "held-01-720.json", "metadata_sha256": "REPLACE_720_METADATA_SHA256"}
    }
  ]
}
```

`6×9` 是用户已有 `7×10` 方格棋盘的内角点数量，格边长 25 mm。上述残差阈值是显式示例诊断预算，不是现有项目新增的光学验收阈值；真实使用应先确定预算，再观测结果，不能为通过而事后调宽。

- 每对内，棋盘需固定不动直到两个模式的采集都完成，模式切换/重新下载不能挪动相机、镜头、板架或棋盘。不同 fit/held-out 对应不同物理姿态；时间戳不同不等于姿态独立。
- 工具要求操作者明确声明姿态和安装/对焦未变化，但哈希与声明不能独立证实物理事实，因此报告一直保留 `physical_pose_identity_verified=false`。fit/held-out 任一模式的角点集合若在允许的编号对齐下重合（最大差不超过 `1e-6` 像素），即使改了 `pose_id` 也会拒绝。这个检查只排除数值重复：同姿态的两次带噪采集可能有不同字节和不同角点坐标，仍不能据此证明姿态独立。
- `fit_axis_aligned` 只由 fit 对估计 A，held-out 对不参与重拟合。最小诊断需要 fit 对和独立 held-out 对；这不是“用两对图完成镜头标定”的承诺。后续实际补拍量取决于误差和可见区域覆盖。
- 也可用 `method=supplied_axis_aligned` 并给出 `A_source_to_target`；此时所有对都必须为 held-out，工具不修正提供的 A。
- `corner_order=auto` 会评分 `identity/reverse_rows/reverse_cols/reverse_both` 四种棋盘编号对齐，不盲目将两种模式的同下标角点视为同一物理点。并列歧义拒绝；也可根据明确物理对应指定其中一种。held-out 的编号评分使用冻结的 A。无标记棋盘的对称性也可能掩盖真实像素翻转，尤其正对且居中的棋盘；正 A 和低误差不证明图像方向正确。报告始终标记 `image_pixel_orientation_verified=false`，方向需沿用独立的文字/非对称目标观察和传感器模式方向审查证据。
- 输入必须是完整原生 640×480/1280×720 图像，未做几何处理。复用现有校准输入验证：PNG 与 RGB565 解码逐像素一致、原始字节/CRC、各层 SHA-256、相机/镜头/模式身份一致；缺角点、重复内容、数据漂移均拒绝，不静默剔除失败图。
- 合成/replay 输入可测试软件，但报告标记来源；它们永不自动成为真实镜头证据。CLI 不接收手填角点数组替代原图。

## 报告如何解释

每对输出 RMS/最大误差、平均 XY 偏差、采用的角点编号对齐；同时列出 fit/held-out 的目标 3×3 区域角点数。它描述已观测角点的一致性，不表示空白格区域也通过。输入文件与工具都有哈希绑定。数值超预算仍输出报告，但配对模式退出码为 1。计算产生非有限值时明确拒绝；报告完整完成严格 JSON 序列化后才创建输出，避免序列化错误留下半份 JSON。

`intrinsics_quantization` 检查目标源 K 的 fx/fy/cx/cy 能否用 signed24、8 位小数表示，并遍历 921600 个源像素量化其 **K 表示** 产生的坐标误差。它没有检查输出 K、畸变系数、Brown 近似、完整反投影、取整地址或 FPGA 算术。`fpga_mapping_verified` 和 `brown_surrogate_verified` 始终为 false。

所有输出均为 `camera720-axis-mode-transfer-diagnostic-v1` 诊断封装，K/D 位于 `candidate_parameters`，不能作为原有校准器的 profile 直接装载。以下字段始终为 false：

```text
optical_calibration_accepted
hardware_release_allowed
hardware_accessed
drop_in_calibration_profile
source_heldout_acceptance_inherited
source_visibility_scope_inherited
independent_target_lens_validation_completed
image_pixel_orientation_verified
```

VGA 的已验收畸变模型、12 张训练/6 张留出记录与右下角遮挡说明仍保持原范围。该工具没有降低原有全新镜头标定流程的样本/覆盖要求，也没有把旧验证结果转为 720p 验收。若实际两种模式不满足固定 crop/scale，先查模式/姿态和数据来源，必要时做独立 720p 标定；不能用任意仿射或调宽误差掩盖变化。

## 验证

```powershell
.venv/Scripts/python.exe -B -X utf8 -m pytest -q distortion/tests/test_camera720_geometry_transfer.py
```

2026-11-01：33 passed。覆盖已知鱼眼投影、跨模式编号反转、冻结 held-out A、姿态泄漏/镜头身份/非有限与缺点拒绝、剪切反射矩阵拒绝、定点全像素计算、原生 720p RGB565+PNG 解码与实际 SB 检测、元数据与原始字节损坏、重新压缩 PNG 也不能复用同一原始帧、CLI 不覆盖既有输出。独立审查后的回归还覆盖：实际像素反转可被棋盘对称性掩盖但方向 flag 保持 false；改名复用 fit/held-out 几何被拒绝；有限极值输入的中间溢出被拒绝；序列化失败不创建部分 JSON。测试中的图像均为离线合成证据，不涉及硬件。

审查记录：`distortion/work/camera720-geometry-peer-review.md`。初版 23 项测试的证据和算术例子保留为历史记录；修订后测试记录为 `distortion/work/camera720-geometry-transfer/pytest-b.xml`，新版算术例子为同目录 `unmeasured-math-example-b.json`。两份例子均不含实拍或光学验收结果。
