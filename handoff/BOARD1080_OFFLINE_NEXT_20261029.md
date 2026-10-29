# 无开发板时的离线推进（2026-10-29）

开发板暂不可用时，工程仍可继续推进，但验收边界要分开记录。

## 已完成

- 最终 DDR 修复候选的原生双角十类时序审计通过，结果见 `distortion/results/board1080-ddr-final-20261029.json`。
- 实际 rowpipe 顶层 `board/board1080_rowpipe_top.v` 的控制体离线回归通过：7 项启动资格、A1–A6 故障隔离、首故障粘滞、held-AW 和公共复位均通过。
- 回归入口：`distortion/tools/run_board1080_rowpipe_control_sim.py`；测试 7 项通过；报告位于 `distortion/build/board1080-rowpipe-control/actual-20261029-a/board1080-rowpipe-control-simulation.json`。
- 已从最终修复 ADF 离线生成 `board1080_top.sbit`：3,791,112 字节，SHA256 `9f6bbe5fc02e7b66da1be6d449d6e68fef40f6f227068196f50a6a3a37a7967a`。文件位于 `distortion/build/board1080-timing/bit-1029-a/generate_bitstream/`；结果及输入/日志哈希见 `distortion/results/board1080-offline-bitstream-20261029.json`。
- PDS 在出位流之前实际执行了完整双角十类与精确例外审计；日志顺序为 Report Timing → PRE_BIT_NATIVE_AUDIT_PASS → Generate Bitstream。原始及复制 ADF 哈希保持相同，没有硬件操作。

该回归使用明确的 PLL/DDR/System/HDMI stub，只证明实际 board top 的控制 wiring 和状态机，不证明真实 FIFO、DDR IP、PLL、IIC、HDMI PHY、CDC 时序或硬件稳定性。

## 当前缺口

已验证的最终 ADF 现已能生成 `.sbit`，但需要完整的源码/流程声明上下文。只含 MPNR 的独立工程曾返回 `Flow-0044: Place hasn't been run`；复制旧工程后又重跑前置综合，已停止。成功的独立配方声明当前109项闭包及完整流程，再给 STA 和 `gen_bit_stream` 显式传入**同一个已审计 ADF 副本**，并在两者之间执行原生报告审计。

本次实际重型阶段只有 Report Timing 和 Generate Bitstream；PDS 因指定输入数据库而跳过了前置综合/PNR 计算。不能把声明过 compile/pnr 或工具打印 successfully 当成重新从源码构建通过。原本可复现的修复流程和冻结的输入 ADF 仍是前提。

下一项较大的离线工作是把已验证修复整合到可重新布局的 fullflow，使它能支持后续 RTL 修改：

1. 使用当前 109 项源码闭包、最终 rowpipe 顶层、原 FDC/RCF 和四组精确复位范围。
2. 在 PNR 完成后执行 `_N173` 分支绕行。
3. 用新进程重新生成完整 STA 和例外报告。
4. 在同一最终 PNR 状态执行 `gen_bit_stream -scbv {High Voltage} -unused_io_status UNUSED`。
5. 绑定最终 `.sbit`、ADF、时序报告、引脚报告和全部输入 SHA。

当前位流门禁只证明原生内部时序/例外与文件输入身份。仍需完成实际板型、全引脚电气、HDMI AC 和 CDC 边界检查，再做实板画面/DDR长稳验证；不声称硬件放行。大型位流和 ADF 留本机，Git 只提交工具、测试和哈希证据。
