# Current-top readiness reachability — source-bound proof preparation

Question: in one external COMMON-reset epoch, can the current diagnostic
`power_ready && rx_done_ref[1]` produce1→0→1? This is NOT the new STOP/START
protocol and no production RTL/FDC has been modified.

## Result and exact limit

The finite dependency-cone overapproximation closes all39 baseline states /
449 transitions, including10 ready-high states,4 post-high/low states and2
blocked-guard states. No blocked-guard state has readiness high. Thus the
model's readiness has at most ONE HIGH INTERVAL per common-reset epoch. A
0→1→0 sequence on a sticky fault is allowed; this is NOT a claim of monotone
nondecreasing readiness. Ref/cfg clocks may stop independently or forever;
simultaneous edges use old-state NBA equations. RX synchronizer first-stage
sampling may hold or capture arbitrarily; no analog metastability/glitch model
or fairness is assumed for this safety result.

With only wrapper latch retained:47states/544transitions, property still closes.
With only sticky driver retained:38/439, also closes. Removing BOTH sticky
behaviors yields an executable21-state witness of1→0→1. The original source
has BOTH; the mutant demonstrates the property check is capable of failure.

Source premises are explicitly bound by9 writer inventories and9 wiring/guard
checks against current frozen files. The3 actual_self files are unmodified
self-developed top/checked-wrapper/checked-driver copies for independent source
review. The vendor-derived RX register-table BODY IS EXCLUDED. Its complete
`init_over` writer inventory was checked locally: reset→0, completion→1,
otherwise self-hold. Its hash/line numbers and semantic result are in the
ledger, but this is not cloud elaboration of that omitted body. Conditional
cone proof and its source mapping must NOT be presented as a literal formal
equivalence proof of the entire production top.

## Why the premise is supported by these exact sources

* power_ready and configuration_ready cannot fall again while the common
  epoch remains active after startup. Counter completion cutpoints occur
  arbitrarily early/late/never in the model, a superset of real countdowns.
* cfg_reset_pipe only releases after configuration_reset_n, which is common
  reset AND those startup qualifications. No runtime PLL-lock reset was added.
* Actual iic_dri_checked transaction_failed has one reset-zero writer and five
  set-one sites; no runtime clear. Wrapper failed_latched independently latches
  the error until configuration reset. Raw error and latch both gate seq_rst_n.
* RX init_over is sticky while seq_rst_n is active. Polling/SETING do not clear
  it. Once sticky failed is asserted, visible init_over_rx remains masked low
  even if its synchronously reset register retains1 with cfg clock stopped.
* rx_done_ref is a2-stage reference-clock sample; reference reset clears both.
  A single-high-interval input cannot produce two high intervals with monotone
  hold/current capture sampling. Missing clocks only stall progress.

Potential invalidating changes: independent configuration reset/retry while
common reset remains high, clearing BOTH fault stores during runtime, replacing
RX completion with a live lock/HPD/status indication that can recover, another
writer of startup qualifications, a different source/config build, or physical
fault/metastability behavior outside the two-state monotone sampling model.
HDMI cable/PCLK changes are not direct inputs of this readiness expression;
they still can create separate observer sticky-fault recovery requirements.

## Candidate implication — narrow, not full equivalence

Under the single-high-interval property, sticky blocked cannot suppress a
later legally recovered ready-high state in this same top epoch: that later
state is unreachable. Therefore the generic helper ready-bounce policy
difference need not, by itself, reject a LOCAL top-specific candidate.

This does NOT establish full observable or cycle equivalence. The new guard
adds a reference commit and pixel permit synchronization; startup phase,
which first source frame is sampled, outer polarity/timing/rate state and
failure-priority behavior have not been compared at the real full top. The
current contract bench instantiates the actual geometry helper, not that full
outer observer. Physical reset release on raw RS is still unaccepted. These
remain explicit regression/proof obligations, not reasons to add STOP/START
automatically or blindly call the present candidate production-equivalent.

## Minimal executable HDL replay (NOT RUN locally)

The projection preserves the source equations of the dependency cone; timer
completion, RX completion and registered driver error are cutpoints admitting
more behavior than the actual machines. It is an evidence model, not a renamed
production module. The21-step mutant witness is generated from CPU states.
Four modes receive the SAME controls: original sticky/sticky, nonsticky driver,
no wrapper latch, and both broken. Each step checks the fourth mode's15 state
bits against the independently generated CPU trace. Baseline and single-sticky
modes must reject1→0→1, while the double-broken mode MUST exhibit it. Additional
common-reset with clocks stopped/new initialization verifies the property is
epoch-scoped and does not prevent a new legal initial readiness rise.

From package root, under the cloud's existing bounded-process supervisor:

```
python -B scripts/review_binding.py
python -B scripts/readiness_reachability.py --out run-cpu
iverilog -g2012 -I. -s tb_readiness_cone -o cone.vvp -c sources.f
vvp cone.vvp
python -B scripts/check_hdl_csv.py readiness.csv
```

Suggested budgets: compile30s, sim30s plus bounded cleanup; only dozens of
scheduled cone edges, no frame memories or long runs. A terminal marker,
exit0 and independent CSV oracle are required; all protected files remain
hash-bound. CPU and static source checks ran locally; HDL is PENDING until
cloud execution. No new PDS, bitstream, board operation, Git or original-thread
interface is involved. Vendor/IP/license/media/private absolute paths excluded.

## Next admission, if the cone result is accepted

Do not implement a new auto-recovery protocol yet. First discharge the omitted
RX sticky writer premise against the exact licensed local source if an
independent reviewer requires elaboration; whole-machine reachability is not
needed for a reset/one/hold register but a hash/guard mapping must be retained.
Then make a source-isolated full OUTER-observer candidate and define allowed
startup-latency differences. Reuse fresh/old-epoch and stopped-clock assertions
under the real registered readiness generator, not an arbitrarily bouncing
ready peer. Only after behavioral/identity coverage passes should one consider
new source-matched physical RDC/STA evidence. Existing39-state safety evidence
does not remove either of those obligations.
