# Implementation-g real system regression

The complete 64×64 system passed two reset epochs with all user synchronizer
native-property overlays and the lane's registered return bundle. This follows
the implementation-f cache/writer/display/completion changes. System source
identity is `c7129183c94cc20a58bdc8466cf902e7a6826799fc4c314aa65f07e69add2ba9`.
Build ID is `11037003`; every overlay remained unchanged during simulation.

`physical-g-source-binding.json` verifies exact overlay source hashes against
the native physical-g snapshot, identity
`7a246494adf458b607d430b9ebc60c13420f7f859352edb82ad6211e0a20eb8b`.
Prepared identities differ because absolute include paths are relocated into
each work directory. The original C baseline remains unchanged.

The real mapper/cache/writer, three-slot capture DMA, read-return stage, shared
arbiters, asynchronous FIFOs and scanout ran at 125 MHz core and 148.5 MHz
input/output clocks. At 64×64, row padding uses its linear fallback and the
engine partitions 32/32 rows. Native row16 indexing and 640/440 partitioning
are covered by the separate 1920×1080 engine tests.

Both epochs passed every pixel, CRC, frame-ID and ownership check: 34 source
commits, 33 publications, 32 unique displays (12 raw and 20 corrected), five
repeat displays and 151,552 displayed pixels. Source/result writes and memory
contents were checked independently. Every source slot was reused at least
five times per epoch. AR/AW/W stalls, return gaps, shared read/write service,
capture/result arbitration, display/sample arbitration and active mode switches
all have nonzero coverage. Underflows and mismatches were zero.

Eight intentionally unreserved whole input frames per epoch exercised source
exhaustion; accepted malformed/drop counts were zero. The busy-reset case kept
DDR memory intact, changed input texture and restarted frame IDs before checking
recovery and final drain. Exact counters are in `system-report.json`.

The matching evidence directory contains the XSim commands/logs, source hashes,
per-epoch counters and complete build/interface inventory. Functional simulation
does not measure metastability margin or physical Gray-bus skew. The G native
FIFO synthesis/map/route audit supplies separate structural evidence; physical
delay/skew constraints and board stability retain separate acceptance criteria.
