# Clock, parameter and constraint contract

This is a source/configuration contract, not measured clocks or routed timing. Every published constraint is preserved byte-for-byte; no false paths or broad asynchronous groups were added.

## Core clock trace

1. TOP `board1080_top` takes differential `clk_p/clk_n`. `u_gtp`, a `GTP_INBUFGDS`, produces the net `ddr_ref_clk`.
2. `u_ddr3_test_h` receives `.ref_clk(ddr_ref_clk)` and exports `.core_clk(core_clk)`.
3. That `core_clk` drives the processing system through `.core_clk(core_clk)`, the KEY1 debounce through `.clk(core_clk)`, and the pipeline/core reset synchronizers. `STATS_CORE_HZ(125000000)` is the selected interpretation, not a clock source.
4. The diagnostic FDC defines `ref_clk` on `clk_p`, period 8.0 ns. `ddrphy_sysclk` is generated from this reference at `u_ddr3_test_h.u_ddrphy_top.ddrphy_gpll/clkout0`, multiply 16 / divide 16, also 8.0 ns. This is the intended vendor UI/core clock model. `DDR3_PARAMETERS.csv` agrees: `CLKIN_FREQ=125.000`, `DFI_CLK_PERIOD=8000` ps.
5. Because the actual vendor RTL is absent, final physical net connectivity from that named generated clock through vendor `core_clk` output and coverage of all user registers must be checked in the new PDS reports. A TOP net name and a stats constant do not independently prove its hardware frequency.

## Other named clocks

- `board27`: `clk_27m`, period 37.037037 ns, nominal 27 MHz.
- `cfg_clk`: generated at `configuration_pll/clkout0`, board27 ×10/27 = 10 MHz. Saved primitive arithmetic: 27×2×21.25/114.75 = 10 MHz.
- `pixel_clk`: generated at `video_pll/clkout0`, board27 ×11/2 = 148.5 MHz. The TOP net is `pix_clk`, which is connected to the system's `pix_out_clk`. Saved PLL arithmetic: 27×2×19.25/7 = 148.5 MHz. A stale TOP comment claiming 74.25 MHz is not the contract.
- `input_pixel`: input `pixclk_in`, constrained to 6.657789 ns, approximately 150.2 MHz. This is a timing envelope, not a measurement of the HDMI camera. TOP activity-admission window values remain 147000 to 150000.
- HDMI raster: HT=2200, VT=1125, active 1920×1080. At the intended output pixel rate this is 60 Hz. One line is about 14.814815 microseconds and one output frame is about 16.666667 ms.
- Late-select grace: 8192 core cycles /125 MHz =65.536 microseconds, about 4.42368 output line periods. This is an upper bounded wait window, not an always-added delay, a promise of a saved frame, or a whole-camera latency measurement.
- KEY1 debounce: 2,500,000 cycles /125 MHz =20 ms. Original release/press synchronization and reset behavior are unchanged.

## Preserved DDR relations and coverage obligations

The diagnostic FDC defines `rst_clk`, `ddrphy_sysclk`, `phy_dq_clk_0/1` and `phy_dq_sysclk_0/1` at the original vendor hierarchy. The two fast PHY clocks derive from ref_clk ×16/2; the divided PHY clocks use edges {5 13 21}. Preserve the two multicycle=2 paths from `ddrphy_sysclk` to `phy_dq_sysclk_0/1` and all four 0.4 ns setup/hold uncertainties in both directions.

`ddr-ip-clock-relations.fdc` adds only the three original vendor-owned asynchronous groups, named `rst_clk`, `phy_dq_clk_0`, `phy_dq_clk_1`. Each has the single original clock group; it is asynchronous to other clocks under PDS semantics. It does not add groups for `ddrphy_sysclk` or either divided PHY clock. Do not replace these with one broad “all DDR versus user clocks” exception. Final-route leaf-clock ownership must be audited again.

The original 20 directed cross-clock min/max path bounds among board27, cfg_clk, input_pixel, pixel_clk and ddrphy_sysclk remain unchanged. They are diagnostic budgets, not CDC/skew/hold or external HDMI AC signoff. The diagnostic FDC expressly lacks accepted external I/O delay constraints and trace-skew evidence. Do not treat a clean covered-path STA result as complete board timing acceptance.

## Fixed logical settings

TOP is `board1080_top`; device Logos2 PG2L100H / -6 / FBG676; no compile-time TOP overrides. Selected source expressions retain fixed Brown (`RATIONAL_BROWN_PROFILE=1`), Gamma OFF (`R34_ENABLE_GAMMA=0`), no runtime rotation, identity cosine=1073741824 and sine=0, cache profile6/AA, HEAD=0, INDEX_BITS=7, QUERY_DEPTH=4096, GROUP_WIDTH=64, MACRO_TILE_HEIGHT=32, RESULT_BANKS=2, CORE_PRIORITY=1, STATS_ENABLE=1, STARTUP_SCAN_ALIGN=1, STARTUP_SCAN_GUARD_CYCLES=0 and STARTUP_PRIME_NEXT_SOURCE=1. KEY1 requests RAW=0/CORR=1. The added TOP grace=8192 is explicitly forwarded; system standalone default remains0.

The 145-port PCF remains identical, including UART RX=B24, TX=C24 and KEY1=C23. Map retains the two-net vendor DDR priority RCF. Physical stages retain the four original priorities: both ddrphy_ioclk_gate nets, all_group_ca_dly and debug_data[273]. Place seed2/decongestion1 and the original route hold-repair settings are unchanged.
