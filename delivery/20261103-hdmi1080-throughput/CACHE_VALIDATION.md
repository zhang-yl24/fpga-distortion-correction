# Cache packed-scatter candidate

The candidate preserves the frozen HDMI cache's module names, ports, query FIFO,
lookup refresh, frame ownership, counters and fault handling. It changes the two
parity RAMs from 16-bit words to 32-bit words, with half as many addresses. Each
word contains two pixels of the same parity. Original linear-pixel bit 1 selects
the half word and is registered with the synchronous-read metadata.

Each scatter cycle writes eight pixels through four 32-bit ports. One 128-pixel
line takes 16 scatter cycles, compared with 32 in the frozen implementation.
At INDEX_BITS=7 the logical pixel storage remains 32 KiB, plus the existing
256-byte DDR fill buffer. Isolated PDS synthesis results are recorded below;
integrated placement, routing and timing remain to be measured.

## Reproduce

From this package directory, with Vivado Simulator available:

```powershell
python -B tools/run_cache_regression.py --workdir _build/cache-check-01 --vivado-bin D:/Vicado/Vivado/2017.4/bin
```

The work directory must be new. The runner compiles the exact frozen cache and
candidate separately, runs both against the same independent pixel formula,
checks completion markers and simulator errors, and records source/log hashes.
It performs no hardware or PDS actions.

## Recorded validation

All four baseline/candidate directed/stream cases passed. The directed bench
checks every pixel position within a 128-pixel line, parity and half-word
selection, line boundaries, cache-tag conflict replacement, new and same-bank
frame invalidation, FIFO/output backpressure, pending-frame drain, reset at the
final scatter write, and bad RID/early or missing RLAST/unsolicited return faults.

The stream bench checks all four neighbour pixels, fractional coordinates and
25-bit tag for 2,073,600 queries over a full 1920x1080 raster. AR, returned data
and output have deterministic stalls; thousands of bursts return their first
beat on the address-handshake cycle. Results are checked against an independent
synthetic DDR image, including right and bottom boundary zeros.

| Isolated cache stream metric | Frozen | Candidate |
| --- | ---: | ---: |
| Queries checked | 2,073,600 | 2,073,600 |
| DDR line fills | 16,200 | 16,200 |
| Cache hits | 8,272,201 | 8,272,201 |
| Scatter cycles | 518,400 | 259,200 |
| Stream cycles through final output | 3,851,999 | 3,586,079 |

The isolated workload uses 265,920 fewer cycles (6.90%), corresponding to
2.12736 ms at 125 MHz. Differences beyond scatter cycles arise from the changed
alignment with deterministic stalls. This test excludes the mapper, writer,
capture/display contention, physical DDR and board timing. Use integrated-engine
results and new board telemetry to assess application throughput.

Recorded result and native logs: `evidence/cache/`. Candidate SHA256:
`712d285371ba812e5cd66966657b042817b6a1ca4d010fe00e60c47f953bf1b1`.

## Isolated PDS RAM inference

PDS 2025.2 build 211867 compiled and synthesized both cache versions at WIDTH=1920,
HEIGHT=1080, INDEX_BITS=7, TAG_W=25, TIMEOUT_BITS=26. The 25-bit cache tag matches
the actual sampler input: a 24-bit raster tag plus its geometry-mask bit.
Temporary source copies change only those parameter defaults and line endings;
the exact transformation and all source/report hashes are preserved under
`evidence/cache-synthesis/`.

| Isolated synthesis resource | Frozen | Candidate | Change |
| --- | ---: | ---: | ---: |
| LUT | 1,294 | 1,370 | +76 |
| FF | 1,021 | 1,086 | +65 |
| DRM36K equivalents | 10.5 | 10.5 | 0 |
| APM | 3 | 3 | 0 |

Both versions infer eight 36K block RAM primitives for the pixel arrays, plus
five 18K primitives for tag lookup. The candidate's two parity arrays are each
4096x32; each maps to four 36K primitives. This verifies that the wider scatter
does preserve block-RAM inference in isolated synthesis.

The resource probe used the tool's inferred 1000 ns clock without an FDC and
provides no timing acceptance. Candidate device mapping then rejected the 647
exposed internal module ports against 300 package pins. The actual board wraps
these internal buses; a full-board map and PNR must be assessed separately.
The native map failure is retained alongside the successful synthesis reports.
