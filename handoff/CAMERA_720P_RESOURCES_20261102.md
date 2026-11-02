# 当前 720p 统计矫正版资源占用

2026-11-02。对象是已下载 SRAM 的 `camera720_calibrated_stats_delay_top`：真实 1280×720 镜头矫正、DDR 帧存储、HDMI OUT 与 UART 计数。芯片为 `Logos2-PG2L100H--6-FBG676`。本次只读核算既有原生报告，未重新运行 PDS、未修改 RTL、未下载开发板。

## 当前资源表

主要采用 `build-c/place_route/run_route_optimize.log` 的最终布局布线资源表；百分比由实际 Used/Available 重新计算到两位小数，不沿用 PDS 向上取整的显示值。

| 资源 | 已用 | 总量 | 占用 | 数量余量 |
| --- | ---: | ---: | ---: | ---: |
| LUT，最终物理报告的 LUT 项 | 14,948 | 66,600 | 22.44% | 51,652 |
| FF 寄存器 | 18,692 | 133,200 | 14.03% | 114,508 |
| APM 算术块 | 66 | 240 | 27.50% | 174 |
| DRM，36 Kbit 等效块 | 16.5 | 155 | 10.65% | 138.5 |
| IO | 129 | 300 | 43.00% | 171 |
| GPLL | 3 | 6 | 50.00% | 3 |
| PPLL | 2 | 6 | 33.33% | 4 |
| CLMA 逻辑簇 | 4,652 | 11,675 | 39.85% | 7,023 |
| CLMS 逻辑簇 | 1,858 | 4,975 | 37.35% | 3,117 |
| Distributed RAM，LUT 资源子项 | 610 | 19,900 | 3.07% | 19,290 |
| DDR_PHY 资源 | 7 | 24 | 29.17% | 17 |

LUT 合计为 CLMA `10,434` + CLMS `4,514`；FF 合计为 `13,477 + 5,215`。同一物理报告还单列 `LUT-CONST=1,222+333=1,555` 与 LUT-FF pairs，保留其独立口径，不把各子项简单相加当作另一份总 LUT。表中 LUT 余量仅是该 LUT 项的数量差；实际可放置能力还受到常量、逻辑簇打包、时钟、互连等约束。Distributed RAM 使用逻辑资源，不应在 LUT 数量之外再次作为独立逻辑容量相加。

在较早的 Device Map 阶段，同一 C 版本报告 LUT **15,054/66,600=22.60%**，FF 同为18,692。映射与最终物理报告口径不同，应注明阶段；旧交接里的 **15,068 LUT 属于更早的统计候选，不是本次上板 C 版本**。

原生综合实例统计为 `16 × GTP_DRM36K_E1 + 1 × GTP_DRM18K_E1`，即16.5个36 Kbit等效块。按原语标称位容量换算为608,256 bit（74.25 KiB），器件155块标称总量为5,713,920 bit（697.5 KiB）。这些是片上存储原语容量；具体端口宽度/奇偶位配置下的可用视频数据容量不同，且**不包含外部 DDR3 容量或带宽**。一帧1280×720 RGB565有效像素为1,843,200字节，完整帧存储依赖外部DDR。

其他物理资源：HCKB 21/96、RCKB 4/24、MRCKB 1/12、USCM 5/32、TSERDES 14/48、DDRPHY_IOCLK_DIV 2/6、DDRPHY_CPD 1/12。BKCL 6/6 与 CCS 1/1 已全部使用；这些专用配置/时钟资源的100%不能解释为所有计算资源耗尽，也不能忽略它们对新设计的具体约束。ADC、HSSTLP、PCIE 在本报告中均为0使用。

## 与无 UART 的 720p 矫正版对比

按两版的 `place_route/run_route_optimize.log` 同一口径：

| 资源 | 原 `camera720_calibrated_top` | 当前统计版 | 差值 |
| --- | ---: | ---: | ---: |
| LUT | 14,542 | 14,948 | +406 |
| FF | 18,159 | 18,692 | +533 |
| APM | 66 | 66 | 0 |
| DRM，36 Kbit 等效块 | 16.5 | 16.5 | 0 |
| IO | 128 | 129 | +1 |
| GPLL / PPLL | 3 / 2 | 3 / 2 | 0 / 0 |
| CLMA / CLMS | 4,598 / 1,804 | 4,652 / 1,858 | +54 / +54 |

当前仍有明显的 LUT、寄存器、算术块和片上存储数量余量，UART统计增量很小。但这不证明720p30或1080p能直接实现；当前板上三个计数均约15 FPS，需要进一步测传感器实际PCLK、有效帧与帧调度等待，带宽和时序也必须随优化重新验证。不能将各类资源百分比平均为一个“FPGA总占用率”。

## 原始证据与当前下载绑定

下列路径均相对于仓库根目录。`distortion/work/` 是本机生成目录；仓库副本若未随交付包包含原件，应按以下 SHA 校验原始资料，不能把此说明当作重新执行原生验证。

| 证据 | 路径 | SHA256 |
| --- | --- | --- |
| 当前最终物理资源表 | `distortion/work/camera720-stats-delay/build-c/place_route/run_route_optimize.log` | `75a507b13c458676112186084c862f1bda5a9b27c207be3bada7c5663c642ce4` |
| 当前映射资源表 | `distortion/work/camera720-stats-delay/build-c/device_map/run.log` | `011bd71d31408d5f458f4a13f30b3effa32184eadfdf466da64da3a9ae629fb2` |
| DRM实例原文及完整原生输出 | `distortion/work/camera720-stats-delay/build-c/execution-stdout.log` | `dff1e3ff2641d814babf51db218a8b87962a9f02bedce374d62d67259d56de7b` |
| 构建收据，绑定上述日志 | `distortion/work/camera720-stats-delay/build-c/execution-result.json` | `552be712cc4ebfec41b88c0af79149df93a873b6030faeb8945ea0147d510ce4` |
| 单分支布线修复，功能/放置不变 | `distortion/work/camera720-stats-delay/physical-route-c/result.json` | `27deb553e437b97d2e45609d8eb46a301a21bb8510a35ef2a9c7953efec1e041` |
| 复位验效，功能/FF放置不变 | `distortion/work/camera720-stats-delay/repaired-reset-effect-c.json` | `e08c87dd0988c53efc2dd10c62dd70e9acb686a6a26ef5c237da85dc1c1fac93` |
| 当前位流核验 | `distortion/work/camera720-stats-delay/bit-c2/verification.json` | `d961831dc7e69fc5b36853a761da125ab0ac925ad61820c65be9fa5556e66a0c` |
| 当前 SRAM 下载收据 | `distortion/work/camera720-stats-delay/program-c2/receipt.json` | `fa7e9b908988ee81d903f1a093d52aa46d774b28e02c328997ab9e6bf9ce2398` |
| 原720p矫正版最终物理资源表 | `distortion/work/camera720-calibrated/build-a/place_route/run_route_optimize.log` | `347fa73e1db24e297f0283b046a65177365a462b8d2b3dddd41381a2fa40feb8` |

构建的原ADF为`ac00dabf39ad37064560713ba695f16ac1dea3cfa1968d627c515ca83b081356`；后续单分支布线与精确复位修复保留功能及FF放置，最终ADF为`29e2e519cdb7e27ca43209dd57761bd8e70d2e761decbfebf96f5167b311e19e`。成功下载的位流SHA为`825bbf3920ee8c2d769b0f39a4b11f1c9eddad27247e19d8faeae2bccfaaa952`。上述资源对应这一条构建和下载链；原构建曾有的严格诊断/时序失败历史不因资源统计而被改写。
