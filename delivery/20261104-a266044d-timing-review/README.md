# a266044d 摄像头诊断版：四条 setup 时序违例

**状态：时序未闭合。此报告用于定位问题，不能视为稳定性或摄像头兼容性验证通过。**

- 对应位流 SHA256：`a266044d4da4b8883fc7fa1e9250f62aee37bbf27df349354b2a11250129c547`。
- 位流文件：`camera-op-input-firstloss-timing-unclosed4-setup-minus32ps-diagnostic.sbit`（3,791,112 字节）。
- PDS 2025.2-ads；器件 PG2L100H-6FBG676；顶层 board1080_top。
- 最终独立 min/max STA 于 2026-11-04 11:33:18（UTC+8）完成；慢角 setup 4 个失败端点，WNS −0.032 ns。其他 11 个 corner/check 组合报告无违例。
- 本包直接提取该位流身份文件绑定的最终报告，不重新运行 PDS，不改变工程、约束或板卡。

## 四条失败路径

| # | Slack (ns) | Capture clock | Endpoint | Data delay (ns) | Route delay |
|---|---:|---|---|---:|---|
| 1 | -0.032 | `phy_dq_sysclk_0` | `u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[11].u_outbuft_addr0/opit_1/TX_DATA[0]` | 6.372 | 5.884 (92.3%) |
| 2 | -0.023 | `phy_dq_sysclk_1` | `u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[3].ddrphy_data_slice/u_tserdes0_dqs/oserdes_inst/TS_CTRL[7]` | 6.212 | 5.805 (93.4%) |
| 3 | -0.012 | `phy_dq_sysclk_0` | `u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[14].u_outbuft_addr0/opit_1/TX_DATA[2]` | 6.352 | 5.758 (90.6%) |
| 4 | -0.006 | `phy_dq_sysclk_0` | `u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[5].u_outbuft_addr0/opit_1/TX_DATA[2]` | 6.346 | 5.973 (94.1%) |

四条均从 `ddrphy_sysclk` 发起，边沿为 rise-rise。报告实际应用的例外为 `MultiCycle Path Setup -end 2`，Requirement 为 10.000 ns。该描述是对现有报告的转述，不表示建议新增或放宽例外。完整约束匹配与时钟信息见原始报告。

## 路径 1：slack -0.032 ns

- **Slack**：`-0.032`
- **Logic Levels**：`2`
- **High Fanout**：`64`
- **Start Point**：`u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/ddrphy_dqs_rddata_align/this_group_ca_dly/opit_0_inv/CLK`
- **End Point**：`u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[11].u_outbuft_addr0/opit_1/TX_DATA[0]`
- **Exception**：`MultiCycle Path Setup -end 2`
- **Launch Clock**：`ddrphy_sysclk`
- **Capture Clock**：`phy_dq_sysclk_0`
- **Clock Edges**：`rise-rise`
- **Clock Skew**：`-2.544`
- **Launch Clock Delay**：`5.623`
- **Capture Clock Delay**：`2.640`
- **Clock Pessimism Removal**：`0.439`
- **Requirement**：`10.000`
- **Data delay**：`6.372`
- **Logic delay**：`0.488 (7.7%)`
- **Route delay**：`5.884 (92.3%)`

### Data arrival time is 11.995

