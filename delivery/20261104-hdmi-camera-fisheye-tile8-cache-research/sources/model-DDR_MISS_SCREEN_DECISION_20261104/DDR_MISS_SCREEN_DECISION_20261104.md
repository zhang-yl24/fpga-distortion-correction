# INDEX8 slow-path scheduling screen

Prefer the decoded slow-address snapshot plus post-fill bulk-read experiment
over demand-prefetch in the current one-hour verification window. The exact
local state count saves 288,045 cycles, while one same-query demand descriptor
saves only 22,050–24,080 cycles in the explicit DDR scheduling models below.
These are source-trace/model results. No new board FPS or physical sign-off is
claimed, and the released INDEX8 source remains unchanged.

The primary artifact is `full-prototype-aligned-state-screen-c.json` (SHA256
`248a9672aa55fa0a0e8fb1eb97f3544f28bc5f04a93ac637b5aa6cee33f11548`).
It binds root's actual isolated bulk source `0d0f85ed…70b92` and decoded slow
source `f2c16c15…f9c1d2`. The prior a/b reports conservatively charged a
BULK_CHECK after every fill. They are retained and superseded: actual root RTL
routes neighbour3 directly from final write commit to LOAD, so those reports
overcharged 8,385 cycles.

The existing native 8x8 coordinate/block trace was originally generated in the
df9tp experiment directory. Its mapper/profile/order is independent of cache
capacity. The engine differs from the selected INDEX8 engine only in INDEX8→9.
This screen independently decoded all four block addresses from its Q8 values
and reproduced the current INDEX8 counts. It inherits no df9tp physical result.

| Full1920x1080 control quantity | Count |
| --- | ---: |
| Queries | 2,073,600 |
| All-hit fast queries | 2,038,895 |
| Slow queries | 34,705 |
| 256-byte fills | 37,483 |
| Valid-neighbour hit events | 7,416,463 |
| RAM write commits | 299,864 |

Every variant preserves those request/replacement/hit/query counts and final
cache tags. The state model does not independently prove new pixel arithmetic,
fault handling, epoch behavior, CDC, RAM mapping or physical timing.

| Scheduling variant | Local state cycles saved | Time at125MHz |266k screen |
| --- | ---: | ---: | --- |
| Actual bulk only, including n3 skip and failed checks |125,130 |1.001040ms | below |
| Snapshot SELECT removal and hit CHECK→PICK only |240,021 |1.920168ms | below |
| Snapshot plus actual bulk, overlapping work counted once |288,045 |2.304360ms | above by22,045 |

Snapshot eliminates 138,752 valid-neighbour SELECT edges and 101,269 hit LOAD
edges. OOB neighbours still consume one CHECK edge. Misses retain real final
commit followed by LOAD/PICK. Bulk can finish 26,320 slow queries: 6,105 after
neighbour0, 39 after neighbour1 and20,176 after neighbour2. In most cases only
one original neighbour remains, so bulk does not generally save8–12 cycles.
It pays29,098 checks, including2,778 failed checks. Bulk adds only48,024 cycles
beyond snapshot; adding the standalone improvements would double-count work.

The remaining8,385 slow queries last miss at neighbour3. Their actual RTL
bypasses BULK_CHECK. Within the native INDEX8 trace no four-neighbour tuple
contains same-index/different-tag aliasing, so that fallback must be verified
with synthetic collisions, not inferred from native coverage. The model's
synthetic tests cover this case and charge failed bulk checks correctly.

`full-lookahead-cycle-model-a.json` (SHA256
`ac0107570a5de8a46f4c61d4da8076b000411097078d210d6bd213c785cc685a`)
tests one alternative scheduling variable. After one fill has actually
committed, it can issue one known missing later neighbour of the same held
query. No next-query prediction, added capacity or second outstanding burst
is allowed. The current unsaved pixel indices are protected from replacement.
RAM reads stall on the modeled direct-fill write-commit edges; tag publication
waits for the actual last commit. It issues2,724 early known-demand requests
and preserves all original fill/query/read/publication counts.

| First-R latency assumption | Control service cycles | Demand-lookahead service cycles | Saved |
| --- | ---: | ---: | ---: |
|0 |3,231,189 |3,208,415 |22,774 |
|8 |3,532,027 |3,509,977 |22,050 |
|40 |4,730,912 |4,706,832 |24,080 |

Both sides use the same periodic AR-ready/R-hole rules. Latency0 needs5,807
read-port stall edges in the lookahead variant; latencies8 and40 need none.
The baseline latency0 service total differs from the saved normal-system
scan-active count by22 cycles, and latency40 differs from the saved first
sustained frame by13 cycles. This is a useful local calibration, not a proof
of steady-state arbitration: later sustained frames have much more physical
AR contention while HDMI reads compete. Mapper, writer drain, bank admission,
capture cadence and presentation are outside these service totals.

A demand-prefetch RTL implementation would still need a separate registered
fill-owner descriptor while selected pixel metadata advances, correct same-cycle
AR/first-R handling, RAM-port read replay, final-commit publication, conflict
protection and epoch/fault drain. It cannot hide a forty-cycle DDR wait behind
only a few remaining slow housekeeping cycles. Its measured model benefit is
too small to justify that complexity in this verification window.

The proposed one-hour gate is:

1. Keep original d473 cache and provider family frozen. Use root's independent
   prototype files and new output namespaces only.
2. Require the unchanged independent cache unit pixel/CRC oracle, INDEX3/7/8/9,
   warm64/63 II=1, stalled RESULT/payload stability, malformed RID/RLAST/timeout,
   reset and final-commit collision coverage to pass for the combined candidate.
3. Compare a full-system normal candidate against the already saved normal
   control, including all4,147,200 scanned pixels, corrected/raw CRCs, complete
   source/owner/drain, same37,483 corrected fills and299,864 real RAM commits.
   Require at least266,000 actual processing-cycle reduction as a screening
   gate; modeled288,045 has only22,045 cycles margin. Record any AR/write/scan
   contention differences. If the gate misses, stop before new native EDA.
4. If the functional/cycle gate passes, run the independent sustained contention
   gate before physical work. Then require fresh RAM mapping and all-ten STA;
   original+0.092ns setup margin cannot be inherited. The current snapshot RTL
   reads RAM unconditionally in CHECK, so tag-hit comparison does not gate its
   RAM CE, but placement and new mux fanout still need actual timing proof.
5. Even a processing gauge below33.333ms does not establish30 unique display
   FPS. Only a future complete bit/SRAM/receive-only short+600s measurement with
   bank/admission/unique-presented counters could establish a board result.

The independent local model suite passed47 cases in0.61s; its saved JUnit is
`miss-scheduling-model-tests-a.xml`. It covers collisions, OOB, last-neighbour
skip, nonoverlapping savings, deterministic random replacement and single-owner
lookahead at latency0/1/8/40 and multiple AR/R phases. No EDA, COM, alias,
published source or archive was modified by this screen.
