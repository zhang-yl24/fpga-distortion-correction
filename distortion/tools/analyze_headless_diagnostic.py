"""Independently analyze sealed thermal/ISP diagnostic UART bytes, offline only."""
from pathlib import Path
import argparse
import binascii
import hashlib
import json
import re

THERMAL_KEYS = ('V', 'B', 'Q', 'TV', 'TF', 'E', 'TR', 'TC', 'TA', 'TS', 'CV', 'OT', 'AL')
THERMAL_WIDTHS = (2, 8, 8, 1, 1, 2, 4, 3, 8, 8, 8, 1, 2)
ISP_ADDRESSES = [0x5001, 0x3406, 0x3503, 0x4300, 0x501f, 0x503d, *range(0x3400, 0x3406),
                 0x3500, 0x3501, 0x3502, 0x350a, 0x350b, 0x3a00, 0x3a19, 0x5000,
                 0x3017, 0x3018, 0x3035, 0x3036]
ISP_PATTERN = re.compile(rb'ISP T=([0-9A-F]{8}) A=([0-9A-F]{4}) V=([0-9A-F]{2}) E=([0-9A-F])\r\n')


def complete_lines(data, prefix):
    """Opening COM mid-record may truncate only the first and last record."""
    lines = data.splitlines(keepends=True)
    discarded_first = discarded_last = 0
    if lines and not lines[0].startswith(prefix):
        discarded_first = len(lines.pop(0))
    if lines and not lines[-1].endswith(b'\r\n'):
        discarded_last = len(lines.pop())
    if not lines:
        raise ValueError('no complete diagnostic records')
    if any(not line.startswith(prefix) or not line.endswith(b'\r\n') for line in lines):
        raise ValueError('corrupt or unrelated record within the stream')
    return lines, {'leading_partial_bytes': discarded_first, 'trailing_partial_bytes': discarded_last}


def analyze_thermal(data):
    lines, boundary = complete_lines(data, b'THERMAL_IDLE ')
    rows = []
    for line in lines:
        if len(line) != 125:
            raise ValueError('thermal snapshot length differs')
        body, crc = line[:-2].rsplit(b' Z=', 1)
        if not re.fullmatch(rb'[0-9A-F]{4}', crc) or int(crc, 16) != binascii.crc_hqx(body, 0xffff):
            raise ValueError('thermal snapshot CRC differs')
        fields = [field.split('=') for field in body.decode('ascii').split(' ')[1:]]
        if tuple(key for key, value in fields) != THERMAL_KEYS or any(not re.fullmatch('[0-9A-F]+', value) for key, value in fields):
            raise ValueError('thermal fields differ, duplicate or reordered')
        if any(len(value) != width for (key, value), width in zip(fields, THERMAL_WIDTHS)):
            raise ValueError('thermal field widths differ')
        row = {key: int(value, 16) for key, value in fields}
        if row['V'] != 1 or row['B'] != 921600 or row['TR'] > 0xffff or row['TC'] != row['TR'] >> 4:
            raise ValueError('thermal protocol/baud/raw code differs')
        if any(row[key] not in (0, 1) for key in ('TV', 'TF', 'OT')) or row['AL'] > 31 or row['E'] > 255:
            raise ValueError('thermal flags out of range')
        if rows and row['Q'] != ((rows[-1]['Q']+1) & 0xffffffff):
            raise ValueError('duplicate or skipped thermal record sequence')
        if rows and (row['TS'] < rows[-1]['TS'] or row['CV'] < rows[-1]['CV']):
            raise ValueError('thermal sample/conversion counter regressed')
        if row['TS'] > max(0, row['CV']-2):
            raise ValueError('thermal sample count exceeds possible fresh conversion epochs')
        if rows and row['TS']-rows[-1]['TS'] > row['CV']-rows[-1]['CV']:
            raise ValueError('new thermal samples lack new ADC conversion epochs')
        row['sample_age_seconds'] = row['TA']/27000000
        row['approximate_celsius'] = round(row['TC']*0.1219-273.15, 3) if row['TV'] and row['TC'] else None
        rows.append(row)
    valid_rows = [row for row in rows if row['TV'] and not row['TF'] and row['E'] == 0 and
                  row['TC'] > 0 and row['TA'] < 54000000 and row['TS'] > 0 and row['CV'] > 2]
    fresh = len(valid_rows) >= 2 and len({row['TS'] for row in valid_rows}) >= 2
    temperatures = [row['approximate_celsius'] for row in valid_rows]
    plausible = bool(temperatures) and all(-40 <= value <= 125 for value in temperatures)
    fault_free = len(valid_rows) == len(rows)
    alarm_seen = any(row['OT'] or row['AL'] for row in rows)
    below_ceiling = fresh and plausible and all(value < 60 for value in temperatures)
    return {'schema': 1, 'target': 'thermal_idle', 'transport_integrity_passed': True,
        'records': len(rows), 'boundary': boundary, 'snapshots': rows,
        'fresh_adc_samples_observed': fresh,
        'all_records_valid_and_fault_free': fault_free,
        'over_temp_or_alarm_observed': alarm_seen,
        'approximate_celsius_range': [min(temperatures), max(temperatures)] if temperatures else None,
        'project_conservative_ceiling_celsius': 60,
        'diagnostic_temperature_sanity_range_celsius': [-40, 125],
        'temperature_values_pass_sanity_check': plausible,
        'fresh_snapshots_below_project_ceiling': below_ceiling,
        'observed_low_load_status_meets_project_snapshot_policy': below_ceiling and fault_free and not alarm_seen,
        'hardware_accessed_by_analyzer': False, 'external_temperature_calibration_verified': False,
        'physical_input_provenance_verified_by_analyzer': False,
        'future_active_load_temperature_verified': False, 'continuous_thermal_interlock_installed': False,
        'limits': 'This offline analyzer alone cannot distinguish real hardware from replay; bind a separate programming/receive receipt. CRC authenticates the recorded byte values only. Celsius uses the existing approximate internal-ADC conversion, without external calibration. The 60C ceiling and sanity interval are diagnostic policies, not device ratings. These low-load snapshots do not establish temperature after a later SRAM configuration or thermal safety under raw/DDR load.'}