| Location | Delay Type | Incr | Path | Trans | Logical Resource |
|---|---|---|---|---|---|
| Clock ddrphy_sysclk (rising edge) |  | 0.000 | 0.000 | r |  |
| N3 |  | 0.000 | 0.000 | r | clk_p (port) |
|  | net (fanout=1) | 0.110 | 0.110 |  | clk_p |
| IOBD_372_468/DIN | td | 0.970 | 1.080 | r | u_gtp/opit_0/O |
|  | net (fanout=1) | 0.000 | 1.080 |  | u_gtp/ntD |
| IOLHR_364_468/DI_TO_CLK | td | 0.105 | 1.185 | r | u_gtp/opit_2/DI_TO_CLK |
|  | net (fanout=3) | 0.294 | 1.479 |  | ddr_ref_clk |
| MRCKB_361_456/CLKOUT_U_P | td | 0.148 | 1.627 | r | u_ddr3_test_h/u_ddrphy_top/u_clkbufm/clkbufm_inst/CLKOUT_P |
|  | net (fanout=2) | 0.432 | 2.059 |  | u_ddr3_test_h/u_ddrphy_top/pll_refclk |
| RCKB_363_456/CLKOUT | td | 0.177 | 2.236 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].u_clkbufr/goprclk/CLKOUT |
|  | net (fanout=1) | 0.450 | 2.686 |  | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/ppll_clkin [0] |
| PPLL_367_307/CLKOUTPHY | td | 0.037 | 2.723 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].ddrphy_ppll/u_ppll/ppll_inst/CLKOUTPHY |
|  | net (fanout=36) | 0.045 | 2.768 |  | u_ddr3_test_h/u_ddrphy_top/phy_ioclk_fb |
| DDRPHY_IOCLK_DIV_368_310/CLKOUT | td | 0.123 | 2.891 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].u_ddrphy_ioclkdiv/ddrphy_ioclk_div_inst/CLKOUT |
|  | net (fanout=35) | 0.000 | 2.891 |  | u_ddr3_test_h/u_ddrphy_top/phy_sysclk_fb |
| GPLL_367_769/CLKOUT0 |  | 0.431 | 3.322 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_gpll/u_gpll/gpll_inst/CLKOUT0 |
|  | net (fanout=1) | 0.753 | 4.075 |  | u_ddr3_test_h/u_ddrphy_top/gpll_clkout0 |
| USCM_215_636/CLKOUT | td | 0.168 | 4.243 | r | u_ddr3_test_h/u_ddrphy_top/u_sysclk_bufg/gopclkbufg/CLKOUT |
|  | net (fanout=15617) | 1.380 | 5.623 |  | core_clk |
| CLMS_339_925/CLK |  |  |  | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/ddrphy_dqs_rddata_align/this_group_ca_dly/opit_0_inv/CLK |
| CLMS_339_925/Q2 | tco | 0.203 | 5.826 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/ddrphy_dqs_rddata_align/this_group_ca_dly/opit_0_inv/Q |
|  | net (fanout=2) | 2.565 | 8.391 |   | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/debug_data [135] |
| CLMA_333_582/Y2 | td | 0.074 | 8.465 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/ddrphy_dqs_rddata_align/all_group_ca_dly_r2/opit_0_inv_L6QQ_perm/L6 |
|  | net (fanout=64) | 1.470 | 9.935 |   | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/all_group_ca_dly |
| CLMA_357_391/CR1 | td | 0.211 | 10.146 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/ddrphy_control_path_adj/adj_addr_95:88_3[1]/gateop_LUT6DL5_perm/L5 |
|  | net (fanout=1) | 1.849 | 11.995 |   | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/adj_addr [88] |
| IOLHR_364_420/TX_DATA[0] |  |  |  | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[11].u_outbuft_addr0/opit_1/TX_DATA[0] |

### Data required time is 11.963

