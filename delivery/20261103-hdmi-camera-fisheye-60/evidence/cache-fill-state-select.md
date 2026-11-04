# RAM fill addresses selected from registered state

The implementation-f cache changes only the four data-RAM address selectors.
They select the fill address whenever the registered state is AR or FILL,
instead of using `scatter_write` as the address-mux select. The original
`scatter_write`, `read_enable`, `read_lower`, RID, RLAST, timeout and fault
expressions are unchanged. Metadata, cache indexing, tag occupancy, DDR fill
length and query scheduling are unchanged.

Cache SHA-256:
`3fbeeed340a9fa9c880c95ce5f9bad2666d6a9b77ae4bef8849859a439b84e11`.
Unit-test SHA-256:
`6fd87188bd1577ddef0241eab7fb17d3491339ff0eb9937c9efc5004ad84b5e4`.
The preceding implementation-e cache hash was
`af1ccb64704011209280b5b9907a7813b2cf1817fb42b8c4c3226a6455b7a0f0`.

Every write requires `receiving`, which implies AR with an accepted address or
FILL. Both old and new selectors therefore choose the same fill address on a
write edge. Reads occur in IDLE for accepted fast queries or LOAD for saved
slow neighbors; both selectors choose the same read address in those states.
An AR/FILL cycle with no enabled RAM operation may present a different address,
without changing stored data or registered read outputs. The final fill beat
uses the pre-edge FILL state before transitioning to LOAD. A first return on
the AR handshake uses the pre-edge AR state. Invalid returns retain their
original write suppression and sticky fault behavior.

This separates protocol qualification from data-RAM address selection, removing
the `fill_beat`/return-control through `scatter_write` path into the address mux.
Protocol qualification continues to control RAM write enable. There is no
added clock cycle; implementation timing still requires a new routed report.

| Passing evidence directory | INDEX_BITS | Row padded | PREDECODE |
|---|---:|---:|---:|
| `cache-fill-state-i10-p1/` | 10 | 1 | 1 |
| `cache-fill-state-i10-p0/` | 10 | 1 | 0 |
| `cache-fill-state-i7/` | 7 | 0 | 1 |
| `cache-fill-state-i9/` | 9 | 0 | 1 |

Each XSim 2017.4 run records 2,614 comparisons between the new addresses and
the former expressions on actual enabled RAM ports. Required directed coverage
includes four full DDR bursts whose first R beat arrives on the AR handshake,
54 final fill beats, 91 slow LOAD read edges and three malformed receiving
beats with all RAM enables suppressed. The ordinary DDR model retains response
gaps and address/data backpressure.

Each run checks 185 native-WIDTH1920 numerical query records, 451 RAM content
observations, complete four-neighbor RGB/fraction/tag outputs, replacement,
frame draining, reset on the final fill edge and four fault classes. The
metadata selector equivalence monitor checks 768 neighbor reads, including
seven post-miss younger-query refreshes. Padded mode records 450 neighbor
indices that differ from linear mapping. WIDTH639 and WIDTH4096 retain their
explicit linear fallback. Five-cycle first-hit latency, 64 warm outputs over
63 cycles and 32 changing-metadata outputs over 31 cycles remain unchanged.

The earlier implementation-e system receipt predates this change and the lane
launch/system-completion changes. Combined implementation-f validation follows
the next source freeze; these receipts establish the cache unit results.