def analyze_isp(data):
    lines, boundary = complete_lines(data, b'ISP ')
    rows, scans, pending = [], [], []
    leading_rows = 0
    previous_time = None
    leading_next = None
    for line in lines:
        match = ISP_PATTERN.fullmatch(line)
        if not match:
            raise ValueError('malformed ISP register row')
        elapsed, address, value, error = [int(group, 16) for group in match.groups()]
        if error:
            raise ValueError('SCCB read error at '+f'{address:04X}')
        if previous_time is not None and elapsed < previous_time:
            raise ValueError('ISP elapsed counter regressed')
        previous_time = elapsed
        row = {'elapsed_ms': elapsed, 'address': f'{address:04X}', 'value': f'{value:02X}', 'error': error}
        rows.append(row)
        if leading_next is not None and address != ISP_ADDRESSES[leading_next]:
            raise ValueError('initial partial ISP scan order differs')
        if not pending and address != ISP_ADDRESSES[0]:
            if scans:
                raise ValueError('unexpected register after complete ISP scan')
            if address not in ISP_ADDRESSES:
                raise ValueError('unknown register in initial partial ISP scan')
            leading_next = (ISP_ADDRESSES.index(address)+1) % len(ISP_ADDRESSES)
            leading_rows += 1
            continue
        leading_next = None
        if address != ISP_ADDRESSES[len(pending)]:
            raise ValueError('ISP register order differs')
        pending.append(row)
        if len(pending) == len(ISP_ADDRESSES):
            regs = {int(item['address'], 16): int(item['value'], 16) for item in pending}
            wanted = {0x4300: 0x6f, 0x501f: 1, 0x3017: 0x7f, 0x3018: 0xf0, 0x3035: 0x21, 0x3036: 0x60}
            scans.append({'first_ms': pending[0]['elapsed_ms'], 'last_ms': pending[-1]['elapsed_ms'],
                'configuration_readback': {f'{key:04X}': f'{regs[key]:02X}' for key in wanted},
                'reference_configuration_matched': all(regs[key] == value for key, value in wanted.items()),
                'controls': {'awb_isp_enabled': bool(regs[0x5001] & 1), 'awb_automatic': not bool(regs[0x3406] & 1),
                    'aec_automatic': not bool(regs[0x3503] & 1), 'agc_automatic': not bool(regs[0x3503] & 2),
                    'test_pattern_enabled': bool(regs[0x503d] & 128)},
                'non_atomic_rgb_gain_codes': [regs[key] << 8 | regs[key+1] for key in (0x3400, 0x3402, 0x3404)],
                'non_atomic_exposure_code': regs[0x3500] << 16 | regs[0x3501] << 8 | regs[0x3502],
                'non_atomic_agc_code': regs[0x350a] << 8 | regs[0x350b]})
            pending = []
    return {'schema': 1, 'target': 'camera_isp_probe_d5', 'transport_format_passed': True,
        'uart_records_have_crc': False, 'records': len(rows), 'complete_scans': len(scans),
        'at_least_two_complete_scans': len(scans) >= 2, 'scans': scans, 'rows': rows,
        'boundary': boundary, 'leading_partial_scan_rows': leading_rows, 'trailing_partial_scan_rows': len(pending),
        'all_complete_scans_match_reference': bool(scans) and all(scan['reference_configuration_matched'] for scan in scans),
        'hardware_accessed_by_analyzer': False, 'optical_color_or_exposure_quality_verified': False,
        'physical_input_provenance_verified_by_analyzer': False,
        'limits': 'The probe writes reference initialization first, then reads individual SCCB registers. Multi-byte gains/exposure are non-atomic observations; configuration is not optical quality. This separate SRAM configuration does not observe the previous raw transaction, its exact exposure, its DDR state or later thermal state.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=('thermal_idle', 'camera_isp_probe_d5'), required=True)
    parser.add_argument('--wire', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.output.parent.is_dir() or args.output.exists():
        parser.error('output must be a new file in an existing directory')
    data = args.wire.read_bytes()
    result = analyze_thermal(data) if args.target == 'thermal_idle' else analyze_isp(data)
    result['wire'] = {'path': str(args.wire.resolve()), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
    result['analyzer_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    with args.output.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    print(json.dumps({key: result[key] for key in ('target', 'records')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
