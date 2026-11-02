# 720p orientation and crop review — 2026-11-01

Read-only product-readiness review of the frozen current720 source and build-b inputs. No PDS or hardware access; no candidate changes.

## Finding

The 720p bytes `3820=41,3821=07` preserve the **same documented mirror/flip bits** as the hardware-accepted upright VGA bytes `3820=00,3821=06`. There is no evidence here of a return to the old 180-degree orientation. The old reversed VGA setting was `3820=06,3821=00`. Physical image orientation still receives the normal first-board visual check.

| Control | Upright VGA | Current720 | Documented direction bits [2:1] | Difference |
|---|---:|---:|---|---|
| 3820 | 00 | 41 | 00 in both: ISP/sensor vflip clear | bit6 and bit0; not flip bits |
| 3821 | 06 | 07 | 11 in both: ISP/sensor mirror set | bit0: horizontal binning enabled |

Evidence: `hardware_check/ov5640-datasheet.txt` table4-1, lines2207–2217, identifies bits2 and1 as the ISP/sensor direction controls. Table7-7, lines6567–6579, labels 3820[7:3] Debug mode, leaves 3820[0] undescribed, and labels 3821[0] horizontal binning. We therefore do not assign undocumented semantics to 3820[6]/[0]. The locally retained ST driver independently clears only mask06 (`&=F9`) and sets06 for its mirror/flip API: `vendor/reference/st-ov5640/ov5640.c:1626–1713`.

The current720 ordered actions write41/07 at indices219/220, check full-byte values at283/284 and348/349, and never subsequently change these registers. Replaying the 403 actions agrees with `FinalModeBytes`; the ROM encoding is checked by the retained-source verifier. `ov5640_cadence_upright_init.v:32–35` supplies the accepted VGA00/06 comparison. The actual frozen build-b compiled initializer, frontend, command ROM, top and identity header match their source/compiled hashes and differ only by declared include rewriting. The current top uses this frontend; the remap is identity with no extra rotation.

## Actual programmed windows

These are inclusive sensor address windows, **not** directly the final ISP output size. Values were derived from the ordered register writes, including the VGA orientation wrapper.

| Field | Upright VGA | Current720 |
|---|---:|---:|
| Output 3808..380B | 640 × 480 | 1280 × 720 |
| X start/end 3800..3805 | 0..2623 | 0..2623 |
| Y start/end 3802..3807 | 4..1947 | 250..1705 |
| Inclusive sensor window | 2624 × 1944 | 2624 × 1456 |
| X/Y offsets 3810..3813 | 16 / 6 | 16 / 4 |
| X/Y increment bytes 3814/3815 | 31 / 31 | 31 / 31 |
| Horizontal binning bit3821[0] | 0 | 1 |
| HTS/VTS | 1936 / 1088 | 1892 / 740 |

Thus the current mode changes vertical crop, offsets and binning as well as output size. It is not a uniform 2× resize of the calibrated 640×480 image: that would give 1280×960, not 1280×720. Multiplying every intrinsic entry by2 would also incorrectly change homogeneous K[2,2]; even scaling just the pixel-valued focal lengths/principal point by2 cannot represent the changed crop without its offset transform. The old calibration file explicitly binds `image_size=[640,480]` and `capture_mode_id=vga640x480-rgb565-upright-3820-00-3821-06`. A proven mode-to-mode coordinate transform could provide a starting estimate, but its geometry must be verified on 720 images before correction acceptance. This review supplies no new 720 calibration.

## Product consequence and checks

No orientation source fix is indicated by these bytes. The current candidate deliberately validates **1280×720 identity transport**, centered in the existing 1920×1080p30 HDMI raster. Its zero-distortion coefficients mean initial 720 transport is not yet the accepted lens-corrected 720 product. After transport is physically checked, derive/validate the 720 lens profile and restore optical correction acceptance, then optimize measured frame throughput.

`prepare_camera720_sensor.verify` passed. `pytest -q -p no:cacheprovider distortion/tests/test_camera720_sensor.py`: 6 passed, 4 subtests passed. The RTL testbench explicitly checks output geometry/clock/RGB/pad settings; it does not independently assert the direction mask, so the static action replay and local datasheet/ST cross-check are the direction evidence here. No new tests or acceptance gates are needed for this read-only finding.

Key frozen references:
- current720 initializer SHA256 `f8530a40248f462e2914c27c3ca961f66b316aa1aa669539e88c26b3f1e02456`.
- 720 command ROM SHA256 `05ce241ce37286b6820eeeaad28eeff0821f12d1319bdc6747c4fd04a72ff22c`.
- 720 ordered sequence SHA256 `88cd19153f7f5fda5c80b86a4112f6e689ca52f094642cd1e2ce967261ee2c5d`.
- Source binding: `distortion/board/camera720-output-sources.json`; compiled binding: `distortion/work/camera720-output/build-b/plan.json`.
- VGA reference: `distortion/board/ov5640_cadence_trial_commands.vh`, `distortion/rtl/experimental/ov5640_cadence_upright_init.v`, `handoff/CAMERA_VGA_UPRIGHT_20261031.md`.
- VGA optical profile: `distortion/results/camera-vga-calibration-20261101-a/profiles/fisheye-profile-a.json`.
