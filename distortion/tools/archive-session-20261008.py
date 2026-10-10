"""Seal today's complete native/build/capture evidence after actual idle."""
from pathlib import Path
from datetime import datetime
import hashlib,json,os,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
LAB=ROOT/'results/lab-20261008'
read=lambda path:json.loads(path.read_text(encoding='utf-8-sig'))
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest().upper()


def main():
    session=read(LAB/'session.json')
    status=read(ROOT/'status.json')
    if not (session['native_regression']['passed'] and session['candidate_build']['validated']
            and status['current_sram_target']=='heartbeat'
            and status['current_connection']['checked_on'].startswith('2026-10-08')):
        raise ValueError('Need completed native/build checks and fresh actual heartbeat first')
    env={k:v for k,v in os.environ.items() if k.upper()!='PSMODULEPATH'}
    validation=subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',
        str(ROOT/'tools/program-heartbeat.ps1'),'-Target','gamma_capture','-ValidateOnly'],
        capture_output=True,text=True,env=env,timeout=90)
    (LAB/'release-validate-only.log').write_text(validation.stdout+validation.stderr,encoding='utf-8')
    if validation.returncode:
        raise RuntimeError('Current candidate no longer passes offline pre-download gates')
    archive=ROOT/'results/verified'/('lab-release-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
    archive.mkdir()
    def copy(src,dest):
        src=src.resolve()
        if not src.is_relative_to(ROOT.resolve()) or not dest.resolve().is_relative_to(archive.resolve()):
            raise ValueError('Archive copy escaped project')
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dest)
        if sha(src)!=sha(dest):raise ValueError(f'Archive copy changed: {src}')
    manifest=read(ROOT/'build/gamma_capture/validated-build.json')
    for name,digest in manifest['SourceSHA256'].items():
        if sha(ROOT/name)!=digest:raise ValueError(f'Candidate source changed: {name}')
        copy(ROOT/name,archive/'source'/name)
    for name in session['session_tools_sha256']:
        if sha(ROOT/name)!=session['session_tools_sha256'][name]:raise ValueError(f'Session tool changed: {name}')
        copy(ROOT/name,archive/'source'/name)
    extras=['tools/gamma_triplets.py','tools/frame_protocol.py','tools/evaluate-tone-pair.py',
        'tools/capture-corrected-pairs.py','tools/host-angle.py','tools/analyze-rotation-telemetry.py',
        'tools/record-gamma-frozen-sim.py','tools/prepare-gamma-frozen-native-test.py',
        'tools/run-gamma-frozen-native-20261008-sim.ps1','tools/archive-session-20261008.py',
        'model/reference.py','model/host_protocol.py','tests/test_gamma_triplets.py','tests/test_tone_pair_analysis.py',
        'board/program-gamma_capture.tcl']
    for name in extras:copy(ROOT/name,archive/'source'/name)
    for path in LAB.rglob('*'):
        if path.is_file():copy(path,archive/'laboratory'/path.relative_to(LAB))
    build=ROOT/'build/gamma_capture'
    for path in (Path(manifest['Bitstream']),Path(manifest['TimingReport']),build/'validated-build.json',
                 build/'build.log',build/'place_route/gamma_capture_prr.prt'):
        copy(path,archive/'build'/path.name)
    native=read(LAB/'gamma-frozen-native-simulation-check.json')
    work=Path(native['work_directory'])
    for name in native['artifacts_sha256']:copy(work/name,archive/'simulation'/name)
    for path in (work/'source-snapshot').rglob('*'):
        if path.is_file():copy(path,archive/'simulation/source-snapshot'/path.relative_to(work/'source-snapshot'))
    for name in ('simulation.log','source-sha256.json','compile.log','elab.log'):
        copy(ROOT/'build/capture_warmup_sim'/name,archive/'warmup-simulation'/name)
    for target in ('gamma_capture_settled','gamma_capture_colorbars','camera_isp_probe','gamma_capture_settled_d5','gamma_capture_colorbars_d5','corrected_gamma_d5'):
        target_manifest=read(ROOT/'build'/target/'validated-build.json')
        for name,digest in target_manifest['SourceSHA256'].items():
            if sha(ROOT/name)!=digest:raise ValueError('Diagnostic source changed: '+name)
            copy(ROOT/name,archive/'source'/name)
        copy(ROOT/f'board/program-{target}.tcl',archive/f'source/board/program-{target}.tcl')
        copy(ROOT/'build'/target/'build.log',archive/'diagnostic-builds'/target/'build.log')
    for folder in ('camera_colorbars_sim','camera_state_scan_sim','preview_sim'):
        for name in ('simulation.log','source-sha256.json','compile.log','elab.log'):
            path=ROOT/'build'/folder/name
            if path.exists():copy(path,archive/'diagnostic-simulation'/folder/name)
    investigation=read(LAB/'color-investigation.json')
    probe_folder=Path(investigation['probe']['folder'])
    for path in probe_folder.rglob('*'):
        if path.is_file():copy(path,archive/'camera-state'/path.relative_to(probe_folder))
    for item in read(LAB/'grid-straightness.json')['pairs']:
        folder=Path(item['folder'])
        for path in folder.iterdir():
            if path.is_file():copy(path,archive/'historical-grid-pairs'/folder.parent.name/folder.name/path.name)
    for target in ('corrected_pipeline_cadence_seed4','corrected_pipeline_parity_cadence'):
        attempt=ROOT/'build'/target
        if (attempt/'bounded-result.json').exists():
            for path in attempt.rglob('*'):
                if path.is_file() and path.suffix.lower() in ('.log','.json','.prt','.txt') and not path.name.endswith('-pins.json'):
                    copy(path,archive/'pipeline-placement-attempt'/target/path.relative_to(attempt))
            for name in read(ROOT/f'board/{target}-sources.json'):
                copy(ROOT/name,archive/'pipeline-attempt-source'/name)
    parity=read(LAB/'pipeline-parity-regression.json')
    for name,digest in parity['source_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Parity regression input changed: '+name)
        copy(ROOT/name,archive/'parity-regression-source'/name)
    for kind,log in parity['simulation_logs'].items():
        path=Path(log['path'])
        if sha(path)!=log['sha256']:raise ValueError('Parity simulation log changed')
        for name in ('simulation.log','compile.log','elab.log','cycles.csv'):
            artifact=path.parent/name
            if artifact.exists():copy(artifact,archive/'parity-simulation'/kind/name)
    for item in session['captures']:
        folder=Path(item['path']).parent
        for path in folder.rglob('*'):
            if path.is_file():copy(path,archive/'captures'/folder.name/path.relative_to(folder))
    archived_transfer_shas=set()
    for target in ('heartbeat','gamma_capture','corrected_gamma','gamma_capture_settled','gamma_capture_colorbars','camera_isp_probe','corrected_pipeline_cadence_seed4','corrected_pipeline_parity_cadence','gamma_capture_settled_d5','gamma_capture_colorbars_d5','corrected_gamma_d5'):
        build_roots=[ROOT/'build'/target]+list((ROOT/'build').glob('preserved-'+target+'-20261008-*'))
        for target_root in build_roots:
            proofs=[path for path in target_root.glob('program-evidence-*/transfer.json')
                    if read(path)['CheckedOn'].startswith('2026-10-08')]
            if not proofs:continue
            target_manifest=read(target_root/'validated-build.json')
            # Saved absolute paths refer to the pre-preservation location.
            target_bit=target_root/'generate_bitstream'/(target+'.sbit')
            original_root=Path(target_manifest['Bitstream']).parents[1]
            target_timing=(target_root/Path(target_manifest['TimingReport']).relative_to(original_root)
                if target_manifest.get('TimingReport') else target_root/'place_route'/(target+'_timing_summary_after_hold_fix.txt'))
            if sha(target_bit)!=target_manifest['SHA256']:raise ValueError(f'Transferred bitstream changed: {target}')
            if target_manifest.get('TimingSHA256') and sha(target_timing)!=target_manifest['TimingSHA256']:
                raise ValueError(f'Transferred timing changed: {target}')
            if 'All Constraints Met' not in target_timing.read_text():raise ValueError(f'Transferred timing did not pass: {target}')
            digest=target_manifest['SHA256'];archived_transfer_shas.add(digest)
            copy(target_bit,archive/'transferred-builds'/target/digest/target_bit.name)
            copy(target_timing,archive/'transferred-builds'/target/digest/target_timing.name)
            copy(target_root/'validated-build.json',archive/'transferred-builds'/target/digest/'validated-build.json')
            for path in proofs:
                if read(path)['SHA256']!=digest:raise ValueError('Transfer differs from preserved build')
                for evidence in path.parent.iterdir():
                    if evidence.is_file():copy(evidence,archive/'transfers'/target/path.parent.name/evidence.name)
    for item in session['captures']:
        report=read(Path(item['path']))
        if report.get('capture_transfer') and report['capture_transfer']['SHA256'] not in archived_transfer_shas:
            raise ValueError('A physical capture bitstream is missing from the release')
    for name in ('board/heartbeat.v','board/heartbeat.fdc','board/build-heartbeat.tcl','board/program-heartbeat.tcl'):
        copy(ROOT/name,archive/'source'/name)
    for name in ('status.json','README.md'):copy(ROOT/name,archive/name)
    release={'created_local':datetime.now().isoformat(),'hardware_accessed_by_archiver':False,
             'current_board_target':'heartbeat','scope':'Native 640x480 zero-angle frozen-source capture; source/output identity, exact integer remap and Gamma, final 125MHz timing. Optical resolution and live enhancement benefit are separate acceptance items.',
             'physical_complete_groups':sum(len(item['groups']) for item in session['captures'] if item['passed'] and item['hardware_accessed']),
             'physical_optical_complete_groups':sum(len(item['groups']) for item in session['captures'] if item['passed'] and item['hardware_accessed'] and item['source_kind']=='physical_same_source' and item['input_origin']=='optical_camera_scene'),
             'sensor_pattern_complete_groups':sum(len(item['groups']) for item in session['captures'] if item['passed'] and item['input_origin']=='sensor_internal_test_pattern'),
             'd5_correction':'Historical AA22 source data retains numerical evidence only. New AA23 target evidence and complete physical correction findings are separately preserved in laboratory/d5-correction.json.',
             'historical_binding_limit':'Earlier diagnostic transfers retain exact bitstream, timing and source-hash manifests. The current warmed wrapper source snapshot is bound to the final candidate only; it is not claimed as the unchanged source of earlier diagnostic binaries.'}
    (archive/'release.json').write_text(json.dumps(release,indent=2)+'\n',encoding='utf-8')
    hashes={path.relative_to(archive).as_posix():sha(path) for path in archive.rglob('*') if path.is_file()}
    (archive/'files-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf-8')
    if not all(sha(archive/name)==digest for name,digest in read(archive/'files-sha256.json').items()):
        raise ValueError('Final release hash verification failed')
    print(json.dumps({'archive':str(archive),'verified_files':len(hashes),'physical_groups':release['physical_complete_groups']}))


if __name__=='__main__':main()
