"""Preserve one sealed guarded run and its exact source/bit/helper versions."""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parents[1]
APPROVED = ROOT/'build/offline-20261024'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def other_reset_references(manifest):
    """Preserve the electrical-source evidence required by the reset trial."""
    contract = manifest.get('OtherSensorResetTrialContract')
    if manifest.get('Target') != 'raw_camera_capture_cam1_guarded_isolated':
        if contract is not None:
            raise ValueError('unexpected other-sensor reset contract')
        return {}
    refs = contract.get('reference_source_sha256') if isinstance(contract, dict) else None
    if not isinstance(refs, dict) or len(refs) != 4:
        raise ValueError('isolated target requires four reset reference files')
    result = {}
    for name, expected in refs.items():
        path = (ROOT/name).resolve()
        if (not path.is_relative_to(ROOT.resolve()) or not path.is_file()
                or not isinstance(expected, str) or len(expected) != 64 or sha(path) != expected.lower()):
            raise ValueError('other-sensor reset reference missing, escaped or changed: '+name)
        result[path.relative_to(ROOT).as_posix()] = expected.lower()
    return result


def snapshot(run):
    run = Path(run).resolve()
    if not run.is_dir() or not run.is_relative_to(APPROVED.resolve()):
        raise ValueError('only an existing sealed guarded run in approved scratch may be archived')
    result, plan = load(run/'result.json'), load(run/'plan.json')
    if result.get('operation') != 'bounded_guarded_native_then_heartbeat' or not result.get('executed'):
        raise ValueError('require a completed execution receipt, including failures if applicable')
    archive, receipt = run/'implementation-snapshot.zip', run/'implementation-snapshot.json'
    if archive.exists() or receipt.exists():
        raise ValueError('this source snapshot already exists; never overwrite evidence')
    files = set(path for path in run.rglob('*') if path.is_file())
    for name, expected in plan['source_sha256'].items():
        path = (ROOT/name).resolve()
        if not path.is_relative_to(ROOT.resolve()) or sha(path) != expected.lower():
            raise ValueError('live helper changed before snapshot; preserve its original version first: '+name)
        files.add(path)
    build = plan['program_plan']['validation']['build']
    for name, expected in build['source_sha256'].items():
        path = (ROOT/name).resolve()
        if not path.is_relative_to(ROOT.resolve()) or sha(path) != expected.lower():
            raise ValueError('routed source changed before snapshot: '+name)
        files.add(path)
    for path_key, hash_key in (('manifest_path', 'manifest_sha256'), ('bitstream_path', 'bitstream_sha256'),
            ('pinout_path', 'pinout_sha256'), ('timing_report_path', 'timing_sha256')):
        if sha(build[path_key]) != build[hash_key].lower():
            raise ValueError('bound routed artifact changed before snapshot: '+path_key)
    manifest_path = Path(build['manifest_path'])
    manifest = load(manifest_path)
    reset_references = other_reset_references(manifest)
    files.update(ROOT/name for name in reset_references)
    if sha(manifest['PinReport']) != build['pin_report_sha256'].lower():
        raise ValueError('routed pin report changed before snapshot')
    if sha(ROOT/f'board/{manifest["Target"]}-sources.json') != build['prepared_source_manifest_sha256'].lower():
        raise ValueError('prepared source manifest changed before snapshot')
    files.update(Path(build[key]) for key in ('manifest_path', 'bitstream_path', 'pinout_path', 'timing_report_path'))
    files.add(Path(manifest['PinReport']))
    files.add(ROOT/f'board/{manifest["Target"]}-sources.json')
    files.add(ROOT/'output/project/guarded-protocol-v2.json')
    # Include all fixed idle dependencies, not only restoration logs.
    idle = plan['idle_plan']['validation']
    idle_bit = ROOT/'build/heartbeat/generate_bitstream/heartbeat.sbit'
    if sha(idle_bit) != idle['bitstream_sha256'].lower():
        raise ValueError('idle bitstream changed before snapshot')
    files.add(idle_bit)
    for name, expected in {**idle['source_sha256'], **idle['artifact_sha256']}.items():
        if sha(ROOT/name) != expected.lower():
            raise ValueError('idle artifact/source changed before snapshot: '+name)
        files.add(ROOT/name)
    if (ROOT/'tools/audit_guarded_wire.py').is_file():
        files.add(ROOT/'tools/audit_guarded_wire.py')
    files.add(Path(__file__).resolve())
    records = []
    for path in sorted(files):
        if not path.is_file() or not path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError('snapshot contains a missing/non-project file: '+str(path))
        records.append({'archive_path': path.relative_to(ROOT).as_posix(), 'bytes': path.stat().st_size, 'sha256': sha(path)})
    provenance = {'schema': 1, 'scope': 'exact_guarded_execution_and_implementation_snapshot',
        'original_run': str(run), 'operation_result_passed': result.get('passed'), 'files': records,
        'other_sensor_reset_reference_sha256': reset_references,
        'limits': 'Exact source and evidence versions, not a new hardware test or optical/stereo certification. Absolute paths inside original records describe the originating host; archive paths and SHA256 provide portable readback.'}
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as stream:
        for record in records:
            path = ROOT/record['archive_path']
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != record['sha256']:
                raise ValueError('file changed during snapshot: '+record['archive_path'])
            stream.writestr(record['archive_path'], data)
        stream.writestr('SNAPSHOT-MANIFEST.json', json.dumps(provenance, ensure_ascii=False, indent=2))
    with zipfile.ZipFile(archive) as stream:
        if len(stream.namelist()) != len(set(stream.namelist())):
            raise ValueError('duplicate archive members')
        for record in records:
            data = stream.read(record['archive_path'])
            if len(data) != record['bytes'] or hashlib.sha256(data).hexdigest() != record['sha256']:
                raise ValueError('snapshot readback differs: '+record['archive_path'])
    output = {'schema': 1, 'archive_path': str(archive), 'archive_sha256': sha(archive),
        'archive_bytes': archive.stat().st_size, 'verified_files': len(records),
        'archive_readback_passed': True, 'original_run': str(run), 'hardware_accessed_by_archiver': False}
    with receipt.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(output, ensure_ascii=False, indent=2)+'\n')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(snapshot(args.run_dir), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
