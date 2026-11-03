# Writer beat register fanout probe

The baseline and `syn_maxfan=32` variants both passed native PDS 2025.2 compile, ADS synthesis and device map. `verification.json` records complete synthesis register fanout, same-bit clone D/CE/CLK/R and initialization checks, mapped high-fanout summaries and file hashes. The large synthesis VM remains in the recorded local probe directory; its SHA-256 is included here.

The live writer attribute change is `a65636a57d7ec9cceabfbee3dbac42277c70cc1e68bd9004e3b27f8ae62c50a6`. Its functional tokens match frozen H after removing comments and the relocated CRC include path. The earlier `analysis.md` records the fallback assessment made before this attribute and the picture predecode were applied.

The top-level observation mux preserves every writer data bit while reducing external package IO. The initial direct-top attempt synthesized successfully but exceeded the package IO limit at device map; its failed artifacts remain separately in the local work directory.

`probe.py`, `verify.py` and the Tcl files retain original absolute workspace paths for provenance. Adjust these explicit paths and choose a fresh work directory to rerun elsewhere. Native duplicated-register behavior is locally checked; no whole-device formal equivalence or routed timing pass is claimed by this probe.
