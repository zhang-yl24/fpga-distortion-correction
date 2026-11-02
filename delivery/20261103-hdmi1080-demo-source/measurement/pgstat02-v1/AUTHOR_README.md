# PGSTAT02 morning measurement client and report

This is the isolated v1 host correction. The original v0 tree, ZIP, Library
version0 and old16-test results remain preserved. `reference/v0-results/`
contains the old results; `work/V0_PRESERVATION.json` binds their original ZIP.
These changes fix report validation defects found with synthetic counterexamples;
they are not observations of a board malfunction.

The v1 checks add three source-bound guarantees:

- A no-wrap-proved native process sample must take at least2073600 edges.
  A small legacy residue without a no-wrap proof remains unproven and excluded
  from absolute time; it is not mislabeled as an8ns frame or automatically
  rejected as impossible.
- In a healthy common-reset epoch, `(captured-processed) mod2^32` equals the
  instantaneous processing bit0/1. Across a window, integer `delta_captured-
  delta_processed` equals `processing2-processing1`, including-1 when one old
  active frame and a new frame finish after only one new acceptance. Granted
  capture rejects and no-grant windows never enter this identity. The number
  of completions is also bounded by `floor(delta_tick/2073600)+1`, allowing a
  frame already active before the window.
- LIVE metadata must match loaded-bit SHA, epoch/reset, boundary and input
  attestation, plus SHA256 of the exact manifest/plan/attestation file bytes.
  The CLI reads each file once and uses those bytes for both parse and digest.
  Even whitespace-only file edits after capture are rejected. Do not overwrite
  the three captured input files; preserve later notes separately.

Direct Python callers analyzing LIVE logs must additionally pass
`input_file_bytes={"manifest":bytes,"plan":bytes,"run_attestation":bytes}`.
The report parses those byte objects again, checks that they equal its parsed
arguments, then compares their exact file hashes to capture metadata. It does
not hash a canonical JSON redump or trust hashes merely copied from metadata.
CLI arguments are unchanged.

`reference/v1-semantics-rtl/` contains exact audit-only copies including the
actual grant-fix DMA SHA8e27e93d... from this archive. No RTL or RX is changed,
compiled or selected. `work/V1_SEMANTICS_REVIEW.json` gives reset, drop, duration
and counter proofs. The added invariants describe this single-engine native
profile; a future architecture must re-establish its contract before reuse.

This package adds a capture client and strict report around the archived
`stats_protocol.py`, `pure_window.py` and normal B4 helper. Those originals
are copied byte-for-byte; no wire protocol or RTL is changed. All work here
uses synthetic offline fixtures. No COM/JTAG, board, EDA or installation.

## Actual build binding

Read `reference/MEASUREMENT_RUN.md` and the build manifest first. The archived
diagnostic bit is SHA256
`57044fe803d9880f016b53c91234def946bb13da6cc1d357cd15689a5212a374`,
fixed correction1/Gamma0, PARAM_ID `e5ccceb0`, native1920x1080, PGSTAT02,
without PGFRAME. It retains the verified PC30 input profile and original
writer/cache. It is not the later D256/coordinate-compression/60Hz build.
The source archive records remaining setup violations and no board acceptance.
This host tool adds no timing or physical acceptance.

`work/BIT_IDENTITY_CHECK.json` is an offline file-SHA check, not a load receipt.
Before live use, main must load the intended bit using its existing board
workflow and record what is actually running. A later bit needs its own
source-bound fixed-mode manifest and real load evidence. Merely editing a
SHA string does not establish that identity.

## Reproduce offline checks now

```text
python run_offline_checks.py
```

This runs only memory transports and synthetic serialized ACK/PGSIG/PGSTAT
packets. `work/OFFLINE_RESULT.json` and `SYNTHETIC_EXAMPLE_REPORT.json` are
explicitly synthetic. Their sample rates/latencies are not hardware results.
No serial library is required for offline checks or report generation.

## Morning execution, by main after hardware connection

Copy `RUN_ATTESTATION_TEMPLATE.json` into a new run directory and fill the
actual load-receipt evidence, input description and uninterrupted reset epoch.
Describe whether the source is PC or camera, its observed interface/mode and
the evidence used. The existing Penn calibration does not establish that the
new camera lens is calibrated.

The packet-boundary byte offset must come from main's known receive/transmit
state. The client does not infer it from a quiet gap, request ACK timing or a
global magic search. Unknown bytes before that boundary are retained; complete
old packets after it can be strictly walked to the matching ARMED ACK.
An unknown starting boundary is a missing measurement prerequisite; capture
or preserve raw data, establish the boundary, and do not declare validation.

The collector is the only live command below. It does not program/reset the
board, scan ports, purge the input buffer or retry uncertain writes. Pass the
port verified by main's existing workflow; `COMx` is a placeholder.

