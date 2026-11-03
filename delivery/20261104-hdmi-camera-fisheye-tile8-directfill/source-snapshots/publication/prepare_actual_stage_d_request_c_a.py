"""Resolve the final selected v3 request only after all real saved results exist.

No assembler/provider invocation, EDA, hardware, source copy or Git operation.
--seal writes a fresh request and data-derived README under publication only.
The separate assembler default CLI is the later read-only preview.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import ast
import hashlib
import json
import os

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
REPO = OUT.parents[1]
ROOT = REPO / 'distortion'
WORK = ROOT / 'work/hdmi-camera-fisheye-tile8df8-20261103-a'
PEER = WORK.with_name('hdmi-camera-fisheye-tile8df9-20261103-a')
ASSEMBLER = HERE / 'assemble_stage_d_c.py'
ASSEMBLER_SHA = '1f0169ef3f4b9b18d418babed1d3d37d50211322e74fa62fd3b34ba14353b75f'
REQUEST = HERE / 'actual-assembly-request-c-a.json'
README = HERE / 'README_D_ACTUAL_FINAL.md'
PENDING = HERE / 'actual-assembly-request-c-a.pending.json'
DELIVERY = 'delivery/20261104-hdmi-camera-fisheye-tile8-directfill'
ROLE_PATHS = {
    'FinalProof': WORK / 'final-proof-v3-a.json',
    'BitVerification': WORK / 'bit-v3-a/verification.json',
    'BitPlan': WORK / 'bit-v3-a/bitstream-plan.json',
    'BitExecution': WORK / 'bit-v3-a/execution-result.json',
    'PreBitGate': WORK / 'bit-v3-a/pre-bit-audit.json',
    'ProgramPlan': WORK / 'program-v3-a/plan.json',
    'ProgramReceipt': WORK / 'program-v3-a/receipt.json',
    'FPS30': WORK / 'fps-corrected-v3-a/receipt.json',
    'FPS600': WORK / 'fps-corrected-v3-long-a/receipt.json',
    'ResourceIdentity': OUT / 'df8-v3-final-resources-a.json',
    'ProviderManifest': WORK / 'physical-release-provider-source-manifest-v3-a.json',
    'RootSourceReview': WORK / 'root-independent-complete-source-review-v3-a.json',
    'BuildPlan': WORK / 'build-a/plan.json',
    'ProductionManifest': ROOT / 'board/hdmi-camera-fisheye-tile8df8-build-sources.json',
    'SourceContractReview': PEER / 'directfill-independent-peer-review-a.json',
    'UnitReceipt': PEER / 'cache-unit-a/simulation.json',
    'CollisionReceipt': PEER / 'cache-commit-collision-a/simulation.json',
    'NormalSmall': WORK / 'system-small-a/simulation.json',
    'NormalNative': WORK / 'system-native-a/simulation.json',
    'SustainedSmall': WORK / 'system-sustained-small-a/simulation.json',
    'SustainedNative': WORK / 'system-sustained-native-a/simulation.json',
    'WarningsReview': WORK / 'source-warnings-a.json',
    'WarningsInventory': WORK / 'source-warning-inventory-a.json',
    'ReleaseGO': WORK / 'physical-to-release-v3-go-a.json',
    'PrewarmAuthority': WORK / 'release-prewarm-authority-v3-a.json',
    'PrewarmWrapper': WORK / 'release-prewarm-wrapper-source-manifest-v3-a.json',
    'PrewarmTransition': WORK / 'release-prewarm-authorized-transition-v3-a.json',
    'ReleaseInputManifest': WORK / 'release-input-manifest-v3-a.json',
    'RequestSnapshot': WORK / 'release-prewarm-bit-request-v3-a.snapshot.json',
    'RequestComparison': WORK / 'release-prewarm-recreated-request-check-v3-a.json',
    'OriginalProviderManifest': WORK / 'physical-release-provider-source-manifest-a.json',
    'OriginalRootSourceReview': WORK / 'root-independent-complete-source-review-a.json',
}
EXTRA_PATHS = {
    'FPS30IndependentV3Review': OUT / 'saved-fps-df8-v3-30s-review-a.json',
    'FPS600IndependentV3Review': OUT / 'saved-fps-df8-v3-600s-review-a.json',
    'ActualV3VsPublishedComparison': OUT / 'df8-v3-vs-published-tile8-comparison-a.json',
    'NextFPSPlan': OUT / 'TILE8_DIRECTFILL_RESULTS_AND_NEXT_PLAN_20261104.md',
    'NextFPSEvidence': OUT / 'tile8df8_v3_next_fps_evidence_20261104.json',
    'SmallPhysicalSummary': OUT / 'df8-v3-final-physical-summary-a.json',
    'SmallPhysicalSummaryMarkdown': OUT / 'df8-v3-final-physical-summary-a.md',
    'ActualTailRootExitObservation': OUT / 'v3-tail-full-physical-exit-root-observation-b.json',
    'ActualReleaseWorkerExit': OUT / 'df8-v3-prewarm-worker-exit-a.json',
    'ActualReleaseRootExitObservation': OUT / 'v3-release-exit-root-observation-a.json',
    'ActualLongFPSWorkerExit': OUT / 'df8-v3-long-fps-worker-exit-a.json',
    'SavedWireAnalyzerDSource': OUT / 'verify_saved_fps_stability_d.py',
    'ActualV3IdentityReviewerESource': OUT / 'verify_saved_fps_stability_e.py',
    'ActualV3ComparisonSource': OUT / 'verify_directfill_v3_vs_tile8_a.py',
    'FinalPublicationPinPeer': OUT / 'publication-v3-final-pin-independent-peer-a.json',
    'ActualLive32SourceCopyReceipt': HERE / 'live-source-copy-32-d-a.json',
    'ActualByteAttributeAppendReceipt': HERE / 'byte-attributes-append-d-a.json',
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def local(path):
    path = Path(path).absolute()
    require(path == path.resolve() and path.drive.upper() != 'P:', 'canonical original D:/C: path required')
    return Path('\\\\?\\' + str(path)) if os.name == 'nt' else path


def sha(path):
    digest = hashlib.sha256()
    with local(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    def unique(rows):
        value = {}
        for name, item in rows:
            require(name not in value, 'duplicate JSON member')
            value[name] = item
        return value
    return json.loads(local(path).read_text(encoding='utf-8-sig'), object_pairs_hook=unique)


def reference(path):
    require(local(path).is_file(), 'required actual input missing: ' + str(path))
    return {'Path': str(path), 'SHA256': sha(path)}


def contracts():
    require(sha(ASSEMBLER) == ASSEMBLER_SHA, 'reviewed assembler source changed')
    tree = ast.parse(ASSEMBLER.read_text(encoding='utf-8'))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ('ROLES', 'SCHEMA', 'DESTINATION'):
                    values[target.id] = ast.literal_eval(node.value)
    selected = read(ROLE_PATHS['ReleaseInputManifest'])
    roles = dict(ROLE_PATHS)
    for name in ('MapperSimulation', 'IOSimulation', 'Profile'):
        roles[name] = Path(selected[name]['Path'])
    require(set(roles) == values['ROLES'] and len(roles) == 35, 'exact frozen assembler35 roles required')
    require(selected['SystemSimulation']['Path'] == str(roles['NormalNative']), 'actual native system role changed')
    return values, roles


def pending():
    values, roles = contracts()
    return {'Schema': 'tile8df8v3-stage-d-pending-request-v1', 'AssemblyRequestComplete': False,
        'SelectedCandidate': 'df8', 'ReleaseFamily': 'tile8df8v3',
        'ActualAssemblerRequestSchema': values['SCHEMA'],
        'Assembler': reference(ASSEMBLER), 'ActualRequestOutput': str(REQUEST),
        'Repository': str(REPO), 'BasePackage': str(ROOT / 'work/tile8-publish-20261103/distortion/results/hdmi-camera-fisheye-tile8-20261103-a'),
        'DestinationPackage': str(REPO / values['DESTINATION']),
        'RolePaths': {name: str(path) for name, path in roles.items()},
        'RequiredAdditionalFiles': {name: str(path) for name, path in EXTRA_PATHS.items()},
        'Missing': [{'Role': name, 'Path': str(path)} for name, path in {**roles, **EXTRA_PATHS}.items() if not local(path).is_file()],
        'FPSRolesUseOriginalMeasurementReceipts': True, 'IndependentReviewsAndComparisonUseAdditionalFiles': True,
        'NoUnknownSHAInvented': True, 'PreviewExecuted': False, 'ArchiveAssembled': False,
        'SourceCopied': False, 'GitIndexModified': False, 'EDAExecuted': False, 'HardwareAccessed': False}


def final_content(roles):
    short, long = (read(EXTRA_PATHS[name]) for name in ('FPS30IndependentV3Review', 'FPS600IndependentV3Review'))
    comparison = read(EXTRA_PATHS['ActualV3VsPublishedComparison'])
    resource, program = read(roles['ResourceIdentity']), read(roles['ProgramReceipt'])
    for review, receipt_role in ((short, 'FPS30'), (long, 'FPS600')):
        require(review.get('Schema') == 'tile8df8v3-saved-uart-stability-review-v1' and review.get('Passed') is True and
            review.get('Role') == 'candidate' and review.get('NewCandidateMeasured') is True and
            review.get('BaselineSelfTestOnly') is False and review['Identity'].get('IdentityChainVerified') is True and
            review['Identity']['Bitstream'] == program['Bitstream'] and
            review['InputSHA256'].get(str(roles[receipt_role])) == sha(roles[receipt_role]), 'actual complete distinct v3 review identity required')
    require(short['Identity'] == long['Identity'] and comparison.get('Schema') == 'tile8df8v3-vs-published-tile8-saved-wire-comparison-v1' and
        comparison.get('Passed') is True and comparison.get('InputDrift') == [] and
        comparison['InputSHA256'].get(str(EXTRA_PATHS['FPS30IndependentV3Review'])) == sha(EXTRA_PATHS['FPS30IndependentV3Review']) and
        comparison['InputSHA256'].get(str(EXTRA_PATHS['FPS600IndependentV3Review'])) == sha(EXTRA_PATHS['FPS600IndependentV3Review']), 'actual paired comparison required')
    require(resource.get('Schema') == 'tile8-next15h-independent-resource-attribution-v3' and resource.get('Candidate') == 'df8' and
        resource.get('Draft') is False and resource.get('FinalAttributionPassed') is True and resource.get('OnBoardResourceBinding') is True and
        resource['EvidenceChain']['Bitstream'] == program['Bitstream'], 'actual final resource/bit/SRAM chain required')
    require(program.get('Passed') is True and program.get('DoneConfirmed') is True and program.get('FlashWritten') is False,
            'actual volatile SRAM completion required')
    bit = program['Bitstream']; summary = read(EXTRA_PATHS['SmallPhysicalSummary'])
    lines = ['# Tile8 directfill INDEX8 v3', '',
        'This delivery preserves the original A/B/C archive bytes and adds the selected INDEX8 directfill source and actual v3 physical, SRAM and saved UART evidence.', '',
        '源码：[directfill缓存](../../distortion/rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v) · [INDEX8处理引擎](../../distortion/rtl/experimental/hdmi_camera_fisheye_engine_tile8df8.v)。归档：[阶段D包](../../distortion/results/hdmi-camera-fisheye-tile8-20261103-a)。', '',
        '| Actual UART window | Source FPS | Captured FPS | Processed FPS | Unique presented FPS | Scan refresh FPS | Last completed frame (ms at125MHz) |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for label, review in (('30-second acquisition', short), ('600-second acquisition', long)):
        analysis = review['WireAnalysis']; rates = analysis['IndependentHostRates']
        cells = [rates[name + '_per_second'] for name in ('source_frames', 'captured_frames', 'processed_frames', 'unique_presented_frames', 'scan_refreshes')]
        lines.append('| ' + label + ' | ' + ' | '.join(f'{number:.6f}' for number in cells) + f" | {analysis['LastProcessCycles']['Last'] / 125000:.6f} |")
    counts = {key: resource['Resources'][key]['Used'] for key in ('LUT', 'FF', 'DRM', 'APM')}
    new_mean_ms = short['WireAnalysis']['LastProcessCycles']['Mean'] / 125000
    old_mean_ms = comparison['Comparison30Seconds']['Baseline']['ProcessGaugeMSUsingNominal125MHz']['Mean']
    reduction = (old_mean_ms - new_mean_ms) / old_mean_ms * 100
    short_unique = short['WireAnalysis']['IndependentHostRates']['unique_presented_frames_per_second']
    lines += ['', 'Actual bit: ' + bit['SHA256'] + f" ({bit['Bytes']:,} bytes). FinalADF: " + program['FinalADFSHA256'] + '.',
        '', '实测结论：新唯一结果帧约 ' + f'{short_unique:.2f}' + ' FPS，30 新帧/秒目标未达。HDMI 约30次/秒扫描刷新包含重复显示，不能作为30新帧目标达成。',
        '', f"短测 {short['WireAnalysis']['CompleteSamples']} 个 last-completed-frame gauge 的均值为 {new_mean_ms:.6f} ms；旧版同类短测均值为 {old_mean_ms:.6f} ms，缩短 {reduction:.4f}%。这些是同类采样 gauge，按125MHz换算，不是光学端到端延迟或完整逐帧分布。",
        '', '后续提帧方案与证据分层见 [结果与下一步方案](docs/TILE8_DIRECTFILL_RESULTS_AND_NEXT_PLAN_20261104.md)。',
        '', 'All ten physical summary tables passed with zero failures/TNS. Final physical proof SHA256: ' + summary['SourcePhysicalProof']['SHA256'] + '.',
        '', 'Final resource counts bound to the programmed SRAM image: ' + ', '.join(f'{key} {value}' for key, value in counts.items()) + '.',
        '', 'The measured unique result rate and HDMI scan rate are listed separately. Process-cycle values are sampled last-completed-frame gauges, not an optical latency distribution. The source-to-captured difference reflects admission; it is not an invalid-image-drop count. The protocol exposes no image overflow or live underflow counter.',
        '', 'Use immutable d only for saved-wire analysis and e for complete v3 source/bit/program/release identity. The saved comparison uses verify_directfill_v3_vs_tile8_a.py and the actual two reviews; no model latency is substituted for board FPS.',
        '', 'CI checks original C and new D bytes plus the explicitly mapped finite110-source/cache-unit/collision contract. It does not rerun full native EDA, STA, bit generation or board tests. Large physical artifacts stay local with original path/SHA256/size indices; the actual bit is included.',
        '', 'Run: python -B ' + DELIVERY + '/verify_stage_d_portable.py --package distortion/results/hdmi-camera-fisheye-tile8-20261103-a', '']
    return '\n'.join(lines)


def fresh_json(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write('\n')


def seal():
    intent = pending()
    require(not intent['Missing'], 'actual inputs still missing: ' + repr(intent['Missing']))
    require(not REQUEST.exists() and not README.exists(), 'fresh request/README output required')
    values, roles = contracts()
    text = final_content(roles)
    references = {name: reference(path) for name, path in roles.items()}
    additional = [{'Source': reference(path), 'Reason': name} for name, path in EXTRA_PATHS.items()]
    with README.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(text)
    additional.append({'Source': reference(README), 'Reason': 'Actual complete evidence-derived final delivery README'})
    request = {'Schema': values['SCHEMA'], 'Candidate': 'df8', 'Repository': str(REPO),
        'BasePackage': intent['BasePackage'], 'DestinationPackage': intent['DestinationPackage'],
        'Roles': references, 'AdditionalFiles': additional}
    fresh_json(REQUEST, request)
    return {'ActualRequest': reference(REQUEST), 'ActualREADME': reference(README), 'PreviewExecuted': False,
            'ArchiveAssembled': False, 'GitIndexModified': False, 'EDAExecuted': False, 'HardwareAccessed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--write-pending', action='store_true')
    group.add_argument('--seal', action='store_true')
    args = parser.parse_args()
    if args.seal:
        value = seal()
    else:
        value = pending()
        if args.write_pending:
            fresh_json(PENDING, value)
    print(json.dumps(value, indent=2))


if __name__ == '__main__':
    main()
