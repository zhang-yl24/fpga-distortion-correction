# Three-source scheduling candidate and evidence

Five frozen RTL overlays are under `overlay/`, relative to the native project root. `overlay-manifest.json` binds each original file from `D:/fpga-build/both-final/native` and candidate SHA256. The integration build uses these changes together with the separate cache, writer and reset changes. No board measurements are claimed here.

## Why add a source bank

The real bank core admits a source only when neither processing nor a pending result blocks it. A pending result waits for a display request. Two source banks can consequently remain occupied across the next capture grant even when processing takes less than one input period. The new source bank stores the capture that would otherwise be discarded while a completed source waits for processing/display alignment.

Logical source banks 0, 1, 2 map to physical DDR slots 0, 1, 4. Result slots remain 2 and 3. With the default BANK_STRIDE=1048576 in 4-byte units, this adds a 4 MiB source region at byte offset 16 MiB. Every source-bank metadata path is two bits; reservation/writable masks are three bits. Two completed-source descriptors remain sufficient for one active processor, one queued completed source and one capturing source. Invalid logical source bank 3 is rejected. Existing transaction drain, CRC, source ID and result lease rules remain in place. The old core header mentioning four banks describes the previous layout; the candidate has five physical slots.

## Real bank-core scheduling experiment

`run_scheduler.py` compiles the actual old/new bank core with an explicit engine duration stub and a synthetic capture/display driver. Input period is 3333 simulation cycles; capture begins at offset 121; output lease is 3320. After 40 warmup periods, 240 input periods are counted. Five output phases (0, 700, 1400, 2100, 2800) and three processing durations (2252, 2575, 3000) give 30 cases across both source-bank counts.

`scheduler-results.json` contains the verified rerun. Each simulation prints `STUB_PROCESS` and asserts that the measured bank-core process count equals requested duration + 1. These results supersede an earlier exploratory run whose elaborated stub duration was not adequately checked. Only the current logs with `measured_process` are authoritative.

`scheduler-source-bindings.json` binds the exact compiled bank copies and test stub/bench. The baseline copy has Windows line endings and is asserted text-identical to the original after newline normalization; both byte hashes are recorded. The candidate copy is byte-identical to the frozen core overlay.

| Processing duration / input period | Two-source results over five phases | Three-source results over five phases |
| --- | --- | --- |
| 2252 / 3333 | 3 phases: 240 new; 2 phases: 180 new, 60 repeat, 60 no-bank | All 240 new, zero repeat/no-bank |
| 2575 / 3333 | 3 phases: 240 new; 2 phases: 180 new, 60 repeat, 60 no-bank | All 240 new, zero repeat/no-bank |
| 3000 / 3333 | 1 phase: 240 new; 4 phases: 180 new, 60 repeat, 60 no-bank | All 240 new, zero repeat/no-bank |

These ratios correspond to the previously observed approximate 22.5 vs 30 new-frame scheduling regime when scaled to a 33.33 ms frame period. The stub does not simulate pixels, real DDR arbitration, clock-domain crossings, output underflow, 1080p processing cost or the board. It isolates the scheduling mechanism.

`boundary-results.json` uses the same verified three-source elaboration. Output period 3330 with duration 2252 or 3000 produced 240 unique scans during the window. Output period 3340 with duration 2252 produced 239 unique scans from 240 captures, with zero no-bank loss during this finite window. Long-term frequency mismatch can still cause repeats/drops. Duration 3340 or 3700 with output/input period 3333 produced 120 unique scans, 120 repeats and 120 no-bank drops: added buffering cannot remove a persistent processing-budget overrun.

## Real capture/DMA/shared-write verification

`run_dma_three.py` / `dma-three/2.log` run the actual capture CDC and input DMA with independent RGB565/CRC expectations. All three banks are used (mask 7); logical bank 2 is released and reused; a blocked completed head coexists with a capturing third source, then a completed tail. Head metadata stays stable and tail promotion is atomic. Every source write is restricted to physical slot 0, 1 or 4. Bad line/frame, overflow with already accepted AW/W draining, common reset of a partial frame, invalid release and uncommitted/unowned release rejection are covered. Final pressure counters include AW stalls 538, W stalls 215, commit stalls 1187 and no-free event 1.

`run_link_three.py` / `link-three/2.log` additionally use the real shared DDR write arbiter, with a result-writer traffic proxy. Three 32x16 source frames and 128 result bursts pass exact pixel/CRC and source/result address-isolation checks. Coverage: AW stalls 53, W stalls 484, contention 12, commit stalls 106, same-cycle first source AW/W 6, same-cycle first result AW/W 128, and 2048 result beats. The proxy does not validate the image-processing engine.

## Actual-engine end-to-end integration verification

`system-small/` and the authoritative directed run `system-three-final/` both pass using 34 actual prepared integration RTL files from `D:/fpga-stable/build/stable-a/native`. The engine, new cache read stage, registered writer, reset changes, input CDC/DMA, shared read/write arbiters, reader, output async FIFO and registered DE/RGB scanner are present. The bench models only the external DDR UI; no image engine stub is used. `compile-sources.json` binds each RTL file and the adapted bench; `verification.json` confirms source/bench hashes before and after all three completed tool stages and hashes every fixture, CSV and relevant log.

Both runs use eight continuous 32x16 frames, synthetic nonzero radial/tangential parameters, identity rotation and Gamma disabled. The CPU goldens use the repository's unchanged pure-numpy bilinear oracle and integer Brown functions, with every coordinate checked against its separate scalar oracle. Actual DDR source/result words, geometry masks, registered output RGB values and full-frame CRCs are checked independently. Both runs also pass mid-scan fault isolation, a fault at the bank-release consumption edge, and coordinated-reset recovery.

The directed run delays only the initial scan admission until the third input frame begins. It then scans all eight frames. Source bank sequence is **0, 1, 0, 2, 1, 0, 2, 1**; the source texture sequence is **0, 1, 2, 1, 2, 0, 2, 0**. Thus logical bank 2 / physical slot 4 is written, sampled, released and reused with different source data and a different independently expected output CRC. The final CSVs contain eight input/commit/process/unique-scan records, 4096 uniquely scanned pixels, 256 source beats and 256 result beats. Drop, overflow, no-free, underflow and CRC-mismatch counters are zero. AW stalls=1003, W stalls=101 and AR stalls=58 exercise backpressure. Three initial blank rasters are expected from the deliberate delayed admission. The final source2 CRC changes from `5df24653` to `a02e1578`; corresponding output CRC changes from `4f224d3f` to `0294210b`.

`system-three/` is an exploratory predecessor and is excluded from the frozen evidence. The completed evidence is copied once to `evidence-frozen/`; its `evidence-manifest.json` lists every file's size and SHA256. Successful verification files and that directory are not overwritten by further runs. Simulation helpers retain explicit local source/tool paths; reproducing on another computer requires updating those paths to the matching native project and installed XSim.

## Integration and board acceptance

The scheduling, DMA/link and small actual-system checks are complete. The digital evidence establishes the exercised data/ownership behavior. Native 1080p frame rate, final STA, physical DDR reset behavior and camera correction quality require their corresponding integration and board evidence.

On hardware, use pure correction mode and record input timing, verified full-scan unique frame IDs, repeats, no-free/drop/overflow counts and measured processing cycles. `captured_frames` currently increments when the processor accepts a completed source, so it must not be interpreted as an input SOF counter. `last_process_cycles` excludes descriptor waiting time. A stable approximately 29.97 unique scans/s requires the processing and display paths to satisfy their real budgets after timing convergence.
