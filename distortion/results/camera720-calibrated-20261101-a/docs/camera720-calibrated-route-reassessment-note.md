# Exact route serialization reassessment

The original native save completed with exit 0, but its strict CPU comparator rejected a source file table change. The unchanged original receipt remains `physical-route-a/result.json`, SHA256 `f5c7a2e4df273a54a8bd72682153eb51578ac0d9e4df016a8180c0fed42cb489`, with `ExecutionPassed=false`. The saved ADF is `826441df556ae5e4e1541b2a5efa55e420f80abaade153fb91bfa0355fec55c4`.

Independent actual CPU reassessment completed in `camera720-calibrated/route-reassessment-a.json`, SHA256 `4c66c5b7330f617d6e68ce85b169f28ed5e7bdf1f8658224886b375e67ffa6c9`. It binds 378 exact input hashes. The original native receipt, original tools and original stage were not edited or rerun.

Full route and token comparison found:

- All 35,046 nets remain present; only the requested `_N177` terminal route changed, with the exact requested contiguous wire pair. Its logical connections and leaf are unchanged.
- All 48 CDB definitions and all 37 complete references under the same 20 parent objects are unchanged. Their source location fields are retained and compared as part of the full entries.
- The only FILETABLE change is `(FILETABLE (FILEMAP 2 ""))` to `(FILETABLE)`: deletion of one empty filename entry.
- Outside CDB entries, native save removed 20,836 numeric FILEID fields and 20,836 numeric LINENUM fields. No other source metadata payload is allowed by the new disposition.
- All remaining nonroute semantic tokens match SHA256 `07ec5041ffed3acfab9d37bf6add52bafee43eedca204d2efc60ce8892aaf197`. No logical, placement or constraint change is allowed by this metadata disposition.

The new `camera720_calibrated_route_reassessment.py` SHA256 is `e9e09cfcbd2be3f1619b21b35385fc99713265d7f75bc8bdd3b7e197768d3bf8`. Its first audit reconstructed the complete source recipe and native route/CDB evidence. Later boundaries require the exact audit producer, explicit source receipt SHA, original failed receipt identity, all original native artifacts, complete input closure and candidate hashes. They rehash those bytes without repeating the expensive semantic parser. The new result explicitly retains `SourceExecutionPassed=false` and separately reports `ReassessmentPassed=true`.

New read-only inspector: `camera720_calibrated_reassessed_inspect.py`, SHA256 `0b8e2435912afa34ef3f199fc9dd906cd3f73c95dca46a4a76b3cdb72046e915`, schema `camera720-calibrated-reassessed-inspection-v1`. The inspector requires an explicit 64-hex source SHA and accepts this reassessment or the exact new reset application provider. API remains `bind_receipt(path) -> (result, watched)`.

Actual CPU-prepared fresh native stages, 380 hashes each and 300-second native limits:

- `physical-report-a/stage-plan.json`: SHA256 `56a7928adfc428c2cb796452c381b72a40dd1b869d06745437052db30f518d49`.
- `physical-export-a/stage-plan.json`: SHA256 `01119200de00e7a69e1acdd3c914fcdd23c69c0cd67eb6f376a3d68345c2c9b4`.

The reviewer ran no PDS or hardware operations. Focused CPU tests: 17 passed and 25 subtests passed. The metadata tests reject real filenames, unexpected payloads, partial removals, unrelated native failures and use of the original failed schema as a new accepted source. Fresh STA and functional export remain necessary; this reassessment does not claim timing, bitstream, optical or hardware acceptance.
