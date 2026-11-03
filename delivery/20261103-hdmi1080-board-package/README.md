# 1080p 畸变校正帧率优化：完整工程包

[下载完整工程 ZIP（约 30 MB）](hdmi1080-board-delivery.zip?raw=true) · [SHA256 校验文件](hdmi1080-board-delivery.zip.sha256) · [Release 备用下载](https://github.com/zhang-yl24/fpga-distortion-correction/releases/tag/hdmi1080-throughput-20261103)

本目录供团队直接下载完整工程。ZIP 包含 130 项完整工程源码及依赖闭包、baseline/cache/both 三份 `.sbit`、一键重建脚本、帧率日志分析工具、原始构建和时序证据，以及基础／提高任务验收表。

1. 下载 ZIP，解压到短路径，例如 `D:/fpga/`，得到 `fpga1080/`。
2. 阅读 `fpga1080/START_HERE.md`，运行 `python -B verify_package.py` 核验文件。
3. 上板对比顺序为 baseline → both（组合优化版）；cache 用作单项对照。三份位流位于包内 `bitstreams/`。
4. 需要在另一台电脑重编译时，使用包内 `rebuild.py` 重新生成本机路径；具体命令见操作说明。

当前配置为 **HDMI 1080p29.97/30、Penn 开发参数、零旋转、Gamma OFF**。组合版在指定离线模型中减少 12.54% 处理周期，像素与 mask 一致。三版均已完成 Map、PNR、STA 和位流导出，标签为 **DIAGNOSTIC_NOT_TIMING_SIGNOFF**；优化位流尚未板测，setup、DDR recovery/removal 与外部 IO/CDC 验收仍待完成。1080p60 稳定纯校正尚未实现。

基础／提高任务逐项结论位于包内 `delivery/20261103-hdmi1080-throughput/ACCEPTANCE_AUDIT.md`，正文的相对证据链接可在解压后的完整目录中使用。

代码与可在线查看的详细证据：[固定源码提交 bdaf8c1](https://github.com/zhang-yl24/fpga-distortion-correction/tree/bdaf8c1527fb46cc5b8753415fa02f464a8c08b0/delivery/20261103-hdmi1080-throughput)；[PR #22](https://github.com/zhang-yl24/fpga-distortion-correction/pull/22)。

包内 497 个文件哈希、80 项原生依赖、三份工程准备和 38 项工具测试已通过。[解压复核记录](delivery-validation.json)

ZIP SHA256：`3164e3fca394b5a9734438329589ec476ff59b1731cfb7c90fc9084051faec81`
