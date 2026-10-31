# 独立处理输出候选的 HDMI OUT 核对（2026-10-31）

本记录只读检查当前候选，不改变 RTL、IP、时序约束或硬件。用户本轮明确开发板已断电；需要上板时由主代理通知通电。本轮不进行 HDMI IN 或摄像头物理输入排查。

**后续补充已完成**：同一最终ADF的332条原生查询现已覆盖27个数据/控制口与转发时钟的slow/fast、min/max、rise/fall；[完整分析](../distortion/build/processed-output/tx-delay-analysis-20261031-a.json)保存共PLL参考的分段延迟与条件skew窗口。上升沿采样前一像素情景为−1.066至+7.918ns；下降沿采样当前像素且0.4–0.6周期相位情景为−6.412至−0.434ns，零skew不满足后者。实际寄存器采样模式和封装/PCB偏斜仍未知，`ExternalTimingAccepted=false`。这些条件分析不改写下面原始max-only报告的边界；位流和上板准备见[最新记录](PROCESSED_OUTPUT_READY_20261031.md)。

## 已核对的实际配置

`hdmi_tx_init.v` 使用27MHz，7-bit I2C地址59，scratch读写验证加49项寄存器设置。新审计逐项比较 `ms7210_commands.vh` 与原厂 `ms7210_ctl.v`，49项的地址、数据和顺序完全相同，包括 `1281=04`。此前真实SCL/SDA数字回归仍适用。

当前原生ADF为 `1d19936ede917ea1268a17a11fb3b0b34ff84753abefb062ae26d8a2c7c7550b`。`ddr_video_output_1080_board.v` 在像素时钟上升沿同时寄存 RGB/HS/VS/DE；原生报告证实全部27个视频数据/控制端口由该逻辑的 pixel_clk 上升沿发出，同一视频PLL的CLKOUT0转发到 `pix_clk`。名义74.25MHz、周期13.468013ns。

原生时序报告中28个输出端口（包括转发时钟）在slow/fast各有1条**最大**延迟路径，共56条。最慢数据为 `g_out[0]`：slow 10.071ns、fast 7.052ns；对应转发clock的报告最大值为5.882ns、4.225ns。它们均为未设置外部延迟的组合输出路径。fast角的最大值不是最小延迟，不能用于宣称外部hold通过。

## 数据手册的适用范围

重看本机已核查的MS7210完整手册第13、14页图像：表11.1列SDR输入setup0.879ns、hold0.22ns；SDR图的采样窗口围绕PCLK上升沿。脚注明确数字来自仿真，不是实测。时钟占空比范围40%–60%。

当前本机手册仍不含MS7210 `0x1281.bit2` 的定义，也没有把49项初始化设置逐项对应为某一采样边沿；不能将MS7200同地址的输出反相定义移到MS7210。板级数据/clock最坏偏斜和实际修订版走线延迟也没有已验证数值。

因此没有新填 `set_output_delay`，没有将外部AC标为通过。该缺口属于显示采样质量和正式接口时序证据；现有资料没有发现新候选电气方向/电压或引脚冲突。是否进行可逆SRAM诊断试显，应与完整设计的引脚、位流、DDR/CDC核验一起判断，不应把未知AC自动写成“必须继续等待输入调试”或“整板已通过”。显示图像和LED状态可形成新的实测证据，不能倒推全PVT时序保证。

## 可继续做的离板定向查询

PDS官方Tcl手册第45页说明 `get_path_delay` 的 `-min`、`-fast`、`-rise_from/-fall_from/-rise_to/-fall_to` 选项。初次应只做一个数据与一个clock探针确认native对象语法，再扩展各数据位和两种边沿，不以猜测约束改动数据库。

```tcl
report_path_timing -help
get_path_delay -help
get_path_delay -from {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -to {g_out[0]} -min -fast -max_path 8
get_path_delay -from {video_pll/u_gpll/gpll_inst/CLKOUT0} -to {pix_clk} -min -fast -max_path 8
```

主代理随后已在 `physical-tx-probe-20261031-a` 执行上述两条min/fast探针及help：原生exit0、输入无漂移、ADF不变。G0从其FF CLK到端口的最小路径为3.250ns；转发clock从PLL CLKOUT0到端口的最小路径为2.259ns。**两者参考起点不同，不能直接相减计算hold**；G0仍缺PLL→FF时钟脚的传播段。探针自动选择的最小转发clock路径是下降沿，也不能代表上升沿。

此外 `get_path_delay` 最后一行Port增量为0，而原STA报告分别含G0/clock输出封装增量0.104/0.102ns，后续需在同一参考模型下计入。已准备 `build/processed-output/tx-common-reference-20261031.body.tcl` 五条进一步共参考点/边沿探针，尚未由本审计运行。得到完整实际min/max及edge后，可计算相对转发clock的允许板级skew区间，并分别报告已知手册SDR上升沿假设和未证实寄存器模式；不能在未知模式下只给一组“通过”裕量。

## 本轮证据

- 工具：[audit_processed_output_tx.py](../distortion/tools/audit_processed_output_tx.py)。
- 完整核对：[tx-evidence.json](../distortion/results/processed-output-tx-20261031/tx-evidence.json)，绑定当前ADF、原生报告、TX源码与手册哈希，56条路径各保留原始行号及文本摘要哈希。
- 手册来源及版本/原图核查：[此前完整AC资料记录](HDMI_EXTERNAL_AC_FINDINGS_20261029.md)。MS7210 PDF SHA256仍为 `be817ef43ceafac1178a734c21081295fef005a783e99a6f52ef666c146931d2`。手册和图像只保留本机忽略目录，未复制进成果目录。

本审计工具没有运行EDA、没有硬件访问；上述原生探针由主代理在独立副本执行。外部时序接受标志保持false；不覆盖前一轮内部时序零失败和功能图不变的有效结论。
