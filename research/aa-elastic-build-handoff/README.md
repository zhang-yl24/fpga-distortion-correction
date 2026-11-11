# Minimal isolated PDS synthesis handoff

**OFFLINE_PREPARED_AND_TESTED; PDS_NOT_RUN; NOT_BUILD_ACCEPTED.** This handoff contains only new first-party Python, instructions, hashes and sanitized test summaries. It contains no seed RTL, vendor IP, ROM payload, private logs, ADF, bitstream, tool or license. The helper does not create branches or publish.

Workflow: verify existing private inputs, generate isolated scripts, run compile+synthesis on the authorized PDS computer, then collect fresh evidence. Only the explicit `run` command launches PDS.

Target: the published `research/aa-elastic-result-buffer` at commit `22d5b2bc09c0013939de57d47436405a380bb5fd`, alongside the unchanged `delivery/20261107-camera1080p60-key1-aa`. The opt-in top is `board1080_elastic_research_top`: `ENABLE_ELASTIC_BUFFER=1`, `RESULT_BANKS=3`. Generic compatibility defaults and the admitted AA candidate are unchanged. HDMI camera 1920×1080 nominal 60 Hz, KEY1 RAW/CORR, fixed Brown, Gamma OFF and zero rotation remain the target. Actual core/DDR-UI 125 MHz and pixel/PLL 148.5 MHz are preserved. The existing input constraint is approximately 150.2 MHz; it is not a requested clock increase.

## What this closes

The historical native record contains an actually executed command for fresh project creation via **`pds_shell -file ... -work_dir ... -project_name ...`**. Its Tcl records real `add_design`, `add_constraint`, `set_arch`, `compile` and `synthesize` syntax. This handoff uses that entry, not invented `create_project`, `open_project` or ADF commands. It stops after synthesis. No map, PNR, STA, bitgen or hardware action is provided.

A read-only preflight authenticates the published recipe, all 164 canonical originals, the existing 174-file private derived native tree, all 85 ordered imports, the exact top/device/constraints and ROM. It reuses the public preparer's existing in-memory validation, not its tests or simulations. It then generates private path-bound Tcl with guarded ROM hooks and a 120-occurrence active FDC query inventory. Preparing the scripts is not PDS validation.

## Repository placement

Use the sibling directory `research/aa-elastic-build-handoff/`. Leave all 24 files under `research/aa-elastic-result-buffer/`, its manifest, and the AA delivery README byte-identical. Nesting this handoff inside the pinned candidate root breaks its exact-inventory gate.

From the handoff directory, the candidate is `../aa-elastic-result-buffer`, but resolve that reference before passing it to the helper. For example:

```text
python -c "from pathlib import Path; print(Path('../aa-elastic-result-buffer').resolve(strict=True))"
```

Use the printed absolute path as `--candidate` below. Do not pass literal `..` components to either preparer. The examples use the equivalent resolved Windows path.

## Four steps on the authorized PDS computer

Prerequisites: Python 3.10+, the exact published source directory, the authorized canonical `ON/native` plus sibling manifest/MAP/KEY1 record, and its already-generated full private native input directory. If the last item is unavailable, use the pinned public `prepare_native.py --native ... --out ...` once; do not substitute an old top, simulation stubs, or regenerate approximate vendor IP. The legacy full preparation package is not required by this launcher.

Use real absolute paths. On Windows, forward-slash paths such as `D:/private/...` work with Python and the generated Tcl; filesystem behavior has been exercised on Linux, not Windows/PDS. Generate the handoff on the target computer: prepared scripts contain its exact paths and cannot be moved and reused. Keep every output outside the candidate, seed record, existing private inputs, and this handoff directory.

1. Verify existing private inputs without writing or invoking PDS:

```text
python -B pds_handoff.py prepare --candidate D:/source/research/aa-elastic-result-buffer --native D:/private/canonical/ON/native --prepared D:/private/elastic-native --dry-run
```

2. Create a fresh **private** handoff directory; its parent must already exist:

```text
python -B pds_handoff.py prepare --candidate D:/source/research/aa-elastic-result-buffer --native D:/private/canonical/ON/native --prepared D:/private/elastic-native --out D:/private/elastic-synthesis-01
```

3. Only when that computer has the licensed, matching PDS installation and execution is authorized, launch the isolated compile+synthesis attempt:

```text
python -B pds_handoff.py run --run D:/private/elastic-synthesis-01 --pds E:/Pango/PDS2025/pango/PDS_2025.2-ads/bin/pds_shell.exe
```

The historical executable is PDS 2025.2 build 211867, SHA256 `32983ea8e0cf0498481e5ae8ff75fcdd4ee329f2efb83dea9d8eee85583931cc`. That exact binary hash is checked before launch and again after return. Matching version text alone does not pass. If it differs, stop and inspect the legitimate installed version; do not change the pin merely to force a run. License/runtime/device/IP availability is only learned by the actual tool attempt, never inferred from the executable hash.

The launcher reconstructs every permitted script from authenticated inputs before execution, so changing a script and editing its local hash receipt does not bypass the gate. It invokes:

```text
pds_shell.exe -file <private handoff>/SYNTHESIS.tcl -work_dir <private handoff>/work -project_name aa_elastic_<unique nonce>
```

It imports the 85 listed files exactly once, four original constraints in recorded order, and sets `Logos2 PG2L100H -6 FBG676`. It uses `compile -verilog_standard SystemVerilog -top_module board1080_elastic_research_top -include_path <verified roots> -pre_tcl <guarded hook>` then `synthesize -ads -selected_syn_tool_opt 2 -pre_tcl <guarded hook>`. There are no top-parameter overrides and no timing/CDC exceptions added. Historical `MAP_PREPARED.tcl` is read for identity, **never sourced**.

