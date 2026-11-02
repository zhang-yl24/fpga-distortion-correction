# 720p checkpoint evidence selection — draft, 2026-11-01

This is an evidence-selection proposal, not a release receipt. Only this note is written. No files have been copied, no frozen candidate or receipt has been changed, and no PDS/hardware operation has been run for this review. Root owns CURRENT and the physical handoff.

## First-board document review

Reviewed `handoff/CAMERA_720P_FIRST_BOARD_20261101.md` against `board/camera720_transport_top.v`, `rtl/experimental/ov5640_current720_frontend.v`, `rtl/experimental/capture_warmup.v`, `rtl/experimental/ddr_video_output_1080_board.v`, `tools/camera720_program.py`, and `tools/program_native_raw.py` (paths below are relative to distortion unless stated otherwise). No factual error requiring a handoff edit was found.

- Input is CAM2 OV5640 RGB565 1280×720; identity remap, zero distortion coefficients, no additional rotation. The existing HDMI scan remains 1920×1080p30. Picture coordinates x320..1599/y180..899 are relative to the active image, not the total raster counters; `WX=X0+(AW-WIDTH)/2`, `WY=Y0+(AH-HEIGHT)/2`, and default RGB outside consumption is black.
- The frontend requires configuration and at least two complete 2560-byte ×720-line frames. The 8-second warmup counts a **continuous** interval during which camera, DDR, output PLL and TX readiness are all true; any readiness loss restarts it. The document correctly warns against treating brief startup black as a failed download.
- LED0 is approximately 1Hz; LED1 DDR readiness, LED2 output PLL lock, LED3 camera mode readiness, LED4 TX initialization, LED5 capture bit4, LED6 processing bit4, LED7 sticky fault. Ten complete bit4 blink cycles represent320 counter increments; this remains a coarse processed/captured-frame measurement, not unique displayed-frame rate.
- The top exposes no UART port. The program recipe uses PG2L100H, ID0x00602899 and1MHz JTAG, verifies the current bit/evidence chain, records DONE and cleanup, and performs volatile SRAM only. Notification and current board-power confirmation remain required before execution.
- Upright orientation, crop limits, VGA fallback SHA and the separation between DONE, image observation and optical acceptance are consistent. The VGA fallback SHA also agrees with archived calibrated-camera download/live records.

## Suggested portable README outline

1. **Status and scope:** named top, source checkpoint/commit, candidate ADF hash, preparation/native-check/bit/SRAM/board-observation statuses with exact evidence links. State explicitly that this is 720p identity transport, no720 optical acceptance, no measured720 fps yet. Do not replace pending entries with inferred pass.
2. **Expected image and controls:** one paragraph from the reviewed first-board handoff: central unscaled1280×720 in1080p30, black border, orientation/live update, LED meanings, startup delay, no HDMI IN or UART dependency.
3. **Evidence index:** a small table with purpose, original repository-relative path, packaged path (if actually copied), SHA256, and status. Keep original JSON bytes and their original absolute references unchanged.
4. **Reproduction boundary:** exact producer/tool hashes and environment version; identify which dependencies are in the checkpoint, already tracked in the repository, or retained in the original local work directory/external installation. A compact review checkpoint is not automatically a self-contained executable archive.
5. **Next action and limits:** finish all actual CDC cases, generate/verify bit, prepare/validate SRAM plan, notify user and confirm power, then capture actual screen/LED feedback. Only afterwards validate720 geometry/calibration and measure/optimize fps. CI remains deferred per user request; local CPU tests do not imply GitHub CI passed.

## Essential retained evidence

The final bit request has nine fields: Schema, Target, BuildPlan, CandidateADF, FinalInspectionReceipt, FinalCDCProof, FinalIOProof, ResetApplicationReceipt and ResetEffectAudit. Use these as the primary index instead of copying the entire PDS work tree. Additional raw evidence is selected from their actual dependencies, not from folder names or guessed passing stages.

