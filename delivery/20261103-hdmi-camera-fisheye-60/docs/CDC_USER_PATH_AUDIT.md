# 用户 CDC 结构与精确约束审计

本记录区分源码协议、原生映射结构和实际时序约束。G 的已列同步链完成映射检查；H 进一步加入配置域复位链保护和四组 Gray 指针约束。当前记录不构成完整 CDC、复位或板级签核。H 的实际路由检查结果另存对应证据，旧构建证据按源哈希保留。

## 已发现并修正的结构问题

E 的 PDS 编译日志明确忽略 `async_reg="true"`。综合 `.vm` 中的两级 DFF 在映射阶段仍被合并为 `gopSRL2`。本包用户同步链改用 `(* PAP_ASYNC_REG=1, syn_srlstyle="registers" *)`；既有 `syn_preserve` 属性保持。独立原生 FIFO probe 已验证该组合保留独立 FF。

G 非 FIFO 清单包含 73 条逻辑链：32 条 `no_grant` 统计链和 `processed_ref` 没有消费者，整链被裁剪；40 条存活链逐条核验两级 FF、目标时钟和第一级至第二级连接。4 条等价复位链共享已存在的完整两级 owner，综合日志明确记录两个级的等价合并。合计检查 74 个实际 FF，其中包含 output 与 FIFO 共享的 reset owner。全部在 device-map 报告中带 `PAP_ASYNC_REG=TRUE`，最终路由原语为 `gopQ`。部分级间 D 输入含本地同步复位 LUT，已通过 LUT INIT 真值枚举验证 release 有效时与前一级 Q 恒等。

G 最终全网表另检出 `hdmi_configuration` 的 `cfg_reset_pipe`、`seq_reset_pipe`、`tx_reset_pipe` 三条三级复位释放链；每条前两级被映射为 SRL。这三条链原本未声明 `async_reg`，因此早期属性替换清单未覆盖。H 新增 `ms72xx_rearm_observed_ctl.v` overlay，仅添加上述属性，剥离属性后全文一致；H 须验证全部 9 个 FF。更新后的全用户逻辑清单为 114 条链、231 个级，包含 FIFO。

证据：`evidence/cdc-user-audit/physical-g-nonfifo-mapping.json`、`physical-g-reset-aliases.log`、`ms72xx-attribute-addendum.json`、`synchronizer-chains-g.json` 与当前 `synchronizer-chains.json`。FIFO 的完整 34 条 Gray 链及 68 个 FF 证据见 `evidence/cdc-fifo-g/`。

## 四组 Gray 指针边界

| 实例 | 源时钟 → 目标时钟 | 源指针位数 | 第一级目标 |
| --- | --- | --- | --- |
| `system/display_fifo` | core → pixel | 10 | `wr_gray_r1[9:0]` |
| `system/display_fifo` | pixel → core | 10 | `rd_gray_w1[9:0]` |
| `system/input_link/input_dma/capture/pixels` | pixel → core | 7 | `wr_gray_r1[6:0]` |
| `system/input_link/input_dma/capture/pixels` | core → pixel | 7 | `rd_gray_w1[6:0]` |

`video_async_fifo` 每个本域时钟最多推进一个指针，Gray 源为寄存器输出；活动 epoch 内相邻值为零位或一位变化。同步后的满/空与距离计算只消费第二级指针。共同复位终止当前 epoch，不能把复位跳零当作正常的 Gray 单位变化证明。两个独立域任意单独复位、停止时钟后继续消费旧事务的恢复行为仍需独立验收。

默认加载文件为 `constraints/gray-pointer-cdc.fdc`。四组各施加 6 ns `set_max_delay -datapath_only` 和 6 ns `set_max_skew`，总计八项命令。core 周期为 8 ns，pixel 约束包络为 6.6667 ns；6 ns 小于最短源周期。PDS 原生报告的 max-delay 从源寄存器时钟端计算 tco，加互连，并扣除目标 setup，因此实际报告范围包含寄存器时序弧。每组 skew 单独计算，四组之间没有混合。

约束使用完整层次、首尾锚定的 `get_cells -hierarchical -regexp`。PDS 在综合前将向量寄存器命名为 `rd_gray[6:0]` 等，综合后拆成逐位对象；表达式同时覆盖向量和逐位名称，并包含源 MSB 的 `wr_binary[9]/rd_binary[9]` 或 `[6]` 别名。目标严格限制到第一级同步器。G 未施加该约束时最高位合并为 binary 名；小型约束 probe 与 H 综合会保留 Gray 最高位名称。审计器据实际数据网络核验两种合法 MSB 名称，低位严格要求对应 Gray 位。

