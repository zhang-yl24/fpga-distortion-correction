# 720p reset audit — 2026-11-01

Only CPU audit, preparation, and tests were executed by this agent. No PDS, programming, hardware, or git operation. Published VGA sources/helpers are unchanged.

## Files

- New tools/audit_camera720_reset.py: current build/receipt binding, complete dynamic ordinary DDR recovery inventory, exact unapplied pin query and scope proposal, current placed-netlist graph and vendor source proof. The current sensor/monitor cannot enter the DDR proposal. Full prove requires a clean exact-name query receipt plus export receipt; no constraints are applied by this tool.
- Changed new tools/audit_camera720_timing_inventory.py: recovery_record preserves PDS MaxDelay -datapath_only recovery paths, which omit both clock-edge rows. It stores unknown launch/capture clocks and edges as null, keeps PathGroup separately, and requires the exact exception syntax and source constraint line. It never fabricates clocks from the path group.
- New tests/test_camera720_recovery_parser.py: 6 tests passed.
- New tests/test_camera720_reset.py: 8 tests passed, including a complete synthetic two-check scope (not old 245), monitor summary/datapath failure rejection, unknown source rejection, exact native name matching, and header-only adaptation.
- Existing new tests/test_camera720_inspect.py: all 22 tests still passed after parser change.

## Actual build-b findings

ADF SHA256: 420127079b4123b3942edd45c1f5b725221a4e3b3a1b8a91a448d9526e6d0cbe.

The new report has 7,656 detailed recovery records: 3,824 ordinary records with clock edges and 3,832 MaxDelay datapath-only records without clock edges. 1,680 detail records belong to camera_configuration/monitor; none is failing. No summary recovery failures exist outside the classified DDR clock groups. Detailed top-N coverage is not universally proven merely by these counts.

Dynamic DDR scope reconstructed each corner from the current native report: 245 logical checks, 252 native capture-edge variants; slow failing 245, fast failing 229. Each native summary group total/WNS/TNS/failing count matches the reconstructed records. These counts were derived, not copied or asserted as historical constants. The proposed exact scope is five source FF clock pins and 127 unique source/target pairs (126 internal plus one entry RDC).

IMPORTANT: the two ordinary hold failures are camera_pclk -> camera_pclk, not the historical DDR data pair. Root owns the separate hold correction. DDR recovery scope cannot remove those data checks.

## Evidence prepared

- work/camera720-output/reset-scope-a/plan.json and recovery-inventory.json bind the actual export-a receipt/report and build-b. The exact native query body is query-body.tcl; proposed-scope.fdc remains unapplied and unapproved.
- work/camera720-output/reset-graph-preliminary-a.json: the actual export-a placed netlist passed existing strict DDR reset graph analysis through top-module-token-only adaptation. 126 internal primitive targets and the entry two-stage PLL-lock reset chain were proved. Native exact-name query and the final combined scope proof remain separate.
- work/camera720-output/reset-vendor-preliminary-a.json: all 75 current DDR IDF/expanded bodies rehashed byte-identical to vendor source. Existing vendor-reference.json is used only as a byte inventory; no historical approval is inherited and no global clock groups are imported.
- Root has prepared work/camera720-output/reset-query-a. This agent's duplicate preparation was rejected because that directory already existed, before any write or process launch.

## Complete after root runs the native query

Use audit_camera720_reset.prove with:

- scope-plan: work/camera720-output/reset-scope-a/plan.json
- query-receipt: work/camera720-output/reset-query-a/result.json
- export-receipt: work/camera720-output/export-a/result.json
- vendor-proof: results/camera-vga-reset-analysis-20261031-a/vendor-reference.json
- output-dir: work/camera720-output/reset-proof-a (fresh)

The function rebinds all native receipts/artifacts, rederives the current complete report inventory, proves exact pin names and netlist graph, rehashes the same-config vendor source, and saves proof.json. Even a passed scope proof does not apply exceptions or approve hardware. Root must independently derive any isolated application, verify no route/placement/unrelated constraint change, rerun STA and compare exact exception effects.

## Completed combined proof

Root executed the exact native query successfully. This agent then executed the CPU-only prove stage and obtained Status=pass, ScopeAuditPassed=true in work/camera720-output/reset-proof-a/proof.json. The proof binds this same build-b ADF, exact five source names and 127 source/target pairs, current export-a report, all 126 internal reset primitive targets plus the entry synchronizer graph, and all 75 same-configuration vendor files. Both corners have 245 logical checks and 252 native variants; slow failing245/fast229 were reconstructed completely.

TimingExceptionApproved=false, ConstraintsApplied=false, TimingAccepted=false, HardwareReleaseAllowed=false remain deliberate. This proof is a source for a later isolated application and exact effect audit, not an application or timing pass.

A complete receipt-bound ten-table inventory was also saved as work/camera720-output/reset-timing-inventory-a.json. It records 16 failing clock groups (14 DDR recovery groups, two camera hold groups), without hiding the monitor details or datapath-only checks.

## Additional root hold-route review

Read-only review of camera720_hold_route.py found the intended branch-only mutation, complete non-target route sibling comparison, semantic/placement comparison, unchanged CDB and original ADF hash binding present. Unused selected NE waypoint pins and the exact saved-route inclusion are checked. Fresh STA is still required and the tool does not claim timing or hardware pass.

One evidence issue was reported to root: derive() originally selected build-b/report_timing/camera720_transport_top.rtr and only hashed the file as currently observed. It should select the same-name report from the bound query receipt Artifacts (query-a contains it), and verify the receipt SHA, so hold/setup measurements and the route dump are both proven to originate from the same native ADF inspection. Root owns that file and any correction; this agent did not modify it.

Final scope/parser code and proof hashes:

- tools/audit_camera720_reset.py: 95fa24322eb4f81fc32ecc90434798d56145a41b5a4d0c8a5bc89114642807c6
- tools/audit_camera720_timing_inventory.py: ae9cee0bef28cc190c259cc611b9e6b4fdca99108a2534c3f03474fd303a3908
- tests/test_camera720_reset.py: 8450e0a2f3e4680caf25028283deb4d9ae1431f62d2441b079b9f6c2dabdbb3d
- tests/test_camera720_recovery_parser.py: 214d3dc10faa77ed8062749ea097ebd21b7a24c9c51cc7e033ca6aecb8b4ea0c
- work/camera720-output/reset-scope-a/plan.json: 56a31e9c162beed8aa84bb48c447da37c2644e73192f2be63248a6ed7d80bc2e
- work/camera720-output/reset-proof-a/proof.json: 77e452031c0fc5fd45d379c8a041e94b0b723a90b712b4cf75992212d9b80f5d
- work/camera720-output/reset-timing-inventory-a.json: ae19253de2a80dcd7bad89b255c73986ab61f7e35adb1b2f838b1f58e328eddf
