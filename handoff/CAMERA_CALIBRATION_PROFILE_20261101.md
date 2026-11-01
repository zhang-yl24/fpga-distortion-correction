> 2026-11-01最新实板结果：本次实际镜头矫正位流已下载，用户确认画面持续更新、直线明显变直，LED5/6闪烁、LED7常灭。首次实屏观察通过；仍为640×480有效相机图像，后续再评估帧率/1080p。见[矫正构建与实屏交接](CAMERA_VGA_CALIBRATED_BUILD_20261101.md)。下方为标定/构建阶段历史。

# 当前镜头标定与离线矫正（2026-11-01）

当前任务继续保持 OV5640 CAM2 → 畸变处理 → HDMI OUT，在640×480完成矫正后再讨论1080p与帧率。HDMI IN保持暂停。

## 已完成

- 12张训练、6张独立验证全部采完，原图640×480 RGB565_LE。棋盘7×10方格、6×9内角点、25mm；每次摆好后稳定至少10秒。明确选入的18张均54角点、CRC通过、无单图质量警告，已逐张复核overlay。
- 训练RMS **0.217101px**，验证均值 **0.219665px**，验证最大 **0.358012px**；原门槛0.5/0.5/1.0px未改。正式profile的K/D与纯训练诊断完全相同，验证数据未用于拟合。
- 训练3×3角点累计`[[47,114,46],[44,269,84],[15,29,0]]`；验证`[[14,38,28],[68,138,20],[4,14,0]]`。固定FPGA/转接板遮挡右下，仅明确排除[2,2]覆盖验收，其余8格训练≥15、验证≥3通过。不是精确遮挡轮廓，不代表全画幅光学验收，也没有施加显示遮罩。
- 已按真实K/D生成离线矫正对照图，棋盘线条视觉上变直。它是软件预览，不是新位流实屏验收。

## 软件反解修复与独立验证

OpenCV4.11的`fisheye.undistortPoints`会在反解前把畸变半径截断至π/2。训练图7/8超过这个畸变坐标半径，但同一拟合模型推导的最大前向光线角约85.027°。不能把畸变半径直接当成光线角，也不能删掉边缘训练图绕过检查。

新增`distortion/tools/fisheye_forward_inverse.py`：显式启用`bounded_monotone_bisection_v1`，证明[0°,88°]内严格单调（最小导数1.0），64次有界二分、不截断观测坐标、拒绝域外点；仅允许浮点边界舍入余量。固定K/D，solvePnP只估计棋盘外参，检查全部点z>0，以原始畸变像素计算误差。88°在验证误差计算前根据训练数据确定，是工程模型域，不是镜头FOV实测。

`calibrate_fisheye_profile.py`保留默认OpenCV路径，只有manifest显式选择才用新路径。合成投影往返、中心/边界/域外、非单调、K/D错误、旧默认兼容、验证扰动不改变K/D、范围/选图拒绝等 **38项测试、14个子例通过**。独立只读审查也检查了数值方法；最终实现和测试由主代理完成。

冻结记录`profiles/validation-freeze-a.json`先于正式验证，随后回读全部来源SHA确认无变化。源码依据：[OpenCV4.11 fisheye.cpp](https://raw.githubusercontent.com/opencv/opencv/4.11.0/modules/calib3d/src/fisheye.cpp)。双目旧工具的OpenCV适用域没有同步扩展，不要据此声称双目已支持。

## FPGA参数映射结果

原样使用相机K作输出K的映射失败：1440坐标溢出、64个定点折叠样本，最大有效坐标误差4.448586px；失败报告保留，没有放宽0.25px门槛。

对输出焦距240/280/320分别完整检查，均通过。选择三个已检方案中视野最宽的 **f=240、中心(319.5,239.5)、640×480、旋转0°**：

- 全307200坐标最大误差 **0.056592px**、RMS0.010015px；溢出0、参考/定点折叠0，所有双线性邻域在源图边界内。
- 新`MAX_RADIUS_Q22`至少 **11610104**，旧8388608不能直接沿用。
- 输出视野比原始鱼眼收窄；不声称最宽可行方案。K/D未更改，输出视图选择不属于重新拟合镜头。
- 仅检查0°；不能直接用该记录放行其他旋转角。矩形边界内和低坐标误差不等于遮挡区/完整视野光学验收。

## 当前状态与下一步

更新：用户现已确认断电，当前SRAM配置失效。后续候选进度见[离板构建交接](CAMERA_VGA_CALIBRATED_BUILD_20261101.md)。下面板上配置描述是断电前的历史状态。

板上仍为`raw_camera_capture_cam2_delay` / bit-d3-a，SHA256 `292b755c8bdf5f16e8697b87fc1c9ae1dbb342226404c9f647eb27030b501fa3`。本轮只通过COM7只读采图，所有采集进程均正常退出，没有再次JTAG下载；当前不需要用户继续举棋盘。没有矫正位流、没有矫正上板验收。

下一步建立独立calibrated VGA候选：使用审计过的f240整数参数与新radius guard；先跑真实RTL逐坐标/逐像素回放，再做源码/引脚/CDC/双角时序/位流绑定检查。准备好上板时先告知用户；如果此后断电，先确认重新上电，再下载。不要重跑已过的采图工程EDA，也不要修改已封存来源。

## 证据入口

会话根：`distortion/work/camera-vga-calibration-20261031/`。

- `capture-progress.json`：明确选中18张，未选attempt留存；held02选a03、held04选a04，其他held选a01。
- `dataset-scoped-a.json`：SHA256 `a195198bb07ec580b7080a68e1e570f2c69ec22ff13177f593c8d68dc29432e1`。
- `profiles/fisheye-profile-a.json`：SHA256 `94181c07a4456f511853f51022eba1b55965b115e1569f3fcbad460a2d92999e`，candidate_ready_for_profile_review=true，hardware_release_allowed=false。
- `reports/calibration-review-a.json`、`reports/brown-mapping-f240-a.json`、`profiles/output-k-f240-a.json`。
- `previews/held05-raw-vs-corrected-f240-a.png`：仅本地软件对照图。

[数值标定封存包](../distortion/results/camera-vga-calibration-20261101-a/README.md)包含41项文件、18份原图本地引用；manifest SHA256 `cec6b65f0e7629ff8d9a012a288e28b576329cc330379207801bbc964e872a58`。原始现场RGB565/PNG和预览仍留本机work，未复制到可推送包。封存含脚本快照及质量角点，缺少本地像素时不能重做标定。

本轮新采图/标定开发和封存仍本地未提交/推送；此前已推送的正立显示基线是另一阶段。
