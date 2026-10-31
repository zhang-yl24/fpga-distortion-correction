# 无开发板时的离线推进（2026-10-29）

**2026-10-31最新：OV5640摄像头接入已开始，开发板按用户通知已断电；上板前先通知并取得新的上电确认。** 仅电脑HDMI IN / MS7200支线暂停。新640×480候选两组仿真通过，原生构建完成但DDR hold/recovery未过，尚无摄像头位流或下载。先修复新候选时序和完成物理检查，再准备上板看实时画面。摄像头仍连接，旧“未接摄像头”是误点。见[摄像头交接](CAMERA_VGA_INPUT_20261031.md)与[CURRENT顶部](CURRENT.md)；下文为历史依据，不覆盖当前状态。本次只更新本地文档。

开发板暂不可用时，工程仍可继续推进，但验收边界要分开记录。

## 2026-10-29 新源码修复更新

以下“当前缺口”中的步骤1–4现已完成。新库的251条边沿变体映射、入口功能网表、精确引脚和原始路线均独立通过，随后在副本应用定向修复并用新PDS进程重跑报告。最终ADF SHA256为 b7ee4ac251b5d97c6887ef1fd7aeacf22d8a6ce93be821ca4255823f03c74f5c，位于 distortion/build/ddr-timing-repair/fresh-repaired-1029-a/input.adf。双角十类时序均零失败，hold最差+0.060/+0.020ns；数据setup/hold例外为空，每角复位例外严格为244项IP加1项入口。

完整新结果为 distortion/results/board1080-fresh-repair-20261029.json 和 board1080-fresh-ddr-final-20261029.json。新工具单独命名、固定新profile，历史工具继续拒绝不同ADF。新网表的9个原始clear缓冲节点已全树检查，仅连接复位负载；两级同步器第一级功能扇出为1。初次旧检查器对缓冲树的拒绝与runner版本banner检查中止都保留原始记录，没有覆盖成“初次成功”。

步骤5也已完成：fresh-bit-1029-a/generate_bitstream/board1080_top.sbit为3,791,112字节，SHA256 b90c0a5c6ef607f5054fe9c635dd1f551ea1d54cbfcf268335dce708ad0a3048。生成前实际执行同一ADF的STA和独立审计，355项输入无漂移。完整结果 distortion/results/board1080-fresh-bitstream-20261029.json，同时绑定实际执行审计器快照及补严固定ADF检查后的两份重审计。新源码到位流链已完成；真实外部IO AC、CDC/RDC协议、DDR训练与稳定画面仍需完成板级验收。下面保留各历史阶段说明。

## 已完成

- 最终 DDR 修复候选的原生双角十类时序审计通过，结果见 `distortion/results/board1080-ddr-final-20261029.json`。
- 实际 rowpipe 顶层 `board/board1080_rowpipe_top.v` 的控制体离线回归通过：7 项启动资格、A1–A6 故障隔离、首故障粘滞、held-AW 和公共复位均通过。
- 回归入口：`distortion/tools/run_board1080_rowpipe_control_sim.py`；测试 7 项通过；报告位于 `distortion/build/board1080-rowpipe-control/actual-20261029-a/board1080-rowpipe-control-simulation.json`。
- 已从最终修复 ADF 离线生成 `board1080_top.sbit`：3,791,112 字节，SHA256 `9f6bbe5fc02e7b66da1be6d449d6e68fef40f6f227068196f50a6a3a37a7967a`。文件位于 `distortion/build/board1080-timing/bit-1029-a/generate_bitstream/`；结果及输入/日志哈希见 `distortion/results/board1080-offline-bitstream-20261029.json`。
- PDS 在出位流之前实际执行了完整双角十类与精确例外审计；日志顺序为 Report Timing → PRE_BIT_NATIVE_AUDIT_PASS → Generate Bitstream。原始及复制 ADF 哈希保持相同，没有硬件操作。
- 已在 `fresh-1029-b` 从当前源码重新执行 compile → synthesize → dev_map → pnr → route_optimize → STA，原生退出0、六阶段均实际完成，109项源码与109个编译副本无漂移，STA前后ADF相同。新ADF SHA256 `0f6101036b3c3981544e032ec93c3ad2b5468c79e55fa4f8f6a8014265fb15be`，完整回执见 `distortion/results/board1080-fresh-rebuild-20261029.json`。
- fresh构建尚未接入精确修复：十类汇总逐行与严格基线E相同，slow/fast各1项hold（−0.037/−0.222ns），recovery为245/234项失败，另外六类零失败。现有已修复ADF与位流未改；新构建成功不代表新库时序通过。
- bitstream准备器的13项测试已加入CI；本地相关66项通过，提交 `e96f534` 的GitHub Actions已通过。
- 新ADF只读探针已验证原 `_N173` 路线、驱动/负载物理站点和126个复位源端点对与旧修复profile相同；扩展STA前后ADF不变，汇总不变。`nworst 4` 每角展开251条IP复位边沿变体，不等于244项逻辑检查，不能直接丢弃多出的变体。入口RDC新功能导出和精确原生pin查询尚未重绑，修复准入保持false，见 `distortion/results/board1080-fresh-admission-20261029.json`。

该回归使用明确的 PLL/DDR/System/HDMI stub，只证明实际 board top 的控制 wiring 和状态机，不证明真实 FIFO、DDR IP、PLL、IIC、HDMI PHY、CDC 时序或硬件稳定性。

## 当前缺口

已验证的最终 ADF 现已能生成 `.sbit`，但需要完整的源码/流程声明上下文。只含 MPNR 的独立工程曾返回 `Flow-0044: Place hasn't been run`；复制旧工程后又重跑前置综合，已停止。成功的独立配方声明当前109项闭包及完整流程，再给 STA 和 `gen_bit_stream` 显式传入**同一个已审计 ADF 副本**，并在两者之间执行原生报告审计。

`bit-1029-a` 的实际重型阶段只有 Report Timing 和 Generate Bitstream；PDS 因指定输入数据库而跳过了前置综合/PNR 计算。不能把声明过 compile/pnr 或工具打印 successfully 当成重新从源码构建通过。原本可复现的修复流程和冻结的输入 ADF 仍是前提。

当前源码的独立fullflow已经跑通。下一项离线工作是把精确修复接到这份新库上，并形成完整的源码到位流流程：

1. 将 `nworst 4` 的251项实际路径变体映射回244项逻辑检查，核对慢/快角边沿身份和失败数，不折叠掉未解释的路径。
2. 为新ADF补独立原生 pin-query 记录，并重新导出/审计入口两级RDC功能网表；建立完整的新库 admission profile。
3. 准入后为新ADF建立独立输入绑定，应用精确复位范围与必要的数据支路绕行。现有准备器只接受历史基线SHA，必须保留该拒绝，不能直接替换哈希或因 `_N173` 名字相同就套用旧物理锚点。
4. 用新进程重新生成完整 STA 和例外报告，并与这份fresh基线比较；只允许已审计目标的变化。
5. 在同一最终 PNR 状态执行 `gen_bit_stream -scbv {High Voltage} -unused_io_status UNUSED`，绑定最终 `.sbit`、ADF、时序报告、引脚报告和全部输入 SHA。

当前位流门禁只证明原生内部时序/例外与文件输入身份。仍需完成实际板型、全引脚电气、HDMI AC 和 CDC 边界检查，再做实板画面/DDR长稳验证；不声称硬件放行。大型位流和 ADF 留本机，Git 只提交工具、测试和哈希证据。