| Location | Delay Type | Incr | Path | Trans | Logical Resource |
|---|---|---|---|---|---|
| Clock phy_dq_sysclk_0 (rising edge) |  | 10.000 | 10.000 | r |  |
| N3 |  | 0.000 | 10.000 | r | clk_p (port) |
|  | net (fanout=1) | 0.110 | 10.110 |  | clk_p |
| IOBD_372_468/DIN | td | 0.829 | 10.939 | r | u_gtp/opit_0/O |
|  | net (fanout=1) | 0.000 | 10.939 |  | u_gtp/ntD |
| IOLHR_364_468/DI_TO_CLK | td | 0.091 | 11.030 | r | u_gtp/opit_2/DI_TO_CLK |
|  | net (fanout=3) | 0.247 | 11.277 |  | ddr_ref_clk |
| MRCKB_361_456/CLKOUT_U_P | td | 0.126 | 11.403 | r | u_ddr3_test_h/u_ddrphy_top/u_clkbufm/clkbufm_inst/CLKOUT_P |
|  | net (fanout=2) | 0.367 | 11.770 |  | u_ddr3_test_h/u_ddrphy_top/pll_refclk |
| RCKB_363_456/CLKOUT | td | 0.149 | 11.919 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].u_clkbufr/goprclk/CLKOUT |
|  | net (fanout=1) | 0.383 | 12.302 |  | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/ppll_clkin [0] |
| PPLL_367_307/CLKOUTPHY | td | 0.026 | 12.328 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].ddrphy_ppll/u_ppll/ppll_inst/CLKOUTPHY |
|  | net (fanout=36) | 0.023 | 12.351 |  | u_ddr3_test_h/u_ddrphy_top/phy_ioclk_fb |
| DDRPHY_IOCLK_DIV_368_310/CLKOUT | td | 0.101 | 12.452 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].u_ddrphy_ioclkdiv/ddrphy_ioclk_div_inst/CLKOUT |
|  | net (fanout=35) | 0.188 | 12.640 |  | u_ddr3_test_h/u_ddrphy_top/phy_sysclk_fb |
| IOLHR_364_420/OCLKDIV |  |  |  | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[11].u_outbuft_addr0/opit_1/OCLKDIV |
| clock pessimism |  | 0.439 | 13.079 |  |  |
| clock uncertainty |  | -0.760 | 12.319 |  |  |
| Setup time |  | -0.356 | 11.963 |  |  |

## 路径 2：slack -0.023 ns

- **Slack**：`-0.023`
- **Logic Levels**：`2`
- **High Fanout**：`36`
- **Start Point**：`u_ddr3_test_h/u_ddrphy_top/ddrphy_dfi/phy_wrdata_en_d[0]/opit_0_inv_L6Q_perm/CLK`
- **End Point**：`u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[3].ddrphy_data_slice/u_tserdes0_dqs/oserdes_inst/TS_CTRL[7]`
- **Exception**：`MultiCycle Path Setup -end 2`
- **Launch Clock**：`ddrphy_sysclk`
- **Capture Clock**：`phy_dq_sysclk_1`
- **Clock Edges**：`rise-rise`
- **Clock Skew**：`-2.741`
- **Launch Clock Delay**：`5.605`
- **Capture Clock Delay**：`2.640`
- **Clock Pessimism Removal**：`0.224`
- **Requirement**：`10.000`
- **Data delay**：`6.212`
- **Logic delay**：`0.407 (6.6%)`
- **Route delay**：`5.805 (93.4%)`

### Data arrival time is 11.817