```text
python host/collect_measurement.py --port COMx --baud 115200 --plan reference/canonical-requests/PLAN.json --manifest reference/MEASUREMENT_BUILD_MANIFEST.json --run-attestation RUN_ATTESTATION.json --output-dir runs/morning-capture
python host/measurement_report.py --wire runs/morning-capture/uart.raw.bin --manifest reference/MEASUREMENT_BUILD_MANIFEST.json --plan reference/canonical-requests/PLAN.json --run-attestation RUN_ATTESTATION.json --capture-meta runs/morning-capture/capturemeta.json --output runs/morning-report.json
```

Run the report after successful collection before quoting results. The client
saves raw chunks before parsing and logs exact request bytes/SHA, write intents,
uncertain writes, packet offsets and host scheduling provenance. Capture
completion means the requested packets arrived; the report separately verifies
counter continuity and computes rates/latencies. On errors raw data remains.

The exact existing three commands are preserved: SGA1 ticket1,
nonce20261103hex, then SGT1 ticket2/nonce20261104hex and ticket3/nonce20261105hex.
Require the matching ARMED ACK and complete mode1/PARAM_ID-matching PGSIG before
the first SGT. Wait about20 host seconds only to schedule the final SGT.
Both actual snapshot ticks determine the measurement window. Source-checked
request bytes are pinned by SHA; arbitrary requests are not substituted.

The original broadcast RX parser limitation remains. New generic routing was
excluded after its HDL validation was denied in the main workflow. This client
uses only the existing exact prechecked commands; no spacing trick is presented
as a protocol repair. RPC timeouts and the conservative34.36-second window
guard are capture/counter-integrity limits, not new thermal/board-run limits.

## What the report validates

The parser never resynchronizes after an error. It validates packet CRC and
schema/version, exact SGT ticket/nonce, SGA session/ARMED status, native complete
PGSIG mode/parameter, manifest clock125MHz, snapshot sequence and all adjacent
counter windows. A raw-SHA or recorded ACK-boundary mismatch is rejected.
The final complete PGSTAT boundary is recorded; a partial next packet from the
same already-saved read chunk is retained as a tail, not silently discarded or
misreported as corruption of the selected window.

PGSTAT02 contains no boot identifier. A request nonce and PGSIG scan epoch are
not reset epochs. Real load/reset/input evidence remains external; counter
consistency checks can reject problems but cannot prove an unseen reset never
occurred. Reported time uses the build's nominal clock, not UART receive time.

| Quantity | Calculation and meaning |
|---|---|
| Core interval | Full64-bit `tick2-tick1`; no+1 |
| New pure-correction rate | Modulo32 processed delta / nominal core interval |
| New presented rate | Modulo32 presented delta / interval; new ID successful display closure |
| Repeat rate | Modulo32 repeat delta / interval |
| Successful nonblank repeat fraction | repeat/(new presented+repeat); None if denominator0 |
| Accepted source descriptors | Wire `captured_frames` delta; not all camera arrivals |
| DMA rejects | Granted capture completion rejects only; no-grant/overflow detail is omitted |
| Last internal processing sample | `raw last-index+1`, only absolute when32-bit no-wrap is proved |

The full64 tick supports its low32 carry. Current conservative windows are
positive and shorter than2^32 core cycles, approximately34.36seconds at125MHz.
Event counters and request sequence support modulo32 carry under this bound;
sequence must advance exactly1 for this exclusive client. Full64 decrease is
rejected. Source frame-ID descent/wrap is rejected because this display profile
uses an unsigned new-ID comparison, rather than a wrap-aware comparison.

The legacy cycle word has no overflow flag. Absolute `raw+1` is allowed when
the snapshot's since-reset core tick is below2^32 and bounds the duration, or
when at least two serial-engine completions occurred within a shorter-than2^32
tick interval, proving the last frame started and finished inside it. Otherwise
the raw value and raw+1 candidate are retained and excluded from absolute-time
statistics. `work/COUNTER_SEMANTICS_REVIEW.json` gives exact source/line evidence,
including same-edge completion count/tuple updates and the125MHz clock chain.

## Sampling and external E2E boundary

The exact current plan supplies at most two last-completion endpoint samples.
The report gives their count, min/median/mean/range and nearest-rank percentiles,
with wrap-proof status. This is a sparse sampled distribution, not all frames,
not a tail-latency guarantee and not stage-wait timing. The first endpoint's
completion may predate the throughput window; it is excluded from the window
coverage numerator. More sampling needs an additionally source-checked request
plan; this package does not silently broaden the three-command RX claim.

PGSTAT02 does not export no-grant/no_free losses, all scan events or stage
timestamps. Do not infer total camera drop rate, camera arrival fps, overall
refresh rate or wait-stage histograms from it. `captured+dropped` is not total
input frames. FPGA PixelCRC and eight samples are not an independent full-image
correctness/calibration oracle.

`external_E2E` stays UNMEASURED. Source descriptor acceptance to successful bank
completion excludes exposure, HDMI receiver/capture before acceptance and output
scan/monitor after completion. Actual camera-to-display E2E requires the separate
physical common-timebase observation. UART wall time and simulation time cannot
substitute for it; this package does not claim corrected60fps.
