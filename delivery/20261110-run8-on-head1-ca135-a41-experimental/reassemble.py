"""Reassemble exact original Run8 ZIP. No hardware or build operations."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
manifest = json.loads((root / "PARTS.json").read_text(encoding="utf-8"))
chunks = []
for part in manifest["parts"]:
    data = (root / part["name"]).read_bytes()
    if len(data) != part["bytes"] or hashlib.sha256(data).hexdigest() != part["sha256"]:
        raise SystemExit("Part verification failed: " + part["name"])
    chunks.append(data)
data = b"".join(chunks)
if len(data) != manifest["archive_bytes"] or hashlib.sha256(data).hexdigest() != manifest["archive_sha256"]:
    raise SystemExit("Reassembled archive verification failed")
output = root / manifest["archive"]
if output.exists():
    if output.read_bytes() != data:
        raise SystemExit("Refusing to overwrite a different existing archive: " + str(output))
else:
    with output.open("xb") as f:
        f.write(data)
print("PASS: " + str(output))
print("SHA256: " + manifest["archive_sha256"])
