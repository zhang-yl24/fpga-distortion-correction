# tile8 64 KiB cache evaluation — not released for board use

This candidate starts from the source-bound, board-tested 1080p15 tile8 release (baseline commit `a6558c9987528455bd3102b5ac98729452f2ec8f`). The only RTL change is the engine cache `INDEX_BITS` from 7 to 8. HDMI configuration, input qualification, reset logic, pins, clock frequencies, frame ownership, and display scheduling retain their released source bytes. Five include paths are relocated. The released `INPUT_TIMING_CONFIGURED=1` is retained.

## Results

The sparse independent pixel regression passed at both capacities, including stalls, conflicts, frame drain, reset and six error cases. A full 1920×1080 coordinate trace checked all four RGB neighbours and fractional coordinates for every output under deterministic DDR/output stalls. Block reads decreased from 49,465 to 37,483 (24.2%); simulated cache completion decreased from 4,683,832 to 4,235,790 cycles (9.6%). These are cache-module results, not measured whole-system FPS. Display scheduling can retain 15 FPS despite shorter processing time.

PDS 2025.2 completed synthesis, map, placement, route, hold optimization and two-corner timing. All 144 mapped/routed pins match the original FDC. Fresh timing did **not** pass: slow setup -6.331 ns, fast hold -1.903 ns, with additional recovery/removal failures. Cross-domain and reset physical treatment requires completion; no broad timing exclusions were added. No new bitstream was generated or programmed. Do not substitute this candidate for the working rollback bitstream.

There are also genuine same-clock setup failures in the raw timing report: input_pixel -0.495 ns, pixel_clk -0.149 ns, and ddrphy_sysclk -1.639 ns. The failure cannot be attributed solely to missing cross-domain exceptions. Timing optimization and independent validation remain required before a board candidate can be issued.

The public tile8 rebuild instructions explicitly state that ordinary rebuilds do not reproduce its complete final physical flow. The release receipt references `distortion/work/hdmi-camera-fisheye-tile8-20261103-a/physical-v2-a/result.json` and `input.adf`; the corresponding directory was not found in the inspected local source copies. Recovering that directory together with its stage Tcl, exact scope/constraint inputs and referenced proofs would provide the original physical treatment for review. It must be revalidated against this new netlist and tool version.

## Rebuild source preparation

`python prepare_build.py --output D:/t8s/new-build` verifies the manifest and produces 111 source inputs plus `implement.tcl`. Use a fresh short path. Preparation does not run EDA. Build with the compatible PDS installation using `pds_shell.exe -file D:/t8s/new-build/implement.tcl -work_dir D:/t8s/new-build -project_name hdmi_camera_fisheye_top`. The script does not generate a bitstream. Completion of the tool command does not imply timing acceptance; review all timing tables separately.

For the full-frame cache regression, install NumPy and OpenCV in the test Python environment, set `FPGA_VIVADO_BIN` to the Vivado simulator bin directory, then run `python tests/run_tile8_full_cache.py`. It creates a fresh `tests/tile8-full-cache` directory and checks the simulated block-read counts against the access model. The original sparse regression results are retained as evidence; the full-frame bench is included for reproduction.

The stable rollback SHA256 is `1236d82f113e1ddb1c5e24502ed1aa03e4758db0a7d6ff17bf9216f0fbd0e4f3`. The failed O/P bitstream is a different design and is not the baseline of this candidate.
