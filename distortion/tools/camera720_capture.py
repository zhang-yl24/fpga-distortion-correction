"""Bind and passively receive one current720 native frame; no programming.

Live binding deliberately fails until the separate camera720_raw_bitstream and
camera720_raw_program providers exist and verify the actual new candidate.
Those providers must expose the existing verify/validate/context interfaces.
Offline replay never acquires physical-camera provenance. UART is receive-only;
there is no trigger, serial command, JTAG call or end-of-session heartbeat.
"""
import argparse
import copy
from datetime import datetime, timezone
import importlib
import json
import math
from pathlib import Path
import re

import native_camera_capture as capture
from frame_protocol import FrameParser

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
TARGET = 'raw_camera_capture_cam2_current720'
MODE = 'current720-rgb565-upright-3820-41-3821-07'
PROFILE = 'current720-current-lens-uncalibrated'
SIZE = [1280, 720]
PAYLOAD_BYTES = 1843200
BAUD = 921600
CONTRACT = {'protocol': 'PGFRAME1', 'payload_role': 'native_raw',
            'geometry_applied': False, 'image_size': SIZE}
BOARD = {'inner_corners': [6, 9], 'square_size_mm': 25.0,
         'source': 'user-declared 7x10 squares, 25mm; board presence not inferred'}
REVIEW_SCHEMA = 'camera720-raw-connection-review-v1'
RECORD_SCHEMA = 'camera720-raw-capture-build-v1'
PROGRAM_SCHEMA = 'camera720-raw-sram-execution-v1'
read, sha = capture.load_json, capture.sha


def require(condition, message):
    if not condition:
        raise ValueError(message)


