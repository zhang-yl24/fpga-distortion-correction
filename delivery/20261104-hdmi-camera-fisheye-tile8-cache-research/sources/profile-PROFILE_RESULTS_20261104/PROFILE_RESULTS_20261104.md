# INDEX8 full-system profiling, 2026-11-04

This is a new complete 1920x1080 XSim run, not a hardware FPS measurement. It preserves the original 16 continuous input rasters, four complete accepted corrected frames, all 8,294,400 independent output pixels, CRCs, ownership, and final drain assertions. All 21 production prepared sources and three headers retain the frozen baseline bytes. The DDR model retains its 40-cycle first-beat delay and periodic beat gaps. No PDS, P: or COM access occurred.

Run: 08:44:01 preparation / 08:44:12 native start / 09:42:24 completion, within the unchanged 3600-second tool bound. The run and independent saved-CSV analysis both passed, with no source or input drift.

| ID | Accepted input index | Engine ms | Offer wait ms | Pending wait ms | First display grant ms |
|---|---:|---:|---:|---:|---:|
| 1 | 0 | 37.981864 | 0.000000 | 12.018024 | 66.666852 |
| 2 | 1 | 39.591704 | 33.333240 | 27.074952 | 133.333524 |
| 3 | 4 | 39.606824 | 49.999912 | 27.059824 | 200.000188 |
| 4 | 8 | 39.605128 | 49.999904 | 27.061520 | 266.666852 |

The steady source acceptance and first-display-grant interval is 66.66667 ms. Source 2 is already offered at 33.333604 ms while engine 1 runs; it cannot be accepted until 66.666844 ms. Subsequent engines take about 39.6 ms and then wait about 27.06 ms for a display boundary. This reproduces the 15-new-frame scheduling step in the actual system model. It does not establish a new board frame rate.

Each frame has 37,483 real cache fills, 299,864 real RAM commit beats, and 37,483 valid publications. The physical AR-to-first-R histogram contains only 41 or 42 cycles (mean about 41.20); exclusive wait before the first R costs about 12.056 ms per frame. Missing cycles between subsequent R beats cost about 0.480 ms. The steady cache AR arbitration/backpressure bucket is about 260,000 cycles, or 2.08 ms. These buckets and FSM occupancies describe overlapping system observations and cannot simply be added as achievable optimization gains.

The first frame has no read-client contention; subsequent frames record 666, 691, and 758 cycles with both read clients requesting. Raw `cache_later_r_wait` includes one accepted-AR edge per fill. The independent analysis subtracts that contribution and verifies the result against the complete beat-gap histogram.

Interpretation boundaries:

- Timeline `input_source_index` is the input raster currently arriving at an event. The source identity is joined from original `frames.csv`, giving actual input indices 0, 1, 4, 8.
- `pending_fall` is sampled after NBA; its raw bank column is the next write bank. Consumed result-bank identity is checked using the matching frame display grant.
- `capture_grant_not_ready` measures CDC grant receiver backpressure, not a no-free-frame count.
- Engine start/done deltas exactly match original hardware-process-cycle counters. The inclusive processing-state observer contains one extra edge.

Artifacts:

- `native-a/profiling.json`: SHA256 `724b3df185cb7f6089677e55f3fa326401ee0bbc9e09d23dba42dd50b7845ebb`, 85616 bytes.
- `analysis-a.json`: SHA256 `50952630d7c251bb7175de60bcd5954cff17513dc63081a5bac8e413836150da`, 17233 bytes.
- `native-a/profile-timeline.csv`: SHA256 `de61e7e36cd9801112549b4ad9cfbb333c7c0877f44f30a16419bb18a58d9c27`, 4833 bytes.
- `native-a/profile-cycles.csv`: SHA256 `83c755ad8ad221b559dedac3649a03ba53a21d9cf69bfed747b09ad08eda031c`, 355 bytes.
- `native-a/profile-cache-fsm.csv`: SHA256 `ca5d4fe9bcf939e3eb7db1eb10adf51ba52f02e9c9e6b179d77dbb38e3e00950`, 482 bytes.
- `native-a/profile-ddr-histograms.csv`: SHA256 `603099d18aa984a1e4cc4c207aeab4a600e25c58481a621be632655969565a40`, 1027 bytes.
