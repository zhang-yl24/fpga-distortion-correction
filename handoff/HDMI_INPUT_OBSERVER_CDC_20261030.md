# HDMI 输入观察器 CDC 离线交接（2026-10-30）

后续续接说明：本页记录截至 scoped CDC 审计完成时的独立事件。之后已从同一精确 ADF 离线导出位流并通过独立产物及直接网表/引脚复核，见[位流续接记录](HDMI_INPUT_BITSTREAM_20261030.md)；用户又明确开发板已断电，本轮未下载。最新状态以 [CURRENT.md](CURRENT.md) 顶部为准。温度状态仍未核实；用户已明确暂停测温支线，不以此阻塞正常 HDMI 离线开发。

独立候选 hdmi_uart_input_diag 已完成当前精确源码的数字仿真、原生构建、同步器连通性核查及限定对象的时序审计。限定约束后的双角十类报告均零失败；本轮没有生成新位流或下载开发板。结果不替代外部 HDMI AC、完整 CDC/MTBF、温度、真实输入像素、显示画面或整机畸变矫正验收。

[结果汇总](../distortion/results/hdmi-input-observer-20261030.json)及[提交内证据目录](../distortion/results/hdmi-input-observer-20261030/)记录本轮来源与哈希。03:02 恢复 SRAM、RX/ALL 初始化完成的实板事件使用的是旧 hdmi_uart_delayed_diag，见[独立实板交接](HDMI_INPUT_BRINGUP_20261030.md)，不能作为此观察器上板证据。旧下载日志 over_temp=1 仍待核实，当前建议断电；本轮离线工作没有测温或证明该状态解除。

## 实现与当前证据

新增 [hdmi1080_input_status_cdc.v](../distortion/rtl/experimental/hdmi1080_input_status_cdc.v) 和 [dvp_mode_admission_monitor_cdc.v](../distortion/rtl/experimental/dvp_mode_admission_monitor_cdc.v)，在独立顶层 [hdmi_uart_input_diag.v](../distortion/board/hdmi_uart_input_diag.v) 中选择；原主工程及旧观察器不直接替换。

源域以寄存器输出 Gray 计数，快照通过 request/ack 保持：源域写 held_snapshot 后保持，参考域等待同步 ACK 和额外稳定周期，先采入 ref_snapshot，下一拍才消费。各域业务状态使用本域同步释放复位；停 PCLK 时用复位有效性屏蔽旧状态，故障不会异步复位 DDR 或下游事务。

| 本机证据目录（相对 distortion/build/hdmi-uart-diagnostic/） | 实际结果 |
|---|---|
| input-cdc-sim-1030-c | 当前 7 项源码/helper 哈希一致、无漂移；小尺寸 5 场景通过，27 次快照应用、27 次源快照、1448 次 Gray 检查；完整 1080 光栅两种极性、6 个完整光栅、短行拒绝、停 PCLK、粘滞故障及复位恢复通过 |
| input-cdc-pds-1030-c | PDS 2023.2 原生完整构建退出 0，用时 144.957 秒；46 脚及方向匹配。同域已报告时序无失败，但未限定异步入口的原始总审计仍失败，原报告保留 |
| input-cdc-export-1030-c | 从对应原始 ADF 导出功能网表；161 个真实独立 FF（8 个 V_FFASYN、153 个 V_FFSYN），81 对级间直接 Q→D、同钟、使能有效，均落在各对相同 CLM 中 |
| input-cdc-scoped-1030-c | 精确对象查询通过；只在原始 ADF 副本应用限定约束，保存后以独立进程重载 STA，退出 0、ADF 前后无漂移；双角十类均零失败 |

源代码和 FDC 明确要求同步寄存器保留并禁止折叠为 SRL；早期版本的 Gray 两级采样曾映射为 SRL，不能沿用其映射结论。最终功能网表已逐个证明这 161 个 FF 和 81 对连通性，既不靠寄存器名字存在推断，也不把综合属性声明当作最终映射证明。

仍有 6 条 DeviceMap-2009 的 PAP_ASYNC_REG 被忽略警告，涉及 polarity_sync[0]、timing_bad_sync[0]、timing_good_sync[0]、geometry/p_enable[0]、geometry/r_enable[0]、geometry/source_running_sync[0]。对应 FF 和后级直连已独立核实，警告原样保留；同 CLM 位置不证明属性最终保留，也不量化亚稳态消解时间或 MTBF。功能网表提供连通与位置证据；随后独立进程对 81 对实际 Q→D 执行 get_path_delay 查询，全部返回有限值，默认 slow/max 最大为 0.636 ns。可同模式对照的 4 条原生 STA 路径数值一致；查询仅为 Q→D，不含 CLK→Q、setup 或 MTBF，也不代替逐链完整多角分析。原详细 STA 直接展示 26/81 对，其余连接与数值查询见提交内 chain-delay/chain-delay-review.json。

## 限定时序约束的含义

原报告的同域检查已通过；外部输入像素时钟与板载参考时钟没有固定相位，不能把跨域同步入口当成普通同步组合路径。先确认同步链、Gray 输出和保持快照协议，再对**精确列出的入口**采用有界路径要求。此次没有通过例外改变物理走线速度，也没有取消同步器级间正常时序。

每个工艺角的实际报告与例外表均核对为：

