# Rebuild AA locally

Place this `rebuild/` directory next to `native/` and `constraints/` in the project checkout. Python 3 is needed for the offline check and stage launcher. Use a legitimate installed PDS toolchain and your own normal license setup. The scripts inherit the user's environment and contain no license paths or license contents.

First generate or legally restore the required vendor IP using the supplied IP regeneration instructions and parameter tables. DDR is HMIC_S 1.10, generated originally by IP Compiler 2022.2-SP6.4 build 146967. A generic PDS 2025 installation must not be assumed to contain this generator. Keep the specified `native/source/platform/video_base/ipcore/` layout and `native/source/board/bringup_pll.v`. No placeholder or black-box replacement is supplied.

Run this first; it launches no EDA:

```text
python rebuild/verify_sources.py
```

It lists every missing file and stops with exit code 2 until the required 155 native files and their includes/IDF synthesis references are present. `source-list.txt` is the relative required-file list; `design_imports.txt` is the exact ordered list of 68 direct design imports. A successful file check does not prove vendor IP byte identity, legal entitlement, synthesis equivalence, timing closure, or hardware operation.

After closure is complete, the following explicit commands start new builds. Replace the example tool and checkpoint names with your locally installed executable and the actual outputs from the preceding stage. Each command uses a fresh `build-repro/<stage>/` directory and refuses to overwrite an existing directory.

```text
python rebuild/run_build.py map --pds pds_shell
python rebuild/run_build.py place --pds pds_shell --input-adf build-repro/map/prj_tasks/pnr_1/device_map/board1080_top_map.adf
python rebuild/run_build.py route --pds pds_shell --input-adf build-repro/place/prj_tasks/pnr_1/place_route/board1080_top_plc.adf
python rebuild/run_build.py sta --pds pds_shell --input-adf build-repro/route/prj_tasks/pnr_1/place_route/board1080_top_pnr.adf
python rebuild/run_build.py bitgen --pds pds_shell --input-adf build-repro/route/prj_tasks/pnr_1/place_route/board1080_top_pnr.adf
```

The checkpoint layout above follows the original PDS output layout; use the actual generated Map ADF if your tool installation changes this layout, rather than renaming or substituting another project's file. `--pds` accepts an executable file path or executable name found on PATH, not a tool directory. Run stages serially and review each log, final checkpoint, actual reports and constraint coverage before proceeding. Keep the route stage's final optimized `*_pnr.adf` unchanged between STA and bitgen. Exit code zero alone is not timing signoff; missing or zero-coverage checks are not passes. These scripts do not infer a connection between an arbitrary supplied ADF and source tree.

The independent STA stage preserves the original negative-path report selection: `min_max`, maximum 10000 paths, slack below 0, worst 1, exceptions and maximum skew requested. It does not run route or change constraints. The bitgen stage only emits an offline SRAM artifact. None of these scripts opens COM, programs a board, uses JTAG/Flash, accesses the network, or runs functional simulation.

## Preserved build configuration

* Logos2, PG2L100H, speed grade -6, FBG676; TOP `board1080_top`; SystemVerilog; ADS synthesis option 2.
* All 68 direct imports retain their original order. Public includes are relative to the `native/` search root; this replaces host-specific include locations without changing the referenced include contents.
* The Map stage loads the original diagnostic FDC, DDR clock relation FDC, two-net vendor DDR route priority RCF and KEY1 FDC. Physical stages load the same timing/pin FDCs plus the 145-port paired PCF and four-net merged route priority RCF. No clock, IO, hold, asynchronous group or multicycle constraint is relaxed.
* Placement seed 2, decongestion 1. Route optimization fixes hold with `TRUE`, clock-path-cross-SRB threshold 100 and clock-tree threshold 100.
* The four physical priority nets remain the two `ddrphy_ioclk_gate` nets, `all_group_ca_dly`, and `debug_data [273]`. UART TX C24, RX B24, KEY1 C23.

The original build supplied no compile-time TOP parameter overrides. Keep the published source defaults and instance arguments: STARTUP_SCAN_ALIGN=1, STARTUP_SCAN_GUARD_CYCLES=0, STARTUP_PRIME_NEXT_SOURCE=1, RATIONAL_BROWN_PROFILE=1, R34_ENABLE_GAMMA=0, STATS_ENABLE=1, CORE_HZ=125000000, CORE_PRIORITY=1, INDEX_BITS=7, QUERY_DEPTH=4096, MACRO_TILE_HEIGHT=32, GROUP_WIDTH=64, RESULT_BANKS=2. These names span TOP defaults and selected instance parameters; they are not all TOP parameters. The verifier checks the corresponding TOP source expressions without adding overrides.

Public source relocation and locally regenerated vendor IP can change implementation results. Rebuilding with the same options does not guarantee the delivered bitstream or 3 ps setup margin will be reproduced. Review the supplied timing report limitations and independently review every newly generated implementation.
