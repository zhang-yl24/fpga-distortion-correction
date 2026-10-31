# Reset/epoch minimum contract — HDL pending

This is a pure self-developed, small geometry-helper contract experiment.
It includes the exact frozen helper (SHA256 `57779e03f9c29d2e168fbabf77ae540675ebfc1ebec3e6e24ba3b7f7b6c6b329`),
an isolated six-edit candidate, a new guard and a directed bench. Production
RTL, all previous packages, FDC, RS checks and final ADF are unchanged.
No vendor/IP/license/media/board pins or private absolute paths are included.

The real outer HDMI polarity/rate observer, I2C/configuration delays and full
board top are NOT instantiated. The wrapper reproduces their relevant
precondition: readiness is a reference-clock register asynchronously cleared
by COMMON reset. It cannot change while ref_clk is stopped except for that
asynchronous assertion. The one-register peer is not a test of the real
power-up delay. The REAL helper snapshot interval remains 27000 reference
edges. Geometry is synthetic 8 bytes x4 lines, raster16x8; this is not a
native1080 test or pixel/calibration proof.

Three simultaneous instances:

* KIND0: exact helper, `rst_n=common_reset_n && readiness_ref`, modeling the
  currently valid top reset-release guard.
* KIND1: raw COMMON reset to both reset synchronizer stages; readiness becomes
  local run/epoch permits. A reference initialization barrier precedes permit
  synchronization to PCLK; existing enable/disabled-source handshake is kept.
* KIND2: intentionally unsafe raw-reset release without the top guard. It MUST
  be rejected by the concrete stale-request/changed-bundle witness, not silently
  excluded or accepted as a passing design.

IMPORTANT CANDIDATE LIMIT: after readiness has been committed, sampled ready
loss latches blocked until COMMON reset. This stricter recovery policy is an
explicit protocol change; the candidate is NOT production-equivalent or
approved for integration. A short ready pulse is not required to enable a
session. A ready register magically changing with its source clock stopped is
outside the real top contract, not a coverage claim. Unexpected ready loss
must fail closed; re-arm requires common reset and new initialization.

Both stages retain raw asynchronous clear. Digital assertions cannot prove
physical recovery/removal, reset pulse width or MTBF. Removing a reference
launch path from RS does not make the raw external reset timing accepted.

## Directed obligations

1. Mature real 27000-cycle outstanding request1; stop ref, asynchronously
   assert/release common reset with both clocks stopped, then advance PCLK.
   KIND0/1 cannot answer stale request before reference state clears.
2. KIND2 must capture old request1, allow live frame counters to advance,
   resume ref for8 edges to ACK-detection/settle, then PCLK for3 and ref for1.
   Independent temporal scoreboard must reject changed bundle after ACK.
3. Common reset and restart both clocks; real source frames and newly captured
   snapshot must publish with current scoreboard epoch, correct held payload
   and positive good_frames, followed by authorize.
4. Stop PCLK and reset; ref-only progress cannot release the stopped pixel
   synchronizer or authorize retained business state; resume/recover.
5. Stop/resume ref without reset; held bundle changes only on a new request.
6. Reference-generated ready low/high bounce withdraws authorize; candidate
   remains blocked until common reset. No READY_BOUNCE recovery is inferred.
7. Common reset/new epoch recovers, never accepting a retained prior tuple.
8. Three relative release/clock-edge orders, including simultaneous edges,
   preserve old-state/NBA two-stage release, then fresh-epoch publication.

The scoreboard is independently tagged by common-reset epochs and observed
business-clear events, not a DUT epoch output. It records the bundle when
ACK is detected, then requires stability at capture and correct publication.
Assertions also check actual source/reference state clears under !p_run/!r_run.
The checker requires both reference and source reset work to have executed
before accepting a bundle. DUT numeric outputs are not used as a standalone
golden for geometry arithmetic; that unrelated arithmetic is outside scope.

## Cloud execution

From this directory, with an externally supervised own process group:

```
python -B scripts/test_cpu.py
python -B scripts/replay_helper_boundary.py
iverilog -g2012 -s tb_reset_epoch_contract -o contract.vvp -c sources.f
vvp contract.vvp
python -B scripts/check_contract.py contract.csv
```

Do NOT run a second long native1080 experiment. This bench is a small helper
test. Suggested outer budgets: compile90s, simulate120s, plus bounded cleanup;
retain stdout/stderr on timeout. Use the cloud's already validated group
supervisor; this package does not introduce a competing process killer.
Its in-simulation20ms watchdog is a failure guard, not a promised run duration.
At most about6 x27000 ref rounds and ~650k manual domain edges are expected;
no frame-sized memories, vendor models or large generated vectors. RAM is
only the helper's scalar registers and small event log.

`RESET_EPOCH_CONTRACT_PASS`, vvp exit0, complete CSV AND independent Python
oracle PASS are all required. The intentional KIND2 ERROR records are required
negative evidence, not permission to ignore KIND0/1 errors. No terminal marker
means INCOMPLETE. The expected final reset epoch is8; fresh publications in
cases3/4/5/7/8 must be tagged3/4/4/5/8, respectively.

The reused CPU witness remains an abstract control replay, not fresh HDL proof.
Only CPU preparation is run locally. HDL compile/simulation are pending cloud
execution; neither this bundle nor a future digital PASS is physical RDC,
PDS timing, whole-observer or hardware acceptance.
