# Implementation-i real system regression

The complete 64脳64 system passed both reset epochs with the I frozen registered-return cache contract,
address fanout8 attributes, writer beat fanout32 attribute, display picture
predecode/private completion payload and all user CDC attributes. Build ID is `11037003`; system identity is
`a2f36cb0d72aa8efcd8a18a3b45ee63b975bf43feee6118e1127302cc0d51b80`.
No overlay changed during simulation.

`physical-i-source-binding.json` binds the native physical-i identity
`d931793d62bc852c25be57f16528ac7d18dc70fc5760138dcf05e6f443ee8bd5`:
all original overlay hashes match, and all 116 prepared files match after
normalizing only the absolute compiled-root prefix. Of these, 111 match byte
for byte and five contain relocated include paths. Each file also matches its
own manifest hash. Build/profile/cache/clock settings agree. The build inventory
contains no missing or duplicated entries, missing overlay entries or source
drift.

The real mapper/cache/writer, three-slot capture DMA, return register, shared
arbiters, asynchronous FIFOs and scanout ran with core 125 MHz and input/output
148.5 MHz. At 64脳64, the cache uses linear fallback and the engine partitions
32/32 rows. Native row16 indexing and the 640/440 partition belong to the
separate complete 1920脳1080 engine verification.

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
I FIFO native structure and Gray timing results are recorded separately.
