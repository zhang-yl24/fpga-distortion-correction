"""Record simulated integration and provisional real calibration separately."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil

root=Path(__file__).resolve().parents[1]
sources=['rtl/ddr_read_arbiter.v','rtl/ddr_write_arbiter.v','rtl/ddr_result_writer.v','rtl/remap_frame_engine.v',
    'tests/tb_ddr_read_arbiter.sv','tests/tb_ddr_result_store.sv','tests/tb_remap_frame_engine.sv',
    'tools/generate-result-writer-test.py','tools/generate-frame-engine-test.py',
    'tools/run-frame-store-sim.ps1','tools/run-frame-engine-sim.ps1']
logs={}
for name,path in {'result_writer':'build/frame_store_sim/tb_ddr_result_store.log',
    'read_arbiter':'build/frame_store_sim/tb_ddr_read_arbiter.log',
    'frame_engine':'build/frame_engine_sim/simulation.log'}.items():
    text=(root/path).read_text(errors='replace')
    passes=[line for line in text.splitlines() if line.startswith('PASS ')]
    assert len(passes)==1 and not any('Fatal:' in line for line in text.splitlines())
    logs[name]=passes[0]
audit=json.loads((root/'results/calibration-audit-20261006/audit.json').read_text())
comparison=json.loads((root/'results/calibration-comparison-20261006.json').read_text())
result={'recorded_at':datetime.now().isoformat(timespec='seconds'),
    'implemented':True,'simulation_verified':True,'hardware_integrated':False,'hardware_programmed':False,
    'new_frame_pipeline_routed_timing_verified':False,'frame_engine_golden_pixels':1536,
    'result_writer_golden_pixels':1536,'tests':logs,
    'output_format':'RGB888 interpolation -> R/B high 5 bits, G high 6 bits -> RGB565 DDR frame',
    'bank_policy':'Aligned, non-overlapping source/output ranges; parent also locks display bank until release.',
    'publish_policy':'Only complete frame after ordered pixel storage and write drain; no faulted partial frame published.',
    'source_sha256':{s:hashlib.sha256((root/s).read_bytes()).hexdigest().upper() for s in sources},
    'limits':'Integration simulation uses three 32x16 synthetic frames; no measured FPGA correction/FPS/latency or full-board timing pass.'}
calibration={'real_images_available':True,'accepted_final_parameters_available':False,
    'selected_views':audit['selected_views'],'training_views':len(comparison['train_images']),
    'held_out_views':len(comparison['held_out_images']),'square_mm':20,
    'corner_counts_by_3x3_region':audit['corner_counts_by_3x3_region'],
    'all_nine_regions_observed':audit['all_nine_regions_observed'],
    'candidates':audit['candidates'],
    'decision':'Do not program first-round coefficients. Supplement left/lower/edge coverage, refit and validate full-image maps.',
    'comparison':'distortion/results/calibration-comparison-20261006.json',
    'audit':'distortion/results/calibration-audit-20261006/audit.json'}
(root/'results/frame-engine-progress-20261006.json').write_text(json.dumps(result,indent=2)+'\n')
(root/'results/calibration-status-20261006.json').write_text(json.dumps(calibration,indent=2)+'\n')
archive=root/'results/verified/frame-engine-20261006'
for source in sources:
    dest=archive/source;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/source,dest)
for source in ['build/frame_engine_sim/source.mem','build/frame_engine_sim/result.mem','build/frame_engine_sim/crcs.mem',
    'build/frame_engine_sim/reference.json','build/frame_engine_sim/simulation.log',
    'build/frame_store_sim/tb_ddr_read_arbiter.log','build/frame_store_sim/tb_ddr_result_store.log',
    'results/frame-engine-progress-20261006.json','results/calibration-status-20261006.json']:
    dest=archive/source;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/source,dest)
state=json.loads((root/'status.json').read_text(encoding='utf-8-sig'))
state['remap_frame_engine']=result;state['real_camera_calibration']=calibration
state['verification'].update(remap_full_frame_simulation_passed=True,
    corrected_result_store_and_burst_arbitration_simulation_passed=True)
state['brown_remap_core']['real_calibration_candidates_available']=True
state['next_hardware_requirement']='Integrate remap frame engine, source/result/display ownership and DDR arbiters into actual board; complete edge calibration coverage.'
(root/'status.json').write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
report=f'''{result['recorded_at']} 标定候选审核与整帧矫正通路仿真

真实数据：首轮 25 帧通过传输校验，加此前试拍共 26 张；筛选 20 个不同姿态，16 拟合、4 留出验证。用户确认 20mm 方格。
候选：Brown/fisheye 留出平均角点误差 0.2078/0.2132 像素；只说明当前已覆盖区域的验证。
覆盖：下方三个区域没有角点，左侧覆盖不足。Brown 外推全图有 9245 像素出现局部映射折返；fisheye 没有折返，但边缘精度仍未验证。不将首轮参数写进板卡。
新增：读/写 DDR 完整突发仲裁；RGB888 插值结果量化为 RGB565、有序写回结果帧；整帧坐标生成、参数锁定和完成后发布。
验证：整帧通路三个 32×16 合成帧，1536 像素逐项匹配独立整数模型及 zlib CRC32；恒等、非线性、同一源缓存更新、并发显示读请求、暂停和复位恢复。
结果存储另有 1536 个随机/极值 RGB888 输入，独立核对打包及 CRC32；写入同时存在摄像头突发；读仲裁覆盖 1/2/8/16 个块。
故障隔离：非法像素顺序、RLAST/RID、超时、无主响应、源/结果缓存重叠、地址未对齐等失败不发布半帧。
边界：新增整帧模块尚未接入实际板卡 PHY/HDMI，未做新整板时序验证，不能报告矫正实测或帧率。板上仍是已验证的 calibration_capture，DDR/JTAG 保持 125MHz/5MHz。
下一步：实板帧所有权与新通路集成；用户返回后补采边缘，重新审核标定模型。不要重复已经通过的外设入门测试。
证据：distortion/results/frame-engine-progress-20261006.json；results/calibration-status-20261006.json；results/verified/frame-engine-20261006。

以下保留此前过程记录，以最新状态为准：
----------------------------------------
'''
p=root/'results/progress-2026-10-06.txt';previous=p.read_text(encoding='utf-8-sig')
if '标定候选审核与整帧矫正通路仿真' not in previous.split('\n',1)[0]:p.write_text(report+previous,encoding='utf-8')
print(json.dumps({'frame_engine_simulation_verified':True,'hardware_integrated':False,
    'real_selected_views':audit['selected_views'],'final_calibration_parameters_available':False},indent=2))
