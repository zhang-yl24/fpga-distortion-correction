# AA follow-up research: AC metadata compaction and AD critical-prefix routing

Status: cloud-only preparation. Neither candidate has been compiled by PDS,
timed, bit-generated or board-tested. The released AA bitstream is unchanged.

## Exact baseline and purpose

Repository: zhang-yl24/fpga-distortion-correction.
Baseline commit: 87cf6ca466ba90d4d18c5d4d82ccd8b1820fde99.
Frozen delivery: delivery/20261107-camera1080p60-key1-aa.

- AC cache baseline SHA256: ff5e551c13083cecf9325b6acef0a00b58f7f1776cd7f5dbec341e52f2082088
- AC cache candidate SHA256: e2d641a61e20f375de0202528915e626dd3e7c43e8f40473d5308bd39cbd25e5
- AD RCF baseline SHA256: 3b39508ebfb7701e379fc53d980c7790f40ce397a2647cd36ce845c417a2b684
- AD RCF candidate SHA256: 5cb550036a03c995e85eb1227e84b250d6e7d715f2cee3516aabcc5483e40170

No rotation is added. Camera qualification, KEY1, parameter mapping, Gamma
configuration, bank ownership, frame publication, DDR protocol and all timing
constraints retain the AA contract. Gamma remains disabled in AA.

## First priority: AD, one added priority-route net

The published AA routed slow setup path is +0.003 ns. It traverses
debug_data [135] -> all_group_ca_dly -> adj_ba [16], with 5.706 ns
route delay of 6.349 ns total data delay (89.872 percent).
The current extra prefix priority names debug_data [273], not [135].
This observation does not make [273] wrong: its previous role must be preserved.
AD retains every original priority (both generated gate nets, common CA net,
and [273]) and adds only [135].

Use an independent copy of the AA placed database and the exact same
device/TOP/source/imports/seed/clocks/pins/exception constraints/hold settings.
Resolve [135] against that netlist before routing; stop on missing or ambiguous
objects. Run route and independent slow/fast setup, hold, recovery, removal,
pulse-width and skew checks. Compare actual worst paths and all failing counts,
including whether a new endpoint becomes critical. Do not relax clocks,
multicycle/hold or uncertainty. Do not infer an improvement from priority alone.
Retain AA routed database and bitstream as the comparison/rollback baseline.

No RTL simulation is needed for a priority-only comparison because RTL is
unchanged; all implementation timing checks still apply.

## Second priority: AC, remove redundant native query metadata

Actual AA hierarchy forwards a 24-bit raster tag plus one masking bit:
cache TAG_W=25, COMPACT_COORDS=1, HEAD_PREDECODE=1, QUERY_DEPTH=4096,
WIDTH=1920, HEIGHT=1080, INDEX_BITS=7, CACHE_ROW_STRIDE=2.

AA token width = 38 coordinate bits + 25 tag bits +
4 bounds + 28 line bits + 28 block bits + 1 crossing bit = 124.
AC token width = 38 + 25 + 4 + 28 = 95.
Logical storage reduction is 29*4096=118784 bits (14848 bytes, 14.5 KiB).
This is not a measured DRM/LUT reduction; RAM primitive granularity and
inference can change the physical result. There is no extra pipeline stage,
query-depth change or intended cycle/performance change.

For the bounded 2x2 footprint and this exact mapping, two valid neighbours
have identical full block ID iff they have identical line ID:
different rows have different parity, and adjacent 128-pixel blocks have
distinct local-line IDs. The lease unique-mask may therefore compare the
already-carried line IDs. Native foreground tag lookup already uses the
8-bit directory code derived from coordinates.
Generic geometries retain the original full block/crossing metadata path.
Native full head-block aliases remain diagnostic only; far-OOB raw diagnostic
block IDs may be canonicalized differently and are not a functional contract.

Cloud verification performed with the included pure-JS bounded model:
2,076,601 coordinate footprints (x=-1..1919, y=-1..1079),
12,429,602 valid-neighbour pair checks and matching token pack/unpack checks.
Arbitrary validity masks at block boundaries and walking full payload bits
are also checked. This is a mathematical model test, not execution of the
candidate RTL. The original AA resource/timing result does not transfer to AC.

Required next evidence before promotion:
1. Compile the exact AC module against the existing AA cache/store/FIFO bench.
2. Cycle-by-cycle A/B of visible accept/output pixels/tags, AR/R/fill events,
   fail/fault and lease lifetime with queue-full stalls, OOB footprints,
   x=127/128 and y boundaries, DDR backpressure, multiple generations,
   reset/abort and QID wrap cases. Compare only defined diagnostic signals.
3. Reuse the existing real camera/core/scanner full-frame test with changing
   input fingerprints and KEY1 RAW/CORR transitions. Bind each scanned frame
   to the expected source ID/mode/CRC and drain all leases.
4. Same-configuration Map: actual inferred FIFO width/depth, DRM count,
   LUT/FF/control sets and hierarchy. Stop if the intended token change is
   absent or if a new long decode/control path appears.
5. Only then place/route and independent full STA. No board claim until the
   teammate tests the specifically identified bitstream.

Do not combine AC and AD before each has an interpretable independent result.
Existing native six/sixty-frame model evidence is useful as a regression
target, not proof that either new candidate already passes it.

## Files and use

- d256_runtime_prefetch_cache_AC.sv: full independent source candidate.
- vendor-ca-debug-priority_AD.rcf: additive independent route candidate.
- prepare_candidate.py: strict SHA-gated exclusive-output copier; never
  overwrites an input, invokes PDS, accesses hardware or downloads anything.
- verify_native_head_model.js: run with Node.js; also executed in the cloud JS
  tool for this result. No npm or external library dependency.
- CLOUD_MODEL_RESULT.json: exact model result and baseline binding.
- SHA256SUMS.txt: source/tool/report checksums.

Example after placing this directory beside its distributed files:
python prepare_candidate.py ac path/to/AA/d256_runtime_prefetch_cache.sv path/to/new/AC_cache.sv
python prepare_candidate.py ad path/to/AA/vendor-ca-debug-priority.rcf path/to/new/AD.rcf

Use the outputs only in an isolated project copy and update its input manifest
before admission. Do not edit running/frozen build inputs or the published AA
native directory. No proprietary IP implementation or credentials are included.

## Latency and throughput boundary

AC has no intended latency reduction. AD has no intended frame-cycle change.
They address storage pressure and implementation margin first. AA's single-pixel
125 MHz architecture has only 9733.33 cycles above 2073600 pixels per 60 Hz
frame before all other overhead. Positive internal STA and a short behavioral
DDR trace do not prove sustained camera60. Keep capture/core/scan contention,
DDR stalls/refresh and fresh FrameID timing in acceptance; no new acceptance
threshold or fabricated board measurement is introduced.