| Location | Delay Type | Incr | Path | Trans | Logical Resource |
|---|---|---|---|---|---|
| Clock ddrphy_sysclk (rising edge) |  | 0.000 | 0.000 | r |  |
| N3 |  | 0.000 | 0.000 | r | clk_p (port) |
|  | net (fanout=1) | 0.110 | 0.110 |  | clk_p |
| IOBD_372_468/DIN | td | 0.970 | 1.080 | r | u_gtp/opit_0/O |
|  | net (fanout=1) | 0.000 | 1.080 |  | u_gtp/ntD |
| IOLHR_364_468/DI_TO_CLK | td | 0.105 | 1.185 | r | u_gtp/opit_2/DI_TO_CLK |
|  | net (fanout=3) | 0.294 | 1.479 |  | ddr_ref_clk |
| MRCKB_361_456/CLKOUT_U_P | td | 0.148 | 1.627 | r | u_ddr3_test_h/u_ddrphy_top/u_clkbufm/clkbufm_inst/CLKOUT_P |
|  | net (fanout=2) | 0.432 | 2.059 |  | u_ddr3_test_h/u_ddrphy_top/pll_refclk |
| RCKB_363_456/CLKOUT | td | 0.177 | 2.236 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].u_clkbufr/goprclk/CLKOUT |
|  | net (fanout=1) | 0.450 | 2.686 |  | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/ppll_clkin [0] |
| PPLL_367_307/CLKOUTPHY | td | 0.037 | 2.723 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].ddrphy_ppll/u_ppll/ppll_inst/CLKOUTPHY |
|  | net (fanout=36) | 0.045 | 2.768 |  | u_ddr3_test_h/u_ddrphy_top/phy_ioclk_fb |
| DDRPHY_IOCLK_DIV_368_310/CLKOUT | td | 0.123 | 2.891 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].u_ddrphy_ioclkdiv/ddrphy_ioclk_div_inst/CLKOUT |
|  | net (fanout=35) | 0.000 | 2.891 |  | u_ddr3_test_h/u_ddrphy_top/phy_sysclk_fb |
| GPLL_367_769/CLKOUT0 |  | 0.431 | 3.322 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_gpll/u_gpll/gpll_inst/CLKOUT0 |
|  | net (fanout=1) | 0.753 | 4.075 |  | u_ddr3_test_h/u_ddrphy_top/gpll_clkout0 |
| USCM_215_636/CLKOUT | td | 0.168 | 4.243 | r | u_ddr3_test_h/u_ddrphy_top/u_sysclk_bufg/gopclkbufg/CLKOUT |
|  | net (fanout=15617) | 1.362 | 5.605 |  | core_clk |
| CLMS_351_319/CLK |  |  |  | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_dfi/phy_wrdata_en_d[0]/opit_0_inv_L6Q_perm/CLK |
| CLMS_351_319/Q3 | tco | 0.203 | 5.808 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_dfi/phy_wrdata_en_d[0]/opit_0_inv_L6Q_perm/L6Q |
|  | net (fanout=36) | 2.292 | 8.100 |   | u_ddr3_test_h/u_ddrphy_top/phy_wrdata_en [0] |
| CLMA_327_612/Y0 | td | 0.108 | 8.208 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[3].ddrphy_data_slice/ddrphy_wdata_path_adj/N910_13/gateop_perm/L6 |
|  | net (fanout=2) | 1.095 | 9.303 |   | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[3].ddrphy_data_slice/ddrphy_wdata_path_adj/_N1134 |
| CLMA_357_649/Y1 | td | 0.096 | 9.399 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[3].ddrphy_data_slice/ddrphy_wdata_path_adj/N912_0[3]_1/gateop_perm/L6 |
|  | net (fanout=2) | 2.418 | 11.817 |   | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[3].ddrphy_data_slice/adj_wrdqs_en [6] |
| TSERDES_371_614/TS_CTRL[7] |  |  |  | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[3].ddrphy_data_slice/u_tserdes0_dqs/oserdes_inst/TS_CTRL[7] |

### Data required time is 11.794

| Location | Delay Type | Incr | Path | Trans | Logical Resource |
|---|---|---|---|---|---|
| Clock phy_dq_sysclk_1 (rising edge) |  | 10.000 | 10.000 | r |  |
| N3 |  | 0.000 | 10.000 | r | clk_p (port) |
|  | net (fanout=1) | 0.110 | 10.110 |  | clk_p |
| IOBD_372_468/DIN | td | 0.829 | 10.939 | r | u_gtp/opit_0/O |
|  | net (fanout=1) | 0.000 | 10.939 |  | u_gtp/ntD |
| IOLHR_364_468/DI_TO_CLK | td | 0.091 | 11.030 | r | u_gtp/opit_2/DI_TO_CLK |
|  | net (fanout=3) | 0.247 | 11.277 |  | ddr_ref_clk |
| MRCKB_361_456/CLKOUT_U_P | td | 0.126 | 11.403 | r | u_ddr3_test_h/u_ddrphy_top/u_clkbufm/clkbufm_inst/CLKOUT_P |
|  | net (fanout=2) | 0.367 | 11.770 |  | u_ddr3_test_h/u_ddrphy_top/pll_refclk |
| RCKB_363_762/CLKOUT | td | 0.149 | 11.919 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[1].u_clkbufr/goprclk/CLKOUT |
|  | net (fanout=1) | 0.383 | 12.302 |  | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/ppll_clkin [1] |
| PPLL_367_613/CLKOUTPHY | td | 0.026 | 12.328 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[1].ddrphy_ppll/u_ppll/ppll_inst/CLKOUTPHY |
|  | net (fanout=85) | 0.023 | 12.351 |  | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/phy_clk_p [1] |
| DDRPHY_IOCLK_DIV_368_616/CLKOUT | td | 0.101 | 12.452 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[1].u_ddrphy_ioclkdiv/ddrphy_ioclk_div_inst/CLKOUT |
|  | net (fanout=84) | 0.188 | 12.640 |  | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/phy_sysclk_p [1] |
| TSERDES_371_614/OCLKDIV |  |  |  | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[3].ddrphy_data_slice/u_tserdes0_dqs/oserdes_inst/OCLKDIV |
| clock pessimism |  | 0.224 | 12.864 |  |  |
| clock uncertainty |  | -0.760 | 12.104 |  |  |
| Setup time |  | -0.310 | 11.794 |  |  |

