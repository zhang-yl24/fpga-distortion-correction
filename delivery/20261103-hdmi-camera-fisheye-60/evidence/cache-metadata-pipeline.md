# Registered cache metadata and independent admission

The physical-a INDEX7 implementation exposed a real 125 MHz slow-corner path
from `pixel_number[2][10]` to `pre_tag[6]/CE`, slack -2.910 ns. Seven logic
levels accounted for 1.338 ns and routing for 8.990 ns. Asynchronous tag reads
fed `all_hit`, `accept_query`, upstream readiness and the pre-stage clock enable.

The cache now uses a separate two-entry decoded-address FIFO whose admission
depends on registered occupancy. Four synchronous tag/valid reads accompany a
registered query; tag comparison therefore starts from lookup registers. The
slow neighbor path has a synchronous metadata-read stage too. A younger query
looked up on the same edge as an older miss is refreshed at slow completion,
after all fill/tag writes, to prevent using a tag invalidated by replacement.
No timing exception or clock constraint was changed.

RTL SHA-256:
`6cab23f8f279e0e3dbad87d665944373ead3702dfb06fa702765b98e7c8f847e`.
This change preserves the eight-beat direct DDR fill and the external ports.
Warm input-to-first-valid latency rises from four to five cycles. Continuous
hits retain one pixel per cycle; each slow in-bounds neighbor adds one lookup
cycle. Full-frame performance and routed timing are measured separately.

All four INDEX7/INDEX9 × PREDECODE0/PREDECODE1 directed regressions pass. They
check 168 independent numeric query
records and 403 RAM writes, all four RGB neighbors, changing XY/fractions/tags,
conflicting line replacement, frame admission/drain, reset on beat seven, input
and output backpressure, and four malformed-response quarantine cases. Both
show 64 outputs over 63 cycles and 32 varying queries over 31 cycles. New
coverage records 27 full decoded-FIFO cycles, 124 simultaneous FIFO refills,
7 speculative lookups on miss, and 7 post-miss refreshes. An assertion checks the current
actual tag/valid contents whenever a fast hit is accepted.

Capacity estimate from physical-a: that INDEX7 snapshot used 61 of 155 DRM36K
equivalents. Its two caches used 16 DRM36Ks for pixel data. INDEX9 quadruples
that data allocation to approximately 64 DRM36Ks, suggesting roughly 109 total
before extra synchronous tag replicas, or about 113 with five metadata read
copies per lane. This is an estimate; the final synthesis report determines
actual replication, packing, LUT/FF use and timing. Indexed valid bits still
require a multiport mux and must be checked in routed INDEX9 timing.

Reproduce using `tools/run_cache_direct64.py --work <new-directory>
--index-bits 7` or `--index-bits 9`; `--predecode 0` also checks the compatible
internal-address path. Receipts and logs are in `cache-metadata-i7-p0/`,
`cache-metadata-i7-p1/`, `cache-metadata-i9-p0/` and `cache-metadata-i9-p1/`.
