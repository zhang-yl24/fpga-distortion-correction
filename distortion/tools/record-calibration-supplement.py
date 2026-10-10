"""Record real calibration, bounded approximation and RTL checks separately."""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import shutil
import zlib

root=Path(__file__).resolve().parents[1]
def read(path):return json.loads((root/path).read_text(encoding='utf-8-sig'))
selection=read('captures/calibration-selected-20261006-quality/selection.json')
models=read('results/calibration-output-camera-20261006.json');model=models['candidates']['fisheye2']
candidate=read('results/calibration-fpga-candidate-20261006/candidate.json')
assert model['matched_output_K_trial_eligible'] and candidate['passed']
sim_path=root/'build/calibrated_mapper_sim/simulation.log'
sim=sim_path.read_text(errors='replace');assert 'PASS real-calibration mapper: 307200' in sim
captures=[]
for name in ('calibration-capture-supplement-20261006.json','calibration-capture-tilt-20261006.json'):
    capture=read('results/'+name)
    assert capture['rejected_packets']==0 and len(capture['frames'])==capture['saved_frames']
    for frame in capture['frames']:
        payload=Path(frame['raw']).read_bytes()
        assert len(payload)==614400 and f'{zlib.crc32(payload):08X}'==frame['source_crc32']==frame['received_crc32']
    captures.append({'summary':'distortion/results/'+name,'saved_frames':capture['saved_frames'],
        'complete_chessboards':sum(f['chessboard_detected'] for f in capture['frames']),
        'rejected_packets':capture['rejected_packets']})
frame_hashes={name:hashlib.sha256(Path(name).read_bytes()).hexdigest().upper() for name in selection['selected']}
result={'recorded_at':datetime.now().isoformat(timespec='seconds'),'date':'2026-10-06',
    'real_images_available':True,'selected_views':len(selection['selected']),
    'native_source_frames':len(list((root/'captures/calibration').glob('*.png'))),
    'supplement_capture_sessions':captures,'square_mm':20,'five_squares_measured_mm_user_confirmed':100,
    'corner_counts_by_3x3_region':models['corner_counts_by_3x3_region'],
    'all_nine_regions_observed':True,'accepted_final_parameters_available':False,
    'initial_distortion_only_trial_parameters_available':True,
    'calibrated_model':'fisheye2; k3 and k4 fixed at zero',
    'output_camera_policy':'output_K equals source_K, no rotation',
    'view_wise_cross_validation_mean_px':model['view_wise_cross_validation_mean_px'],
    'view_wise_cross_validation_max_px':model['view_wise_cross_validation_max_px'],
    'matched_output_K_between_fold_map_sd_p95_px':model['matched_output_K_map_sd_95th_percentile_px'],
    'fixed_output_K_between_fold_map_sd_p95_px':model['map_sd_95th_percentile_px'],
    'fixed_output_K_trial_eligible':model['eligible_for_first_hardware_comparison'],
    'output_camera_choice_audit':'distortion/results/calibration-output-camera-20261006.json',
    'model_order_comparison':'distortion/results/calibration-stability-20261006-model-order.json',
    'quality_selection':'distortion/captures/calibration-selected-20261006-quality/selection.json',
    'sharpness_quality_report':'distortion/results/calibration-sharpness-20261006-tilt.json',
    'quality_rejected_frames':1,'quality_rejection_note':'Independent black/white edge-width criterion; original image kept. No residual-based deletion.',
    'hardware_candidate':'distortion/results/calibration-fpga-candidate-20261006/candidate.json',
    'hardware_coordinate_model':candidate['hardware_coordinate_model'],
    'coordinate_error_metrics':candidate['coordinate_error_metrics'],
    'actual_calibration_rtl_coordinates_verified':307200,'rtl_simulation_passed':True,
    'new_correction_hardware_programmed':False,
    'selected_image_sha256':frame_hashes,
    'limits':'Cross-validation of captured board corners and coordinate error against the fitted model. No measured FPGA corrected image/FPS/latency. Polynomial is bounded to current 640x480 matched-K view; exact fisheye/rotation remains unimplemented.'}
(root/'results/calibration-status-20261006.json').write_text(json.dumps(result,indent=2)+'\n')
archive=root/'results/verified/calibration-trial-20261006'
paths=['results/calibration-status-20261006.json','results/calibration-capture-supplement-20261006.json',
    'results/calibration-capture-tilt-20261006.json','results/calibration-comparison-20261006-quality.json',
    'results/calibration-stability-20261006-quality.json','results/calibration-stability-20261006-model-order.json',
    'results/calibration-output-camera-20261006.json','results/calibration-sharpness-20261006-tilt.json',
    'results/calibration-fpga-candidate-20261006/candidate.json',
    'results/calibration-fpga-candidate-20261006/coordinates-q8.bin',
    'results/calibration-fpga-candidate-20261006/calibration-candidate.vh',
    'build/calibrated_mapper_sim/simulation.log','build/calibrated_mapper_sim/configs.mem',
    'build/calibrated_mapper_sim/counts.vh','tests/tb_calibrated_mapper.sv','tests/test_chessboard_sharpness.py',
    'tools/check-calibration-stability.py','tools/check-chessboard-sharpness.py',
    'tools/filter-calibration-quality.py','tools/audit-output-camera-choice.py','tools/export-fisheye-surrogate.py',
    'tools/prepare-calibrated-mapper-test.py','tools/run-calibrated-mapper-sim.ps1','tools/preview-calibrated-reference.py',
    'captures/calibration-selected-20261006-quality/selection.json']
