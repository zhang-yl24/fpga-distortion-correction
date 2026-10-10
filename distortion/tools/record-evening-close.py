"""Bind final actual heartbeat transfer and midnight cutoff to a saved close."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json
root=Path(__file__).resolve().parents[1];lab=root/'results/lab-20261007'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
status=read(root/'status.json');assert status['current_sram_target']=='heartbeat'
paths=list((root/'build/heartbeat').glob('program-evidence-*/transfer.json'))
path=max(paths,key=lambda p:read(p)['CheckedOn']);transfer=read(path);manifest=read(path.parent/'validated-build.json')
assert transfer['Done'] and transfer['Target']=='heartbeat'
assert transfer['CheckedOn']==status['current_connection']['checked_on']
assert transfer['SHA256']==manifest['SHA256']==hashlib.sha256(Path(manifest['Bitstream']).read_bytes()).hexdigest().upper()
policy=read(lab/'evening-cutoff-policy.json')
now=datetime.now(ZoneInfo('Asia/Shanghai'));assert now<datetime.fromisoformat(policy['agent_wrapup_by'])
result={'passed':True,'recorded_at':now.isoformat(),'hardware_accessed_by_recorder':False,
    'idle_transfer':transfer,'policy':policy,'new_heavy_tests_disabled_for_this_session':True,
    'actual_user_power_off_observed':False,
    'unfinished_offline_work':['corrected_pipeline_hit routing','gamma_frozen_native_sim complete three-group regression'],
    'limits':'Final heartbeat transfer was measured. User power-off after this check has not been independently observed. Unfinished offline jobs and incomplete native prefix are not passing release evidence.'}
(lab/'evening-close-check.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'passed':True,'idle_at':transfer['CheckedOn'],'closed_at':now.isoformat()}))
