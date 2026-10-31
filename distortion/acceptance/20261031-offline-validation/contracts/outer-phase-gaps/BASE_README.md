# Real outer+geometry three-way directed comparison — HDL PENDING

Three isolated routes use actual self-developed `hdmi1080_input_status_cdc`
and its actual geometry helper. Baseline source bytes are unmodified.

0. Original: raw observer reset is common-reset AND registered readiness.
1. Current guard prototype: raw common reset, additional reference commit and
   two-stage pixel permit; the previous guard/helper source hashes are retained.
2. Smaller isolated prototype: both local2-stage reset/release registers keep
   asynchronous COMMON reset; their shifted-in1 becomes registered readiness.
   Reference public/consumer validity is also masked by same-domain readiness.
   No STOP/START, driver retry, reset command or auto-recovery protocol is added.

These candidates are NEW FILES ONLY, not production integration. Full module
diffs are included. Attributes, geometry arithmetic, snapshot scheduling,
bundled-data handshake and fault-code priorities remain as in the frozen sources.
Physical reset/recovery/removal, IO and hardware acceptance remain FALSE.

## Readiness premise and source boundary

The common reset starts a new scoreboard epoch. Ready is reference-registered,
asynchronously cleared by that common reset and has at most one high interval
per epoch. It may fall terminally but cannot re-rise without common reset.
The peer waits15 live reference edges before arming, a cheap concretization of
the actual top's much longer initialized reference prefix, NOT a simulation of
the actual power/I2C elapsed time. Source proof:39states/449transitions in the
earlier source-bound dependency model; IIC driver and wrapper sticky stores;
RX premise checked against local source SHA
`e5055d02e8f7af1c4c3efc151f0a71f2ed50216e55c6f95e3ac4c3f74368b21e`.
Exact local evidence is copied into evidence/RX_STICKY_LOCAL.json. Meyesemi RX
BODY IS NOT INCLUDED. This is an explicit assumption supported by local checks,
not independent cloud RX-source equivalence. The legal one-high-interval peer
must not be replaced with an arbitrary ready bounce to claim a production bug.

## What this actually tests

WIDTH8/HEIGHT4, raster16x8, real outer HS/VS/DE/polarity/timing logic and helper.
Snapshot interval remains27000 ref edges. Activity window64 with independent
expected174..182 PCLK edges at the selected normal clocks. Only rate thresholds
are scaled consistently with that small test window. There are no pixel/frame
buffers or vendor IP. This is not native1080 performance or board verification.
Timeprecision is1ps; requested37.037037ns reference /13.315579ns PCLK are rounded
by the simulator, not asserted to equal measured board frequencies.

Cases1–4 arm readiness near earliest/mid DE, before VS, at VS-active and at the
first active-line boundary. Actual x/y at the registered ready rise are logged.
All routes must independently recognize correct polarity,8x4 geometry, positive
fresh good frames, no bad frames, expected activity and no normal-input fault.
Each is terminally disabled and cannot publish retained state afterwards.

Case5: after normal qualification, PCLK becomes100MHz with unchanged raster
cycle geometry. Rate fault0x25 must occur alone. An extra HS edge outside DE
then creates real timing fault0x24 without changing geometry;0x24 outranks0x25.
An extra VS edge during DE then creates real geometry fault, whose pending0x80
or held0x14 outranks both. No DUT force/deposit, relaxed golden or deleted fault
assertion is used. Terminal ready low must mask all public qualification/fault.

Case6: actual pending snapshot_apply is present before the terminal ready fall
on the next reference edge; old data cannot become a new-epoch valid result.
Case7: ref stops, common reset asserts/releases while PCLK continues, then ref
resumes and a fresh session qualifies. Case8: PCLK stops during common reset,
reference/ready initialization resumes, no stale qualification is accepted,
then PCLK resumes and real fresh geometry qualifies. Case9: timing_bad_sync[0]
is1 while stage[1] is0; terminal fall and stage[1] arrival occur on the SAME
reference edge, and invalidation must outrank the newly arriving fault.

Independent temporal scoreboard tags common-reset epochs, requires source/ref
business clearing before captures and checks ACK-detection→settle bundle
stability. Qualification is checked against the synthetic raster's known
polarity/dimensions/count bounds, not merely one DUT against another.

## Acceptance levels — do not merge them

Baseline versus smaller prototype: public tuple is compared after EVERY live
reference edge after initialization: qualified/failed/fault/polarity validity,
VS/HS inactive levels, good/bad counts, activity count and measured dimensions.
Any mismatch is a FATAL. Common reset must invalidate without needing either
clock. Pixel-internal normalized_vs is unconnected at the real top and is not
silently counted as a public top-level output in this comparison.

Current guard versus baseline: startup gate and public differences are counted
and the first public difference per case is logged. They are NOT waived as
production equivalence. Under stable valid raster each route must qualify
within31000 reference edges of each test's wait, with fresh correct values.
Unexpected faults, wrong frames/values, old epoch, missed faults or wrong fault
priority are fatal for ALL routes. This fixed small-test bound is not a native
1080 response-time guarantee. Phase/count differences can remain for independent
review even if safety contracts pass. No assertion says every startup delay is
acceptable for the final product.

Successful terminal is `THREEWAY_DIRECTED_CONTRACT_COMPLETE`, not unrestricted
EQUIVALENCE_PASS. A pass supports only these directed digital traces and the
top-observable tuple; it does not prove every input trajectory, actual full
board HDL, UART wire behavior, setup/hold/recovery/removal, or production use.
UART's observer inputs are the compared ref-domain tuple; the actual UART/PLL/
configuration sources are not instantiated. Their behavior is a compositional
boundary, not a claimed new UART test.

## Cloud run (no local HDL/EDA has been run)

Under the cloud's previously validated own-process supervisor:

```
python -B scripts/review_manifest.py
python -B scripts/test_preparation.py
iverilog -g2012 -I. -s tb_outer_threeway -o outer.vvp -c sources.f
vvp outer.vvp
python -B scripts/check_outer.py outer.csv
```

Suggested compile60s/sim240s plus bounded cleanup. Approximately10ms simulation,
about270k reference and750k pixel rising edges across9cases /3routes; based on
the previous helper23.6s run, expected tens of seconds to a few minutes, not an
observed new runtime.30ms simulation watchdog remains a failure guard. Small
scalar state only, estimated well below100MiB before simulator overhead; no
large vectors. Save partial stdout/stderr/CSV on timeout, mark INCOMPLETE and
do not extend or rerun blindly. Final exit0, terminal and independent oracle
must all succeed. Progress markers and CSV events flush immediately.
