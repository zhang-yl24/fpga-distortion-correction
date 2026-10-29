# Checked HDMI 候选完整构建（2026-10-29）

## 本轮范围

本轮在 `a998293` 已验证的 checked I²C/控制器/顶层基础上，为其建立独立的 PDS 完整构建。`board1080-checked-i2c.fdc` 相对原 FDC 仅将 `hd_scl` 的方向由 OUTPUT 改为 INOUT，K22/K23、电平、驱动强度、SLEW 和 DDR RCF 保持不变。原 source-only 清单、所有历史 RTL/helper/ADF/位流未改。

新 `prepare_board1080_checked.py` 验证 109 源闭包、31 项显式设计、74 项 IDF 所属文件、3 个头文件和 5 处 include 重写，计划绑定 123 项输入及上游清单链。旧准备器的角色和哈希拒绝规则未放宽。新准备/审计测试共 40 项通过；它们已接入 GitHub CI。首次测试失败源于临时夹具漏拷贝祖先清单以及 Windows 临时路径过长，修复夹具并完整复测后通过，未借此跳过真实生产验证。

`distortion/build/board1080-timing/checked-1029-a` 已通过独立启动前核验（123 输入、109 编译副本、235 个被核验文件），启动 compile → synthesize → dev_map → pnr → route_optimize(200ps) → report_timing。用户已明确授权本次使用电池；实际开始时间为北京时间 21:07:26，当时系统回报 Online、82% 电量。日志和开始/结束回执保存在该目录。构建不包含位流生成、下载或硬件访问。

本轮 11 个相关测试文件最终完整回归 202 项通过（115.48 秒），四个交付基线和依赖闭包审计通过。测试在 Windows 本机执行；后续 GitHub CI 结果单独记录。

另外新增的原生展开报告/功能网表准备工具 14 项测试通过（127.85 秒），连接图检查器最终 27 项测试通过，这些测试合计 **202 + 14 + 27 = 243 项**，加上最终 DDR 审计 22 项，本轮共 **265 项**。这些自动测试均为 CPU-only；真实 PDS 执行、导出网表及其来源核验结果见下文，不能把 CPU 测试通过等同硬件或全部时序通过。

## 已完成的实现核查与剩余边界

- 最终路由报告已确认 `hd_scl` 与 `hd_sda` 均为 INOUT，分别映射 K22/K23；PCF 本身不保存方向。当前 ADF 导出的功能网表进一步确认两路输入回读、两级采样、恒零输出和三态控制连接，具体范围与来源核验见下文。
- 新 wrapper 的 HDMI recovery/removal 已从本次实际双角报告重新盘点；配置时钟相关行全部非负。原始完整构建的 DDR recovery 实际失败为 slow 245、fast 228，不沿用旧版 fast 234 项；后续带精确例外的报告单列，不能覆盖原始结果。
- 已取得本库的展开路径、两条目标末段路线、精确 pin 查询和 DDR 入口复位功能连接证据。它们不自动批准时序例外；旧固定 SHA 工具继续拒绝新库，不能用汇总相同替代实际结构证据。
- SCL/SDA 外部上拉及实际电平仍需确认。现有手册只证明 K22/K23 共接 HDMI 芯片，未证明 SCL 上拉阻值或电源；不凭空加内部上拉或 IODELAY。

## HDMI 等待语义

checked 驱动的超时是单次总线事务的超时，不是整个初始化的总超时。RX/TX 都先向 0003 写 5A 再读回比较，这应称写后回读检查，不能称芯片 ID。RX 读取 209C..209F，并等待 `freq_rec[17:16]` 从 00 到 10；缺寄存器定义时不把它直接解释为 PHY 锁定。没有 HDMI 输入时允许等待，不能添加全局初始化超时把正常等待报错。未来可独立增加写后回读不一致的诊断与有限重试。

## 原始完整构建结果（保留失败基线）

