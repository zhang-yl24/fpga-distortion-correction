# Implementation-e rowpad640 system regression — Build ID 11037003

This regression includes the implementation-e metadata address selector and
writer/display payload-control changes. It supersedes the earlier combined
system snapshot while preserving its logs. `physical-e-source-binding.json`
confirms that every RTL and constraint overlay source hash exactly matches the
physical-e snapshot. Prepared source identities differ because include paths
are relocated to each work directory.

| RTL | Source SHA-256 |
|---|---|
| Cache | `af1ccb64704011209280b5b9907a7813b2cf1817fb42b8c4c3226a6455b7a0f0` |
| Writer | `6799f5bd169449ee5eb42593d18d37a6f03ba9cbcf6b04db296fbf4c7c890c8e` |
| Display output | `f17d2b71943af40d2619178b8cadc11a75b82f56942537f9d13332837de1b6f5` |
| Lane | `dc664bfc2c9a4511eb3ba794cee0d3e758b1d972929bd21a2b35517be8c5aa48` |

The real complete system regression passed with the final two-entry lane FIFO,
synchronous cache metadata, 8-beat direct fill, two-stripe writer, registered DDR
return bundle, three source slots and final display count pipeline. The source
identity is `02c7aa6f15d1482f36c1b145d57872284f048ba417598e9398e174bf43c3b9b5`.
All overlay hashes stayed unchanged during the test. The matching directory
contains the preparation receipt, report, per-epoch results and XSim 2017.4 logs.

The frozen profile is tile 8×8, upper cache INDEX10 with row16 padding enabled,
lower cache INDEX9 with linear indexing, and NATIVE_TOP_ROWS=640. The optional
vendor CA fanout16 constraint is included in the snapshot, giving Build ID
`11037003`. Functional simulation does not exercise the constraint's physical
implementation.

This test runs WIDTH64×HEIGHT64 with exact 125 MHz core and 148.5 MHz input/output
clock ratios. At this width, row-padding explicitly falls back to linear
indexing; the engine uses its small-frame automatic split of 32/32 rows.
Native 1920×1080 row16 indexing and the 640/440 split are checked by the native
cache unit tests and separate full-frame engine regression. The native engine
reference covers every full-resolution output pixel. This scaled system test
adds capture/display clock crossings, slot ownership and shared DDR contention.

| Check | Epoch 0 | Epoch 1 | Total |
|---|---:|---:|---:|
| Source commits | 18 | 16 | 34 |
| Published results | 17 | 16 | 33 |
| Unique displayed frames | 16 | 16 | 32 |
| Raw / corrected unique frames | 6 / 10 | 6 / 10 | 12 / 20 |
| Repeat displays | 3 | 2 | 5 |
| Displayed pixels checked | 77,824 | 73,728 | 151,552 |
| Source slot commit counts | 7 / 6 / 5 | 6 / 5 / 5 | 13 / 11 / 10 |
| Underflows / mismatches | 0 / 0 | 0 / 0 | 0 / 0 |

Source/result writes and committed DDR contents are also checked per pixel
(139,264 source pixels and 135,168 result pixels in each check category).
Independent RGB565 textures, a scaled C-profile integer mapper and integer
bilinear reference supply pixel and CRC expectations. Frame IDs, source/result
leases and held address/data bundles are checked throughout.

Both epochs have nonzero AR/AW/W backpressure, return gaps, shared read/write
service competition, capture/result write competition, display/sample read
competition, all-three-source-slots-reserved cycles and active mode switches.
Eight whole input frames per epoch receive no reservation under the deliberately
faster scaled input raster. Accepted captures have zero malformed/drop count.

The common reset interrupts an active engine while DDR is busy after a drained
phase. The DDR memory retains its old values; epoch 1 changes the input texture
and restarts frame IDs to expose stale-data recovery defects. The final epoch
drains every accepted frame and checks repeat display behavior. Epoch 0's last
processing frame and one queued result are intentionally interrupted by reset.

Reproduce using `tools/run_system_contention.py --work <new-directory>
--ddr-fanout16`. The report explicitly records `hardware_tested: false`.
Native throughput, routed timing and board stability require their separate
evidence; this test provides scaled functional and ownership coverage.

Read-only integration review found all 34 build design paths and four constraint
paths present, no duplicate plain-Verilog module definitions, no missing overlay
build entries, and no changed snapshot or live overlay hashes. Existing top,
engine, core, sampler and public cache ports are preserved. The deliberate
internal changes are the cache's decoded address inputs and the source-slot
bank/ownership widths across capture, DMA, link, bank and system. Their widths
are connected consistently in the elaborated system. Added modules are the
lane, read-return register and raster writer backend. The review inventory is
`integration-review.json`; it complements the actual system elaboration and
does not claim to parse encrypted vendor IP.

The elaborator reports a 32-to-28-bit output-base expression at engine line 59.
The accepted-frame layout check bounds the complete output range to 28 bits;
both lane start offsets lie inside that range, so truncation drops zero upper
bits for accepted frames. Two mapper forward-declaration warnings come from the
unchanged baseline. These warnings were reviewed without changing the frozen
RTL. The full-resolution and scaled pixel-address checks cover the used layouts.

