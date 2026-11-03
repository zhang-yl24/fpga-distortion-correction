# 稳定提帧候选：解压后入口

本包目标为 **1080p29.97/30 的稳定纯校正**。盘古 100Pro+，PG2L100H / FBG676 / -6；配置身份 `8c73465e`。已完成内部双角时序、数字仿真和位流导出，实板性能尚待测试。

## 先核验，再上板

解压到短路径，例如 `D:/fpga/fpga1080`，保留完整目录结构。Python 3.10+，从包根目录运行：

```powershell
python -B verify_package.py
python -B delivery/20261103-hdmi1080-stable30/tools/verify_candidate.py
python -B -m unittest discover -s delivery/20261103-hdmi1080-stable30/tests -p test_candidate.py -v
```

位流位于：

`bitstreams/both/both_corrected_8c73465e_DIAGNOSTIC_NOT_TIMING_SIGNOFF.sbit`

SHA256：`f77c4991ef485466971fc9145d173769c1dcda3839665d72abfc4bc6288adeb4`。

输入设为 1920×1080、29.97 或 30 Hz，沿用已跑通演示版的连接与 LOAD/ARM 操作。纯校正模式固定，原图/校正自动切换关闭。具体采集和判断方法见 `delivery/20261103-hdmi1080-stable30/docs/BOARD_HANDOFF.md`。先保存可回退的原演示版，再测试新位流。

本版内部原生时序 12 类均零违规，最小 setup 裕量 +0.009 ns。位流仍保留诊断标签，HDMI 外部 IO、CDC/复位物理验收和长时间实板稳定性待补。完整状态见 `PACKAGE_STATUS.json` 与候选目录的 `evidence/board/summary.json`。

## 完整工程与重建

包内包括冻结演示源码、稳定候选覆盖文件、按 SHA 匹配的 80 项原生依赖、测试和原构建证据。厂商工具及授权使用接收方本机安装。

准备完整原生工程、约束与 PDS 阶段目录（不启动 EDA）：

```powershell
python -B delivery/20261103-hdmi1080-stable30/tools/build_board_candidate.py prepare --dependency-native native-dependencies --output-root D:/fpga-build2 --run-name stable30-01 --variant both --mode corrected
```

完整重建时，使用一个尚不存在的 run 名：

```powershell
python -B rebuild.py --pds-shell E:/PDS_2025.2-ads-win64/pango/PDS_2025.2-ads/bin/pds_shell.exe --output-root D:/fpga-build2 --run-name stable30-02 --variant both --mode corrected
```

入口依次执行 prepare、Map、布局布线、独立双角 STA 和诊断位流导出，任一步失败即停止。可直接使用随包已生成位流先上板；重新编译后应重新核对时序和源身份。

`board-builds/stable-a/` 保存本次构建的历史绝对路径、回执、数据库和日志，供追溯。新电脑应运行 prepare/rebuild 生成当地路径绑定。不要直接续跑历史快照。

## 当前结论

- 引擎仿真：完整 1080p、22.650624 ms @125 MHz；图像与有效掩码匹配整数参考。
- 调度：三源槽减少输入/显示相位导致的缺空闲槽丢帧；额外占用 4 MiB 外部 DDR。
- 当前仍为 Penn 参数、零旋转、Gamma OFF；实际镜头标定需另行导入并核验。
- 1080p60 校正待下一阶段处理；本包不作为基础与提高任务全部完成的证明。

报告可引用本包有证据的源码、资源、仿真及内部时序结果。纯校正新帧率、端到端延迟、同源校正精度和长期运行数据须待板测后填写。