4. Collect and inspect only that run's fresh evidence:

```text
python -B pds_handoff.py collect --run D:/private/elastic-synthesis-01
```

`run` also calls this collector automatically. Exit code **0** means offline preparation only. Exit **2** means refusal/incomplete or changed evidence. Exit **3** after run/collect means synthesis evidence collected but **review/acceptance remains open**, including when every subprocess command returned zero. Save collector output only in a private location outside the run tree if needed. Repeated collect is read-only.

## Report/constraint/ROM gates

- A run needs matching start/end receipts, unique run markers, all 85 import and four constraint stage markers, zero tool exit status, unchanged input and generated-script identities, and unchanged output/log/ROM-trace hashes. A brand-new work directory is mandatory; an interrupted or previously started handoff cannot be relaunched. Report timestamps older than this run are flagged. These are integrity checks, not a cryptographic proof against someone fabricating receipts.
- The guarded ROM hooks only write missing `run8_intervals_30bit.mem` inside the owned project subtree and refuse conflicting bytes or outside-CWD writes. They embed the authenticated ROM privately and record actual bootstrap/compile/synthesize CWDs. The collector re-hashes every recorded ROM copy. The original run observed `prj_tasks/syn_1/compile` and `.../synthesize`; the new hooks do not assume that exact directory layout. **Mapped ROM initialization/content and memory inference still require actual synthesis reports/netlist inspection.**
- `CONSTRAINT_QUERY_INVENTORY.json` identifies every active `get_ports/get_pins/get_clocks` expression and original file/line. After synthesis, `query_probes.tcl` attempts those exact read-only expressions and captures return code plus raw result. A query exception, empty result, missing or repeated probe is flagged. **A raw Tcl result is not a cardinality.** `_opaque_collection_1` might be a collection handle, not one object.
- **Unverified PDS API boundary:** the retained scripts do not establish a collection-size/enumeration command or whether these queries run against an available post-synthesis netlist in the shell. Do not guess `sizeof_collection`, `llength`, `get_cells`, `report_clocks` or an unsupported report command. Check the installed PDS command documentation and real netlist context; obtain a real object count/name list for every query and review expected cardinality, not just nonempty strings. Probe errors may mean the stage/API is unavailable, rather than a proven missing object. This is an explicit remaining blocker to constraint acceptance.
- The query inventory covers explicit get_* expressions, **not** the many `define_attribute` pin assignments or the two `def_route` targets. Inspect native constraint import diagnostics and actual object coverage for those too. The old `system.input_link` comments are not active constraints and are not evidence that `system.g_elastic.candidate` CDC is covered.
- The collector lists fresh report paths/hashes and triages blackbox, unresolved-cell, license/fatal and common unmatched-object messages. Any match needs review, including benign “0 blackboxes” wording. No matches do not prove absence. Obtain the tool's real module/cell/resource reports and explicitly establish zero unresolved/blackbox cells, correct DDR/PLL elaboration, top/device, clock propagation, and initialized ROM. Exact report-generation/blackbox-count API was not established by the retained record, so none is invented.
- Preserve the original DDR clock relations, routing priorities, 8 ns core and 148.5 MHz pixel assumptions. Review FIFO Gray crossings, grant/done held bundles, owner/request/reset crossings and the new two-bit result-slot metadata in actual hierarchy. CDC/STA and physical capacity/bandwidth remain separate gates. No existing AA/Run8 timing, bitstream or camera observation transfers to this candidate.

## Missing dependencies and lifecycle limits

The earlier full input-resolution audit resolved 74 IDF source references, 25 visible include edges and four constraint files. It authenticated 71 protected `.vp` sources without elaborating them. Eight IDF **declared output** entries remain absent: generator log, simulation slice, example test RTL, three example testbenches, and Verilog/VHDL templates. They were not silently promoted to required synthesis sources, invented, or replaced. If PDS actually requires one, stop and obtain the exact authorized vendor artifact. A new generated IP variant is not the pinned canonical identity.

`run` is foreground and waits for `pds_shell` to return. It deliberately does not implement the historical Windows process-tree/job controller, an admission scheduler, or a resource/time watchdog. Do not run another build concurrently. On interruption/crash, retain the start-only receipt, inspect and stop only this project's tool descendants using the computer's established procedure, then prepare a different fresh directory. Neither a root process exit nor this helper proves all descendants exited. Inputs and output directories must stay stable; concurrent filesystem replacement by another process is unsupported. This helper is a minimal local synthesis handoff, not a replacement for an existing mandatory computer execution policy.

## Offline verification included

```text
python -B test_handoff.py
python -O -B test_handoff.py
```

The tests use tiny first-party fixtures and an existing `tclsh`, never PDS or HDL simulation. They cover Tcl command construction/quoting, query brackets in braces, raw-result versus cardinality, ROM staging/conflict/outside-CWD behavior, changed scripts plus rewritten receipts, wrong project, paths/symlinks/existing output, missing receipts, report drift/staleness, blackbox diagnostics, incomplete ROM phases and query errors. The real offline preflight and prepared script generation reuse already-generated private inputs. No long native/camera simulation was repeated.

The distributable is only this directory's explicit manifest. Never package a generated private handoff, private input tree, canonical seed, raw tool logs or reports. `COMMAND_PROVENANCE.json` records hashes and source roles without copying the historical private logs. `results/` distinguishes tests/preparation from all not-run PDS and board gates.
