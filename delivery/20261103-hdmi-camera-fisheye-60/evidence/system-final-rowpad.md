# Earlier rowpad-profile system regression

`system-final-rowpad/` contains passing receipts and XSim 2017.4 logs for the
then-current combined cache, writer, output consumer, read-return register, three-slot
capture DMA and real dual-lane engine. No engine stub or internal force is used.
The runner verifies that every overlay still matches the prepared source hash
after simulation; `changed_overlays_after_snapshot` is empty.

This snapshot predates the two-entry lane FIFO and final output count pipeline.
The final rowpad640/Build ID 11037003 combination is recorded separately in
`system-final-rowpad640-fanout16.md` and its matching evidence directory.

The prepared configuration is tile8×8, upper lane INDEX10 with row padding
enabled, and lower lane INDEX9 with the linear mapping. This system test uses
WIDTH64×HEIGHT64, so the upper cache follows its documented linear fallback.
The native WIDTH1920 padded path is covered by `cache-rowpad.md` and the separate
full-frame engine tests. Core/input/output clocks are 125/148.5/148.5 MHz.

The two epochs check 34 source commits, 33 published results, 32 unique displayed
frames (12 raw, 20 corrected), five repeated displays and 151,552 displayed
pixels. Every pixel is checked against an independent scaled C-profile integer
reference; source, result and display CRCs must match. All three source slots
cycle at least five times per epoch. Shared read/write service, capture/result
write arbitration, display/sample read arbitration, address/data backpressure
and mode changes during active work all have nonzero coverage.

A common reset interrupts real processing while DDR is busy. Memory persists
across reset, while input texture changes and frame IDs restart; the second
epoch checks recovery and drains all accepted frames. Both epochs finish with
zero underflow and checksum mismatch. Eight whole input frames per epoch have
no reservation, intentionally exercising source exhaustion under the scaled
80×72 input and 96×96 output rasters.

These are functional/ownership results under a deterministic shared-service DDR
model. Native 1080p60 bandwidth, FPGA routed timing and physical board stability
have separate acceptance criteria.

Reproduce with `tools/run_system_contention.py --work <new-directory>`.
`--cache-index-bits 7` or `9` requests uniform linear caches; without an override
the runner uses the prepared rowpad profile.
