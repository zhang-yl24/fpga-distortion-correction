"""Create a local, portable source/dependency/board-evidence ZIP for teammates.

No EDA, programming, serial, Git mutation, network access, or license packaging.
The default destination is the task workspace's outputs directory. --inspect
performs read-only source/dependency validation without creating an archive.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import importlib.util
import json
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
BASE = ROOT.parent / '20261103-hdmi1080-demo-source'
OUTPUT_BASE = REPO.parents[1] if REPO.name == 'repo' and REPO.parent.name == 'work' else REPO
DEFAULT_OUTPUT = OUTPUT_BASE / 'outputs/hdmi1080-stable30-candidate-20261103.zip'
DEFAULT_DEPENDENCIES = (REPO / 'native-dependencies' if (REPO / 'native-dependencies').is_dir()
                        else Path('C:/Users/Lenovo/Documents/Codex/fpga-native-recovered'))
ARCHIVE_ROOT = 'fpga1080'
SKIP_PARTS = {'_work', '_build', '__pycache__', '.pytest_cache', '.git',
              'xsim.dir', '.Xil', 'logbackup', 'bak', 'backup'}
FORBIDDEN_SUFFIXES = {'.lic', '.exe', '.dll', '.msi', '.msix', '.pyc', '.pyo',
                      '.wdb', '.vcd', '.fst', '.dcp', '.zip', '.7z', '.rar'}
TEST_SUPPORT = (
    'distortion/tools/generate-brown-vectors.py',
    'distortion/tools/calibrate.py',
    'distortion/tools/calibrate_fisheye_profile.py',
    'distortion/tools/stereo_fisheye_calibrate.py',
    'distortion/tools/wideangle_mapping_audit.py',
    'distortion/tools/fisheye_forward_inverse.py',
    'distortion/model/reference.py',
    'distortion/model/rotation.py',
    'distortion/requirements.txt',
    'distortion/board/bringup.fdc',
    'distortion/board/corrected_gamma_d5.fdc',
)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_member(name):
    name = str(name).replace('\\', '/')
    path = PurePosixPath(name)
    require(name and not path.is_absolute() and '..' not in path.parts and
            not any(c in name for c in ':\r\n\x00'), 'Unsafe archive path: ' + name)
    return path.as_posix()


def source_file(root, rel):
    path = (Path(root) / safe_member(rel)).resolve()
    require(path.is_relative_to(Path(root).resolve()) and path.is_file(),
            'Missing or outside source tree: ' + str(path))
    require(not path.is_symlink(), 'Symlink input is not supported: ' + str(path))
    return path


def import_helper(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    old = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = old
    return module


def forbidden(path):
    parts = [p.lower() for p in path.parts]
    return (any(p in {s.lower() for s in SKIP_PARTS} for p in parts)
            or path.suffix.lower() in FORBIDDEN_SUFFIXES
            or any(p in ('license', 'licenses', 'license.dat', 'license.txt') for p in parts))


def add_entry(entries, name, path, category):
    name = safe_member(name)
    path = Path(path).resolve()
    require(path.is_file(), 'Missing package input: ' + str(path))
    require(not forbidden(Path(name)), 'Excluded binary/cache/license file: ' + name)
    require(name not in entries, 'Duplicate archive entry: ' + name)
    entries[name] = {'source': path, 'bytes': path.stat().st_size,
                     'sha256': digest(path), 'category': category}


def build_summary(work):
    work = work.resolve()
    require((work / 'board-flow.json').is_file(), 'Build work lacks board-flow.json')
    plan = read_json(work / 'board-flow.json')
    preparation_path = work / 'preparation.json'
    preparation = read_json(preparation_path)
    require(digest(preparation_path) == plan['preparation']['sha256'], 'Build preparation binding changed')
    helper = import_helper('board_package_prepare', ROOT / 'tools/prepare_candidate.py')
    _, current_sources, identity = helper.candidate_sources(plan['variant'], plan['mode'])
    require(all(preparation.get(key) == identity[key]
                for key in ('variant', 'mode', 'param_id_hex', 'candidate_identity_sha256')),
            'Archived build uses different RTL/parameters from the candidate being packaged')
    for row in preparation['files']:
        compiled = source_file(work / 'native', row['path'])
        require(digest(compiled) == row['compile_sha256'], 'Prepared build source changed: ' + row['path'])
        if row['path'] in current_sources:
            require(hashlib.sha256(current_sources[row['path']]).hexdigest() == row['input_sha256'],
                    'Prepared input differs from current candidate: ' + row['path'])
    result = {key: plan.get(key) for key in ('variant', 'mode', 'param_id_hex', 'architecture')}
    result.update(candidate_identity_sha256=preparation['candidate_identity_sha256'], hardware_verified=False, relocated_snapshot_resumable=False,
                  external_io_timing_accepted=plan.get('external_io_timing_accepted', False),
                  cdc_protocol_and_reset_signoff=plan.get('cdc_protocol_and_reset_signoff', False),
                  stages={})
    for stage in ('map', 'route', 'sta', 'bitstream'):
        path = work / (stage + '-result.json')
        if not path.is_file():
            result['stages'][stage] = {'record_present': False, 'stage_completed': False}
            continue
        item = read_json(path)
        row = {key: item.get(key) for key in ('stage_completed', 'error', 'returncode', 'label',
                    'physical_timing_accepted', 'hardware_release_allowed', 'diagnostic_bit_requested')}
        row['record_present'] = True
        row['receipt_sha256'] = digest(path)
        if 'timing' in item:
            row['timing'] = {key: item['timing'].get(key) for key in
                            ('complete_two_corner_report', 'all_native_checks_met', 'summaries')}
        row['artifacts'] = {key: {'sha256': ref.get('sha256'),
                                 'filename': Path(ref.get('path', '')).name}
                            for key, ref in item.get('artifacts', {}).items()}
        result['stages'][stage] = row
    return result


def collect_build(entries, label, work, detail, max_bytes):
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,32}', label) is not None, 'Invalid build label')
    work = work.resolve()
    summary = build_summary(work)
    selected = {}
    if detail == 'full':
        for path in work.rglob('*'):
            if path.is_file():
                rel = path.relative_to(work)
                if not forbidden(rel):
                    selected[rel.as_posix()] = path
    else:
        # Include stage receipts and exactly referenced local artifacts/logs.
        # Native dependency sources already exist in the portable build closure.
        def visit(value):
            if isinstance(value, dict):
                if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
                    path = Path(value['path']).resolve()
                    if path.is_relative_to(work):
                        require(path.is_file() and digest(path) == value['sha256'],
                                'Build receipt artifact changed: ' + str(path))
                        selected[path.relative_to(work).as_posix()] = path
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        for pattern in ('*.json', '*.tcl', '*.fdc'):
            for path in work.glob(pattern):
                selected[path.name] = path
                if path.suffix == '.json':
                    visit(read_json(path))
    size = sum(path.stat().st_size for path in selected.values())
    require(size <= max_bytes, 'Build snapshot exceeds limit; use evidence detail or raise --max-build-mib')
    for rel, path in sorted(selected.items()):
        add_entry(entries, 'board-builds/' + label + '/' + rel, path, 'board_evidence_' + detail)
    bit_receipt = work / 'bitstream-result.json'
    summary['portable_bitstream'] = None
    if bit_receipt.is_file():
        receipt = read_json(bit_receipt)
        ref = receipt.get('artifacts', {}).get('exported_bitstream')
        if receipt.get('stage_completed') and isinstance(ref, dict):
            path = Path(ref['path']).resolve()
            require(path.is_relative_to(work) and path.is_file() and digest(path) == ref['sha256'],
                    'Exported bitstream missing or changed')
            variant = summary['variant']
            require(variant in ('baseline', 'writer', 'cache', 'both'), 'Unknown bitstream variant')
            member = 'bitstreams/' + variant + '/' + path.name
            add_entry(entries, member, path, 'exported_board_bitstream')
            summary['portable_bitstream'] = {'path': member, 'sha256': ref['sha256'],
                                             'label': receipt.get('label'),
                                             'mode': summary.get('mode'), 'hardware_verified': False}
    summary.update(snapshot_detail=detail, archived_files=len(selected), archived_bytes=size)
    return summary


def collect(args):
    frozen = import_helper('board_package_frozen', BASE / 'tools/verify_package.py').verify()
    candidate = import_helper('board_package_candidate', ROOT / 'tools/verify_candidate.py').verify()
    require(frozen['included_sources_verified'] == 50 and
            frozen['external_dependencies_required'] == 80, 'Unexpected frozen source closure')
    entries = {}
    index = read_json(BASE / 'PACKAGE_MANIFEST.json')
    for row in index['files']:
        add_entry(entries, 'delivery/' + BASE.name + '/' + row['path'],
                  source_file(BASE, row['path']), 'frozen_demo')
    add_entry(entries, 'delivery/' + BASE.name + '/PACKAGE_MANIFEST.json',
              BASE / 'PACKAGE_MANIFEST.json', 'frozen_demo')
    # Candidate payload may include newly reviewed docs/tools beyond an older
    # seal. Every archived file receives a new byte-exact package binding.
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if forbidden(rel):
            continue
        add_entry(entries, 'delivery/' + ROOT.name + '/' + rel.as_posix(), path, 'candidate')
    manifest = read_json(BASE / 'manifests/source-manifest.json')
    dependencies = args.dependency_native.resolve()
    rows = [r for r in manifest['files'] if r['disposition'] == 'external_dependency']
    require(len(rows) == 80, 'Expected exactly 80 native dependencies')
    for row in rows:
        path = source_file(dependencies, row['path'])
        require(path.stat().st_size == row['bytes'] and digest(path) == row['sha256'],
                'Exact native dependency mismatch: ' + row['path'])
        add_entry(entries, 'native-dependencies/' + row['path'], path, 'native_dependency')
    for name in ('recovery-report.json', 'source-manifest.json', 'README.md'):
        path = dependencies / name
        if path.is_file():
            add_entry(entries, 'native-dependencies/' + name, path, 'dependency_provenance')
    for rel in TEST_SUPPORT:
        add_entry(entries, rel, source_file(REPO, rel), 'test_and_review_support')
    for rel in ('distortion/tools/__init__.py', 'distortion/model/__init__.py'):
        if (REPO / rel).is_file():
            add_entry(entries, rel, REPO / rel, 'test_and_review_support')
    builds = {}
    for value in args.build_work:
        require('=' in value, '--build-work requires LABEL=PATH')
        label, raw = value.split('=', 1)
        require(label not in builds, 'Duplicate build label')
        builds[label] = collect_build(entries, label, Path(raw), args.build_detail,
                                      args.max_build_mib * 1024 * 1024)
    if args.require_corrected_bitstreams:
        available = {item['variant'] for item in builds.values()
                     if item.get('mode') == 'corrected' and item.get('portable_bitstream')}
        require({'both'} <= available,
                'Final package requires the exported stable30 both/corrected bitstream')
    status = {'schema': 'hdmi1080-local-board-delivery-v1',
              'created_utc': datetime.now(timezone.utc).isoformat(),
              'source_validation': frozen, 'candidate_validation': candidate,
              'included_native_dependencies': len(rows), 'hardware_verified': False,
              'calibration_profile': 'Frozen Penn frame240; current-camera calibration not asserted',
              'video_profile': 'Frozen HDMI 1080p29.97/30 DDR correction chain',
              'board_builds': builds,
              'scope': 'Local teammate delivery; preserves frozen and candidate sources separately. '
                       'No PDS executable or license, JTAG programming, physical acceptance, '
                       'or 60-new-corrected-frames/s claim.'}
    extract_prefix = args.extract_parent.as_posix().rstrip('/') + '/' + ARCHIVE_ROOT + '/'
    longest_name = max(entries, key=lambda name: len(extract_prefix + name))
    longest_chars = len(extract_prefix + longest_name)
    require(longest_chars <= 240,
            'Extracted path exceeds 240 characters; use a shorter --extract-parent or build label: ' + longest_name)
    status['path_validation'] = {'recommended_extract_parent': args.extract_parent.as_posix(),
                                  'archive_root': ARCHIVE_ROOT, 'longest_member': longest_name,
                                  'longest_extracted_path_characters': longest_chars,
                                  'path_budget_characters': 240}
    return entries, status


VERIFY_SCRIPT = '''"""Verify extracted board-package bytes using only Python's standard library."""
from pathlib import Path, PurePosixPath
import hashlib
import json
ROOT=Path(__file__).resolve().parent
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
manifest=json.loads((ROOT/'PACKAGE_MANIFEST.json').read_text(encoding='utf-8'))
for row in manifest['files']:
    rel=PurePosixPath(row['path'])
    if rel.is_absolute() or '..' in rel.parts:raise ValueError('Unsafe manifest path')
    p=(ROOT/row['path']).resolve()
    if not p.is_relative_to(ROOT) or not p.is_file() or p.stat().st_size!=row['bytes'] or sha(p)!=row['sha256']:
        raise ValueError('Missing or changed package file: '+row['path'])
