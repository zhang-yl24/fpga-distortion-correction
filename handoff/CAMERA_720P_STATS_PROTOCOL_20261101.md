# Experimental core-domain FPS telemetry, 2026-11-01

This is an offline-tested module for a future isolated candidate. It is not part
of the frozen 720p correction bitstream and has not measured camera FPS on a board.
It does not change video admission, memory ownership, processing or scan control.

## Counter scope and domains

| Packet value | Existing source | Meaning / decision |
|---|---|---|
| `SourceAccepted` | `rtl/experimental/camera_vga_input_dma.v:105` | `sys_clk` count incremented by complete `source_valid && source_ready`; routed to core top as `captured_frames`. Not all sensor frames. |
| `Processed` | `rtl/experimental/lens1080_bank_core.v:78` | Core count of completed processing transactions at source release. |
| `UniquePresented` | `rtl/experimental/camera_vga_video_system.v:235` | Core count after complete scan metadata/CRC/pixel count and FIFO drain, with a new frame ID. Not HDMI refresh rate or repeated scans. |
| `CoreTicks` | New statistics module | 64-bit core clock edge count from local reset; nominal 125 MHz is crystal/PLL-derived, not an independent time standard. |
| `Underflows` | `camera_vga_video_system.v:153,164` and `ddr_video_output_1080_board.v` | Existing value is **pixel clock domain**. Version 1 leaves this field unavailable, with bytes fixed to zero; zero is not a measured count. |
| `Failed` / `Fault` | Optional future core-synchronous inputs | Existing top `system_fault` can select held `board_fault` from the reference domain (`camera720_calibrated_top.v:163`). The initial isolated integration ties `status_valid=0`, `failed=0`, `fault=0`. No new CDC is introduced. |

All three counter buses must share the statistics module's `clk` and reset epoch.
The current top's similarly named aggregate status wires must not automatically
be treated as coherent core-domain inputs. A future valid fault source can expose
the system's internal core-registered sticky status under a separately reviewed
interface; that is outside this change.

## Module and wire format

`rtl/experimental/camera720_core_stats_uart.v` exposes only one output, `tx`.
Inputs are `clk`, `rst_n`, three 32-bit counters, and optional synchronous
`status_valid`, `failed`, and 8-bit `fault`. Parameters default to core 125 MHz,
UART 115200 baud, and one sample per 125000000 core clocks. It reuses the existing
`rtl/uart_tx.v` in 8N1 mode. No RX, command, trigger or video backpressure exists.

Every packet is exactly 64 bytes, little-endian:

| Offset | Bytes | Field |
|---:|---:|---|
| 0 | 8 | ASCII `PGFPS01` followed by LF |
| 8 | 1 | Version = 1 |
| 9 | 1 | Bit 0 = failed; bit 1 = fault status valid; other bits zero |
| 10 | 2 | Packet length = 64 |
| 12 | 4 | Scheduled sample sequence, modulo 2^32 |
| 16 | 8 | Core ticks at the snapshot edge |
| 24 | 4 | Source accepted count |
| 28 | 4 | Processed count |
| 32 | 4 | Unique presented count |
| 36 | 4 | Reserved, zero; underflows unavailable |
| 40 | 1 | Fault code, zero when status is unavailable |
| 41 | 3 | Reserved, zero |
| 44 | 8 | Build label |
| 52 | 8 | Profile label |
| 60 | 4 | IEEE CRC32 over bytes 0..59; reflected polynomial EDB88320, initial/final XOR FFFFFFFF |

The first 60 bytes are latched together. Counts describe their values just before
the sampling edge, and ticks count that edge; consecutive differences retain a
consistent convention. CRC and UART transmission use this held snapshot while
live counters continue changing. At nominal settings the packet occupies about
5.56 ms of wire time per second. This is instrumentation traffic, not video FPS.

If transmission is still active on a sample edge, that sample is skipped. Sequence
still advances, making the telemetry gap visible; the video pipeline is unaffected.
A zero build/profile label means unidentified. Nonzero 64-bit labels also require
an external manifest mapping to full source/profile/bitstream SHA256 identities;
they are not cryptographic bitstream verification and must avoid a self-hash cycle.

## Host interpretation and limitations

`tools/camera720_stats.py` reads a binary file or accepts incremental byte chunks.
It never opens a serial port. Length, version, reserved fields and CRC are checked
before emitting a record. Noise/corrupt frames are skipped; partial frames never
produce counts. A partial tail and rejected packets are explicitly reported.

For adjacent compatible records, seconds = delta(core ticks) / nominal core Hz;
FPS is the corresponding counter delta divided by those seconds. Unsigned 32-bit
counter and sequence wrap is supported. Counter deltas assume fewer than 2^32
events between samples, with at most one frame event per core edge; implausible
regressions are rejected. Sequence gaps represent missing telemetry, not dropped
camera frames. Fault status remains unknown when `status_valid=0`.

Observed tick/sequence regression, duplicate/out-of-order sequence or changed
build/profile suppresses interval rates. **This cannot identify every reset.**
After an unobserved reset and enough missing early packets, all values can again
exceed the previous sample. Every rate therefore carries
`AssumesContinuousResetEpoch=true` and `ResetEpochContinuityProven=false`.
Board/reset control history and full identity bindings belong to the later actual
measurement session. Do not label file parsing alone as an authenticated board
measurement, independent frequency measurement, sensor FPS or HDMI refresh FPS.

## Offline verification

`tests/test_camera720_stats.py` tests byte corruption, every truncation/chunk split,
resynchronization, invalid/reserved fields, optional fault status, counter/sequence
wrap, tick low-word wrap, epoch/identity changes, hidden-reset ambiguity and finite
numeric rates. It does not open hardware.

`tests/tb_camera720_core_stats_uart.sv` drives changing synthetic counters while
the **real** `uart_tx` sends bytes. An independent observer samples only the TX
wire at 8N1 bit centers and the host checks packets against independently recorded
scheduled input values. It exercises normal cadence, an oversubscribed UART,
counter wrap, tick low-word wrap and a reset in the middle of a packet. The tick
seed near 2^32 and accelerated clock/cadence are testbench-only, explicitly recorded.

Run the bounded digital simulation with:

```powershell
.venv/Scripts/python.exe -B -X utf8 distortion/tools/run_camera720_stats_sim.py --work-dir distortion/work/camera720-core-stats/<fresh-name> --maximum-seconds 180
```

This invokes only xvlog/xelab/xsim. It does not run PDS, modify existing candidate
RTL, or access UART/JTAG. An isolated top, native timing/pins/CDC checks, bitstream,
and actual measurement session remain separate work.
