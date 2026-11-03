"""Independently reparse saved UART bytes and compare the corrected board rate."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import sys

WORK = Path(__file__).resolve().parent
REPO = WORK.parents[2]
sys.path[:0] = [str(REPO / 'distortion/tools'), str(REPO / '.venv/Lib/site-packages')]
import hdmi_camera_fisheye_fps as protocol
import measure_hdmi_fisheye_fps as measurement


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    return {'Path': str(path), 'SHA256': sha(path)}


def reparse(work, program_name, measurement_name):
    program_path = work / program_name / 'receipt.json'
    program = json.loads(program_path.read_text(encoding='utf-8-sig'))
    assert all(program.get(k) is True for k in ('Passed', 'DoneConfirmed', 'ExpectedDeviceAndIDConfirmed'))
    assert program['FlashWritten'] is False and program['CleanupErrors'] == []
    assert sha(program['Bitstream']['Path']) == program['Bitstream']['SHA256']
    path = work / measurement_name / 'receipt.json'
    value = json.loads(path.read_text(encoding='utf-8-sig'))
    assert value['passed'] is True and value['uart_transmit_bytes'] == 0
    assert value['program_receipt'] == {'path': str(program_path), 'sha256': sha(program_path)}
    assert value['bitstream'] == program['Bitstream']
    assert value['final_adf_sha256'] == program['FinalADFSHA256']
    wire = Path(value['wire']['path'])
    assert sha(wire) == value['wire']['sha256']
    parser = protocol.Parser()
    frames = parser.feed(wire.read_bytes())
    assert frames == [{k: v for k, v in frame.items() if k != 'host_elapsed_seconds'}
                      for frame in value['frames']]
    assert len(frames) >= 10 and parser.rejected == value['crc_rejected_packets'] == 0
    assert parser.discarded == value['discarded_bytes'] == 0
    assert all(frame['corrected_requested'] and frame['status_valid']
               and not frame['failed'] and not frame['fault'] for frame in frames)
    assert all(((b['sequence'] - a['sequence']) & 0xffffffff) == 1
               for a, b in zip(frames, frames[1:]))
    summary = protocol.summarize(frames)
    host = measurement.arrival_summary(value['frames'])
    assert summary == value['nominal_clock_summary']
    assert host == value['independent_host_summary'] and host['clock_cross_check_within_3percent']
    assert summary['counter_delta']['scan_blank_frames'] == 0
    totals = {key: sum((b[key] - a[key]) & 0xffffffff
                      for a, b in zip(frames, frames[1:]))
              for key in ('cache_hits', 'cache_misses', 'queries')}
    return {'Receipt': ref(path), 'ProgramReceipt': ref(program_path),
            'WireReparsed': True, 'Samples': len(frames), 'Summary': summary, 'Host': host,
            'PerSampleCacheTotals': totals,
            'MissFraction': totals['cache_misses'] / (totals['cache_hits'] + totals['cache_misses'])}


def main():
    old = reparse(WORK.parent / 'hdmi-camera-fisheye-20261103-a', 'program-c', 'fps-corrected-c')
    new = reparse(WORK, 'program-a', 'fps-corrected-a')
    rate = lambda value: value['Host']['host_timed_rates']['unique_presented_frames_per_second']
    output = {'Schema': 'hdmi-camera-fisheye-fill8r3s3-live-comparison-v1', 'Passed': True,
              'CheckedUTC': datetime.now(timezone.utc).isoformat(), 'Baseline': old, 'Candidate': new,
              'UniqueFrameRateRatio': rate(new) / rate(old),
              'HardwareAccessedByVerifier': False,
              'Limits': 'Saved digital UART telemetry and independent host arrival timing; no optical latency claim.'}
    path = WORK / 'live-fps-comparison-a.json'
    with path.open('x', encoding='utf-8') as stream:
        json.dump(output, stream, indent=2, allow_nan=False)
    print(json.dumps({'Passed': True, 'BaselineUniqueFPS': rate(old), 'CandidateUniqueFPS': rate(new),
                      'Ratio': output['UniqueFrameRateRatio'], 'Output': str(path)}), flush=True)


if __name__ == '__main__':
    main()
