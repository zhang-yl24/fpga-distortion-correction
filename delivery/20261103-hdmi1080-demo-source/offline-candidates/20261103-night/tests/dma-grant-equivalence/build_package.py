"""Seal copies for the one-line grant-fire paired HDL review; no native writes."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parents[1]
BASE = WORK / 'frame-ab-dwell3s-20261102-a/native'
NATIVE = ROOT.parent / 'native'
OLD_UNIT = WORK / 'hdmi-localcmd-dma-descriptor2-20261101-e/package/unit'
OLD_DEPS = OLD_UNIT.parent / 'system/ce'
SHA_BASE = '7a21acc092ba97a268cfc319521ec8fc0e9eb0dca62289ba2ffbeae68705ec2e'
SHA_CAND = '8e27e93d18c3826aed51df59de48a81e8668c6461495a5c5d039b158ffb68e29'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    sources = [
        (BASE / 'source/rtl/experimental/hdmi1080_input_dma.v', ROOT / 'baseline/hdmi1080_input_dma.v'),
        (NATIVE / 'source/rtl/experimental/hdmi1080_input_dma.v', ROOT / 'candidate/hdmi1080_input_dma.v'),
        (NATIVE / 'source/rtl/experimental/hdmi1080_capture_cdc.v', ROOT / 'deps/hdmi1080_capture_cdc.v'),
        (NATIVE / 'source/rtl/video_async_fifo.v', ROOT / 'deps/video_async_fifo.v'),
        (OLD_UNIT / 'tb_dma_descriptor2.sv', ROOT / 'unit/tb_dma_descriptor2.sv'),
        (OLD_UNIT / 'oracle.py', ROOT / 'unit/oracle.py'),
        *[(p, ROOT / 'unit/vectors' / p.name) for p in sorted((OLD_UNIT / 'vectors').iterdir()) if p.is_file()]]
    protected = {str(s): sha(s) for s, _ in sources}
    assert sha(sources[0][0]) == SHA_BASE and sha(sources[1][0]) == SHA_CAND
    assert sources[0][0].read_bytes().replace(b'if(grant_valid && grant_ready)begin', b'if(grant_valid)begin') == sources[1][0].read_bytes()
    for source, target in sources:
        assert target.is_relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    binding = {'baseline_dma_sha256': SHA_BASE, 'candidate_dma_sha256': SHA_CAND,
        'only_dma_change': 'line119 if(grant_valid && grant_ready)begin -> if(grant_valid)begin',
        'unit_origin': str(OLD_UNIT), 'baseline_native': str(BASE), 'candidate_native': str(NATIVE),
        'stimulus_changed': False, 'original_four_csv_oracle_changed': False,
        'passive_observer': 'unit/dma_public_trace.sv: all 33 public ports; pre and post every sys edge; pre-edge invariant checks',
        'unit_coverage_retained': {'data_frames': 6, 'pixels': 1536, 'DDR_beats': 96, 'descriptors': 3,
                                  'reset_full': 1, 'reset_reserved': 1, 'pop_push': 1, 'stall_prefetch': True},
        'copied_sources': [{'origin': str(s), 'path': t.relative_to(ROOT).as_posix(), 'sha256': sha(t)} for s, t in sources],
        'historical_unit_dependencies': {p.name: {'historical_sha256': sha(OLD_DEPS / p.name),
              'new_native_sha256': sha(p), 'exact_match': sha(OLD_DEPS / p.name) == sha(p)}
              for p in [ROOT / 'candidate/hdmi1080_input_dma.v', ROOT / 'deps/hdmi1080_capture_cdc.v', ROOT / 'deps/video_async_fifo.v']},
        'native_write_or_EDA_or_hardware_or_upload': False}
    (ROOT / 'SOURCE_BINDING.json').write_text(json.dumps(binding, indent=2) + '\n', encoding='utf-8')
    assert all(sha(Path(p)) == h for p, h in protected.items())
    evidence_result = ROOT / 'evidence/xsim_approved_pair_a/result.json'
    local = {'status': json.loads(evidence_result.read_text())['status'] if evidence_result.exists() else 'HDL_NOT_RUN',
             'tools': {n: shutil.which(n) for n in ('iverilog', 'vvp')},
             'xsim_short_functional_evidence': 'evidence/xsim_approved_pair_a/result.json' if evidence_result.exists() else None,
             'native_and_original_unit_sources_verified_unchanged': len(protected)}
    (ROOT / 'LOCAL_PREFLIGHT.json').write_text(json.dumps(local, indent=2) + '\n', encoding='utf-8')
    files = [p for p in sorted(ROOT.rglob('*')) if p.is_file() and p.name != 'MANIFEST.json'
             and p.suffix != '.zip' and 'results' not in p.relative_to(ROOT).parts and '__pycache__' not in p.parts]
    manifest = {'kind': 'paired real-descriptor2 source and local XSim evidence package' if evidence_result.exists() else 'source-only paired real-descriptor2 test package; HDL not yet run',
                'files': [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in files]}
    (ROOT / 'MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    archive = ROOT / 'dma-grant-fire-paired-unit-20261103-a.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for path in [*files, ROOT / 'MANIFEST.json']:
            z.write(path, path.relative_to(ROOT).as_posix())
    print(json.dumps({'archive': str(archive), 'bytes': archive.stat().st_size, 'sha256': sha(archive),
                      'manifest_files': len(files), 'local': local}))


if __name__ == '__main__':
    main()
