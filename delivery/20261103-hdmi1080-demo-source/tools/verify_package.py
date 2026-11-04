"""Verify the delivered immutable source subset, without EDA or hardware."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def safe_relative(root, rel):
    p = (Path(root) / rel).resolve()
    if not p.is_relative_to(Path(root).resolve()):
        raise ValueError('Path escapes root: ' + rel)
    return p

def verify(root=ROOT):
    root = Path(root).resolve()
    package_index = root / 'PACKAGE_MANIFEST.json'
    if package_index.is_file():
        package = json.loads(package_index.read_text(encoding='utf-8'))
        expected_files = {r['path'] for r in package['files']}
        actual_files = {p.relative_to(root).as_posix() for p in root.rglob('*')
                        if p.is_file() and not any(part in ('_build','__pycache__','.pytest_cache')
                                                  for part in p.relative_to(root).parts)
                        and p != package_index}
        if actual_files != expected_files:
            raise ValueError('Package file inventory differs')
        for r in package['files']:
            p = safe_relative(root,r['path'])
            if p.stat().st_size!=r['bytes'] or sha(p)!=r['sha256']:
                raise ValueError('Package file missing/changed: '+r['path'])
    manifest = json.loads((root / 'manifests/source-manifest.json').read_text(encoding='utf-8'))
    rows = manifest['files']
    if len(rows) != manifest['source_count'] or len({r['path'] for r in rows}) != len(rows):
        raise ValueError('Source inventory inconsistent')
    included = []
    for r in rows:
        p = safe_relative(root / 'native', r['path'])
        if r['disposition'] == 'included_source':
            if not p.is_file() or p.stat().st_size != r['bytes'] or sha(p) != r['sha256']:
                raise ValueError('Source missing/changed: ' + r['path'])
            included.append(r['path'])
        elif r['disposition'] == 'external_dependency':
            if p.exists():
                raise ValueError('External dependency entered upload subset: ' + r['path'])
        else:
            raise ValueError('Unknown source disposition')
    actual = {p.relative_to(root / 'native').as_posix() for p in (root / 'native').rglob('*') if p.is_file()}
    if actual != set(included):
        raise ValueError('Unmanifested native payload')
    recipe = json.loads((root / 'manifests/build-recipe.json').read_text(encoding='utf-8'))
    declared = recipe['designs'] + recipe['constraints']
    if any(p not in {r['path'] for r in rows} for p in declared):
        raise ValueError('Unbound build declaration')
    return {'included_sources_verified':len(included),
            'external_dependencies_required':len(rows)-len(included),
            'full_build_available_without_dependencies':False,
            'eda_executed':False, 'hardware_accessed':False}

if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
