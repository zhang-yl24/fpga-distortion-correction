"""Read-only verification of bundled files using package-relative paths."""
from pathlib import Path
import argparse
import hashlib
import json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="portable-evidence-manifest-e.json")
    args = parser.parse_args()
    package = Path(__file__).resolve().parent
    manifest_path = (package / args.manifest).resolve()
    if not manifest_path.is_relative_to(package):
        raise ValueError("manifest must stay inside this package")
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    if value["Schema"] != "hdmi-camera-fisheye-fill8r3s3-portable-archive-v1":
        raise ValueError("unexpected manifest schema")
    seen = set()
    for row in value["BundledFiles"]:
        relative = Path(row["Path"])
        target = (package / relative).resolve()
        if relative.is_absolute() or ".." in relative.parts or not target.is_relative_to(package):
            raise ValueError("nonportable or escaped file path")
        if row["Path"] in seen:
            raise ValueError("duplicate archive entry")
        seen.add(row["Path"])
        if target.stat().st_size != row["Bytes"]:
            raise ValueError("size mismatch: " + row["Path"])
        if hashlib.sha256(target.read_bytes()).hexdigest() != row["SHA256"]:
            raise ValueError("SHA mismatch: " + row["Path"])
    print(json.dumps({"Passed": True, "BundledFilesVerified": len(seen),
                      "LargePhysicalProofsBundled": False, "HardwareAccessed": False}))


if __name__ == "__main__":
    main()
