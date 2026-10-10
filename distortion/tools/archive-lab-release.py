"""Seal current finite laboratory evidence and matching sources; no hardware access."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib, json, shutil

root = Path(__file__).resolve().parents[1]
lab = root / 'results/lab-20261007'
read = lambda p: json.loads(p.read_text(encoding='utf-8-sig'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest().upper()
session = read(lab / 'session.json')
status = read(root / 'status.json')
assert status['current_sram_target'] == 'heartbeat', 'Finish hardware tests in idle first'
assert session['automatic_idle_transfer']['Done']
now = datetime.now(ZoneInfo('Asia/Shanghai'))
archive = root / 'results/verified' / ('lab-release-' + now.strftime('%Y%m%d-%H%M%S'))
archive.mkdir(parents=True)
targets_without_historical_source_hashes = []

def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    assert sha(src) == sha(dst), str(src)

for target, transfer in session['physical_transfers'].items():
    build = root / 'build' / target
    manifest = read(build / 'validated-build.json')
    bit = Path(manifest['Bitstream'])
    report = Path(manifest['TimingReport'])
    assert transfer['Done'] and transfer['SHA256'] == manifest['SHA256'] == sha(bit)
    assert sha(report) == manifest['TimingSHA256']
    assert 'All Constraints Met' in report.read_text()
    source_hashes = manifest.get('SourceSHA256') or {}
    if not source_hashes: targets_without_historical_source_hashes.append(target)
    for rel, digest in source_hashes.items():
        src = root / rel
        assert sha(src) == digest, 'Source changed after validated build: ' + rel
        copy(src, archive / 'source' / rel)
    for src in (bit, report, build / 'validated-build.json', build / 'build.log',
                build / 'multiseed_summary.csv', build / 'place_route' / (target + '_prr.prt')):
        copy(src, archive / 'builds' / target / src.name)
    for suffix in ('-sources.json', '-pins.json'):
        src = root / 'board' / (target + suffix)
        if src.exists(): copy(src, archive / 'source' / src.relative_to(root))

for folder in ('tools', 'tests', 'model'):
    for src in (root / folder).rglob('*'):
        if src.is_file() and '__pycache__' not in src.parts and src.suffix in ('.py','.ps1','.sv','.v','.vh','.json'):
            copy(src, archive / 'source' / src.relative_to(root))
for name in ('adaptive-twelve-native-check.json','camera-cadence-simulation-check.json','paired-cache-native-check.json','pipeline-hit-native-check.json','pipeline-twelve-native-check.json','host-control-simulation-check.json','host-angle-native-check.json','host-client-check.json','adaptive-gamma-simulation-check.json','gamma-tagged-simulation-check.json','gamma-frame-simulation-check.json','gamma-native-simulation-check.json','gamma-tone-simulation-check.json','gamma-video-simulation-check.json','gamma-frozen-capture-simulation-check.json','gamma-frozen-native-simulation-check.json'):
    if not (lab/name).exists():continue
    check=read(lab/name);assert check['passed']
    for rel,digest in check['source_sha256'].items():
        src=root/rel
        assert hashlib.sha256(src.read_bytes()).hexdigest().lower()==digest.lower(),rel
        copy(src,archive/'source'/rel)
for src in lab.rglob('*'):
    if src.is_file(): copy(src, archive / 'laboratory' / src.relative_to(lab))
if 'gamma_frozen_native_partial' in session and 'gamma_frozen_native_simulation' not in session:
    partial=session['gamma_frozen_native_partial']
    for rel,digest in partial['source_sha256'].items():
        assert sha(root/rel)==digest.upper()
        copy(root/rel,archive/'unfinished-native-source'/rel)
optical_groups=([session['fresh_physical_pair']] if 'fresh_physical_pair' in session else [])+session.get('additional_optical_pairs',[])
for group in optical_groups:
    for pair in group['pairs']:
        folder=Path(pair['directory'])
        for src in folder.iterdir():
            if src.is_file():copy(src,archive/'fresh-optical-capture'/folder.parent.name/folder.name/src.name)
        for src in folder.parent.iterdir():
            if src.is_file():copy(src,archive/'fresh-optical-capture'/folder.parent.name/src.name)
for folder in ('early_pack_sim','early_video_sim','early_native_sim','rotated_native_sim',
               'rotated_video_sim','rotated_query_sim','adc_reader_sim','temperature_monitor_sim',
               'overlap_video_sim','frame_period_sim','adaptive_video_sim','adaptive_native_sim','adaptive_writer_sim',
               'short_burst_native_sim','short_burst_query_sim','adaptive_twelve_native_sim','camera_cadence_sim',
               'paired_cache_native_sim','paired_cache_query_sim','paired_cache_video_sim',
               'pipeline_hit_native_sim','pipeline_hit_query_sim','pipeline_hit_video_sim','pipeline_hit_stream_sim','pipeline_twelve_native_sim','host_control_sim','host_angle_native_sim','gamma_tagged_sim','gamma_frame_sim','gamma_native_sim','gamma_native_tone_sim','gamma_video_sim','gamma_frozen_capture_sim','gamma_frozen_native_sim'):
    if folder=='gamma_frozen_native_sim' and 'gamma_frozen_native_simulation' not in session:continue
    if folder.startswith('pipeline_hit') and 'pipeline_hit_native_simulation' not in session:continue
    src = root / 'build' / folder / 'simulation.log'
    log = src.read_text()
    assert 'PASS' in log and 'Fatal:' not in log, folder
    copy(src, archive / 'simulation' / folder / src.name)
    for name in ('serial-simulation.log','concurrent-simulation.log','client-tests.log','host-tests.log','export.bin','tone.mem','start-proof.json','reference.json','cycles.csv','source.mem','result.mem','crcs.mem','rotations.mem','phases.mem','packets.mem','golden.mem','counts.vh','checksum.vh'):
        extra=src.parent/name
        if extra.exists():copy(extra, archive / 'simulation' / folder / name)
    snapshot=src.parent/'source-snapshot'
    for extra in snapshot.rglob('*'):
        if extra.is_file():copy(extra, archive / 'simulation' / folder / 'source-snapshot' / extra.relative_to(snapshot))
for src in (root/'vendor/competition').glob('*'):
    if src.is_file():copy(src,archive/'competition'/src.name)
for src in (root/'build/host_control_sim').glob('*'):
    if src.is_file() and (src.name.startswith('client-before-') or src.name=='idle-file-output-validation.log' or src.name.startswith('host-idle-') or src.name.startswith('host-cadence-') or src.name.startswith('gamma-')):
        copy(src,archive/'host-client-recovery'/src.name)
for candidate_file in ('gamma-board-candidate.json','gamma-capture-board-candidate.json'):
    if not (lab/candidate_file).exists():continue
    candidate=read(lab/candidate_file)
    for rel,digest in candidate['source_sha256'].items():
        assert sha(root/rel)==digest.upper()
        copy(root/rel,archive/'candidate-source'/rel)
if 'adaptive_gamma_simulation' in session:
    work=root/'build/gamma_sim'
    for name in ('tb_adaptive_gamma-simulation.log','tb_gamma_exhaustive-simulation.log','start-proof.json','reference.json','golden.mem'):
        copy(work/name,archive/'simulation/gamma_sim'/name)
    for src in (work/'source-snapshot').rglob('*'):
        if src.is_file():copy(src,archive/'simulation/gamma_sim/source-snapshot'/src.relative_to(work/'source-snapshot'))
if 'gamma_device_mapping' in session:
    proof=session['gamma_device_mapping'];assert proof['passed_mapping']
    for rel,digest in proof['source_sha256'].items():assert sha(root/rel)==digest.upper()
    for name in ('build.log','start-proof.json','map.tcl','device_map/adaptive_gamma_stream_map.adf','device_map/adaptive_gamma_stream_dmr.prt'):
        copy(root/'build/gamma_mapping'/name,archive/'mapping/gamma'/name)
idle_proofs = list((root / 'build/heartbeat').glob('program-evidence-*/transfer.json'))
latest = max(idle_proofs, key=lambda p: read(p)['CheckedOn'])
assert read(latest)['Done'] and read(latest)['CheckedOn'] == status['current_connection']['checked_on']
for src in latest.parent.iterdir():
    if src.is_file(): copy(src, archive / 'idle' / src.name)
idle_manifest = read(latest.parent / 'validated-build.json')
idle_bit = Path(idle_manifest['Bitstream'])
assert sha(idle_bit) == read(latest)['SHA256'] == idle_manifest['SHA256']
copy(idle_bit, archive / 'idle' / idle_bit.name)
for rel in ('board/heartbeat.v','board/heartbeat.fdc','board/build-heartbeat.tcl','board/program-heartbeat.tcl'):
    src = root / rel
    if src.exists(): copy(src, archive / 'source' / rel)
copy(root / 'status.json', archive / 'status.json')
copy(root / 'README.md', archive / 'README.md')
meta = {'created_at': now.isoformat(), 'hardware_accessed_by_archiver': False,
        'current_board_target': 'heartbeat', 'source_lab': str(lab),
        'targets': list(session['physical_transfers']),
        'targets_without_historical_source_hashes': targets_without_historical_source_hashes,
        'source_binding_limit': 'Older baseline manifests may lack source hashes; their bitstream and timing hashes are checked, but current source snapshots are not claimed as historically bound to those baseline binaries.',
        'scope': '640x480 native input. Host timestamps approximate new-frame rates. Internal ADC temperature is not externally calibrated. Higher resolution and final optical accuracy remain unverified.'}
(archive / 'release.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
hashes = {str(p.relative_to(archive)): sha(p) for p in archive.rglob('*') if p.is_file()}
(archive / 'files-sha256.json').write_text(json.dumps(hashes, indent=2)+'\n', encoding='utf-8')
assert all(sha(archive / rel) == digest for rel,digest in read(archive / 'files-sha256.json').items())
print(json.dumps({'archive': str(archive), 'verified_files': len(hashes)}))
