# G to H prefetch and index FIFO review

Scope: independent read-only source comparison against `D:/f60-run/physical-g/compiled/rtl/experimental/`, with no repeated simulation or routed-timing claim. No blocking functional issue was found in the reviewed changes.

Reviewed live SHA-256:

- `rtl/ddr_adaptive_result_writer.v`: `c82d52ad9adc0c53901bac3e07b6fbcfa99a1e28afb1c2985808dd61ca78ec11`
- `rtl/ddr_neighbour_cache_scatter4_rowpipe.v`: `a77a7fb5d527b8de0728719a634db6b9de7f6bd086d39e35dcc692661a34a1fe`

## Writer publication

The functional change removes readiness/reset/failure gates from private `cmd_pixel` and `cmd_lane` capture. `cmd_pending` retains the G acceptance predicate and reset/failure handling. On any rising edge, a pending RAM update consumes the previous payload and lane. The new private capture takes effect in the nonblocking update region afterward. Consecutive accepted pixels directed to the same word therefore remain ordered. A bubble or full-bank stall may replace private data, but cannot create a pending command or overwrite burst RAM without a previously accepted command.

The edge that asserts reset or detects failure can still retire an older pending command, matching G. Reset/failure then clears command ownership. The bank-full, AW admission, committed-burst drain, CRC and success paths are unchanged. Word/bank wrap has the same one-edge publication latency as G; no new stale last pixel is exposed.

## Decoded cache index head/tail

`pre_to_decoded` retains the strict `decoded_count < 2` condition. The valid transitions are:

| Prior count | Push | Pop | New head/tail |
| --- | --- | --- | --- |
| 0 | 1 | 0 | New input becomes head |
| 1 | 1 | 0 | Head held, new input becomes tail |
| 1 | 0 | 1 | Queue empty; stale data unowned |
| 1 | 1 | 1 | Lookup consumes old head, new input becomes head |
| 2 | 0 | 1 | Lookup consumes old head, tail becomes head |

At count 2, push is always false even when popping. This prevents the whole-vector tail-to-head assignment and new-input assignment from competing. At count 1 with simultaneous push/pop, synchronous metadata lookup and query fields consume the old head before its nonblocking replacement. Thus the head matches the former circular storage at `decoded_read`, while all remaining payload fields keep their original pointer updates.

Reset clears count and query validity; unreset index payload is invisible until a new push establishes ownership. Failure prevents both movement events. The existing error cycle may perform the same already-enabled lookup as G, followed by failed/FAULT isolation. RESULT metadata refresh still selects the held query index independently of the new head.

Future maintenance constraint: introducing full-plus-pop push lookahead would require a separate count-2 simultaneous transition that promotes the old tail and writes the new input to tail. The current admission predicate deliberately excludes that transition.

The existing publication oracle and old-slot index assertions cover the implementation contracts above. This review adds no test-pass claim beyond their separately recorded results.
