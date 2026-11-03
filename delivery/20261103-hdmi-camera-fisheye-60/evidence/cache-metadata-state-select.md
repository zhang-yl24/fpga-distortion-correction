# Metadata address selection from registered cache state

The only RTL change from rowpad cache SHA-256
`8b0da259d55b7ea052576152c656162c83316b8c69eceb5c71ccaafb2370414a`
is selection of `query_line_index` throughout `state == RESULT`, instead of
selecting it with `refresh_query`. The read enable remains
`pre_to_query || refresh_query`, where `refresh_query` is
`consume_slow && query_valid`. Cache mapping, data fill, query state and all
external interfaces remain unchanged.

The new cache SHA-256 is
`af1ccb64704011209280b5b9907a7813b2cf1817fb42b8c4c3226a6455b7a0f0`.
The assertion-extended unit test SHA-256 is
`aa86d462f8eb845342200daeafd90a859f3b622b948f99b62832ba9ac293c66b`.

Enabled-read equivalence follows directly from the control expressions:

- When `refresh_query` is true, state is RESULT and both address expressions
  select the held query's index.
- When a read is enabled and `refresh_query` is false, `pre_to_query` is true.
  It requires IDLE, so both expressions select the decoded FIFO head.
- With neither condition true, the metadata read registers do not update.

The proof covers the same-cycle miss/younger-query preload, a held RESULT,
RESULT consumption with or without a younger query, and fault/reset handling.
There is no additional pipeline cycle. The change removes output readiness
from metadata address selection; output readiness still participates in the
read enable. Physical timing improvement requires a new implementation run.

All four XSim 2017.4 regressions passed with stable source hashes:

| Evidence directory | INDEX_BITS | Row padded | PREDECODE |
|---|---:|---:|---:|
| `cache-state-select-i10-p1/` | 10 | 1 | 1 |
| `cache-state-select-i10-p0/` | 10 | 1 | 0 |
| `cache-state-select-i7/` | 7 | 0 | 1 |
| `cache-state-select-i9/` | 9 | 0 | 1 |

The new monitor checks each enabled metadata-read edge against the former
consume-dependent address, across all four neighbor ports. Every configuration
records 764 address comparisons: 184 preload edges and seven refresh edges,
with four neighbors per edge. Both paths have required nonzero coverage.

Each run also retains 184 independent native-WIDTH1920 numerical query checks,
419 direct-fill RAM content checks, seven speculative younger-query refreshes,
boundaries, alias replacement, pending frame drain, output/input stalls, reset
on the final fill beat and four malformed DDR cases. The padded configurations
exercise 446 neighbor indices that differ from linear mapping. First warm-hit
latency remains five cycles, with 64 outputs over 63 cycles and 32 changing
metadata outputs over 31 cycles. Unsupported WIDTH639 and WIDTH4096 retain the
documented linear fallback.

These are cache-unit results. The earlier `system-final-rowpad640-fanout16/`
receipt predates this change and the subsequent writer/display payload changes;
the new combined `system-final-e-rowpad640-fanout16/` regression includes all
three changes, passes, and binds its source hashes to the physical-e snapshot.
