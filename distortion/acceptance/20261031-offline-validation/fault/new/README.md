# Real-system underflow / common reset / fresh-session recovery

Prepared lightweight cloud test, HDL NOT_RUN. No DUT change, device action or physical DDR claim.

This is one32x32 corrected-frame fault followed by one32x32 corrected-frame recovery. The same37 source/header bytes as final Git delivery are preserved. Real geometry engine/cache/writers/arbiters/input DMA/display reader/FIFO/scanner and bit-level UART remain; DDR UI is the self-owned behavioral model. Vectors are the existing independently generated synthetic c4 fixture, not DUT-derived pixels.

The test stalls only the first display AR, checks active accepted lease and pending/unarmed session before first pixel, then requires one actual scanner underflow0x02/bad done with zero consumed pixels and no good presentation or successful bank release. Top-level summary code need not equal0x02. It requires black RGB and no valid pixels/metadata after fault while HS/VS/DE continue raster timing. A pending ARM must yield ABORTED0x14/epoch0 ACK; this is deliberately not a claim about an already-activated session or old in-flight signature.

The entire old ACK must drain before common reset, with the old bad lease/held AR quarantined rather than normally released. The new nonce/ticket/tag must produce exactly1024 corrected pixels, independent CRC and samples, one ARMED ACK and one signature. Physical UART byte decoding is the final evidence. The unchanged real host AcquisitionGuard/decoder/oracle are included for CPU rejection checks and independent final replay. No camera/Penn/vendor files are included.

CPU-only (portable Python stdlib):

```sh
python3 -B test_cpu_contract.py
python3 -B run_fault.py --out unused
```

Only after native1080 releases its cloud slot and a reviewer admits this package:

```sh
python3 -B run_fault.py --rtl --out /workspace/fault-recovery-a --admitted-seconds 900
```

The runner accepts a fresh workspace output, not tmpfs, and refuses Windows HDL execution. Compile90s; simulate at most900s; actual125MHz core,74.25MHz pixel,27MHz control,UART divisor234. The reused cleanup helper applies childRLIMIT_AS6GiB, own-groupRSS5GiB and available-memory1.5GiB stop thresholds, birth-identity checks and bounded TERM/KILL group cleanup. stdout/stderr, progress and partial files persist on failure/timeout. `result.json` becomes PASS only after the independent oracle; timeout/environment loss stays incomplete.

Expected wire stream176bytes: old ABORTED24, new ARMED24, new signature128. Wire TX15.253ms; two real RX commands4.167ms plus real processing/reset/drain. Planning500-630s from c4's measured25.10 wallseconds/sim-ms;35ms simulation watchdog and900s wallbudget are explicit independent caps, not a guarantee. Small arrays use the old32x32 fixture, but simulator object overhead is measured under the RSS guard. A full-raster black interval and full-byte idle window are required, not fixed long UART sleep.

The3-frame normal A/B/A assertions are not claimed here. Its source/result/bus/layout/ownership/pixel/CRC guards are reused, with a scoped expected fault instead of broad phase-1 error acceptance. This case does not cover actual calibration loss (no calib_done input), native1080 failure, mid-packet reset, old already-buffered signature revocation, physical IO or CDC MTBF. No hardware release.
