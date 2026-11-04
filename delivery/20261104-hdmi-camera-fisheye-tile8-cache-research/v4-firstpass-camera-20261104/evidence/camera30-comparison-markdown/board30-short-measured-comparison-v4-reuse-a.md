# Actual V4 30-second board measurement

Requested counter criteria: **MET**.
Only this 30-second acquisition is assessed. No 600-second stability or visual confirmation is claimed.

Samples: 30; nominal counter window: 29.000000 s; host window: 28.999370 s.

| Counter | Nominal /s | Host /s | Old nominal /s |
|---|---:|---:|---:|
| Source | 60.000000 | 60.001304 | 60.000000 |
| Captured | 30.000000 | 30.000652 | 15.000000 |
| Processed | 30.000000 | 30.000652 | 15.000000 |
| Unique new frames | 30.000000 | 30.000652 | 15.000000 |
| Scan refreshes | 30.000000 | 30.000652 | 30.000000 |
| Good scans | 30.000000 | 30.000652 | 30.000000 |
| Repeated scans | 0.000000 | 0.000000 | 15.000000 |
| Blank scans | 0.000000 | 0.000000 | 0.000000 |

Last-process snapshots, ms: min 29.793016; median 29.845248; p95 29.889032; max 29.889032.
One last_process_cycles snapshot per telemetry sample; not every processed frame.
Continuous telemetry: True; no observed errors: True.
Capture/source ratio: 0.5; unique/scan ratio: 1.0; repeat/scan ratio: 0.0.

Nominal capture/process/unique/scan must be 30 +/-1%; host rates 30 +/-3%; source 60 +/-3%. Adjacent sequence/core tick/host cadence and existing clean counters must pass. Repeated scans are not new frames.

Diagnostic follow-up, not a proven root cause:

- 本窗口满足约定计数与连续性标准；仍需单独确认板卡实际画面。

The old baseline is an observed comparison; identical scene or controlled workload is not established.
Review: D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction\output\new-next-probe-20261104\assoc2way256-fastpipe-a\board-fps30-independent-review-v4-reuse-a.json
Measurement: D:\GravityLRT\thu\semester_4.5\FPGAchina\fpga-distortion-correction\distortion\work\hdmi-camera-fisheye-assoc2way256-fastpipe-20261104-a\fps-corrected-v4-reuse-a\receipt.json
