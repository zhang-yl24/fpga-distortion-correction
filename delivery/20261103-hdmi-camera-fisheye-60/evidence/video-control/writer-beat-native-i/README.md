# I native writer beat duplication

Source identity: `d931793d62bc852c25be57f16528ac7d18dc70fc5760138dcf05e6f443ee8bd5` (116 compiled inputs).

The independent audit confirms `syn_maxfan=32` survives both complete-design synthesis and final PNR. Each lane contains 9/9/33/65 registers for beat bits 0/1/2/3: 232 registers overall. All actual Q output nets connect to at most 32 primitive input pins, including BUF/INV expansion. The corresponding H maxima were 263/262/1029/2052, with one register per bit. Per-bit total loads remain identical.

Every synthesized same-bit copy has identical D/CE/CLK/R and INIT/GRS settings; the original register signatures also match H exactly. Functional source tokens match H after excluding the attribute comment and relocated CRC include path. These checks establish the local duplication and its unchanged synchronous control semantics. They do not constitute whole-device formal equivalence.

The final routed topology comes from the official functional netlist exported from I's final `_pnr.adf`; both hashes are recorded. Counts include connected LUT input pins even when their truth table ignores that input. The map report is a bounded list whose cutoff was 142; full synthesis and PNR parsing provide the per-register evidence.

I's global timing remains failed: slow core -2.886 ns, pixel -2.414 ns and core-to-PHY0 -0.012 ns, with additional related-clock failures retained in `evidence/physical-i/timing.json`. The local fanout reduction does not establish timing closure, an accepted 60 FPS bitstream, or board readiness.

The two included audit scripts accept `--project`, `--reference` or `--netlist`, and `--output` paths. Large source netlists remain in the local native run directories and are bound by SHA-256. This folder contains the compact audit evidence and H comparison needed to review the claim.
