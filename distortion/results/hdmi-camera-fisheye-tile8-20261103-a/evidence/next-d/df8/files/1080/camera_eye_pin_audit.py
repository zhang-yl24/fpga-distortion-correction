"""Compare a candidate with the legacy board's explicit CAM1/CAM2 pin maps.

This file never infers the eye from a photograph, opens hardware or authorizes
programming. Matching an old FPGA pin reference cannot establish the new camera
module's connector, power rails, IO levels, sensor ID or exposure synchronization.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re


ROOT = Path(__file__).resolve().parents[1]
CAMERA_PORTS = (
    'cam_rst_n', 'cam_scl', 'cam_sda', 'cam_pclk', 'cam_vsync', 'cam_href',
    *('cam_data['+str(bit)+']' for bit in range(8)),
)
REFERENCE_FILES = {
    'CAM1': 'board/camera_sync-pins.json',
    'CAM2': 'board/corrected_gamma_d5-pins.json',
}
EXPECTED_D5 = {'CAM1': 'Y21', 'CAM2': 'AA23'}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: '+str(key))
        result[key] = value
    return result


def read_pin_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),
                      object_pairs_hook=_unique_object)


def _validate_map(pins):
    if not isinstance(pins, dict):
        raise ValueError('pin map must be a JSON object mapping ports to package pins')
    for port, pin in pins.items():
        if not isinstance(port, str) or not port or not isinstance(pin, str) or not re.fullmatch(r'[A-Z]{1,2}[1-9][0-9]*', pin):
            raise ValueError('each port must name a nonempty string and an uppercase package pin')
    missing = sorted(set(CAMERA_PORTS)-set(pins))
    if missing:
        raise ValueError('missing camera ports: '+', '.join(missing))
    unexpected = sorted(port for port in pins if port.startswith('cam_') and port not in CAMERA_PORTS)
    if unexpected:
        raise ValueError('camera ports outside the legacy 14-route interface: '+', '.join(unexpected))


def _conflicts(pins):
    owners = {}
    for port, pin in pins.items():
        owners.setdefault(pin, []).append(port)
    return [{'pin': pin, 'ports': sorted(ports)} for pin, ports in sorted(owners.items()) if len(ports) > 1]


def load_reference_maps():
    """Read existing board references and verify their camera-route invariants."""
    maps, sources = {}, {}
    for eye, relative in REFERENCE_FILES.items():
        path = ROOT/relative
        pins = read_pin_json(path)
        _validate_map(pins)
        conflicts = _conflicts(pins)
        if conflicts:
            raise ValueError(eye+' legacy reference has conflicting package pins: '+str(conflicts))
        camera = {port: pins[port] for port in CAMERA_PORTS}
        if camera['cam_data[5]'] != EXPECTED_D5[eye]:
            raise ValueError(eye+' legacy D5 reference must be '+EXPECTED_D5[eye]+'; AA22 is historical and defective')
        maps[eye] = camera
        sources[eye] = {'path': str(path.resolve()), 'sha256': _sha(path),
                        'scope': 'legacy FPGA/adapter reference; not a verified new-module pinout'}
    overlap = sorted(set(maps['CAM1'].values()) & set(maps['CAM2'].values()))
    if overlap:
        raise ValueError('legacy CAM1/CAM2 camera routes overlap: '+', '.join(overlap))
    return maps, sources


def audit_pin_map(pins, eye):
    """Return a legacy-reference comparison; physical new-module facts stay false.

    ``eye`` is the electrical CAM1/CAM2 interface chosen by the operator, never
    the visual left/right lens. Missing/invalid input raises ValueError; a valid
    but mismatched/conflicting candidate returns passed=False with diagnostics.
    Full target maps and maps containing exactly the 14 camera ports are accepted.
    """
    if not isinstance(eye, str) or eye not in REFERENCE_FILES:
        raise ValueError('eye must be explicitly CAM1 or CAM2; left/right appearance cannot choose it')
    _validate_map(pins)
    references, sources = load_reference_maps()
    expected = references[eye]
    camera = {port: pins[port] for port in CAMERA_PORTS}
    mismatches = [{'port': port, 'expected': expected[port], 'actual': camera[port]}
                  for port in CAMERA_PORTS if camera[port] != expected[port]]
    conflicts = _conflicts(pins)
    d5_defect = camera['cam_data[5]'] == 'AA22'
    matches = not mismatches and not conflicts and not d5_defect
    return {
        'schema': 1, 'kind': 'legacy_camera_eye_pin_reference_audit',
        'eye': eye, 'passed': matches, 'old_reference_match': matches,
        'camera_route_count': len(CAMERA_PORTS), 'candidate_port_count': len(pins),
        'camera_pins': camera, 'mismatches': mismatches, 'pin_conflicts': conflicts,
        'historical_AA22_D5_rejected': d5_defect,
        'legacy_reference_pair_non_overlapping': True, 'reference_sources': sources,
        'new_module_verified': False, 'hardware_ready': False,
        'download_authorized_by_tool': False, 'hardware_accessed': False,
        'eye_chosen_from_photograph': False,
        'sensor_DOVDD_or_supply_voltage_verified': False,
        'limits': ('Only the selected legacy FPGA package-pin mapping is compared. '
                   'A matching JSON does not establish the new module connector orientation, '
                   'pinout, supply/IO voltage, sensor identity, programmed bitstream, source '
                   'provenance or synchronization. Review those independently before live use. '
                   'FPGA LVCMOS33 constraints are not a measurement of sensor DOVDD; '
                   'the local historical module schematic labels DOVDD as 2.8 V.'),
        'source_sha256': {'tools/camera_eye_pin_audit.py': _sha(Path(__file__))},
    }


def write_new_report(path, report):
    path = Path(path).resolve()
    if path.parent != (ROOT/'output/project').resolve() or not path.parent.is_dir():
        raise ValueError('output must be a new file directly in existing distortion/output/project')
    with path.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', type=Path, required=True, help='candidate -pins.json; no hardware access')
    parser.add_argument('--eye', choices=tuple(REFERENCE_FILES), required=True,
                        help='electrical CAM1/CAM2 identity, not visual left/right')
    parser.add_argument('--output', type=Path, help='new report in existing distortion/output/project')
    args = parser.parse_args(argv)
    try:
        pins = read_pin_json(args.candidate)
        report = audit_pin_map(pins, args.eye)
        report['candidate_file'] = {'path': str(args.candidate.resolve()), 'sha256': _sha(args.candidate)}
        if args.output:
            write_new_report(args.output, report)
        print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
        return 0 if report['passed'] else 1
    except (ValueError, OSError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    raise SystemExit(main())
