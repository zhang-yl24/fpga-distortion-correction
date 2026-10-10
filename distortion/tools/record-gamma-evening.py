"""Keep non-triggering light tests separate from successful recovery acceptance."""
from pathlib import Path
import json
root=Path(__file__).resolve().parents[1];lab=root/'results/lab-20261007'
read=lambda name:json.loads((lab/name).read_text(encoding='utf-8-sig'))
checks=[]
for tag,label in (('gamma_7_5','initial lamp/white-paper attempt'),('gamma_0','second lamp/white-paper attempt, user held scene through test')):
    check=read('host-angle-'+tag+'-check.json');transaction=read('host-angle-'+tag+'-transaction.json')
    assert check['passed'] and check['wrapper_finished_cleanly']
    rows=[v['fields'] for v in transaction['observations']]
    assert all(v['GM'] in (0,1,2) and 0<=((v['GF']-v['CF'])&0xffffffff)<=2 for v in rows)
    checks.append({'scene':label,'finite_video_and_command_passed':True,'desired_mode':2,'desired_mode_observed':any(v['GM']==2 for v in rows),
        'observed_modes':sorted({v['GM'] for v in rows}),'gamma_completed_frames_delta':(rows[-1]['GF']-rows[0]['GF'])&0xffffffff,
        'physical_check':check})
report={'hardware_accessed_by_recorder':False,'attempts':checks,'dimming_physical_acceptance_passed':any(v['desired_mode_observed'] for v in checks),
    'screen_observation':read('gamma-bright-screen-observation.json'),
    'limits':'Scene appearance is not measured sensor exposure. White-paper tests did not activate mode2. Diagnostic raw capture uses an earlier camera configuration and a later frame with clothing/background visible; it cannot prove the statistics of the Gamma white-paper scene.'}
(lab/'gamma-bright-attempts-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
recovery=read('gamma-power-cycle-recovery-check.json');assert recovery['passed']
observation={'source':'direct_user_reply','user_reply':'恢复正常，有实时变化，无明显异常','scope':'one power-cycle and fresh SRAM download of Gamma at 33.375 degrees','normal_picture':True,'live_motion':True,'no_obvious_corruption_or_tearing':True}
(lab/'gamma-power-cycle-observation.json').write_text(json.dumps(observation,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'finite_bright_tests':len(checks),'physical_dimming_passed':report['dimming_physical_acceptance_passed'],'one_power_cycle_recovery_passed':True}))
