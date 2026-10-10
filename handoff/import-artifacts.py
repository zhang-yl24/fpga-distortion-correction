"""Safely import a handoff ZIP, checking the published SHA256 before extraction."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--replace', action='store_true', help='Allow replacing differing local files')
    args = parser.parse_args()
    releases = json.loads((ROOT/'handoff/manifests/release-assets.json').read_text())
    expected = next((e for e in releases['assets'] if e['name'] == args.archive.name), None)
    if not expected:
        raise ValueError('Archive is not in the published release asset manifest')
    h = hashlib.sha256()
    with args.archive.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    if h.hexdigest().upper() != expected['sha256']:
        raise ValueError('Archive SHA256 mismatch; no files extracted')
    with zipfile.ZipFile(args.archive) as archive:
        members = archive.infolist()
        for item in members:
            path = (ROOT/item.filename).resolve()
            if not path.is_relative_to(ROOT) or '.git' in Path(item.filename).parts:
                raise ValueError('Unsafe archive member: '+item.filename)
            if path.exists() and not item.is_dir() and not args.replace:
                if hashlib.sha256(path.read_bytes()).digest() != hashlib.sha256(archive.read(item)).digest():
                    raise ValueError('Local file differs; refusing overwrite: '+item.filename)
        for item in members:
            if item.is_dir():
                continue
            path = ROOT/item.filename
            path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as source, path.open('wb') as dest:
                shutil.copyfileobj(source, dest)
            stamp = time.mktime((*item.date_time, 0, 0, -1))
            os.utime(path, (stamp, stamp))
    print('Imported', len(members), 'entries from', args.archive.name)

if __name__ == '__main__':
    main()
