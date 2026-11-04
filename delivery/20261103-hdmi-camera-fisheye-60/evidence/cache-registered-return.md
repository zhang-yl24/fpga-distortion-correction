# Cache registered-return contract

`REGISTERED_RETURN` is optional and defaults to 0 in the core, sampler and cache.
The lane selects 1 because it already registers the complete RDATA/RID/RLAST/
RVALID bundle. With this contract, only the FILL state accepts returned beats;
shared ARREADY no longer participates in the cache RAM write-enable receive
condition. The generic default retains the AR-handshake-edge first-beat case.

When an external first R beat arrives on the external AR handshake edge, the
lane captures it by nonblocking assignment while the cache changes AR→FILL.
The cache consumes that beat on the next edge in FILL. Data, ID, last and valid
keep their common offset. No new register or miss cycle was added.

Before address fanout attributes, cache SHA-256 is
`5c82ee0065ed6a9b01e5a9d63953478daa80b79b9b9cdcfe8a0c226de37f2107`.
Complete pass-through hashes are in `cache-registered-return-sources.json`.
Four unchanged legacy regressions passed at rowpad INDEX10/PREDECODE0 and 1,
linear INDEX7 and 9, including all four AR-edge-first fills and the independent
metadata/RAM/pixel/handshake checks. Their evidence is `cache-return-legacy-*`.

`cache-return-bundle-final/report.json` verifies two actual caches side by side,
one default and one contract mode, behind an explicit complete one-cycle lane
bundle. Their handshake, AR, counters, output values and timing match on all
459 compared edges. The memory pattern independently checks 44 neighbour pixels
including line crossings, final-beat words, partial image boundaries and negative
coordinates. Registered-bundle fields are checked on every one of 508 edges.

The test covers 19 legal external AR-edge first responses, AR stalls, 39 read
gaps, continuous returns, output backpressure, reset with a pending final return,
and RID/early-last/missing-last/unsolicited-return quarantine. A separate contract
violation sends an R before external AR and aligns its buffered R with the later
AR edge: mode 1 rejects it as unsolicited without a RAM write; default mode 0
retains its generic AR-edge acceptance. Including that deliberate violation,
the raw bus totals 20 AR-edge first responses, 9 AR stalls, 22 returned last
markers, 4 pending-return reset edges and 4 ordinary error cases.

This evidence proves digital protocol equivalence for the declared lane return
contract. It does not establish native routing improvement; the separately
frozen I physical run measures that effect. Address fanout attributes and their
native probe are recorded independently.

The final I cache also applies the separately proven four `syn_maxfan=8`
address attributes, SHA-256
`35ee33af1940a0b02e4c7ae9bd21d1e119bb6fd32c60a109f7b2b822fc3dee9a`.
Its text exactly matches the native probe's candidate, and removing attributes
and whitespace gives the same RTL tokens as the parameter-only baseline.
Four legacy groups and the explicit bundle test were rerun against this final
hash; all passed with unchanged coverage and cycle counts. These results are
in `cache-return-fanout8-*`, and final pass-through hashes are in
`cache-return-fanout8-sources.json`. Native duplication, projected LUT truth
functions and exact load partitions are documented independently in
`cache-address-fanout8/verification.json`; full I PNR remains the timing test.
