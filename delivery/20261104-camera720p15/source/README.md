# Frozen 720p15 production source closure

Top: `compiled/board/camera720_view_toggle_top.v`; BuildID `47e52e93b7238f29`; ProfileID `f79c44d9bdeb5b11`.

- `compiled/` and `timing.tcl`: all 118 production inputs in `build-plan.json` PreparedSHA256, copied byte for byte.
- `upstream/`: original camera720-stats-delay/build-c source/compiled inputs and baseline plan used to produce this build.
- `generator-inputs/`: remaining repository inputs named by InputSHA256, including the original generator script.
- `impl.tcl`, `.pds`, `sources_info.log`: original local build control files, preserved without rewriting.
- `finalization/`: archived post-route hold correction, reset-scope, final timing export and bitstream generation controls.
- `../source-manifest.json`: relative package paths, exact stored bytes and SHA256, original paths and provenance roles.

All 240 InputSHA256 entries were checked against the original files: 239 repository inputs are copied, and the external PDS executable is listed but not redistributed. All 118 PreparedSHA256 entries are present and match. This directory includes the frozen inputs rather than relying on mutable default RTL.

These are original bytes, so historical absolute paths/includes and the original baseline work layout remain in scripts. This is a source/provenance closure, not a tested one-command portable rebuild. Relocation, PDS 2023.2-SP3 (build 154097), device/IP installation and a fresh implementation/STA are required before claiming a rebuilt bitstream. No EDA or hardware operation was performed for this export.

The profile processes a 1280x720 camera image centered in a configured 1920x1080, 30 Hz HDMI raster. The board counter result is 15 new corrected frames/s; it is not a 15 Hz HDMI scan setting.
