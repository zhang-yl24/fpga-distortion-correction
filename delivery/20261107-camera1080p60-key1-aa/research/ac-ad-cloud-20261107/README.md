# AA follow-up research: configuration correction, AE and AD

Research only. No candidate in this directory has been compiled by PDS,
timed, bit-generated or board-tested. Released AA sources and bitstream remain
unchanged.

## Correction: AA is HEAD0, not HEAD1

The previous revision incorrectly described AA as HEAD_PREDECODE=1 and
attributed a 124 -> 95 bit FIFO reduction to AA. That attribution is retracted.

At baseline commit 87cf6ca466ba90d4d18c5d4d82ccd8b1820fde99:
- board1080_cfg100_top.v line 9 defaults RATIONAL_BROWN_PROFILE=1.
- line 214 passes CACHE_HEAD_PREDECODE(RATIONAL_BROWN_PROFILE ? 0:1).
- System -> bank -> engine -> core -> sampler pass that parameter onward.
- The sampler explicitly uses COMPACT_COORDS=1.
- Core's 24-bit raster tag is forwarded with one masking bit, giving cache TAG_W=25.
- Therefore actual AA query FIFO width is 38 coordinate + 25 tag = 63 bits.
- AC does not reduce that actual AA FIFO width or storage at all.

Read-only inspection also checked the original local MAP_PREPARED.tcl and
PDS-generated runs/map-a/impl.tcl. Neither contains a parameter override
changing this configuration. Their exact SHA256 values and source lines are
recorded in AA_HEAD_CONFIGURATION_AUDIT.json. No local EDA job was started.
This is source/controller evidence, not a new netlist-parameter dump.

The original AC file is retained as explicitly conditional research:
only a hypothetical HEAD1 native build has 124 -> 95 token bits and
29*4096=118784 bits less logical FIFO payload. That is neither an actual AA
saving nor a measured DRM result. Do not enable HEAD1 just to claim this number.

## Priority 1: AD route candidate, actual AA timing path

Published AA slow setup slack is +0.003 ns on a path through
debug_data [135] -> all_group_ca_dly -> adj_ba [16].
Route is 5.706 ns of 6.349 ns data delay (89.872 percent).
The existing additional prefix priority names [273], not [135].
This does not make [273] wrong; AD preserves it and every generated gate/common
CA priority, adding only [135]. Route preference is not a timing guarantee.

Use an independent copy of AA's exact placed database and unchanged
device/TOP/parameters/RTL/seed/clocks/pins/exception constraints/hold settings.
Verify the added net resolves unambiguously before route. Compare all slow/fast
setup, hold, recovery, removal, pulse-width and skew checks, endpoint counts,
worst paths and resources against AA. Keep the original routed database.
Never relax timing constraints or bypass hold repair to improve setup.
No new RTL regression is required for this priority-only comparison.

## Priority 2: AE, isolate the useful HEAD0 native decode change

AE changes exactly one comparison expression in the exact AA cache:
native head_unique compares head_line[h]==head_line[z] instead of full
head_block[h]==head_block[z]. Generic geometries keep the original equality.
No FIFO field/width/depth, pipeline stage, interface, scheduling or delay
is changed. Both AA and AE retain HEAD_PREDECODE=0 and 63-bit FIFO tokens.

For a bounded 2x2 footprint under WIDTH=1920, HEIGHT=1080, INDEX_BITS=7,
CACHE_ROW_STRIDE=2, full block equality is equivalent to line equality.
The two adjacent source rows differ in parity. Within one row, equal
128-pixel blocks give equal line; crossing one block increments the local
line index and cannot alias it. Validity masks exclude unsupported neighbours.

In actual HEAD0 AA, full foreground head_block and next_head_block are
computed only for native duplicate detection (other native tag lookups use
coordinate-derived directory codes). After AE, those full block aliases are
diagnostic-only and can be eliminated by synthesis. This targets arithmetic
and foreground block-register pressure; it does not target query FIFO capacity.
Up to four 14-bit full block registers become functionally unused, but existing
compiler optimization may already eliminate some logic. No LUT/FF/DRM saving,
cycle improvement or timing improvement is claimed before matched Map/STA.

The included bounded model ran 2,076,601 footprints and 12,429,602 valid pair
comparisons, including all useful partial borders. It also checks arbitrary
validity masks at block boundaries. These head_unique results apply to both
HEAD0 and HEAD1. Token pack tests in the same file exercise hypothetical
HEAD1 compaction only; they are not evidence that AA elaborates HEAD1.
This remains a mathematical model, not execution of AE/AC RTL.

Required AE evidence:
1. Compile AA and AE with the actual HEAD0 configuration and unchanged
   cache/store/FIFO dependencies.
2. Compare visible acceptance, pixels/tags, DDR/fill events and fault/lease
   behavior cycle-by-cycle under full-queue stalls, x=127/128 and row borders,
   OOB footprints, backpressure, multi-generation traffic, reset/abort and QID wrap.
   Undefined diagnostic aliases are not an output contract.
3. Same-configuration Map must explicitly report HEAD0 and FIFO63, source hashes,
   hierarchy LUT/FF/control sets and inferred RAM. Inspect whether the native
   head block arithmetic/register cone disappears and whether path timing worsens.
4. Reuse continuous camera/core/scanner frame fingerprints and KEY1 transitions;
   bind each scan to source ID/mode/CRC and drain all leases.
5. Only a worthwhile Map result proceeds to physical implementation and independent
   full STA. No board promotion without exact identified candidate verification.

Keep AD and AE independent until each has an interpretable result. The released
AA six/sixty-frame behavioral model evidence does not transfer automatically.

## Files and exact identities

Baseline frozen directory: delivery/20261107-camera1080p60-key1-aa.

- AA cache SHA256: ff5e551c13083cecf9325b6acef0a00b58f7f1776cd7f5dbec341e52f2082088
- AE cache SHA256: 7a34f75eca6cd8e7eb74ab1adf347572431e26bb8c820b8d2e0032fcc38fed19
- Conditional AC cache SHA256: e2d641a61e20f375de0202528915e626dd3e7c43e8f40473d5308bd39cbd25e5
- AA RCF SHA256: 3b39508ebfb7701e379fc53d980c7790f40ce397a2647cd36ce845c417a2b684
- AD RCF SHA256: 5cb550036a03c995e85eb1227e84b250d6e7d715f2cee3516aabcc5483e40170

prepare_candidate.py accepts ae/ac/ad, verifies exact input and candidate hashes,
and writes an exclusive new output file. It cannot overwrite frozen inputs,
invoke PDS or access hardware/network. Insert output only into an isolated
project copy with a new input manifest. No proprietary implementation, license,
credential or private absolute path is included.

verify_native_head_model.js runs with Node.js without npm dependencies; its
bounded checks were also executed with the cloud JS tool.
CLOUD_MODEL_RESULT.json distinguishes actual HEAD0 widths from hypothetical HEAD1.
AA_HEAD_CONFIGURATION_AUDIT.json records the correction and checked evidence.
SHA256SUMS.txt binds all files except itself.

## Functional and performance boundaries

Camera1080p60, KEY1 RAW/CORR and the fixed Brown profile remain the targets.
No rotation is added. Gamma stays OFF, matching actual AA.
Neither AD nor AE intentionally changes latency or pixel cycles. Actual sustained
fresh60 requires measured capture/core/scan contention, DDR service and frame-ID
evidence; internal STA or a bounded model is not that measurement.
At 125 MHz, only 9733.33 cycles separate 2073600 one-pixel cycles from the 60 Hz
budget before all overhead. Preserve protocol/fault and full-frame bank safety.