- 74 个同步首级 D、92 个有效快照捕获 D、1 个反向请求首级 D，共 167 条 8 ns MaxDelay 检查保持有效；没有被 false-path 覆盖。
- 只排除上述 167 个入口的 hold 检查；setup false-path 为 0。
- 另仅排除 input_status/p_reset[0:1] 和 input_status/geometry/p_reset[0:1] 四个像素域复位同步 FF 的 RS 引脚 recovery/removal，各 4 项。
- 未匹配到任何第二级 D；时钟摘要和非目标汇总行保持原样。被排除的检查不等于该物理路径获得正裕量。

限定约束后已报告最差裕量如下，单位 ns；每项失败数均为 0：

| 检查 | Slow | Fast |
|---|---:|---:|
| Setup | +1.079 | +1.869 |
| Hold | +0.157 | +0.104 |
| Recovery | +0.659 | +1.889 |
| Removal | +0.184 | +0.026 |
| 最小脉宽 | +6.457 | +6.457 |

这验证了当前限定路径集合及剩余 STA；FullCDCSignoff、HardwareReleaseAllowed 仍为 false。Gray 数据的物理一致性、复位模拟行为、外部采样边沿/板级延迟及可靠性评估仍有独立边界，不能仅由“十类通过”宣称整板可用。

原始报告、ADF、脚本和日志随证据目录交付；较大的原生文件使用 .gz 无损压缩。manifest.json 同时记录存储文件及解压原件的 SHA256，解压后可逐字节核验。prior-mapping-b 保存早期属性未生效的输入与失败证据，native-build 保存未添加入口时序例外的最终映射构建，scoped-cdc 保存增加限定约束后的副本及报告。

## enable 接口边界

当前 HDMI 集成的 enable 来自本域复位有效与 polarity_known；公共复位以外，每轮仅从 0 到 1 启动一次。小尺寸测试覆盖双方都观察到禁用、停 PCLK 导致源域没观察到禁用、停钟公共复位和故障恢复。

通用 monitor **不保证任意短 enable 脉冲安全**：低脉冲若只被源域观察而参考域漏采，参考域 epoch 不一定被清除。复用为可反复门控模块时，须维持 disable 至双方观察，或补充握手与相应测试；不能把本次受限集成的结果扩展到该短脉冲场景。

## 复现入口与重新构建要求

以下命令从仓库根目录执行；使用新后缀，不能覆盖本轮证据。数字仿真依赖本机 Vivado，helper 自行创建目录，调用前目录须不存在：

~~~powershell
$hdmiCdcStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
.\.venv\Scripts\python.exe distortion/tools/run_hdmi_input_cdc_sim.py --workdir "distortion/build/hdmi-uart-diagnostic/input-cdc-sim-$hdmiCdcStamp"
~~~

准备器需要预先创建空工作目录；它只准备工程，不运行 PDS、不生成位流、不下载：

~~~powershell
$hdmiCdcWork = "distortion/build/hdmi-uart-diagnostic/input-cdc-pds-$hdmiCdcStamp"
New-Item -ItemType Directory -Path $hdmiCdcWork -ErrorAction Stop | Out-Null
.\.venv\Scripts\python.exe distortion/tools/prepare_hdmi_input_diagnostic.py --workdir $hdmiCdcWork
~~~

实际原生构建命令已写入该目录 build-plan.json；本机 PDS/许可证配置就绪时按其参数执行：

~~~powershell
$hdmiCdcPlan = Get-Content "$hdmiCdcWork/build-plan.json" -Raw | ConvertFrom-Json
$hdmiCdcExe = $hdmiCdcPlan.Command[0]
$hdmiCdcArgs = $hdmiCdcPlan.Command[1..($hdmiCdcPlan.Command.Count - 1)]
& $hdmiCdcExe @hdmiCdcArgs
$hdmiCdcNativeExit = $LASTEXITCODE
if ($hdmiCdcNativeExit -ne 0) { throw "PDS exited with $hdmiCdcNativeExit" }
~~~

退出 0 只说明流程执行结束。复验须另外保存执行回执、原始日志、来源哈希及自身原生报告，再检查映射/时序；新准备器不会自动应用本轮 scoped 约束。

本轮 scope-plan.json、scope.fdc、apply.tcl、report.tcl 仅绑定下方原始 ADF。它们使用优化后的精确对象名，**不得直接套到新 ADF**。重新综合或布线后必须重新核对独立 FF/级间连通、原生查询的 74/92/1/4 组对象及实际例外集合，再在隔离副本保存并独立重载 STA；不能只改哈希或用调用者提供的目标名放行。

绑定 SHA256：

- 原始 PDS ADF：c6147cfac62256064972e92b8cc8e8c6fa5d1d22e1667622970b91c29bd7d1fa。
- 限定约束后 ADF：d7858e4b705469e6619ba3c99df2c78bf47e2e4f515aeb3b328ea67c70c676a8。
- dvp_mode_admission_monitor_cdc.v：57779e03f9c29d2e168fbabf77ae540675ebfc1ebec3e6e24ba3b7f7b6c6b329。
- hdmi1080_input_status_cdc.v：a301a9960792921f0a8142f5d6eab070b80505ddfd3a297bc733a09ee9c8f71c。

后续先完成剩余物理 CDC/外部接口与硬件状态核实，再单独决定是否生成位流和开展实板观察；本交接不把旧 delayed 诊断的 RX/ALL done 或 Windows 模式识别迁移给新观察器。