## 路径 3：slack -0.012 ns

- **Slack**：`-0.012`
- **Logic Levels**：`2`
- **High Fanout**：`64`
- **Start Point**：`u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/ddrphy_dqs_rddata_align/this_group_ca_dly/opit_0_inv/CLK`
- **End Point**：`u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[14].u_outbuft_addr0/opit_1/TX_DATA[2]`
- **Exception**：`MultiCycle Path Setup -end 2`
- **Launch Clock**：`ddrphy_sysclk`
- **Capture Clock**：`phy_dq_sysclk_0`
- **Clock Edges**：`rise-rise`
- **Clock Skew**：`-2.544`
- **Launch Clock Delay**：`5.623`
- **Capture Clock Delay**：`2.640`
- **Clock Pessimism Removal**：`0.439`
- **Requirement**：`10.000`
- **Data delay**：`6.352`
- **Logic delay**：`0.594 (9.4%)`
- **Route delay**：`5.758 (90.6%)`

### Data arrival time is 11.975

| Location | Delay Type | Incr | Path | Trans | Logical Resource |
|---|---|---|---|---|---|
| Clock ddrphy_sysclk (rising edge) |  | 0.000 | 0.000 | r |  |
| N3 |  | 0.000 | 0.000 | r | clk_p (port) |
|  | net (fanout=1) | 0.110 | 0.110 |  | clk_p |
| IOBD_372_468/DIN | td | 0.970 | 1.080 | r | u_gtp/opit_0/O |
|  | net (fanout=1) | 0.000 | 1.080 |  | u_gtp/ntD |
| IOLHR_364_468/DI_TO_CLK | td | 0.105 | 1.185 | r | u_gtp/opit_2/DI_TO_CLK |
|  | net (fanout=3) | 0.294 | 1.479 |  | ddr_ref_clk |
| MRCKB_361_456/CLKOUT_U_P | td | 0.148 | 1.627 | r | u_ddr3_test_h/u_ddrphy_top/u_clkbufm/clkbufm_inst/CLKOUT_P |
|  | net (fanout=2) | 0.432 | 2.059 |  | u_ddr3_test_h/u_ddrphy_top/pll_refclk |
| RCKB_363_456/CLKOUT | td | 0.177 | 2.236 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].u_clkbufr/goprclk/CLKOUT |
|  | net (fanout=1) | 0.450 | 2.686 |  | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/ppll_clkin [0] |
| PPLL_367_307/CLKOUTPHY | td | 0.037 | 2.723 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].ddrphy_ppll/u_ppll/ppll_inst/CLKOUTPHY |
|  | net (fanout=36) | 0.045 | 2.768 |  | u_ddr3_test_h/u_ddrphy_top/phy_ioclk_fb |
| DDRPHY_IOCLK_DIV_368_310/CLKOUT | td | 0.123 | 2.891 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].u_ddrphy_ioclkdiv/ddrphy_ioclk_div_inst/CLKOUT |
|  | net (fanout=35) | 0.000 | 2.891 |  | u_ddr3_test_h/u_ddrphy_top/phy_sysclk_fb |
| GPLL_367_769/CLKOUT0 |  | 0.431 | 3.322 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_gpll/u_gpll/gpll_inst/CLKOUT0 |
|  | net (fanout=1) | 0.753 | 4.075 |  | u_ddr3_test_h/u_ddrphy_top/gpll_clkout0 |
| USCM_215_636/CLKOUT | td | 0.168 | 4.243 | r | u_ddr3_test_h/u_ddrphy_top/u_sysclk_bufg/gopclkbufg/CLKOUT |
|  | net (fanout=15617) | 1.380 | 5.623 |  | core_clk |
| CLMS_339_925/CLK |  |  |  | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/ddrphy_dqs_rddata_align/this_group_ca_dly/opit_0_inv/CLK |
| CLMS_339_925/Q2 | tco | 0.203 | 5.826 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/ddrphy_dqs_rddata_align/this_group_ca_dly/opit_0_inv/Q |
|  | net (fanout=2) | 2.565 | 8.391 |   | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/debug_data [135] |
| CLMA_333_582/Y2 | td | 0.074 | 8.465 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/ddrphy_dqs_rddata_align/all_group_ca_dly_r2/opit_0_inv_L6QQ_perm/L6 |
|  | net (fanout=64) | 1.306 | 9.771 |   | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/all_group_ca_dly |
| CLMA_357_481/CR3 | td | 0.317 | 10.088 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/ddrphy_control_path_adj/adj_addr_119:112_3[2]/gateop_LUT6DL5_perm/L5 |
|  | net (fanout=2) | 1.887 | 11.975 |   | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/adj_addr [113] |
| IOLHR_364_504/TX_DATA[2] |  |  |  | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[14].u_outbuft_addr0/opit_1/TX_DATA[2] |

