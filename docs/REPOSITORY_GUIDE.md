# 仓库与版本导航

本仓库按各版本交付目录提供源码、位流、构建和验证入口。PR #28已回退；统一`project.py`与其聚合目录不属于本次提交。

| 任务 | 入口 |
| --- | --- |
| 本次报告、海报、参数与提交要求 | [submission](../submission/README.md) |
| 最新direct-fill源码与保存的15 FPS板测证据 | [20261104 direct-fill](../delivery/20261104-hdmi-camera-fisheye-tile8-directfill/README.md) |
| 原tile8便携重建、15 FPS回退 | [20261103 tile8](../delivery/20261103-hdmi-camera-fisheye-tile8/README.md) |
| S3/fill8历史5 FPS基线 | [fill8](../delivery/20261103-hdmi-camera-fisheye-fill8/README.md) |
| C历史基线、标定输入与参数 | [fisheye C](../delivery/20261103-hdmi-camera-fisheye-c/README.md) |
| 原板测交付包 | [board package](../delivery/20261103-hdmi1080-board-package/README.md) |
| 程序RAR制作与完整性验证 | [导出说明](../tools/SUBMISSION_PACKAGE.md) |

## 独立验证入口

在仓库根目录运行：

```text
python -B delivery/20261103-hdmi-camera-fisheye-tile8/verify_source.py
python -B delivery/20261104-hdmi-camera-fisheye-tile8-directfill/verify_stage_d_portable.py --package distortion/results/hdmi-camera-fisheye-tile8-20261103-a
```

上述检查验证已保存的源码和证据，不启动EDA或访问开发板。需要原tile8重建时按该目录README操作；direct-fill保留实际生产源和构建记录，不能用旧tile8的prepare脚本冒充重建新位流。

原tile8位流为`1236d82f…`，direct-fill为`aa219913…`。同样的15 FPS不表示同一位流，两版时序、资源与处理耗时分别绑定。

## 队友路线与历史资料

报告引用的stable30/Q512/O/P记录继续在其原提交中保留，见[报告历史引用入口](../submission/report/README.md)。PR #28汇总资料可在[被回退提交](https://github.com/zhang-yl24/fpga-distortion-correction/tree/e1ec8904abcceefd71b78ecbc3200efc206a32fe)查看；当前主线不重新包含那些聚合目录。Git回退保留历史，不删除队友分支。
