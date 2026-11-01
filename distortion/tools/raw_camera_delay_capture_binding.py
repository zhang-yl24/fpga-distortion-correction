"""Create source-bound PGFRAME1 records without inventing hardware declarations.

Default output is a pending binding with every connection declaration false.
A live-ready binding additionally needs explicit connection-review evidence
and a clean, same-bitstream native SRAM programming receipt. No device access.
"""
import argparse
import copy
import json
from pathlib import Path
import re

import raw_camera_delay_bitstream as bit
import raw_camera_delay_program as program
import native_camera_capture as capture

prep, require, sha = bit.prep, bit.require, bit.sha
SELF = Path(__file__).resolve()
RECORD_SCHEMA = 'raw-camera-delay-capture-build-v1'
REVIEW_SCHEMA = 'raw-camera-delay-connection-review-v1'
CONTRACT = {'protocol':'PGFRAME1', 'payload_role':'native_raw',
            'geometry_applied':False, 'image_size':[640,480]}


def read(path):
    return capture.load_json(path)


def lower_binding(path):
    return {'path':str(Path(path).resolve()), 'sha256':sha(path)}


def checked_source_closure(manifest, plan):
    require(manifest.get('Target') == prep.TARGET and manifest.get('RawCaptureContract') == CONTRACT
            and plan.get('RawCaptureContract') == CONTRACT, 'current native raw contract required')
    sources = manifest.get('SourceSHA256')
    require(isinstance(sources, dict) and sources and set(sources) == set(manifest['source_files']),
            'complete manifest source closure required')
    for name, digest in sources.items():
        path = (prep.PROJECT / name).resolve()
        require(path.is_relative_to(prep.PROJECT) and path.is_file() and sha(path) == digest
                and plan['InputSHA256'].get(name) == digest, 'build source drift: ' + name)
    pins = prep.baseline.RAW_PINS
    require(pins in sources, 'pinout JSON must belong to the built source closure')
    require(capture.audit_pin_map(read(prep.PROJECT / pins), 'CAM2')['passed'], 'CAM2 pinout audit failed')
    return dict(sources), prep.PROJECT / pins


def review_declarations(path):
    value = read(path)
    keys = set(capture.CONNECTION_FIELDS[:-1])
    require(set(value) == {'Schema','Target','Eye','Declarations','Evidence'}
            and value['Schema'] == REVIEW_SCHEMA and value['Target'] == prep.TARGET
            and value['Eye'] == 'CAM2', 'explicit current CAM2 review required')
    declarations, evidence = value['Declarations'], value['Evidence']
    require(isinstance(declarations, dict) and set(declarations) == keys
            and all(v is True for v in declarations.values()), 'three explicit connection declarations required')
    require(isinstance(evidence, dict) and set(evidence) == keys
            and all(isinstance(v, str) and v.strip() for v in evidence.values()), 'each declaration needs its actual review evidence')
    return declarations


def checked_program_receipt(path, bitwork, verified):
    path = bit.inspect.canonical(path, prep.WORK)
    require(path.name == 'receipt.json', 'exact native programming receipt required')
    value = read(path)
    require(value.get('Schema') == 'raw-camera-delay-sram-execution-v1' and value.get('Target') == prep.TARGET,
            'another candidate programming receipt is forbidden')
    for flag in ('Passed','Executed','HardwareAccessed','ProgrammingAttempted','DoneConfirmed',
                 'UserConfirmedBoardPowered','UserNotifiedBeforeExecution','CurrentPowerConfirmationAsserted'):
        require(value.get(flag) is True, 'unconfirmed programming flag: ' + flag)
    require(value.get('FlashWritten') is False and value.get('CleanupErrors') == [] and not value.get('Error'),
            'programming must complete SRAM-only with clean cleanup')
    plan_path = path.parent / 'plan.json'
    plan = program.validate(plan_path)
    require(value['PlanSHA256'] == sha(plan_path) and value['ExecutorSHA256'] == sha(program.SELF)
            and Path(plan['BitstreamWorkDirectory']) == bitwork
            and value['Bitstream'] == plan['Bitstream'] == verified['Bitstream']
            and value['CandidateADFSHA256'] == verified['CandidateADFSHA256'],
            'programming receipt differs from verified bit and prepared plan')
    logs = value.get('Logs')
    require(isinstance(logs, dict) and {'scan.out.log','scan.err.log','program.out.log','program.err.log'} <= set(logs),
            'complete native scan/program logs required')
    for name, digest in logs.items():
        log = bit.inspect.canonical(path.parent / name, path.parent)
        require(sha(log) == digest, 'program log drift: ' + name)
    for stage in ('scan', 'program'):
        require((path.parent / (stage+'.err.log')).read_bytes() == b'', 'native programming stderr is not empty')
        text = (path.parent / (stage+'.out.log')).read_text(encoding='utf-8', errors='replace')
        require(not re.search(r'(?im)\b(error|failed|fatal)\b', text), 'native programming log contains errors')
        (program.hw._check_scan if stage == 'scan' else program.hw._check_program)(text)
    return value