print(json.dumps({'verified_files':len(manifest['files']),'source_bytes_verified':True,
                  'hardware_verified':False,'note':'Read PACKAGE_STATUS.json for archived stage status.'},indent=2))
'''


REBUILD_SCRIPT = '''"""One-command source rebuild through a labelled diagnostic bitstream.

Uses the recipient's installed PDS and stops immediately on any failed stage.
No JTAG, UART, Flash, or hardware programming is performed.
"""
from pathlib import Path
from datetime import datetime
import argparse
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
FLOW=ROOT/'delivery/20261103-hdmi1080-stable30/tools/build_board_candidate.py'

def run(command):
    print('Running: '+subprocess.list2cmdline([str(x) for x in command]),flush=True)
    subprocess.run([str(x) for x in command],cwd=ROOT,check=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pds-shell',type=Path,required=True)
    p.add_argument('--output-root',type=Path,default=Path('C:/fpga-build'))
    p.add_argument('--variant',choices=('baseline','writer','cache','both'),default='both')
    p.add_argument('--mode',choices=('corrected','raw','demo'),default='corrected')
    p.add_argument('--run-name')
    p.add_argument('--seed',type=int,default=1)
    p.add_argument('--timeout-seconds',type=int,default=10800)
    a=p.parse_args()
    if not a.pds_shell.is_file():p.error('PDS executable was not found')
    run_name=a.run_name or (a.variant+'-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    output=a.output_root.resolve()
    work=output/run_name
    common=[sys.executable,'-B',FLOW]
    try:
        run(common+['prepare','--dependency-native',ROOT/'native-dependencies',
                    '--output-root',output,'--run-name',run_name,
                    '--variant',a.variant,'--mode',a.mode])
        for stage in ('map','route','sta','bitstream'):
            command=common+['run','--work',work,'--stage',stage,'--pds-shell',a.pds_shell.resolve(),
                            '--seed',str(a.seed),'--timeout-seconds',str(a.timeout_seconds)]
            if stage=='bitstream':command.append('--diagnostic-bit')
            run(command)
    except subprocess.CalledProcessError as exc:
        print('Build stopped. Keep the failed stage logs under '+str(work),file=sys.stderr)
        return exc.returncode if exc.returncode else 1
    receipt=json.loads((work/'bitstream-result.json').read_text(encoding='utf-8'))
    if not receipt.get('stage_completed') or receipt.get('label')!='DIAGNOSTIC_NOT_TIMING_SIGNOFF':
        raise RuntimeError('A completed labelled diagnostic bitstream receipt is required')
    print(json.dumps({'completed':True,'work':str(work),'label':receipt['label'],
                     'bitstream':receipt['artifacts']['exported_bitstream'],
                     'hardware_verified':False,'hardware_programmed':False},indent=2))
    return 0

if __name__=='__main__':
    raise SystemExit(main())
'''


def start_here(status):
    return (ROOT / 'docs/START_HERE.md').read_text(encoding='utf-8')


def create_package(args):
    entries, status = collect(args)
    count = len(entries)
    total = sum(row['bytes'] for row in entries.values())
    if args.inspect:
        return {'inspect_only': True, 'output_created': False, 'input_files': count,
                'input_bytes': total, 'native_dependencies': 80,
                'board_builds': status['board_builds'], 'path_validation': status['path_validation']}
    output = args.output.resolve()
    require(output.suffix.lower() == '.zip', '--output must name a ZIP')
    checksum = output.with_suffix(output.suffix + '.sha256')
    receipt = output.with_suffix(output.suffix + '.json')
    require(not any(p.exists() for p in (output, checksum, receipt)), 'Use a fresh output name')
    generated = {
        'START_HERE.md': start_here(status).encode('utf-8'),
        'PACKAGE_STATUS.json': (json.dumps(status, indent=2, ensure_ascii=False) + '\n').encode('utf-8'),
        'verify_package.py': VERIFY_SCRIPT.encode('utf-8'),
        'rebuild.py': REBUILD_SCRIPT.encode('utf-8'),
        'requirements-simulation.txt': b'numpy>=1.24\n',
    }
    for variant in ('both',):
        records = [dict(build_label=label, **item) for label, item in status['board_builds'].items()
                   if item.get('variant') == variant]
        payload = {'variant': variant, 'hardware_verified': False,
                   'exported_bitstream_present': any(r.get('portable_bitstream') for r in records),
                   'builds': records}
        generated['bitstreams/' + variant + '/STATUS.json'] = (
            json.dumps(payload, indent=2, ensure_ascii=False) + '\n').encode('utf-8')
    manifest_rows = [{'path': name, 'bytes': row['bytes'], 'sha256': row['sha256'],
                      'category': row['category']} for name, row in sorted(entries.items())]
    manifest_rows += [{'path': name, 'bytes': len(blob), 'sha256': hashlib.sha256(blob).hexdigest(),
                       'category': 'generated_package_document'} for name, blob in sorted(generated.items())]
    manifest = {'schema': 'portable-board-package-files-v1', 'files': manifest_rows,
                'hardware_verified': False, 'archive_root': ARCHIVE_ROOT}
    generated['PACKAGE_MANIFEST.json'] = (json.dumps(manifest, indent=2, ensure_ascii=False)+'\n').encode('utf-8')
    output.parent.mkdir(parents=True, exist_ok=True)
    # Create-only archive: a failed partial archive remains for diagnosis.
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for name, row in sorted(entries.items()):
            require(digest(row['source']) == row['sha256'], 'Input changed before packaging: ' + name)
            archive.write(row['source'], ARCHIVE_ROOT + '/' + name)
        for name, blob in sorted(generated.items()):
            archive.writestr(ARCHIVE_ROOT + '/' + name, blob)
    for name, row in entries.items():
        require(digest(row['source']) == row['sha256'], 'Input changed during packaging: ' + name)
    with zipfile.ZipFile(output) as archive:
        require(archive.testzip() is None, 'ZIP CRC verification failed')
        for row in manifest_rows:
            blob = archive.read(ARCHIVE_ROOT + '/' + row['path'])
            require(len(blob) == row['bytes'] and hashlib.sha256(blob).hexdigest() == row['sha256'],
                    'Archived bytes differ: ' + row['path'])
    archive_sha = digest(output)
    checksum.write_text(archive_sha + '  ' + output.name + '\n', encoding='ascii')
    result = {'schema': 'portable-board-package-receipt-v1', 'passed': True,
              'archive': str(output), 'sha256': archive_sha, 'archive_bytes': output.stat().st_size,
              'manifest_files': len(manifest_rows), 'source_files': count, 'source_bytes': total,
              'native_dependencies': 80, 'hardware_verified': False,
              'board_builds': status['board_builds'], 'path_validation': status['path_validation'],
              'zip_crc_and_sha_verified': True}
    receipt.write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dependency-native', type=Path, default=DEFAULT_DEPENDENCIES)
    p.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    p.add_argument('--build-work', action='append', default=[], metavar='LABEL=PATH')
    p.add_argument('--build-detail', choices=('evidence', 'full'), default='evidence')
    p.add_argument('--max-build-mib', type=int, default=512)
    p.add_argument('--require-corrected-bitstreams', action='store_true',
                   help='Fail unless the stable30 both fixed-correction bitstream is included')
    p.add_argument('--extract-parent', type=Path, default=Path('C:/fpga'),
                   help='Short extraction parent used for Windows path-length validation')
    p.add_argument('--inspect', action='store_true')
    args = p.parse_args()
    require(1 <= args.max_build_mib <= 8192, 'Invalid build size bound')
    print(json.dumps(create_package(args), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
