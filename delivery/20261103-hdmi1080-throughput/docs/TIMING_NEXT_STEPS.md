# 后续时序优化建议（尚未修改 RTL）

本记录基于 `C:/Users/Lenovo/Documents/Codex/fpga-build/cache-a` 的 **route-03**：144 个引脚、全部电气属性与 11 个时钟已通过构建审计。工具为 PDS 2025.2 build 211867，器件 PG2L100H / FBG676 / -6。此处只保存问题定位与候选方案；当前交付 RTL、协议、流水线周期和约束均保持原样。

最终三版工程改在 D 盘重新构建，其 STA 须按各自最终 ADF 单独审阅。下列结果不能直接作为其他构建的时序结论。

## 证据范围与身份

- 完成的短报告：`stages/route-03/prj_tasks/pnr_1/report_timing/board1080_top.rtr`，提供双角汇总与每组代表路径。
- 详细 slow 路径：`stages/sta/prj_tasks/pnr_1/report_timing/board1080_top.rtr`。该次独立 STA 因 C 盘空间不足未完整成功；已经写出的 slow setup 路径可逐条读取，其 155 个违规端点及 TNS 与完成的短报告完全一致。fast 结论仅采用已完成短报告的汇总。
- 这里的“端点”按 STA 引脚计数；同一个优化后寄存器可能有多个数据输入端点。

| 文件 | SHA-256 |
| --- | --- |
| route-03 最终 `board1080_top_pnr.adf` | `1b5c702d6522d1e6718f423cd12ab56fa060a53023fbcbd88f54618cdaec4a0a` |
| route-03 短 RTR | `fb034e3ccb8e04b2ca8a2ac2ff938ae35866d485acfaddd0520f79a4a17684c9` |
| 原生 cache 候选 `ddr_compact_neighbour_cache_scatter4.v` | `712d285371ba812e5cd66966657b042817b6a1ca4d010fe00e60c47f953bf1b1` |
| 原生 `board1080-diagnostic.fdc` | `2ff6dd8510e7b0566f550143561ac4138c19cd255944811b4561979f6e8b0f23` |

## Slow setup 精确分类

| 类别 | 违规端点 | WNS / ns | TNS / ns | 实际路径与含义 |
| --- | ---: | ---: | ---: | --- |
| cache 有效位反馈 | 49 | -0.762 | -9.538 | `inner/valid_lines[125]` → 动态选线、miss 判定 → `inner/valid_lines[6]` 等有效位更新输入 |
| cache FIFO 坐标到 lookup | 12 | -0.594 | -2.802 | `read_pointer` → FIFO 坐标选择、邻点算术、线索引 → `neighbour_input[*].lookup_valid[*]` 输入 |
| 显示控制跨域诊断界限 | 70 | -0.316 | -6.589 | `system/grant_epoch[2]` → grant 校验、`control_fault_now` → `output_video/requested_words[16]/CE` 等；约束为 core→pixel 的 8ns datapath max |
| 显示像素域内部控制 | 24 | -0.200 | -2.104 | `output_video/words_0_addrreg[1]` → 像素 RAM、CRC、故障判定 → `lease_epoch[5]/CE` 等 |
| 合计 | 155 | -0.762 | -21.033 | core 同域 61、core→pixel 70、pixel 同域 24 |

最差有效位反馈路径只有 6 级逻辑，数据延迟 8.389ns：逻辑 1.438ns、布线 6.951ns（82.9%）；末段控制网扇出 128，单段布线 2.832ns。FIFO lookup 最差路径为 10 级，逻辑 3.966ns、布线 4.085ns。两类需要分别处理。

显示像素域的 24 个违规端点集中于 `lease_epoch` 16 个、`active_id` 2 个、`expected_crc` 6 个输入。其最差路径布线 11.314ns，占数据延迟的 85.4%。跨域 70 个端点覆盖请求计数、RAM 写使能、last-good 记录和 grant 身份控制；应保留 held-bundle 握手与稳定时间审查。

## 建议顺序与最小修改范围

### 1. 优先验证 CHECK 有效位清除条件的等价简化

