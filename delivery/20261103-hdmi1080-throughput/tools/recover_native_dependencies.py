"""Recover 80 frozen dependencies, or verify an unpacked native dependency tree.

No EDA, hardware, network, Git mutation, or vendor/license edits are performed.
Only byte-identical manifest matches are written. Source modifications below
reproduce three historical derived files and are checked against their frozen
SHA256 values before output is created. Verification needs no source checkout
or Git history and performs no file writes.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def normalize_lf(blob):
    return blob.replace(b'\r\n', b'\n')


def input_bytes(repo, relative, expected_lf=None):
    path = repo / relative
    original = path.read_bytes()
    normalized = normalize_lf(original)
    if expected_lf and sha(normalized) != expected_lf:
        raise ValueError('Historical source identity differs: ' + relative)
    return original, normalized, {'path': relative, 'source_sha256': sha(original),
                                   'normalized_lf_sha256': sha(normalized)}


def replace_once(blob, old, new):
    if blob.count(old) != 1:
        raise ValueError('Historical replacement is not unique: ' + repr(old))
    return blob.replace(old, new)


DEFAULT_MANIFEST = Path(__file__).resolve().parents[2] / '20261103-hdmi1080-demo-source/manifests/source-manifest.json'


def recover(repo, destination, verify_only=False, manifest_path=None):
    destination = destination.resolve()
    manifest_path = Path(manifest_path).resolve() if manifest_path else DEFAULT_MANIFEST
    manifest_blob = manifest_path.read_bytes()
    rows = [r for r in json.loads(manifest_blob)['files'] if r['disposition'] != 'included_source']
    if len(rows) != 80 or len({row['path'] for row in rows}) != 80:
        raise ValueError('Expected 80 unique external dependency paths')
    for row in rows:
        if not re.fullmatch(r'[0-9a-f]{64}', row['sha256']) or not isinstance(row['bytes'], int) or row['bytes'] <= 0:
            raise ValueError('Invalid dependency identity: ' + row['path'])
        target = (destination / row['path']).resolve()
        if not target.is_relative_to(destination):
            raise ValueError('Manifest path escapes destination')
    if verify_only:
        records = []
        for row in rows:
            target = destination / row['path']
            if not target.is_file():
                raise ValueError('Recovered dependency is missing: ' + row['path'])
            blob = target.read_bytes()
            if len(blob) != row['bytes'] or sha(blob) != row['sha256']:
                raise ValueError('Recovered dependency identity differs: ' + row['path'])
            records.append(dict(path=row['path'], bytes=len(blob), sha256=sha(blob)))
        return dict(schema='frozen-native-local-verification-v1', passed=True,
                    required=len(rows), matched=len(records), manifest_sha256=sha(manifest_blob),
                    hardware_accessed=False, eda_executed=False, files=records)
    if repo is None:
        raise ValueError('--repo is required for recovery; verification uses only --out and the manifest')
    repo = repo.resolve()
    prepared, records = {}, []
    for row in rows:
        relative = row['path']
        direct = 'distortion/' + relative.removeprefix('source/')
        steps = []
        if relative.endswith('/iic_dri_cfg100_reset.v'):
            original, blob, origin = input_bytes(repo, 'distortion/platform/video_base/source/hdmi/iic_dri.v',
                '5f60bc8bcac110f0125a278c332065d2594874c465ec961c603662f92c16b13e')
            blob = replace_once(blob, b'module iic_dri #(', b'module iic_dri_cfg100_reset #(')
            blob, count = re.subn(rb'        if\(start\)(//[^\n]*\n            trans_en <=)',
                lambda m: b"        if(!rstn)\n            trans_en <= `UD 1'b0;\n        else if(start)" + m[1], blob)
            assert count == 1
            blob, count = re.subn(rb'        if\(start_en\)(  //[^\n]*\n            busy <=)',
                lambda m: b"        if(!rstn)\n            busy <= `UD 1'b0;\n        else if(start_en)" + m[1], blob)
            assert count == 1
            steps = ['Normalize CRLF to LF', 'Rename module to iic_dri_cfg100_reset',
                     'Add synchronous active-low reset branch to trans_en and busy']
        elif '/tx49-preamble-' in relative:
            original, blob, origin = input_bytes(repo, 'distortion/platform/video_base/source/hdmi/ms7210_ctl.v',
                'c9b101e58f381ddf3c6d663d0003c18065302659424b8345022161413ccf09ae')
            old = (b'                CONECT   ,\n                INIT     ,\n'
                   b'                SETING   ,\n                STA_RD   : iic_trig <= busy_falling;')
            new = (b"                INIT     : iic_trig <= busy_falling && (dri_cnt != 5'd18);\n"
                   b'                CONECT   ,\n                SETING   ,\n'
                   b'                STA_RD   : iic_trig <= busy_falling;')
            blob = replace_once(blob, old, new)
            steps = ['Normalize CRLF to LF', 'Guard INIT terminal trigger at dri_cnt=18']
        elif '/night-recovery-edid-' in relative:
            original, blob, origin = input_bytes(repo, 'distortion/rtl/experimental/ms7200_1080p30_rearm_ctl.v')
            blob = replace_once(blob, b'ms7200_1080p30_rearm_ctl', b'ms7200_ctl')
            steps = ['Normalize CRLF to LF', 'Rename ms7200_1080p30_rearm_ctl to ms7200_ctl']
        else:
            original, normalized, origin = input_bytes(repo, direct)
            alternatives = [('Original bytes', original), ('Normalize CRLF to LF', normalized),
                            ('Normalize line endings to CRLF', normalized.replace(b'\n', b'\r\n'))]
            matches = [(action, value) for action, value in alternatives
                       if len(value) == row['bytes'] and sha(value) == row['sha256']]
            if not matches:
                raise ValueError('No exact local byte match: ' + relative)
            action, blob = matches[0]
            steps = [action]
        if len(blob) != row['bytes'] or sha(blob) != row['sha256']:
            raise ValueError('Derived bytes differ from frozen identity: ' + relative)
        target = (destination / relative).resolve()
        if not target.is_relative_to(destination):
            raise ValueError('Manifest path escapes destination')
        if target.exists() and target.read_bytes() != blob:
            raise ValueError('Existing destination has different bytes: ' + relative)
        prepared[target] = blob
        records.append(dict(path=relative, bytes=len(blob), sha256=sha(blob),
                            origin=origin, transformations=steps))
    for target, blob in prepared.items():
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob)
    for target, blob in prepared.items():
        if target.read_bytes() != blob:
            raise ValueError('Post-write verification differs: ' + str(target))
    report = dict(schema='frozen-native-local-recovery-v1', passed=True, required=len(rows),
                  matched=len(records), manifest_sha256=sha(manifest_blob),
                  hardware_accessed=False, eda_executed=False, vendor_source_edited=False,
                  files=records)
    (destination / 'recovery-report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    (destination / 'source-manifest.json').write_bytes(manifest_blob)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, help='Source checkout for recovery; unused in verify-only mode')
    parser.add_argument('--out', type=Path, required=True, help='Explicit native dependency directory')
    parser.add_argument('--manifest', type=Path, help='Default: sibling frozen delivery source manifest')
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    report = recover(args.repo, args.out, args.verify_only, args.manifest)
    print(json.dumps({k: report[k] for k in ('passed', 'required', 'matched', 'manifest_sha256')}, indent=2))
