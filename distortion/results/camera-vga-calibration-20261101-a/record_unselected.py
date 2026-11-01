"""Retain a reviewed unsuccessful attempt without adding it to selected views."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json

HERE = Path(__file__).resolve().parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--view', required=True)
p.add_argument('--attempt', type=int, required=True)
p.add_argument('--review', required=True)
p.add_argument('--next', required=True)
a = p.parse_args()
plan = json.loads((HERE / 'session-plan.json').read_text(encoding='utf-8'))
if a.view not in {v['view_id'] for v in plan['planned_views']} or not 1 <= a.attempt <= 99:
    p.error('planned view and explicit attempt required')
quality = HERE / 'captures' / f'{a.view}-a{a.attempt:02d}' / 'quality.json'
q = json.loads(quality.read_text(encoding='utf-8'))
received = json.loads((quality.parent / 'receive-summary.json').read_text(encoding='utf-8'))
state = json.loads((HERE / 'capture-progress.json').read_text(encoding='utf-8'))
if any(v['QualityPath'] == str(quality) for v in state['SelectedViews']):
    raise ValueError('cannot reject an already selected attempt')
frame = received['frames'][0]
event = {'RecordedUTC': datetime.now(timezone.utc).isoformat(), 'ViewID': a.view,
    'Attempt': a.attempt, 'QualityPath': str(quality),
    'QualitySHA256': hashlib.sha256(quality.read_bytes()).hexdigest(),
    'RawFrameAndCRCPassed': received['passed'], 'CompleteInnerCorners': len(q['corners']),
    'FrameID': frame['frame_id'], 'CRC32': frame['source_crc32'],
    'SelectedForDataset': False, 'Review': a.review}
with (HERE / 'capture-records' / f'{a.view}-a{a.attempt:02d}-not-selected.json').open('x', encoding='utf-8') as out:
    json.dump(event, out, indent=2); out.write('\n')
state.setdefault('UnselectedAttempts', []).append(event)
state.update(UpdatedUTC=event['RecordedUTC'], Next=a.next)
(HERE / 'capture-progress.json').write_text(json.dumps(state, indent=2)+'\n', encoding='utf-8')
print(json.dumps({'retained_attempt':quality.parent.name, 'selected':False,
    'TrainViews':state['TrainViews'], 'HeldViews':state['HeldViews']}))
