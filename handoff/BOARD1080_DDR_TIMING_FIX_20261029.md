# DDR 定向时序修复（2026-10-29）

当前工作分支 `codex/ddr-ip-timing-fix`。`final-r` 在同一已布线候选中合并了单支路物理绕行与精确复位例外；原生双角十类汇总均零失败。它是离板诊断候选：外部 IO、CDC 边界与实物验收仍需完成，不能把这些汇总等同于整板签核。

## 修复内容

Verilog、DDR IP、125 MHz 主时钟、DDR 多周期及不确定度没有修改。采用两项分别验证后合并的改动：

1. **真实数据 hold**：只对 `_N173` 的 `TX_DATA[2]:IOLHR_364_624` 分支指定一段已确认存在的设备连线，其余连接由 PDS 自动完成。保留原有源/目的地、放置位置及数据路径检查，没有用 false path 或修改 hold 判据消除失败。
2. **复位约束**：依据同配置原厂 IP 的异步关系及完整原生报告，绑定四个实际 IP 寄存器的 clock pin 与 126 个实际 reset pin，覆盖每角 244 项检查。CPD reset 是独立第四源，不混入 dqs reset。另将 `power_ready` 至原厂两级入口同步器的 1 项作为单独 RDC 例外；实际功能网表已确认两级、CE=1、异步 clear、FF1 仅驱动 FF2、输出取 FF2，无 LOCK 反馈死锁。

内部四组端点分别为 dqs reset 104、iol reset 14、training reset 7、CPD reset 1。它们对应 244 项 STA 检查，同一引脚可以参与不同内部时钟的检查，不能把引脚数与检查数混为一谈。完整清单包含 fast 角原先已非负的 11 项。仅凭 158 个存在的硬宏 reset pin 会误纳入 33 个未接 ISR；本修复使用实际时序端点。

未使用全局异步 clock group，也没有把 `TX_DATA`、普通 D 或自研 CDC 纳入新例外。新规则对 recovery 和 removal 都生效；setup/hold 的 false-path 例外必须为空，详见原生例外审计结果。

## 同一最终候选的结果

原生报告：`distortion/build/ddr-fix-20261029/final-r/reload/board1080_top.rtr`。

| 检查 | slow 最差裕量(ns) | fast 最差裕量(ns) | 失败数 |
| --- | ---: | ---: | ---: |
| setup | +0.447 | +3.248 | 0 / 0 |
| hold | +0.060 | +0.020 | 0 / 0 |
| recovery | +2.792 | +4.759 | 0 / 0 |
| removal | +0.353 | +0.160 | 0 / 0 |
| minimum pulse width | +0.035 | +0.035 | 0 / 0 |

每角保留 setup 60064、hold 58600、recovery 5158、removal 3928、MPW 16369 项检查。复位例外前 recovery/removal 分别为 5403/4173；减少的 245 项必须逐路径对应 244 项 IP 内部复位加独立入口 1 项。

对照同一 MPNR 基线，物理绕行只改变 `ddrphy_sysclk → phy_dq_sysclk_1` 的 hold 汇总：−0.037/−0.222 ns → +0.281/+0.021 ns，420 项检查全部保留。这里是该 clock pair 的最差值，不冒称原失败端点自身的新裕量；其余 setup/hold 汇总保持。PDS 全流程报告与 MPNR 报告存在细小的数值口径差异，因此定向效果使用相同 MPNR 入口前后比较。

十表通过不代表外部覆盖已完成。原有 54 项缺输入延迟、110 项缺输出延迟以及诊断 CDC 边界仍需结合实际板卡和 HDMI 接口资料收敛；此前八帧 1080P、30.000fps 数字回归继续作为同一 RTL 的功能证据，本轮未重新仿真或宣称实物帧率。

## 可核查的物理修改

原路线：

```text
CR3:CLMA_357_619 → S_CR3:SRB_354_618 → ZDNE[0]:SRB_354_618
→ IDNE[0]:SRB_360_624 → S_B2:SRB_360_624 → TX_DATA[2]:IOLHR_364_624
```

