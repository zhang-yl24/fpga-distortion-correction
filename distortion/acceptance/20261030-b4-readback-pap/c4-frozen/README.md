# c4 event-bounded real-system b4 regression (not yet run)

This isolated bundle uses the actual CE system, input DMA, correction engine,
cache, writer, read/write arbiters, reader, async FIFO, scanner and unchanged b4.
The DDR user-port peer is self-owned behavioral memory inside the reused system
TB. There is NO engine completion peer in this source list and no vendor IP.

Run CPU/hash preparation with `python -B run_system.py`.
After explicit execution admission, run signed cloud Icarus with:

    python -B run_system.py --rtl --out work-real-system

Compile90s / simulation300s; preserve any failure, no automatic retry.
The new bench has not been compiled or simulated at packaging/preparation time.

Three32x32 unthrottled frames: same raw input, raw/corrected/raw modes, Gamma0.
Reuse the previously validated synthetic fixture verbatim; raw and corrected
differ at926 pixels. All3072 final scan pixels and original system assertions
must pass. No Penn video or new optical calibration is involved.

New tag is sampled at source commit and live input poisoned afterward. Actual
27MHz UART RX loads the session, actual TX bits are independently decoded.
Both frame1 raw and frame2 corrected packets must match immutable golden pixels,
RGB888 CRC, samples, mode, tag, epoch and identity. Finite telemetry buffering
may drop frame3 at this deliberately fast small raster; drop accounting must
match exactly and video must not be backpressured or lose frames.

The240000-cycle video budget is separated from the2.1ms command preamble and
event-bounded UART drain with the same60ms global watchdog. No DUT timing constant or target clock was shortened. Original
video successful summary alone cannot pass: new telemetry completion and Python
oracle are mandatory. A first-query assertion is carried from the validated
frame240 v3 TB: test stale reuse on accepted query, not a lawful pipeline wait.

This run does not repeat c1's reset or bank-peer tests and does not claim1080
throughput, physical UART/HDMI, DDR PHY, CDC/MTBF, or timing/hardware acceptance.
Upload/copy only manifest-listed files plus manifest.json; never runtime work
directories, __pycache__, or local provenance logs outside this folder.

## c3 correction after preserved c2 failure

c2 failed at first ROI: genuine scanner underflow0x02. Its legacy SMALL-only
collision fixture withheld display AR until a future cache request; real UART
preamble changed raster phase and that request could not arrive before ROI.
c3 does not rerun that phase-dependent injection as normal readback acceptance.
Both legacy forced AR/AW collision controls are disabled in this named normal
phase. Their positive coverage requirements are scoped to injection mode, and
zero injected hold/forced-collision counts are REQUIRED in normal mode.
Observed natural read/write contention is still reported but may be zero.
All periodic bus backpressure, real memory/engine/arbiter/FIFO paths and semantic
pixel/CRC/ownership/underflow/fault assertions remain. No DUT/oracle vector/clock/
timeout/UART change. This does NOT claim forced dual-client coverage in c3.
See C3_CHANGELOG.md for exact evidence and acceptance boundary.

## c4 superseding drain/runner status

See C4_CHANGELOG.md. c3 video passed in cloud but timed out before UART acceptance.
c4 preserves partial logs on timeout and requires complete independent wire packets,
all CDC/mailboxes/serializers idle for16 cycles per domain, then a full quiet byte.
No c4 HDL run has occurred. Host wall budget is explicit via --simulate-timeout;
default300 remains until an evidenced allowance is admitted.
