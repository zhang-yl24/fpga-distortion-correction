# 主要方案一：OV5640 720p15 原图／校正切换

本目录对应已上板的`camera720_view_toggle_top`：处理有效图像1280×720，保存的29秒计数窗口接受、处理和新显示各435帧，即15 FPS。HDMI配置为1920×1080p30扫描，720p画面居中显示；15 FPS是新图像帧率。

## 文件入口

- [可直接选择的SRAM位流](bitstream/camera720_view_toggle_top.sbit)：从原封存gzip无损解出，未重新编译。
- [版本身份](identity.json)：位流SHA256、BuildID、ProfileID及原始出处。
- [冻结源码与构建输入](source/README.md)、[源码清单](source-manifest.json)：118项实际Prepared输入与239项仓库原输入，包含必要IP、约束、原工程和Tcl。
- [时序与资源报告](reports/README.md)、[报告清单](reports-manifest.json)：快慢角时序摘要及完整报告gzip，RouteOptimize原始资源及与最终实现的对应证据。
- [原板测归档](../../distortion/results/camera720-view-toggle-live-20261102-a/README.md)、[同版汇总](../../distortion/results/camera720-view-toggle-live-20261102-a.json)。

## 使用与校验

KEY1每按一次切换原图／校正，默认校正；KEY0复位。LED0表示请求模式，实际画面在完整帧边界切换。此版本连接OV5640 CAM2，不能把另一个HDMI摄像头的接线和参数直接套用。

位流SHA256：`0ca6d19bf074c73cba0346a22e54ba3afb99a595728e6420a1cbb767b963dfe5`，大小3,791,112字节。BuildID为`47e52e93b7238f29`，ProfileID为`f79c44d9bdeb5b11`。原下载使用易失SRAM，Flash未写。

在包根目录运行：

```text
python -B delivery/20261104-camera720p15/verify_selected.py
python -B distortion/results/camera720-view-toggle-live-20261102-a/verify_bundle.py --summary distortion/results/camera720-view-toggle-live-20261102-a.json
```

这些命令只校验文件和保存的记录，不执行下载、EDA或新板测。构建记录保留原绝对路径；在新机器重建时需要路径重定位、相容PDS和重新验证，不能把归档完整性当作已经完成便携重建。

资源采用本版原RouteOptimize结果，并通过后续功能／放置保持证据关联最终位流，见报告说明；不把另一旧统计版的资源表套用于本版。
