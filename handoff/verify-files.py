"""Read-only SHA256 verification. Does not build, test RTL or access hardware."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest().upper()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', default='handoff/manifests/repository-files.json')
    args = parser.parse_args()
    record = json.loads((ROOT / args.manifest).read_text(encoding='utf-8-sig'))
    failures = []
    for entry in record['files']:
        path = (ROOT / entry['path']).resolve()
        if not path.is_relative_to(ROOT):
            failures.append({'path': entry['path'], 'error': 'outside workspace'})
        elif not path.is_file():
            failures.append({'path': entry['path'], 'error': 'missing'})
        elif path.stat().st_size != entry['bytes'] or digest(path) != entry['sha256']:
            failures.append({'path': entry['path'], 'error': 'size or SHA256 differs'})
    print(json.dumps({'passed': not failures, 'checked': len(record['files']),
                      'failures': failures}, ensure_ascii=False, indent=2))
    return 1 if failures else 0

if __name__ == '__main__':
    sys.exit(main())