原生双 FIFO probe 完成 compile、synthesize、device-map、P&R、STA。slow/fast 各恰好 34 条实际 source-net→first-stage 路径和 4 个独立 skew 组，全部满足 6 ns；slow 最大数据延迟 0.932 ns、最小 slack 4.932 ns，fast 分别 0.569 ns、5.357 ns。G 冻结源码在独立工程重编译，16 次绑定查询均只命中预期单个向量对象，8 个唯一对象覆盖源 34 位和目标 34 位；0 error、0 critical warning。证据位于 `evidence/cdc-gray-constraint-probe/`。这些小工程数值不替代 H 实际 1080p 路由结果。

`prepare_candidate.py` 为原生报告添加 `-report_max_skew` flag。独立导出、SHA 校验和重定位已验证：116 个输入，Gray FDC 和报告选项均保留。工具未改变厂商时钟关系、用户全域 clock-group 或 false-path。

H 完成后的检查命令：

```text
python tools/verify_gray_constraints.py --project D:/f60-run/physical-h --output evidence/physical-h/gray-constraints.json
```

审计要求两个 corner 各恰好 34 个正确目标、正确实际源网络、6 ns datapath-only delay 和 4 个完整 skew 组；负 slack 保留完整数值及原始报告 SHA，写 `FAIL` 并返回非零状态。已用注入 -0.125 ns 和缺报告场景验证失败留证。第一级至第二级的同域 setup/hold、同步器恢复时间和 MTBF 仍由原生时序及器件方法另行检查。 原生 probe 的两个 corner 均不再列出 Gray 第一级 D 的普通 hold 路径，第二级 D 的 34 条同域 hold 路径仍在报告中，见 `probe-hold-observation.json`；这记录了 PDS 对 datapath-only 的实际处理，H 仍须复核同域 hold。

## H 实际路由结果

H 源身份为 `fe756ccb51cbbf1ea30a337eec0c22d5419fd4cdb5cd34dad2097bcde880e44d`。最终 `_pnr.adf` 在独立目录只读导出完整仿真网表，没有修改 H 工程。

非 FIFO 共 76 条逻辑链中，33 条无消费者链仍整链裁剪，43 条存活链包含 89 个逻辑级。等价共享后共 83 个实际 FF，全部映射为 `gopQ`，device-map 属性存在，逐级有效态连接通过；新增三条配置域三级复位链的 9 个 FF 全部独立。证据为 `physical-h-nonfifo-mapping.json`，它同时绑定原始 PNR 数据库、完整网表、综合日志、映射报告、逻辑清单和 candidate-plan 哈希。

四组 Gray 在 slow/fast 各精确覆盖 34 条实际路径，数据边界与 skew 全部通过。slow 最大数据延迟 1.011 ns、最小 max-delay slack 4.853 ns、最大实际 skew 1.170 ns；fast 分别为 0.623 ns、5.303 ns、0.853 ns。完整逐位记录位于 `physical-h-gray-constraints.json`；四份原始 XML 报告压缩保存在 `physical-h-reports/`，附原文及压缩件 SHA。此结论只覆盖已列 CDC 结构和 Gray 边界，其余 setup/hold、held bundle、复位和外部接口仍按各自证据判定。

## I 实际路由结果

I 源身份为 `d931793d62bc852c25be57f16528ac7d18dc70fc5760138dcf05e6f443ee8bd5`，所有 23 个 RTL/约束覆盖输入与冻结清单匹配。最终 PNR 网表统一只读导出供三项审计共用；源码、FDC 和 prepare 保持冻结。

非 FIFO 结果与 H 的审计范围一致：76 条逻辑链、33 条无消费者整链裁剪、43 条存活链/89 个逻辑级、83 个实际 `gopQ`。包含配置域三条三级复位释放链。全部实际 FF 的目标时钟、属性和逐级活动态连接检查通过；命名常量网络额外核验实际 LUT INIT，逻辑清单的源码哈希逐文件与 I candidate-plan 强校验。

