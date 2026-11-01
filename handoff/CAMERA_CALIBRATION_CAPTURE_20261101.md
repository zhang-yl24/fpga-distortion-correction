# 当前镜头棋盘采集进度（2026-11-01）

主线保持当前640×480模式的真实镜头畸变矫正；1080p/帧率优化后置。

板上为raw_camera_capture_cam2_delay，位流SHA256 292b755c8bdf5f16e8697b87fc1c9ae1dbb342226404c9f647eb27030b501fa3。
用户已确认预览正立、左右正确且持续更新。UART COM7/921600输出完整640×480；HDMI预览160×120放大。

已保留训练候选12/12、独立留出6/6。均为54角点、CRC通过、无单图质量警告；尚无正式验收的K/D或矫正效果。
物理棋盘为7×10方格/6×9内角点/25mm，来自用户声明；每张保持平整，每次摆好后稳定至少10秒。

| 视图 | 分组 | 帧事务号 | CRC32 | 质量记录 |
| --- | --- | --- | --- | --- |
| train-01 | train | 282 | D3987120 | [quality](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-calibration-20261031/captures/train-01-a01/quality.json) |
| train-02 | train | 313 | E959353B | [quality](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-calibration-20261031/captures/train-02-a01/quality.json) |
| train-03 | train | 343 | A1CABCC6 | [quality](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-calibration-20261031/captures/train-03-a01/quality.json) |
| train-04 | train | 362 | 106349B7 | [quality](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-calibration-20261031/captures/train-04-a01/quality.json) |
| train-05 | train | 407 | 733B060B | [quality](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-calibration-20261031/captures/train-05-a02/quality.json) |
| train-06 | train | 437 | 301194B1 | [quality](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-calibration-20261031/captures/train-06-a01/quality.json) |
| train-07 | train | 458 | DADBCB97 | [quality](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-calibration-20261031/captures/train-07-a01/quality.json) |
| train-08 | train | 483 | F13BF4EE | [quality](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-calibration-20261031/captures/train-08-a01/quality.json) |
| train-09 | train | 533 | 9C4F7AEF | [quality](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-calibration-20261031/captures/train-09-a02/quality.json) |
| train-10 | train | 556 | 003AE6D0 | [quality](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-calibration-20261031/captures/train-10-a01/quality.json) |
| train-11 | train | 653 | 48245947 | [quality](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-calibration-20261031/captures/train-11-a01/quality.json) |
| train-12 | train | 703 | 9DADF9A4 | [quality](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-calibration-20261031/captures/train-12-a02/quality.json) |
| held-01 | held_out | 764 | 41FF725A | [quality](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-calibration-20261031/captures/held-01-a01/quality.json) |
| held-02 | held_out | 826 | F2BB936E | [quality](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-calibration-20261031/captures/held-02-a03/quality.json) |
| held-03 | held_out | 850 | 183E211E | [quality](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-calibration-20261031/captures/held-03-a01/quality.json) |
| held-05 | held_out | 933 | B071ADDE | [quality](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-calibration-20261031/captures/held-05-a01/quality.json) |
| held-06 | held_out | 950 | A6F4C96E | [quality](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-calibration-20261031/captures/held-06-a01/quality.json) |
| held-04 | held_out | 967 | F6E9CAB9 | [quality](D:/GravityLRT/thu/semester_4.5/FPGAchina/fpga-distortion-correction/distortion/work/camera-vga-calibration-20261031/captures/held-04-a04/quality.json) |

训练3×3角点累计：`[[47, 114, 46], [44, 269, 84], [15, 29, 0]]`。留出：`[[14, 38, 28], [68, 138, 20], [4, 14, 0]]`。
要求分区（行列从0起）：`[[0, 0], [0, 1], [0, 2], [1, 0], [1, 1], [1, 2], [2, 0], [2, 1]]`；每区至少训练15点/留出3点。不能仅凭视图数认为覆盖已满足。
用户确认FPGA/转接板实体遮挡右下视野、相机固定。仅本次覆盖验收保守排除右下格[2,2]，其余阈值不变；原九格覆盖不通过，不能声称全画幅光学验收。未修改原计划、显示图像或硬件。详见会话visibility-scope-20261101-a.json。

下一步：Capture complete:12 training and6 held-out. Assemble scoped dataset and complete train-only-driven forward inverse validation before freezing and evaluating held-out reprojection. No accepted correction profile or new bitstream yet.

真实状态与明确选中列表：`distortion/work/camera-vga-calibration-20261031/capture-progress.json`。
原图、metadata、quality及overlay均保留在该会话captures下；overlay不是标定输入。
留出姿态不能重复训练姿态，不用于拟合或根据其结果反复选参数；需要补拍时保留失败attempt并递增编号。
当前流程仍依赖用户保持本次上电状态；断电后旧绑定文件不能代替新的上电/下载确认。

## 采集后的正式数值结果

12训练/6验证采集完成；K/D数值候选验证通过，尚无矫正上板。训练RMS0.217101px，验证均值0.219665px、最大0.358012px。完整状态及下一步以[标定交接](CAMERA_CALIBRATION_PROFILE_20261101.md)为准。