def identity_from_template(template):
    capture.validate_binding(template)
    require(template['eye'] == 'CAM2' and template['image_size'] == [640,480], 'only current CAM2 VGA capture is supported')
    return {k:copy.deepcopy(template[k]) for k in ('schema', *capture.IDENTITY_FIELDS, 'image_size', 'pixel_format')}


def prepare(bitwork, identity_path, output_dir, *, connection_review=None, program_receipt=None):
    bitwork = prep.work_path(bitwork); output_dir = prep.work_path(output_dir)
    require(not output_dir.exists(), 'fresh binding output directory required')
    require((connection_review is None) == (program_receipt is None),
            'live-ready output needs both explicit connection review and native programming receipt')
    identity_path = bit.inspect.canonical(identity_path, prep.PROJECT.parent)
    identity_sha = sha(identity_path); binding = identity_from_template(read(identity_path))
    verified = bit.verify(bitwork); bitplan, context = bit.validate(bitwork)
    require(verified['Verified'] is True and verified['Target'] == prep.TARGET, 'verified current raw bit required')
    build = context['Build']; manifest_path = prep.PROJECT / prep.MANIFEST
    manifest = read(manifest_path); sources, pins = checked_source_closure(manifest, build)
    timing = bitwork / bit.REPORT
    bit.passed_tables(timing)
    require(re.search(r'(?m)^\s*(?:Design Summary\s*:\s*)?All Constraints Met\.?\s*$',
                      timing.read_text(encoding='utf-8', errors='replace')), 'native receiver requires actual All Constraints Met report')
    review = {name:False for name in capture.CONNECTION_FIELDS}
    confirmations = None
    if connection_review is not None:
        connection_review = bit.inspect.canonical(connection_review, prep.PROJECT.parent)
        declared = review_declarations(connection_review)
        checked_program_receipt(program_receipt, bitwork, verified)
        review.update(declared); review['programmed_bound_bitstream'] = True
        confirmations = {'ConnectionReview':lower_binding(connection_review), 'ProgramReceipt':lower_binding(program_receipt)}
    record = {'Schema':RECORD_SCHEMA, 'CreatedUTC':prep.utc(), 'Target':prep.TARGET,
              'Device':program.hw.DEVICE, 'SCBV':'High Voltage', 'SHA256':verified['Bitstream']['SHA256'],
              'TimingSHA256':sha(timing), 'RawCaptureContract':copy.deepcopy(CONTRACT), 'SourceSHA256':sources,
              'SourceManifest':lower_binding(manifest_path), 'BuildPlan':lower_binding(context['PlanPath']),
              'BitstreamPlan':lower_binding(bitwork/'bitstream-plan.json'),
              'Bitstream':verified['Bitstream'], 'CandidateADFSHA256':verified['CandidateADFSHA256'],
              'NativeTiming':verified['NativeTiming'], 'BitEvidenceSHA256':verified['EvidenceSHA256'],
              'HardwareAccessed':False, 'ActualConnectionIndependentlyObserved':False,
              'ExternalACTimingAccepted':False, 'BindingToolSHA256':sha(SELF)}
    require(sha(identity_path) == identity_sha and not bit.inspect.drift(context['Watched']), 'capture record input drift')
    output_dir.mkdir()
    record_path = output_dir / 'validated-build.json'
    with record_path.open('x', encoding='utf-8', newline='\n') as f: json.dump(record, f, indent=2); f.write('\n')
    binding.update(connection_review=review, build_binding={
        'validated_build':lower_binding(record_path), 'bitstream':lower_binding(verified['Bitstream']['Path']),
        'pinout':lower_binding(pins), 'timing_report':lower_binding(timing)})
    binding['status'] = 'LIVE_READY_OPERATOR_DECLARATIONS_BOUND' if confirmations else 'PENDING_CONNECTION_AND_PROGRAMMING'
    binding['provenance'] = {'identity_template':lower_binding(identity_path), 'confirmations':confirmations,
                             'declarations_are_operator_supplied':True, 'hardware_accessed_by_binding_tool':False}
    live = capture.validate_live_binding(binding, base_dir=output_dir) if confirmations else None
    name = 'binding.json' if confirmations else 'binding.pending.json'
    with (output_dir/name).open('x', encoding='utf-8', newline='\n') as f: json.dump(binding, f, indent=2); f.write('\n')
    return {'Prepared':True, 'ValidatedBuild':str(record_path), 'Binding':str(output_dir/name),
            'LiveReady':bool(confirmations), 'LiveValidation':live, 'HardwareAccessed':False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('bit-work', 'identity-template', 'output-dir'): p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--connection-review', type=Path); p.add_argument('--program-receipt', type=Path)
    a = p.parse_args()
    print(json.dumps(prepare(a.bit_work, a.identity_template, a.output_dir,
                            connection_review=a.connection_review, program_receipt=a.program_receipt), indent=2))


if __name__ == '__main__': main()
