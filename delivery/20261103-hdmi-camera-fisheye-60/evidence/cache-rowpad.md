# Optional source-row padded cache index

The cache, sampler, core and spatial lane expose `ROW_PADDED_INDEX=0` by default.
For widths from 128 to 2048 that are exact multiples of 128, enabling the
parameter uses `(16 * source_y + floor(source_x / 128)) mod 2**INDEX_BITS`.
Other widths explicitly fall back to the existing linear index. At native
WIDTH=1920, each source row has 15 real cache lines and reserves 16 cache slots;
INDEX10 is therefore `{source_y[5:0], source_x[10:7]}` for valid pixels.

All four indices are calculated from decoded XY and registered in the decoded
FIFO. No division by 15 is placed on the metadata or BRAM address path. The
metadata read, post-miss refresh, slow lookup, data read and direct fill use the
same indices. Tags and DDR addresses retain the real linear source-line number.
RAM word offsets retain the original linear pixel bits `[6:3]`; parity and
16-bit lane selection are unchanged. The eight-beat DDR fill remains intact.

Original rowpad-stage cache SHA-256:
`8b0da259d55b7ea052576152c656162c83316b8c69eceb5c71ccaafb2370414a`.
The later state-selected metadata address change is documented separately in
`cache-metadata-state-select.md`, with new source hashes and four passing
regression receipts. The original receipts below remain bound to this hash.
The core/sampler overlays only add parameter propagation; the original files
in `distortion/` and the sealed C delivery are unchanged.

Passing unit receipts:

- `cache-rowpad-i10-p1/`: INDEX10 padded, PREDECODE1.
- `cache-rowpad-i10-p0/`: INDEX10 padded, PREDECODE0.
- `cache-rowpad-linear7/` and `cache-rowpad-linear9/`: default linear compatibility.

Every case checks 184 independent native-1920 numeric query records, 419
direct-fill RAM writes, four-neighbor pixels and metadata, 16 different offsets
of the same two source lines, cross-row neighborhoods, line boundaries, alias
replacement, frame invalidation, pending-frame drain, reset and four malformed
DDR responses. The padded cases record 446 in-bounds neighbor indices that
actually differ from linear indexing, so padded-mode coverage is non-vacuous.
An independent XY oracle checks every registered index, each slow/fill index,
and every real DDR request address. Seven speculative younger queries are
refreshed after misses; accepting a stale tag is an assertion failure.

Both padded and linear modes retain five-cycle first-hit latency, 64 successive
outputs over 63 cycles, and 32 changing-XY/fraction/tag outputs over 31 cycles.
Unsupported WIDTH639 and WIDTH4096 each pass six arithmetic/index cases proving
the explicit linear fallback. Full native-frame miss counts, throughput and
routed resource/timing acceptance are separate tests.

Reproduce with `tools/run_cache_direct64.py --work <new-directory> --index-bits
10 --row-padded-index`; add `--predecode 0` for the compatibility path.