完整构建已原生退出 0，全部 6 个阶段完成；最终 ADF 与 STA 前快照 SHA256 均为 `c411d60712ba01ea9356553a69516d316aa68dc8fa67505f7b962d610dec4029`。123 项输入和 109 编译副本无漂移，RTR/XML 十类汇总逐项一致。`distortion/results/board1080-checked-full-build-20261029.json` 保存完整诊断；流程完成，但时序未全部通过，也未生成新位流。

| 检查 | slow 最差裕量 / 失败数 | fast 最差裕量 / 失败数 |
| --- | --- | --- |
| setup | +0.245 ns / 0 | +2.951 ns / 0 |
| hold | +0.021 ns / 0 | -0.189 ns / 2 |
| recovery | -3.960 ns / 245 | -2.964 ns / 228 |
| removal | +0.250 ns / 0 | +0.079 ns / 0 |
| minimum pulse width | +0.035 ns / 0 | +0.035 ns / 0 |

两个 fast hold 失败均在 `ddrphy_sysclk → phy_dq_sysclk_1`，TNS 为 -0.330 ns；旧版只有一处的支路方案不能直接套用。新增 HDMI 配置相关统计无失败：`board27 → cfg_clk` recovery 5 项，slow/fast 最差 +4.795/+6.040 ns；`cfg_clk → cfg_clk` recovery/removal 共各 84 项，全部非负。它们需要保留，不能为处理 DDR 而做全局跨域切断。

输入延迟缺失由 54 增为 55（新增双向 SCL 的输入路径），输出仍缺 110；这份原始完整构建报告没有 false-path。最终路由报告验证 142 项声明、134 个实际占用，只有预期 8 个 RGB565 低位被优化；K22/K23 均为 BANKL4 的 INOUT。引脚方向正确不等同外部上拉、电压或 IO AC 验收。

## 展开报告、导出与路径诊断

- [完整构建诊断](../distortion/results/board1080-checked-full-build-20261029.json) 已完成最终 `route_optimize` 和 STA，保存上表的原始失败结果；不再处于“等待最终 route/STA”的阶段。
- [原生展开报告与功能导出回执](../distortion/results/board1080-checked-native-diagnostics-20261029.json) 记录 `checked-probe-1029-a` 与 `checked-export-1029-a` 两次原生执行均退出 0。输入、编译副本无漂移，原始 ADF 未改；展开报告和导出时的十类汇总均与本次完整构建一致，均无 false-path。功能网表导出实际启动阶段为 `Report Timing`、`Generate Netlist`，不能把日志中的跳过前缀当作重新执行完整构建。
- [展开路径诊断](../distortion/results/board1080-checked-path-diagnosis-20261029.json) 比较了十类表共 152 行，时钟定义及负载不变；六组内部 DDR recovery 的报告覆盖和算术审计通过。这是覆盖审计，不是复位例外批准。两个负 hold 逻辑检查对应 3 条原生变体，WNS -0.189 ns、TNS -0.330 ns。
- 综合网表 `synthesize/board1080_top_syn.vm` SHA256 为 `7d3332f1cb343668a8e57047836e7048a4fe4d13c72c1e0c7084c088fbc942a8`。其中 `cfg_reset_pipe`、`seq_reset_pipe`、`tx_reset_pipe` 各保留 3 个独立 GTP_DFF_C；当前完整双角 STA 中对应配置时钟检查已取得并为非负。该综合结构观察不替代模拟亚稳态或硬件验证。

## 原生路线与 pin 查询

[只读路线及 pin 查询结果](../distortion/results/board1080-checked-route-query-20261029.json) 的原生返回码为 0，精确 Tcl 和完成标记核验通过。源 ADF 及其副本都保持上述 `c411...` 哈希，123 项输入无漂移。10 条 pin 查询的匹配数量为 `1, 1, 1, 1, 1, 104, 1, 14, 1, 7`，并取得 `_N55`、`_N63` 两条目标末段的实际原生路线。

这份查询回执只记录原始结构和候选绕行依据，没有修改路线、保存新 ADF 或请求新 STA。pin 精确匹配证明对象身份及数量，不证明对应时序例外合理；架构图中的候选节点也不证明实际占用或可达性。

