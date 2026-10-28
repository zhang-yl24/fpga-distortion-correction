"""Isolated rowpipe + CDC-reset system regression; no PDS or hardware access.

The rowpipe unit passed independently. This integration candidate still needs
its own small, native eight-frame and final routed timing evidence. All fixture,
fault, reset, CRC, scan and same-source small gates are inherited unchanged.
"""
from contextlib import contextmanager
from pathlib import Path
import re

import run_board1080_system_sim as system


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "build/board1080-rowpipe-reproduction"
ORIGINAL_CACHE = "rtl/experimental/ddr_compact_neighbour_cache_scatter4.v"
CANDIDATE_CACHE = "rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v"
ORIGINAL_SAMPLER = "rtl/experimental/ddr_remap_sample_scatter4.v"
CANDIDATE_SAMPLER = "rtl/experimental/ddr_remap_sample_scatter4_rowpipe.v"
ORIGINAL_SYSTEM = "rtl/experimental/hdmi1080_video_system.v"
CDC_SYSTEM = "rtl/experimental/hdmi1080_video_system_cdc_reset.v"
PROOF = "tests/rowpipe-candidate-source.json"
SELF = "tools/run_board1080_rowpipe_system_sim.py"
SAMPLER_NOTE = (b"// ISOLATED ROWPIPE INTEGRATION CANDIDATE; not native-frame/STA/hardware accepted.\n"
                b"// Same sampler module name: compile this file OR the original sampler, never both.\n")


def configuration(root, compile_names, frozen, helpers):
    """Validate the exact isolated replacement before changing any runner state."""
    root = Path(root).resolve()
    names = tuple(compile_names)
    if len(set(names)) != len(names):
        raise ValueError("duplicate compilation source in original closure")
    replacements = {ORIGINAL_CACHE: CANDIDATE_CACHE, ORIGINAL_SAMPLER: CANDIDATE_SAMPLER,
                    ORIGINAL_SYSTEM: CDC_SYSTEM}
    if any(names.count(name) != 1 for name in replacements):
        raise ValueError("original cache, sampler and system must each occur once")
    if any(name in names for name in replacements.values()):
        raise ValueError("candidate and original compilation closures must be mutually exclusive")
    original = root / ORIGINAL_CACHE
    candidate = root / CANDIDATE_CACHE
    if (ORIGINAL_CACHE not in frozen or not original.is_file() or not candidate.is_file()
            or system.sha(original) != frozen[ORIGINAL_CACHE]):
        raise ValueError("original frozen cache is missing or changed")
    proof = system.load(root / PROOF)
    candidate_hash = proof.get("CandidateSHA256")
    if (proof.get("BaseSource") != ORIGINAL_CACHE or proof.get("Candidate") != CANDIDATE_CACHE
            or proof.get("BaseSHA256") != frozen[ORIGINAL_CACHE]
            or not isinstance(candidate_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", candidate_hash)
            or system.sha(candidate) != candidate_hash
            or proof.get("PublicFIFO2NormalizedBytesEqual") is not True
            or proof.get("SlowStateMachineBytesEqual") is not True
            or type(proof.get("AddedElasticStages")) is not int or proof["AddedElasticStages"] != 1):
        raise ValueError("rowpipe candidate differs from the bound source proof")
    old_instance = b"    ddr_neighbour_cache_scatter4 #("
    new_instance = b"    ddr_neighbour_cache_scatter4_rowpipe #("
    original_sampler = (root / ORIGINAL_SAMPLER).read_bytes()
    if (original_sampler.count(old_instance) != 1
            or (root / CANDIDATE_SAMPLER).read_bytes() != SAMPLER_NOTE + original_sampler.replace(old_instance, new_instance, 1)):
        raise ValueError("rowpipe sampler differs beyond its one cache instance and isolation note")
    compiled = tuple(replacements.get(name, name) for name in names)
    updated_frozen = {name: digest for name, digest in frozen.items() if name != ORIGINAL_CACHE}
    updated_frozen[CANDIDATE_CACHE] = candidate_hash
    updated_helpers = tuple(dict.fromkeys((*helpers, SELF, PROOF, ORIGINAL_SAMPLER)))
    return {"COMPILE": compiled, "FROZEN": updated_frozen, "HELPERS": updated_helpers}


@contextmanager
def configured_system():
    previous = system.fixtures.previous
    values = configuration(ROOT, system.COMPILE, previous.FROZEN, system.HELPERS)
    saved = system.BASE, system.COMPILE, system.HELPERS, previous.FROZEN
    try:
        system.BASE, system.COMPILE, system.HELPERS = BASE, values["COMPILE"], values["HELPERS"]
        previous.FROZEN = values["FROZEN"]
        yield
    finally:
        system.BASE, system.COMPILE, system.HELPERS, previous.FROZEN = saved


def run(args):
    with configured_system():
        return system.run(args)


def main(argv=None):
    with configured_system():
        return system.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
