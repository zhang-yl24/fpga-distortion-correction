# Rollback identities and pretest check

Keep the colleague's approved rollback files untouched and ready before any U load. Select the approved file that the colleague already uses, verify its SHA256 locally, and record the choice in the test log. This package does not bundle or program rollback bits.

## a266 camera diagnostic baseline

File: `camera-op-input-firstloss-timing-unclosed4-setup-minus32ps-diagnostic.sbit`

SHA256: `a266044d4da4b8883fc7fa1e9250f62aee37bbf27df349354b2a11250129c547`; bytes: 3,791,112. The package preparer verified the local frozen file's hash and size. The user/colleague reported camera success; we have not replayed that observation. This artifact retains four slow setup violations, worst slack -0.032 ns, and is not fully signed off.

The exact path exists in fixed public ref `5d53319c4167596cd2f577c65a3b2d8dfd54494d`:
https://github.com/zhang-yl24/fpga-distortion-correction/blob/5d53319c4167596cd2f577c65a3b2d8dfd54494d/delivery/20261104-op-camera-input-unclosed4-diagnostic/camera-op-input-firstloss-timing-unclosed4-setup-minus32ps-diagnostic.sbit

Its protocol is PGIQ0001 diagnostics, not U's normal PGSTAT02 path. It has no PGSTAT02/SGA/SGT presentation counters. Use its own published instructions and decoder if the hardware owner selects it.

## Colleague's peer15 baseline

SHA256: `aa21991374fbeb4a6733741095f38e27336f1e47dd67b963feb243428a5b353b`. Exact public download path and local file size are unverified here. Use the colleague-held previously verified file and require a matching hash before the U test. The prior reported record is 599 seconds / 8,985 new frames, approximately 15 fps; this package preparer did not replay the raw record. Do not substitute another bit based on its filename.

## Optional low-load golden

SHA256: `df7eec4b4e38441183b45baf8b38d8414fdd456a5eb78fb3aeb1fd94b361b360`. Use only if the colleague already possesses and has verified that golden artifact. It is not assumed available or selected by this package.

If U fails to present the camera reliably, stop the test, preserve the evidence and restore the preselected approved rollback artifact using the established local procedure. Prior rollback observations are not U measurements. This document performs no SRAM, Flash, JTAG or serial action.
