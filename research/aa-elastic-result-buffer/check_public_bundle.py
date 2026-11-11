#!/usr/bin/env python3
"""Check exact allowlist, content hashes, private-path markers and recursive ZIP members.
These checks complement source provenance review; marker absence alone proves no license.
"""
import argparse
import io
import json
from pathlib import Path
import re
import stat
import sys
import zipfile
sys.dont_write_bytecode = True
from prepare_native import Refusal, need, rel, read, sha, inventory, json_load

MARKERS = [
    ('compiler_source_excerpt', re.compile(rb'^\s*\d+\s*\|', re.M)),
    ('proprietary_notice', re.compile(rb'pango\s+proprietary', re.I)),
    ('vendor_copyright', re.compile(rb'^[^\r\nA-Za-z]{0,12}copyright[^\r\n]{0,120}pango|^[^\r\nA-Za-z]{0,12}pango[^\r\n]{0,120}copyright', re.I | re.M)),
    ('encrypted_source', re.compile(rb'`pragma\s+protect|beg[i]n_protected|BEGIN RSA PRIVATE [K]EY', re.I)),
    ('private_absolute_path', re.compile(rb'/(?:workspace|home|Users|mnt/data)/|[A-Za-z]:[\\/](?:Users|fpga|work)', re.I)),
]

def scan_bytes(name, data, report, depth=0):
    need(depth <= 8, 'archive nesting limit')
    report['scanned_files'] += 1
    report['scanned_bytes'] += len(data)
    for kind, pattern in MARKERS:
        need(not pattern.search(data), 'content marker: ' + kind + ': ' + name)
    stream = io.BytesIO(data)
    if zipfile.is_zipfile(stream):
        report['nested_archives'] += 1
        with zipfile.ZipFile(stream) as z:
            infos = z.infolist()
            need(len(infos) == len(set(z.namelist())), 'duplicate archive members')
            need(sum(x.file_size for x in infos) <= 128 * 1024 * 1024, 'archive expansion limit')
            for i in infos:
                rel(i.filename); need(not stat.S_ISLNK(i.external_attr >> 16), 'archive symlink')
                scan_bytes(name + '!' + i.filename, z.read(i), report, depth + 1)
        need(False, 'nested archive not in this delivery allowlist')
    need(not data.startswith((b'\x1f\x8b', b'7z\xbc\xaf\x27\x1c', b'Rar!')), 'unreviewed compressed container')

def check(root):
    manifest = json_load(read(root / 'PUBLIC_MANIFEST.json'))
    need(inventory(root) == set(manifest) | {'PUBLIC_MANIFEST.json'}, 'public allowlist differs')
    report = {'status': 'PASS_PUBLIC_CONTENT_CHECK', 'scanned_files': 0, 'scanned_bytes': 0,
              'nested_archives': 0, 'protected_marker_hits': 0, 'private_path_hits': 0}
    for name in sorted(inventory(root)):
        data = read(root / name)
        if name != 'PUBLIC_MANIFEST.json': need(sha(data) == manifest[name], 'public hash mismatch')
        scan_bytes(name, data, report)
    return report

def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('root', type=Path, nargs='?', default=Path(__file__).absolute().parent)
    a = p.parse_args()
    try:
        print(json.dumps(check(a.root), indent=2)); return 0
    except (Refusal, OSError, ValueError, zipfile.BadZipFile) as e:
        print('REFUSED: ' + str(e), file=sys.stderr); return 2

if __name__ == '__main__': sys.exit(main())
