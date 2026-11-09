"""Offline-only: verify 75 frozen native inputs, then apply seven exact overlays."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--aa-native', required=True, type=Path,
                        help='Explicit frozen AA native directory containing source/ and b4/')
    parser.add_argument('--output', required=True, type=Path, help='New, nonexistent workspace')
    args = parser.parse_args()
    out = args.output.resolve()
    frozen = args.aa_native.resolve()
    for protected in (frozen, ROOT.resolve()):
        if out == protected or protected in out.parents:
            parser.error('Output must be outside the frozen AA native tree and publication directory')
    identity = json.loads((ROOT / 'PUBLIC_IDENTITY.json').read_text())
    changes = json.loads((ROOT / 'SOURCE_IDENTITY.json').read_text())['Sources']
    verified = {}
    for entry in identity:
        relative = Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Unsafe manifest path')
        data = (args.aa_native / relative).read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
        if sha(data) != entry['sha256'] or blob != entry['git_blob_sha1']:
            raise ValueError('Frozen AA identity mismatch: ' + str(relative))
        verified[str(relative)] = data
    overlays = {}
    for relative, entry in changes.items():
        data = (ROOT / 'overlays' / relative).read_bytes()
        if sha(verified[relative]) != entry['AA_SHA256'] or sha(data) != entry['AF54_SHA256']:
            raise ValueError('Overlay identity mismatch: ' + relative)
        overlays[relative] = data
    if len(verified) != 75 or len(overlays) != 7:
        raise ValueError('Unexpected source counts')
    out.mkdir(parents=True, exist_ok=False)
    for tree in ('baseline', 'candidate'):
        for relative, data in verified.items():
            target = out / tree / 'native' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(overlays.get(relative, data) if tree == 'candidate' else data)
    for name in ('run.py', 'check_traversal.py', 'SOURCE_IDENTITY.json', 'CONFIGURATION.json'):
        shutil.copyfile(ROOT / name, out / name)
    shutil.copytree(ROOT / 'tests', out / 'tests')
    (out / 'MATERIALIZED.json').write_text(json.dumps({'verified_native_inputs':75,
        'changed':7, 'unchanged':68, 'baseline_commit':'ea180eb7b57b8a0115e2ce793553034ca5b65a24',
        'network':False, 'vendor_tools':False}, indent=2)+'\n')
    print('Verified 75 inputs; applied seven overlays. Workspace:', out)

if __name__ == '__main__':
    main()
