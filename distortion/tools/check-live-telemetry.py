"""Validate a finite, timestamped hardware run; frame counts are hexadecimal."""
from pathlib import Path
from datetime import datetime
import json
import re
import shutil

root = Path(__file__).resolve().parents[1]
work = root / 'build/live_video'
capture = json.loads((work / 'telemetry-timed.json').read_text(encoding='utf-8-sig'))
records = []
for sample in capture['Samples']:
    fields = {k: int(v, 16) for k, v in re.findall(r'(\w+)=([0-9A-F]+)', sample['Line'])}
    required = {'CAM', 'E', 'I', 'H', 'D', 'V', 'F', 'P', 'L', 'WF', 'RF', 'PF', 'UF', 'MF', 'OW', 'X', 'CS', 'RS', 'PS'}
    assert required <= fields.keys(), sample
    assert all(fields[k] == v for k, v in {'CAM': 0x5640, 'E': 0, 'I': 1, 'H': 1, 'D': 1, 'V': 1, 'P': 307200, 'L': 480, 'UF': 0, 'MF': 0, 'OW': 0, 'X': 0}.items()), sample
    records.append((datetime.fromisoformat(sample['ReceivedUtc']), fields))
assert len(records) >= 6, 'Need at least six complete healthy telemetry samples.'
for (_, before), (_, after) in zip(records, records[1:]):
    for k in ('F', 'WF', 'RF', 'PF'):
        assert after[k] >= before[k], f'{k} regressed; reset or counter wrap during this run.'
span = (records[-1][0] - records[0][0]).total_seconds()
assert span > 4
delta = {k: records[-1][1][k] - records[0][1][k] for k in ('F', 'WF', 'RF', 'PF')}
assert all(v > 0 for v in delta.values()), delta
assert abs(delta['RF'] - delta['PF']) <= 2, 'DDR read and pixel completion counts diverged.'
source_crcs = {fields['CS'] for _, fields in records}
assert len(source_crcs) > 1, 'No changing source frame CRC observed.'
# CS describes the newest capture; RS/PS describe their last completed frame.
# These fields can legitimately differ in a coherent snapshot. Each hardware
# stage compares against its own locked frame CRC; X/MF report mismatches.
result = {
    'samples': len(records), 'observed_span_seconds': span, 'counter_delta': delta,
    'approx_rates_per_second': {k: round(v / span, 3) for k, v in delta.items()},
    'distinct_source_crc32': len(source_crcs), 'underflows': 0, 'pixel_crc_errors': 0,
    'ownership_errors': 0, 'fault': 0, 'frame_pixels': 307200, 'frame_lines': 480,
    'resolution': [640, 480], 'crc': 'IEEE CRC32, RGB565 little-endian byte order',
    'limits': 'Finite hardware run. Rates use host serial receive timestamps, with about 100 ms polling uncertainty. PF/RF count display refreshes and may repeat a captured image; WF counts new committed camera frames.'
}
out = root / 'results'
shutil.copyfile(work / 'telemetry.txt', out / 'live-video-20261006.txt')
shutil.copyfile(work / 'telemetry-timed.json', out / 'live-video-timed-20261006.json')
(out / 'live-video-check-20261006.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
