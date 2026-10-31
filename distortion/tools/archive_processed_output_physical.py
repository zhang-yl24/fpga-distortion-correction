"""Archive completed isolated output physical stages, including failed trials.

Native text evidence and self-authored helpers are copied with readback hashes.
ADF files and generated netlists containing vendor logic remain local hash
references. A passing comparison is recorded only when a supplied audit and all
of its inputs can be revalidated. Archiving never grants hardware acceptance.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import shutil

PROJECT = Path(__file__).resolve().parents[1]
BUILD = PROJECT / 'build/processed-output'
BASELINE_MANIFEST = PROJECT / 'results/processed-output-20261031/manifest.json'
BASELINE_MANIFEST_SHA = '3acafbfaf01b2f51452e05e4599c469468d7394ca49360ac0cb495f9fcada94c'
BASELINE_ADF = BUILD / 'pds-20261031-a/place_route/processed_output_top_pnr.adf'
BASELINE_ADF_SHA = '97df0e42848650499802b2cf0e4375f420b4c2c98cc55bd9e2dc97fb62a5b980'
PRESERVED_FAILURES = ('physical-query-20261031-a', 'physical-hold-20261031-a',
                      'physical-hold-20261031-b')
SOURCES = (
    'tools/run_processed_output_physical.py', 'tools/run_processed_output_export.py',
    'tools/audit_processed_output_physical.py', 'tools/audit_processed_output_reset.py',
    'tools/audit_processed_output_entry_netlist.py',
    'tools/audit_processed_output_reset_query.py', 'tools/prepare_processed_output_reset_scope.py',
    'tools/audit_processed_output_routes.py',
    'tools/audit_processed_output_route_occupancy.py',
    'tools/archive_processed_output_physical.py', 'tests/test_processed_output_reset.py',
    'tests/test_processed_output_entry_netlist.py',
    'tools/audit_ddr_entry_reset_netlist.py', 'tools/audit_ddr_final_timing.py',
    'tools/audit_ddr_recovery_variants.py', 'tools/audit_fresh_ddr_timing.py',
    'tools/prepare_ddr_native_recovery_constraints.py', 'tools/prepare_ddr_native_reset_scope.py',
    'tools/prepare_ddr_ip_reset_constraints.py', 'tools/prepare_processed_output.py',
    'tools/prepare_board1080_timing.py',
)
TEXT_SUFFIXES = {'.json','.log','.tcl','.fdc','.rcf','.rtr','.rtx','.rpt','.txt','.csv',
                 '.cmr','.snr','.dmr','.ccr','.pcf','.prr','.prt','.ror','.plr','.rur','.gnr'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def canonical(value, parent, directory=False):
    path = Path(value).absolute()
    require(path.resolve() == path and path.is_relative_to(parent), 'escaped or linked evidence path')
    require(path.is_dir() if directory else path.is_file(), 'missing evidence: ' + str(path))
    return path


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def reference(path, reason):
    path = canonical(path, PROJECT)
    return {'LocalPath':str(path), 'ProjectRelativePath':path.relative_to(PROJECT).as_posix(),
            'SHA256':sha(path), 'Bytes':path.stat().st_size, 'Copied':False, 'Reason':reason}


def copy_bound(source, target, compress):
    digest, size = sha(source), source.stat().st_size
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open('rb') as stream, target.open('xb') as output:
        if compress:
            with gzip.GzipFile(filename='', mode='wb', fileobj=output, mtime=0) as encoded:
                shutil.copyfileobj(stream, encoded, 1 << 20)
        else:
            shutil.copyfileobj(stream, output, 1 << 20)
    require(sha(source) == digest and source.stat().st_size == size, 'source changed during copy')
    return {'Bytes':target.stat().st_size, 'SHA256':sha(target),
            'Encoding':'gzip' if compress else 'identity', 'OriginalBytes':size,
            'OriginalSHA256':digest, 'Origin':str(source)}


def verify_archive(destination):
    destination = canonical(destination, PROJECT / 'results', directory=True)
    manifest_path = destination / 'manifest.json'
    manifest = load(manifest_path)
    require(manifest.get('Schema') == 'processed-output-physical-evidence-archive-v1', 'archive schema differs')
    for name, row in manifest['Files'].items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'unsafe archive member')
        path = canonical(destination / name, destination)
        require(sha(path) == row['SHA256'] and path.stat().st_size == row['Bytes'], 'archive encoded hash differs')
        require(row['Encoding'] in ('identity','gzip'), 'unknown archive encoding')
        digest, size = hashlib.sha256(), 0
        opener = gzip.open if row['Encoding'] == 'gzip' else open
        with opener(path, 'rb') as stream:
            for block in iter(lambda:stream.read(1 << 20), b''):
                digest.update(block)
                size += len(block)
        require(digest.hexdigest() == row['OriginalSHA256'] and size == row['OriginalBytes'],
                'archive decoded payload differs')
    actual = {p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
    require(actual == set(manifest['Files']) | {'manifest.json'}, 'unexpected/missing archive member')
    return {'ReadbackVerified':True, 'Files':len(manifest['Files']),
            'ManifestSHA256':sha(manifest_path), 'LocalReferences':len(manifest['LocalReferencesOnly'])}


def completed_stage(path):
    work = canonical(path, BUILD, directory=True)
    require(work.parent == BUILD, 'stage must be a direct processed-output child')
    receipts = [work / name for name in ('result.json','export-result.json') if (work / name).is_file()]
    require(len(receipts) == 1, 'exactly one completed stage receipt required: ' + work.name)
    receipt_path = receipts[0]
    receipt = load(receipt_path)
    require(receipt.get('Schema') in ('processed-output-isolated-physical-v1', 'processed-output-functional-export-v1'),
            'unknown stage receipt schema')
    require(receipt.get('FinishedUTC') and isinstance(receipt.get('ExitCode'), int)
            and isinstance(receipt.get('ExecutionPassed'), bool), 'stage is incomplete')
    require(receipt.get('HardwareAccessed') is False and receipt.get('BitstreamRequested') is False,
            'unexpected hardware operation in stage')
    for name, digest in receipt.get('Artifacts', {}).items():
        file = canonical(work / name, work)
        require(sha(file) == digest, 'stage artifact changed since completion: ' + str(file))
    # Preserve native failures verbatim; successful execution is not timing acceptance.
    status = {key:receipt.get(key) for key in
              ('Schema','StartedUTC','FinishedUTC','ExitCode','ExecutionPassed','TimedOut','Diagnostics',
               'InputDrift','SourceADFSHA256','ResultADFSHA256','InputADFUnchanged')}
    status.update(OriginalDirectory=str(work), Receipt=receipt_path.name,
                  ReceiptSHA256=sha(receipt_path), Deleted=False)
    return work, status


def comparison_evidence(path):
    if path is None:
        return {'Provided':False, 'NativeComparisonPassed':False, 'InternalTimingMet':False}, None
    path = canonical(path, PROJECT)
    report = load(path)
    require(report.get('Schema') == 'processed-output-physical-comparison-v1'
            and report.get('AuditPassed') is True, 'comparison must be a completed native comparison audit')
    for group in ('InputSHA256','ToolsSHA256'):
        require(report.get(group), 'comparison lacks bound inputs/helpers')
        for name, digest in report[group].items():
            file = canonical(name, PROJECT)
            require(sha(file) == digest, 'comparison evidence changed: ' + name)
    candidate = report['CandidateADF']
    file = canonical(candidate['Path'], BUILD)
    require(sha(file) == candidate['SHA256'] and report.get('CandidateSnapshotMatchesADF') is True,
            'comparison final ADF differs')
    require(report.get('AllTenNativeTimingTablesChecked') is True
            and report.get('NoDataSetupOrHoldFalsePaths') is True, 'comparison coverage is incomplete')
    return {'Provided':True, 'OriginalPath':str(path), 'SHA256':sha(path),
            'NativeComparisonPassed':True,
            'InternalTimingMet':report.get('AllReportedInternalTimingChecksMet') is True,
            'ResetExceptionsApplied':report.get('ResetExceptionsApplied'),
            'CandidateADF':candidate}, path


def archive(destination, stages, evidence_dirs=(), extra_files=(), comparison=None):
    destination = Path(destination).absolute()
    require(destination.resolve() == destination and destination.parent == PROJECT / 'results'
            and not destination.exists(), 'destination must be a fresh direct results child')
    require(stages, 'explicit completed stage list is required')
    require(sha(BASELINE_MANIFEST) == BASELINE_MANIFEST_SHA and sha(BASELINE_ADF) == BASELINE_ADF_SHA,
            'immutable initial candidate/151-item evidence baseline changed')
    stage_paths = {canonical(p, BUILD, directory=True) for p in stages}
    # The original failures are mandatory evidence for this repair session.
    stage_paths.update(BUILD / name for name in PRESERVED_FAILURES)
    completed = [completed_stage(p) for p in sorted(stage_paths)]
    directories = [canonical(p, PROJECT, directory=True) for p in evidence_dirs]
    require(all(p.parent == PROJECT / 'results' and p.name.startswith('processed-output-reset-')
                for p in directories), 'only explicitly selected reset evidence directories are supported')
    extra = [canonical(p, PROJECT) for p in extra_files]
    require(all(p.suffix.lower() in TEXT_SUFFIXES for p in extra), 'extra evidence must be native text')
    comparison_info, comparison_path = comparison_evidence(comparison)
    sources = [canonical(PROJECT / name, PROJECT) for name in SOURCES]
    local = [reference(BASELINE_MANIFEST, 'Original 151-item archive is immutable and referenced only'),
             reference(BASELINE_ADF, 'Original routed baseline remains local')]
    watched = {row['LocalPath']:row['SHA256'] for row in local}
    destination.mkdir()
    files = {}

    def add(path, name, *, compress=None):
        path = canonical(path, PROJECT)
        compress = path.suffix == '.log' or path.stat().st_size >= 131072 if compress is None else compress
        relative = name + ('.gz' if compress else '')
        require(relative not in files and '..' not in Path(relative).parts and not Path(relative).is_absolute(),
                'duplicate/unsafe archive entry')
        files[relative] = copy_bound(path, destination / relative, compress)
        watched[str(path)] = files[relative]['OriginalSHA256']

    for path in sources:
        add(path, 'sources/' + path.relative_to(PROJECT).as_posix(), compress=False)
    stage_summary = []
    for work, status in completed:
        stage_summary.append(status)
        for path in sorted(work.rglob('*')):
            if not path.is_file():
                continue
            relative = path.relative_to(work)
            if any(part in ('compiled','sources','xsim.dir') for part in relative.parts):
                continue
            if (path.suffix.lower() == '.adf' or path.suffix.lower() == '.v' and path.name != 'dummy.v'
                    or path.name == 'route-dump.txt'):
                row = reference(path, 'Routed database or generated netlist with vendor logic; no bytes copied')
                local.append(row)
                watched[str(path)] = row['SHA256']
            elif path.suffix.lower() in TEXT_SUFFIXES or path.name in ('executor-snapshot.py','dummy.v'):
                add(path, 'stages/' + work.name + '/' + relative.as_posix())
    for directory in directories:
        for path in sorted(directory.rglob('*')):
            if path.is_file():
                require(path.suffix.lower() in TEXT_SUFFIXES, 'unexpected reset evidence format')
                add(path, 'reset/' + directory.name + '/' + path.relative_to(directory).as_posix())
    for index, path in enumerate(extra):
        add(path, f'extra/{index:02d}-' + path.name)
    if comparison_path is not None:
        add(comparison_path, 'comparison/' + comparison_path.name)
    for name, digest in watched.items():
        require(sha(name) == digest, 'evidence changed before archive freeze: ' + name)
    manifest = {'Schema':'processed-output-physical-evidence-archive-v1',
                'ArchivedUTC':datetime.now(timezone.utc).isoformat(), 'Destination':str(destination),
                'Stages':stage_summary, 'MandatoryFailedTrialsPreserved':list(PRESERVED_FAILURES),
                'Comparison':comparison_info, 'Files':files, 'LocalReferencesOnly':local,
                'Original151ItemArchiveSHA256':BASELINE_MANIFEST_SHA,
                'CurrentSelfAuthoredHelperSnapshots':list(SOURCES),
                'HardwareAccessedByArchiver':False, 'EDAExecutedByArchiver':False,
                'TimingAccepted':False, 'HardwareReleaseAllowed':False,
                'ReadbackRequired':True, 'ManifestSelfHashExcluded':True,
                'Limits':['Execution success and archive integrity do not constitute timing or hardware acceptance.',
                          'Only the supplied revalidated comparison can report its limited native timing result.',
                          'Generated vendor-containing netlists and routed database bytes are referenced locally, not copied.',
                          'Current helper snapshots are distinguished from per-stage executor snapshots and historical input hashes.',
                          'Failed native trials are preserved with their actual exit codes and diagnostics.']}
    with (destination / 'manifest.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(manifest, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return {'Archived':True, 'Manifest':str(destination / 'manifest.json'), **verify_archive(destination)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('--stage', type=Path, action='append', default=[])
    parser.add_argument('--evidence-dir', type=Path, action='append', default=[])
    parser.add_argument('--extra-file', type=Path, action='append', default=[])
    parser.add_argument('--comparison', type=Path)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    result = (verify_archive(args.destination) if args.verify_only else
              archive(args.destination,args.stage,args.evidence_dir,args.extra_file,args.comparison))
    print(json.dumps(result))


if __name__ == '__main__':
    main()
