# c3: separate normal readback from legacy collision injection

## Preserved failure / root cause

c2 ZIP SHA256 fccb52f9faa18fa5a608681f255edd2e1fe6e89ccd9f98500b7739ba73b70303
is unchanged. Parent/cloud worker reports original and observation-only rerun
fail at the same time. Compile exit0, vvp exit1. At first ROI pixel
2210109477ps, x10/y3, accepted grant epoch2/id1, CONFIG_OK1:

- frame_active1, FIFO empty1, queued/inflight/requested/received all0;
- scanner fault_now02 (underflow), parent fault/abort0;
- display AR valid1/ready0, address0200000, owner0;
- forced_display_ar_hold_cycles reached413 while waiting for a later sample AR.

This is a REAL scan underflow correctly rejected by the existing assertion, not
a parser/false-positive/timeout error. c2 introduced a real UART command preamble
while the video raster continued running. That changed the source/raster phase.
The old SMALL forced-contention fixture could withhold the first display request
until the next source-frame commit; this is not a legal normal scan-prefetch
assumption at every launch phase. Static timing predicts the ROI within2ps of
reported failure and about12.4us before second-source EOF.

## Exact minimal changes

1. Name the current test phase as normal readback, with localparam
   LEGACY_COLLISION_INJECTION=0. Gate BOTH old forced display-AR and result-AW
   future-client waits behind it. Their code is retained, not reinterpreted as
   valid stress or silently treated as passed.
2. Scope positive forced-collision and dual-client coverage predicates to that
   injection mode. Normal mode instead ASSERTS all forced holds/events remain0.
   Natural read/write contention is reported as observed, including zero.
   This is a declared reduction of collision-coverage scope, NOT a claim that
   the old forced-contention regression passed under new UART phase timing.
3. Python result explicitly marks collision injection NOT_RUN_IN_NORMAL_READBACK_PHASE,
   checks the zero-injection counters, and records natural contention counts.

## Checks and inputs preserved

- All36 design/header files and all15 original synthetic fixture files unchanged.
- No RTL, grant/FIFO/data path, reset, DUT timing constant or clock modification.
- UART preamble, serializer/RX/TX,40ms drain and60ms total simulated cap unchanged.
- Original240000-cycle video budget and90s/300s host budgets unchanged.
- Periodic AR ready gating (mod7), AW gating(mod9), W gating(mod6), same-AW first
  beat and delayed first beat coverage remain. FIFO and real arbitration remain.
- Bad scan completion / underflow / parent failure assertions remain verbatim.
- All3072 pixel, raw/corrected output, CRC, layer, epoch/cache, bank ownership,
  capture overlap, exact cadence, completion/drain/drop assertions remain.
- Independent expected-vector metadata, RGB888 CRC/sample and UART packet oracle
  remains; raw frame1 and corrected frame2 wire signatures still mandatory.
- No new test PASS until real compile/sim and wire oracle complete.

c3 is PREPARED, NOT_COMPILED/NOT_RUN locally. The old collision-injection result
remains a separate preserved failure; a future phase-independent stress test must
define feasible deadlines and prove actual dual-client overlap separately. No
hardware/CDC timing/MTBF/DDR PHY acceptance is inferred from this normal regression.
