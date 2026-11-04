# Sustained bench: finite four-frame cadence scope

**This is a finite observation, not a passed long-run or board 30 FPS claim.**

The source emits 16 complete 1920x1080 frames at 148.5 MHz with a 2200x1125 raster: one SOF every 16.666666666/667 ms, without waiting for DUT readiness. Input runs from 0.000212121 ms through terminal EOF 266.666878787 ms. All 16 have observed first/last pixel events; last is logged when the bench count reaches 2,073,600.

The bench explicitly caps accepted frames at four. On a core negedge it clears capture_admit when input_dma.source_valid and source_id == 4. This is completed-capture/DMA offer state, not the later bank-accept source_commit. The cap edge was not logged: its conservative source-derived bounds are after input-frame-7 EOF at 116.666878787 ms and before ID4 bank acceptance at 133.333516 ms. No exact disable timestamp is invented.

| Accepted ID | Input frame (1-based) | SOF ms | First/last pixel ms | Bank accept / process start ms | Process done / publish ms | Process cycles ms | Unique scan start / done ms |
|---|---:|---:|---|---:|---:|---:|---|
| 1 | 1 | 0.000212121 | 0.608912457 / 16.607020202 | 16.666940000 | 47.708660000 | 31.041712 | 67.884210487 / 99.880425975 |
| 2 | 2 | 16.666878787 | 17.275579124 / 33.273686868 | 66.666844000 | 98.596484000 | 31.929632 | 101.217543820 / 133.213759308 |
| 3 | 5 | 66.666878787 | 67.275579124 / 83.273686868 | 100.000180000 | 131.919140000 | 31.918952 | 134.550877153 / 166.547092642 |
| 4 | 7 | 100.000212121 | 100.608912457 / 116.607020202 | 133.333516000 | 165.263156000 | 31.929632 | 167.884210487 / 199.880425975 |

source_commit is the bank source_valid/source_ready acceptance and processing assertion. The published hardware cycle gauge is one 8 ns core cycle below the endpoint commit-to-publish timestamp difference; both are retained in JSON without conflation.

Observed cadence:

- Bank-accept gaps: 49.999904000, 33.333336000, 33.333336000 ms. The first gap includes startup/display handoff.
- Publish gaps: 50.887824000, 33.322656000, 33.344016000 ms.
- New-frame full-scan completion gaps: 33.333333333, 33.333333334, 33.333333333 ms: exactly three finite 30 Hz intervals.
- After ID4, the same frame is fully scanned again at 233.213759308, 266.547092642 and 299.880425975 ms. These are repeats, not additional new frames.

Why four of sixteen is not a measured 15 FPS bottleneck:

Accepted input frames are 1, 2, 5 and 7. Input 3, 4 and 6 receive no capture grant during earlier occupied/backpressured states. Later input 8 through 16 also include the deliberately capped period; the no_free/no_grant counter increments when the first DE cannot begin capture, including when admission has been disabled. Thus total 4/16 = 25% combines startup, waiting and a deliberate finite stop. It is not steady-state acceptance measured over an uncapped stream.

The source keeps running while IDs1–4 are processed and scanned: all four first unique scans finish before terminal input EOF. Thus the three consecutive new-frame intervals are not fabricated by sending a short input burst and only scanning after all input stopped. However, the test does stop accepting after four and never demonstrates a fifth new frame. Its 266.667 ms whole input window cannot be described as sustained 30 FPS output.

Conclusion: compatible with the 30 FPS goal for this finite modeled pipeline, with a worst observed process gauge of 31.929632 ms; insufficient to prove uncapped long-run throughput or board FPS. The same-bench FIFO baseline serves finite cache/cycle/timing comparison only. Actual short/long board unique-frame rates and visual inspection remain separate.

No RTL, frozen provider, or existing receipt changed. No simulator or full pixel/CRC recheck was run. Only small CSV/summary/header/bench files were read. Exact events and source references are in the companion JSON.
