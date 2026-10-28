"""Exact offline CAM1 clone factory; never touches CAM2 sources or hardware."""
from pathlib import Path
import argparse
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
APPROVED = ROOT / 'build/offline-20261024'
ORIGINAL = 'raw_camera_capture_cam2_guarded'
TARGET = 'raw_camera_capture_cam1_guarded'
BUILD_TAG = 0x52473101
CAMERA_ID = 0x43414D31
CAMERA_SLOT = 1
REFERENCE = 'board/camera_sync-pins.json'
REFERENCE_SHA256 = 'ed08e477a07a485f6def7dfde6ea6b7d8647eea67cf69856dea2a94039e97fb3'
ORIGINAL_MANIFEST_SHA256 = '538f357c33503eaf777d1780a11e04c8e455d1612ee172934ed134cd14afc823'
INHERITED_SIMULATION = 'build/offline-20261024/guarded-board-sim-20261025-182211-132/guarded-board-simulation.json'
INHERITED_SIMULATION_SHA256 = 'ebeca366e40713c5cc17bf03f62699ca12dcf7c79bc8e4ef8746a9b9004d23bf'
OWN = [f'board/{ORIGINAL}.v', f'board/{ORIGINAL}.fdc',
       f'board/{ORIGINAL}-pins.json', f'board/build-{ORIGINAL}.tcl']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=unique)


def _inside(path):
    candidate = (ROOT / path).resolve()
    if not candidate.is_relative_to(ROOT.resolve()) or not candidate.is_file():
        raise ValueError('source must be an existing project file: ' + path)
    return candidate


def clone_top(data):
    """Only the module name, three identity constants and descriptive comments."""
    replacements = [(b'module '+ORIGINAL.encode()+b'(', b'module '+TARGET.encode()+b'('),
                    (b"GUARDED_BUILD_TAG=32'h52473201,CAMERA_ID=32'h43414d32",
                     b"GUARDED_BUILD_TAG=32'h52473101,CAMERA_ID=32'h43414d31"),
                    (b"CAMERA_SLOT=2'b10", b"CAMERA_SLOT=2'b01")]
    for old, new in replacements:
        if data.count(old) != 1:
            raise ValueError('CAM2 top identity anchor differs')
        data = data.replace(old, new)
    for old, new in [(b'PGGUARD02 CAM2 candidate', b'PGGUARD02 CAM1 candidate'),
                     (b'Existing CAM2 reference pinmap', b'Existing CAM1 reference pinmap'),
                     (b'// CAM2 denotes connector slot', b'// CAM1 denotes connector slot')]:
        if data.count(old) != 1:
            raise ValueError('CAM2 comment identity anchor differs')
        data = data.replace(old, new)
    return data


def clone_fdc(data, old_pins, camera_pins):
    for port, pad in camera_pins.items():
        old = ('define_attribute {p:'+port+'} {PAP_IO_LOC} {'+old_pins[port]+'}').encode()
        new = ('define_attribute {p:'+port+'} {PAP_IO_LOC} {'+pad+'}').encode()
        if data.count(old) != 1:
            raise ValueError('camera FDC location anchor differs: '+port)
        data = data.replace(old, new)
    return data


def source_evidence():
    """All shared103 have either explicit simulation SHA or preserved raw97 SHA."""
    original_path = ROOT/f'board/{ORIGINAL}-sources.json'
    if sha(original_path) != ORIGINAL_MANIFEST_SHA256:
        raise ValueError('frozen CAM2 prepared manifest changed')
    if sha(ROOT/REFERENCE) != REFERENCE_SHA256:
        raise ValueError('reviewed CAM1 pin reference changed')
    original = load(original_path)
    baseline = load(ROOT/'board/raw_camera_capture_cam2_ref-sources.json')
    sim_path = ROOT/INHERITED_SIMULATION
    if sha(sim_path) != INHERITED_SIMULATION_SHA256:
        raise ValueError('frozen successful CAM2 simulation changed')
    sim = load(sim_path)
    required = {'tb_raw_capture_lease', 'tb_guarded_raw_camera_capture',
                'tb_guarded_temperature_cdc', 'tb_guarded_status_uart', 'tb_guarded_board_pipeline'}
    if (sim.get('Passed') is not True or sim.get('HardwareAccessed') is not False or
            sim.get('OriginalRaw97SourceBindingPreserved') is not True or
            len(sim.get('RegressionTops', [])) != 5 or set(sim['RegressionTops']) != required):
        raise ValueError('successful complete CAM2 digital regression required')
    for name, expected in baseline['SourceSHA256'].items():
        if sha(_inside(name)).upper() != expected.upper():
            raise ValueError('frozen original raw97 source changed: '+name)
    sources = original['source_files']
    if (len(sources) != 107 or len(set(sources)) != 107 or
            set(sources) != set(original['SourceSHA256'])):
        raise ValueError('CAM2 exact107 source closure differs')
    sim_hashes = {name.replace('\\', '/'): value.upper() for name, value in sim['SourceSHA256'].items()}
    for name, expected in sim_hashes.items():
        if sha(_inside(name)).upper() != expected:
            raise ValueError('CAM2 simulation source changed: '+name)
    if sha(Path(sim['MixedStream'])).upper() != sim['MixedStreamSHA256'].upper():
        raise ValueError('inherited CAM2 mixed wire changed')
    shared = {}
    for name in sources:
        current = sha(_inside(name)).upper()
        if current != original['SourceSHA256'][name].upper():
            raise ValueError('frozen CAM2 prepared source changed: '+name)
        if name not in OWN:
            evidence = sim_hashes.get(name) or baseline['SourceSHA256'].get(name, '').upper()
            if current != evidence:
                raise ValueError('shared source lacks inherited simulation/baseline evidence: '+name)
            shared[name] = current
    if len(shared) != 103:
        raise ValueError('CAM1 must inherit exactly103 shared sources')
    return original, shared


