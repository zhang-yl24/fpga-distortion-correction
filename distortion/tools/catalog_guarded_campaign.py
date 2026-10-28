"""Index sealed finite hardware runs without promoting failed cases to success.

Rechecks every original snapshot member, source/helper binding, retained wire,
and programming-log hash. This reads files only; no device interface is used.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import zipfile

from audit_guarded_wire import audit_bytes

ROOT = Path(__file__).resolve().parents[1]
APPROVED = ROOT/'build/offline-20261024'
HEARTBEAT = 'df7eec4b4e38441183b45baf8b38d8414fdd456a5eb78fb3aeb1fd94b361b360'
TAGS = {'raw_camera_capture_cam2_guarded': 0x52473201,
        'raw_camera_capture_cam1_guarded': 0x52473101,
        'raw_camera_capture_cam1_guarded_sccb25': 0x52473125,
        'raw_camera_capture_cam1_guarded_isolated': 0x52473149,
        'raw_camera_capture_cam2_guarded_bars': 0x52473242}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def local(path):
    path = Path(path).resolve()
    if not path.is_relative_to(ROOT.resolve()) or not path.is_file():
        raise ValueError('missing or non-project evidence path')
    return path


def catalog_run(run):
    run = Path(run).resolve()
    if run.parent != APPROVED.resolve():
        raise ValueError('require an existing run directly under approved scratch')
    result, plan = load(run/'result.json'), load(run/'plan.json')
    target = plan['program_plan']['target']
    if (target not in TAGS or result['operation'] != 'bounded_guarded_native_then_heartbeat'
            or result['executed'] is not True or result['hardware_accessed'] is not True
            or plan.get('target', target) != target or result.get('target', target) != target
            or result['guarded_program']['target'] != target):
        raise ValueError('require a sealed execution receipt for an explicit validated target')
    idle, programmed = result['idle_program'], result['guarded_program']
    for receipt in (idle, programmed):
        if not (receipt['executed'] and receipt['passed'] and receipt['done_confirmed']
                and receipt['operation'] == 'volatile_sram_only'):
            raise ValueError('programming or final heartbeat event lacks its successful receipt')
        for path, digest in receipt['logs'].items():
            if sha(local(path)) != digest.lower():
                raise ValueError('programming log changed')
    if idle['target'] != 'heartbeat' or idle['bitstream_sha256'].lower() != HEARTBEAT:
        raise ValueError('final SRAM event differs from the fixed heartbeat')
    snapshot = load(run/'implementation-snapshot.json')
    archive = local(snapshot['archive_path'])
    if (Path(snapshot['original_run']).resolve() != run or archive != run/'implementation-snapshot.zip'
            or sha(archive) != snapshot['archive_sha256'] or not snapshot['archive_readback_passed']):
        raise ValueError('implementation snapshot hash differs')
    with zipfile.ZipFile(archive) as packed:
        manifest = json.loads(packed.read('SNAPSHOT-MANIFEST.json'))
        if (Path(manifest['original_run']).resolve() != run
                or manifest['scope'] != 'exact_guarded_execution_and_implementation_snapshot'
                or manifest['operation_result_passed'] is not result['passed']):
            raise ValueError('snapshot belongs to a different sealed run or result')
        archived = {row['archive_path']: row for row in manifest['files']}
        if (len(archived) != len(manifest['files']) or len(archived) != snapshot['verified_files']
                or len(packed.namelist()) != len(set(packed.namelist()))
                or set(packed.namelist()) != set(archived) | {'SNAPSHOT-MANIFEST.json'}):
            raise ValueError('snapshot membership differs')
        required = [run/name for name in ('plan.json', 'result.json', 'received-wire.bin',
                                         'tx-commands.jsonl', 'status-events.jsonl')]
        if (run/'session-summary.json').is_file():
            required.append(run/'session-summary.json')
        required.extend(local(path) for receipt in (idle, programmed) for path in receipt['logs'])
        required.extend(local(Path(receipt['workdir'])/'receipt.json') for receipt in (idle, programmed))
        required.extend(local(record['session_binding_path']) for record in (result, programmed)
                        if record.get('session_binding_path'))
        if any(path.relative_to(ROOT).as_posix() not in archived for path in required):
            raise ValueError('snapshot omits required evidence from this run')
        for name, row in archived.items():
            payload = packed.read(name)
            if len(payload) != row['bytes'] or hashlib.sha256(payload).hexdigest() != row['sha256']:
                raise ValueError('snapshot member failed readback')
            if name.startswith(run.relative_to(ROOT).as_posix()+'/') and sha(local(ROOT/name)) != row['sha256']:
                raise ValueError('sealed original run evidence changed after snapshot')
        build = plan['program_plan']['validation']['build']
        for name, digest in list(build['source_sha256'].items())+list(plan['source_sha256'].items()):
            key = name.replace('\\', '/')
            if key not in archived or archived[key]['sha256'] != digest.lower():
                raise ValueError('original source/helper version missing from its snapshot')
    wire = local(run/'received-wire.bin')
    if sha(wire) != result['received-wire.bin']['sha256']:
        raise ValueError('retained UART wire changed')
    decoded = audit_bytes(wire.read_bytes(), expected_tag=TAGS[target])
    for name in ('tx-commands.jsonl', 'status-events.jsonl'):
        if sha(local(run/name)) != result[name]['sha256']:
            raise ValueError('retained command/status log changed')
    analyses = {path.name: sha(path) for path in run.glob('*.json')
                if path.name.startswith(('independent-', 'digital-', 'historical-'))}
    return {'run': str(run), 'target': target, 'scenario': plan['scenario'],
            'scenario_passed': result['passed'], 'failure': result.get('error'),
            'source_kind': load(run/'session-summary.json')['source_kind'] if (run/'session-summary.json').is_file() else None,
            'status_packets': decoded['status_packets'], 'raw_frames': decoded['raw_frames'],
            'last_status': decoded['statuses'][-1],
            'result_sha256': sha(run/'result.json'), 'plan_sha256': sha(run/'plan.json'),
            'wire_sha256': sha(wire), 'original_source_files': len(build['source_sha256']),
            'original_helper_sha256': plan['source_sha256'],
            'bitstream_sha256': programmed['bitstream_sha256'], 'snapshot': snapshot,
            'analysis_sha256': analyses,
            'last_confirmed_sram_event': {'target': 'heartbeat', 'sha256': HEARTBEAT,
                'receipt_checked_at_utc': idle['checked_at_utc'], 'fresh_post_program_done': True},
            'evidence_integrity_passed': True, 'optical_acceptance_inferred': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='append', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output.parent != (ROOT/'output/project').resolve():
        parser.error('output must be a new file in existing output/project')
    if len({path.resolve() for path in args.run}) != len(args.run):
        parser.error('duplicate run paths are not allowed')
    rows = [catalog_run(path) for path in args.run]
    latest = max((row['last_confirmed_sram_event'] for row in rows),
                 key=lambda row: datetime.fromisoformat(row['receipt_checked_at_utc']))
    report = {'schema': 1, 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'hardware_accessed_by_catalog': False, 'evidence_integrity_passed': True,
              'run_count': len(rows), 'scenario_pass_count': sum(row['scenario_passed'] for row in rows),
              'all_selected_scenarios_passed': all(row['scenario_passed'] for row in rows),
              'last_confirmed_sram_event': latest, 'runs': rows, 'catalog_sha256': sha(__file__),
              'limits': 'Receipt and original snapshot integrity are distinct from scenario success. Later physical state is not continuously observed. Individual analyses have their own pass criteria; this index never promotes a failed camera/color/optical test.'}
    with output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({key: report[key] for key in ('run_count', 'scenario_pass_count', 'evidence_integrity_passed', 'all_selected_scenarios_passed')}))


if __name__ == '__main__':
    main()
