# FIFO predecode cache timing candidate

This isolated overlay targets the actual both-final setup report. Repository and sealed delivery sources are unchanged. No physical implementation has been run for this overlay.

## Actual timing diagnosis

The sixteen slow setup failing endpoints sum to TNS -2.992 ns. Eleven cache FIFO read-pointer to lower-neighbour tag/valid lookup endpoints account for TNS -2.597 ns and WNS -0.619 ns. Three DDR return to cache validity endpoints account for -0.137 ns; one DDR calibration/data gate to reader CRC endpoint has -0.206 ns; one writer beat to DDR data endpoint has -0.052 ns. `setup-paths.json` preserves every unique setup endpoint and its native path text. Recovery/removal paths are excluded using the native Setup time check type.

## RTL change

`sources/experiment.v` replaces the private cache core implementation within the same public module. The existing two-entry FIFO stores four precomputed signed-coordinate linear pixel numbers plus four bounds flags on its normal push edge. Private core lookup now consumes those registered fields. The FIFO head mux no longer feeds coordinate multiplication/addition before tag/valid indexing. Existing XY/fraction/tag, queue handshakes, frame drain, miss state machine and lookup-refresh timing are preserved. No new cycle or throughput bubble is introduced. Additional registered payload may increase FF usage; synthesis/STA must determine the actual resource and physical timing effects.

Public module and interface: `ddr_neighbour_cache_scatter4_tag_prefetch_local`, unchanged. Overlay destination: `source/rtl/experimental/ddr_compact_neighbour_cache_scatter4.v` in the prepared native source tree. `source-change.diff` contains every change. Source SHA256: `9f80b781a9f154f797966f346321ae8da732dbf29eb0f12054e85c66160744ed`.

This overlay contains only FIFO predecode. The previous optional CHECK invalidation experiment is separate and has not been mixed in.

## Verification

Four original cases passed: current directed/full 1080p, candidate directed/full 1080p. Candidate tests instantiate the prior cache alongside the new cache and compare all output ports, FIFO state, state machine, valid-lines, query valid, AR state and watchdog on every cycle. Both full-frame cases independently check all four neighbouring RGB pixels, fractions and 25-bit tag for all 2,073,600 queries.

Both versions take 3,586,079 cache cycles, 16,200 misses/bursts, 259,200 scatter cycles, 8,272,201 hits. Full-frame lockstep covered 3,586,088 cycles, including 5,394 same-cycle AR/first-return responses. Directed lockstep covered 1,700 cycles with backpressure, frame change, conflicts, reset and malformed returns.

Additional signed-coordinate directed testing checks a cross-product of 64 Q16.8 edge coordinates, including minimum/maximum 24-bit signed values, negative fractions and image boundaries; its full directed run passed 2,211 lockstep cycles. Seven additional priority scenarios passed 304 lockstep cycles, covering invalid matching tag, conflicting valid tag, CHECK error, final scatter error, reset, AR timeout and FILL timeout. All tools exited zero and required PASS markers were observed.

Reports: `run-a/results.json` and `supplement/run-a/results.json`. Logs preserve exact simulator commands, input and log hashes. Run `python -B run_experiment.py --workdir <fresh-directory>` to repeat the four original cases. Supplemental runner uses a fresh `supplement/run-a` and refuses to overwrite; clone the small sources/tests/supplement snapshot without old outputs before replaying.

## Integration status

Simulation validation is complete for the stated scenarios. Full geometry-engine regression and complete PDS Map/PNR/STA on the exact overlay remain required. Physical clock frequency, timing signoff and stable board FPS are unmeasured. This change shortens a known combinational path and preserves logical cycle throughput; it does not by itself increase processed pixels per cycle.