### Data required time is 11.963

| Location | Delay Type | Incr | Path | Trans | Logical Resource |
|---|---|---|---|---|---|
| Clock phy_dq_sysclk_0 (rising edge) |  | 10.000 | 10.000 | r |  |
| N3 |  | 0.000 | 10.000 | r | clk_p (port) |
|  | net (fanout=1) | 0.110 | 10.110 |  | clk_p |
| IOBD_372_468/DIN | td | 0.829 | 10.939 | r | u_gtp/opit_0/O |
|  | net (fanout=1) | 0.000 | 10.939 |  | u_gtp/ntD |
| IOLHR_364_468/DI_TO_CLK | td | 0.091 | 11.030 | r | u_gtp/opit_2/DI_TO_CLK |
|  | net (fanout=3) | 0.247 | 11.277 |  | ddr_ref_clk |
| MRCKB_361_456/CLKOUT_U_P | td | 0.126 | 11.403 | r | u_ddr3_test_h/u_ddrphy_top/u_clkbufm/clkbufm_inst/CLKOUT_P |
|  | net (fanout=2) | 0.367 | 11.770 |  | u_ddr3_test_h/u_ddrphy_top/pll_refclk |
| RCKB_363_456/CLKOUT | td | 0.149 | 11.919 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].u_clkbufr/goprclk/CLKOUT |
|  | net (fanout=1) | 0.383 | 12.302 |  | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/ppll_clkin [0] |
| PPLL_367_307/CLKOUTPHY | td | 0.026 | 12.328 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].ddrphy_ppll/u_ppll/ppll_inst/CLKOUTPHY |
|  | net (fanout=36) | 0.023 | 12.351 |  | u_ddr3_test_h/u_ddrphy_top/phy_ioclk_fb |
| DDRPHY_IOCLK_DIV_368_310/CLKOUT | td | 0.101 | 12.452 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].u_ddrphy_ioclkdiv/ddrphy_ioclk_div_inst/CLKOUT |
|  | net (fanout=35) | 0.188 | 12.640 |  | u_ddr3_test_h/u_ddrphy_top/phy_sysclk_fb |
| IOLHR_364_504/OCLKDIV |  |  |  | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[14].u_outbuft_addr0/opit_1/OCLKDIV |
| clock pessimism |  | 0.439 | 13.079 |  |  |
| clock uncertainty |  | -0.760 | 12.319 |  |  |
| Setup time |  | -0.356 | 11.963 |  |  |

## 路径 4：slack -0.006 ns

