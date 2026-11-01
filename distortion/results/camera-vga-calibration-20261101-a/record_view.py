"""Record an explicitly reviewed capture candidate; no fitting or hardware."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--view', required=True)
p.add_argument('--attempt', type=int, required=True)
p.add_argument('--review', required=True)
p.add_argument('--next', required=True)
a = p.parse_args()
plan = read(HERE / 'session-plan.json')
pose = next(v for v in plan['planned_views'] if v['view_id'] == a.view)
quality_path = HERE / 'captures' / f'{a.view}-a{a.attempt:02d}' / 'quality.json'
q = read(quality_path); received = read(quality_path.parent / 'receive-summary.json')
assert received['passed'] and received['saved_frames'] == 1 and received['rejected_packets'] == 0
assert q['complete_board_detected'] and len(q['corners']) == 54 and q['warnings'] == []
assert q['manifest_view_candidate']['view_id'] == a.view and q['manifest_view_candidate']['split'] == pose['split']
assert all(q['identity_binding'][k] == v for k,v in plan['identity'].items())
assert sha(Path(q['image_path'])) == q['image_sha256']
assert sha(Path(q['metadata_path'])) == q['metadata_sha256']
state = read(HERE / 'capture-progress.json')
assert a.view not in {v['ViewID'] for v in state['SelectedViews']}
frame = received['frames'][0]
item = {'ViewID':a.view, 'Split':pose['split'], 'QualityPath':str(quality_path),
    'QualitySHA256':sha(quality_path), 'FrameID':frame['frame_id'], 'CRC32':frame['source_crc32'],
    'CornerCount':54, 'Warnings':[], 'Review':a.review, 'ImageSHA256':q['image_sha256']}
state['SelectedViews'].append(item)
for previous in state.get('UnselectedAttempts', []):
    if previous.get('QualityPath') == str(quality_path):
        assert previous['QualitySHA256'] == sha(quality_path)
        previous.update(SelectionRevised=True, SelectionRevisionUTC=datetime.now(timezone.utc).isoformat(),
                        SelectionRevisionReason=a.review)
counts = {'train':[[0]*3 for _ in range(3)], 'held_out':[[0]*3 for _ in range(3)]}
images = set()
for item in state['SelectedViews']:
    path = Path(item['QualityPath']); assert sha(path) == item['QualitySHA256']
    value = read(path); assert value['image_sha256'] not in images
    images.add(value['image_sha256'])
    for row in range(3):
        for col in range(3):counts[item['Split']][row][col] += value['source_image_3x3_corner_counts'][row][col]
required_cells = plan['required_coverage_cells']
scope = None
if state.get('VisibilityScope'):
    reference = state['VisibilityScope']; path = Path(reference['Path'])
    assert sha(path) == reference['SHA256']
    scope = read(path)
    assert scope['Schema'] == 'current-vga-physical-visibility-scope-v1'
    assert scope['SessionPlan']['SHA256'] == sha(HERE / 'session-plan.json')
    assert scope['Identity'] == plan['identity'] and scope['ExcludedCoverageCells'] == [[2, 2]]
    assert scope['RequiredCoverageCells'] == [v for v in required_cells if v != [2, 2]]
    assert scope['OtherQualityThresholdsChanged'] is False and scope['DecisionAnnouncedToUser'] is True
    required_cells = scope['RequiredCoverageCells']
state.update(UpdatedUTC=datetime.now(timezone.utc).isoformat(), Next=a.next,
    TrainViews=sum(v['Split']=='train' for v in state['SelectedViews']),
    HeldViews=sum(v['Split']=='held_out' for v in state['SelectedViews']),
    SourceImage3x3TrainingCornerCounts=counts['train'], SourceImage3x3HeldCornerCounts=counts['held_out'],
    RequiredCoverageCells=required_cells,
    OriginalNineCellTrainingCoveragePassed=all(counts['train'][r][c] >= 15 for r in range(3) for c in range(3)),
    ScopedTrainingCoveragePassed=all(counts['train'][r][c] >= 15 for r,c in required_cells),
    ScopedHeldCoveragePassed=all(counts['held_out'][r][c] >= 3 for r,c in required_cells),
    KDAvailable=False, CalibrationAccepted=False)
events = HERE / 'capture-records'; events.mkdir(exist_ok=True)
event = events / f'{a.view}-a{a.attempt:02d}-selected.json'
with event.open('x', encoding='utf-8', newline='\n') as stream:
    json.dump(state, stream, indent=2); stream.write('\n')
(HERE / 'capture-progress.json').write_text(json.dumps(state, indent=2)+'\n', encoding='utf-8', newline='\n')
lines = ['# 当前镜头棋盘采集进度（2026-11-01）', '',
    '主线保持当前640×480模式的真实镜头畸变矫正；1080p/帧率优化后置。', '',
    '板上为raw_camera_capture_cam2_delay，位流SHA256 292b755c8bdf5f16e8697b87fc1c9ae1dbb342226404c9f647eb27030b501fa3。',
    '用户已确认预览正立、左右正确且持续更新。UART COM7/921600输出完整640×480；HDMI预览160×120放大。', '',
    f"已保留训练候选{state['TrainViews']}/12、独立留出{state['HeldViews']}/6。均为54角点、CRC通过、无单图质量警告；尚无正式验收的K/D或矫正效果。",
    '物理棋盘为7×10方格/6×9内角点/25mm，来自用户声明；每张保持平整，每次摆好后稳定至少10秒。', '',
    '| 视图 | 分组 | 帧事务号 | CRC32 | 质量记录 |', '| --- | --- | --- | --- | --- |']
for value in state['SelectedViews']:
    lines.append(f"| {value['ViewID']} | {value['Split']} | {value['FrameID']} | {value['CRC32']} | [quality]({Path(value['QualityPath']).as_posix()}) |")
lines += ['', '训练3×3角点累计：`'+str(counts['train'])+'`。留出：`'+str(counts['held_out'])+'`。',
    '要求分区（行列从0起）：`'+str(required_cells)+'`；每区至少训练15点/留出3点。不能仅凭视图数认为覆盖已满足。',
    ('用户确认FPGA/转接板实体遮挡右下视野、相机固定。仅本次覆盖验收保守排除右下格[2,2]，其余阈值不变；原九格覆盖不通过，不能声称全画幅光学验收。未修改原计划、显示图像或硬件。详见会话visibility-scope-20261101-a.json。' if scope else '当前使用原计划全部九格覆盖范围。'), '',
    '下一步：'+a.next, '',
    '真实状态与明确选中列表：`distortion/work/camera-vga-calibration-20261031/capture-progress.json`。',
    '原图、metadata、quality及overlay均保留在该会话captures下；overlay不是标定输入。',
    '留出姿态不能重复训练姿态，不用于拟合或根据其结果反复选参数；需要补拍时保留失败attempt并递增编号。',
    '当前流程仍依赖用户保持本次上电状态；断电后旧绑定文件不能代替新的上电/下载确认。', '']
(REPO / 'handoff/CAMERA_CALIBRATION_CAPTURE_20261101.md').write_text('\n'.join(lines), encoding='utf-8', newline='\n')
print(json.dumps({'TrainViews':state['TrainViews'], 'HeldViews':state['HeldViews'], 'Coverage':counts, 'Next':a.next}))
