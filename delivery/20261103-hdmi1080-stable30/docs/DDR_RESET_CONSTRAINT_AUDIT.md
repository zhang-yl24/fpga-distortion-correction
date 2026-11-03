# DDR 复位、时钟关系与优先布线审计

审计对象：`D:/fpga-build/both-final`，PDS 2025.2 ADS；2026-11-03。候选文件放在本目录，原工程及封存文件均未改动。

## 结论与可做改动

1. 当前工程漏载了匹配版本 DDR IP 的两条优先布线约束。`vendor-ddr.rcf` 可用于候选工程的 place/route 阶段。两条命令完整保留，层级前缀由 `I_ips_ddr_top` 改为当前实例 `u_ddr3_test_h`。
2. 当前诊断 FDC 有意移除了原生成约束中的异步时钟组。因此 IP 复位/动态相位控制路径被按固定相位普通同步域分析。`ddr-ip-clock-relations.fdc` 仅恢复厂商原文件的 `rst_clk`、`phy_dq_clk_0`、`phy_dq_clk_1` 三条关系；没有新增自拟的 false_path。
3. 这三条关系修正 STA 的 IP 集成模型。RCF 恢复厂商要求的布线优先级。实际冷启动、复位恢复和长时间 DDR 稳定性仍由上板测试确认。
4. 保留同一路由 ADF 的原诊断 STA，另存恢复厂商约束后的 STA，分开报告两组结果。原报告中的 recovery/removal 数量不得改写为电路故障已修复。

## 匹配证据

参考源位于 Git HEAD `bdaf8c1527fb46cc5b8753415fa02f464a8c08b0`：

`vendor/reference/ddr/2_9_ddr3_test/2_9_ddr3_test/ddr3_test/ipcore/ddr3_test/`

`ip_reference_comparison.json` 保存每个文件的来源和完整 SHA256。当前 IP 与参考文件逐字节一致：

- `ddr3_test.idf`：Pango id042003，HMIC_S 1.10，PG2L100H，FBG676，-6，generator 2022.2-SP6.4 build146967；371 项参数全部相同。
- `ddr3_test.v`、`ddr3_test_ddrphy_top.v`。
- `rtl/ips2l_rst_sync_v1_3.vp`、`rtl/ddrphy/ips2l_ddrphy_reset_ctrl_v1_3.vp`。
- `rtl/ddrphy/ddr3_test_slice_top_v1_10.v`。

对应参考 FDC 保存为 `docs/vendor-ddr-example-ddr_test.fdc`：

- 第7–18行：生成时钟、core 与 phy_dq_sysclk 的 multicycle=2，以及双向0.4 ns uncertainty。
- 第19–23行：free_clk、ref_clk、rst_clk、phy_dq_clk_0/1 单独异步组。
- 第32–34行：CPD 和两条 gate 寄存器的位置约束；当前诊断 FDC 已保留。

参考 RCF 保存为 `docs/vendor-pnr__ddr3_test.rcf`，SHA256 `01a316eaa22fb40512d6d7948533b18296e2cc2860469bbf1ae8dbf0fe872002`。当前 native 中没有 `.rcf`，原 route.tcl 只加载诊断 FDC、UART overlay 与 map PCF。该 RCF 含 `ddrphy_ioclk_gate [0]` 与 `[1]` 两条 prior_net。总线空格书写方式保留厂商原文；载入后必须检查 PDS 对象解析及 route 日志。

## 官方说明

本地厂商包 `docs/board-package-UG042003_HMIC_S_IP.pdf`：

- 第66页，2.8.3：HMIC_S 的具体时钟约束参考 IP `/pnr` 下 `.fdc`；rst_clk 驱动 GPLL 动态移相及复位序列；core/phy 时钟约束需要匹配 ADS/OEM 工具格式。
- 第67页，2.8.4：IP 内部位置约束须与生成 FDC 一致，可按实际实例修改路径。
- 第67页，2.8.5：IP 的优先布线信息位于 `.rcf`，Example Design 自动加载，自建工程需要手动加载。

上述两页已渲染、视觉核对，图片为 `docs/ug042003-page66.png` 和 `docs/ug042003-page67.png`。

PDS 2025.2 自带帮助 `bin/helpDoc_pango.qch` 内的 `UG990202_Design_Workspace_User_Guide.htm` 第3.5.4.16节提供精确命令语义，已读出到 `docs/pds-help/`：单个 `-group` 与其余全部时钟异步，包括派生时钟；需要保留父子同步检查时，应把两者放入同一组。因此厂商单独分组 fast PHY 与 divided PHY 是明确的模型选择，不能仅凭它们拥有共同参考源删除该约束。

## 每条时钟关系的影响

| 恢复的厂商组 | 影响 | 仍保留 |
|---|---|---|
| rst_clk | rst_clk 与其他全部时钟之间的双向路径，包括上电复位进入 IP 的边界，以及 IP 动态相位/复位控制 | rst_clk 域内部的 setup/hold/recovery/removal |
| phy_dq_clk_0 | 第0个 fast PHY 域与其他时钟的交互，包括训练复位及 IO 复位 | 该 fast PHY 域内部路径 |
| phy_dq_clk_1 | 第1个 fast PHY 域与其他时钟的交互，包括训练复位及 IO 复位 | 该 fast PHY 域内部路径 |