- **Slack**：`-0.006`
- **Logic Levels**：`2`
- **High Fanout**：`64`
- **Start Point**：`u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/ddrphy_dqs_rddata_align/this_group_ca_dly/opit_0_inv/CLK`
- **End Point**：`u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[5].u_outbuft_addr0/opit_1/TX_DATA[2]`
- **Exception**：`MultiCycle Path Setup -end 2`
- **Launch Clock**：`ddrphy_sysclk`
- **Capture Clock**：`phy_dq_sysclk_0`
- **Clock Edges**：`rise-rise`
- **Clock Skew**：`-2.544`
- **Launch Clock Delay**：`5.623`
- **Capture Clock Delay**：`2.640`
- **Clock Pessimism Removal**：`0.439`
- **Requirement**：`10.000`
- **Data delay**：`6.346`
- **Logic delay**：`0.373 (5.9%)`
- **Route delay**：`5.973 (94.1%)`

### Data arrival time is 11.969

| Location | Delay Type | Incr | Path | Trans | Logical Resource |
|---|---|---|---|---|---|
| Clock ddrphy_sysclk (rising edge) |  | 0.000 | 0.000 | r |  |
| N3 |  | 0.000 | 0.000 | r | clk_p (port) |
|  | net (fanout=1) | 0.110 | 0.110 |  | clk_p |
| IOBD_372_468/DIN | td | 0.970 | 1.080 | r | u_gtp/opit_0/O |
|  | net (fanout=1) | 0.000 | 1.080 |  | u_gtp/ntD |
| IOLHR_364_468/DI_TO_CLK | td | 0.105 | 1.185 | r | u_gtp/opit_2/DI_TO_CLK |
|  | net (fanout=3) | 0.294 | 1.479 |  | ddr_ref_clk |
| MRCKB_361_456/CLKOUT_U_P | td | 0.148 | 1.627 | r | u_ddr3_test_h/u_ddrphy_top/u_clkbufm/clkbufm_inst/CLKOUT_P |
|  | net (fanout=2) | 0.432 | 2.059 |  | u_ddr3_test_h/u_ddrphy_top/pll_refclk |
| RCKB_363_456/CLKOUT | td | 0.177 | 2.236 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].u_clkbufr/goprclk/CLKOUT |
|  | net (fanout=1) | 0.450 | 2.686 |  | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/ppll_clkin [0] |
| PPLL_367_307/CLKOUTPHY | td | 0.037 | 2.723 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].ddrphy_ppll/u_ppll/ppll_inst/CLKOUTPHY |
|  | net (fanout=36) | 0.045 | 2.768 |  | u_ddr3_test_h/u_ddrphy_top/phy_ioclk_fb |
| DDRPHY_IOCLK_DIV_368_310/CLKOUT | td | 0.123 | 2.891 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].u_ddrphy_ioclkdiv/ddrphy_ioclk_div_inst/CLKOUT |
|  | net (fanout=35) | 0.000 | 2.891 |  | u_ddr3_test_h/u_ddrphy_top/phy_sysclk_fb |
| GPLL_367_769/CLKOUT0 |  | 0.431 | 3.322 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_gpll/u_gpll/gpll_inst/CLKOUT0 |
|  | net (fanout=1) | 0.753 | 4.075 |  | u_ddr3_test_h/u_ddrphy_top/gpll_clkout0 |
| USCM_215_636/CLKOUT | td | 0.168 | 4.243 | r | u_ddr3_test_h/u_ddrphy_top/u_sysclk_bufg/gopclkbufg/CLKOUT |
|  | net (fanout=15617) | 1.380 | 5.623 |  | core_clk |
| CLMS_339_925/CLK |  |  |  | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/ddrphy_dqs_rddata_align/this_group_ca_dly/opit_0_inv/CLK |
| CLMS_339_925/Q2 | tco | 0.203 | 5.826 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[1].ddrphy_data_slice/ddrphy_dqs_rddata_align/this_group_ca_dly/opit_0_inv/Q |
|  | net (fanout=2) | 2.565 | 8.391 |   | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/debug_data [135] |
| CLMA_333_582/Y2 | td | 0.074 | 8.465 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_group[0].ddrphy_data_slice/ddrphy_dqs_rddata_align/all_group_ca_dly_r2/opit_0_inv_L6QQ_perm/L6 |
|  | net (fanout=64) | 1.306 | 9.771 |   | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/all_group_ca_dly |
| CLMA_357_481/Y2 | td | 0.096 | 9.867 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/ddrphy_control_path_adj/adj_addr_47:40_3[1]/gateop_LUT6DL5_perm/L6 |
|  | net (fanout=2) | 2.102 | 11.969 |   | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/adj_addr [41] |
| IOLHR_364_498/TX_DATA[2] |  |  |  | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[5].u_outbuft_addr0/opit_1/TX_DATA[2] |

