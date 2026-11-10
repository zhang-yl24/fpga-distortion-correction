"""Read-only raw-byte verification of this minimal first-party overlay."""
from pathlib import Path
import hashlib
import json

root = Path(__file__).resolve().parent
manifest = json.loads((root / "SOURCE_MANIFEST.json").read_text(encoding="utf-8"))
assert manifest["scope"] == "all_published_files_except_SOURCE_MANIFEST.json"
seen = set()
for item in manifest["files"]:
    rel = Path(item["path"])
    assert not rel.is_absolute() and ".." not in rel.parts and str(rel) not in seen
    seen.add(str(rel))
    data = (root / rel).read_bytes()
    assert len(data) == item["bytes"], f"size mismatch: {rel}"
    assert hashlib.sha256(data).hexdigest() == item["sha256"], f"SHA256 mismatch: {rel}"
actual = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()
          and p.name != "SOURCE_MANIFEST.json" and "__pycache__" not in p.parts}
assert actual == seen, f"unexpected/missing files: {actual ^ seen}"
rtl = json.loads((root / "RTL_IDENTITY.json").read_text(encoding="utf-8"))
for item in rtl["files"]:
    assert item in manifest["files"]
words = (root / "rom/run8_intervals_30bit.mem").read_text(encoding="ascii").splitlines()
assert len(words) == 266 and all(0 <= int(w, 16) < (1 << 30) for w in words)
print(f"PASS_OVERLAY_RAW_HASHES files={len(seen)} rtl_assets={len(rtl['files'])} rom_words={len(words)}")