| Purpose | Essential source / selection | Current status |
|---|---|---|
| Candidate and build identity | `build-b/plan.json`, source manifest `board/camera720-output-sources.json`, exact constraints/compiled-input hash records; final `reset-save-ready-a/input.adf` retained once | Candidate ADF exists; hash777bed47…48904 |
| Reset scope/effect | `reset-save-ready-a/result.json`, its exact stage recipe and applied reset FDC/proof; `reset-proof-a/proof.json`, `proposed-scope.fdc`; `reset-effect-a.json` and its baseline/final comparison references | Effect audit passed; retain final and baseline identities |
| Final full STA / native structure | `reset-export-a/result.json`, exact stage Tcl/plan and logs, `report_timing/camera720_transport_top.rtr`, exception report, placed exported netlist, route/placement information referenced by final audits | Actual final export passed; retain ten-table/exception evidence, not just summary flags |
| Electrical / pin / IO proof | `io-proof-fast-a.json`; successful `io-native-b` and `io-sites-native-a` receipts, exact query bodies, reports and all relevant diagnostic logs | IO audit passed; external AC acceptance remains separate |
| Logical-to-physical CDC mapping | `native-endpoints-d.json`, `sameble-supplement-a.json`, `physical-clm-boundaries-b.json`; vendor acceptance note/basis/extract and referenced exact document identities |976 base logical relations +3 supplemental;1139 physical queries; no invented individual-FF enumeration |
| Final physical CDC result | **Actual final single recovery coverage JSON once produced**, single plan `cdc-clm-single-a/plan.json`, parent `cdc-clm-through-b/plan.json`, preserved valid `cdc-clm-native-00/result.json`, actual single receipts00..06 plus their command/report/log artifacts | In progress; all2486 applicable cases must be observed and pass before marking complete |
| CDC initial evidence required by that result | Final reset export, `interstage-native-a`, ordinary `cdc-qualified-native-08`..`12`, `through-native-a` receipts and exact report/query/log dependencies | These are selected positive evidence, not disposable duplicates |
| Producers / audit provenance | Current source commit plus exact hashes for single/CLM collector, CLM/sameBLE/endpoint mapping, reset/IO auditors, bitstream/program tools, and imported parser/helper closure listed by audits | Already tracked tools should be referenced, not copied repeatedly per stage |
| Bit authority and generation | Actual request, completed authority, bitstream plan/Tcl/tool snapshot, pre-bit audit, execution result/stdout/stderr, final fresh STA and exception reports, programming report, verified `.sbit`, verification result | **Pending**; record actual filenames and SHA after generation, do not invent a bit hash |
| SRAM plan / actual board evidence | Actual program plan, scan/program Tcl and validation; only after authorized execution: receipt, scan/program logs, DONE and owned-process cleanup, user screen/LED observations | **Pending**; plan is not execution, DONE is not optical/image acceptance |

The small core index may include hashes for large netlists/ADFs/reports and point to the retained dependency archive; it must label any omitted bytes. For a genuinely replayable package, every file required by `InputSHA256`, receipt `Artifacts`, native report parsing and byte-inventory validation must remain available. In particular the live validator checks exact artifact inventories; deleting a duplicate-looking artifact from a receipt directory would invalidate that original stage. Deduplication is a storage/index choice, never an edit to a frozen receipt or its declared coverage.

## Exclude from the compact evidence narrative

- Do not bulk-copy `synthesize`, `place_route`, PDS databases, GUI images, caches or every intermediate ADF. Keep the final candidate once and only the baseline/route/structure artifacts actually needed by the selected audit chain. If an omitted file is still hash-bound, label the compact package as a review checkpoint with retained external/local dependency.
- Do not present invalid `cdc-qualified-native-00` (STA-3006 internal CIN), failed `io-native-a`, superseded endpoint mappings a/b/c, the pre-binding CLM-through-a plan, or prepared but unexecuted grouped `cdc-clm-native-01` as passing evidence. Their originals remain intact in local history; a short issue/status index is enough for the portable README.
- **Do retain** `cdc-clm-native-00`: unlike the invalid older similarly named stage, this is the explicitly bound clean partial receipt required by the single recovery plan. Partial evidence remains partial; it contributes only its actually observed cases.
- Avoid redundant independent summaries, parser probes and broad chronological logs when the final audit binds the underlying raw reports. Do not drop any log used to reject critical C/E/F diagnostics or any receipt that actually supplies a covered case.
- Do not rewrite old absolute paths to appear portable inside frozen JSON. Supply a separate location index; relocation/replay needs deliberate tooling support and revalidation, not a text substitution that changes evidence hashes.

## Stable anchors available now

| Object | SHA256 |
|---|---|
| Final candidate ADF | `777bed47bf6489457f42cda54a3cadc4e74f7a4ae2c8caacc51eb49f14e48904` |
| Reset application receipt | `b72a6a0a5bed4974e57111a2f471850a0308f9bf635ec9ccf80eb3213e24dc4c` |
| Final reset export receipt | `e720dc4717e3bada13671cabb0e0c87203116bbf0e281375c9fca10d20a00661` |
| Reset effect audit | `16bed69e7f3a16f59d48c5ed7356d8eb7c57c8b6be126da2ff91901809174df5` |
| Final IO proof | `792d12eb8fec8d4689ed4ab5a5cc788dae379729dc042b95bc14233a0830f31e` |
| Single recovery plan | `ce557c16859bb163203e17c8a6389520a9109f40972edf10ceff3c5e7754e9ee` |
| Single producer | `ca0691fdf60af99a623e1964240e5d4fc6fe4419d97473f6eadd9e6a26157219` |
| Bitstream adapter | `8d7b7bdf4ed110e9cb573008ff8ca23841094e9a02277514ca4833ab4be81516` |

All paths not under `board/`, `rtl/`, or `tools/` in the evidence table are relative to `distortion/work/camera720-output`, except the three vendor-basis files under `distortion/work/`. This note is a draft selection only; it neither changes the CI-deferred decision nor records720p optical or hardware completion.
