"""Author the selected submission from existing frozen records; no EDA/hardware."""
from pathlib import Path
import gzip, hashlib, json, shutil, os

OUT = Path(__file__).resolve().parent
if os.name == 'nt' and not str(OUT).startswith('\\\\?\\'):
    OUT = Path('\\\\?\\' + str(OUT))
DELIVERY = OUT.parent
SUBMIT = OUT.parents[2]
ARCHIVE = SUBMIT / 'distortion/results/hdmi-camera-fisheye-tile8-20261103-a'
D = json.loads((ARCHIVE / 'portable-evidence-manifest-d.json').read_bytes())
BY_HASH = {}
for e in D['BundledFiles']:
    BY_HASH.setdefault(e['SHA256'], []).append(e)
BASE = 'evidence/next-d/df8/files/'
PLAN = json.loads((ARCHIVE / (BASE + '0014/plan.json')).read_bytes())
files = []

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()

def copy_hash(wanted, rel, role, original_path=None):
    entry = BY_HASH[wanted][0]
    src = ARCHIVE / entry['Path']
    assert sha(src) == wanted and src.stat().st_size == entry['Bytes']
    dst = OUT / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    assert sha(dst) == wanted
    result = {'path': rel, 'bytes': dst.stat().st_size, 'sha256': wanted,
              'role': role, 'original_path': original_path or entry['Path'],
              'frozen_archive_path': entry['Path'], 'copy_mode': 'byte-identical'}
    files.append(result)
    return result

def copy_entry(relative, rel, role):
    src = ARCHIVE / (BASE + relative)
    return copy_hash(sha(src), rel, role)

for item in PLAN['CompiledInputs']:
    rel = item['Source']
    copy_hash(item['OriginalSHA256'], 'source/' + rel, 'production-source', 'distortion/' + rel)
    if item['OriginalSHA256'] != item['CompiledSHA256']:
        record = copy_hash(item['CompiledSHA256'], 'compiled-snapshots/' + rel, 'compiled-snapshot', item['CompiledPath'])
        record['source'] = rel
        record['transformations'] = item['Changes']
assert sum(x['role'] == 'production-source' for x in files) == 110
assert sum(x['role'] == 'compiled-snapshot' for x in files) == 6
rcf = next((p, h) for p, h in PLAN['InputSHA256'].items() if p.endswith('board1080-ddr-ioclk-priority.rcf'))
copy_hash(rcf[1], 'source/board/board1080-ddr-ioclk-priority.rcf', 'route-constraint', 'distortion/board/board1080-ddr-ioclk-priority.rcf')
copy_entry('0014/plan.json', 'build-plan.json', 'original-build-plan')
copy_entry('0015/hdmi-camera-fisheye-tile8df8-build-sources.json', 'production-source-manifest.json', 'original-production-manifest')
copy_entry('0037/hdmi_camera_fisheye_top.sbit', 'bitstream/hdmi_camera_fisheye_top.sbit', 'selected-bitstream')
for original, rel, role in [
    ('0008/receipt.json', 'evidence/program-receipt.json', 'actual-sram-program-receipt'),
    ('0009/receipt.json', 'evidence/board-30s-receipt.json', 'board-30s-receipt'),
    ('0010/receipt.json', 'evidence/board-600s-receipt.json', 'board-600s-receipt'),
    ('1073/wire.bin', 'evidence/board-30s-wire.bin', 'board-30s-raw-wire'),
    ('1074/wire.bin', 'evidence/board-600s-wire.bin', 'board-600s-raw-wire'),
    ('1259/saved-fps-df8-v3-30s-review-a.json', 'evidence/board-30s-review.json', 'saved-independent-30s-review'),
    ('1260/saved-fps-df8-v3-600s-review-a.json', 'evidence/board-600s-review.json', 'saved-independent-600s-review'),
    ('1070/df8-v3-final-physical-summary-a.json', 'evidence/final-physical-summary.json', 'saved-final-physical-summary'),
    ('0012/physical-release-provider-source-manifest-v3-a.json', 'evidence/source-provider-manifest.json', 'source-provider-identity'),
    ('0013/root-independent-complete-source-review-v3-a.json', 'evidence/independent-source-review.json', 'saved-source-review'),
    ('0025/physical-to-release-v3-go-a.json', 'evidence/release-go.json', 'saved-final-release-identity'),
]:
    copy_entry(original, rel, role)

review = json.loads((OUT / 'evidence/board-600s-review.json').read_bytes())
prewarm = review['Identity']['Prewarm']
if isinstance(prewarm, dict) and 'SHA256' in prewarm:
    copy_hash(prewarm['SHA256'], 'evidence/prewarm-identity.json', 'saved-prewarm-identity', prewarm.get('Path'))

proof = next(e for e in D['ExternalPhysicalEvidence'] if e['SHA256'] == review['Identity']['FinalProof']['SHA256'])
src = Path(proof['Path'])
assert sha(src) == proof['SHA256'] and src.stat().st_size == proof['Bytes']
dst = OUT / 'evidence/final-proof.json.gz'
with src.open('rb') as s, dst.open('wb') as d, gzip.GzipFile(filename='', mode='wb', fileobj=d, compresslevel=6, mtime=0) as z:
    shutil.copyfileobj(s, z, length=1048576)
files.append({'path': 'evidence/final-proof.json.gz', 'bytes': dst.stat().st_size, 'sha256': sha(dst),
              'role': 'complete-final-physical-proof', 'original_path': proof['Path'],
              'copy_mode': 'lossless-gzip', 'decoded_sha256': proof['SHA256'], 'decoded_bytes': proof['Bytes']})

report_files = []
for p in sorted((DELIVERY / 'reports').iterdir()):
    if p.is_file():
        report_files.append({'path': p.name, 'bytes': p.stat().st_size, 'sha256': sha(p)})

# The verifier and README are authored separately before this script runs.
for name in ['verify_selected.py', 'README.md', 'assemble_selected.py']:
    p = OUT / name
    files.append({'path': name, 'bytes': p.stat().st_size, 'sha256': sha(p), 'role': 'selected-package-tool-or-guide'})
manifest = {
    'schema': 'tile8-directfill-selected-submission-v1',
    'frozen_commit': '45223998ce3695960297937519d37759499bb4f5',
    'selected_variant': '1080p15 tile8 direct-fill INDEX8 v3',
    'selected_bit_sha256': 'aa21991374fbeb4a6733741095f38e27336f1e47dd67b963feb243428a5b353b',
    'final_adf_sha256': '2b6e662fb25cfb774a494743947c80325fd4796b423b3e0756a0f877117ae430',
    'source_file_count': 110, 'compiled_snapshot_count': 6, 'route_constraint_count': 1,
    'files': sorted(files, key=lambda x: x['path']),
    'report_files': report_files,
    'reports_root': '../reports',
    'default_verifier': 'python verify_selected.py',
    'other_bitstreams_included': False,
    'original_archive_required_for_verification': False,
    'git_required_for_verification': False,
    'portable_eda_rebuild_claimed': False,
    'scope': 'Selected production inputs, exact changed compile snapshots, one actual bit and corresponding saved evidence. Verification checks bytes and saved identity; does not rerun 1211-input historical physical audit, EDA, UART or JTAG.',
}
(OUT / 'source-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf8')
print(json.dumps({'files': len(files), 'production_sources': 110, 'compiled_snapshots': 6,
                  'reports': len(report_files), 'proof_gzip_bytes': dst.stat().st_size,
                  'manifest_sha256': sha(OUT / 'source-manifest.json')}, indent=2))