## IO 连接与证据来源

[原生功能网表 IO 连接检查](../distortion/results/board1080-checked-io-connectivity-20261029.json) 解析 39,917 个单元，确认 `hd_scl`、`hd_sda` 均从输入缓冲进入两个独立采样 FF；两级间无组合逻辑，输出数据为常数 0，输出三态由各自控制链驱动。检查器记录了原生寄存器 Q 到输出禁止端的真值表；没有仅凭寄存器名称推断 RTL 与原生寄存器极性等价。

[独立 IO 来源核验](../distortion/results/board1080-checked-io-provenance-20261029.json) 将上述检查与本次完整构建、导出执行、原始 ADF 及其副本绑定，重放连接检查并复核 109 源、123 项输入及编译副本。原始连接回执保留其独立运行时的 `ExportADFProvenanceVerified=false`；新的独立来源回执为 true，不能回写或掩盖原始证据。导出功能网表 SHA256 为 `ab792e37357e4103eaa77826e47f21bdd0004b214da8fe8c0283f6548d5ef160`。

这些证据证明当前 ADF 导出网表中的功能连接及其来源，**不证明** RTL 到原生控制 FF 的极性等价、物理放置质量、外部上拉、电压、IO AC 或上板行为；相关接受标志仍为 false。本地执行回执和哈希也不构成独立的进程证明。

## DDR 入口复位连接

[当前候选入口 RDC 审计](../distortion/results/board1080-checked-entry-rdc-20261029.json) 的状态为 pass，范围明确为 DDR 入口功能连接。它绑定当前功能导出和 ADF，识别两个复位同步 FF，第一阶段功能扇出为 1；原始清零函数为 `~(reset_n & power_ready)`。同步输出观察到 10 个直接负载，未沿用历史负载数；展开后同步复位树含 65 个 `V_FFASYN.SR` 叶节点，原始清零树含 88 个 FF 复位端和 1 个 PLL 复位端，均为复位类负载。

这项 pass 不等于复位释放的模拟 MTBF、物理时序或硬件验收；入口 RDC 审计本身没有应用任何复位例外。原始完整构建中的 recovery 失败仍按上表保留，后续精确例外的独立候选见下文。

## 仅绕行候选：独立审计完成

[仅绕行原生审计](../distortion/results/board1080-checked-hold-route-only-20261029.json) 已完成并通过。`checked-hold-1029-a` 保存候选后，`checked-hold-sta-1029-a` 在另一进程重载同一候选并执行双角十类 STA，两次原生执行均退出 0。原始 `c411...` ADF 未改；保存及重载候选的 SHA256 均为 `eb4a20abf54c135677dda7075b93144aefb98dc7c953f785bdf4ef077d91eee2`。123 项输入和编译副本无漂移，两条目标末段的实际绕行及重载路线已核对。

两个数据 hold 失败由实际绕行消除，`ddrphy_sysclk → phy_dq_sysclk_1` fast hold 最差裕量由 -0.189 ns 变为 +0.020 ns，失败 2→0、TNS -0.330→0 ns；原先 3 条负裕量原生变体均匹配并变为正值。该阶段**没有添加时序例外，false-path 为 0**；slow/fast recovery 失败仍为 245/228。

152 行汇总中 149 行不变、3 行 hold 发生变化；另一个 slow hold 时钟对的最差裕量由 +0.336 降到 +0.335 ns，这个 0.001 ns 变化保留在审计中，没有声称其他所有路线或行完全不变。全部 502 条内部复位原生变体的身份和裕量、入口 recovery、时钟定义/负载及外部 IO 缺失警告均保持不变。仅绕行阶段通过的是数据 hold 修复与证据核验，仍不是全部时序或硬件放行。

## 精确复位例外候选：原生 STA 与独立复核通过