for path in paths:
    dest=archive/path;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/path,dest)
state=read('status.json');state['real_camera_calibration']=result
state['verification'].update(real_parameter_native_coordinates_rtl_verified=307200,
    calibration_quality_gate_synthetic_tests_passed=3)
state['brown_remap_core'].update(real_calibration_available=True,
    real_calibration_candidates_available=True,real_calibration_candidate=result['hardware_candidate'],
    real_parameter_coordinates_rtl_verified=307200)
state['next_hardware_requirement']='Integrate source/result/display bank ownership and DDR arbiters with the staged matched-K polynomial; compare real FPGA output against integer software reference before performance optimization.'
state['not_yet_implemented']=[s.replace('FPGA fisheye and output rotation coordinate paths','exact fisheye and output rotation FPGA coordinate paths') for s in state['not_yet_implemented']]
(root/'status.json').write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
e=candidate['coordinate_error_metrics']
report=f'''{result['recorded_at']} 标定补采完成与真实参数 RTL 验证

本轮新增左侧/下方 20 帧、倾斜 14 帧，全部 614400 字节完整包源/读出/主机 CRC32 一致；原始采集目录共 60 帧。
筛选：44 个完整且不同的姿态，其中 1 帧按独立棋盘边缘清晰度判据剔除，保留 43 帧。原始模糊帧保留，未按标定残差删图。噪声、光学散焦及低对比度的质量判据测试通过。
覆盖：九个区域均有角点，计数 {models['corner_counts_by_3x3_region']}；20mm 方格，用户五格实测 100mm。
模型：常规 Brown/fisheye 高阶参数的外推敏感；同一批数据比较简化 Brown 与两项 fisheye。两项 fisheye 在匹配输出 K、不旋转的视图中通过首版试验门槛。
交叉验证：按整幅图像分五折，每个图像都曾作为验证图，平均角点误差 {model['view_wise_cross_validation_mean_px']:.4f}px，最差 {model['view_wise_cross_validation_max_px']:.4f}px。
敏感性：匹配源/输出 K 的映射变化 95 分位 {model['matched_output_K_map_sd_95th_percentile_px']:.4f}px；固定独立虚拟相机时仍为 {model['map_sd_95th_percentile_px']:.4f}px，未满足原门槛。不能据此批准旋转或固定虚拟视图，也不能称作误差置信区间。
接入参数：为现有坐标流水线拟合三项 Brown 径向多项式近似，不使用映射表替代计算。只覆盖当前 640×480、源/输出 K 匹配、无旋转视场；不是通用精确 fisheye。
逐坐标核对：307200 个点全部有效；相对拟合 fisheye 模型最大误差 {e['integer_mapper_max_coordinate_error_px']:.6f}px，RMS {e['integer_mapper_rms_coordinate_error_px']:.6f}px，95 分位 {e['integer_mapper_95th_percentile_coordinate_error_px']:.6f}px。独立解析鱼眼公式与 OpenCV map 核对。
RTL：使用真实分阶段参数的 307200 个原生画面坐标、暂停、标签和复位恢复仿真通过。此处是坐标算法的 RTL 证据，不是实板输出或镜头绝对精度。
当前板上仍是 calibration_capture；DDR 125MHz、JTAG 5MHz 没有调整。矫正候选尚未生成/下载新整板位流。
下一步：摄像头源帧/处理结果/显示帧所有权和 DDR 仲裁接入；软件整数参考与 FPGA 同一帧逐像素核对，再做帧率和延迟优化。这轮不再扩展采集。
证据：distortion/results/calibration-status-20261006.json；results/calibration-fpga-candidate-20261006；results/verified/calibration-trial-20261006。

以下保留此前过程记录，以最新状态为准：
----------------------------------------
'''
p=root/'results/progress-2026-10-06.txt';previous=p.read_text(encoding='utf-8-sig')
if '标定补采完成与真实参数 RTL 验证' not in previous.split('\n',1)[0]:p.write_text(report+previous,encoding='utf-8')
print(json.dumps({k:result[k] for k in ('selected_views','native_source_frames','view_wise_cross_validation_mean_px',
    'actual_calibration_rtl_coordinates_verified','initial_distortion_only_trial_parameters_available',
    'new_correction_hardware_programmed')},indent=2))
