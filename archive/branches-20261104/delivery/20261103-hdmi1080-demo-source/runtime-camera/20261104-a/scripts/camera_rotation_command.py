"""Offline camera SGR1 encoder. Writes/prints commands only; never opens hardware."""
from pathlib import Path
import argparse,json,math
from encode_rotation import encode,from_phase
R=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True)
g.add_argument('--angle',type=float);g.add_argument('--phase',type=lambda x:int(x,0));p.add_argument('--request-id',type=lambda x:int(x,0),default=1);p.add_argument('--output',type=Path)
a=p.parse_args();contract=json.loads((R/'PROFILE_CONTRACT.json').read_text());base=int(contract['base_param_id'],16)
r=encode(a.angle,base,a.request_id) if a.angle is not None else from_phase(a.phase,base,a.request_id)
r['camera_calibration64']=contract['camera_calibration64'];r['gamma_profile']=contract['gamma'];r['target']='CAMERA_RUNTIME_GAMMA=1 only; confirm fresh telemetry param_id before accepting'
s=json.dumps(r,indent=2)+'\n'
if a.output:a.output.write_text(s,encoding='utf-8')
print(s,end='')
