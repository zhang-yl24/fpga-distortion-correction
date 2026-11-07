# FAST cache source supplement

This directory contains the exact FAST cache and engine RTL used by the measured v4 bitstream, actual internal FDC, source manifest, build driver, generated build Tcl/plan and three small derivation scripts. It supplements the separate v4-firstpass-camera-20261104 evidence child without modifying that sealed child or the original 1,063 research payloads.

Cache SHA-256: c769fa5b352794c83e655c44a1a295f79c71e43f475b43274158671e4e92e888. Engine SHA-256: d17d5659a8818427d55951d8b0e5807dd21bc9da1ca9d903a56e53f65977804e. Both sources equal their actual native build compiled copies, with no compiled edits, and match the executed authority. See source-identity.json.

The engine already exists at ../sources/fifo-hdmi_camera_fisheye_engine_index10_fifo_a/hdmi_camera_fisheye_engine_index10_fifo_a.v. The FAST cache is derived from the archived choose-clear source; its generator retains the exact input pin. common-dependencies.json records exact archive matches and existing tracked repository paths.

Shared RTL/IP remain under distortion/rtl/experimental/, distortion/board/ and distortion/platform/video_base/ipcore/ddr3_test/. Five representative files (core, bank, remap, top and DDR wrapper) were hash-matched to the actual build original sources. The manifest and plan enumerate dependencies, original/compiled hashes and bound-header include relocations.

This is NOT a self-contained rebuild archive. Reproduction requires the existing repository, baseline manifests and generated fisheye profile/header files, Pango PDS 2023.2, device/IP dependencies and appropriate host paths. The copied scripts retain their original relative-path assumptions; consult OriginalPath in source-manifest.json and restore their original layout. No new build, simulation or hardware execution was performed for this supplement.

Chronology: physical worker 45352 completed the first proof, then redundant second verification was interrupted with actual exit -1. Original release worker 24952 completed native bit generation and first bit verification, then repeated prehardware verification was interrupted with actual exit -1. Separate reuse worker 34312 performed real volatile SRAM programming and the 30-second camera acquisition and exited 0. Neither interrupted wrapper is described as successful.

The actual short observation meets the requested counter criterion (host unique 30.000651945108 frames/s); repeat and blank increments are zero. Only 30 seconds are claimed, not 600-second stability or visual pixel acceptance. No Flash was written.
