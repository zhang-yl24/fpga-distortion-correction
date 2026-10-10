from pathlib import Path
import json
root=Path(__file__).resolve().parents[1]
baseline=root/'build/camera_capture/telemetry.txt'
(root/'results/camera-before-swap-20261006.txt').write_text(baseline.read_text(encoding='utf-8-sig'),encoding='utf-8')
manifest=json.loads((root/'build/camera_sweep/validated-build.json').read_text(encoding='utf-8-sig'))
p=root/'status.json'
s=json.loads(p.read_text(encoding='utf-8-sig'))
s['date']='2026-10-06'
s['bringup']['camera_initialization_blocker']='2026-10-06 before hardware swap: CAM=5640 E=61 INIT=0 W=106 A=3018; no sustained PCLK or complete frame. Six real COM5 samples reproduced yesterday\'s output-enable failure. User will replace camera module AND FMC adapter; replacements not yet confirmed installed.'
s['bringup']['camera_initialization_evidence']='distortion/results/camera-before-swap-20261006.txt'
s['verification'].update(camera_pad_sweep_14_masks_simulation_passed=True,
    camera_pad_sweep_routed_55_pins_checked=True,camera_pad_sweep_setup_wns_ns=0.582,
    rgb565_256bit_burst_pack_simulation_passed=True)
s['current_connection'].update(checked_on='2026-10-06',last_programmed_target='camera_sweep',
    last_programmed_sha256=manifest['SHA256'])
s['camera_pad_sweep']={'implemented':True,'programmed_5mhz':True,
    'hardware_results_collected':False,'reason':'Capture interrupted for user hardware replacement; do not infer real mask results from simulation.',
    'masks_3017_3018':['0000','1000','2000','4000','7000','7100','7200','7400','7800','7010','7020','7040','7080','7FF0'],
    'result_hold_seconds':5,'full_repeat_approx_seconds':80}
s['rgb565_burst_pack']={'implemented':True,'simulation_verified':True,
    'integrated_with_ddr':False,'hardware_verified':False,'packet_bits':256,'pixels_per_packet':16,
    'note':'PCLK-domain only. Async FIFO and DDR write completion/publishing still required. Consumer must wait for frame_complete and all writes; beat_last alone is insufficient.'}
s['next_hardware_requirement']='Await user confirmation camera module and FMC adapter replacements are installed and board powered on. Reprogram volatile SRAM at 5MHz; repeat the same camera_sweep masks and COM5 capture. Swapping both parts tests the pair, not either individual component.'
p.write_text(json.dumps(s,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