执行的定向命令：

```tcl
unroute -branch {_N173:TX_DATA[2]:IOLHR_364_624;}
manual_route -net {_N173} -branch {TX_DATA[2]:IOLHR_364_624} -pins {ZDNE[0]:SRB_342_582>IDNE[0]:SRB_348_588;}
```

锚点及其连接取自本机 PG2L100H 官方 `pattern/drawing/wirepattern.txt`。原生 `show -design_net` 确认最终路线经过这两个锚点，并自动接回同一终点；两条工具命令均成功，随后保存并由新进程重载 STA。这里的 `>` 连接一条分支上的 pin，`;` 结束分支；把所有 pin 用分号隔开会触发 DesignEditor-0029，失败试验已保留。

这是一条 FPGA 内部支路的工具布线约束，不涉及开发板外部接线。

## 证据链和复现边界

- 严格基线 E：`distortion/build/board1080-timing/holdfix-full-20261028-e/`，最终 ADF SHA256 `c146885f90da22cae61d106f0768529c98f3d2e55f8604315328e61700d4e3fc`。
- 相同已布线基线的 MPNR 报告：`distortion/build/ddr-fix-20261029/mpnr-base-g/`，没有例外路径。
- 仅物理修复 Q：`distortion/build/ddr-fix-20261029/hold-detour-q/`，ADF SHA256 `8b38ddadd1a426f33b88f91737946d5dad73f062592b00b587217e13ea0c8495`，hold 零失败，复位失败仍原样保留。
- 仅复位 P：`distortion/build/ddr-fix-20261029/persist-all-p/`，recovery 零失败，数据 hold 仍 −0.037/−0.222 ns。
- 最终 R：`distortion/build/ddr-fix-20261029/final-r/`，ADF SHA256 `0a5446de4beb7789ed87542bccd022fa5cc007cd41df8f97ea9718398ca312aa`，保存后 STA 前后哈希相同；保存/重载分别 71.695/90.202 秒，均退出 0。
- 入口结构：[JSON](../distortion/results/board1080-entry-rdc-20261029.json)；完整原生复位清单：[JSON](../distortion/results/board1080-native-recovery-20261029.json)。
- 精确 native name proof 的完整 244 项生成计划：`distortion/build/ddr-native-reset-scope/complete-20261029-b/plan.json`；工具同时重核原厂来源、IDF、74 个 IP 源及当前 109 项闭包。

原始大型 ADF、sim.v、rtr/db 保留本机，不把它们或许可证写入 Git。重布线命令绑定当前设备、源 ADF 和实际 net/site 身份；改变 RTL、IP、工具、布局后不能盲套 `_N173`。

## 已解决的工具接口问题

PDS 会先预解析 Tcl，随后在流程中再次执行。独立 MPNR 载入放在 `if {[info script] ne {}}` 的运行阶段，并先初始化架构/设计，才能避免预解析时静默退出。

`get_pins` 实际返回内部句柄 `@tcicmdresultN`，其 Tcl `llength` 不能代表匹配数量。真实匹配使用原生 Timing-5001 记录中的数量和完整 `t:<hierarchy>/<pin>` 名称核对；本机实际查询使用 slash pin，文档中的后端 colon 拼法在本次查询匹配为 0。

在已载入的 MPNR 内即时新增例外后直接报告会返回空 Tcl 错误。可行流程为：仅修改 ADF **副本**的约束→`save_adif`→新进程重载→`mpnr_report_timing`。`save_adif` 实际保存回所载入的副本，不能把 `-file_name` 当成另存 ADF 的保证。执行工具必须先复制原件并核 SHA。

关闭 ControlChain 的另一项全流程试验产生新的更差 hold，已拒绝作为方案，详见 [ControlChain 对照](BOARD1080_CONTROLCHAIN_20261029.md)。当前成功候选沿用严格基线的默认布线设置，仅定向修改上述一条支路。
