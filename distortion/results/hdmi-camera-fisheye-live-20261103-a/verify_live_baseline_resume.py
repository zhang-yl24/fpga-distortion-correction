"""Reparse the two saved UART captures without opening hardware."""
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


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


program_path = WORK / 'program-c/receipt.json'
program = json.loads(program_path.read_text(encoding='utf-8'))
assert all(program[k] is True for k in ('Passed', 'DoneConfirmed', 'ExpectedDeviceAndIDConfirmed'))
assert program['CleanupErrors'] == [] and program['FlashWritten'] is False
assert digest(program['Bitstream']['Path']) == program['Bitstream']['SHA256']
summaries = {}
for name, corrected in [('fps-corrected-c', True), ('fps-raw-c', False), ('fps-corrected-return-c', True)]:
    receipt_path = WORK / name / 'receipt.json'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    assert receipt['passed'] is True and receipt['uart_transmit_bytes'] == 0
    assert receipt['program_receipt'] == {'path': str(program_path), 'sha256': digest(program_path)}
    assert receipt['bitstream'] == program['Bitstream']
    assert receipt['final_adf_sha256'] == program['FinalADFSHA256']
    wire = Path(receipt['wire']['path'])
    assert digest(wire) == receipt['wire']['sha256']
    parser = protocol.Parser()
    decoded = parser.feed(wire.read_bytes())
    saved = receipt['frames']
    assert decoded == [{k: v for k, v in f.items() if k != 'host_elapsed_seconds'} for f in saved]
    assert parser.rejected == receipt['crc_rejected_packets'] == 0
    assert parser.discarded == receipt['discarded_bytes'] == 0
    assert protocol.summarize(decoded) == receipt['nominal_clock_summary']
    assert measurement.arrival_summary(saved) == receipt['independent_host_summary']
    assert all(f['corrected_requested'] is corrected for f in decoded)
    assert all(f['status_valid'] and not f['failed'] and not f['fault'] for f in decoded)
    assert len(decoded) >= 10
    summary = receipt['nominal_clock_summary']
    assert summary['counter_delta']['scan_blank_frames'] == 0
    if not corrected:
        assert summary['counter_delta']['scan_repeat_frames'] == 0
    assert all(((b['sequence'] - a['sequence']) & 0xffffffff) == 1 for a, b in zip(decoded, decoded[1:]))
    # The raw mode can increment hits more than 2^32 over a 29-second window.
    # Sum each one-second increment so multiple wraps are retained. Saved
    # provider receipts stay untouched, including their endpoint-only ratio.
    totals = {k: sum((b[k] - a[k]) & 0xffffffff for a, b in zip(decoded, decoded[1:]))
              for k in ('cache_hits', 'cache_misses', 'queries')}
    summaries[name] = {
        'Receipt': {'Path': str(receipt_path), 'SHA256': digest(receipt_path)},
        'WireReparsed': True,
        'Samples': len(decoded),
        'RequestedCorrected': corrected,
        'NominalClockSummary': summary,
        'IndependentHostSummary': receipt['independent_host_summary'],
        'PerSampleCacheCounterTotals': totals,
        'CacheMissFractionUsingPerSampleTotals': totals['cache_misses'] / (totals['cache_hits'] + totals['cache_misses']),
    }

output = WORK / 'live-baseline-reparsed-with-return-and-wraps-resume.json'
result = {
    'Schema': 'hdmi-camera-fisheye-live-baseline-reparse-v1',
    'Passed': True,
    'CheckedUTC': datetime.now(timezone.utc).isoformat(),
    'ProgramReceipt': {'Path': str(program_path), 'SHA256': digest(program_path)},
    'Modes': summaries,
    'HardwareAccessedByThisVerification': False,
    'Limits': 'Saved digital telemetry only; no end-to-end optical latency or image re-evaluation.',
}
with output.open('x', encoding='utf-8') as stream:
    json.dump(result, stream, indent=2, allow_nan=False)
print(json.dumps({'Passed': True, 'Output': str(output), 'Modes': list(summaries)}, indent=2))
