"""Copy a completed offline candidate and receipts; never touch hardware."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

WORK = Path(__file__).resolve().parent
PROJECT = WORK.parents[1]
DEST = PROJECT / 'results/raw-camera-ready-20261101-a'


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda:stream.read(1 << 20), b''):result.update(part)
    return result.hexdigest()


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


verified = read(WORK / 'bit-d3-a/verification.json')
assert verified['Verified'] is True and verified['Target'] == 'raw_camera_capture_cam2_delay'
assert verified['HardwareAccessed'] is False
plan = read(WORK / 'bit-d3-a/bitstream-plan.json')
program = read(WORK / 'program-d3-a/plan.json')
pending = read(WORK / 'binding-d3-a/binding.pending.json')
assert program['Bitstream'] == verified['Bitstream'] and program['HardwareAccessed'] is False
assert program['Executed'] is False and not (WORK / 'program-d3-a/receipt.json').exists()
assert pending['status'] == 'PENDING_CONNECTION_AND_PROGRAMMING'
assert not any(pending['connection_review'].values())
assert not DEST.exists()

selected = {
    'd3/plan.json', 'd3/execution-result.json', 'd3/timing.tcl',
    'e4/result.json', 'h3/hold-analysis.json', 'p4/proof.json',
    'a4-request.json', 'a4-waypoints.json', 'a4/result.json',
    'e5/result.json', 'q5/result.json', 'effect-a4.json', 'io4/io-cdc.json', 'io4/query-body.tcl',
    'bit-d3-a-request.json', 'bit-d3-a/bitstream-plan.json', 'bit-d3-a/bitstream.tcl',
    'bit-d3-a/pre-bit-audit.json', 'bit-d3-a/execution-result.json', 'bit-d3-a/verification.json',
    'bit-d3-a/stdout.log', 'bit-d3-a/stderr.log',
    'bit-d3-a/generate_bitstream/raw_camera_capture_cam2_delay.sbit',
    'bit-d3-a/generate_bitstream/raw_camera_capture_cam2_delay.bgr',
    'program-d3-a/plan.json', 'program-d3-a/scan.tcl', 'program-d3-a/program.tcl',
    'binding-d3-a/validated-build.json', 'binding-d3-a/binding.pending.json',
    'release-d3-a.py', 'archive-d3-a.py',
}
selected.update('h3/' + case['Excerpt'] for p in read(WORK / 'h3/hold-analysis.json')['Paths'] for case in p['Cases'])
members = {'evidence/' + name:WORK / name for name in sorted(selected)}
session = PROJECT / 'work/camera-vga-calibration-20261031'
members.update({'session/' + name:session / name for name in (
    'README.md', 'session-plan.json', 'binding.template.json', 'dataset.draft.json',
    'capture_one.py', 'assemble_dataset.py', 'preparation-check.json')})
for path in members.values():assert path.is_file(), str(path)

inputs = {Path(name):digest for name,digest in plan['InputSHA256'].items()}
for name,digest in verified['EvidenceSHA256'].items():inputs[WORK / 'bit-d3-a' / name] = digest
for path,digest in inputs.items():assert sha(path) == digest, str(path)
assert sha(Path(verified['Bitstream']['Path'])) == verified['Bitstream']['SHA256']
DEST.mkdir()
files = []
for name,source in members.items():
    target = DEST / name
    assert len(str(target)) < 260
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = sha(source)
    shutil.copyfile(source, target)
    assert sha(target) == digest == sha(source)
    files.append({'Path':name, 'SHA256':digest, 'Bytes':target.stat().st_size,
                  'SourceRepoRelative':source.relative_to(PROJECT.parent).as_posix(), 'CopiedByteForByte':True})
readme = f'''# 正立 VGA 原图采集候选：离板准备完成

本包为当前 OV5640 CAM2 镜头标定准备完整原图导出，尚未下载或取得实板原图。
开发板已断电；必须通知用户并取得新的上电确认，才能使用新会话的 SRAM 下载流程。

- 目标：`{verified['Target']}`，PG2L100H / FBG676 / -6。
- 位流：[采图位流](evidence/bit-d3-a/generate_bitstream/raw_camera_capture_cam2_delay.sbit)。
- SHA256：`{verified['Bitstream']['SHA256']}`，{verified['Bitstream']['Bytes']:,} 字节。
- 最终 ADF：`{verified['CandidateADFSHA256']}`。
- fresh STA 双角十类检查及例外一致性通过；原生位流生成与读回核验完成。
- 最终 IO/CDC、128 引脚映射和 8 位输入延迟映射通过限定数字核查。
- 下载计划仅 SRAM，未执行。采图绑定仍为 pending，四项接线/下载声明全部 false。

UART 为 PGFRAME1 / 921600 baud / 640×480 RGB565_LE 原图，图像方向与已验收正立版本相同。
HDMI 预览是 720p60 扫描，将每四行/列采样得到的 160×120 图像放大；不能用显示器照片标定。
这次工作用于取得标定原图，当前还没有实际镜头 K/D 或畸变矫正画质验收。

下一步先确认 UART 实际端口，再下载本候选并验证一帧 614,400 字节原图、头/源/读回 CRC 与方向。
首帧通过后采集 6×9 内角点、25 mm 棋盘：12 个训练姿态和 6 个独立留出姿态。
每次摆好后稳定至少 10 秒，并保持到采集结束，详情见[采图会话](session/README.md)。

证据入口：[位流核验](evidence/bit-d3-a/verification.json)、
[修改范围审计](evidence/effect-a4.json)、[最终 IO/CDC](evidence/io4/io-cdc.json)、
[待执行 SRAM 计划](evidence/program-d3-a/plan.json)、
[待确认采图绑定](evidence/binding-d3-a/binding.pending.json)。

复制件保留原始字节，因此绝对路径仅对应原机。完整 ADF、厂商网表、路线和大时序报告只保留
本地路径/大小/哈希引用，本包不能独立重算完整物理证明。源码及工具在同仓库 distortion 下。
不得把历史计划和声明当作新的上电确认。外部 AC、原生电气设置、模拟 MTBF 与长期稳定性未验收。
已实板确认的显示版回退位流仍保存在 `../camera-vga-upright-live-20261031-a/`，本包没有覆盖它。
'''
(DEST / 'README.md').write_text(readme, encoding='utf-8', newline='\n')
files.append({'Path':'README.md', 'SHA256':sha(DEST / 'README.md'),
              'Bytes':(DEST / 'README.md').stat().st_size, 'GeneratedFromVerifiedRecords':True})
references = [{'Path':str(p), 'SHA256':h, 'Bytes':p.stat().st_size,
               'Copied':False} for p,h in sorted(inputs.items()) if p not in members.values()]
manifest = {'Schema':'raw-camera-delay-offline-ready-archive-v1',
    'CreatedUTC':datetime.now(timezone.utc).isoformat(), 'Target':verified['Target'], 'Files':files,
    'LocalReferences':references, 'Bitstream':verified['Bitstream'],
    'CandidateADFSHA256':verified['CandidateADFSHA256'], 'NativeTiming':verified['NativeTiming'],
    'CopiedFilesReadbackVerified':True, 'BoundInputsRehashed':True,
    'AuditRecomputedByArchiver':False, 'HardwareAccessed':False, 'HardwareValidated':False,
    'PendingNewBoardPowerConfirmation':True, 'PendingFirstRawFrame':True, 'CalibrationKDAvailable':False,
    'Limits':'Offline candidate only. Absolute paths and receipts describe this machine. '
             'Large ADF/routes/netlists/STA reports are local hash references; the package alone does not '
             'recompute full native proofs. Historical plans are not current power confirmation.'}
with (DEST / 'manifest.json').open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(manifest, stream, indent=2); stream.write('\n')
assert read(DEST / 'manifest.json') == manifest
print(json.dumps({'Archived':True, 'Destination':str(DEST), 'Files':len(files),
                  'LocalReferences':len(references), 'ManifestSHA256':sha(DEST / 'manifest.json'),
                  'HardwareAccessed':False}), flush=True)
