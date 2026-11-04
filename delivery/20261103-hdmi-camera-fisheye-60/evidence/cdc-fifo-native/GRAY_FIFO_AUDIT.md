# Physical-e Gray FIFO audit

The shared RTL is `compiled/rtl/video_async_fifo.v`, SHA256
`140e97b7de1c3718d75f6bd0c657c9df602d724c5162a26386b053deafa07e36`.
This audit reads the frozen physical-e snapshot; it does not modify that snapshot.

| Instance | Depth/word width | Pointer width | Write clock | Read clock |
|---|---|---:|---|---|
| `system/display_fifo` | 512 × 256 | 10 | ddrphy_sysclk, 8 ns | input_pixel, 6.6667 ns constraint |
| `system/input_link/input_dma/capture/pixels` | 64 × 256 | 7 | input_pixel, 6.6667 ns constraint | ddrphy_sysclk, 8 ns |

For either instance, a source binary pointer increments once on its local
`enable && ready` edge and otherwise holds. Its Gray register receives
`(next_binary >> 1) ^ next_binary`. Thus each active source-clock edge changes
zero or one Gray bits, including modulo wraparound. Gray-to-binary conversion,
full and empty logic use only the second synchronized pointer. Both directions
have separate first/second registers in RTL, with no combinational logic between
them. The first stage feeds its matching second stage in the synthesis netlist.

All FIFO instances share the top-level `pipeline_reset_n`; each domain has a
two-register asynchronously asserted, locally released reset chain. Pointer
and data-valid reset are local synchronous actions while that chain is low.
Ready is low immediately when the local reset chain clears. The single-bit Gray
transition rule applies during operation, not to clearing an arbitrary pointer
on reset. Common reset and disabled admission prevent treating that reset jump
as an active pointer transition. Reset release needs the local clock edges;
one side is never independently reset by a frame/mode/enable change.

Synthesis optimizes Gray MSBs to the identical binary MSBs. Logical source and
first-stage destinations are:

| Instance | Source | First-stage destination | Source-period bound |
|---|---|---|---:|
| display_fifo | `wr_gray[8:0]`, `wr_binary[9]` | `wr_gray_r1[9:0]/D` | 8 ns |
| display_fifo | `rd_gray[8:0]`, `rd_binary[9]` | `rd_gray_w1[9:0]/D` | 6.6667 ns |
| capture/pixels | `wr_gray[5:0]`, `wr_binary[6]` | `wr_gray_r1[6:0]/D` | 6.6667 ns |
| capture/pixels | `rd_gray[5:0]`, `rd_binary[6]` | `rd_gray_w1[6:0]/D` | 8 ns |

The bounds above describe the intended per-bus maximum source-Q to first-stage-D
propagation/skew requirement, with the pixel period taken from the conservative
150 MHz FDC envelope. They are not newly applied constraints. All bits of each
bus, including the optimized MSB alias, must be matched and reported. The
first-to-second-stage paths remain destination-domain synchronous paths.

The synthesis `.vm` contains two banks of `GTP_DFF_R` for each Gray direction.
However, `prj_tasks/syn_1/compile/run.log:389` and following lines explicitly
state that `async_reg` is illegal and ignored. The synthesis CDC report records
four CDC-2 and four CDC-5 rows with `without ASYNC_REG property`.

The mapped/routed `hdmi_camera_fisheye_top_route_optimize.netlist` then contains
34 `gopSRL2` instances for the 20 display and 14 capture Gray chains. Their
names retain the first-stage base, for example
`system/display_fifo/rd_gray_w1[8]/opit_0_inv_srl`. The display reset chain is
also `gopSRL2`. This is a confirmed structural gap: the intended independent
two-flop chains are not preserved through device mapping. Adding timing bounds
alone would not restore the requested structure.

The extracted routed setup report covers 17 input_pixel→ddrphy_sysclk Gray
endpoints, all terminating at `.../opit_0_inv_srl/D`, with data delays
5.918–6.126 ns and setup slacks -4.435 to -4.195 ns under the current clock
relationship. It also includes four local downstream paths starting from an
SRL output. Opposite-direction Gray setup paths are absent from this bounded
report, so it cannot establish all 34 per-bit bounds or a bus-skew signoff.
Some packed physical start names differ from the logical bit: the capture
MSB path starts at a cell named `wr_gray[5]`, while its arrival net is explicitly
`wr_binary[6]`. Use mapped Q/net connectivity, not the packed cell base alone.

`fifo-gray-audit.json` retains synthesis cells, CDC rows, mapped cells and routed
path details. `audit_fifo_gray.py` reproduces the extraction. Remaining work is
native-attribute preservation checked after mapping, complete per-bit bus
binding, and explicit routed maximum-delay/skew evidence; no timing exceptions
were added during this audit.
