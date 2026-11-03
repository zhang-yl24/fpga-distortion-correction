# G residual writer and pixel paths: H fallback options

Read-only assessment against frozen H sources. No delivery RTL has been changed.

## Actual G paths

Source: `D:/f60-work/mapper/physical-g-subsystem-paths.json`.

| Path | Slack | Data delay | Logic | Route | Dominant detail |
| --- | ---: | ---: | ---: | ---: | --- |
| lane 1 raster writer beat[2] to send_data[147] | -1.593 ns | 9.107 ns | 0.493 ns | 8.614 ns | Beat fanout 1029 costs 4.755 ns; next mux-to-mux net costs 3.417 ns |
| output y to RGB reset input | -0.546 ns | 6.830 ns | 1.379 ns | 5.451 ns | y range, picture, consume, healthy RGB gating; six logic levels |

The writer path is a large asynchronous word-selection route. A register added after `send_data` leaves this failing source-to-register path intact. An effective extra stage would have to partition the selection mux and prefetch ahead of committed writes.

## Writer option order

1. Try the targeted native register fanout attribute when H confirms the same residual problem. This has the smallest functional change: `reg [3:0] beat /* synthesis syn_maxfan = 32 */;`. The official local ADS synthesis guide UG990102 section 8.2.14 explicitly supports registers and describes driver duplication. This ordinary data selector is distinct from the excluded clock/asynchronous reset objects.
2. A registered one-hot next-word selector is a fallback if routed timing still needs a structural change. The first word remains prefetched before AW. Initialize next selection to word 1 for the selected bank before AW is visible; advance only on accepted nonlast W beats. Backpressure holds both selection and published data. Keep binary beat for protocol checks. This preserves 16 consecutive W transfers and current cycle counts. A 16-bit within-bank selector adds 16 FF per lane, but a bit may still feed both banks (up to 512 mask inputs). A 32-bit physical-word selector includes bank ownership and has nominal 256-bit data fanout per selected word. Native synthesis can refactor either expression, so final fanout and LUT cost require inspection.
3. Split-mux data pipelining is a larger alternative. A four-group partial selection stage would add roughly 4 x 256 = 1024 data FF per lane before the final mux, plus selection/valid control; eight groups double that stage storage. It also needs read-ahead tracking that stays aligned through arbitrary W stalls. Since this DDR interface has no separate client WVALID, a committed burst must have each next word available whenever WREADY arrives. It cannot insert per-beat bubbles. Added launch latency could be hidden before AW; one unavoidable extra cycle for each of the 8100 frame bursts would total 64.8 us at 125 MHz before overlap. This is a budgeting bound, not a measured throughput loss.
4. A DRM storage rewrite changes write granularity, synchronous read scheduling and resource allocation. G already uses 147.5/155 DRM equivalents. The 16-bit pixel write / 256-bit burst read width relationship needs a native packing study. No memory rewrite is justified from this selector path alone.

## Completed attribute probe

Location: `D:/f60-work/video/writer-beat-fanout-probe-r2/`.

The complete lane-1 raster writer uses actual 1920 x 440 dimensions. An identical wrapper exposes every WDATA bit through a dynamic 32-bit slice and all statistics through a dynamic status mux to fit the 300 available package IOs. Both baseline and attribute variants completed compile, ADS synthesis and device map. The first direct-top attempt exceeded IO capacity and is retained separately; it is excluded from passing probe results.

| Item | Baseline | syn_maxfan 32 |
| --- | ---: | ---: |
| Beat bit 0 registers | 1 | 9 |
| Beat bit 1 registers | 1 | 9 |
| Beat bit 2 registers | 1 | 33 |
| Beat bit 3 registers | 1 | 65 |
| Synthesis fanout, bits 0/1/2/3 | 260/260/1027/2051 | 32/32/32/32 maximum |
| Largest beat net in mapped high-fanout report | 2052 | 32 |
| FF | 9387 | 9499 |
| LUT | 3206 | 3204 |
| DRM | 0 | 0 |

`verification.json` binds source and report hashes. Removing comments yields identical RTL tokens. Within each bit family every synthesized clone has the same D, CE, CLK, R, INIT and GRS setting, establishing local register equivalence by induction. Total output loads per bit are conserved. The mapped report is a bounded high-fanout list: it reports 58 beat nets at 32; complete synthesis net parsing checks all 116 beat registers. This establishes implemented duplication, with no routed timing or whole-device formal equivalence claim.

The unrelated `send_bank` net remains at mapped fanout 2309. The beat synchronous reset/control driver gains fanout 116. These are residual routing considerations for the full candidate. The proposed attribute adds no latency; isolated resource changes need confirmation after whole-system synthesis.

## Pixel position predecode

If H retains the picture/consume path to RGB, precompute only position; keep every current-frame ownership, queued count, failed and same-edge fault predicate live.

A full one-bit `picture_position_q` can be maintained alongside x/y with `picture_position_q(next) = rectangle(next_x, next_y)`, using exactly the counter's wrap conditions and width-safe intermediate coordinates. Reset it to zero. For every legal configuration the pixel at (0,0) is outside the picture because WX > 0 or WY > 0. Induction then gives `picture_position_q == picture(x,y)` after every released clock edge, including horizontal wrap, vertical wrap, WX=0 and WY=0 cases. Use that aligned bit in place of the current `picture` predicate. The existing word-end position bit can remain as implemented.

This adds one FF and local next-position logic, with zero changes to pixel timing, HS/VS/DE, CRC order, request/grant boundaries or done timing. The estimate assumes synthesis shares existing next-counter expressions; actual LUT change requires native measurement. Predecode must run through blanking and fault states and cannot depend on grant, enable or queue state. Fault priority and immediate abort/unsolicited-return veto remain unchanged.

An even narrower alternative is a single registered vertical-span bit. Initialize it to WY==0; update it only at line wrap to the next y range, and retain the original horizontal x comparison. This directly cuts the recorded y comparator chain, while leaving x decoding in the consume path. Full picture predecode removes both position comparisons before RGB gating. H's actual startpoint should choose between them.

Required validation before applying either pixel option: per-edge equality to the original combinational picture condition, 2 full 1080 frames and existing 38 fault/ownership scenarios, plus legal zero-start/last-line/maximum-counter configurations. Existing same-edge fault and held-result assertions continue to apply. H's current source remains frozen pending its actual timing report.
