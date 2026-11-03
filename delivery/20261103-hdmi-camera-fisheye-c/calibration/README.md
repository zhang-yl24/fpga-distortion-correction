# 当前 C 版镜头标定与使用参数

本目录对应已经写入易失 SRAM 的 `hdmi_camera_fisheye_top` C 基线。位流 SHA256 `8c43a77d9ddce72dc7015ef7f63aabe37ab6758dd698e2e811b669c5aa5ba047`，标定原件 SHA256 `ed59f83e3cfbc77b0c876293129955fea96aec21784e520592111506671b81af`，与板上 ProfileID `ed59f83e3cfbc77b` 一致。用户已确认矫正效果正常及 KEY1 原图/矫正往返切换，仍报告迟滞和卡顿；该基线矫正约 4.3 个新画面/秒，原图约 30 个新画面/秒。

`calibration.json` 是明确标注的便携派生参数：保留原 JSON 的精确浮点值，使用相对的原件和图像引用；没有重新拟合或改写冻结参数。`originals/` 中的两份 JSON、标定报告和两张电脑预览图与原件逐字节一致，哈希见 `assets-sha256.json`。

## 原生 1920×1080 参数

模型为 **OpenCV fisheye**，D 的顺序为 `[k1,k2,k3,k4]`，不得当作 Brown 的径向/切向系数使用。

```text
K_source = [[808.2272613458829, 0, 943.7446431879945],
            [0, 810.0804859591761, 556.5635877240222],
            [0, 0, 1]]
D = [-0.023025039402366058, 0.0010939325830845673,
     -0.004404026888512618, 0.0010249559182549826]
```

当前 C 部署投影使用 `balance=0.5`、`R=I`、1920×1080 直线投影输出。输出内参与源内参分别保存，不能互换：

```text
K_output = [[498.5237444253359, 0, 895.4756299331018],
            [0, 499.66683439231093, 561.1161479755821],
            [0, 0, 1]]
```

部署投影来自已通过的 `profile-a/profile.json`，其原件 SHA256 为 `f176c34bec93646e82ddd0ad8755e1a828221aecf687e545ef9452331ddd9d8c`。FPGA 固定点实现使用 Q30 径向 ROM，参数对应的全 2,073,600 坐标验证最大误差约 0.0064 原生像素；这不是全视场光学误差。

## 标定图与对比图

- [真实棋盘训练图](calibration-board-training-view32.png)：960×540 GRAY8，完整拟合 `views[32]`，属于 28 张训练图之一，没有用于 7 张留出误差的计算。原始文件名、SHA256、训练身份和采样几何见 [逐图来源](selected-calibration-view.json)。该图保持原字节，选择了无现场人员、棋盘较大的视图；背景仍含小相框照片。
- [原图/矫正对比](originals/new-lens-calibration-comparison-c.png)：左侧未矫正，右侧为电脑 OpenCV 预览。它不是 FPGA HDMI 输出的采集帧。
- [电脑矫正预览](originals/new-lens-fisheye-preview-c.png)：`balance=0.5`。黑边反映该输出视场选择。

采图是原生 1920×1080 的 2×2 灰度降采样，几何关系为 `native = 2*snapshot + 0.5`。在 960×540 图片上使用 `calibration.json` 的 `snapshot_preview.K_snapshot` 和 `K_output_snapshot`；在 1920×1080 上使用 `K_native` 和 `rectification.K_output_native`。D 保持不变，不可把 1080 的 K 直接套在这张 540 图片上。

49 张真实采图中最终选用 35 个不同有效姿态，28 训练、7 留出；训练 RMS 0.381927 原生像素，留出平均 0.391519、最大 0.870875 原生像素。棋盘为 9×6 内角点、25mm 格距。`dataset/` 已包含完整 C 拟合使用的 **35 张有效原图**，逐字节匹配冻结拟合 JSON 的 `views`，保持原来的 28 训练 / 7 留出划分；[dataset-manifest.json](dataset-manifest.json) 列出每张的原索引、身份、相对路径、字节数、SHA256 和来源元数据哈希。未纳入其余 14 张近重复/角点不全图。上面的单张训练图是 `views[32]` 的便捷副本，SHA 与 dataset 中同图一致；两张预览另属同次标定交付。

## 数据集复现范围

35 张图均为原始 960×540 GRAY8 快照，未裁切、遮挡或改画面；部分包含现场人物、室内陈设及小相框照片。它们按用户要求作为实际标定图一并交付。逐图留出误差也写入 manifest，并保持原 JSON 中留出索引的顺序。

原始完整拟合 JSON 保存输入文件/元数据哈希、棋盘规格、训练/留出分组、K/D 和逐留出误差，**没有序列化逐角点坐标或逐视图外参**。现已附全部实际拟合图，可使用同一 9×6、25mm 棋盘规格重新检测角点，再按 manifest 的固定划分独立复算；此次打包没有重新检测或拟合，也不把重算结果宣称为原执行记录。精确部署参数可直接读取 `calibration.json`，无需重新拟合。

## 原件的历史状态

`originals/CALIBRATION_RESULT_C.md`、两份原始 JSON 在上板前生成，保留当时的 snapshot 固件、`fpga_rectification_deployed=false` 和“待接入 FPGA”等描述；这些字段描述该原件生成时的历史状态。当前部署状态由后来生成的 SRAM 回执和用户反馈覆盖，原件保持不改。

后续状态来源为仓库实板证据目录的 [SRAM 下载回执](../../../distortion/results/hdmi-camera-fisheye-live-20261103-a/program-c/receipt.json)、[用户观察](../../../distortion/results/hdmi-camera-fisheye-live-20261103-a/user-observation.json) 和三次 FPS 采集回执；精确 SHA 绑定在 `calibration.json`。正式 C 版 SRAM 下载于北京时间 2026-11-03 10:58:55 完成，DONE/器件 ID 确认，Flash 未写。完整全视场光学验收和端到端光学延迟测量仍未完成，用户目测确认不替代这两项量化结果。

原始 JSON/回执中的历史机器路径仅用于来源追溯；使用参数时不依赖这些路径。原始文件的预部署标记也不会阻止直接使用便携参数复现相同投影。
