# 当前板上鱼眼矫正 C 版（2026-11-03）

本包封存当前新 HDMI 摄像头的已上板版本 `hdmi_camera_fisheye_top` C。2026-11-03 北京时间 10:58:55 下载易失 SRAM 完成，器件 ID `0x00602899`、DONE 和清理通过，Flash 未写。用户已确认“正畸效果正常，但又迟滞和卡顿”，KEY1 原图/矫正往返切换正常。此处发布已下载的 C 基线，实板唯一新画面约 4.3 FPS；独立提速工作不属于本包。

## 直接查看

- [标定图、原图/矫正对比和参数说明](calibration/README.md)
- [便携参数 calibration.json](calibration/calibration.json)：精确原生 K、fisheye D、当前输出 K，balance=0.5
- [已下载位流](bitstreams/hdmi_camera_fisheye_top_C.sbit?raw=true)：3,791,112 字节
- [源码闭包及重建方法](SOURCE_README.md)、[110 份输入的哈希清单](source-manifest.json)
- [原始下载与三次实测证据](../../distortion/results/hdmi-camera-fisheye-live-20261103-a/README.md)
- [离线验证说明](VERIFY_README.md)

位流 SHA256：`8c43a77d9ddce72dc7015ef7f63aabe37ab6758dd698e2e811b669c5aa5ba047`。最终 ADF SHA256：`7b21d06112eda0213bd60780d971e90a9da492d7a29daac09eda11d388f96310`。目标器件 PG2L100H、速度级 -6、FBG676；生成工具为 Pango PDS 2023.2-SP3 build 154097。

## 图像链路与当前性能

摄像头输入为 1920×1080、约 148.5MHz / 60Hz RGB888 数字信号；FPGA 采集进入双源帧 DDR 缓冲，125MHz 矫正核心通过鱼眼径向 ROM 与定点逆向映射生成源坐标，缓存读取并双线性插值，双结果帧 DDR 缓冲在完整帧边界交给 HDMI 1920×1080 / 30Hz 扫描。Gamma 关闭、无旋转；KEY1 选择原图/矫正，KEY0 复位。

| 窗口 | 样本 / 有效秒数 | 处理 FPS | 唯一新画面 FPS | HDMI 刷新 Hz |
| --- | --- | ---: | ---: | ---: |
| 默认矫正 | 30 / 29 | 4.3103 | 4.2759 | 30.0 |
| KEY1 原图 | 30 / 29 | 30.0 | 30.0 | 30.0 |
| KEY1 切回矫正 | 12 / 11 | 4.2727 | 4.2727 | 30.0 |

矫正最后一帧约 222ms。三次测量期间均无 fault、CRC 拒包或新增空白帧；启动时累计的 7 次空白保持不变。HDMI 刷新率与新画面 FPS 分开记录，未测端到端光学延迟。协议 PGHFPS02，115200，BuildID `11030001`，ProfileID `ed59f83e3cfbc77b`。

## 标定与实现对应

35 个有效独立姿态（28 训练、7 留出），OpenCV fisheye 模型四项 D，当前输出投影为 balance=0.5、R=I。留出平均误差约 0.3915 原生像素。包内提供全部 35 张有效标定图（含原训练/留出划分）、一张方便查看的训练图副本和两张电脑预览。其余 14 张近重复或角点不全的图不纳入拟合和交付；可从这些图像重新提角点并复算，原始角点坐标未序列化。原始报告生成于上板前，内部未部署状态按历史理解，后来下载和用户观察见实板证据。

实际部署的量化配置保存于 [profile-a 原始报告](evidence/profile-a/profile.json) 和 `distortion/board/hdmi-camera-fisheye-{profile,radial-table}.vh`。1025 节点 / 1024 段 Q30 径向 ROM，原生 2,073,600 坐标的定点映射最大误差约 0.0064 像素；这是数值实现误差。原始映射、系统双帧、I/O 仿真报告在 `evidence/`，其中绝对路径只作来源记录。

## 验证与重建

在仓库根目录运行，无需串口、FPGA 或第三方 Python 包：

```powershell
python delivery/20261103-hdmi-camera-fisheye-c/verify_release.py
python delivery/20261103-hdmi-camera-fisheye-c/prepare_build.py --output .bld
python delivery/20261103-hdmi-camera-fisheye-c/verify_source.py --prepared .bld
```

`.bld` 必须尚不存在；Windows 建议短路径克隆。准备脚本只生成编译输入和 Tcl，不访问硬件。新布局布线仍需重新核验时序、物理约束和下载产物，历史签核属于上面的精确位流/ADF。大型 STA/数据库保留于原机，包内提供其摘要和原件哈希。

`release-manifest.json` 对本次发布文件逐一绑定字节数和 SHA256。冻结原件和闭包源通过 `.gitattributes` 保留字节，离线验证会重解码三次 UART 原始字节，并逐字段对照回执。原图 cache_hits 的多次 32 位回绕按逐样本累加修正；原始回执不改写，FPS 不受此问题影响。
