# Current progress and evidence boundaries

This external status supersedes packaging-time NOT_RUN text only for the c4 cloud
run described below. Frozen package contents and historical claims are unedited.
Evidence is the parent's cloud-worker completion report; raw run/audit hashes are
still being sealed by that worker and have not been independently read here.

| Item | Actual evidence | Remaining limit |
|---|---|---|
| c1 integration seams | Cloud PASS: 512 pixels / 304 UART pin bytes, reset and bank metadata | Completion peer in focused bank test, not full engine |
| c2 real system | FAIL retained: first ROI underflow during TB forced AR hold | Not normalized into success |
| c3 real system | Video 3 frames/3072 pixels passed; full UART test INCOMPLETE after 300s | No final wire/footer/oracle acceptance |
| c4 real system | Compile/vvp exit0, independent final oracle PASS; 667.003s within admitted 900s; event end 26.575543ms | 32x32 synthetic A/B/A, identity rotation, Gamma off |
| c4 video | 3072 real engine/scanner pixels, 3 frames, no video drop/underflow | DDR UI behavioral memory; not physical DDR training/traffic |
| c4 UART | 280 actual pin-decoded bytes, ACK1, signatures frames1/2 including corrected pixels; telemetry drop1 accounted | Signature/sample protocol, not complete image upload; no board pins tested |
| c4 drain | Both-domain stability, empty CDC/queues and complete UART-byte quiet guard PASS | No analog metastability/MTBF proof |
| Contention | Natural read/write contention0; forced collision NOT_RUN | Do not claim collision coverage from periodic ready stalls |
| Integrated board | Existing PDS2025.2 real-IP Compile PASS, no new run | No matching synth/map/PNR/STA for b4 integration |
| Hardware | HardwareReleaseAllowed=false | UART pin assignment/BASE V1.4 IO and physical timing remain unresolved |

## Shortest next engineering path (plan only)

1. Attach the cloud worker's sealed compile/simulation/oracle result hashes and
   exact tool version to this external receipt. Do not rerun the passed c4 test.
2. Freeze the already compiled b4 board candidate closure, then request one
   synthesis/resource-map admission to check sampler/packet storage and real
   two-stage CDC preservation. Do not silently proceed to PNR: the normal-flow
   precise-object/constraint entry issue remains open. Keep vendor/IP local.
3. Before any routed implementation acceptance, resolve supported exact CDC
   constraint/object binding, preserve internal stage and reset checks, then run
   a single admitted same-map-PCF physical diagnosis. Neither the old CE timing
   pass nor c4 simulation transfers to this new integrated board candidate.
4. Plan one affected native1080 readback regression with independent expected
   coordinates/CRC/samples and normal 1080 frame cadence. Reuse the existing
   native harness, avoid a full new eight-frame run without a coverage reason.
   c4 closes the real computation/readback connection, not native1080 scale.
5. Hardware remains a separate specific authorization: PC HDMI input plus UART
   signature/sample readback, no display monitor prerequisite. Verify V1.4 pin
   mapping/electrical constraints and safe reset/stop/recovery procedure first.
   Do not infer a physical HDMI output picture from internal digital signatures.

No new tool run, engineering modification, Git action or hardware operation is
authorized by this handoff update.
