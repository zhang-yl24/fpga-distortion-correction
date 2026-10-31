"""Archive explicit completed camera physical evidence, entirely on the CPU.

Use --config to freeze a fresh archive, --config ... --validate-only to inspect
the completed inputs without writing, or --verify-only DIRECTORY for readback.
ADF databases, route dumps and generated vendor netlists remain local hash
references. Native failures are preserved as failures; archiving grants no
timing or hardware approval. The example configuration is intentionally not a
discovery mechanism: the owner supplies the final stages and final audit.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil

PROJECT = Path(__file__).resolve().parents[1]
WORK = PROJECT / 'work/camera-vga-output'
TOOL = Path(__file__).resolve()
SCHEMA = 'camera-vga-physical-archive-config-v1'
ARCHIVE_SCHEMA = 'camera-vga-physical-evidence-archive-v1'
STAGE_SCHEMAS = {'camera-vga-isolated-query-v1', 'camera-vga-functional-export-v1',
                 'camera-vga-physical-repair-v1'}
TEXT_SUFFIXES = {'.json', '.log', '.tcl', '.fdc', '.rcf', '.rtr', '.rtx', '.rpt', '.txt',
                 '.csv', '.cmr', '.snr', '.dmr', '.ccr', '.pcf', '.prr', '.prt', '.ror',
                 '.plr', '.rur', '.gnr', '.md'}
SOURCE_SUFFIXES = {'.py', '.v', '.sv', '.vh', '.json', '.md'}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def canonical(value, parent=None, directory=False):
    parent = PROJECT if parent is None else Path(parent)
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT / path
    require('..' not in path.parts, 'parent traversal is forbidden')
    path = path.absolute()
    require(path.resolve() == path and path.is_relative_to(parent.resolve()),
            'escaped or linked evidence: ' + str(path))
    require(path.is_dir() if directory else path.is_file(), 'missing evidence: ' + str(path))
    return path


def binding(path):
    return {'LocalPath': str(path), 'SHA256': sha(path), 'Bytes': path.stat().st_size}


def file_set(directory):
    return {canonical(p, directory) for p in directory.rglob('*') if p.is_file()}


def completed_stage(path):
    work = canonical(path, WORK, directory=True)
    require(work.parent == WORK, 'stage must be a direct camera work child')
    receipt_path = canonical(work / 'result.json', work)
    receipt = load(receipt_path)
    require(receipt.get('Schema') in STAGE_SCHEMAS, 'unknown native stage schema')
    require(isinstance(receipt.get('FinishedUTC'), str) and receipt['FinishedUTC'] and
            type(receipt.get('ExitCode')) is int and type(receipt.get('ExecutionPassed')) is bool,
            'native stage is not completed: ' + work.name)
    require(receipt.get('HardwareAccessed') is False and receipt.get('BitstreamRequested') is False,
            'unexpected hardware scope in native stage')
    artifacts = receipt.get('Artifacts')
    require(isinstance(artifacts, dict) and artifacts, 'stage has no bound artifacts')
    for name, digest in artifacts.items():
        require(not Path(name).is_absolute(), 'absolute stage artifact name')
        path = canonical(work / name, work)
        require(sha(path) == digest, 'stage artifact changed after completion: ' + str(path))
    keys = ('Schema', 'StartedUTC', 'FinishedUTC', 'ExitCode', 'ExecutionPassed', 'TimedOut',
            'Diagnostics', 'InputDrift', 'ActualStages', 'SourceADFSHA256', 'ResultADFSHA256',
            'InputADFUnchanged', 'TimingAccepted', 'HardwareReleaseAllowed')
    status = {key: receipt.get(key) for key in keys}
    status.update(OriginalDirectory=str(work), ReceiptSHA256=sha(receipt_path),
                  FailedTrialPreserved=not receipt['ExecutionPassed'],
                  HistoricalInputHashesPreservedVerbatim=True)
    return work, status


def final_audit(path):
    path = canonical(path)
    audit = load(path)
    require(audit.get('Schema') in ('camera-vga-physical-comparison-v1',
                                   'camera-vga-physical-union-comparison-v1') and
            audit.get('AuditPassed') is True, 'completed camera comparison audit is required')
    require(audit.get('HardwareAccessed') is False and audit.get('HardwareReleaseAllowed') is False,
            'audit hardware boundary differs')
    watched = {path: sha(path)}
    documents = [audit]
    union_token = None
    if audit['Schema'] == 'camera-vga-physical-union-comparison-v1':
        union_token = audit.get('ExceptionUnionComparison')
        require(isinstance(union_token, dict) and isinstance(union_token.get('Proof'), str) and
                isinstance(union_token.get('ProofSHA256'), str) and
                re.fullmatch(r'[0-9a-f]{64}', union_token['ProofSHA256']),
                'union comparison requires an explicit bound proof')
        proof_path = canonical(union_token['Proof'])
        proof_hash = union_token['ProofSHA256']
        require(sha(proof_path) == proof_hash, 'exception union proof hash differs')
        require(audit.get('InputSHA256', {}).get(str(proof_path)) == proof_hash,
                'exception union proof is not bound by final audit')
        proof = load(proof_path)
        require(proof.get('Schema') == 'camera-vga-exception-union-comparison-v1' and
                proof.get('AuditPassed') is True and proof.get('MembershipCompletedFromBothUnions') is True,
                'successful complete exception union proof required')
        watched[proof_path] = proof_hash
        documents.append(proof)
    for document in documents:
        for group in ('InputSHA256', 'ToolSHA256'):
            require(isinstance(document.get(group), dict) and document[group], 'audit lacks bound ' + group)
            for name, digest in document[group].items():
                source = canonical(name)
                require(sha(source) == digest, 'final audit input drift: ' + str(source))
                require(source not in watched or watched[source] == digest, 'conflicting audit hash')
                watched[source] = digest
    summary = {key: audit.get(key) for key in ('Schema', 'AuditedUTC', 'AuditPassed', 'ResetScoped',
               'AllInternalChecksMet', 'ClockDefinitionsAndLoadsUnchanged', 'NoDataFalsePaths',
               'CornerSummaries', 'FalsePathCounts', 'HardwareAccessed', 'HardwareReleaseAllowed',
               'ExternalIOAccepted', 'Limits')}
    summary.update(OriginalPath=str(path), SHA256=sha(path), BoundInputsRevalidated=True)
    if union_token is not None:
        summary.update(ExceptionUnionComparison=union_token, ExceptionUnionProofRevalidated=True)
    return path, summary, watched


def local_only_reason(path, relative=None):
    if path.suffix.lower() == '.adf':
        return 'Native ADF database; keep original bytes local.'
    if path.name.lower().startswith('route-dump'):
        return 'Full native route dump; keep original bytes local.'
    if relative is not None and any(p in ('compiled', 'sources', 'xsim.dir') for p in relative.parts):
        return 'Staged implementation/source tree; preserve a local hash reference.'
    if path.suffix.lower() in ('.v', '.sv', '.vh', '.vm', '.vqm') and path.name != 'dummy.v':
        return 'Generated HDL may contain full vendor logic; keep original bytes local.'
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in ('executor-snapshot.py', 'dummy.v'):
        return 'Non-text or unclassified native artifact; preserve a local hash reference.'
    return None


def prepare(config_path):
    config_path = canonical(config_path)
    config = load(config_path)
    fields = {'Schema', 'Destination', 'Stages', 'FinalAudit', 'EvidenceDirectories', 'SourceFiles', 'ExtraFiles'}
    require(set(config) == fields and config.get('Schema') == SCHEMA, 'unsupported archive config fields/schema')
    destination = Path(config['Destination'])
    if not destination.is_absolute():
        destination = PROJECT / destination
    destination = destination.absolute()
    require(destination.resolve() == destination and destination.parent == PROJECT / 'results' and
            re.fullmatch(r'camera-vga-physical-[A-Za-z0-9_-]+', destination.name) and not destination.exists(),
            'destination must be a fresh direct camera physical results child')
    for field in ('Stages', 'EvidenceDirectories', 'SourceFiles', 'ExtraFiles'):
        require(isinstance(config[field], list) and all(isinstance(x, str) for x in config[field]),
                field + ' must be a path list')
    require(config['Stages'], 'explicit completed stages are required')
    completed = [completed_stage(p) for p in config['Stages']]
    require(len({p for p, _ in completed}) == len(completed), 'duplicate selected stage')
    audit_path, audit_summary, watched = final_audit(config['FinalAudit'])
    watched[config_path] = sha(config_path)
    selected, refs, directories = {}, {}, {}

    def add(path, name, reason=None):
        path = canonical(path)
        require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'unsafe archive member')
        digest = sha(path)
        require(path not in watched or watched[path] == digest, 'input changed while preparing archive')
        watched[path] = digest
        if reason:
            refs[path] = {**binding(path), 'Copied': False, 'Reason': reason}
        else:
            require(name not in selected and path not in selected.values(), 'duplicate copied source/member')
            selected[name] = path

    add(config_path, 'configuration.json')
    add(TOOL, 'sources/tools/' + TOOL.name)
    for work, _ in completed:
        directories[work] = file_set(work)
        for path in sorted(directories[work]):
            relative = path.relative_to(work)
            add(path, 'stages/' + work.name + '/' + relative.as_posix(), local_only_reason(path, relative))
    for value in config['EvidenceDirectories']:
        directory = canonical(value, directory=True)
        require((directory.parent == PROJECT / 'results' and
                 directory.name.startswith(('camera-vga-hold-analysis-', 'camera-vga-reset-analysis-'))) or
                (directory.parent == WORK and directory.name.startswith('reset-proof-')),
                'unsupported camera analysis/proof directory')
        require(directory not in directories, 'duplicate evidence directory')
        directories[directory] = file_set(directory)
        for path in sorted(directories[directory]):
            add(path, 'analysis/' + directory.name + '/' + path.relative_to(directory).as_posix(),
                local_only_reason(path))
    for value in config['SourceFiles']:
        path = canonical(value)
        require(path.parent in (PROJECT / 'tools', PROJECT / 'tests') and path.suffix.lower() in SOURCE_SUFFIXES,
                'source snapshot must be an explicit self-authored tool/test')
        if path == TOOL:
            continue
        add(path, 'sources/' + path.relative_to(PROJECT).as_posix())
    for index, value in enumerate(config['ExtraFiles']):
        path = canonical(value)
        if path in selected.values():
            continue
        add(path, f'extra/{index:02d}-' + path.name, local_only_reason(path))
    if audit_path not in selected.values():
        add(audit_path, 'audit/' + audit_path.name)
    for path in watched.copy():
        if path not in selected.values() and path not in refs:
            refs[path] = {**binding(path), 'Copied': False, 'Reason': 'Final audit dependency; original is locally hash-bound.'}
    for path in selected.values():
        refs.pop(path, None)
    require(all(sha(path) == digest for path, digest in watched.items()), 'input drift during archive preflight')
    return {'Config': config_path, 'Destination': destination, 'Stages': [s for _, s in completed],
            'Audit': audit_summary, 'Selected': selected, 'References': refs, 'Watched': watched,
            'DirectoryInventories': directories}


def copy_bound(source, target, compress):
    original = binding(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open('rb') as incoming, target.open('xb') as outgoing:
        if compress:
            with gzip.GzipFile(filename='', mode='wb', fileobj=outgoing, mtime=0) as encoded:
                shutil.copyfileobj(incoming, encoded, 1 << 20)
        else:
            shutil.copyfileobj(incoming, outgoing, 1 << 20)
    require(binding(source) == original, 'source changed during copy: ' + str(source))
    return {'Origin': str(source), 'SHA256': sha(target), 'Bytes': target.stat().st_size,
            'Encoding': 'gzip' if compress else 'identity', 'OriginalSHA256': original['SHA256'],
            'OriginalBytes': original['Bytes']}


def verify_payloads(destination, files):
    for name, row in files.items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'unsafe archive member')
        path = canonical(destination / name, destination)
        require(sha(path) == row['SHA256'] and path.stat().st_size == row['Bytes'], 'encoded archive hash differs')
        require(row['Encoding'] in ('identity', 'gzip'), 'unsupported encoding')
        digest, count = hashlib.sha256(), 0
        opener = gzip.open if row['Encoding'] == 'gzip' else open
        with opener(path, 'rb') as stream:
            for block in iter(lambda: stream.read(1 << 20), b''):
                digest.update(block); count += len(block)
        require(digest.hexdigest() == row['OriginalSHA256'] and count == row['OriginalBytes'],
                'decoded archive content differs')


def verify_archive(destination):
    destination = canonical(destination, PROJECT / 'results', directory=True)
    manifest_path = destination / 'manifest.json'
    manifest = load(manifest_path)
    require(manifest.get('Schema') == ARCHIVE_SCHEMA, 'archive schema differs')
    verify_payloads(destination, manifest['Files'])
    actual = {p.relative_to(destination).as_posix() for p in file_set(destination)}
    require(actual == set(manifest['Files']) | {'manifest.json'}, 'unexpected or missing archive member')
    for row in manifest['LocalReferencesOnly']:
        path = canonical(row['LocalPath'])
        require(sha(path) == row['SHA256'] and path.stat().st_size == row['Bytes'], 'local reference drift')
    return {'ReadbackVerified': True, 'Files': len(manifest['Files']),
            'LocalReferencesVerified': len(manifest['LocalReferencesOnly']),
            'ManifestSHA256': sha(manifest_path), 'HardwareReleaseAllowed': False}


def archive(config_path):
    plan = prepare(config_path)
    destination = plan['Destination']
    destination.mkdir()
    files = {}
    for name, source in sorted(plan['Selected'].items()):
        compress = source.suffix.lower() in ('.rtr', '.rtx') or source.stat().st_size >= 131072
        target = name + ('.gz' if compress else '')
        require(target not in files, 'compressed archive name collision')
        files[target] = copy_bound(source, destination / target, compress)
    verify_payloads(destination, files)
    for path, digest in plan['Watched'].items():
        require(sha(path) == digest, 'input drift before archive freeze: ' + str(path))
    for directory, expected in plan['DirectoryInventories'].items():
        require(file_set(directory) == expected, 'stage/evidence directory changed during archive')
    manifest = {'Schema': ARCHIVE_SCHEMA, 'ArchivedUTC': datetime.now(timezone.utc).isoformat(),
                'Destination': str(destination), 'Stages': plan['Stages'], 'FinalAudit': plan['Audit'],
                'Files': files, 'LocalReferencesOnly': [r for _, r in sorted(plan['References'].items())],
                'FailedTrialCount': sum(s['FailedTrialPreserved'] for s in plan['Stages']),
                'ExplicitStageListOnly': True, 'PerFileDecodedReadbackVerifiedBeforeManifest': True,
                'InputsUnchangedAtFreeze': True, 'ManifestSelfHashExcluded': True,
                'EDAExecutedByArchiver': False, 'HardwareAccessedByArchiver': False,
                'TimingAcceptedByArchiver': False, 'HardwareReleaseAllowed': False,
                'Limits': ['FinalAudit reports only its original revalidated scope; this archive adds no timing approval.',
                           'Failed stages retain original exit codes and diagnostics.',
                           'Current source snapshots and historical per-stage input hashes are separate evidence.',
                           'ADF, route dumps and generated vendor HDL remain local; this archive is not self-contained.']}
    with (destination / 'manifest.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(manifest, stream, indent=2, allow_nan=False); stream.write('\n')
    return {'Archived': True, 'Manifest': str(destination / 'manifest.json'), **verify_archive(destination)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--config', type=Path)
    choice.add_argument('--verify-only', type=Path, metavar='DIRECTORY')
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    require(not args.validate_only or args.config is not None, '--validate-only requires --config')
    if args.verify_only:
        result = verify_archive(args.verify_only)
    elif args.validate_only:
        plan = prepare(args.config)
        result = {'Validated': True, 'FilesWouldCopy': len(plan['Selected']),
                  'LocalReferences': len(plan['References']), 'Stages': len(plan['Stages']),
                  'Destination': str(plan['Destination']), 'FilesWritten': False, 'EDAExecuted': False}
    else:
        result = archive(args.config)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
