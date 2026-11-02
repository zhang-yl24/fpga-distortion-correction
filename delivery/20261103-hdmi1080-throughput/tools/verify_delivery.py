"""Verify sealed candidate bytes and bind recorded tests to current RTL sources."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def verify_sources(bindings, base):
    for name, digest in bindings.items():
        name = name.replace('\\', '/')
        if '/delivery/' in name:
            path = REPO / 'delivery' / name.split('/delivery/', 1)[1]
        else:
            path = base / name
        if sha(path) != digest:
            raise ValueError('Recorded source changed: ' + str(path))


def verify():
    manifest = read(ROOT / 'FILE_MANIFEST.json')
    for name, digest in manifest['files'].items():
        path = (ROOT / name).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or sha(path) != digest:
            raise ValueError('Delivery file missing or changed: ' + name)
    for variant in ('baseline', 'writer', 'cache', 'both'):
        report = read(ROOT / 'evidence/engine' / variant / 'report.json')
        if not report['passed'] or report['source_drift']:
            raise ValueError('Engine report failed')
        verify_sources(report['source_sha256'], REPO)
        scalar = REPO / 'distortion/tools/generate-brown-vectors.py'
        if sha(scalar) != report['fixtures']['scalar_source_sha256']:
            raise ValueError('Independent scalar reference changed')
    writer = read(ROOT / 'evidence/writer/writer-ab.json')
    if not writer['passed'] or len(writer['cases']) != 25 or not all(r['passed'] for r in writer['cases']):
        raise ValueError('Writer regression incomplete')
    verify_sources(writer['source_sha256'], REPO)
    cache = read(ROOT / 'evidence/cache/cache-results.json')
    if not cache['passed'] or len(cache['cases']) != 4 or not all(r['passed'] for r in cache['cases']):
        raise ValueError('Cache regression incomplete')
    verify_sources(cache['source_sha256'], ROOT.parent)
    mode = read(ROOT / 'evidence/mode/result.json')
    if not mode['passed']:
        raise ValueError('Mode regression failed')
    verify_sources(mode['source_sha256'], ROOT)
    return {'verified_files': len(manifest['files']), 'recorded_rtl_sources_match': True,
            'engine_variants': 4, 'writer_cases': 25, 'cache_cases': 4,
            'hardware_verified': False, 'full_board_timing_verified': False}


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