未复制 `free_clk`、`ref_clk` 全组，也未为 ddrphy_sysclk 或 phy_dq_sysclk_0/1 新建异步组。board27、cfg_clk、input_pixel、pixel_clk、ddrphy_sysclk 用户域彼此之间现有8 ns max/0 ns min约束继续有效。ddrphy_sysclk 与 phy_dq_sysclk_0/1 的真实数据关系仍保留原 multicycle 和 uncertainty。

这些关系会隐藏以对应 IP 域为一端的全部跨域时序。因此每次最终编译都必须重新检查这些域没有驱动用户寄存器。

## 完整时钟端点归属证据

`clock_endpoint_ownership.json` 由完整 `report_clock_network_slow.db` 解析得到，独立派生时钟分别计数，解析数与工具 drive loads 一致。并非仅取最差50条路径：

| 时钟 | 所有时钟负载 | IP外负载 |
|---|---:|---:|
| rst_clk | 127 | 0 |
| phy_dq_clk_0 | 35 | 0 |
| phy_dq_clk_1 | 84 | 0 |
| phy_dq_sysclk_0 | 35 | 0 |
| phy_dq_sysclk_1 | 84 | 0 |
| ddrphy_sysclk | 19134 | 15287 |

前三域和两个 divided PHY 域的每一项叶节点均位于 `u_ddr3_test_h/`。所有 pin 名、可用源文件及行号已写入 JSON。core 域明确驱动大量用户逻辑，不能对整个 core 域施加单组异步豁免。

复核命令：`python audit_clock_ownership.py --report <final/report_clock_network_slow.db> --output <final/clock_endpoint_ownership.json>`。脚本对缺失时钟、树解析数量不匹配、IP域出现用户负载立即失败。

## power_ready → IP 复位边界

当前慢角 recovery -1.306 ns、removal -0.406 ns 均为：

`power_ready/opit_0_inv_L6Q_perm/CLK` → `u_ddr3_test_h/u_ddrphy_top/u_ddrphy_rst_seq_rstn_sync/sig_async_r1[0]/opit_0_inv_srl/RS`。

top 在 board27 域生成 power_ready，`global_reset_n = reset_n && power_ready` 接到 DDR resetn。DDR PHY 顶层455–483行显示：外部复位同时复位 rst_clk GPLL；已有 `ips2l_rst_sync_v1_3` 在 rst_clk 域采样 rst_gpll_lock，并使用 ddr_rstn 作复位，输出 rst_seq_rstn。厂商单独 rst_clk 组覆盖此异步进入边界。

不能把 top 的 DDR resetn 简单改成“等 rst_clk 同步后才释放”，因为 rst_clk 的 PLL 本身由该输入保持复位，会形成启动依赖循环。

保护块内部 RTL 和综合导出的该模块仍为加密形式，本审计没有解密。可见 STA 说明 `sig_async_r1` 输出 rst_seq_rstn 并驱动后级；目前证据不足以将该 RS 叫作两级同步器的首级，更不能声称第二级已独立核验。恢复厂商约束的依据是完全匹配的 IP 和其生成约束，而非推测同步器内部结构。

同域下游复位分发目前仍受分析：慢角 rst_clk→rst_clk recovery 最小4.183 ns、removal 最小0.417 ns；ddrphy_sysclk→ddrphy_sysclk recovery 最小2.614 ns、removal 最小0.395 ns。新的三条组关系不会移除同域路径。最终候选须重新核对。

若需要器件级 CDC 签核，向厂商确认 ips2l_rst_sync_v1_3 的复位结构、同步级数、异步解除时序合同及 PDS2025.2 对此 IP1.10 的推荐约束。该项仍开放。

## 原诊断结果与验收

原 both-final：慢角 recovery245个失败端点（用户边界1个、IP内部244个），快角232个（用户边界1个、IP内部231个）；两角各1个 removal 失败端点，都是上述边界。16个 setup 失败端点属于用户 core 域，由单独 RTL 时序优化处理。

应用后检查：

1. RCF 已被 route 阶段实际加载，两条对象都解析成功；避免将“加入工程文件”当作已生效。
2. FDC 中三个 clock 名全部找到，例外报告/clock interaction 的作用域与上表一致；所有用户域间8 ns/0 ns约束仍存在。
3. 保留 core↔divided PHY 与全部同域结果；setup、hold、recovery、removal、MPW、Skew 全角检查，记录 IO 外部时序尚缺项。
4. 用最终位流上板统计冷启动/复位成功率、DDR初始化完成时间、错误计数、纯校正新帧率及持续运行。当前审计未执行上板。

建议材料表述：已恢复与当前 IP 版本匹配的复位/PHY 时钟关系及 gate 优先布线约束，保留原诊断结果用于复查；候选的时序报告与板上稳定性分别验收。

## 已有材料的勘误建议

- 将“DDR 复位时序问题已解决”修订为“已查明诊断约束省略厂商 IP 时钟组，并补齐对应约束与优先布线文件；候选时序及板上复位稳定性待/已分别验证”，填写实际状态。
- 将“recovery245个故障”修订为“诊断模型下245个失败端点，其中244个属于IP内部跨相位复位/训练路径，1个属于用户上电复位进入IP的异步边界”。
- 将“16个setup失败和DDR recovery均由流水线解决”拆开：16个setup由用户RTL与布局布线修复；DDR路径按匹配版本厂商模型、RCF与硬件验收处理。
- 删除未有证据的“仅同步器首级放行、二级已验证”等表述；当前保护模块的级数仍未从公开产物中核验。
