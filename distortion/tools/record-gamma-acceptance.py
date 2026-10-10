"""Update acceptance planning from existing finite evidence; no hardware access."""
from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
lab = root / 'results/lab-20261007'
read = lambda name: json.loads((lab / name).read_text(encoding='utf-8-sig'))
physical = read('gamma-physical-check.json')
auto = read('gamma-auto-check.json')
assert physical['passed'] and auto['passed']
assert physical['bitstream_sha256'] == auto['bitstream_sha256']
observation = {
    'source': 'direct_user_reply',
    'scope': 'Gamma all-twelve-angle finite automatic rotation test',
    'user_reply': '全部角度正常，无明显花屏或撕裂',
    'normal_picture': True,
    'no_obvious_corruption_or_tearing': True,
    'limits': 'Qualitative screen observation; no measured optical benefit or hardware latency.'
}
(lab / 'gamma-auto-observation.json').write_text(json.dumps(observation, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
requirements = read('competition-requirements.json')
for row in requirements['requirements']:
    if row['requirement'].startswith('Adaptive Gamma'):
        row['state'] = 'integrated_125mhz_final_timing_and_finite_physical_all_twelve_angle_visual_pass'
        row['evidence'] += [name for name in ('gamma-physical-check.json','gamma-auto-check.json','gamma-observation.json','gamma-auto-observation.json') if name not in row['evidence']]
        row['remaining'] = 'Independent matched real strong/low-light image comparisons; quantitative contrast, clipping, noise and optical quality; physical dimming-mode acceptance'
    if row['requirement'].startswith('Real calibrated'):
        row['remaining'] = 'Physical edge straightness did not improve in one left-side pose; independent multi-pose optical validation. Nonzero tangential RTL coverage is provided separately by synthetic gamma-frame regression.'
        if 'gamma-frame-simulation-check.json' not in row['evidence']:row['evidence'].append('gamma-frame-simulation-check.json')
(lab / 'competition-requirements.json').write_text(json.dumps(requirements, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
note = f'''2026-10-07 最新有限实板验收；当前 heartbeat，实际待机下载 {auto['idle_transfer']['CheckedOn']}。

最新整合版 corrected_gamma：相机提速、电脑任意角度、畸变矫正、双线性插值、自适应Gamma、DDR/HDMI与测温。
最终125MHz多角时序、130管脚、源码/位流绑定通过。
13.7°命令只发送一次并收到控制器/新增帧确认，约{physical['approx_new_frame_rate_fps']:.2f}新增帧/s。
全部12角度约{auto['approx_rates_per_second']['CF']:.2f}新增帧/s，最大处理{auto['max_process_ms_at_125mhz']:.2f}ms，视频错误0。
GM实板读到恒等/提亮，增强帧计数持续增加；用户确认首次与全部角度画面正常、无明显花屏或撕裂。
HDMI约60Hz包含重复帧，不能称为60fps处理；真实光照画质收益尚未测量。

对照：cadence零角度18.26fps、12角度16.11fps；host/cadence全部12角度15.92fps。
这些是不同有限窗口，不把小差异解释成性能提升。
Gamma整板20344 LUT、19830 FF、83 APM、20 DRM；比host/cadence增加572 LUT、319 FF，APM/DRM不变。

离线：Gamma整合10小帧10240像素、非零径向/切向系数；6原生任意角度1843200像素；3合成暗帧921600像素；全部像素/DDR写拍/CRC匹配。
三独立时钟旁路视频含四bank所有权、CRC发布、错误隔离和处理中复位；真实暗场图像不是合成回归。
客户端12项测试通过；异常后实际待机流程另有物理证据。

下一步：同源真实亮/暗场增强前后对照及噪声/剪切/对比度；物理相机旋转；独立多姿态边缘直线、MTF50/SFR；硬件输入到显示延迟。
命中流水 corrected_pipeline_hit 仍在布线，需最终时序/位流/源码检查后才可下载，不宣称实板收益。
高分辨率、长时间热稳定与重复冷启动仍待验收；不宣称1080p30/60或最终光学精度。
有限重载测试结束实际下载heartbeat；重载前至少待机60秒。内部ADC温度未外部校准。
'''
(lab / 'next-session.txt').write_text(note, encoding='utf-8')
print(json.dumps({'passed': True, 'gamma_all_angle_fps': auto['approx_rates_per_second']['CF'], 'hardware_accessed': False}))
