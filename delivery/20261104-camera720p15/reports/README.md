# Original timing and utilization reports

`timing/camera720_view_toggle_top.rtr.gz` and `_exception.rtr.gz` preserve the complete native final-export-a reports. Decompress with any gzip reader. Their uncompressed identities and byte counts are in `../reports-manifest.json`; the large original files are deliberately retained as gzip. `timing/summary-first-232-lines.txt` is an exact byte excerpt of the full report, not a replacement for it.

The final timing input ADF is `f31e112a1764d8175cce5cac013c2611b4032ebcd615219c3dfc763cf338ff2d`, linked by the program receipt to bitstream SHA256 `0ca6d19bf074c73cba0346a22e54ba3afb99a595728e6420a1cbb767b963dfe5`.

For utilization, use `utilization/place_route/run_route_optimize.log` (original RouteOptimize stage): LUT 14910, FF 18596, DRM 16.5, APM 70, IO 130. FF and LUT totals sum CLMA and CLMS rows. Percentages in summary.json are recomputed from counts and capacities; the native log rounds percentages upwards. Map reports are preserved separately and must not be mixed with this stage.

Binding chain: original build-a execution-result records the exact RouteOptimize log SHA and ADF `7a75c09e...`; hold-route-c changes two routing branches, preserving functional and placement semantics, yielding `a79c822b...`; reset-save-a and effect-a preserve cells, placements and routes, yielding final `f31e112a...`. The final-export and bit/program receipts complete the chain. This package does not claim a newly executed resource report on the final ADF. See the original receipts in `binding/`.

The ten internal corner/type summaries all pass. This does not convert external HDMI/camera AC, physical reset or board fault counters into completed acceptance. No EDA or hardware was run while assembling this export.