### Data required time is 11.963

| Location | Delay Type | Incr | Path | Trans | Logical Resource |
|---|---|---|---|---|---|
| Clock phy_dq_sysclk_0 (rising edge) |  | 10.000 | 10.000 | r |  |
| N3 |  | 0.000 | 10.000 | r | clk_p (port) |
|  | net (fanout=1) | 0.110 | 10.110 |  | clk_p |
| IOBD_372_468/DIN | td | 0.829 | 10.939 | r | u_gtp/opit_0/O |
|  | net (fanout=1) | 0.000 | 10.939 |  | u_gtp/ntD |
| IOLHR_364_468/DI_TO_CLK | td | 0.091 | 11.030 | r | u_gtp/opit_2/DI_TO_CLK |
|  | net (fanout=3) | 0.247 | 11.277 |  | ddr_ref_clk |
| MRCKB_361_456/CLKOUT_U_P | td | 0.126 | 11.403 | r | u_ddr3_test_h/u_ddrphy_top/u_clkbufm/clkbufm_inst/CLKOUT_P |
|  | net (fanout=2) | 0.367 | 11.770 |  | u_ddr3_test_h/u_ddrphy_top/pll_refclk |
| RCKB_363_456/CLKOUT | td | 0.149 | 11.919 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].u_clkbufr/goprclk/CLKOUT |
|  | net (fanout=1) | 0.383 | 12.302 |  | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/ppll_clkin [0] |
| PPLL_367_307/CLKOUTPHY | td | 0.026 | 12.328 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].ddrphy_ppll/u_ppll/ppll_inst/CLKOUTPHY |
|  | net (fanout=36) | 0.023 | 12.351 |  | u_ddr3_test_h/u_ddrphy_top/phy_ioclk_fb |
| DDRPHY_IOCLK_DIV_368_310/CLKOUT | td | 0.101 | 12.452 | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_dqs_bank[0].u_ddrphy_ioclkdiv/ddrphy_ioclk_div_inst/CLKOUT |
|  | net (fanout=35) | 0.188 | 12.640 |  | u_ddr3_test_h/u_ddrphy_top/phy_sysclk_fb |
| IOLHR_364_498/OCLKDIV |  |  |  | r | u_ddr3_test_h/u_ddrphy_top/ddrphy_slice_top/i_mem_addr_0[5].u_outbuft_addr0/opit_1/OCLKDIV |
| clock pessimism |  | 0.439 | 13.079 |  |  |
| clock uncertainty |  | -0.760 | 12.319 |  |  |
| Setup time |  | -0.356 | 11.963 |  |  |

## 审阅提示

- 失败路径位于 DDR PHY 时钟/地址输出相关逻辑；各路径路由延时比例请见上表和逐段明细。仅凭报告不能确定根因，需结合器件/IP 推荐约束和布局分析。
- 模式为诊断位流，摄像头现场输入兼容性及实际稳定性仍需验证；此包不包含新的上板结果。
- `paths.csv` 适合筛选比较，`paths.json` 保留全部路径字段及逐段数据；`raw/*.db` 为原样复制的 PDS XML 文本，可用文本编辑器或 XML 工具查看。
- 此远端报告目录包含 10 份路径数据/原始时序报告、本文和校验清单；完整构建身份及执行元数据未包含在交付中。
- `SHA256SUMS.txt` 覆盖本包其他文件。
