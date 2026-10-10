"""Compare saved physical UART processing cycles at matched rotation angles."""
from pathlib import Path
from datetime import datetime
import hashlib
import importlib.util
import json
import re
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root = Path(__file__).resolve().parents[1]
lab = root / 'results/lab-20261007'
spec = importlib.util.spec_from_file_location('rotation_telemetry', root / 'tools/analyze-rotation-telemetry.py')
analyzer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyzer)
records = {}
for target, prefix, label in (
    ('corrected_rotate', 'rotation', '原缓存旋转版'),
    ('corrected_overlap', 'overlap', '采集与矫正并行'),
    ('corrected_adaptive', 'adaptive', '自适应分块'),
    ('corrected_adaptive_seed2', 'adaptive_seed2', '自适应分块（布局2）'),
    ('corrected_adaptive_cadence', 'cadence', '分块＋相机提速'),
):
    path = lab / (prefix + '-auto-telemetry-timed.json')
    if not path.exists():
        continue
    capture = json.loads(path.read_text(encoding='utf-8-sig'))
    summary = analyzer.analyze(capture)
    start = datetime.fromisoformat(capture['StartedUtc'])
    angles = {}
    for sample in capture['Samples']:
        if (datetime.fromisoformat(sample['ReceivedUtc']) - start).total_seconds() < 4:
            continue
        fields = {k: int(v, 16) for k, v in re.findall(r'\b(\w+)=([0-9A-Fa-f]+)\b', sample['Line'])}
        angle = round(fields['RA'] * 360 / (1 << 32)) % 360
        if fields['AU'] != 1:
            continue
        angles.setdefault(angle, []).append(fields['CY'])
    assert set(angles) == set(range(0, 360, 30)), (target, sorted(angles))
    records[target] = {
        'label': label,
        'telemetry_path': str(path.relative_to(root)),
        'telemetry_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'summary': summary,
        'angles': {str(a): {'samples': len(v), 'median_process_ms': statistics.median(v) / 125000,
                           'max_process_ms': max(v) / 125000} for a, v in sorted(angles.items())},
    }
assert len(records) >= 2, 'Need physical automatic-rotation captures from two versions'
baseline = records['corrected_rotate']['angles']
for target, record in records.items():
    record['cycle_reduction_percent_vs_original_by_angle'] = {
        a: (1 - row['median_process_ms'] / baseline[a]['median_process_ms']) * 100
        for a, row in record['angles'].items()
    }
result = {
    'passed': True,
    'hardware_accessed': False,
    'core_clock_hz': 125000000,
    'versions': records,
    'limits': 'Finite physical tests with different camera scenes. Per-angle cycles are medians of UART observations, not scene-independent benchmarks. CF counts newly completed corrected frames; HDMI PF includes repeated refreshes. Temperature uses the uncalibrated internal ADC. No simulated results are included.',
}
(lab / 'physical-rotation-comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
plt.rcParams.update({'font.family': 'Microsoft YaHei', 'text.color': 'black', 'axes.labelcolor': 'black',
                     'xtick.color': 'black', 'ytick.color': 'black'})
fig, ax = plt.subplots(figsize=(10, 4.5), layout='constrained')
for record in records.values():
    ax.plot(range(0, 360, 30), [record['angles'][str(a)]['median_process_ms'] for a in range(0, 360, 30)],
            marker='o', label=record['label'])
ax.set(xlabel='旋转角度（°）', ylabel='采样中的每帧处理时间中位数（ms）',
       title='640×480、125 MHz：12 个角度的实板处理时间')
ax.set_xticks(range(0, 360, 30))
ax.set_ylim(bottom=0)
ax.spines[['top', 'right']].set_visible(False)
ax.legend(frameon=False)
fig.supxlabel('仅比较有限实板串口采样；场景与采样时刻不同。处理时间不等于采集周期或 HDMI 刷新周期。', fontsize=10)
fig.savefig(lab / 'physical-rotation-comparison.png', dpi=150)
plt.close(fig)
print(json.dumps({'passed': True, 'physical_versions': list(records)}, ensure_ascii=False))