def expected_files():
    original, shared = source_evidence()
    old_pins = load(ROOT/f'board/{ORIGINAL}-pins.json')
    camera_pins = {name: pad for name, pad in load(ROOT/REFERENCE).items() if name.startswith('cam_')}
    if len(camera_pins) != 14 or camera_pins.get('cam_data[5]') != 'Y21':
        raise ValueError('CAM1 must have14 reviewed camera pads including D5Y21')
    pins = dict(old_pins)
    pins.update(camera_pins)
    if len(pins) != 129 or len(set(pins.values())) != 129 or pins.get('uart_rxd') != 'B24':
        raise ValueError('CAM1 shared129 pin map collides or RX differs')
    files = {}
    for old_name in OWN:
        data = (ROOT/old_name).read_bytes()
        if old_name.endswith('.v'):
            data = clone_top(data)
        elif old_name.endswith('.fdc'):
            data = clone_fdc(data, old_pins, camera_pins)
        elif old_name.endswith('-pins.json'):
            # Preserve formatting and every non-camera byte of the CAM2 JSON.
            for port, pad in camera_pins.items():
                old = json.dumps(port).encode()+b': '+json.dumps(old_pins[port]).encode()
                new = json.dumps(port).encode()+b': '+json.dumps(pad).encode()
                if data.count(old) != 1:
                    raise ValueError('pin JSON anchor differs: '+port)
                data = data.replace(old, new)
        else:
            data = data.replace(ORIGINAL.encode(), TARGET.encode())
        files[old_name.replace(ORIGINAL, TARGET)] = data
    sources = [name.replace(ORIGINAL, TARGET) if name in OWN else name for name in original['source_files']]
    hashes = {name: hashlib.sha256(files[name]).hexdigest().upper() if name in files else shared[name]
              for name in sources}
    contract = dict(original['GuardedControlContract'])
    if contract.get('build_tag') != 0x52473201:
        raise ValueError('CAM2 contract build tag differs')
    contract['build_tag'] = BUILD_TAG
    manifest = {'target': TARGET, 'hardware_accessed': False, 'physical_eye': None,
                'connector_slot_tag': CAMERA_SLOT, 'camera_id': CAMERA_ID,
                'reference_board_port': 'CAM1 D5 Y21, UART RX B24',
                'RawCaptureContract': original['RawCaptureContract'], 'GuardedControlContract': contract,
                'source_files': sources, 'SourceSHA256': hashes,
                'ReferenceSHA256': {REFERENCE: REFERENCE_SHA256.upper()},
                'CloneVerification': {'OriginalTarget': ORIGINAL,
                    'OriginalPreparedManifestSHA256': ORIGINAL_MANIFEST_SHA256.upper(),
                    'InheritedSimulationEvidence': str(ROOT/INHERITED_SIMULATION),
                    'InheritedSimulationEvidenceSHA256': INHERITED_SIMULATION_SHA256.upper(),
                    'UnchangedSharedDependencyCount': 103, 'SharedSourceSHA256': shared,
                    'CameraPortCount': 14, 'PhysicalEye': None, 'StereoSynchronizationVerified': False},
                'limits': 'Offline exact connector variant only. CAM1 is a board slot, not a physical eye. No simultaneous stereo, new electrical compatibility, optics, temperature safety or hardware acceptance.'}
    files[f'board/{TARGET}-sources.json'] = (json.dumps(manifest, indent=2)+'\n').encode()
    files['tests/tb_guarded_cam1_pipeline.sv'] = cam1_testbench()
    return files, manifest