四组 Gray 在 slow/fast 各精确覆盖 34 个实际源网络到第一级 D，6 ns max-delay 和四组 6 ns max-skew 全部通过。slow 最大数据延迟 1.306 ns、最小 max-delay slack 4.558 ns、最大实际 skew 1.389 ns；fast 分别为 0.799 ns、5.127 ns、0.982 ns。逐位证据为 `physical-i-gray-constraints.json`；非 FIFO 结构为 `physical-i-nonfifo-mapping.json`；四份原始 XML 压缩在 `physical-i-reports/`，均绑定 SHA。FIFO 的结构逐边审计由 `evidence/cdc-fifo-i/` 单独记录。

上述通过项不覆盖 held-bundle 的完整数据稳定窗口、组合 level/toggle 源毛刺、UART 多位诊断快照一致性、复位恢复/移除及单域复位恢复、同步器 MTBF、HDMI 外部 AC 和真实板卡长期新帧率。整机同域与 DDR PHY setup/hold 也须使用 I 的独立物理时序报告，不能由 Gray 子项通过推导。

## 其他跨域分类与剩余证明

| 类别 | 已核对的源码结构 | 剩余工作 |
| --- | --- | --- |
| 两级 level/toggle | capture grant/end/ACK；display request/grant/ACK/done；board fault、VS、活动状态；I2C 输入采样 | 实际 FF 与目标时钟核对；组合源的毛刺、短脉冲捕获和事件丢失条件需逐项审查 |
| capture grant held bundle | bank/id 与请求 toggle 同拍保存；grant busy 保持到完成握手 | 给出最早控制检测与最慢数据到达的物理窗口；核对所有消费者 |
| capture end held bundle | good/bank/id/pixels/CRC/fault 与 end toggle 保存；等待 ACK 时禁止下一 capture | 同上，并覆盖共同 reset 终止 epoch |
| display request/grant/done held bundle | grant response busy、done pending 在 ACK 返回前防止覆写；请求带 epoch，超时进入故障 | 审查每个 bundle 的完整 fanout、比较流水和最早采样边界，形成专用数据路径界限 |
| sticky fault 多位总线 | board/system fault 为粘性状态；部分消费由已同步故障 level 触发 | `board_fault` 到 UART 快照没有独立 ACK，改变边沿的一致性语义需明确；同步 level 限定的其他消费仍需数据稳定窗口 |
| reset/RDC | common 异步断言、本域同步释放；用户保护属性已补齐 | 最终映射、恢复/移除、时钟停止/重启及分区复位传播；厂商加密复位内部不作推定 |
| 外部接口 | 输入像素时钟采用 150 MHz 包络，I2C 两级采样 | HDMI 外部 AC、板上时钟/复位、长期连续运行和每秒新帧数仍待验收 |

held bundle 与 toggle 同拍更新，接收方两级同步后再在时钟沿处理事件，源码可建立约两目标周期的最早稳定窗口。物理证明还需要控制最早延迟、数据最慢延迟、目标 setup、复位行为和全 fanout；保持到 ACK 单独不足以证明该窗口。当前没有把这些总线纳入 Gray 约束，也没有加入泛化跨域豁免。

E 采样报告中的 core→pixel、pixel→core、board27→core 跨域负 slack 已按实际源/目标归类到 `physical-e-crossing-inventory.json`。报告存在 max-path 采样上限，未出现的路径不能据此认定已通过。

## 本机原始依据

官方本机目录：`E:/PDS_2025.2-ads-win64/pango/PDS_2025.2-ads/doc/`。

- `UG990102_ADS_Synthesis_User_Guide.pdf`：8.2.39，PDF 181 页/印刷 179 页，`PAP_ASYNC_REG`；8.2.21，PDF 142 页/印刷 140 页，`syn_srlstyle="registers"`。
- `UG990004_Tcl_Command_User_Guide.pdf`：4.57，PDF 66 页/印刷 64 页，`gen_netlist -input_db_file ... -func_sim_only`。原生工具只接受 P&R 数据库；map 数据库导出被明确拒绝，故 device-map 的属性证据与 route 的完整连线证据分别记录。
- `UG990002_Pango_Design_Suite_User_Guide.pdf`：PDF 212–213 页/印刷 210–211 页，Max Skew 与 Exception 报告。
- PDS 2025.2 build 211867 的实际命令帮助见 `pds-constraint-command-help.log`；本工具提供 `set_max_skew`，没有 `set_bus_skew`。
- 厂商自带 `ip/module_ip/ipmc_flex_ram/ipmc_flex_ram_eval/ipmc_fifo/ipmc_drm_afifo.sdc` 同样使用源指针到第一级指针的 `set_max_delay -datapath_only`。本包的具体对象和数值通过独立原生 probe 验证。
