# Isolated camera720 reset application and derived inspection

Only the following new implementation/test files were created; existing source, scope, receipts and PDS tools were not edited by this subtask:

- `tools/camera720_reset_apply.py`
- `tools/camera720_reset_inspect.py`
- `tests/test_camera720_reset_apply.py`
- `tests/test_camera720_reset_inspect.py`

CPU verification: `python -B -X utf8 -m pytest distortion/tests/test_camera720_reset_apply.py distortion/tests/test_camera720_reset_inspect.py -q --tb=short` passed **63 tests**. Negative cases cover unproved/overclaimed flags, old schemas, widened regexes, count/name changes, duplicate/unsafe pins, artifact mutation/reuse, changed logic/routes/file tables, arbitrary external files, missing wire-rule hashes and false native success.

The apply tool rederives the current reset report inventory, exact queries/FDC, graph proof and same-configuration vendor provenance. It binds the original build independently and then uses the current `camera720_derived_inspect.bind` to prove the measured-route descendant. The original failed raw-token route receipt is preserved; only the parent's tightly limited CDBENTRY ordering / empty FILEMAP proof may justify its derivative. The official wire rule is allowed only at the exact PG2L100H path under the same bound PDS installation and with its expected SHA-256.

Native apply (not executed by this subtask) copies the descendant to a fresh directory, initializes STA once, applies only exact proved `set_false_path` commands, saves/readbacks the ADF and emits a native route dump. There is no second STA, route mutation or bitstream operation. All routes and all non-constraint functional/placement tokens must remain unchanged; CDB/CDBENTRY deltas are recorded without approving their scope. Source FILETABLE bytes must stay identical during this reset step. A successful save is deliberately not timing or constraint-effect approval.

The separate reset inspector binds the entire apply chain and accepts only the new 720p reset application schema. Its `query`, `report` and `export` modes run read-only fresh-process diagnostics against the saved reset ADF. Export performs fresh STA and native placed-netlist export; report performs fresh STA and a native route dump. `bind_receipt(path, watched)` returns a **receipt dict**, updating `watched`; it does not return the original inspector's `(receipt, watched)` tuple. Final ten-type timing/exception effects, CDC/IO acceptance, optical acceptance and hardware release remain separate audits and are never inferred from either tool's execution success.

Every native mode has a 120–300 s configured deadline, hidden owned process, cleanup on timeout/unexpected stage, exact LF Tcl/dummy bytes and immutable evidence hashes. Normal parent exit is recorded without claiming independent descendant-liveness verification; callers may independently inspect process state as in the current root workflow.

Lifecycle code was adapted from `run_camera_vga_calibrated_physical.py` (SHA-256 `4712630982a8900d8669cb6e3f82daf68f7bdd20fec991a2918a230e8009a0c0`) and `run_camera_vga_calibrated_derived_inspect.py` (`6b50635b79b4ac29ff96514661e74279395c790feaa5668a53e2ede62e1c9b54`). Their historical inventories/approval decisions are not imported or reused.

Frozen new tools:

- Apply: `5a97a1481399d18156ede9765d4dbdfb86de059d5e5a7f598f9dd47bcf48e716`
- Inspect: `191e36dfb22ce077ff4ebb18f0d3ca766f5e4357d2ef1884dbf0067a0cabdfed`

Real evidence rebinding passed the original reset proof and latest measured-route binding. An initial integration attempt rejected the official external wire rule, which motivated the narrow path/hash fix and additional negative test above. The complete fresh CPU preparation then **passed** in 193.2 s, binding 435 inputs and deriving 5 exact commands / 127 source-target pairs. No PDS or hardware process was started by this subtask.

Prepared plan: `camera720-output/reset-save-ready-a/stage-plan.json`. Input is the measured-route ADF SHA-256 `2d7b577dc6bb0a42364f2e2bf6490d3003a5c8cbb4ebf21fd5057ce9b38c074e`; original proof/build ancestor is `420127079b4123b3942edd45c1f5b725221a4e3b3a1b8a91a448d9526e6d0cbe`. All timing/optical/physical/hardware approval fields remain false.

Next commands, for the root agent's separately coordinated native execution from repository root:

```powershell
.venv/Scripts/python.exe -B -X utf8 distortion/tools/camera720_reset_apply.py --stage-plan distortion/work/camera720-output/reset-save-ready-a/stage-plan.json --execute
```

Only after that clean application, prepare/run a separate export (it again fully rebinds every dependency):

```powershell
.venv/Scripts/python.exe -B -X utf8 distortion/tools/camera720_reset_inspect.py --source-receipt distortion/work/camera720-output/reset-save-ready-a/result.json --name reset-export-a --mode export --execute
```

These commands are not a release or a substitute for auditing the resulting fresh timing/exception effects. Complete large-file CPU rebinding happens before each native process starts and is separate from its 300 s native deadline.
