"""Reparse packaged C/S3 UART evidence offline; never open a serial/JTAG device."""
from pathlib import Path
import hashlib
import json

import hdmi_camera_fisheye_fps as protocol
from measure_hdmi_fisheye_fps import arrival_summary

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'distortion/results/hdmi-camera-fisheye-fill8r3s3-20261103-a'


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check(receipt, wire, programmed, bit):
    value, program = read(receipt), read(programmed)
    require(all(program.get(k) is True for k in
                ('Passed', 'DoneConfirmed', 'ExpectedDeviceAndIDConfirmed')) and
            program.get('FlashWritten') is False and program.get('CleanupErrors') == [],
            'successful SRAM receipt required')
    require(value.get('passed') is True and value.get('uart_transmit_bytes') == 0,
            'successful receive-only measurement required')
    require(value['program_receipt']['sha256'] == sha(programmed) and
            value['bitstream'] == program['Bitstream'] and
            value['final_adf_sha256'] == program['FinalADFSHA256'] and
            sha(bit) == program['Bitstream']['SHA256'] and
            bit.stat().st_size == program['Bitstream']['Bytes'] and
            sha(wire) == value['wire']['sha256'], 'firmware/receipt/wire identity differs')
    parser = protocol.Parser()
    frames = parser.feed(wire.read_bytes())
    require(frames == [{k: v for k, v in row.items() if k != 'host_elapsed_seconds'}
                       for row in value['frames']] and len(frames) >= 30 and
            parser.rejected == value['crc_rejected_packets'] == 0 and
            parser.discarded == value['discarded_bytes'] == 0,
            'saved UART decode differs')
    require(all(row['corrected_requested'] and row['status_valid'] and
                not row['failed'] and not row['fault'] for row in frames) and
            all(((b['sequence'] - a['sequence']) & 0xffffffff) == 1
                for a, b in zip(frames, frames[1:])), 'mode/status/sequence differs')
    summary, host = protocol.summarize(frames), arrival_summary(value['frames'])
    require(summary == value['nominal_clock_summary'] and host == value['independent_host_summary']
            and host['clock_cross_check_within_3percent'] and
            summary['counter_delta']['scan_blank_frames'] == 0,
            'independent rate/blank/clock recomputation differs')
    return summary, host


def main():
    c = PACKAGE / 'evidence/baseline-C'
    s = PACKAGE / 'evidence/fps-S3'
    baseline, baseline_host = check(c / 'corrected-fps-receipt.json', c / 'corrected-wire.bin',
        c / 'program-receipt.json', ROOT /
        'delivery/20261103-hdmi-camera-fisheye-c/bitstreams/hdmi_camera_fisheye_top_C.sbit')
    candidate, candidate_host = check(s / 'corrected-receipt.json', s / 'corrected-wire.bin',
        PACKAGE / 'evidence/program/receipt.json', PACKAGE / 'artifacts/hdmi_camera_fisheye_top.sbit')
    metric = 'unique_presented_frames_per_second'
    ratio = candidate_host['host_timed_rates'][metric] / baseline_host['host_timed_rates'][metric]
    comparison = read(s / 'independent-C-vs-S3-comparison.json')
    require(comparison['Passed'] is True and comparison['UniqueFrameRateRatio'] == ratio,
            'saved independent comparison differs')
    print(json.dumps({'Passed': True, 'BaselineUniqueFPS': baseline[metric],
        'CandidateUniqueFPS': candidate[metric], 'HostRateRatio': ratio,
        'ScanRefreshHz': candidate['scan_refreshes_per_second'],
        'HardwareAccessed': False, 'OpticalLatencyMeasured': False}))


if __name__ == '__main__':
    main()