当前 CHECK 分支在 `valid_lines[selected_line] && tags[selected_line] == selected_block` 不成立时，同时发起 miss 并清除有效位。有效位本身因此进入全阵列写回控制路径。

可另建可选候选：**保留原 hit/miss、state、计数和 AR 决策，只把 CHECK 的有效位清零独立为 tag 不匹配时执行**。

| 旧有效位 | tag 是否相等 | 原行为 | 候选行为 |
| --- | --- | --- | --- |
| 0 | 相等 | 写 0 | 保持 0 |
| 0 | 不等 | 写 0 | 写 0 |
| 1 | 相等 | 保持 1 | 保持 1 |
| 1 | 不等 | 写 0 | 写 0 |

该变换有望切断 `valid_lines → miss → valid_lines` 组合反馈，保持现有周期和吞吐；实际收益须由综合及布线确认。仍可能存在 tag 比较到高扇出清除网络的路径。

实现时需保持 reset、frame acceptance、scatter 完成、坏返回和 timeout 的赋值优先级，确保有效位只有一个写入过程。四态仿真须覆盖“有效位为 1 的 tag 已被正确初始化”不变量，检查 reset 后未初始化 tag 不会进入有效查询。ARVALID 保持与故障事务处理沿用现有逻辑。

### 2. FIFO 预解码作为独立后续候选

在外层两项 FIFO 入队时保存四邻点 pixel number 与 bounds，可缩短读指针之后的坐标算术和 lookup 索引链，直接对应上述 12 个端点。现有 `pixel_number` 已注册，但同拍 lookup 仍使用 incoming `decoded_number`，该组合路径仍存在。

预解码无法直接切断有效位反馈，也无法处理显示模块的 94 个违规端点。新增入队算术路径、寄存器负载与面积需重新评估；完整 payload、fraction、tag、bounds、frame drain、stall 和 `lookup_refresh` 必须保持对应关系。仅据此次 WNS，不宜优先大改 FIFO。

### 3. 显示模块可另行评估局部 CE 拆分

现有显示实现已将请求/FIFO 控制从实时最终 CRC 判定中分离。`lease_epoch`、`active_id`、`expected_crc` 仍位于 `fault_now` 总控制分支，可研究将其 grant 写入独立为 `!failed && control_fault_now==0 && grant_event && grant_valid`。

等价依据需要测试证明：合法 grant 要求 `!frame_active`，CRC-only 失败边沿要求 `frame_active && consume`，二者互斥。若成立，可消除 CRC 到这些身份寄存器 CE 的路径且保持周期。reset 与单写入者规则、同拍故障优先级需保留。跨域 held-grant 控制链还需另行优化；不放宽现有 8ns 诊断界限。

## 复位与物理验收单列

- Recovery：slow 245 个端点，WNS -3.803ns；fast 225 个端点，WNS -2.954ns。其中 244 / 224 个属于 DDR IP training/reset 到 PHY、IO、TSERDES，另 1 个属于 `power_ready` 到 DDR `rst_seq` 同步器 RS。
- Removal：`power_ready → u_ddrphy_rst_seq_rstn_sync/sig_async_r1[0]/RS` 有 1 个端点违规，slow -0.349ns、fast -0.311ns。该端点 recovery 为 slow -1.394ns、fast -0.865ns。
- 双角 hold 与 minimum pulse width 汇总通过；这两项不能覆盖 recovery/removal。
- DDR 复位路径需结合 IP 的复位/训练协议和真实端点复核，保持与用户数据流水线分开处理。此文不提出新增 false path、multicycle 或宽松时钟约束。
- HDMI 外部输入/输出 AC 延迟、实际采样相位及板卡走线偏差仍待补齐。跨域诊断界限与引脚电气审计不构成完整物理签核；上板还需验证冷启动、PLL/DDR 就绪、复位恢复和长时间运行。

后续任何 RTL 候选应先单独命名并运行像素/metadata 差分、背压、跨 line、frame/reset/fault 回归，再绑定新源码身份完成全帧测试和带完整约束的 PDS 实现。当前三版诊断交付不纳入上述未验证修改。
