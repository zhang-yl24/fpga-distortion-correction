# U camera delivery review package

Status: READY_FOR_ROOT_REVIEW. The root execution thread has reclaimed the publication action and reports direct receipt of the user's destination authorization. root_publish_go is true for local handoff preparation; remote_review_pending remains true. Only root will perform the original-channel formal review and any remote write. Prior WITHHELD_AUTHORIZATION and the destination-authorization denial remain in RELEASE_BINDING.json authorization_audit. This preparation does not claim that remote review, publication or remote-file verification succeeded. The name camera60 identifies the development target; it does not establish 60 fresh frames/s. U has not been tested with the colleague's camera. RAW full-raster simulation and CORR short tests do not establish system throughput.

**This source package is not self-contained for rebuilding the FPGA.** It requires a lawful native dependency copy and matching local constraints; see BUILD_BOUNDARY.md. Identical bit-byte reconstruction is not promised.

The actual candidate bit is `bits/camera60-key1-unified-20261104-a.sbit`, 3,791,112 bytes, SHA256 `4ed2cbf1100f90ebe5301aa20a95bcd2bea4e0f9da4a56d761a4fc0cb27312aa`. STA_SUMMARY.json contains all twelve actual aggregate checks and the explicit vendor-model boundary. The original 26,500,862-byte RTR is retained locally, not published; this package does not publish a complete original RTR. External IO/reset and physical CDC remain outside full signoff.

The sole intended real source is the colleague's 1080p camera over HDMI. KEY1 selects RAW or corrected presentation at a frame boundary. RAW uses Gamma off. Correction and adaptive Gamma use the candidate's frame-latched settings; a button request alone does not prove the active frame mode.

`src/` contains four firstparty files only. SOURCE_EXPORT.json separates original source hashes from exported hashes. The top's three absolute includes are replaced by native-relative includes; the export is therefore not byte-identical to the implementation input. Other exports are byte-exact. Original build inputs remain unchanged.

Review BUILD_BOUNDARY.md before attempting reconstruction, OPERATIONS.md before a supervised camera test, and ROLLBACK.md before any load. RELEASE_BINDING.json binds the actual bit and final STA aggregate. Publication identity is the Git commit in the publication receipt. The model boundary remains explicit.

Run `python -B tools/verify_review_package.py` for an offline package integrity check. It does not build, program, open serial ports or contact the network.

Rollback identity is now recorded: a266 was locally hash/size verified; peer15 requires the colleague-held file to match its recorded SHA256 before testing. See ROLLBACK.md for evidence limits and protocol differences.