在已审计的仅绕行候选基础上，主任务执行了限定范围的 **5 条精确例外**，另存 ADF SHA256 为 `857bf183e52cbd96fb9f378f5087f4c55aba66b22f8488822b7e2dc92450c142`。`checked-final-sta-1029-a` 原生 STA 已退出 0；[执行结束回执](../distortion/build/board1080-timing/checked-final-sta-1029-a/execution-complete.json)、[原生时序报告](../distortion/build/board1080-timing/checked-final-sta-1029-a/board1080_top.rtr)和[原生例外报告](../distortion/build/board1080-timing/checked-final-sta-1029-a/board1080_top_exception.rtr)已存在。以下原生报告结果已通过独立最终审计，见末节有效回执。

| 检查 | slow 最差裕量 / 失败数 | fast 最差裕量 / 失败数 | 每角剩余检查数 |
| --- | --- | --- | --- |
| setup | +0.245 ns / 0 | +2.951 ns / 0 | 60,377 |
| hold | +0.060 ns / 0 | +0.020 ns / 0 | 58,905 |
| recovery | +2.552 ns / 0 | +4.484 ns / 0 | 5,244 |
| removal | +0.250 ns / 0 | +0.079 ns / 0 | 4,010 |
| minimum pulse width | +0.035 ns / 0 | +0.035 ns / 0 | 16,405 |

独立审计的 actual-exception 核对确认：每个 corner 的 recovery、removal 各涉及 245 个逻辑检查、490 个原生变体、252 个边沿身份，setup/hold 例外计数为 0。相对于仅绕行基线，差异限定为 7 个 recovery/removal 时钟对被移除，每类减少 245 项检查；其余报告行、时钟与 IO 警告保持一致。上述覆盖与计数已由新版独立审计器复核通过。

**例外将指定路径排除在对应检查之外，不会使这些路径原来的负 recovery 裕量物理上变正。** 表中正 recovery 最差裕量属于例外后的剩余检查，不能把它当成原失败路径被绕行或延时修好的证明，也不能与前一阶段实际修复数据 hold 混为一谈。

有效独立审计文件为 `distortion/results/board1080-checked-ddr-final-20261029-a.json`；原序列化失败半成品已保留在本地构建目录，不作为有效结果提交。最终 CPU 总计 265 项通过。

外部视频 AC 资料有独立进展：新取得的较完整原厂 PDF 包含数值和模式脚注，但 RX 图文相位、QE 信号范围、实际寄存器配置等仍需确认。见 [外部 AC 资料核查](HDMI_EXTERNAL_AC_FINDINGS_20261029.md)；这些候选数值未应用任何 FDC。**外部 IO 仍缺 55 项输入、110 项输出延迟，当前不能宣称完整时序闭合或硬件放行；未生成、未下载新位流。**

## 最终独立审计完成

`audit_checked_ddr_timing.py` 对固定的 c411 → eb4a → 857b 三版本来源、保存/重载过程、原生脚本/日志及候选哈希作严格绑定，最终真实运行通过。有效结果为 [board1080-checked-ddr-final-20261029-a.json](../distortion/results/board1080-checked-ddr-final-20261029-a.json)。124 行保留时序汇总（含 14 行 HDMI 配置检查）与仅绕行基线完全一致；每角 recovery/removal 各精确 245 个逻辑例外，490 条原生路径变体/252 种边沿变体，setup/hold 数据例外为零。实际双角十类最差值和检查数量与前述最终报告表一致。

最终审计 22 项 CPU 测试通过，本轮合计 265 项；四个既有交付基线及依赖闭包审计再次通过。独立代码复核发现的 Path 键 JSON 序列化错误已修复，CLI 改为先完整序列化再独占写入，并增加失败不留下半成品的测试。首次半成品按原字节归档在本地 ignored 构建目录，未冒充有效回执，未因此重跑或修改 PDS 结果。

本轮结果是 checked HDMI 候选自身的完整源码构建和精确 DDR 时序修复证据。没有生成/下载新位流或访问硬件；外部 IO AC、SCL 上拉和电平、CDC/复位模拟安全性、DDR 训练及真实画面稳定性仍需后续验收。下一步从这份固定候选导出并核验位流，然后推进具备接口条件的实板验证。
