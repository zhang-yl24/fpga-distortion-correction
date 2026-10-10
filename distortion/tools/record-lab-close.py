"""Save departure state without assuming that physical power was switched off."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[1]
now = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
plan = {
    'recorded_at': now,
    'hardware_testing_stopped': True,
    'power_off_requested': True,
    'physical_power_off_confirmed': False,
    'thermal_evidence': {
        'download_over_temp_bit': 1,
        'user_reports_chip_hot_to_touch': True,
        'measured_temperature_celsius': None,
    },
    'verified_today': {
        'camera_native_dimensions': [640, 480],
        'same_source_pairs': 2,
        'pixels_compared': 614400,
        'pixel_mismatches': 0,
        'evidence': str(root / 'results/corrected-pair-check-20261006.json'),
        'continuous_corrected_hdmi_verified': False,
    },
    'offline_priorities': [
        {'order': 1, 'task': '修复连续矫正显示版整板时序并生成可复现下载包',
         'current_state': '20 次保持时间修复后仍有 1 条 DDR PHY 快角保持违例，最差 -0.069 ns；该次生成位流还出现 scbv 选项不支持错误，需检查工程器件状态。未通过验收、未下载。',
         'acceptance': '保留 DDR 125MHz、完整原约束；慢角/快角时序全部通过、128 引脚核对、有效位流 SHA256 与构建日志归档。'},
        {'order': 2, 'task': '将两组真实原图和已核对矫正图固化为离线回归样本，优化邻域缓存及 DDR 流水线',
         'acceptance': '独立整数参考逐像素一致；暂停、异常响应、复位、帧区所有权检查通过；记录每帧周期、突发数、缓存命中率和资源。仿真速度与实测速度分开记录。'},
        {'order': 3, 'task': '开发帧边界参数切换、旋转坐标原型和温度监测方案',
         'acceptance': '旋转多角度独立参考检查、越界裁剪和单次插值验证；依据官方 ADC 文档确定温度读出与报警，当前无实际温度值。旋转模型和最终光学精度待验证。'},
    ],
    'next_lab_sequence': [
        '断电安装适配散热片并改善通风；重新上电后先取得温度读数。',
        '仅在离线全约束与位流检查通过后，以 5MHz JTAG 下载连续显示版并做短时测试。',
        '核对矫正实时画面、有效新帧率、延迟与错误计数；HDMI 刷新率不能代替处理帧率。',
    ],
    'scope': '当前实板证明限于 640x480 有界径向近似、匹配输入输出 K、无旋转的算术链路；未证明最终光学精度或连续矫正视频性能。',
}
(root / 'results/offline-plan-20261006.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
status_path = root / 'status.json'
status = json.loads(status_path.read_text(encoding='utf-8-sig'))
status['lab_departure'] = {k: plan[k] for k in ('recorded_at', 'hardware_testing_stopped', 'power_off_requested', 'physical_power_off_confirmed', 'thermal_evidence')}
status['offline_plan'] = str(root / 'results/offline-plan-20261006.json')
status['corrected_video_timing_repair'] = {'all_constraints_met': False, 'remaining_fast_hold_endpoints': 1, 'worst_hold_ns': -0.069, 'downloaded': False, 'log': str(root / 'build/corrected_video/hold-repair.log')}
status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
note = f'''\n## 离开实验室检查点（{now}）\n\n已停止新的下载与实板测试，已请用户关闭 P-ON 并断开电源；物理断电尚未收到确认。下载状态 over_temp=1，用户报告芯片很热，暂无测温值。\n\n实板两组同帧逐像素核对：614,400 像素，差异 0。连续 HDMI 矫正版尚未实板验证。20 次保持时间优化后仍有 1 条快角违例（-0.069 ns）；该次生成位流的 scbv 选项报错也需离线检查。此版本不得下载。\n\n今晚离线顺序：整板时序和位流构建 → 真实样本回归与缓存/DDR 性能优化 → 旋转/参数切换原型及温度监测。详细验收与下次接板顺序见 results/offline-plan-20261006.json。\n'''
for name in ('README.md', 'results/progress-2026-10-06.txt'):
    path = root / name
    path.write_text(path.read_text(encoding='utf-8') + note, encoding='utf-8')
print(json.dumps({'checkpoint': now, 'plan': str(root / 'results/offline-plan-20261006.json')}, ensure_ascii=False))
