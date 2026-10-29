# Checked HDMI 位流导出（2026-10-29）

## 本轮产物

在 `ea7231e` 的完整 checked HDMI 源码构建、双 DDR 数据末段绕行和精确复位例外审计基础上，从固定最终 ADF 导出新版离线位流。没有重新综合或布局布线，也没有使用旧 EDID-only/旧位流替代本候选。

- 工作目录：`distortion/build/board1080-timing/checked-bit-1029-a`。
- 固定输入 ADF SHA256：`857bf183e52cbd96fb9f378f5087f4c55aba66b22f8488822b7e2dc92450c142`。
- 位流：`generate_bitstream/board1080_top.sbit`，3,791,112 字节。
- 位流 SHA256：`b4edadba44368d5de1c5b3237d2cc3dccd7c951918cefb0c40af2ac63f86cb33`。
- 实测文件头包含 `board1080_top`、`Logos2-PG2L100H--6-FBG676`、`Fabric Compiler`、`2023.2-SP3<154097>`；文件头身份检查不等同对整个二进制格式解码或实板兼容认证。
- 原生执行时间：北京时间 2026-10-29 22:23:10 至 22:29:08，约 358 秒，退出码 0。

独立生成后复核已通过：[完整回执](../distortion/results/board1080-checked-bitstream-20261029.json)，绑定全部输入、实际阶段顺序、生成前审计、原始输出与日志哈希。其回执 SHA256 为 `72911c9334660d9902ac69ef5be8081d12f9b45d2aa0881e08bb37173fe4f9b8`。

## 生成前检查

新增 `prepare_checked_board1080_bitstream.py`，固定最终 ADF 及 `board1080-checked-ddr-final-20261029-a.json` 的实际 SHA，不接受调用者任意替换候选或哈希。准备时重新执行原生证据审计；保存原始 `plan.json`、`timing.tcl` 及其副本，另用 `bitstream-plan.json`、`bitstream.tcl` 描述导出。

执行前及生成后均核对 601 项输入，包含 109 源及编译副本、123 项原始闭包输入、历史证据、工具和同一 ADF 副本。新进程实际只运行 `Report Timing` 与 `Generate Bitstream` 两个阶段；源码上下文中的 compile/synthesize/pnr 声明被跳过，不能算作本轮重新构建。

真实执行顺序为：新 STA 完成 → runtime 生成前审计通过 → 位流生成开始 → 位流生成结束。gate 核对 124 行保留时序、14 行 HDMI 配置检查、全部时钟及负载和精确例外：每角 recovery/removal 各 245 个逻辑检查、490 条原生路径变体、252 种边沿变体，setup/hold 数据例外为零。数据和 HDMI 检查没有被屏蔽。新报告仍保留缺输入/输出延迟的 55/110 个端口警告。

最终报告内双角十类检查均无失败，最差 hold 为 slow +0.060 ns、fast +0.020 ns；复位例外表示有范围的检查排除，不表示被排除的复位路径取得正恢复裕量。

日志另有 3 条找不到本导出目录 `place_route/run_place.log`、`run_route.log`、`run_route_optimize.log` 的警告：本轮从已有最终 ADF 导出而未执行这些阶段，警告原文保留；无原生 E/F 错误。

## 复现与测试

工具要求已有、为空且名称为 `checked-bit-*` 的目录，并要求 P: 映射到仓库根目录。准备命令为 `.venv/Scripts/python.exe distortion/tools/prepare_checked_board1080_bitstream.py --work-dir distortion/build/board1080-timing/<checked-bit-new>`；准备本身不运行 PDS。按新计划的 `CommandToRunSeparately` 启动原生执行前，先写带 UTC 时间、实际可执行程序和参数的 `execution-start.json`。gate 在缺少执行来源、错 ADF、输入漂移、新报告变化或例外扩宽时拒绝生成。

新工具 21 项 CPU 测试通过。新工具、最终时序审计及两代位流入口合并回归 82 项通过、1 项跳过；跳过项仅为工作区改名后历史本地产物的可选重放，当前新版检查未跳过。新测试已接入 GitHub CI。

首次严格重放发现旧审计 `RemovedResetSummaryRows` 由 set 遍历生成，跨进程 28 条记录顺序不确定。实测仅该字段顺序不同、内容一致；新入口仅规范该字段的排序，拒绝重复身份及任何字段变化，其他列表保持原顺序比较。原审计工具与回执未修改。另两次准备因缺空目录或 P: 映射被提前拒绝，未运行 EDA、未产生部分候选。一次提升权限的 pytest 临时目录访问失败已用正常测试环境完整重跑通过。

## 使用边界

此文件是 checked HDMI1080p30 候选的离线位流；不代表 OV5640 DVP 直入，不代表已测得实板帧率。此次没有下载、烧写 Flash 或访问开发板。

`High Voltage`、`UNUSED` 为沿用的离线生成参数；本次没有测量实际板卡配置电压、上拉或跳线状态。外部 IO AC、SCL 上拉与电平、CDC/复位模拟安全性、DDR 训练、真实图像和长稳尚待验收。因此硬件放行仍为 false。

下一步核对可用 HDMI 输入/显示与板卡实际接口条件，再从只读识别下载链和明确的板级验收开始推进。原始构建、仅绕行版本及最终版本的报告/脚本/哈希继续保留供交接。
