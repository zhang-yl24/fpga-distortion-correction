# Independent direct RGB display experiment

This candidate tests the received RGB888 bundle on the real display without
DDR, a frame store, a mapper, UART or raw snapshots. Existing raw v2 and the
independent DDR pixel candidate are retained. Its input clock is forwarded
continuously to the HDMI transmitter; all 27 RGB/HS/VS/DE bits pass through the
same existing PCLK sampler. HS and VS retain their sampled electrical levels.
DE remains low until the selected positive VS/DE timing configuration, local
reset release, valid sampler bundle and two-FF synchronized readiness hold.
Readiness faults remain sticky until coordinated common reset.

The builder selects the observed digital profile using a frozen top copy with
INPUT_TIMING_CONFIGURED=1. Canonical top default0 stays blank. The 150 MHz STA
envelope is conservative for the observed approximately148.501 MHz PCLK. No
independent output PLL or synthetic 30 Hz raster changes the source cadence.

## Primary-source basis

The supplied MS7210 datasheet, page6 table1, lists RGB44424-bit SDR with separate
H/V at148.5 MHz for1080P. Its feature table lists a maximum300 MHz sampling clock.
The supplied official HDMI_IN_DDR3_HDMI_OUT example uses a148.5 MHz output PLL
(`source/rtl/HDMI_IN_DDR3_HDMI_OUT_top.v:90`) and registers RGB/HS/VS/DE on that
clock (`:215`). Its49 TX register commands equal the current checked controller
in address, value and order, including1281=04. This supports trying the same
TX initialization table without inventing new register writes.

Bound references (SHA256):

- `vendor/board/盘古100Pro+开发板（MES2L676-100HP）配套资料/4_IC_datasheet/HDMI PHY/《MS7210 Datasheet-CN》-sp(1).pdf`:
  `2e9ea30aaf970a5b53a6f9d71185959a8145df45f1ef0d516b77e13f6c5d25f3`
- Existing text extraction `hardware_check/ms7210.txt`:
  `6550e729e11558e12d23e8e516cecd390ef504077287e7add61efba9016298a7`
- Official example `vendor/reference/video/4_12_HDMI_IN_DDR3_HDMI_OUT/4_12_HDMI_IN_DDR3_HDMI_OUT/5_12_HDMI_IN_DDR3_HDMI_OUT/source/hdmi/ms7210_ctl.v`:
  `c9b101e58f381ddf3c6d663d0003c18065302659424b8345022161413ccf09ae`
- The same example's `source/rtl/HDMI_IN_DDR3_HDMI_OUT_top.v`:
  `ca0d180208c8eca76f24b53aced44fe03d7bc9d8a28f39d622e220694dfb56a6`
- Retained checked TX `distortion/rtl/experimental/ms7210_checked_ctl.v`:
  `53d2dd9e4675126da979c87c76481e2f7705ddcad9abd784156eb76b27e79f6a`

## Limits and release evidence

The register map does not identify every TX edge/AVI setting. The same table
does not guarantee that the new source is RGB, progressive, correctly packed,
or sampled at a safe phase. RX and TX same-numbered registers are different
devices. Input phase, forwarded-clock versus data phase, board skew and external
AC remain unaccepted; no undocumented register is changed to guess them.
An actual display observation is the purpose of this reversible diagnostic.

The new target requires its own native pin/electrical, all-27-bit sampler,
reset/CDC, clock-forwarding, full two-corner internal timing and bitstream
source binding. Both data and forwarded-clock native min/max paths must retain
their actual edge and common reference. Existing raw or DDR proofs are not
transferred. Current safety/physical checks remain separate; unknown external
AC is recorded rather than represented as a completed interface guarantee.
