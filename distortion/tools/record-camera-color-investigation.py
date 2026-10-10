"""Record diagnostic findings with immutable captures and actual idle provenance."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()

def main():
    p=argparse.ArgumentParser();p.add_argument('--capture',action='append',default=[],type=Path)
    p.add_argument('--probe',type=Path);a=p.parse_args()
    result={'recorded_utc':datetime.now(timezone.utc).isoformat(),'hardware_accessed_by_recorder':False,
        'user_observation':'Only slight green tint on live monitor; much less than stored frozen image',
        'png_rendering_check':read(ROOT/'results/lab-20261008/rgb565-rendering-check.json'),
        'research':read(ROOT/'results/lab-20261008/color-investigation-research.json'),'captures':[],
        'limits':'Saved triplets and ongoing monitor preview are different times and sample grids. Unattended optical captures lack controlled lighting and a confirmed neutral target, so cannot establish white-balance causality or light-mode quality.'}
    for path in a.capture:
        folder=path.resolve();summary=read(folder/'summary.json')
        if not summary['passed'] or not summary['idle_transfer']['Done'] or summary['idle_transfer']['Target']!='heartbeat':
            raise ValueError('Incomplete diagnostic or missing actual idle return')
        item={'folder':str(folder),'summary_sha256':sha(folder/'summary.json'),
            'source_kind':summary['source_kind'],'input_origin':summary['input_origin'],
            'capture_transfer':summary['capture_transfer'],'idle_transfer':summary['idle_transfer'],
            'groups':[{'mode':g['mode'],'bypass_mismatched_pixels':g['bypass_mismatched_pixels'],
                'tone_mismatched_pixels':g['tone']['mismatched_pixels'],
                'mean_luminance_before':g['tone']['before']['mean_luminance_code'],
                'mean_luminance_after':g['tone']['after']['mean_luminance_code']} for g in summary['groups']]}
        start=datetime.fromisoformat(summary['capture_transfer']['CheckedOn'])
        idle=datetime.fromisoformat(summary['idle_transfer']['CheckedOn'])
        item['capture_transfer_confirmed_to_idle_confirmed_seconds']=(idle-start).total_seconds()
        for file in ('sensor-colorbars-check.json',):
            if (folder/file).exists():item[file]=read(folder/file)
        result['captures'].append(item)
    if a.probe:
        folder=a.probe.resolve();probe=read(folder/'summary.json')
        if not probe['passed'] or not probe['idle_transfer']['Done'] or probe['idle_transfer']['Target']!='heartbeat':
            raise ValueError('Incomplete read-only probe or missing actual idle')
        if sha(folder/'registers.txt')!=probe['register_log_sha256']:raise ValueError('Probe log changed')
        result['probe']={'folder':str(folder),'summary_sha256':sha(folder/'summary.json'),
            'complete_scans':probe['complete_scans'],'rows':len(probe['rows']),
            'capture_transfer':probe['capture_transfer'],'idle_transfer':probe['idle_transfer'],
            'all_scans_awb_aec_agc_automatic':all(all(s['controls'][key] for key in
                ('awb_isp_enabled','awb_automatic','aec_automatic','agc_automatic')) for s in probe['scans']),
            'first_rgb_gain_codes':probe['scans'][0]['non_atomic_rgb_gain_codes'],
            'last_rgb_gain_codes':probe['scans'][-1]['non_atomic_rgb_gain_codes'],
            'first_agc_code':probe['scans'][0]['non_atomic_agc_code'],
            'last_agc_code':probe['scans'][-1]['non_atomic_agc_code'],
            'limits':'Observed gain adaptation in this run does not prove the root cause of an earlier frozen frame. Individual register rows are non-atomic; no calibrated color target or controlled illumination.'}
    for name,label in (('camera_colorbars_sim','camera colorbars'),('preview_sim','camera_preview')):
        path=ROOT/'build'/name/'simulation.log';text=path.read_text()
        if f'PASS {label}' not in text:raise ValueError('Missing completed diagnostic simulation')
        result.setdefault('simulation_logs',{})[name]={'sha256':sha(path),'passed':True}
    status=read(ROOT/'status.json')
    if status['current_sram_target']!='heartbeat':raise ValueError('Board not idle')
    result['current_board_target']='heartbeat'
    result['current_transfer_checked_on']=status['current_connection']['checked_on']
    correction=ROOT/'results/lab-20261008/d5-correction.json'
    if correction.exists():
        result['d5_mapping_correction']={'path':str(correction),'sha256':sha(correction),
            'physical_restoration_passed':read(correction)['physical_restoration_passed'],
            'limits':'Pin correction restores the missing data bit; residual optical color and white balance need controlled neutral-target acceptance.'}
    files=['tools/prepare-camera-color-candidates.py','tools/validate-camera-color-candidate.py',
        'tools/prepare-camera-color-tests.py','tools/check-rgb565-rendering.py','tools/analyze-sensor-colorbars.py',
        'tools/record-camera-color-investigation.py','tools/capture-gamma-triplets.py',
        'tools/run-camera-colorbars-sim.ps1','tests/tb_ov5640_colorbars.sv',
        'tools/build-pds.ps1','tools/program-heartbeat.ps1','tools/capture-camera-state.py',
        'tools/prepare-camera-state-probe.py','tools/validate-camera-state-probe.py',
        'tools/run-camera-state-scan-sim.ps1','tests/tb_camera_state_scan.sv',
        'tools/plot-camera-state.py','tests/test_camera_color_candidate_guard.py']
    result['tools_sha256']={n:sha(ROOT/n) for n in files}
    (ROOT/'results/lab-20261008/color-investigation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'captures':len(result['captures']),'board':'heartbeat','png_expansion_passed':True}))

if __name__=='__main__':main()
