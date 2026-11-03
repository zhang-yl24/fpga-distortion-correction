"""Read-only, standard-library verification of the sealed stable30 delivery.

The default requires FILE_MANIFEST.json and board evidence. --no-seal is an
explicit development mode; it never qualifies an unsealed package for release.
No EDA, hardware, subprocess or network operations are performed.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import re
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ID = '8c73465ec4d368f9d80f1abf0309c171d84b6c17559bfb606a585ac48ea1e5e2'
EXPECTED_PARAM_ID = '8c73465e'
TOP = 'source/build/offline-20261024/cfg100-independent-20261030-a/candidate/board1080_cfg100_top.v'
SCHEDULER = {
    'source/rtl/experimental/hdmi1080_capture_cdc.v',
    'source/rtl/experimental/hdmi1080_input_dma.v',
    'source/rtl/experimental/hdmi1080_input_write_link.v',
    'source/build/offline-20261024/bypass-system1080-20261029-a/hdmi1080_video_system_geometry_ab.v',
    'source/build/offline-20261024/geometry-bypass-parallel-20261029-coordination/lens1080_bank_core_geometry_bypass.v',
}
CONSTRAINTS = {'ddr-ip-clock-relations.fdc', 'vendor-ddr.rcf'}
IGNORED_PARTS = {'_build', '__pycache__', '.pytest_cache'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def file_sha(path):
    return sha(Path(path).read_bytes())


def digest(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'Invalid SHA256')
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON key: ' + key)
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique_object)


def relative(root, rel):
    require(isinstance(rel, str) and rel != '', 'Empty relative path')
    parts = PurePosixPath(rel)
    require(not parts.is_absolute() and '..' not in parts.parts and '\\' not in rel and ':' not in rel,
            'Invalid relative path: ' + rel)
    result = (Path(root) / rel).resolve()
    require(result.is_relative_to(Path(root).resolve()), 'Path escapes package: ' + rel)
    return result


def check_sha(path, expected):
    require(file_sha(path) == digest(expected), 'SHA256 mismatch: ' + str(path))


def verify_seal(root):
    root = Path(root).resolve()
    seal = root / 'FILE_MANIFEST.json'
    require(seal.is_file(), 'Missing FILE_MANIFEST.json; use --no-seal only during development')
    manifest = read_json(seal)
    rows = manifest['files']
    if isinstance(rows, dict):
        expected = rows
    else:
        require(isinstance(rows, list), 'Manifest files must be an object or list')
        expected = {row['path']: row['sha256'] for row in rows}
        require(len(expected) == len(rows), 'Duplicate manifest file')
        for row in rows:
            if 'bytes' in row:
                require(relative(root, row['path']).stat().st_size == row['bytes'],
                        'Manifest length mismatch: ' + row['path'])
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()
              and p != seal and not any(part in IGNORED_PARTS for part in p.relative_to(root).parts)}
    require(actual == set(expected), 'Sealed package file inventory differs')
    for rel, expected_sha in expected.items():
        check_sha(relative(root, rel), expected_sha)
    return {'files': len(expected), 'manifest_sha256': file_sha(seal)}


def verify_overlays(root, base):
    root, base = Path(root).resolve(), Path(base).resolve()
    overlays = read_json(root / 'OVERLAYS.json')
    require(set(overlays) == SCHEDULER | {TOP}, 'Unexpected overlay path inventory')
    for rel, local in overlays.items():
        require(local == 'overlay/' + rel, 'Unexpected overlay binding: ' + rel)
        require(relative(root, local).is_file(), 'Missing overlay: ' + rel)
    manifest = read_json(root / 'evidence/scheduler-source-manifest.json')
    require(set(manifest) == SCHEDULER, 'Expected exactly five scheduler source records')
    for rel, row in manifest.items():
        check_sha(relative(root, overlays[rel]), row['candidate_sha256'])
        check_sha(relative(base / 'native', rel), row['base_sha256'])
    standalone = (root / 'rtl/ddr_read_return_register.v').read_bytes()
    top = relative(root, overlays[TOP]).read_bytes()
    require(top.endswith(standalone), 'Top appended readstage differs from standalone bytes')
    require(top.count(b'module ddr_read_return_register(') == 1,
            'Expected one appended readstage module')
    return {'scheduler_sources': 5, 'readstage_sha256': sha(standalone)}


def delivered_source(root, base, original):
    """Resolve receipt source paths by their recorded package-relative suffix."""
    normalized = original.replace('\\', '/')
    marker = '/delivery/'
    require(normalized.count(marker) == 1, 'Unknown evidence source provenance: ' + original)
    package, rel = normalized.split(marker, 1)[1].split('/', 1)
    allowed = {root.name: root, base.name: base}
    require(package in allowed, 'Evidence references an unrelated package: ' + package)
    return relative(allowed[package], rel)


def verify_engine(root, base):
    root, base = Path(root).resolve(), Path(base).resolve()
    directory = root / 'evidence/engine'
    report = read_json(directory / 'report.json')
    require(report['passed'] is True and report['source_drift'] == [], 'Engine regression failed or drifted')
    require(report['variant'] == 'both' and report['width'] == 1920 and report['height'] == 1080,
            'Unexpected engine regression variant/dimensions')
    require(report['hardware_accessed'] is False and report['capture_display_arbitration_modeled'] is False,
            'Unexpected engine evidence scope')
    required = {root / 'rtl' / n for n in ['ddr_read_return_register.v',
                'ddr_adaptive_result_writer.v', 'ddr_compact_neighbour_cache_scatter4.v']}
    seen = set()
    for original, expected_sha in report['source_sha256'].items():
        path = delivered_source(root, base, original)
        require(path not in seen, 'Duplicate engine source binding')
        seen.add(path)
        check_sha(path, expected_sha)
    require(required <= seen, 'Engine receipt omits modified RTL')
    for command in report['commands']:
        require(command['returncode'] == 0, 'Engine command did not succeed')
    metrics = report['metrics']
    require(metrics['passed'] is True and metrics['pixels'] == 2073600 and metrics['cycles'] == 2831328,
            'Unexpected full-frame metrics')
    require(metrics['crc32'] == '4be2b2a6' and report['output_sha256'] ==
            '0af8395dd02ae0e56230dc831521f45303f529144c6a61b2b34123c1cef2b812',
            'Full-frame output identity differs')
    # The delivery may omit large memory fixtures and tool-internal artifacts.
    # Every copied artifact that has a receipt digest must match those exact bytes.
    verified = []
    for rel, expected_sha in report['file_sha256'].items():
        path = relative(directory, rel)
        if path.is_file():
            check_sha(path, expected_sha)
            verified.append(rel)
    return {'pixels': metrics['pixels'], 'cycles': metrics['cycles'], 'crc32': metrics['crc32'],
            'output_sha256': report['output_sha256'], 'sources': len(seen),
            'copied_artifacts_verified': sorted(verified), 'hardware_accessed': False,
            'capture_display_arbitration_modeled': False}


def candidate_identity(root):
    """Run only the read-only source selector, suppressing Python bytecode writes."""
    root = Path(root).resolve()
    filename = root / 'tools/prepare_candidate.py'
    module = types.ModuleType('stable30_candidate_sources')
    module.__file__ = str(filename)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        exec(compile(filename.read_bytes(), str(filename), 'exec'), module.__dict__)
        manifest, sources, identity = module.candidate_sources('both', 'corrected')
    finally:
        sys.dont_write_bytecode = previous
    require(identity['candidate_identity_sha256'] == EXPECTED_ID and
            identity['param_id_hex'] == EXPECTED_PARAM_ID, 'Candidate source/constraint identity differs')
    constraints = root / 'constraints'
    require({p.name for p in constraints.iterdir() if p.is_file()} == CONSTRAINTS,
            'Unexpected constraint file inventory')
    recipe = read_json(root.parent / '20261103-hdmi1080-demo-source/manifests/build-recipe.json')
    require(len(recipe['designs']) == 49, 'Frozen design closure changed')
    definitions = sum(sources.get(rel, b'').count(b'module ddr_read_return_register(')
                      for rel in recipe['designs'])
    require(definitions == 1, 'Readstage missing or duplicated in 49-design closure')
    return manifest, sources, identity


def verify_board(root, manifest, sources, identity, required=True):
    root = Path(root).resolve()
    board = root / 'evidence/board'
    prep_path, summary_path = board / 'preparation.json', board / 'summary.json'
    if not prep_path.is_file() or not summary_path.is_file():
        require(not required, 'Missing board preparation.json or summary.json')
        return {'verified': False, 'reason': 'Board evidence not yet complete'}
    prep, summary = read_json(prep_path), read_json(summary_path)
    for item in [prep, summary]:
        require(item['candidate_identity_sha256'] == identity['candidate_identity_sha256'] and
                item['param_id_hex'] == identity['param_id_hex'], 'Board evidence source identity differs')
    require(prep['variant'] == 'both' and prep['mode'] == 'corrected', 'Board preparation variant differs')
    frozen = {row['path']: row for row in manifest['files']}
    files = {row['path']: row for row in prep['files']}
    extras = {'stable-constraints/' + name for name in CONSTRAINTS}
    require(len(frozen) == 130 and len(files) == len(prep['files']) == prep['source_count'] == 132,
            'Board source count differs')
    require(set(files) == set(frozen) | extras and set(prep['additional_constraint_paths']) == extras,
            'Board 130+2 input closure differs')
    for rel, row in files.items():
        digest(row['compile_sha256'])
        if rel in sources:
            expected_sha = sha(sources[rel])
        elif rel in extras:
            expected_sha = file_sha(root / 'constraints' / PurePosixPath(rel).name)
        else:
            require(frozen[rel]['disposition'] == 'external_dependency', 'Unbound board input: ' + rel)
            expected_sha = frozen[rel]['sha256']
        require(row['input_sha256'] == expected_sha, 'Board input SHA256 differs: ' + rel)
        if rel in extras:
            require(row['compile_sha256'] == expected_sha, 'Compiled constraint SHA256 differs: ' + rel)
    flow_path = board / 'board-flow.json'
    flow = read_json(flow_path)
    require(flow['param_id_hex'] == identity['param_id_hex'] and flow['variant'] == 'both' and
            flow['mode'] == 'corrected', 'Board flow identity differs')
    require(flow['preparation']['sha256'] == file_sha(prep_path), 'Board flow preparation receipt differs')
    flow_sha = file_sha(flow_path)
    receipts = []
    # Original receipts keep their local absolute provenance. Never dereference
    # those host-specific paths; verify source and constraint hashes portably.
    for path in sorted(board.rglob('*-result.json')):
        result = read_json(path)
        if result.get('schema') != 'hdmi1080-board-stage-v1':
            continue
        require(result.get('stage_completed') is True and result.get('returncode') == 0,
                'Incomplete board stage receipt: ' + str(path))
        require(result.get('hardware_accessed') is False, 'Unexpected board-access claim')
        require(result['board_flow']['sha256'] == flow_sha, 'Stage belongs to another board flow')
        explicit = result.get('explicit_constraints', [])
        normalized = {ref['path'].replace('\\', '/'): ref['sha256'] for ref in explicit}
        for rel in extras:
            matches = [value for key, value in normalized.items() if key.endswith('/native/' + rel)]
            require(matches == [files[rel]['compile_sha256']], 'Stage constraint binding differs: ' + rel)
        receipts.append(path.relative_to(board).as_posix())
    require(receipts, 'Missing board stage receipts')
    return {'verified': True, 'source_count': 132, 'stage_receipts': receipts,
            'candidate_identity_sha256': identity['candidate_identity_sha256']}


def verify(root=ROOT, require_seal=True):
    root = Path(root).resolve()
    base = root.parent / '20261103-hdmi1080-demo-source'
    seal = verify_seal(root) if require_seal else None
    overlays = verify_overlays(root, base)
    engine = verify_engine(root, base)
    manifest, sources, identity = candidate_identity(root)
    board = verify_board(root, manifest, sources, identity, required=require_seal)
    return {'passed': True, 'sealed_package_verified': require_seal, 'seal': seal,
            'identity': identity, 'overlays': overlays, 'engine': engine, 'board': board,
            'eda_executed': False, 'hardware_accessed': False,
            'scope': 'Read-only source/evidence binding; no new timing or board validation'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--no-seal', action='store_true', help='Development only: omit package-seal requirement')
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.root, require_seal=not args.no_seal), indent=2))
    except (ValueError, OSError, KeyError, TypeError) as error:
        print('CANDIDATE_VERIFICATION_FAILED: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
