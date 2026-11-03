"""One entry point for isolated, byte-preserved FPGA deliveries (no hardware access)."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def catalog():
    return json.loads((ROOT / 'project-catalog.json').read_text(encoding='utf-8'))


def run(args):
    subprocess.run([sys.executable, '-B', *map(str, args)], cwd=ROOT, check=True)


def variant(name):
    for item in catalog()['variants']:
        if item['id'] == name:
            return item
    raise ValueError('Unknown variant: ' + name)


def audit():
    data = catalog()
    errors = []
    for item in data['variants']:
        folder = ROOT / item['path']
        if not folder.is_dir():
            errors.append('Missing variant: ' + item['path'])
        if item['portable_build']:
            for name in ('verify_source.py', 'prepare_build.py', 'source-manifest.json'):
                if not (folder / name).is_file():
                    errors.append('Missing build input: ' + str(folder / name))
    for release in data['releases']:
        for asset in release['assets']:
            if not re.fullmatch(r'sha256:[0-9a-f]{64}', asset['digest'] or ''):
                errors.append('Invalid release digest: ' + asset['name'])
    # ZIP exports remain usable without .git; ancestry is checked in a checkout.
    git_available = (ROOT / '.git').exists()
    if git_available:
        for branch in data['branches']:
            result = subprocess.run(['git', 'merge-base', '--is-ancestor', branch['commit'], 'HEAD'], cwd=ROOT, capture_output=True)
            if result.returncode:
                errors.append('Unintegrated branch: ' + branch['ref'] + ' ' + branch['commit'])
    if errors:
        raise ValueError('\n'.join(errors))
    print(json.dumps({'catalog_verified': True, 'variants': len(data['variants']), 'branches': len(data['branches']), 'ancestry_checked': git_available, 'release_assets': sum(len(r['assets']) for r in data['releases'])}, indent=2))


def safe_output(path):
    output = Path(path).resolve()
    # Bound headers are quoted Verilog strings; Tcl uses brace-delimited paths.
    # Quotes and line/control characters cannot be inserted into either grammar.
    if any(c in output.as_posix() for c in '{}"\r\n\x00') or any(ord(c) < 32 for c in output.as_posix()):
        raise ValueError('Choose an output path without quotes, braces or control characters.')
    if output.exists():
        raise ValueError('Output already exists; choose a new build directory.')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('list')
    sub.add_parser('audit')
    for command in ('verify', 'prepare'):
        p = sub.add_parser(command)
        p.add_argument('--variant', default='tile8')
        if command == 'prepare':
            p.add_argument('--output', required=True)
    p = sub.add_parser('check-asset', help='Verify an already downloaded release file; does not download or unpack.')
    p.add_argument('--tag', required=True)
    p.add_argument('--file', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'list':
        for item in catalog()['variants']:
            print(f"{item['id']:14} {item['status']:48} {item['path']}")
        return
    if args.command == 'audit':
        audit()
        return
    if args.command == 'check-asset':
        assets = [a for r in catalog()['releases'] if r['tag'] == args.tag for a in r['assets'] if a['name'] == args.file.name]
        if len(assets) != 1:
            raise ValueError('Tag/file combination is not in the release catalog.')
        asset = assets[0]
        if args.file.stat().st_size != asset['bytes']:
            raise ValueError('Release asset size differs.')
        with args.file.open('rb') as handle:
            digest = 'sha256:' + hashlib.file_digest(handle, 'sha256').hexdigest()
        if digest != asset['digest']:
            raise ValueError('Release asset SHA256 differs.')
        print('Release asset verified: ' + args.file.name)
        return
    item = variant(args.variant)
    if not item['portable_build']:
        raise ValueError('Use the version-specific instructions in ' + item['path'] + '; it is not selected for the portable build flow.')
    folder = ROOT / item['path']
    if args.command == 'prepare':
        output = safe_output(args.output)
        run([folder / 'prepare_build.py', '--repo', ROOT, '--output', output])
    else:
        run([folder / 'verify_source.py', '--repo', ROOT])
        if args.variant == 'tile8':
            run([ROOT / 'distortion/results/hdmi-camera-fisheye-tile8-20261103-a/verify_archive_portable.py', '--manifest', 'portable-evidence-manifest-c.json'])
            run([ROOT / 'distortion/tools/verify_fisheye_tile8_archive.py'])


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
