# Full 720p camera system regression — passed (2026-11-01)

Only three new files were added by this task: `tests/tb_camera720_system.sv`, `tools/run_camera720_system_sim.py`, `tests/test_camera720_system_sim.py`. No frozen production RTL, existing helper, board source or manifest was modified. No PDS, serial, JTAG or board access occurred.

## Actual executed scope

The actual `camera_vga_video_system` controller and production DVP byte capture, DMA, bank manager, Brown mapper, RGB565 sampler, read/write arbiters, CRC, output FIFO and scanner execute together. Camera byte stimulus and DDR UI alone are modeled. The top's exact `board/camera720-identity.vh` is read and hash-bound; it is transport identity, not lens calibration.

Two distinct 1280x720 frames are sent at modeled 48 MHz PCLK with HTS 1892 pixels (3784 byte clocks), VTS 740 lines, full blanking, active-low VS/HREF and low-byte-first RGB565. Core is 125 MHz; actual output scanner is 74.25 MHz, 2200x1125 raster, 1920x1080 DE with the native720 image centered. Source boundaries may wait for reservation; throughput is not a physical frame-rate measurement. Final test-only suppression of an extra source reservation drains accepted work without resetting it.

## Pass results

- Complete source/result/actual HDMI frames: 2, each 921600 pixels; actual output dump independently compared: 1,843,200 pixels.
- Source and result writes: 115,200 and 115,200 256-bit beats. DDR reads: 230,400 beats. Both final source and result burst addresses use UI offset460672; UI units are four bytes.
- Source, result, scanner and CPU dump CRCs all agree: frame1 `DF5734A7`, frame2 `73964307`.
- Full 1080p30 rasters checked: 4; black-border samples checked: 5,760,000. Underflows0, CRC mismatches0, final draintrue.
- AW/W/AR stall cycles: 6885/36612/11402. Read/write arbitration contention cycles: 91/13.
- Capture+process / process+display / capture+display overlap cycles: 1,430,122 / 1,400,293 / 2,084,203.
- Capture FIFO peak 1/64; output FIFO peak 512/512. A full FIFO was correctly backpressured; no overflow or underflow occurred.
- Two distinct source/result banks were used. This run does not claim bank reuse or repeated scans (both counts0); separate ingress/output regressions cover reuse.
- Whole-run elapsed: 1683.668 seconds. All source and fixture SHA256 values remained unchanged.
- Six CPU verifier negative tests passed: corrupted pixels, mixed frame IDs, truncation/extra data, wrong publication CRC and release ordering were rejected.

## Evidence and reproduction

Passed native+Python report: `work/camera720-system/attempt-c/camera720-system-simulation.json`
Report SHA256: `ef5149b90869f25f13697793e5ae11c3d95d072a53860275124e8a16499ec2de`

```powershell
.venv/Scripts/python.exe -B -X utf8 distortion/tools/run_camera720_system_sim.py --workdir distortion/work/camera720-system/attempt-d --maximum-seconds 1800
.venv/Scripts/python.exe -B -X utf8 -m unittest discover -s distortion/tests -p test_camera720_system_sim.py -v
```

Historical attempts preserved: attempt-a was manually stopped before any complete-frame claim because the unoptimized three-frame estimate exceeded the1800s limit; no RTL assertion had failed. attempt-b quickly rejected the unsupported xelab option spelling `-O 3`. attempt-c uses installed-tool `--O3` and the assigned minimum two complete frames. No claim is based on the interrupted attempts.

No sensor SCCB sequence, board startup, physical DDR/HDMI, input electrical timing, native resource/CDC/timing, stopped-clock recovery, 720p optical calibration or measured FPS acceptance is inferred from this digital test. The report logs exact scope.
