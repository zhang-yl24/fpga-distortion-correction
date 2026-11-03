# I 整工程 RAM 地址扇出审计

候选冻结身份 d931793d62bc852c25be57f16528ac7d18dc70fc5760138dcf05e6f443ee8bd5。

最终 H/I PNR 功能网表逐条核验通过，全部 2624 条 cache DRM ADDRA/B pin 对应原逻辑地址位，未发现遗漏、错接或别名改变。

| Lane | 逻辑地址位 | H 物理 driver nets / 每 net DRM负载 | I 物理 driver nets / 每 net DRM负载 |
|---|---:|---|---|
| 上 INDEX10 | 56 | 56 / 32 | 224 / 8 |
| 下 INDEX9 | 52 | 52 / 16 | 104 / 8 |

上 lane 保留 1792 条 DRM 地址连接，下 lane 保留 832 条。最终网表中的复制实际保留，最大 DRM 扇出为 8。之前独立真实 cache synth/devmap 探针的 LUT 真值等价证明见 ../cache-address-fanout8/verification.json。

物理结果边界：H 最差地址路径 state→odd_a[4]→odd_pixels_29 ADA0[5] slack −1.977 ns。I 的 bounded slow core 路径报告未列出 RAM 地址或写使能端点，故可确认它们退出该有限列表，无法从该报告计算所有同一端点改善量或单独签署这些端点全部通过。I 全局 core 最差变为 −2.886 ns，3601 个失败端点。当前源码候选尚未完成物理时序收敛，地址扇出成功不能表述为整体时序通过或整体改善。

I 剩余结构瓶颈：lane1 state_reg[6]→metadata_index[5]→512-bit valid选择→query_cached_valid[3] slack −2.886 ns。state净扇出36延迟1.756 ns，metadata_index净扇出33延迟4.638 ns，最后局部选择至结果再有2.809 ns；说明大范围valid选择仍受布局布线影响。上 lane selected_line[7]→valid_lines[643] slack −2.394 ns，selected_line净扇出196延迟4.509 ns，包含全阵列写选择译码。

下轮只读建议（尚未实现）：

1. 优先按32/64行分组组织 valid 位，使局部低位选择和局部写译码靠近对应组。SELECT现有边沿可同时预译码所选bank及低位，保持slow lookup/fill协议；先用实际cache综合/映射验证驱动复制与读写一致性，再验原生布局。
2. 对 metadata_index 末级选择与 selected_line 写译码，分别做局部扇出限制/分组驱动探针；现有最终RAM地址复制证明不能自动推广到该结构。
3. 若物理布线仍不收敛，可将valid读分为分组读取寄存和末级选择两个阶段，保持II=1。该方案会改变延迟，必须同步处理query队列持有、slow miss后年轻query刷新、tag/valid对齐及frame drain，不应直接给当前流水插拍。
4. 将valid与tag存储合并并用epoch做帧失效属于较大重构，需要上电初始化、epoch回绕清扫和多读口容量证明。当前资源已紧，先核对DRM/LUT预算，避免将未知初值解释为命中。

后续必要测试：全部head/tail旧槽对应、年轻query conflict refill后的刷新、final fill与LOAD边界、frame失效/复位/错误冻结、native1920 exact pixels与DDR lat12/40完整帧。新的原生时序报告仍为最终判断依据。I所有RTL/约束继续冻结。

本目录保存最终逐pin映射、两阶段文件SHA、有限报告分类对照与原始路径节选。Gray CDC与整机功能由 ../cdc-fifo-i、../cdc-user-audit/physical-i-gray-constraints.json、../system-final-i-rowpad640-fanout16 独立记录。
