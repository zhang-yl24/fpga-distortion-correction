# Run8 ON HEAD1 CA135/A41 experimental package (2026-11-10)

**EXPERIMENTAL / UNTESTED ON BOARD.** This is an SRAM bitstream and captured build evidence, not a board-validated release.

## GitHub split-file distribution

The original ZIP is stored here as three raw binary parts (`.part001`, `.part002`, `.part003`) because the upload transport cannot accept its full encoded size. These are byte slices, not independently extractable ZIP archives.

Download all three part files, PARTS.json and reassemble.py into the same directory. Run `python reassemble.py` (Python 3). It checks each part, joins them in numbered order, checks the complete archive SHA256, and writes the exact original ZIP. It refuses to replace a different existing ZIP. No hardware or build operation is performed.

The reassembled ZIP is byte-identical to the original package; the split format adds no build or board validation. The later local safe-idle closeout and later bilinear candidate are not inside this fixed archive.

## Download and verify

- Package: `Run8_ON_HEAD1_CA135_A41_20261110_EXPERIMENTAL_UNTESTED.zip`
- Bytes: 17950823
- SHA256: `51beaee6d01807e95cfd9ded90340d96792b0aa8e0d5cb73bb480b113c2934ef`
- Bitstream inside: `run8_on_head1_ca135_a41_20261110_EXPERIMENTAL_UNTESTED.sbit`, 3791112 bytes
- Bitstream SHA256: `062c79b745c3bb582f90a3a36aee28ab75e2481d893403cb028fae4bd9c002f3`

Use SHA256SUMS to verify the archive. Read the package README and BUILD_IDENTITY.json before use; verify_package.py checks the payload without programming hardware.

## Identity and evidence

Source overlay commit: `70493a7e2938fbbcf1a368f29bf9ebad50b7c75a`, research/aa-black-run8.
AA generic mapper/core, HEAD1, rational Brown profile, macro64x32/tile8, GammaOFF, rotation0.
PDS2025.2 build211867, PG2L100H-6 FBG676.

Native ON manifest SHA256: `48556db12bfca3fcf283b19309b2deff2e1cc03899304d9884791b988b593eb7`.
ROM run8_intervals_30bit.mem SHA256: `e03f1869bf3247ed5ae84e94fa431885a20cca86b85e6d12d8a38053ecb8c8a7`.
ROM verification passed 266/266 words and actual physical pin/zero-control mapping.
Final repaired ON routed ADF SHA256: `5a72dbd3f905e67d003dcb7f8d15678a693063799d5ab9080a57f59f8861f2a7`.

Matched repair adds only physical routing priorities debug_data[135] and adj_addr[41], with no clock or exception relaxation.
ON slow setup +0.032 ns; OFF +0.039 ns. Each has zero failures in 10 slow/fast categories.
ON resources: LUT 30878, FF 26819, DRM grid 39, APM 68. OFF: 30133/26507/37/68.
ON costs +745 LUT, +312 FF, +2 DRM; this is neither resource savings nor a pure compression-bit contrast.
Original failed margins (-0.010/-0.035 ns) are preserved.

## What is included

ON/OFF each have 164 exact native sources, upstream overlay, ON captured Tcl/scripts/constraints/admissions/receipts, frozen Map/placed/final checkpoints, independent STA/ROM/KEY1 build evidence, actual functional netlist, and original failed/new successful reports.
The archive contains 457 payload files plus its payload manifest.

## Unverified boundaries

Internal covered STA passes, but external input-delay 56/output-delay 111 remain uncovered.
No board programming, Flash, continuous60 fresh frames, actual KEY1, optical or measured latency acceptance is claimed.
Old Brown A/B telemetry tools are not certified as adapted to Run8. Matched new test tooling is separate.
Captured controllers retain original absolute paths and expired stop guards. Cross-machine and fresh-P&R replay are not verified.
No earlier sources, bitstreams, vendor files or reports are replaced by this publication.
