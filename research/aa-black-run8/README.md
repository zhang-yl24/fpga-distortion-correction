# AA black-run8 research overlay

Research only, default OFF. This is not the default delivery, a bitstream, a complete PDS project, a physical timing result or a board-accepted version. The target remains HDMI camera 1920x1080 nominal 60 Hz input, KEY1 RAW/CORR, Gamma OFF and no added rotation. Input/scan rate is not new-frame FPS.

This directory contains only seven first-party RTL modules, one first-party CRC include, the generated fixed black-interval ROM and integration/identity instructions. It does not contain vendor IP, primitives, PLL implementations, licenses, calibration source assets, source images, model frame vectors or bitstreams. Existing frozen delivery paths and default candidate are unchanged.

Use a new isolated copy of the complete, legally available AA/A platform. Do not overlay the Brown-B CORRECTED_ONLY mapper/core, AE HEAD0 or AF54 cache experiments. Required AA inputs and explicit parameter changes are in PDS_INTEGRATION.md. RTL_IDENTITY.json pins the exact nine source assets. Run `python verify_overlay.py` from any directory to check this overlay. SOURCE_MANIFEST.json covers every published file except itself.

## Existing cloud evidence and its limits

- The fixed Brown processing-pipeline model completed compression ON/OFF frames: 2,073,600 checked pixels each, ON 1,895,436 and OFF 2,076,658 bench cycles, identical raster CRC f318aae7 and digest 8dc8b429. The difference is 181,222 model cycles, or 1.449776 ms at 125 MHz. Both issue 23,690 source AR commands, 32,400 AW commands and 129,600 W beats. This is the same new fixed research pipeline pair, not old-AA-bitstream timing or camera-to-display latency.
- The published KEY1 adapter/engine hashes completed CORR then RAW processing frames without reset using distinct synthetic source banks: 4,147,200 pixels, two completions/releases, CRCs 57649cc7 and 06b4fb2c. The display control was abstract; camera capture, display DDR scan, HMIC behavior and real KEY1 were not covered.
- The published system copy has only strict actual-module elaboration, not dynamic capture/process/scan validation. OFF preserves the original bank invocation; ON selects the new adapter. Outside that selection, system capture/scan/control text is retained. Hierarchy and synthesized behavior still require fresh validation.
- Earlier selector/writer-only synthetic results (including 8.726%) are component evidence, not processing-frame or board improvement.

The full evidence remains in the separately retained checkpoint; it is intentionally not copied into this minimal source transfer. These statements do not certify local source copies, implementation or physical results.

## Exact research boundary

Compression applies only to an accepted CORR, identity-rotation, Gamma-OFF snapshot using the fixed matching Rational Brown profile. RAW remains a scalar path. The generic internal rotation inputs are inherited interfaces, not authorization to add rotation to the camera target. Gamma ON is unsupported and faults 0x42. A telemetry parameter ID is an identity tag, not permission to replace calibration while retaining this ROM.

The optional recovery guard and DDR progress observer are not included or connected. There is no autonomous reset, flush acknowledgment, transaction withdrawal or claim of safe bank reuse after an unqualified DDR reset. Preserve the original common reset/release contract.

Before adoption: exact-source PDS compile/Map/P&R/two-corner STA, initialized-ROM inspection, clock/IO/CDC/reset review, actual system admission/scan/lease tests, and physical camera/KEY1/DDR/visibility/rate acceptance are all required. Do not use a compile success or yesterday's A/B timing as their replacement.
