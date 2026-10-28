"""One explicit offline cache-capacity variant; never a hardware plan/executor."""
from pathlib import Path
import run_lens1080_core_sim as base


def main():
    baseline="rtl/experimental/pipeline_gamma_frame_engine_1080_core.v"
    variant="rtl/experimental/pipeline_gamma_frame_engine_1080_core_index7.v"
    original=(base.ROOT/baseline).read_bytes()
    if original.count(b".INDEX_BITS(5)")!=1 or (base.ROOT/variant).read_bytes()!=original.replace(b".INDEX_BITS(5)",b".INDEX_BITS(7)"):
        raise ValueError("index7 candidate must differ by exactly one cache parameter")
    base.COMPILE=tuple(variant if name==baseline else name for name in base.COMPILE)
    base.HELPERS=(*base.HELPERS,"tools/run_lens1080_index7_sim.py")
    return base.main()


if __name__=="__main__":
    raise SystemExit(main())