def cam1_testbench():
    """Keep the successful mixed pipeline, explicitly vary all three identities."""
    data = (ROOT/'tests/tb_guarded_board_pipeline.sv').read_bytes()
    pairs = [(b'module tb_guarded_board_pipeline;', b'module tb_guarded_cam1_pipeline;'),
             (b'.WIDTH(WIDTH),.HEIGHT(HEIGHT),.TIMEOUT_BITS(17)',
              b".BUILD_TAG(32'h52473101),.CAMERA_ID(32'h43414d31),.CAMERA_SLOT(2'b01),\n        .WIDTH(WIDTH),.HEIGHT(HEIGHT),.TIMEOUT_BITS(17)"),
             (b"u32(12)!=32'h52473201", b"u32(12)!=32'h52473101"),
             (b'guarded-board-mixed-stream.bin', b'guarded-cam1-mixed-stream.bin'),
             (b'                raw_count=raw_count+1;',
              b"                if(dut.held_camera_id!==32'h43414d31 || dut.held_eye!==2'b01)$fatal(1,\"CAM1 held identity/slot\");\n                raw_count=raw_count+1;")]
    for old, new in pairs:
        if data.count(old) != 1:
            raise ValueError('inherited pipeline TB anchor differs')
        data = data.replace(old, new)
    return data


def prepare():
    files, manifest = expected_files()
    # Validate all existing destinations before any write; never refresh a differing candidate.
    for name, data in files.items():
        if (ROOT/name).exists() and (ROOT/name).read_bytes() != data:
            raise ValueError('refusing to overwrite differing CAM1 candidate: '+name)
    for name, data in files.items():
        if not (ROOT/name).exists():
            with (ROOT/name).open('xb') as stream:
                stream.write(data)
    return verify_clone()


def verify_clone():
    files, manifest = expected_files()
    for name, data in files.items():
        if (ROOT/name).read_bytes() != data:
            raise ValueError('CAM1 differs beyond exact module/identity14pads/own paths: '+name)
    return manifest


def validate_simulation(path):
    manifest = verify_clone()
    path = Path(path).resolve()
    if not path.is_relative_to(APPROVED.resolve()):
        raise ValueError('CAM1 simulation must be in approved scratch')
    sim = load(path)
    if (sim.get('Passed') is not True or sim.get('HardwareAccessed') is not False or
            sim.get('Target') != TARGET or sim.get('BuildTag') != BUILD_TAG or
            sim.get('CameraID') != CAMERA_ID or sim.get('CameraSlot') != CAMERA_SLOT or
            sim.get('RegressionTops') != ['tb_guarded_cam1_pipeline'] or
            sim.get('PreparedSourceManifestSHA256', '').upper() != sha(ROOT/f'board/{TARGET}-sources.json').upper()):
        raise ValueError('fresh source-bound CAM1 parameterized simulation required')
    for name, expected in sim['SourceSHA256'].items():
        if sha(_inside(name.replace('\\', '/'))).upper() != expected.upper():
            raise ValueError('CAM1 simulation source changed: '+name)
    required = {'tests/tb_guarded_cam1_pipeline.sv', f'board/{TARGET}.v',
                'tools/run-guarded-cam1-sim.ps1'}
    sim_names = {name.replace('\\', '/') for name in sim['SourceSHA256']}
    sim_names.update(name for name in manifest['source_files'] if name.endswith(('.vp', '.idf', '.fdc', '.json', '.tcl')))
    # All RTL exercised in the inherited pipeline must remain explicitly bound.
    old = load(ROOT/INHERITED_SIMULATION)
    required.update(name.replace('\\', '/') for name in old['SourceSHA256']
                    if name.startswith('rtl') and name.endswith(('.v', '.vh')))
    if not required.issubset(sim_names):
        raise ValueError('CAM1 simulation omitted a required RTL/test/source binding')
    wire = Path(sim['MixedStream']).resolve()
    if not wire.is_relative_to(path.parent) or sha(wire).upper() != sim['MixedStreamSHA256'].upper():
        raise ValueError('CAM1 simulated wire changed or escaped simulation directory')
    return sim


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    report = prepare() if args.prepare else verify_clone()
    print(json.dumps({'target': report['target'], 'source_files': len(report['source_files']),
                      'shared_sources': 103, 'active_pins': 129, 'hardware_accessed': False,
                      'build_tag': report['GuardedControlContract']['build_tag']}))


if __name__ == '__main__':
    main()
