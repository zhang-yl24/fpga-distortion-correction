# FPGA 畸变校正主项目

平台：盘古 100Pro+（PG2L100H / FBG676 / -6）。本仓库统一保留 HDMI 1080p、OV5640 720p、VGA、DDR 调试、算法验证与竞赛验收资料。

## 当前上板入口

默认使用 [tile8 鱼眼版本](delivery/20261103-hdmi-camera-fisheye-tile8/README.md)。已保存的约 30 秒串口记录测得 **15.0 个新校正显示帧/秒**，输出扫描 **30 Hz**。位流 SHA256：`1236d82f113e1ddb1c5e24502ed1aa03e4758db0a7d6ff17bf9216f0fbd0e4f3`。

该结论绑定原位流及其证据。重新综合或布局布线后，需要重新完成时序和板测验收。视觉效果、光学端到端延迟、长期稳定性与 KEY1 往返切换仍需验证。

```powershell
python project.py list
python project.py verify --variant tile8
python project.py prepare --variant tile8 --output D:/fpga-build/tile8
```

`prepare` 仅生成独立构建目录和 Tcl。实际运行 PDS 后检查 Slow/Fast 的 setup、hold、recovery、removal、skew、MPW，另行检查 CDC、复位和外部 IO；通过后再上板。各工程分别选择源码清单，避免同名 RTL 模块混编。

## 版本与资料

| 版本 | 用途与状态 | 入口 |
| --- | --- | --- |
| tile8 | 默认真实相机鱼眼；上板新校正显示 15.0 FPS | [工程](delivery/20261103-hdmi-camera-fisheye-tile8/README.md) |
| fill8 / S3 | 真实相机回退；上板新校正显示 5.0 FPS | [工程](delivery/20261103-hdmi-camera-fisheye-fill8/README.md) |
| fisheye C | 原始真实相机基线；约 4.3 FPS | [工程](delivery/20261103-hdmi-camera-fisheye-c/README.md) |
| stable30 | 冻结 Penn 参数候选；板测边界见该包说明 | [工程](delivery/20261103-hdmi1080-stable30/README.md) |
| throughput | 早期 1080p 吞吐候选与证据 | [目录](delivery/20261103-hdmi1080-throughput) |
| demo-source | 演示、鱼眼 H 等各版原始交付与身份 | [目录](delivery/20261103-hdmi1080-demo-source) |
| stable30 O/P | 电脑 HDMI 输入下约 30.011 新处理/呈现 FPS；已匹配 78/83 外部依赖，5 项待补齐 | [源码与板测边界](delivery/20261103-hdmi1080-demo-source/stable30-OP/README.md) |
| fisheye60 | 六项技术路线候选；物理时序 FAIL，实板 60 FPS 未验收 | [工程](delivery/20261103-hdmi-camera-fisheye-60/README.md) |
| 旧板测包 | 原始上板交付 | [目录](delivery/20261103-hdmi1080-board-package) |
| 720p / VGA / DDR / 验收 | 历史工程、工具及验收记录 | [原主线完整说明](https://github.com/zhang-yl24/fpga-distortion-correction/blob/8f365e48b83c16a0f41da7380d16de62cba2c624/README.md)、[验收目录](distortion/acceptance)、[交接目录](handoff) |

[全部分支、标签和发布资产清单](project-catalog.json)记录整合快照，包含原提交、下载链接、资产大小及 GitHub 提供的 SHA256。大型历史 ZIP 保留在原发布页。各分支历史通过 Git 合并保留，历史验证结论与原位流绑定。

## 验证边界

本次源码整理与离线检查的结果见 [整合检查记录](docs/INTEGRATION_VALIDATION.md)。内部处理周期、扫描刷新率、新校正显示帧率分别统计；仿真结果与实板结果分别记录。当前默认版本沿用已发布 RTL、约束及位流，后续提帧优化在独立候选中进行。
