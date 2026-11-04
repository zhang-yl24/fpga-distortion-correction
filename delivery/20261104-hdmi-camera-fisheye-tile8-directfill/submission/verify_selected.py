"""Verify this selected delivery offline with Python 3 standard library only."""
from pathlib import Path
import gzip, hashlib, json, sys, os

ROOT = Path(__file__).resolve().parent
if os.name == 'nt' and not str(ROOT).startswith('\\\\?\\'):
    ROOT = Path('\\\\?\\' + str(ROOT))
REPORTS = ROOT.parent / 'reports'
BIT = 'aa21991374fbeb4a6733741095f38e27336f1e47dd67b963feb243428a5b353b'
ADF = '2b6e662fb25cfb774a494743947c80325fd4796b423b3e0756a0f877117ae430'

def require(condition, message):
    if not condition:
        raise ValueError(message)

def safe(base, name):
    p = Path(name)
    require(not p.is_absolute() and '..' not in p.parts, 'Invalid package path: ' + name)
    resolved = (base / p).resolve()
    require(resolved.is_relative_to(base.resolve()), 'Path escaped package')
    return resolved

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()

def load(name):
    return json.loads(safe(ROOT, name).read_bytes())

def decoded_sha(path):
    h = hashlib.sha256(); size = 0
    with gzip.open(path, 'rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b); size += len(b)
    return h.hexdigest(), size

def main():
    m = load('source-manifest.json')
    require(m['schema'] == 'tile8-directfill-selected-submission-v1', 'Wrong manifest schema')
    require(m['selected_bit_sha256'] == BIT and m['final_adf_sha256'] == ADF, 'Wrong selected image')
    indexed = {}
    for record in m['files']:
        path = safe(ROOT, record['path'])
        require(record['path'] not in indexed, 'Duplicate file')
        indexed[record['path']] = record
        require(path.is_file() and path.stat().st_size == record['bytes'], 'Missing or wrong size: '+record['path'])
        require(sha(path) == record['sha256'], 'SHA mismatch: '+record['path'])
        if record.get('copy_mode') == 'lossless-gzip':
            require(decoded_sha(path) == (record['decoded_sha256'], record['decoded_bytes']), 'Decoded SHA mismatch')
    for record in m['report_files']:
        p = safe(REPORTS, record['path'])
        require(p.is_file() and p.stat().st_size == record['bytes'] and sha(p) == record['sha256'], 'Report mismatch: '+record['path'])
    images = [p for p in ROOT.rglob('*') if p.is_file() and p.suffix.lower() in ('.bit', '.sbit')]
    require(len(images) == 1 and sha(images[0]) == BIT, 'Expected exactly the selected bitstream')
    plan = load('build-plan.json')
    require(len(plan['SourceFiles']) == len(plan['CompiledInputs']) == 110, 'Production input count')
    require(len(set(plan['SourceFiles'])) == 110, 'Duplicate source')
    require(plan['SourceRoles']['UnresolvedModuleInstances'] == [], 'Unresolved modules in saved plan')
    changed = 0
    for item in plan['CompiledInputs']:
        require(indexed['source/'+item['Source']]['sha256'] == item['OriginalSHA256'], 'Original production source differs from plan')
        if item['OriginalSHA256'] != item['CompiledSHA256']:
            changed += 1
            require(indexed['compiled-snapshots/'+item['Source']]['sha256'] == item['CompiledSHA256'], 'Compiled snapshot differs')
    require(changed == 6, 'Expected six transformed compile snapshots')
    require(sum(x['role'] == 'production-source' for x in m['files']) == 110, 'Manifest production count')
    contract = load('production-source-manifest.json')
    require(indexed['production-source-manifest.json']['sha256'] == plan['Manifest']['SHA256'], 'Production manifest identity differs from plan')
    require(indexed['source/board/board1080-ddr-ioclk-priority.rcf']['sha256'] == contract['RouteConstraintSHA256'], 'Route constraint differs')
    provider = load('evidence/source-provider-manifest.json')
    require(provider['BuildPlan']['SHA256'] == indexed['build-plan.json']['sha256'], 'Saved physical provider build-plan identity differs')
    program = load('evidence/program-receipt.json')
    require(program['Passed'] and program['DoneConfirmed'] and program['ExpectedDeviceAndIDConfirmed'], 'Saved SRAM execution did not pass')
    require(not program['FlashWritten'], 'Unexpected flash operation')
    require(program['Bitstream']['SHA256'] == BIT and program['FinalADFSHA256'] == ADF, 'Program identity differs')
    result_windows = []
    for label, expected_samples, seconds, expected_frames in [('30s', 30, 29.0, 435), ('600s', 600, 599.0, 8985)]:
        receipt = load('evidence/board-'+label+'-receipt.json')
        review = load('evidence/board-'+label+'-review.json')
        wire_path = safe(ROOT, 'evidence/board-'+label+'-wire.bin')
        require(receipt['passed'] and review['Passed'] and review['NewCandidateMeasured'] and not review['BaselineSelfTestOnly'], 'Wrong board evidence role')
        require(receipt['bitstream']['SHA256'] == BIT and receipt['final_adf_sha256'] == ADF, 'Board receipt image differs')
        require(receipt['program_receipt']['sha256'] == indexed['evidence/program-receipt.json']['sha256'], 'Board program binding differs')
        require(sha(wire_path) == receipt['wire']['sha256'], 'Wire identity differs')
        identity = review['Identity']
        require(identity['Bitstream']['SHA256'] == BIT and identity['FinalADFSHA256'] == ADF and identity['IdentityChainVerified'], 'Saved review identity differs')
        require(identity['ProgramReceipt']['SHA256'] == indexed['evidence/program-receipt.json']['sha256'], 'Saved review program mismatch')
        require(identity['SourceManifest']['SHA256'] == indexed['evidence/source-provider-manifest.json']['sha256'], 'Source provider identity differs')
        require(identity['BitVerification']['SHA256'] == sha(REPORTS/'bit-verification.json'), 'Bit verification differs from saved board identity')
        require(identity['FinalProof']['SHA256'] == indexed['evidence/final-proof.json.gz']['decoded_sha256'], 'Final proof identity differs')
        frames = receipt['frames']
        require(len(frames) == expected_samples, 'Unexpected saved sample count')
        require(all(x['status_valid'] and not x['failed'] and x['fault'] == 0 and x['corrected_requested'] for x in frames), 'Saved board status/fault failure')
        core_seconds = (frames[-1]['core_ticks'] - frames[0]['core_ticks']) / 125000000
        require(core_seconds == seconds, 'Core counter window mismatch')
        counters = ['processed_frames', 'unique_presented_frames', 'scan_refreshes', 'scan_repeat_frames', 'scan_blank_frames', 'cache_hits', 'cache_misses', 'queries']
        totals = {key: sum((b[key]-a[key]) & 0xffffffff for a,b in zip(frames,frames[1:])) for key in counters}
        require(totals['processed_frames'] == totals['unique_presented_frames'] == expected_frames, 'New frame count mismatch')
        require(totals['scan_refreshes'] == expected_frames*2 and totals['scan_repeat_frames'] == expected_frames and totals['scan_blank_frames'] == 0, 'Scan/repeat counts mismatch')
        analysis = review['WireAnalysis']
        require(analysis['CompleteSamples'] == expected_samples and analysis['NominalCounterWindowSeconds'] == seconds, 'Saved review window mismatch')
        require(analysis['FaultSamples'] == 0 and analysis['TrailingPartialPacketBytes'] == 0, 'Saved fault/partial count mismatch')
        require(all(totals[k] == analysis['PerAdjacentSampleModulo32Totals'][k] for k in counters), 'Adjacent modulo totals differ')
        result_windows.append({'window': label, 'samples': expected_samples, 'core_seconds': seconds, 'unique_frames': expected_frames,
                               'nominal_unique_fps': expected_frames/seconds, 'host_unique_fps': analysis['IndependentHostRates']['unique_presented_frames_per_second']})
    reports = json.loads((REPORTS/'source-bindings.json').read_bytes())
    require(reports['bitstream']['sha256'] == BIT and reports['final_adf_sha256'] == ADF, 'Report identity mismatch')
    timing = reports['final_timing_report']
    require(decoded_sha(safe(REPORTS,timing['complete_report_file'])) == (timing['decoded_sha256'],timing['decoded_bytes']), 'Complete timing decompression mismatch')
    with gzip.open(safe(REPORTS,timing['complete_report_file']), 'rb') as f:
        prefix = f.read(timing['summary_bytes'])
    require(hashlib.sha256(prefix).hexdigest() == timing['summary_sha256'], 'Timing summary is not original prefix')
    require(len(timing['tables']) == 10 and all(t['failing_endpoints'] == 0 and t['total_negative_slack_ns'] == 0 for t in timing['tables']), 'Timing summary differs')
    resource = json.loads((REPORTS/'resource-binding.json').read_bytes())
    require(resource['FinalAttributionPassed'] and resource['OnBoardResourceBinding'], 'Resource attribution not accepted')
    require(resource['EvidenceChain']['Bitstream']['SHA256'] == BIT and resource['EvidenceChain']['FinalADF']['SHA256'] == ADF, 'Resource identity mismatch')
    require(resource['EvidenceChain']['BuildPlan']['SHA256'] == indexed['build-plan.json']['sha256'], 'Resource build-plan identity mismatch')
    print(json.dumps({'passed': True, 'schema': m['schema'], 'verified_files': len(m['files']), 'verified_report_files': len(m['report_files']),
                      'production_sources': 110, 'compiled_snapshots': 6, 'bit_sha256': BIT, 'board_windows': result_windows,
                      'timing_tables': 10, 'git_required': False, 'eda_executed': False, 'hardware_accessed': False,
                      'scope': 'Byte verification and saved identity checks; no new physical audit or hardware measurement.'}, indent=2))

if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('FAILED: '+str(error), file=sys.stderr)
        raise SystemExit(1)
