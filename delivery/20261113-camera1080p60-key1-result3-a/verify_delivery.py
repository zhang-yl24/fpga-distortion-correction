"""Offline integrity check. Never opens UART, programs FPGA or runs build tools."""
from pathlib import Path
import hashlib
import json
import zipfile

root = Path(__file__).resolve().parent
manifest = json.loads((root / 'DELIVERY_MANIFEST.json').read_text(encoding='utf-8'))
for name, entry in manifest['files'].items():
    path = root / name
    data = path.read_bytes()
    if len(data) != entry['bytes'] or hashlib.sha256(data).hexdigest() != entry['sha256']:
        raise SystemExit('FAILED: ' + name)
    if path.suffix == '.zip':
        with zipfile.ZipFile(path) as z:
            if z.testzip() is not None:
                raise SystemExit('FAILED ZIP CRC: ' + name)
    print('OK:', name)
print('Delivery bytes verified. No hardware, loaded-image authentication or FPS claim.')
