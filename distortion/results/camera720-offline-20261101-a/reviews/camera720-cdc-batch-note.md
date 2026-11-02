# 720p CDC native batch offline checkpoint

Date: 2026-11-01. This subtask is complete and frozen. No PDS or hardware action was performed. All Python processes started by this subtask have exited.

New source files only:

- `distortion/tools/camera720_cdc_batch.py`
- `distortion/tests/test_camera720_cdc_batch.py`

The tool has `prepare` and `check` modes. `prepare` fully rebinds the supplied actual placed export and repeats the 720p IO, FIFO/monitor Gray, scalar, reset-chain, held-snapshot and held first-consumer structural extraction. Its local receipt adapter accepts the existing original, measured-route-derived, and reset-derived inspector schemas through their own strict binders. No inspector whitelist or existing source file was modified. A prior structural report or prior pass flag is not accepted as authority for a new ADF.

Each timing command has one source and a small list of destinations, using the already allowed `-max_path 1000 -nworst 8`. Groups contain at most 28 endpoints; the actual original candidate needs at most 27. Every physical pair remains separately enumerated. `check` requires both slow and fast corners, ordinary setup/hold for interstage pairs, and the actual FDC max/min constraints for crossing pairs. Missing native min-delay details are pending, never inferred from max-delay success. A native min-delay dialect that does not match the explicit accepted syntax also fails closed and will need review against its actual receipt. Site queries check exact final instance/site mapping only; electrical attributes remain unverified.

The checker rebinds the exact ADF path/SHA, build SHA, export, complete source/tool closure, approved query body and all native artifacts. It rejects wrong candidate/build, failed native execution, Tcl drift, excepted ordinary interstage paths, negative slack, mismatched clock/edge or bound, and truncated report blocks. Top-N omission cannot pass coverage. Missing cases produce per-pair `supplement-XX.tcl` files, still bounded to 300 allowed commands per batch. Any bad native variant prevents a pass even when other variants cover every case. Overall timing/hardware/electrical acceptance flags remain false.

Validation:

- `python -B -X utf8 -m unittest discover -s distortion/tests -p test_camera720_cdc_batch.py -v`: 16 tests passed.
- AST parsing of both new Python files passed.
- Pure CPU preparation on `work/camera720-output/export-a/result.json` completed with exit 0. Final tool-bound evidence is `work/camera720-output/cdc-batch-original-b/batch-plan.json` and `query-00.tcl`.
- This is the **original build-b ADF only**, SHA `420127079b4123b3942edd45c1f5b725221a4e3b3a1b8a91a448d9526e6d0cbe`: 601 physical pairs, 101 ordinary pairs, 500 crossing pairs, 2,404 corner/kind cases, 133 timing groups + 128 site queries + one route dump = 262 commands in one native context.
- Earlier `cdc-batch-original-a` evidence predates the final tool SHA and is superseded; do not use it.
- Neither the grouped native query nor a final reset/route export preparation/check has been executed. The original ADF preparation demonstrates the CPU tooling only and must not be used as final-ADF physical approval.

Resume after the final candidate export is ready (fresh output directory required):

```powershell
.venv/Scripts/python.exe -B -X utf8 distortion/tools/camera720_cdc_batch.py prepare --export-receipt <final-export-result.json> --output-dir distortion/work/camera720-output/cdc-batch-final-a
```

Use that generated query body with the matching existing strict inspector for the same candidate; this tool itself does not start PDS. After obtaining actual successful query receipts:

```powershell
.venv/Scripts/python.exe -B -X utf8 distortion/tools/camera720_cdc_batch.py check --batch-plan distortion/work/camera720-output/cdc-batch-final-a/batch-plan.json --query-receipt <final-native-query-result.json> --output-dir distortion/work/camera720-output/cdc-coverage-final-a
```

Supply multiple `--query-receipt` arguments when combining the initial query with exact per-pair supplements. Missing pair/corner cases remain explicit until actual bound native evidence covers them. Exit 0 in check mode requires complete enumerated path timing and site mapping; even then it does not approve complete design timing, electrical settings, analog MTBF, reset exceptions, optical correction or hardware release.
