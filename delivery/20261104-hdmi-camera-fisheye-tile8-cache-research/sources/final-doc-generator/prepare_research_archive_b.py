"""Explicit research-only archive preparation. Default intent; never run tools.

--seal requires every required role to exist; --preview validates a sealed plan.
--write is a separate explicit copy operation and never invokes Git mutations.
"""
import argparse
import ast
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PUB = REPO / 'distortion/work/tile8df8-publish-20261104'
HEAD = '45223998ce3695960297937519d37759499bb4f5'
BRANCH = 'codex/hdmi-camera-fisheye-tile8-directfill'
DELIVERY = 'delivery/20261104-hdmi-camera-fisheye-tile8-cache-research'
WORKFLOW = '.github/workflows/fisheye-tile8-cache-research.yml'
ARCHIVE = 'distortion/results/hdmi-camera-fisheye-tile8-20261103-a'
MAX_COPY = 8 * 1024 * 1024


def require(ok, message):
    if not ok:
        raise ValueError(message)


def io(path):
    path = Path(path).absolute()
    return Path('\\\\?\\' + str(path)) if os.name == 'nt' else path


def sha(path):
    digest = hashlib.sha256()
    with io(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(io(path).read_text(encoding='utf-8-sig'))


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with io(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def relative(name):
    require(isinstance(name, str) and name and '\\' not in name and ':' not in name, 'canonical relative path required')
    p = PurePosixPath(name)
    require(not p.is_absolute() and p.as_posix() == name and all(n not in ('', '.', '..') for n in p.parts), 'noncanonical/escaping relative path')
    return p


def source_path(name):
    path = REPO.joinpath(*relative(name).parts)
    require(path.resolve().is_relative_to(REPO.resolve()) and path == path.resolve(), 'source escaped workspace')
    return path


def target_path(name):
    parts = relative(name)
    require('.git' not in {part.casefold() for part in parts.parts}, 'Git internals cannot be a copy destination')
    require(name == WORKFLOW or name.startswith(DELIVERY + '/'), 'target outside the two authorized new namespaces')
    path = PUB.joinpath(*parts.parts)
    require(path.resolve().is_relative_to(PUB.resolve()) and path == path.resolve(), 'target escaped publication worktree')
    for ancestor in [path, *path.parents]:
        if ancestor == PUB.parent:
            break
        require(not ancestor.is_symlink(), 'symlink in target ancestry')
        if ancestor != path and io(ancestor).exists():
            require(io(ancestor).is_dir(), 'target ancestor is not a directory')
    return path


def preflight_names(names):
    folded = {name.casefold() for name in names}
    require(len(folded) == len(names), 'duplicate/case-colliding complete target inventory')
    for name in names:
        parts = relative(name).parts
        for length in range(1, len(parts)):
            require('/'.join(parts[:length]).casefold() not in folded, 'planned file is another planned target parent')


def git_bytes(*args):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0')
    return subprocess.check_output(['git', '-c', 'core.fsmonitor=false', '-C', str(PUB), *args], env=env)


def git(*args):
    return git_bytes(*args).decode('utf-8').strip()


def publication_identity():
    require(git('rev-parse', 'HEAD') == HEAD and git('branch', '--show-current') == BRANCH, 'publication branch/HEAD changed')
    return dict(Head=HEAD, Branch=BRANCH, Worktree=str(PUB))


def protected_snapshot():
    publication_identity()
    require(not git('diff', '--name-only') and not git('diff', '--cached', '--name-only'),
            'published tracked bytes/index must be clean before protected snapshot or copy')
    paths = [n for n in git_bytes('ls-files', '-z', '--', ARCHIVE).decode().split('\0') if n]
    old = read(REPO / 'output/tile8_next15h_20261103/publication/live-source-copy-32-d-a.json')
    paths.extend(old['ExpectedFutureGitIndexPaths'])
    paths.extend(['.gitattributes', '.github/workflows/fisheye-tile8-directfill-archive.yml'])
    paths = sorted(set(paths))
    require(len([n for n in paths if n.startswith(ARCHIVE + '/')]) >= 1593, 'published archive inventory unexpectedly shrank')
    return {name: dict(SHA256=sha(PUB / name), Bytes=io(PUB / name).stat().st_size) for name in paths}


def build_inventory(spec, require_complete):
    files, missing, role_rows, big = {}, [], [], []

    def add(path, bundle_name, expected=None, role=None):
        relative(bundle_name)
        require(bundle_name.casefold() not in {n.casefold() for n in files} or bundle_name in files, 'case-colliding destination')
        if not io(path).is_file():
            missing.append(dict(Role=role, Source=str(path), BundlePath=bundle_name))
            return
        require(io(path).stat().st_size <= MAX_COPY, 'large file must use native reference index: ' + str(path))
        digest = sha(path)
        require(expected is None or digest == expected, 'saved artifact drift: ' + str(path))
        row = dict(OriginalPath=str(path.resolve()), BundlePath=bundle_name, SHA256=digest,
                   Bytes=io(path).stat().st_size, Role=role)
        require(bundle_name not in files or files[bundle_name] == row, 'conflicting file destination')
        files[bundle_name] = row

    for row in spec['Sources']:
        path = source_path(row['Source'])
        add(path, row['BundlePath'], row.get('ExpectedSHA256'), row['Role'])
    for row in spec['Evidence']:
        path = source_path(row['Source'])
        target = row['BundleDirectory']
        add(path, target + '/' + path.name, row.get('ExpectedSHA256'), row['Role'])
        if not io(path).is_file():
            continue
        value = read(path)
        require(not value.get('InputDrift'), 'saved research evidence has input drift: ' + str(path))
        require(not any(value.get(k) is True for k in ('HardwareAccessed', 'PDSAccessed') if row.get('SimulationOnly')), 'simulation role overclaims hardware/PDS')
        if row.get('RequirePassed'):
            require(value.get('Passed') is True, 'required saved unit/small did not pass: ' + str(path))
        role_rows.append(dict(Role=row['Role'], OriginalPath=str(path), BundlePath=target + '/' + path.name,
                              SavedSchema=value.get('Schema'), SavedPassed=value.get('Passed'),
                              SavedCompleteSystemPassed=value.get('CompleteSystemPassed'),
                              SavedExpectedStopFailureReproduced=value.get('ExpectedOriginalStopFailureActuallyReproduced'),
                              SavedBuildCompleted=value.get('BuildCompleted'), SavedExitCode=value.get('ExitCode')))
        artifacts = dict(value.get('ArtifactsSHA256', {}))
        for key in ('OutputSHA256', 'ResultSHA256', 'LogSHA256'):
            for name, digest in value.get(key, {}).items():
                require(name not in artifacts or artifacts[name] == digest, 'conflicting saved output identity')
                artifacts[name] = digest
        if row.get('FullSystemKind'):
            passed = value.get('Passed') is True
            require(passed or (value.get('Passed') is False and isinstance(value.get('Error'), str)
                    and value['Error'] and isinstance(value.get('EndedUTC'), str) and value['EndedUTC']),
                    'terminal failed full-system report must include its error and completion time')
            for filename in ('frames.csv', 'performance.csv', 'scans.csv', 'summary.json', 'simulation.log'):
                p = path.parent / filename
                require(not passed or io(p).is_file(), 'passed full-system CSV missing')
                if io(p).is_file():
                    artifacts.setdefault(filename, sha(p))
            if passed:
                require(read(path.parent / 'summary.json') == value['Summary'], 'raw summary JSON differs from receipt')
                require(list(csv.DictReader(io(path.parent / 'frames.csv').open(encoding='utf-8-sig'))) == value['Frames'], 'actual frames CSV differs from receipt')
                require(list(csv.DictReader(io(path.parent / 'performance.csv').open(encoding='utf-8-sig'))) == value.get('Performance', value.get('PerformanceBreakdown')), 'actual performance CSV differs from receipt')
        for name, digest in value.get('NativeLogSHA256', {}).items():
            require(name not in artifacts or artifacts[name] == digest, 'conflicting saved log identity')
            artifacts[name] = digest
        for name, digest in artifacts.items():
            # Preserve the original receipt JSON. Only its explicit relative
            # artifact key is normalized for the POSIX bundle destination.
            canonical_name = name.replace('\\', '/')
            relative(canonical_name)
            artifact = path.parent.joinpath(*PurePosixPath(canonical_name).parts)
            if io(artifact).stat().st_size <= MAX_COPY and artifact.suffix in ('.json', '.txt', '.csv', '.log'):
                add(artifact, target + '/' + canonical_name, digest, row['Role'] + ':saved-artifact')
            else:
                big.append(dict(OriginalPath=str(artifact), SHA256=digest, Bytes=io(artifact).stat().st_size,
                                BindingReceipt=str(path), IndependentlyRehashedByArchiveTool=False))
        # Native large artifacts stay outside Git. These are saved receipt
        # identity bindings, explicitly not fresh public verification.
        candidates = []
        if isinstance(value.get('TimingReport'), dict):
            candidates.append(value['TimingReport'])
        if isinstance(value.get('Report'), dict):
            candidates.append(value['Report'])
        if isinstance(value.get('SynthesisNetlist'), dict):
            candidates.append(value['SynthesisNetlist'])
        if value.get('ADF') and value.get('ADFSHA256'):
            candidates.append(dict(Path=value['ADF'], SHA256=value['ADFSHA256']))
        candidates.extend(value.get('ReferenceArtifacts', []))
        for reference in candidates:
            p = Path(reference['Path'])
            require(re.fullmatch('[0-9a-f]{64}', reference['SHA256']) and io(p).is_file(), 'native index reference missing')
            big.append(dict(OriginalPath=str(p), SHA256=reference['SHA256'], Bytes=io(p).stat().st_size,
                            BindingReceipt=str(path), IndependentlyRehashedByArchiveTool=False))
    require(not require_complete or not missing, 'required evidence is still pending: ' + ', '.join(row['Role'] for row in missing))
    return list(files.values()), missing, role_rows, big


def verify_safe_stop_clock_basis(spec, value, inputs):
    require(value.get('OriginalProduction20OtherSourcesUnchanged') is True
            and value.get('SustainedBenchOnlyFinalStopStimulusChanged') is True
            and value.get('OriginalBadDoneAssertionRetained') is True
            and value.get('OriginalAllPixelCRCOracleAndOwnershipAssertionsRetained') is True,
            'safe-stop source/assertion facts weakened')
    source_roles = {r['Role']: r for r in spec['Sources']}
    proof_path = source_path(source_roles['safe-stop-bench-safe-stop-transformation-a']['Source'])
    driver_path = source_path(source_roles['safe-stop-run_fifo_safe_system_b']['Source'])
    proof = read(proof_path)
    constants = {n.targets[0].id: ast.literal_eval(n.value) for n in ast.parse(io(driver_path).read_text()).body
                 if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                 and n.targets[0].id in ('OLD_STOP', 'SAFE_STOP')}
    original_bench = REPO / 'distortion/tests/tb_hdmi_camera_fisheye_tile8df8_sustained.sv'
    new_bench = Path(proof['NewBench']['Path'])
    old_bytes = io(original_bench).read_bytes()
    require(sha(original_bench) == proof['OriginalBenchSHA256'] == '3969f1c95698c2cba3251a821a60a51cbb7ab89745c33150c4b27f623f960990'
            and sha(new_bench) == proof['NewBench']['SHA256'] == '344e58d73e1bf9a19eda58a9633851e7e522740acf4585685572fd262b5fdd0c'
            and proof['AllOriginalAssertionsRetainedByteForByte'] is True
            and proof['NoProductionRTLChangeFromFIFOEngineD17Cache745'] is True
            and old_bytes.count(constants['OLD_STOP'].encode()) == 1
            and io(new_bench).read_bytes() == old_bytes.replace(constants['OLD_STOP'].encode(), constants['SAFE_STOP'].encode()),
            'safe stop must be the sole exact frozen native benchmark byte change')
    for p in (proof_path, driver_path, original_bench, new_bench):
        inputs[str(p)] = sha(p)
    return True


def saved_system_summary(spec):
    by_role = {row['Role']: row for row in spec['Evidence']}
    summaries = []
    inputs = {}
    for label, normal_role, sustained_role in spec['ResultsTable']:
        require(normal_role or sustained_role, 'summary row needs an actual explicitly selected run')
        result = dict(Label=label, SystemClockHz=125000000, NormalCorrectedMS=[], NormalRawMS=[], NormalRawCycles=[],
                      Latency40FrameMS=[], NormalFills=[], Latency40Fills=[],
                      NormalScanUniqueIDs=[], Latency40ScanUniqueIDs=[],
                      NormalNewIDIntervalsMS=[], Latency40NewIDIntervalsMS=[])
        for kind, role in (('Normal', normal_role), ('Latency40', sustained_role)):
            if role is None:
                result[kind + 'Status'] = 'NOT_RUN'
                continue
            require(role in by_role, 'summary role not explicitly selected')
            row = by_role[role]
            receipt_path = source_path(row['Source'])
            value = read(receipt_path)
            require(type(value.get('Passed')) is bool and value.get('InputDrift') == [] and value.get('Mode') == 'native', 'actual terminal full-native system receipt required')
            # Every new variant is bound to the same original 125-MHz full
            # system receipt, whose complete CSV/clock identity is preserved.
            if 'SystemClockHz' in value:
                require(value['SystemClockHz'] == 125000000, 'system clock differs')
                clock_value = value
            else:
                baseline = value['BaselineReceipt']
                require(sha(baseline['Path']) == baseline['SHA256'], 'same125-MHz baseline identity missing')
                clock_value = read(baseline['Path'])
                unchanged = value.get('OriginalBenchAndAllAssertionsUnchanged') is True or value.get('Original20OtherPreparedSourcesAndBenchUnchanged') is True
                if value.get('Schema') == 'tile8-assoc2way256-fifo-safe-stop-system-simulation-v1':
                    unchanged = verify_safe_stop_clock_basis(spec, value, inputs)
                require(clock_value['SystemClockHz'] == 125000000 and unchanged,
                        'new variant must retain the original125-MHz clock/assertion basis')
            if kind == 'Latency40':
                require(clock_value['DDRFirstBeatLatencyCycles'] == 40, 'sustained model must preserve actual40-latency fixture')
            inputs[str(receipt_path)] = sha(receipt_path)
            result[kind + 'Status'] = 'PASSED' if value['Passed'] else 'FAILED'
            if not value['Passed']:
                require(isinstance(value.get('Error'), str) and value['Error'] and value.get('EndedUTC'), 'failed native receipt lacks terminal error')
                result[kind + 'Failure'] = value['Error']
                result[kind + 'FailureReceipt'] = dict(Path=str(receipt_path), SHA256=sha(receipt_path))
                # Preserve raw partial CSV in the package, but do not present
                # its intermediate frame timings/IDs as a complete run.
                continue
            performance = list(csv.DictReader(io(receipt_path.parent / 'performance.csv').open(encoding='utf-8-sig')))
            frames = list(csv.DictReader(io(receipt_path.parent / 'frames.csv').open(encoding='utf-8-sig')))
            scans = list(csv.DictReader(io(receipt_path.parent / 'scans.csv').open(encoding='utf-8-sig')))
            require(performance == value.get('Performance', value.get('PerformanceBreakdown')) and frames == value['Frames'], 'saved CSV/receipt summary mismatch')
            frame_map = {r['frame_id']: r for r in frames}
            require(set(frame_map) == {r['frame_id'] for r in performance}, 'performance/frame IDs differ')
            require(all(r['hardware_process_cycles'] == frame_map[r['frame_id']]['hardware_process_cycles']
                        and r['cache_fills'] == frame_map[r['frame_id']]['fills'] for r in performance), 'frame/performance counters differ')
            corrected = [r for r in performance if r['corrected'] == '1']
            require(corrected and (kind != 'Latency40' or len(corrected) == 4), 'full corrected frame coverage absent')
            result['NormalCorrectedMS' if kind == 'Normal' else 'Latency40FrameMS'] = [int(r['hardware_process_cycles']) / 125000 for r in corrected]
            if kind == 'Normal':
                raw = [r for r in performance if r['corrected'] == '0']
                require(len(raw) == 1, 'one raw control frame required')
                result['NormalRawCycles'] = [int(r['hardware_process_cycles']) for r in raw]
                result['NormalRawMS'] = [n / 125000 for n in result['NormalRawCycles']]
            result[kind + 'Fills'] = [int(r['cache_fills']) for r in corrected]
            ids, firsts = [], []
            previous_done = -1
            for index, scan in enumerate(scans):
                require(int(scan['scanned_pixels']) == 2073600, 'partial scan cannot represent a complete unique ID')
                require(int(scan['scan_index']) == index and int(scan['done_ps']) > previous_done, 'scan completion order differs')
                previous_done = int(scan['done_ps'])
                fid = int(scan['frame_id'])
                if fid not in ids:
                    ids.append(fid)
                    firsts.append(int(scan['done_ps']))
                require(int(scan['unique_total']) == len(ids), 'scan unique-ID cumulative count differs')
            require(len(ids) == int(value['Summary']['frames_unique_scanned']), 'scanned ID/summary mismatch')
            result[kind + 'ScanUniqueIDs'] = ids
            result[kind + 'NewIDIntervalsMS'] = [(b - a) / 1e9 for a, b in zip(firsts, firsts[1:])]
            for filename in ('frames.csv', 'performance.csv', 'scans.csv'):
                p = receipt_path.parent / filename
                inputs[str(p)] = sha(p)
        summaries.append(result)
    return dict(Schema='tile8-cache-research-saved-fullsystem-summary-v1', Rows=summaries,
                InputSHA256=inputs, SystemClockHz=125000000,
                Basis='Actual saved hardware_process_cycles /125000; scans.csv first complete scan of each new frame ID, done_ps adjacent deltas.',
                BoardFPSPredicted=False, ProcessingGaugeComparedToBoard=False)


def sealed_assets(output, spec, files, roles, big):
    directory = output.with_suffix('')
    require(not directory.exists(), 'fresh sealed assets directory required')
    directory.mkdir()

    def asset(name, data):
        path = directory / name
        with path.open('xb') as stream:
            stream.write(data)
        files.append(dict(OriginalPath=str(path.resolve()), BundlePath=name, SHA256=sha(path), Bytes=len(data), Role='generated-research-asset'))

    index = dict(Schema='tile8-cache-research-large-native-artifact-index-v1', ResearchOnly=True,
                 Artifacts=big, LargeArtifactBytesCopied=False, PublicVerificationRecomputed=False,
                 Scope='Saved receipt path/SHA bindings plus current saved byte sizes; large bodies are not rehashed by this archive tool.')
    asset('large-native-artifact-index.json', (json.dumps(index, indent=2) + '\n').encode())
    system_summary = saved_system_summary(spec)
    asset('full-system-results-summary.json', (json.dumps(system_summary, indent=2) + '\n').encode())
    text = ('# Tile8 cache research — 2026-11-04\n\n'
            '**板上发布版本仍约 15 个新帧 FPS。此包为隔离研究，没有新位流、SRAM 下载或新板测结论。**\n\n'
            'c 的慢查询状态优化通过了功能仿真，但普通 core setup 为 −0.714 ns、21 fail。'
            'd 仅删除未使用的 SELECT 逻辑；其 raw core/RAM 结果也只属于研究，不能代替完整 physical/source/bit/program 门禁。'
            '2 路 256 KiB 原型从原 tagpipe 单独派生，分别保存单元、边界、系统仿真与 raw 证据。\n\n')
    cause_row = next(r for r in spec['Sources'] if r['Role'] == spec['FinalCoreCauseRole'])
    cause = read(source_path(cause_row['Source']))
    require(cause['AnalysisConsistencyPassed'] is True and cause['ActualOrdinaryCorePassed'] is False
            and cause['AllNegativeCapturePinsClassified'] is True
            and cause['RemainingDataPathFamilies'] == {'FastQueryTagToAcceptFeedback': cause['NegativeCapturePins']},
            'last raw failure classification incomplete')
    last = cause['ActualSummary']
    text += (f"**最后 CHOOSE + FRAME_CLEAR 组合仍未过时序：slow setup {last['WorstSlackNS']} ns、"
             f"TNS {last['TotalNegativeSlackNS']} ns、{last['FailingChecks']} 个失败 capture pins，全部仍属 FAST metadata → accept 反馈。** "
             '已消失的 writer ready、slow choose/fault 和 frame admission/full-clear 负路径不代表整体签核；'
             '本轮到此停止实现，不生成新位流或下载。下一步独立 metadata response queue 方案仅为设计建议。\n\n')
    role_table = '| Role | 保存的 Passed | CompleteSystemPassed（若为诊断） | BuildCompleted | ExitCode |\n|---|---|---|---|---|\n'
    for row in roles:
        role_table += f"| {row['Role']} | {row['SavedPassed']} | {row['SavedCompleteSystemPassed']} | {row['SavedBuildCompleted']} | {row['SavedExitCode']} |\n"
    text += ('\n实际完整 1080p 仿真如下，均沿用 125 MHz core。Normal corrected 是通常延迟模型的 corrected 帧；'
             '40lat 为持续输入、首返回延迟 40 拍模型的四帧。两者都不是板测，unique IDs 是完整扫描过的不同结果 ID，'
             'new-ID interval 为相邻新 ID 首次 scan_done 的间隔，不能把正常 scan 30Hz 当成新帧30FPS。\n\n'
             '| 版本 | Normal corrected / raw ms | 40lat 各帧 ms | fills（normal / 40lat） | scan unique IDs（normal / 40lat） | new-ID interval ms（normal / 40lat） |\n'
             '|---|---|---|---|---|---|\n')
    for row in system_summary['Rows']:
        stress = str(row['Latency40FrameMS']) if row['Latency40Status'] == 'PASSED' else row['Latency40Status'] + '（不列完整数字）'
        normal = str(row['NormalCorrectedMS']) + ' / ' + str(row['NormalRawMS']) if row['NormalStatus'] == 'PASSED' else row['NormalStatus'] + '（不列完整数字）'
        text += ('| ' + row['Label'] + ' | ' + normal + ' | ' + stress
                 + ' | ' + str(row['NormalFills']) + ' / ' + str(row['Latency40Fills'])
                 + ' | ' + str(row['NormalScanUniqueIDs']) + ' / ' + str(row['Latency40ScanUniqueIDs'])
                 + ' | ' + str(row['NormalNewIDIntervalsMS']) + ' / ' + str(row['Latency40NewIDIntervalsMS']) + ' |\n')
        for kind in ('Normal', 'Latency40'):
            if row[kind + 'Status'] == 'FAILED':
                text += '\n' + row['Label'] + ' ' + kind + ' 完整运行失败：`' + row[kind + 'Failure'].replace('|', '/') + '`。原始 partial 表仅供故障定位，不当作完整性能通过。\n\n'
    text += '\nraw control 在各版本可能因 writer/DDR 相位而增减，不能将 corrected 改善泛化为所有模式加速。上表保留实际 raw 控制帧，未用模型修正它。\n'
    safe_row = next(r for r in spec['Evidence'] if r['Role'] == 'fifo-safe-sustained-native')
    safe = read(source_path(safe_row['Source']))
    require(safe['Passed'] is True and safe['InputDrift'] == [] and safe['Summary']['final_drain'] is True
            and int(safe['Summary']['frames_unique_scanned']) == 4 and int(safe['Summary']['unique_scanned_pixels']) == 8294400,
            'final safe-stop full native identity/scan/drain incomplete')
    safe_crc = [r['scan_crc32'] for r in safe['Frames']]
    require(len(safe_crc) == 4 and all(re.fullmatch('[0-9a-f]{8}', n) for n in safe_crc), 'four actual complete scan CRCs required')
    text += (f"\nFIFO safe-stop 最终实际完整运行 **Passed=true**，模拟器运行用时 {safe['ElapsedSeconds']} 秒；"
             f"四个新 ID 共扫描 {safe['Summary']['unique_scanned_pixels']:,} 个独立结果像素，完整 scan CRC32 为 {safe_crc}，"
             f"final_drain={safe['Summary']['final_drain']}。这是有限四帧的完整仿真，通过不授予最后 CHOOSE + FRAME_CLEAR 的 native 性能或 STA 接受。\n")

    text += ('\n原 direct10 与原两路 stress 在 16-input 尾段将 scan_enable 于活动 display lease 中途撤销，'
             '触发原有 bad scan completion/fault07 断言，整次终态均为 FAILED。小诊断 old-stop 的 Passed=true '
             '表示成功复现预期故障，CompleteSystemPassed=false，不是完整系统通过。safe-stop 在小诊断中完整通过；'
             '其新 benchmark 只改变边界停止刺激并保留原断言，新的 FIFO safe-stop 完整 stress 是单独运行、单独一行，不能洗掉两个原失败。\n')
    text += '\n实际 raw 普通 core 与 RAM 映射（不是完整 physical signoff）：\n\n| 版本 | slow setup ns / fail | 十普通 core 表 | cache DRM36K / 逻辑 bytes |\n|---|---|---|---|\n'
    by_role = {r['Role']: r for r in spec['Evidence']}
    for label, timing_role, ram_role in spec['RawResultsTable']:
        timing = read(source_path(by_role[timing_role]['Source']))
        ram = read(source_path(by_role[ram_role]['Source']))
        row = next(r for r in timing['Rows'] if r['Corner'] == 'slow' and r['Kind'] == 'setup')
        drm = ram['DRM36Equivalent'] if 'DRM36Equivalent' in ram else ram['CacheDRM36KCount']
        require(ram['Passed'] is True and ram['TrueDualPortAndReadBeforeWrite'] is True
                and type(ram['LogicalPixelBytes']) is int and drm > 0, 'actual saved cache RAM mapping incomplete')
        text += f"| {label} | {row['WorstSlackNS']} / {row['FailingChecks']} | {timing['Passed']} | {drm} / {ram['LogicalPixelBytes']} |\n"
    resource_row = next(r for r in spec['Sources'] if r['Role'] == spec['ResourceSummaryRole'])
    resource = read(source_path(resource_row['Source']))
    require(resource['ResearchOnly'] is True and resource['Draft'] is True and resource['OnBoardResourceBinding'] is False
            and resource['PhysicalSignoff'] is False, 'raw resource summary scope differs')
    counts = resource['Counts']
    text += (f"\n2 路原型 raw route 总资源：LUT {counts['LUT']}、FF {counts['FF']}、DRM {counts['DRM']}、APM {counts['APM']}。"
             f"其中像素 cache 为 {resource['CacheRAM']['CachePrimitiveCounts']['GTP_DRM36K_E1']} 个 DRM36K、"
             f"{resource['CacheRAM']['LogicalPixelBytes']} bytes；总 DRM 还含 tag/IP，不能与像素 cache 数混用。"
             '这是未上板、普通 core 时序失败候选的 draft 资源身份，不是最终发布资源。\n')
    text += '\n各独立 raw 资源标签（均未上板，完成 raw 也不是 physical signoff）：\n\n| 版本 | LUT | FF | 总 DRM | APM |\n|---|---:|---:|---:|---:|\n'
    source_roles = {r['Role']: r for r in spec['Sources']}
    for label, role in spec['ResourceSummaryRoles']:
        saved = read(source_path(source_roles[role]['Source']))
        require(saved['ResearchOnly'] is True and type(saved['Draft']) is bool and saved['OnBoardResourceBinding'] is False
                and saved['PhysicalSignoff'] is False, 'resource table must retain its raw/draft/no-board scope')
        if not saved['Draft']:
            require(saved['ResourceAndRAMBindingPassed'] is True and saved['InputDrift'] == []
                    and saved['CoreTimingPending'] is False and saved['CacheRAMProviderFinalReceiptPending'] is False
                    and saved['OrdinaryCoreAllTenPassed'] is False and saved['NoBitstreamProduced'] is True
                    and saved['NoSRAMProgramming'] is True, 'completed failed raw resource identity incomplete')
        c = saved['Counts']
        text += f"| {label} | {c['LUT']} | {c['FF']} | {c['DRM']} | {c['APM']} |\n"
    text += ('\n新增的 engine FIFO 探针把单项 elastic stage 改为两个完整 RGB/mask/tag 槽，以 registered count 决定 ready，'
             '切断 writer ready 组合反馈。其 unit 用真实 engine 和 core/writer 接口 stubs；小系统和 raw 结果各按实际 role 保存。'
             '原两路版本 normal 完整测试通过，stress 终态失败；两者都不能授予 FIFO 新版本通过。'
             '原 687 个时序端点中 writer 反馈族为 257，其余 430 个端点仍需真实新 STA，不能承诺一个 FIFO 修好全部。\n')
    text += ('\n容量模型从同一完整冷帧轨迹复现 INDEX8/9 direct 的 37,483/31,110 fills。'
             '256 KiB 2 路 LRU 为 20,630 fills；latency0/8/40 合成服务模型省时约 4.214/5.297/9.615 ms。'
             '这些是地址/周期模型，不是 RTL 或板上 FPS；相联 tag/LRU/way 选择开销、共享 DDR 仲裁和显示调度尚不能由模型代替。\n\n'
             '例如 2 路 256 KiB 的 latency40 纯服务周期模型 28.232632 ms，与上表实际系统硬件处理计数是两个层级，不能互相冒充。\n\n'
             '便携检查命令：`python verify_research_portable_a.py --bundle .`。'
             '它只校验包内 SHA/大小、重放原 assoc-b 三 geometry 的 1173 个已保存有序四邻域像素/CRC 和 5 个边界案例，并运行 9 个有限 LRU 用例。'
             'CHOOSE 等新增 variant 的单元/6-boundary/peer 按实际字节保存，CI 不声称重放全部 variant HDL。'
             '没有重跑完整 1080p 仿真、EDA 或硬件，也没有继承旧 cache 或旧 STA 接受。'
             '大型 rtr/ADF/网表/轨迹仅在 `large-native-artifact-index.json` 中索引。\n\n'
             '下一步以真实系统性能和新的 RAM/时序实现证据决定实现方向；目标持续 ≤30 ms，不从仿真 latency40 外推上板。'
             '已发布的 A/B/C/D、32 项 live source 和旧 workflow 字节保持。\n')
    text += '\n[本轮两路 cache RTL](' + spec['Portable']['AssocCacheSource'] + ') · [本轮容量模型](' + spec['Portable']['CapacityModel'] + ')\n'
    text += '\n[后续 FAST metadata 方案](docs/NEXT_FAST_METADATA_PLAN_A.md) 仅为未来设计，未实现、未仿真、未跑 EDA；不能用于本轮性能或时序接受。\n\n'
    text += '保存角色终态附录：\n\n' + role_table
    asset('README.md', text.encode('utf-8'))
    portable = dict(Schema='tile8-cache-research-portable-map-v1', ResearchOnly=True,
                    Files=files.copy(), AssocCacheSource=spec['Portable']['AssocCacheSource'],
                    CapacityModel=spec['Portable']['CapacityModel'], UnitReceipts=spec['Portable']['UnitReceipts'],
                    BoundaryReceipts=spec['Portable'].get('BoundaryReceipts', []),
                    EDAReexecuted=False, BoardOrReleaseAcceptanceConferred=False)
    # The map cannot contain its own hash. Git and the explicit copy plan bind
    # its exact bytes; the map binds every other delivered payload first.
    asset('source-map.json', (json.dumps(portable, indent=2) + '\n').encode('utf-8'))


def prepare(spec_path, output, seal):
    spec = read(spec_path)
    require(spec['Schema'] == 'tile8-cache-research-archive-spec-v1' and spec['ResearchOnly'] is True, 'explicit research spec required')
    publication_identity()
    files, missing, roles, big = build_inventory(spec, seal)
    repository_copies = []
    for row in spec.get('RepositoryCopies', []):
        require(row['TargetPath'] == WORKFLOW, 'only the new research workflow may be copied outside delivery')
        source = source_path(row['Source'])
        require(io(source).is_file(), 'new workflow template missing')
        repository_copies.append(dict(OriginalPath=str(source), TargetPath=WORKFLOW,
                                      SHA256=sha(source), Bytes=io(source).stat().st_size))
    if seal:
        sealed_assets(output, spec, files, roles, big)
    result = dict(Schema='tile8-cache-research-archive-intent-v1', ResearchOnly=True, Sealed=seal,
                  CreatedUTC=datetime.now(timezone.utc).isoformat(), Publication=publication_identity(),
                  Destination=DELIVERY, Workflow=WORKFLOW, Spec=dict(Path=str(spec_path.resolve()), SHA256=sha(spec_path)),
                  Files=files, RepositoryCopies=repository_copies, Missing=missing, SavedRoleStatus=roles, LargeNativeArtifactIndex=big,
                  ProtectedPublishedBytes=protected_snapshot(),
                  FullSystemOrTimingAcceptanceConferred=False, BoardImageUniqueFPSRemains=15,
                  CopyExecuted=False, GitIndexModified=False, CommitCreated=False, Pushed=False,
                  EDAExecuted=False, HardwareAccessed=False)
    write_new(output, result)
    print(json.dumps(dict(Intent=str(output.resolve()), SHA256=sha(output), Sealed=seal, Files=len(files),
                          Missing=len(missing), ProtectedFiles=len(result['ProtectedPublishedBytes']), CopyExecuted=False)))


def validate_plan(path):
    value = read(path)
    require(value['Schema'] == 'tile8-cache-research-archive-intent-v1' and value['Sealed'] is True and not value['Missing'], 'complete sealed plan required')
    publication_identity()
    require(protected_snapshot() == value['ProtectedPublishedBytes'], 'published archive/ABC/live32/attributes/workflow changed')
    preflight_names([DELIVERY + '/' + row['BundlePath'] for row in value['Files']]
                    + [row['TargetPath'] for row in value.get('RepositoryCopies', [])])
    paths = set()
    for row in value['Files']:
        require(row['BundlePath'].casefold() not in paths, 'duplicate destination')
        paths.add(row['BundlePath'].casefold())
        source = Path(row['OriginalPath'])
        require(source.resolve().is_relative_to(REPO.resolve()) and sha(source) == row['SHA256']
                and io(source).stat().st_size == row['Bytes'], 'source drift before copy')
        target = target_path(DELIVERY + '/' + row['BundlePath'])
        require(not io(target).exists() or (io(target).is_file() and sha(target) == row['SHA256']), 'refuse overwriting different destination bytes')
    for row in value.get('RepositoryCopies', []):
        source = Path(row['OriginalPath'])
        target = target_path(row['TargetPath'])
        require(source.resolve().is_relative_to(REPO.resolve()) and source == source.resolve()
                and sha(source) == row['SHA256'] and io(source).stat().st_size == row['Bytes'], 'workflow source drift')
        require(not io(target).exists() or (io(target).is_file() and sha(target) == row['SHA256']), 'new workflow target differs')
    return value


def copy_plan(path, receipt_path):
    value = validate_plan(path)  # Entire set and all ancestors before any copy.
    require(not io(receipt_path).exists(), 'fresh copy receipt required')
    created, identical = [], []
    for row in value['Files'] + value.get('RepositoryCopies', []):
        source = Path(row['OriginalPath'])
        name = row.get('TargetPath', DELIVERY + '/' + row.get('BundlePath', ''))
        target = target_path(name)
        if io(target).exists():
            identical.append(name)
            continue
        io(target.parent).mkdir(parents=True, exist_ok=True)
        with io(source).open('rb') as src, io(target).open('xb') as dst:
            for block in iter(lambda: src.read(1024 * 1024), b''):
                dst.write(block)
        require(sha(target) == row['SHA256'], 'copied bytes differ')
        created.append(name)
    require(protected_snapshot() == value['ProtectedPublishedBytes'], 'protected published bytes changed')
    result = dict(Schema='tile8-cache-research-explicit-copy-receipt-v1', Passed=True, ResearchOnly=True,
                  Plan=dict(Path=str(path.resolve()), SHA256=sha(path)), Created=created, ExistingIdentical=identical,
                  ProtectedPublishedBytesPreserved=True, GitIndexModified=False, CommitCreated=False, Pushed=False,
                  EDAExecuted=False, HardwareAccessed=False, BoardOrReleaseAcceptanceConferred=False)
    write_new(receipt_path, result)
    print(json.dumps(dict(CopyExecuted=True, Created=len(created), ExistingIdentical=len(identical), ReceiptSHA256=sha(receipt_path))))


def index_plan(path, copy_receipt, output):
    value = read(path)
    receipt = read(copy_receipt)
    require(value['Sealed'] is True and not value['Missing'] and receipt.get('Passed') is True
            and receipt['Plan']['SHA256'] == sha(path), 'actual matching research copy receipt required')
    publication_identity()
    expected = {DELIVERY + '/' + row['BundlePath']: row['SHA256'] for row in value['Files']}
    expected.update({row['TargetPath']: row['SHA256'] for row in value.get('RepositoryCopies', [])})
    require(set(receipt['Created'] + receipt['ExistingIdentical']) == set(expected), 'copy receipt path inventory differs')
    for name, digest in expected.items():
        require(sha(target_path(name)) == digest, 'new copied research bytes drifted')
    for name, saved in value['ProtectedPublishedBytes'].items():
        if name != '.gitattributes':
            require(sha(PUB / name) == saved['SHA256'] and io(PUB / name).stat().st_size == saved['Bytes'], 'old published bytes drifted')
    attributes = io(PUB / '.gitattributes').read_bytes()
    before = value['ProtectedPublishedBytes']['.gitattributes']
    require(hashlib.sha256(attributes[:before['Bytes']]).hexdigest() == before['SHA256'], 'old attributes prefix changed')
    appendix = ('/' + DELIVERY + '/** -text\n/' + WORKFLOW + ' -text\n').encode('ascii')
    require(attributes[before['Bytes']:] == appendix, 'only the exact two reviewed research -text patterns may be appended by root')
    expected['.gitattributes'] = hashlib.sha256(attributes).hexdigest()
    require(not git('diff', '--cached', '--name-only'), 'index plan must precede staging')
    tracked_changes = set(git('diff', '--name-only').splitlines())
    require(tracked_changes == {'.gitattributes'}, 'unexpected tracked worktree changes')
    untracked = {n for n in git_bytes('ls-files', '--others', '--exclude-standard', '-z').decode().split('\0') if n}
    require(untracked == set(expected) - {'.gitattributes'}, 'unexpected untracked files beyond the exact research whitelist')
    paths_file = output.with_suffix('.paths')
    with paths_file.open('xb') as stream:
        stream.write(b''.join(name.encode('utf-8') + b'\0' for name in sorted(expected)))
    result = dict(Schema='tile8-cache-research-explicit-index-plan-v1', Passed=True,
                  CopyReceipt=dict(Path=str(copy_receipt.resolve()), SHA256=sha(copy_receipt)),
                  BaseHead=HEAD, Branch=BRANCH, TargetSHA256=expected,
                  NulPathspec=dict(Path=str(paths_file.resolve()), SHA256=sha(paths_file)),
                  OldPublishedBytesPreserved=True, OldAttributesPrefixPreserved=True,
                  GitIndexModified=False, CommitCreated=False, Pushed=False)
    write_new(output, result)
    print(json.dumps(dict(IndexPlan=str(output.resolve()), Paths=len(expected), SHA256=sha(output), GitIndexModified=False)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--intent', action='store_true')
    group.add_argument('--seal', action='store_true')
    group.add_argument('--preview', type=Path)
    group.add_argument('--write', type=Path)
    group.add_argument('--index-plan', type=Path)
    parser.add_argument('--copy-receipt', type=Path)
    parser.add_argument('--spec', type=Path, default=HERE / 'research-archive-spec-a.json')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output is not None:
        require(args.output.resolve().is_relative_to(HERE.resolve()) and args.output.resolve() == args.output.absolute(),
                'new intent/receipt must stay in the research publication output directory')
    if args.intent or args.seal:
        require(args.output is not None, 'fresh output intent path required')
        prepare(args.spec, args.output, args.seal)
    elif args.preview:
        value = validate_plan(args.preview)
        print(json.dumps(dict(ReadOnlyValidated=True, Files=len(value['Files']), CopyExecuted=False)))
    elif args.write:
        require(args.output is not None, 'fresh copy receipt path required')
        copy_plan(args.write, args.output)
    else:
        require(args.output is not None and args.copy_receipt is not None, 'actual copy receipt and fresh index-plan output required')
        index_plan(args.index_plan, args.copy_receipt, args.output)


if __name__ == '__main__':
    main()
