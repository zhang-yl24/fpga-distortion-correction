"""Freeze offline processed-output release evidence without hardware access.

Native text and explicitly selected project helpers are copied. Routed databases,
vendor netlists and programming files remain local hash references. A failed
generation attempt is preserved beside the verified candidate, never relabelled.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

import archive_processed_output_physical as physical
import processed_output_bitstream as bit

PROJECT, BUILD = physical.PROJECT, physical.BUILD
require, sha, canonical, load = physical.require, physical.sha, physical.canonical, physical.load
SCHEMA = 'processed-output-offline-release-archive-v1'
BIT_SHA = '0537394b548eff5035be031e8056444bad50e20e76cd4b5d49046f477ed01c72'
OLD_ARCHIVES = {
    'processed-output-20261031': '3acafbfaf01b2f51452e05e4599c469468d7394ca49360ac0cb495f9fcada94c',
    'processed-output-physical-20261031': '0957abf4a93067a96d844d34d46fa7744ea214fcb3cba5d8131f7dc8fbf74b28',
}
TEXT_SUFFIXES = physical.TEXT_SUFFIXES | {'.py', '.bgr', '.pds', '.md'}
HELPERS = (
    'tools/archive_processed_output_release.py', 'tools/archive_processed_output_physical.py',
    'tools/processed_output_bitstream.py', 'tools/prepare_processed_output_program.py',
    'tools/prepare_processed_output_preview.py', 'tools/audit_processed_output_cdc.py',
    'tools/audit_processed_output_tx.py', 'tools/prepare_processed_output_tx_delays.py',
    'tests/test_processed_output_bitstream.py', 'tests/test_processed_output_cdc.py',
    'tests/test_processed_output_tx_delays.py',
)


def verify_archive(destination):
    destination = canonical(destination, PROJECT / 'results', directory=True)
    manifest = load(destination / 'manifest.json')
    require(manifest.get('Schema') == SCHEMA, 'unknown archive schema')
    for name, row in manifest['Files'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'unsafe member')
        path = canonical(destination / name, destination)
        require(sha(path) == row['SHA256'] and path.stat().st_size == row['Bytes'], 'encoded hash/size changed')
        require(row['Encoding'] in ('identity', 'gzip'), 'unknown encoding')
        digest, count = hashlib.sha256(), 0
        with (gzip.open if row['Encoding'] == 'gzip' else open)(path, 'rb') as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b''):
                digest.update(chunk)
                count += len(chunk)
        require(digest.hexdigest() == row['OriginalSHA256'] and count == row['OriginalBytes'],
                'decoded hash/size changed')
    actual = {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
    require(actual == set(manifest['Files']) | {'manifest.json'}, 'missing/unexpected archive member')
    for row in manifest['LocalReferencesOnly']:
        path = canonical(row['LocalPath'], PROJECT)
        require(sha(path) == row['SHA256'] and path.stat().st_size == row['Bytes'], 'local reference changed')
    return {'ReadbackVerified': True, 'Files': len(manifest['Files']),
            'LocalReferences': len(manifest['LocalReferencesOnly']),
            'ManifestSHA256': sha(destination / 'manifest.json')}


def check_stage(work):
    work = canonical(work, BUILD, directory=True)
    require(work.parent == BUILD, 'stage must be a direct processed-output child')
    paths = [work / name for name in ('result.json', 'execution-result.json') if (work / name).is_file()]
    require(len(paths) == 1, 'exactly one completed stage receipt required')
    receipt_path = paths[0]
    receipt = load(receipt_path)
    require(receipt.get('Schema') in ('processed-output-isolated-physical-v1',
                                      'processed-output-bitstream-execution-v1'), 'unsupported stage')
    require(receipt.get('FinishedUTC') and type(receipt.get('ExitCode')) is int
            and receipt.get('HardwareAccessed') is False, 'stage is incomplete or accessed hardware')
    for name, digest in receipt.get('Artifacts', {}).items():
        require(sha(canonical(work / name, work)) == digest, 'completed stage artifact changed')
    status = {key: receipt.get(key) for key in ('Schema', 'StartedUTC', 'FinishedUTC', 'ExitCode',
              'ExecutionPassed', 'TimedOut', 'Diagnostics', 'InputDrift', 'FinalADFSHA256',
              'SourceADFSHA256', 'ResultADFSHA256')}
    status.update(OriginalDirectory=str(work), Receipt=receipt_path.name,
                  ReceiptSHA256=sha(receipt_path), FailedTrial=receipt['ExitCode'] != 0)
    return work, status


def archive(destination, stages=(), extra_files=(), evidence_dirs=(), program=None):
    destination = Path(destination).absolute()
    require(destination.resolve() == destination and destination.parent == PROJECT / 'results'
            and not destination.exists(), 'new canonical direct results child required')
    verified = bit.verify(BUILD / 'bit-20261031-b')
    require(verified['Bitstream']['SHA256'] == BIT_SHA, 'unexpected diagnostic bitstream')
    old_paths = []
    for name, digest in OLD_ARCHIVES.items():
        path = PROJECT / 'results' / name / 'manifest.json'
        require(sha(path) == digest, 'prior immutable evidence archive changed')
        old_paths.append(path)
    stage_paths = {BUILD / 'bit-20261031-a', BUILD / 'bit-20261031-b'} | {Path(p).absolute() for p in stages}
    checked = [check_stage(p) for p in sorted(stage_paths)]
    failed = next(row for work, row in checked if work.name == 'bit-20261031-a')
    require(failed['ExitCode'] == 1 and not (BUILD / 'bit-20261031-a' / bit.BIT).exists(),
            'original failed alias-gate trial differs')
    extras = {canonical(p, PROJECT) for p in extra_files}
    extras.update(canonical(PROJECT / p, PROJECT) for p in HELPERS)
    directories = [canonical(p, PROJECT / 'results', directory=True) for p in evidence_dirs]
    require(all(p.parent == PROJECT / 'results' and p.name.startswith('processed-output-')
                for p in directories), 'only explicit processed-output evidence directories supported')
    program_path = None
    if program:
        program_path = canonical(program, BUILD, directory=True)
        plan = load(program_path / 'plan.json')
        require(plan.get('Schema') == 'processed-output-sram-plan-v1' and plan.get('PreparedOnly') is True
                and plan.get('HardwareAccessed') is False and plan.get('Executed') is False
                and plan['Bitstream']['SHA256'] == BIT_SHA, 'prepared-only matching SRAM plan required')
        for name, digest in plan['BoundInputSHA256'].items():
            require(sha(name) == digest, 'prepared SRAM binding changed')
        for row in plan['Tcl'].values():
            require(sha(row['Path']) == row['SHA256'], 'prepared SRAM script changed')
    destination.mkdir()
    files, references, watched = {}, {}, {}

    def reference(path, reason):
        path = canonical(path, PROJECT)
        row = physical.reference(path, reason)
        references[str(path)] = row
        watched[str(path)] = row['SHA256']

    def add(path):
        path = canonical(path, PROJECT)
        relative = path.relative_to(PROJECT).as_posix()
        # Never copy generated/vendor Verilog, databases, bitstreams or route dumps.
        if (path.suffix.lower() not in TEXT_SUFFIXES | {'.png'} and path.name != 'dummy.v'
                or path.name == 'route-dump.txt'):
            reference(path, 'Generated/vendor binary or netlist retained locally; bytes not copied')
            return
        compress = path.suffix.lower() == '.log' or (path.stat().st_size >= 131072 and path.suffix.lower() != '.png')
        name = relative + ('.gz' if compress else '')
        # Deep native report directories exceed legacy Windows path limits.
        # Retain the full original location in each manifest entry instead.
        if len(str(destination / name)) > 235:
            name = 'long-paths/' + hashlib.sha256(relative.encode('utf-8')).hexdigest()[:24] + path.suffix + ('.gz' if compress else '')
        # Deep native report directories exceed legacy Windows path limits.
        # Retain the full original location in each manifest entry instead.
        if len(str(destination / name)) > 235:
            name = 'long-paths/' + hashlib.sha256(relative.encode('utf-8')).hexdigest()[:24] + path.suffix + ('.gz' if compress else '')
        if name in files:
            require(files[name]['Origin'] == str(path), 'archive name collision')
            return
        files[name] = physical.copy_bound(path, destination / name, compress)
        files[name]['ProjectRelativePath'] = relative
        files[name]['ProjectRelativePath'] = relative
        watched[str(path)] = files[name]['OriginalSHA256']

    for path in old_paths:
        reference(path, 'Prior evidence archive immutable and referenced only')
    for work, _ in checked:
        for path in sorted(work.rglob('*')):
            if path.is_file():
                require(not any(part in ('compiled', 'sources', 'xsim.dir') for part in path.relative_to(work).parts),
                        'unexpected source tree inside selected stage')
                add(path)
    for directory in directories + ([program_path] if program_path else []):
        for path in sorted(directory.rglob('*')):
            if path.is_file():
                add(path)
    for path in sorted(extras):
        add(path)
    for path, digest in watched.items():
        require(sha(path) == digest, 'source changed while archiving: ' + path)
    manifest = {'Schema': SCHEMA, 'ArchivedUTC': datetime.now(timezone.utc).isoformat(),
                'Destination': str(destination), 'Files': files,
                'LocalReferencesOnly': list(references.values()), 'Stages': [row for _, row in checked],
                'OriginalArchivesSHA256': OLD_ARCHIVES, 'VerifiedBitstream': verified['Bitstream'],
                'FinalADFSHA256': verified['FinalADFSHA256'],
                'InternalTimingPassed': verified['NativeTiming']['AllTenNativeTimingTablesPassed'],
                'FiniteCDCEvidenceProvided': any(p.name.startswith('cdc-structural-') for p in extras),
                'AllCDCUniversallyProven': False, 'ExternalTimingAccepted': False,
                'BoardPowerLastReported': 'off', 'HardwareAccessedByArchiver': False,
                'EDAExecutedByArchiver': False, 'HardwareValidated': False,
                'PreparedProgramDirectory': str(program_path) if program_path else None,
                'ReadbackRequired': True, 'ManifestSelfHashExcluded': True,
                'Limits': ['Stored files and local references are hashed independently; archive is not hardware validation.',
                           'Finite CDC and conditional TX analyses retain their original scope and limitations.',
                           'Program preparation is separate from device scan, SRAM download and display acceptance.',
                           'Original failed generation trial and original helper snapshots remain preserved.']}
    with (destination / 'manifest.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(manifest, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return {'Archived': True, 'Manifest': str(destination / 'manifest.json'), **verify_archive(destination)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', '--destination', dest='output', type=Path, required=True)
    parser.add_argument('--stage', type=Path, action='append', default=[])
    parser.add_argument('--extra-file', type=Path, action='append', default=[])
    parser.add_argument('--evidence-dir', type=Path, action='append', default=[])
    parser.add_argument('--prepared-program', type=Path)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    result = verify_archive(args.output) if args.verify_only else archive(
        args.output, args.stage, args.extra_file, args.evidence_dir, args.prepared_program)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