def binding(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': sha(path)}


def write_new(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def providers():
    modules = []
    for name in ('camera720_raw_bitstream', 'camera720_raw_program'):
        expected = ROOT/'tools'/(name+'.py')
        require(expected.is_file(), name+' is unavailable; no current720 raw bit is authorized for capture')
        module = importlib.import_module(name)
        require(Path(module.__file__).resolve() == expected.resolve()
                and module.prep.TARGET == TARGET and callable(getattr(module, 'validate', None)),
                'exact current720 raw release provider required')
        modules.append(module)
    require(callable(getattr(modules[0], 'verify', None)), 'actual raw bit verifier required')
    return tuple(modules)


def identity_from_template(value):
    capture.validate_binding(value)
    require(value['eye'] == 'CAM2', 'current720 uses the reviewed CAM2 connection')
    # Keep the physical camera/lens names; never inherit VGA K/D or mode acceptance.
    result = {k: copy.deepcopy(value[k]) for k in ('schema', 'camera_id', 'lens_id', 'eye')}
    result.update(profile_id=PROFILE, capture_mode_id=MODE, image_size=list(SIZE),
                  pixel_format='RGB565_LE', calibration_accepted=False,
                  checkerboard=copy.deepcopy(BOARD))
    return result


def connection_declarations(path):
    value = read(path)
    keys = set(capture.CONNECTION_FIELDS[:-1])
    require(set(value) == {'Schema', 'Target', 'Eye', 'Declarations', 'Evidence'}
            and value['Schema'] == REVIEW_SCHEMA and value['Target'] == TARGET
            and value['Eye'] == 'CAM2', 'explicit current720 CAM2 connection review required')
    require(isinstance(value['Declarations'], dict) and set(value['Declarations']) == keys
            and all(x is True for x in value['Declarations'].values()), 'connection declarations must be explicit')
    require(isinstance(value['Evidence'], dict) and set(value['Evidence']) == keys
            and all(isinstance(x, str) and x.strip() for x in value['Evidence'].values()),
            'each connection declaration needs retained actual evidence')
    return value['Declarations']


def checked_sources(manifest, build):
    require(manifest.get('Target') == TARGET and manifest.get('RawCaptureContract') == CONTRACT
            and build.get('RawCaptureContract') == CONTRACT, 'exact full720 native raw build contract required')
    sources = manifest.get('SourceSHA256')
    require(isinstance(sources, dict) and sources and set(sources) == set(manifest['source_files']),
            'complete raw source manifest required')
    for name, digest in sources.items():
        path = (ROOT/name).resolve()
        require(path.is_relative_to(ROOT) and path.is_file() and capture.valid_digest(digest)
                and sha(path) == digest and build['InputSHA256'].get(name) == digest,
                'raw build source drift: '+str(name))
    return dict(sources)


def checked_program(path, bitwork, verified, program):
    path = Path(path).resolve()
    require(path.name == 'receipt.json', 'actual native programming receipt required')
    value = read(path)
    require(value.get('Schema') == PROGRAM_SCHEMA and value.get('Target') == TARGET,
            'another target or unaudited raw programming receipt is forbidden')
    for flag in ('Passed', 'Executed', 'HardwareAccessed', 'ProgrammingAttempted', 'DoneConfirmed',
                 'UserConfirmedBoardPowered', 'UserNotifiedBeforeExecution'):
        require(value.get(flag) is True, 'missing actual programming flag: '+flag)
    require(value.get('FlashWritten') is False and value.get('CleanupErrors') == [] and not value.get('Error'),
            'clean volatile SRAM completion required')
    plan_path = path.parent/'plan.json'
    plan = program.validate(plan_path)
    require(value['PlanSHA256'] == sha(plan_path) and value['ExecutorSHA256'] == sha(program.SELF)
            and Path(plan['BitstreamWorkDirectory']).resolve() == bitwork
            and value['Bitstream'] == plan['Bitstream'] == verified['Bitstream']
            and value['CandidateADFSHA256'] == verified['CandidateADFSHA256'],
            'program receipt does not bind this verified raw bit')
    logs = value.get('Logs')
    require(isinstance(logs, dict) and {'scan.out.log', 'scan.err.log', 'program.out.log', 'program.err.log'} <= set(logs),
            'actual scan/program logs required')
    for name, digest in logs.items():
        log = (path.parent/name).resolve()
        require(log.is_relative_to(path.parent) and log.is_file() and sha(log) == digest, 'program log drift')
    for stage in ('scan', 'program'):
        require((path.parent/(stage+'.err.log')).read_bytes() == b'', 'program stderr must be empty')
        text = (path.parent/(stage+'.out.log')).read_text(encoding='utf-8', errors='replace')
        require(not re.search(r'(?im)\b(error|failed|fatal)\b', text), 'native program log reports failure')
        (program.hw._check_scan if stage == 'scan' else program.hw._check_program)(text)
    return value


def release_context(bitwork, program_receipt):
    bit, program = providers()
    bitwork = Path(bitwork).resolve()
    verified = bit.verify(bitwork)
    require(verified.get('Verified') is True and verified.get('Target') == TARGET,
            'fully verified actual current720 raw bit required')
    _, context = bit.validate(bitwork)
    manifest_path = ROOT/bit.prep.MANIFEST
    manifest = read(manifest_path)
    sources = checked_sources(manifest, context['Build'])
    pins_name = getattr(bit.prep, 'RAW_PINS', 'board/raw_camera_capture_cam2_ref-pins.json')
    require(pins_name in sources, 'CAM2 pinout JSON must be source-bound')
    pins = ROOT/pins_name
    require(capture.audit_pin_map(read(pins), 'CAM2')['passed'], 'CAM2 pins differ')
    timing = bitwork/bit.REPORT
    bit.passed_tables(timing)
    require(re.search(r'(?m)^\s*(?:Design Summary\s*:\s*)?All Constraints Met\.?\s*$',
                      timing.read_text(encoding='utf-8', errors='replace')), 'actual passing final STA required')
    checked_program(program_receipt, bitwork, verified, program)
    watched = {str(Path(x).resolve()): h for x, h in context['Watched'].items()}
    for file in (SELF, Path(capture.__file__), ROOT/'tools/frame_protocol.py', Path(program_receipt),
                 Path(program_receipt).parent/'plan.json', Path(bit.__file__), Path(program.__file__)):
        watched[str(file.resolve())] = sha(file)
    for name, digest in read(program_receipt)['Logs'].items():
        watched[str((Path(program_receipt).parent/name).resolve())] = digest
    record = {'Schema': RECORD_SCHEMA, 'Target': TARGET, 'SHA256': verified['Bitstream']['SHA256'],
              'TimingSHA256': sha(timing), 'RawCaptureContract': copy.deepcopy(CONTRACT), 'SourceSHA256': sources,
              'SourceManifest': binding(manifest_path), 'Bitstream': verified['Bitstream'],
              'CandidateADFSHA256': verified['CandidateADFSHA256'], 'NativeTiming': verified['NativeTiming'],
              'ProgramReceipt': binding(program_receipt), 'BindingToolSHA256': sha(SELF),
              'HardwareAccessed': False, 'OpticalCorrectionAccepted': False}
    return record, pins, timing, watched


def recipe(bitwork, identity_path, review_path, program_receipt, output):
    identity_path, review_path, program_receipt = [Path(x).resolve() for x in (identity_path, review_path, program_receipt)]
    record, pins, timing, watched = release_context(bitwork, program_receipt)
    value = identity_from_template(read(identity_path))
    declarations = connection_declarations(review_path)
    value.update(connection_review={**declarations, 'programmed_bound_bitstream': True},
        build_binding={'validated_build': {'path': str(Path(output).resolve()/'validated-build.json'),
                       'sha256': ''}, 'bitstream': binding(record['Bitstream']['Path']),
                       'pinout': binding(pins), 'timing_report': binding(timing)},
        current720_provenance={'identity_template': binding(identity_path), 'connection_review': binding(review_path),
                              'program_receipt': binding(program_receipt), 'bit_work': str(Path(bitwork).resolve())},
        status='ACTUAL_CURRENT720_RAW_BIT_AND_PROGRAM_RECEIPT_BOUND')
    for file in (identity_path, review_path):
        watched[str(file)] = sha(file)
    return value, record, watched


def unchanged(watched):
    return all(Path(p).is_file() and sha(p) == h for p, h in watched.items())


def prepare_binding(bitwork, identity_path, review_path, program_receipt, output):
    output = Path(output).resolve()
    require(not output.exists() and output.parent.is_dir(), 'fresh binding directory under an existing parent required')
    value, record, watched = recipe(bitwork, identity_path, review_path, program_receipt, output)
    require(unchanged(watched), 'capture binding input drift')
    output.mkdir()
    write_new(output/'validated-build.json', record)
    value['build_binding']['validated_build'] = binding(output/'validated-build.json')
    capture.validate_live_binding(value, base_dir=output)
    write_new(output/'binding.json', value)
    return {'Binding': binding(output/'binding.json'), 'HardwareAccessed': False, 'LiveReady': True}


def validate_session_binding(path):
    path = Path(path).resolve()
    value = read(path)
    provenance = value.get('current720_provenance')
    require(isinstance(provenance, dict), 'current720 verified release provenance required; generic bindings are insufficient')
    for key in ('identity_template', 'connection_review', 'program_receipt'):
        capture._bound_file(provenance.get(key), key, path.parent)
    expected, record, watched = recipe(provenance['bit_work'], provenance['identity_template']['path'],
        provenance['connection_review']['path'], provenance['program_receipt']['path'], path.parent)
    record_path = path.parent/'validated-build.json'
    require(read(record_path) == record, 'validated raw build record differs from actual release verification')
    expected['build_binding']['validated_build'] = binding(record_path)
    require(value == expected, 'current720 binding/identity/mode or calibration metadata changed')
    live = capture.validate_live_binding(value, base_dir=path.parent)
    for file in (path, record_path):
        watched[str(file)] = sha(file)
    require(unchanged(watched), 'live capture evidence changed during validation')
    return value, live, watched


def first_frame(chunks):
    """Pure one-frame decode; complete bad packets prevent acceptance."""
    parser = FrameParser()
    for chunk in chunks:
        frames = parser.feed(chunk)
        require(parser.rejected == 0, 'malformed PGFRAME1 header/payload/trailer or checksum')
        if frames:
            frame = frames[0]
            require([frame.width, frame.height] == SIZE and len(frame.payload) == PAYLOAD_BYTES,
                    'PGFRAME1 dimensions must be exactly1280x720 and1843200 bytes')
            return frame, {'RejectedPackets': parser.rejected, 'InitialDiscardedBytes': parser.discarded,
                           'TrailingBufferedBytes': len(parser.buffer), 'AdditionalCompleteFramesIgnored': len(frames)-1}
    raise ValueError('incomplete or timed out before one complete current720 frame')


def receive(binding_path, output, session_id, *, port=None, replay=None, seconds=90.):
    require((port is None) != (replay is None), 'select exactly one passive COM receive or offline replay')
    require(type(seconds) in (int, float) and math.isfinite(seconds) and 0 < seconds <= 180,
            'bounded positive receive timeout up to180 seconds required')
    if port is not None:
        require(isinstance(port, str) and re.fullmatch(r'COM[1-9][0-9]*', port), 'explicit Windows COM port required')
    capture.safe_label(session_id, 'session_id')
    output = Path(output).resolve()
    require(output.parent.is_dir() and not output.exists(), 'fresh session output directory required')
    value, live, watched = validate_session_binding(binding_path)
    kind = 'physical_native_camera' if port else 'offline_uart_replay'
    replay_record = binding(replay) if replay else None
    if replay:
        watched[str(Path(replay).resolve())] = replay_record['sha256']
    output.mkdir()
    chunks = capture.serial_chunks(port, BAUD, seconds) if port else capture.file_chunks(replay)
    result = {'Schema': 'camera720-first-frame-session-v1', 'Target': TARGET,
              'StartedUTC': datetime.now(timezone.utc).isoformat(), 'Passed': False,
              'SourceKind': kind, 'HardwareAccessed': bool(port), 'UARTTransmitBytes': 0,
              'JTAGAccessed': False, 'HeartbeatProgrammed': False, 'SessionID': session_id,
              'Binding': binding(binding_path), 'Checkerboard': copy.deepcopy(BOARD),
              'FrameRateMeasured': False, 'OpticalCorrectionAccepted': False,
              'Limits': 'One native raw frame; board need not contain a chessboard. CRC does not identify the sensor or establish calibration.'}
    try:
        with (output/'received-wire.bin').open('xb') as wire:
            def recorded():
                for chunk in chunks:
                    wire.write(chunk)
                    yield chunk
            frame, stats = first_frame(recorded())
        require(unchanged(watched), 'capture inputs changed while receiving')
        saved = capture.save_frame(frame, value, output, session_id, source_kind=kind,
            build_record=live if port else None, replay_record=replay_record)
        result.update(Passed=True, Frame=saved, Protocol=stats)
    except Exception as error:
        result['Error'] = type(error).__name__+': '+str(error)
    finally:
        try:
            if hasattr(chunks, 'close'):
                chunks.close()
            result['ReceiverStreamClosed'] = True
        except Exception as error:
            result.update(Passed=False, ReceiverStreamClosed=False,
                          CloseError=type(error).__name__+': '+str(error))
        result['InputDrift'] = [p for p, h in watched.items() if not Path(p).is_file() or sha(p) != h]
        result['Passed'] &= not result['InputDrift']
        wire_path = output/'received-wire.bin'
        result.update(FinishedUTC=datetime.now(timezone.utc).isoformat(),
                      Wire=binding(wire_path) if wire_path.is_file() else None)
        write_new(output/'session-summary.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare-binding')
    for key in ('bit-work', 'identity-template', 'connection-review', 'program-receipt', 'output'):
        p.add_argument('--'+key, type=Path, required=True)
    p = sub.add_parser('receive')
    for key in ('binding', 'output'):
        p.add_argument('--'+key, type=Path, required=True)
    p.add_argument('--session-id', required=True)
    source = p.add_mutually_exclusive_group(required=True)
    source.add_argument('--port'); source.add_argument('--replay', type=Path)
    p.add_argument('--seconds', type=float, default=90.)
    args = parser.parse_args()
    if args.action == 'prepare-binding':
        result = prepare_binding(args.bit_work, args.identity_template, args.connection_review, args.program_receipt, args.output)
    else:
        result = receive(args.binding, args.output, args.session_id, port=args.port, replay=args.replay, seconds=args.seconds)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get('Passed', True) else 1


if __name__ == '__main__':
    raise SystemExit(main())
