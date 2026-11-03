# 全版本整合与检查

快照基准：2026-11-03，main `8f365e48b83c16a0f41da7380d16de62cba2c624`。

## 整合范围

28 个远端分支、4 个标签、4 次 release / 21 个发布附件。8 个未合入分支由 5 个叶末端涵盖，均通过真实 Git merge 保留历史；`python project.py audit` 检查全部 28 个原提交可从集成 HEAD 到达。发布资产保留 URL、字节数与 SHA256；本轮未重新下载验证全部大型历史资产，可使用 `python project.py check-asset --tag TAG --file FILE` 校验已下载文件。

默认 tile8 保留原生产 RTL、约束、IP、位流和冻结证据。历史候选独立放在 delivery / distortion/acceptance，按各自清单构建。原 README 保存于 docs/history；主入口集中列出当前选择及回退版本。

## 已完成离线验证

- tile8：110 项生产输入、74 项 DDR IP 展开、位流 SHA256、449 项归档文件通过；原串口记录重放得到 15.0 新校正显示 FPS、30 Hz 扫描、30 样本。
- tile8 新目录重建准备：111 项源码/约束输入通过，未执行 EDA。
- fill8、C：各 110 项生产输入、74 项 IP 及位流身份通过。
- stable30：候选封存校验及 12 项单元测试通过。
- throughput：源码/证据校验、38 项单元测试、80 项依赖恢复通过。
- demo-source：原源码、离线候选、DMA 配对输入、早间进度、60Hz 失败时序归档、stable30 板测与 O/P 导出校验通过；PGSTAT02 的 34 项内存测试通过。
- 历史 fault-recovery：69 项输入按哈希恢复通过，CPU 正例、34 项负例和 7 项主机错误场景通过；未重跑 HDL。
- 原 handoff baseline 审计通过。
- 新主入口：5 项目录保护、路径检查、漏合分支及资产摘要检查通过。

首轮命令和回执见 [checks/results.json](integration/checks/results.json)。公共 CPU 回归与远端 CI 尚待本轮完成后更新。

## 修正与已知缺口

1. 合并根 README 的版本冲突，统一默认工程与版本入口，保留原文历史。原主线生产文件没有改动。
2. 主入口在写构建目录前拒绝含引号、花括号或控制字符的路径，防止生成的 Verilog include / Tcl 路径失效；已有目录拒绝覆盖。
3. O/P 的源码包列出 83 项外部依赖，整合仓库按大小及 SHA256 找到 78 项。缺少精确版本的 bringup_pll.v、iic_dri_cfg100_reset.v、ms7200_1080p30_ctl.v、ms7210_ctl.v 与 uart_bound.pcf。见 [逐项依赖清单](integration/stable30-op-dependencies.json)。其电脑 HDMI 板测约 30.011 新处理/呈现 FPS，构建闭包仍待补齐。
4. fisheye60 历史候选保留物理时序 FAIL 状态，不晋升为默认工程。新整理工作没有生成新位流，也没有取得新板测或物理时序签核。

## 后续硬件验证

任何生产 RTL、约束、PDS 版本或布局布线变化，都需重新运行 Slow/Fast 全部时序表、CDC/复位及外部 IO 审查，再进行板测。按同一位流身份分别统计输入、处理、显示、重复、丢帧和故障；另测光学端到端延迟、画质与长期运行。
