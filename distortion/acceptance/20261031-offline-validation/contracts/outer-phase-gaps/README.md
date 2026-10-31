# Two missing ACTUAL ready phases — new isolated bench only

Base: Library `libfile_38b30da37a208191bcfb9d76abd07856` v0,
ZIP SHA256 `1b81eeffb09dc48aa40f01d5e66c7327dc67972aaf11a1185dd4917d917e10f1`.
Its20payload files and previous9case evidence remain frozen. All7 RTL file
hashes are identical here, including both isolated candidates. The only HDL
change is tb/tb_outer_threeway.sv; diff and base hashes are provided. This run
contains ONLY2new missing phase cases. It does not rerun the9old scenarios.

Correction to previous coverage: actual ready positions were(6,1),(1,6),
(3,6),(2,0); different ARM request positions did not cover pre-VS or exact DE
edge. Old results still establish their observed traces, not the missing ones.

This bench pauses ONLY the external synthetic PCLK/raster while all observer
active flags are0, presets the source raster phase, and resumes the clock so
its next rising edge coincides with a reference edge. Effective simulator
periods are unchanged:1ps precision rounds original ref half to18.519ns and
pixel half to6.658ns. The registered ready peer is unchanged. No force/deposit
or change to any DUT register, FDC, RX assumption, golden or candidate occurs.
The pre-ready source may be arbitrary; after release the raster is valid.

Case1: source is preset(14,5); simultaneous PCLK/ref edge advances to(15,5)
and registered ready rises. VS is still inactive, then its NEXT pixel edge
advances to(0,6), VS rises exactly13.316ns later. Actual coordinates and two
timestamps are asserted in HDL and independently checked from phases.csv.

Case2: source is preset(0,0); simultaneous PCLK/ref edge advances to(1,0),
raising DE and ready at the SAME timestamp. Actual DE-edge timestamp must
equal ready-edge timestamp at1ps precision; request coordinates alone cannot
satisfy coverage. The next complete source frames remain independently checked.

Existing baseline-vs-small public comparisons, all-route valid geometry,
epoch/bundle checks and terminal invalidation stay active. Current-guard
differences are recorded, not waived as production equivalence. Small8x4
synthetic raster, real27000ref snapshot interval, no board/native1080 claim.
Candidate/production/physical RDC acceptance remains false pending review.

Run under the existing cloud bounded-process supervisor:

```
python -B scripts/review_manifest.py
python -B scripts/test_phase_preparation.py
iverilog -g2012 -I. -s tb_outer_threeway -o phase.vvp -c sources.f
vvp phase.vvp
python -B scripts/check_phase_gaps.py outer.csv phases.csv
```

Suggested compile45s/sim120s plus bounded cleanup. Expected about2ms simulated,
roughly54000 ref edges, from prior9case41.531s wall about10–30s inferred, not a
new measurement. No local HDL/EDA was run. Full terminal in BOTH CSVs plus
vvp exit0 and independent oracle required. Partial/incorrect phase is failure
or incomplete, never coverage PASS. BASE_README.md is historical base context;
its9case commands/oracle do not apply to this2case supplement.
