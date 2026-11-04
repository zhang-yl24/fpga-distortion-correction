"""Read-only verification of the selected 720p15 sources, bit and reports."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os


def main():
    root = Path(__file__).resolve().parent
    if os.name == 'nt' and not str(root).startswith('\\\\?\\'):
        root = Path('\\\\?\\' + str(root))
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    counts = {}
    for filename in ('source-manifest.json', 'reports-manifest.json'):
        data = json.loads((root / filename).read_text(encoding='utf-8'))
        seen = set()
        for entry in data['files']:
            relative = PurePosixPath(entry['path'])
            if relative.is_absolute() or '..' in relative.parts or ':' in entry['path'] or '\\' in entry['path'] or entry['path'] in seen:
                raise ValueError('Unsafe or duplicate manifest path')
            seen.add(entry['path'])
            path = root.joinpath(*relative.parts)
            if path.stat().st_size != entry['bytes'] or digest(path) != entry['sha256']:
                raise ValueError('File mismatch: ' + entry['path'])
        counts[filename] = len(seen)
    identity = json.loads((root / 'identity.json').read_text(encoding='utf-8'))
    bit = root / identity['bitstream']['path']
    expected = '0ca6d19bf074c73cba0346a22e54ba3afb99a595728e6420a1cbb767b963dfe5'
    if bit.stat().st_size != 3791112 or digest(bit) != expected:
        raise ValueError('720p15 released bitstream mismatch')
    audit = json.loads((root / 'audit.json').read_text(encoding='utf-8'))
    for key in ('source_manifest', 'reports_manifest'):
        if digest(root / audit[key]['path']) != audit[key]['sha256']:
            raise ValueError('Audit/manifest mismatch: ' + key)
    print(json.dumps({'passed': True, 'files': counts, 'bitstream_sha256': expected,
                      'new_eda_executed': False, 'hardware_accessed': False}, indent=2))


if __name__ == '__main__':
    main()
