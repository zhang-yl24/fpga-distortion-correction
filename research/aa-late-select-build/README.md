# AA-derived late-select: independent first-party build kit

**Status: NOT_MAP_OR_STA_PASSED.** This source-only research kit is complete for the published first-party inputs and public build recipe. It is **not** a self-contained licensed PDS project and has not produced a new ADF, SRAM image, routed timing result or board result. Exactly 77 external vendor inputs remain missing. Do not reuse the original AA bitstream or its timing margin as evidence for this candidate.

## Identity and scope

- Baseline: [AA delivery at fixed commit 87cf6ca466ba90d4d18c5d4d82ccd8b1820fde99](https://github.com/zhang-yl24/fpga-distortion-correction/tree/87cf6ca466ba90d4d18c5d4d82ccd8b1820fde99/delivery/20261107-camera1080p60-key1-aa).
- Independent root: this directory. `native/` is its HDL include root. No checkout, simulation evidence, admitted delivery, source outside this directory or user computer is modified by staging this kit.
- Exactly 78 public native inputs are included. The required closure remains 155 native files and 68 ordered direct imports. The omitted 77 comprise 75 DDR files plus two PLL wrappers. Their exact required paths are in `EXTERNAL_INPUTS.json` and `rebuild/expected_source_files.txt`.
- The late-selection system wrapper is frozen at SHA256 `44fa12a52082ca9e2319e7c1ad7ed1e6603efc99c4687a39353a5e8d7895c918`. Its compatibility default remains `DISPLAY_SELECT_GRACE_CYCLES=0`.
- Only the independent TOP adds `DISPLAY_SELECT_GRACE_CYCLES=8192` and explicitly forwards it to the system instance. `patches/top.patch` has exactly these two added lines. `patches/system.patch` documents the earlier frozen candidate change, not a new logic edit in this kit.
- AA cache remains SHA256 `ff5e551c13083cecf9325b6acef0a00b58f7f1776cd7f5dbec341e52f2082088`. Other native inputs, every constraint, the vendor configuration tables and the public PDS recipe remain byte-identical to the fixed baseline. Their Git blob hashes and SHA256s are retained in `provenance/`.

Fixed operating configuration: 1920×1080 at nominal 60 Hz, camera HDMI, KEY1 requests RAW/CORR with original 2,500,000-core-cycle debounce, fixed Brown, zero rotation, Gamma OFF, STATS ON, AA cache HEAD=0, two result banks, core 125 MHz, output pixel 148.5 MHz, input constraint 150.2 MHz. See `CLOCK_AND_PARAMETERS.md` for named nets and constraint relations. The 8192-cycle grace is 65.536 microseconds at the intended core rate, not a guaranteed end-to-end camera latency improvement.

## Offline checks, runnable now

From this directory, using Python 3.9 or newer:

```text
python tools/preflight.py
python tools/test_preflight.py
python rebuild/verify_sources.py
python tools/preflight.py --require-eda --pds pds_shell
```

The first command checks frozen source hashes, TOP forwarding, clocks/constraints through unchanged hashes, ordered imports and public closure. It reports `PUBLIC_KIT_STATIC_PASS_EXTERNAL_INPUTS_STILL_REQUIRED`, not EDA readiness. The second runs only static and failure-path tests in temporary copies. The last two must stop with exit code 2 until the missing legal IP and genuine tool receipts exist. No command above launches a vendor tool, accesses hardware or reruns HDL simulations.

## Inputs required before a new implementation

1. A normally authorized PDS 2025.2 / Fabric Compiler build 211867 installation with ADS and Logos2 PG2L100H, -6, FBG676 support. The public recipe documents `pds_shell`; no executable or license is bundled.
2. Authorized matching DDR inputs from HMIC_S 1.10, identifier 042003. The recorded DDR generator is IP Compiler 2022.2-SP6.4 build146967, not the implementation version. Do not substitute a different HMIC model. For fresh generation follow `ip_setup/IP_REGENERATION_STEPS.txt` and `ip_setup/CONFIG_TOOLS_README.txt` in a new project. The public helper checks all 371 DDR values.
3. Authorized cfg_pll and bringup_pll implementations with all saved PLL parameters. The historical Logos2 PLL model is identifier 041001, observed version 1.5. The frozen wrapper does not certify its generator release. Do not invent one. Both primitive wiring and actual generated-clock coverage still require implementation review.
4. Restore only into this independent root, at the paths listed in `EXTERNAL_INPUTS.json`. Preserve the complete IDF synthesis closure. Run the public read-only configuration checks. The public material supplies no per-file SHA256s for the omitted vendor implementation, so newly restored/generated files receive a new local hash receipt. Matching names or parameters is not original byte identity and does not promise reproducible bit bytes.
5. Prepare private external-input and tool receipts using `RECEIPTS.md`. Keep them local. They record actual evidence and provenance; they are not supplied approvals, license verification, or substitutes for vendor reports. Do not fill unknown facts with guesses. Empty modules, simulation-only models, blackboxes and generic synthesis substitutes are not acceptable.

## New build entry point

Use `tools/run_stage.py`, which gates and invokes the unchanged public `rebuild/run_build.py`. The underlying Tcl/options are fixed-baseline bytes; no new PDS or IP-generator flags were invented. `rebuild/README.md` is the original recipe and historical context, not evidence that this late candidate passed EDA.

```text
python tools/run_stage.py map --pds pds_shell --vendor-receipt private/vendor-inputs.json --tool-receipt private/pds-tool.json
```

For `place`, `route`, `sta` and `bitgen`, add `--input-adf` pointing to the real newly generated preceding checkpoint inside this root and `--predecessor-review` pointing to a local review receipt. Stage order is map, place, route, sta, bitgen. Map incorporates compile/synthesize/dev_map. Each stage refuses an existing output directory, receipt or lock. Failed/interrupted stages are not silently resumed; create a fresh independent copy after diagnosis. The wrapper records source identity, receipts and new output hashes. After exit zero, outputs remain **GENERATED_UNREVIEWED**.

The review receipt must identify actual generated reports by hash and explicitly reject unresolved cells/blackboxes. The wrapper does not parse or certify timing reports. Independently inspect resource use, setup/hold, unconstrained and zero-coverage paths, CDC ownership, external I/O timing assumptions and clock exceptions. Keep the final hold-optimized route ADF unchanged for STA and bitgen. Before bitgen the wrapper also requires a successful STA invocation tied to that exact ADF and unchanged vendor/tool receipts, plus `--sta-review` with explicit setup/hold, clock/exception and unconstrained/zero-coverage report review. Successful invocation is not timing acceptance; board acceptance remains a separate gate.

No script here programs SRAM/Flash, opens a serial port, JTAG or a camera. Offline bitgen is not programming. No generated vendor implementation, ADF, old bitstream, executable, license file or key is distributed.
