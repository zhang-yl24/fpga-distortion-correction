"""Strict single-file overlay preparation. No EDA, network or hardware access."""
import argparse
import hashlib
from pathlib import Path

CASES = {
    "ac": ("ff5e551c13083cecf9325b6acef0a00b58f7f1776cd7f5dbec341e52f2082088", "e2d641a61e20f375de0202528915e626dd3e7c43e8f40473d5308bd39cbd25e5", "d256_runtime_prefetch_cache_AC.sv"),
    "ad": ("3b39508ebfb7701e379fc53d980c7790f40ce397a2647cd36ce845c417a2b684", "5cb550036a03c995e85eb1227e84b250d6e7d715f2cee3516aabcc5483e40170", "vendor-ca-debug-priority_AD.rcf"),
}
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("kind", choices=CASES)
    p.add_argument("baseline", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    old, new, filename = CASES[a.kind]
    candidate = Path(__file__).resolve().parent / filename
    original = a.baseline.read_bytes()
    replacement = candidate.read_bytes()
    assert hashlib.sha256(original).hexdigest() == old, "baseline SHA mismatch"
    assert hashlib.sha256(replacement).hexdigest() == new, "candidate SHA mismatch"
    assert a.output.resolve() != a.baseline.resolve(), "do not overwrite baseline"
    # Exclusive create: no existing file, frozen input or running cohort overwritten.
    with a.output.open("xb") as f:
        f.write(replacement)
    print("PREPARED_ONLY", a.kind, len(replacement), new)
if __name__ == "__main__":
    main()
