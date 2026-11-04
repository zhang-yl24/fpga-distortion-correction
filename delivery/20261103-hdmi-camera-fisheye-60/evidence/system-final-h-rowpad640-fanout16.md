# Implementation-h real system regression

The complete 64×64 system passed both reset epochs with the H frozen cache
index head/tail registers, writer private payload prefetch, all user CDC
attributes and lane return bundle. Build ID is `11037003`; system identity is
`a78f26b0a3008ba72471f8429042929a2ce9bad6b21815a77cf72d2ef89ac6a8`.
No overlay changed during simulation.

`physical-h-source-binding.json` binds the native physical-h identity
`fe756ccb51cbbf1ea30a337eec0c22d5419fd4cdb5cd34dad2097bcde880e44d`:
all original overlay hashes match, and all 116 prepared files match after
normalizing only the absolute compiled-root prefix. Of these, 111 match byte
for byte and five contain relocated include paths. Each file also matches its
own manifest hash. Build/profile/cache/clock settings agree. The build inventory
contains no missing or duplicated entries, missing overlay entries or source
drift.

The real mapper/cache/writer, three-slot capture DMA, return register, shared
arbiters, asynchronous FIFOs and scanout ran with core 125 MHz and input/output
148.5 MHz. At 64×64, the cache uses linear fallback and the engine partitions
32/32 rows. Native row16 indexing and the 640/440 partition belong to the
separate complete 1920×1080 engine verification.

Two epochs produced 34 source commits, 33 publications and 32 unique displayed
frames (12 raw, 20 corrected), plus five repeated displays. All 151,552 display
pixels, CRCs, frame IDs and buffer ownership checks passed. Source writes and
memory contents were checked for 139,264 pixels; result writes and memory
contents for 135,168 pixels. Both epochs reused all three source slots at least
five times. Underflows and mismatches were zero.

DDR AR/AW/W stalls, read gaps, shared R/W service competition, capture/result
and display/sample arbitration, and raw/corrected changes while busy have
nonzero coverage. Eight intentionally unreserved whole input frames per epoch
exercise source exhaustion; accepted malformed/drop counts were zero. The busy
reset kept DDR memory intact, changed textures and restarted frame IDs, then
verified recovery and final drain.

The snapshot includes the board configuration overlays and exact Gray
constraints so its closure can be matched to the native build. The simulation
elaborates the listed real system datapath with model clocks/DDR; it does not
exercise external HDMI configuration silicon or prove physical CDC delay/skew.
H FIFO native structure and Gray timing results are recorded separately.
