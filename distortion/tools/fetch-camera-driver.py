"""Pin the official STMicroelectronics OV5640 reference driver, with license.

Reference material only. A register table must not be applied to the camera
until its silicon ID, oscillator and pixel-interface wiring are verified.
"""
import hashlib
import json
from pathlib import Path
import urllib.request

DEST = Path(__file__).resolve().parents[2] / "vendor/reference/st-ov5640"
REPO = "STMicroelectronics/stm32-ov5640"

def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "FPGA-local-reference"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()

def main():
    commit = json.loads(fetch(f"https://api.github.com/repos/{REPO}/commits/main"))["sha"]
    DEST.mkdir(parents=True, exist_ok=True)
    manifest = {"repo": f"https://github.com/{REPO}", "commit": commit, "files": []}
    for name in ("ov5640.c", "ov5640.h", "ov5640_reg.h", "LICENSE.md"):
        url = f"https://raw.githubusercontent.com/{REPO}/{commit}/{name}"
        data = fetch(url)
        (DEST / name).write_bytes(data)
        manifest["files"].append({"name": name, "url": url, "sha256": hashlib.sha256(data).hexdigest()})
        print(f"Saved {name}: {len(data)} bytes")
    (DEST / "sources.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Pinned ST OV5640 reference commit {commit}")

if __name__ == "__main__":
    main()
