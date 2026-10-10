"""Refresh today's evidence without relabelling previous lab results."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,subprocess,sys,re,importlib.util
ROOT=Path(__file__).resolve().parents[1]
read=lambda path:json.loads(path.read_text(encoding='utf-8-sig'))


def optical_modes(captures):
    """Sensor-generated patterns are hardware evidence, not optical acceptance."""
    return sorted({g['mode'] for c in captures if c['passed'] and c['hardware_accessed']
        and c['source_kind']=='physical_same_source'
        and c.get('input_origin') in (None,'optical_camera_scene')
        for g in c['groups'] if g['passed']})


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--capture',type=Path,action='append',default=[])
    args=parser.parse_args()
    lab=ROOT/'results/lab-20261008';lab.mkdir(exist_ok=True)
    status=read(ROOT/'status.json')
    current=status['current_connection']
    result={'recorded_utc':datetime.now(timezone.utc).isoformat(),'date':'2026-10-08',
            'hardware_connected_user_confirmed':True,
            'previous_sealed_release':str(ROOT/'results/verified/lab-release-20261007-235334'),
            'current_sram_target':status['current_sram_target'],'current_transfer_checked_on':current['checked_on'],
            'current_state_fresh_today':current['checked_on'].startswith('2026-10-08'),
            'thermal_policy':'Finite 24-second capture window after download; actual heartbeat download in finally; at least 60 seconds idle between heavy tests.',
            'native_regression':{'passed':False},'candidate_build':{'validated':False},'captures':[]}
    tests=[]
    for name,count in (('test_gamma_triplets.py',9),('test_tone_pair_analysis.py',6),('test_frozen_gamma_analysis.py',7),('test_pds_source_manifest.py',5),
                       ('test_camera_color_candidate_guard.py',8),('test_session_capture_scope.py',6),('test_grid_straightness.py',4),('test_d5_candidate_guard.py',6),('test_completed_angle_coverage.py',5)):
        process=subprocess.run([sys.executable,str(ROOT/'tests'/name)],capture_output=True,text=True)
        (lab/(name+'.log')).write_text(process.stdout+process.stderr,encoding='utf-8')
        if process.returncode or f'Ran {count} tests' not in process.stderr:
            raise RuntimeError(f'Host regression failed: {name}')
        tests.append({'name':name,'passed':True,'tests':count})
    result['host_tests']=tests
    warmup=ROOT/'build/capture_warmup_sim'
    if (warmup/'simulation.log').exists():
        log=(warmup/'simulation.log').read_text()
        if 'PASS capture warmup:' not in log or re.search(r'(?i)fatal:|error:',log):raise ValueError('Warmup regression failed')
        for name,digest in read(warmup/'source-sha256.json').items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest().upper()!=digest:raise ValueError('Warmup source changed')
        result['capture_warmup_regression']={'passed':True,'delay_ms_at_125mhz':2000,
            'simulation_log_sha256':hashlib.sha256((warmup/'simulation.log').read_bytes()).hexdigest().upper()}
    baseline=lab/'baseline-recovery-transaction.json'
    if baseline.exists():
        transaction=read(baseline)
        if not transaction['acknowledged'] or transaction['idle_return_code']!=0 or transaction.get('error'):
            raise ValueError('Fresh baseline recovery did not complete cleanly')
        spec=importlib.util.spec_from_file_location('rotation_metrics',ROOT/'tools/analyze-rotation-telemetry.py')
        analyzer=importlib.util.module_from_spec(spec);spec.loader.exec_module(analyzer)
        timed={'StartedUtc':transaction['acknowledged_at_utc'],'Samples':[
            {'ReceivedUtc':row['received_utc'],'Line':row['line']} for row in transaction['observations']]}
        baseline_check=analyzer.analyze(timed,warmup=0)
        baseline_check['writes']=transaction['writes']
        baseline_check['idle_return_code']=transaction['idle_return_code']
        baseline_check['transaction_sha256']=hashlib.sha256(baseline.read_bytes()).hexdigest().upper()
        (lab/'baseline-recovery-check.json').write_text(json.dumps(baseline_check,indent=2)+'\n',encoding='utf-8')
        result['fresh_baseline_recovery']=baseline_check
    native=lab/'gamma-frozen-native-simulation-check.json'
    if native.exists():
        native_check=read(native)
        # Verify both original RTL/test inputs and final output artifacts.
        for name,digest in native_check['source_sha256'].items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest().upper()!=digest:
                raise ValueError(f'Native source differs from validation: {name}')
        work=Path(native_check['work_directory'])
        for name,digest in native_check['artifacts_sha256'].items():
            if hashlib.sha256((work/name).read_bytes()).hexdigest().upper()!=digest:
                raise ValueError(f'Native output differs from validation: {name}')
        result['native_regression']={key:native_check[key] for key in ('passed','radius_guard','uart_packets','pixels_compared','modes')}
    manifest=ROOT/'build/gamma_capture/validated-build.json'
    if manifest.exists():
        build=read(manifest)
        if hashlib.sha256(Path(build['Bitstream']).read_bytes()).hexdigest().upper()!=build['SHA256']:
            raise ValueError('Candidate bitstream changed')
        result['candidate_build']={'validated':True,'sha256':build['SHA256'],'timing_sha256':build['TimingSHA256'],
                                   'source_files':len(build['SourceSHA256']),'validation_timestamp':build['Timestamp']}
        resources={}
        for key,used,available,percent in re.findall(r'\|\s*(\w+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)',(ROOT/'build/gamma_capture/build.log').read_text(encoding='utf-8-sig')):
            resources.setdefault(key,{'used':int(used),'available':int(available),'pds_percent':int(percent)})
        result['candidate_build']['mapped_global_resources']=resources
        result['candidate_build']['pin_count']=len(read(ROOT/'board/gamma_capture-pins.json'))
    for path in args.capture:
        report=read(path)
        result['captures'].append({'path':str(path.resolve()),'passed':report['passed'],
            'hardware_accessed':report['hardware_accessed'],'source_kind':report['source_kind'],
            'input_origin':report.get('input_origin','optical_camera_scene' if report['source_kind']=='physical_same_source' else 'offline_replay'),
            'target':report.get('target'),
            'groups':[{'group_id':g['group_id'],'mode':g['mode'],'passed':g['passed'],
                       'bypass_mismatched_pixels':g['bypass_mismatched_pixels'],
                       'tone_mismatched_pixels':g['tone']['mismatched_pixels'],
                       'mean_luminance_before':g['tone']['before']['mean_luminance_code'],
                       'mean_luminance_after':g['tone']['after']['mean_luminance_code']} for g in report['groups']]})
    result['physical_tone_modes_verified']=optical_modes(result['captures'])
    result['pending_acceptance']=['Physical strong-light same-source compression (mode 2)',
        'Camera color/white-balance and textured low-light optical quality',
        'Independent optical edge metrics','Hardware end-to-end latency','Higher-resolution pipeline and final route',
        'Repeated cold-start and bounded thermal stability']
    image_review=lab/'physical-image-review.json'
    if image_review.exists():
        result['physical_image_review']=read(image_review)
    color_audit=lab/'camera-color-audit.json'
    if color_audit.exists():
        result['camera_color_audit']={'path':str(color_audit),'sha256':hashlib.sha256(color_audit.read_bytes()).hexdigest().upper(),
            'scope':'Fixed-ROI channel statistics and initialization table comparison; no hardware readback or color-fidelity acceptance'}
    investigation=lab/'color-investigation.json'
    extra_tools=[]
    if investigation.exists():
        evidence=read(investigation)
        result['color_investigation']={'path':str(investigation),'sha256':hashlib.sha256(investigation.read_bytes()).hexdigest().upper(),
            'scope':'Read-only ISP register scans and internal sensor pattern; optical color fidelity remains unaccepted'}
        extra_tools=list(evidence['tools_sha256'])
        for name,digest in evidence['tools_sha256'].items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest().upper()!=digest:raise ValueError('Color investigation tool changed: '+name)
    grid=lab/'grid-straightness.json'
    if grid.exists():
        evidence=read(grid)
        result['grid_straightness']={'path':str(grid),'sha256':hashlib.sha256(grid.read_bytes()).hexdigest().upper(),
            'measured_pairs':evidence['measured_pairs'],'full_optical_acceptance':False}
        for name,digest in evidence['source_sha256'].items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest().upper()!=digest:raise ValueError('Grid metric tool changed')
    attempt=ROOT/'build/corrected_pipeline_cadence_seed4/bounded-result.json'
    if attempt.exists():result['pipeline_placement_attempt']=read(attempt)
    parity=lab/'pipeline-parity-regression.json'
    if parity.exists():
        evidence=read(parity)
        for name,digest in evidence['source_sha256'].items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest().upper()!=digest:raise ValueError('Parity input changed: '+name)
        result['pipeline_parity_regression']={'path':str(parity),'passed':evidence['passed'],
            'pixels_checked':evidence['pixels_checked'],'hardware_accessed':False,
            'logical_fast_cache_bytes_after':16384}
    parity_attempt=ROOT/'build/corrected_pipeline_parity_cadence/bounded-result.json'
    if parity_attempt.exists():result['pipeline_parity_placement_attempt']=read(parity_attempt)
    d5=lab/'d5-correction.json'
    if d5.exists():
        correction=read(d5)
        result['d5_correction']={'path':str(d5),'sha256':hashlib.sha256(d5.read_bytes()).hexdigest().upper(),
            'physical_restoration_passed':correction['physical_restoration_passed']}
        extra_tools+=list(correction['tools_sha256'])
        for name,digest in correction['tools_sha256'].items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest().upper()!=digest:raise ValueError('D5 tool changed: '+name)
        result['corrected_camera_builds']=correction['corrected_candidate_builds']
        video=correction.get('corrected_gamma_video')
        if video:
            if hashlib.sha256(Path(video['path']).read_bytes()).hexdigest().upper()!=video['sha256']:raise ValueError('Corrected video check changed')
            result['corrected_gamma_video']={key:video['telemetry_acceptance'][key] for key in
                ('passed','canonical_result_angles_deg','approx_rates_per_second','temperature_celsius_range','max_process_ms_at_125mhz','visual_observation_available')}
            for name,digest in video['telemetry_acceptance']['source_sha256'].items():
                if hashlib.sha256((ROOT/name).read_bytes()).hexdigest().upper()!=digest:raise ValueError('Video checker source changed')
            extra_tools+=list(video['telemetry_acceptance']['source_sha256'])
        status['camera_d5_correction']={'fpga_pad':'AA23','historical_wrong_pad':'AA22',
            'physical_restoration_passed':correction['physical_restoration_passed'],
            'evidence':str(d5),'optical_color_acceptance_complete':False}
        result['historical_camera_color_limit']='Before AA23 correction, DVP D5 was constrained to the adjacent unconnected AA22 pad. Numerical regressions remain as-received input tests; camera color and fresh optical acceptance must use corrected data.'
    files=['tools/program-heartbeat.ps1','tools/build-pds.ps1','tools/capture-gamma-triplets.py',
           'tools/frozen_gamma_analysis.py','tools/validate-gamma-capture.py','tools/record-session-20261008.py',
           'tools/pds_source_manifest.py','tools/expand-gamma-capture-sources.py','tools/plot-gamma-capture.py',
           'tools/archive-session-20261008.py','tools/audit-camera-color-20261008.py','tools/run-capture-warmup-sim.ps1','tests/tb_capture_warmup.sv',
           'tests/test_pds_source_manifest.py',
           'tests/test_frozen_gamma_analysis.py','tools/prepare-pipeline-cadence-candidate.py',
           'tools/build-pds-bounded.ps1','tools/read-telemetry.ps1','tests/test_session_capture_scope.py',
           'tools/check-grid-straightness.py','tests/test_grid_straightness.py',
           'tools/prepare-parity-cache-tests.py','tools/record-pipeline-parity-regression.py','tools/prepare-parity-board-candidate.py',
           'tools/host-angle.py','tools/check-d5-video-session.py','tests/test_completed_angle_coverage.py']
    files=list(dict.fromkeys(files+extra_tools))
    result['session_tools_sha256']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest().upper() for name in files}
    (lab/'session.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    status['date']='2026-10-08'
    status['session_20261008']={'evidence':str(lab/'session.json'),'updated_utc':result['recorded_utc'],
                               'native_passed':result['native_regression']['passed'],
                               'gamma_capture_build_validated':result['candidate_build']['validated'],
                               'physical_capture_checks':sum(c['passed'] and c['hardware_accessed'] for c in result['captures'])}
    (ROOT/'status.json').write_text(json.dumps(status,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'host_tests':sum(t['tests'] for t in tests),'native':result['native_regression']['passed'],
                      'build':result['candidate_build']['validated'],'captures':len(result['captures'])}))


if __name__=='__main__':main()
