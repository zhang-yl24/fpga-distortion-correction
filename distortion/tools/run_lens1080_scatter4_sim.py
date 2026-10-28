"""One fixed INDEX7/scatter4 offline candidate; no synthesis or hardware plan."""
from pathlib import Path
import run_lens1080_core_sim as base


def main():
    replacements={
        "rtl/experimental/pipeline_gamma_frame_engine_1080_core.v":"rtl/experimental/pipeline_gamma_frame_engine_1080_scatter4.v",
        "tests/tb_lens1080_core.sv":"tests/tb_lens1080_scatter4.sv"}
    base.COMPILE=tuple(replacements.get(name,name) for name in base.COMPILE)+(
        "rtl/experimental/ddr_compact_neighbour_cache_scatter4.v",
        "rtl/experimental/ddr_remap_sample_scatter4.v",
        "rtl/experimental/rotated_remap_core_gamma_scatter4.v")
    base.TOP="tb_lens1080_scatter4"
    base.SNAPSHOT="lens1080_scatter4_snapshot"
    base.HELPERS=(*base.HELPERS,"tools/run_lens1080_scatter4_sim.py")
    return base.main()


if __name__=="__main__":
    raise SystemExit(main())
