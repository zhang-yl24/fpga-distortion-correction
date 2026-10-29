# Frozen acceptance candidate — 2026-10-29

This isolated snapshot preserves self-authored geometry bypass + atomic Brown13/rotation/Gamma frame sampling,actual capture-DMA/behavior-DDR/arbiter/reader/FIFO scan benches,and the exact board top/controller used for today's diagnostic. It does not replace the repository's production entry. Modules share names with other candidates: compile only the selected manifest closure, never glob all RTL.

Start with HANDOFF.md,FAILURES.md,EXCLUSIONS.md and evidence-summary.json. All hardware/formal gates are false. Hardware,simulation and PDS work remain paused after this Git delivery. This commit does not run tests or authorize their execution.

The source hashes distinguish original validated bytes from include-only portable copies. The new portable entry points receive static delivery review only; no test/EDA run was performed after relocation. Do not transfer original physical/functional acceptance to changed delivery SHA without a separately authorized validation.

## Reproduce later, using explicit local dependencies

`tools/materialize.py` only prepares fresh local inputs and commands; it never launches a tool. Supply a fresh --out directory and explicit --case control,real-directed,real-native or board. For RTL cases supply --vivado-bin. real-* also require --fixture-dir with private files matching the case manifest SHA. Board requires --vendor-root (a lawful distortion dependency root),--parameter-header,--fdc and --pds-shell; all83 source-role hashes are checked. Source/header copies are placed together so no original D: drive path is required. IDF74 bodies are not separate add_design entries.

Example preparation (replace angle-bracket placeholders with local paths):

```
python -B distortion/acceptance/20261029/tools/materialize.py --case real-native --fixture-dir <private-native-fixture> --vivado-bin <Vivado-bin> --out <fresh-output>
python -B distortion/acceptance/20261029/tools/materialize.py --case board --vendor-root <lawful-distortion-dependencies> --parameter-header <private-board1080-penn.vh> --fdc <frozen-diagnostic.fdc> --pds-shell <pds_shell.exe> --out <fresh-output>
```

Only after separately resuming and scheduling one heavy tool at a time, `tools/run_rtl.py --work <prepared-output> --execute-offline-rtl` can consume RTL commands with bounded owned-PID cleanup. Board commands are emitted separately for compile-map,PNR(explicit current-map PCF),and independent saved-ADF STA; there is no bit/download/Flash command. --final-adf may select the already saved exact diagnostic ADF (SHA checked), avoiding recompile/PNR when obtaining the missing independent STA.

`tools/golden_realframe.py` preserves the independently used CPU arithmetic with explicit private contract,source-dir,review-dir,calibration-file,origin-evidence and output-dir arguments. It requires the original exact contract SHA and does not ship its data. Python dependencies are in requirements.txt; tool binaries and licensed IP are external.
