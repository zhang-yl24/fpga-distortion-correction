# 仓库与版本导航

本仓库按各版本交付目录提供源码、位流、构建和验证入口。首次使用请读[项目介绍与使用说明](../README.md)。最新1080p30方案已完成本地摄像头下载验证，源码与时序按独立版本整理；现有两方案程序RAR仍选择720p15与1080p15 direct-fill。

分支选择、当前 AA 候选与历史分支精简方案见[分支导航](../BRANCHES.md)。

| 任务 | 入口 |
| --- | --- |
| 本次报告、海报、参数与提交要求 | [submission](../submission/README.md) |
| 最新1080p30现场结果、核心源码与时序 | [1080p30方案说明](HDMI1080_30FPS.md) |
| 主要方案一：720p15原图／校正切换 | [源码、位流、时序及资源](../delivery/20261104-camera720p15/README.md) |
| 主要方案二：1080p15最优direct-fill | [独立选定包](../delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/README.md) |
| 最新direct-fill源码与保存的15 FPS板测证据 | [20261104 direct-fill](../delivery/20261104-hdmi-camera-fisheye-tile8-directfill/README.md) |
| 原tile8便携重建、15 FPS回退 | [20261103 tile8](../delivery/20261103-hdmi-camera-fisheye-tile8/README.md) |
| S3/fill8历史5 FPS基线 | [fill8](../delivery/20261103-hdmi-camera-fisheye-fill8/README.md) |
| C历史基线、标定输入与参数 | [fisheye C](../delivery/20261103-hdmi-camera-fisheye-c/README.md) |
| 原板测交付包 | [board package](../delivery/20261103-hdmi1080-board-package/README.md) |
| 程序RAR制作与完整性验证 | [导出说明](../tools/SUBMISSION_PACKAGE.md) |
| 每日各分支的开发、验证与合并记录 | [开发历史](DEVELOPMENT_HISTORY.md) |

## 独立验证入口

在仓库根目录运行：

```text
python -B delivery/20261104-camera720p15/verify_selected.py
python -B delivery/20261104-hdmi-camera-fisheye-tile8-directfill/submission/verify_selected.py
```

上述检查验证已保存的源码和证据，不启动EDA或访问开发板。两版均保留实际生产源与构建记录；原绝对路径需在新机器重定位，未冒称一键便携重建。旧C/D整包归档校验器面向完整仓库，不能套用于裁剪后的两版RAR。

原tile8位流为`1236d82f…`，direct-fill为`aa219913…`。同样的15 FPS不表示同一位流，两版时序、资源与处理耗时分别绑定。

## 队友路线与历史资料

团队HDMI吞吐优化、stable30、fisheye60、O/P及输入诊断等路线，按日期、分支、验证状态和原提交入口汇总在[开发历史](DEVELOPMENT_HISTORY.md)。其中的候选结果与两套正式交付分别记录。

各分支代码与证据保留在对应Git提交中。历史合并、回退及本地分支与远端分支的关系也见该记录；不会因某版本位于仓库中就视为已完成同条件板测。
