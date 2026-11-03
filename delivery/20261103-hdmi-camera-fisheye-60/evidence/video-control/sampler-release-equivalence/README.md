# Three-stage sampler release: equivalent backup, not applied

The tested old source is the frozen live sampler with two protected `p_reset` bits, synchronous `sample_valid_hold`, and `sampled_valid = p_reset[1] && sample_valid_hold`. The temporary new source has three protected `p_reset` bits, unchanged data sampling conditioned on bit 1, and `sampled_valid = p_reset[2]`.

The low two reset bits are identical in both designs at every edge. At each PCLK rising edge the old hold and the new third bit both take the pre-edge second bit. On asynchronous reset assertion, the old hold can retain its previous value, but old bit 1 clears and masks it; the new third bit clears directly. Thus stable valid outputs both become zero without a PCLK edge. Between assertions, the new shift chain visits only 000, 001, 011, 111, so its bit 2 implies bit 1. This proves the old AND expression equals new bit 2 after every settled event.

On release, data clears on the first two rising edges and first captures raw VS/HS/DE/RGB on edge 3. Valid rises on that same third edge in both designs. Synchronous data clear and retained data while PCLK is stopped remain identical. The 27-bit sampling assignment and polarity expressions are unchanged.

The independent test uses both modules plus a numeric edge-count/data oracle, downstream RGB565 quantizers, and VS first-sample/edge consumers. Final coverage: 37,940 settled comparisons, six polarity configurations (four valid, two invalid), 13,540 PCLK rising edges, 3,858 asynchronous reset assertions, stopped-low and stopped-high clock cases, 3,761 coincident assertion and 3,846 coincident release stimuli, 695 baseline samples, and 424 consumer VS edges. Clock coincidences are checked after nonblocking updates settle; reset pulses have explicit nonzero duration.

Results and exact source hashes are in `results.json`; test source, old/new simulation-only modules, quantizer source hash and simulator logs are included. This is a digital equivalence argument and regression, with no analog reset-metastability or new routed timing claim.

`probe.py` is the original workspace probe retained for provenance. Its source, testbench and simulator paths refer to the recorded D: workspace; adjust these explicit paths before rerunning it from another checkout. The archived `old.v`, `new.v` and `test.sv` are the exact passing experiment sources.

No live sampler change was applied. Physical-g's actual worst pixel path is output raster decode -> pop -> wide word enable, so the approved next change addresses that path separately.
