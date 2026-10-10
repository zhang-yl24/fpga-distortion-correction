"""Record a standalone core milestone only after simulations and routed timing.

This never programs hardware or promotes the synthetic test shell to a board build.
"""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import re
import shutil

root=Path(__file__).resolve().parents[1]
work=root/'build/brown_remap_probe'
timing_path=work/'place_route/brown_remap_synthesis_top_timing_summary_after_hold_fix.txt'
timing=timing_path.read_text()
all_met='All Constraints Met' in timing
sources=['rtl/mul32_pipe.v','rtl/brown_inverse_mapper.v','rtl/ddr_neighbour_cache.v',
         'rtl/ddr_remap_sample.v','rtl/brown_remap_core.v','rtl/bilinear_rgb.v',
         'board/brown_remap_synthesis_top.v','board/brown-remap-probe.fdc']
assert timing_path.stat().st_mtime>=max((root/s).stat().st_mtime for s in sources)
logs={}
for target in ('mul32_sim','brown_sim','brown_remap_sim'):
    path=root/f'build/{target}/simulation.log';log=path.read_text()
    assert re.search(r'^PASS ',log,re.M) and not re.search(r'fatal:|error:',log,re.I),target
    logs[target]=re.findall(r'^PASS .*',log,re.M)[-1]
slow=timing.split('Setup Summary(Slow Corner):',1)[1].split('Hold Summary',1)[0]
wns=float(re.search(r'core_clk\s+core_clk\s+(-?\d+\.\d+)',slow)[1])
detail=(work/'report_timing/brown_remap_synthesis_top.rtr').read_text()
paths=[]
for chunk in re.split(r'Startpoint\s*:',detail)[1:]:
    endpoint=re.search(r'Endpoint\s*:\s*(.*)',chunk)
    slack=re.search(r'Slack \((MET|VIOLATED)\)\s+(-?\d+\.\d+)',chunk)
    path_type=re.search(r'Path Type\s*:\s*(.*)',chunk)
    if endpoint and slack and path_type and path_type[1].strip()=='max (slow corner)':
        paths.append((chunk.splitlines()[0].strip(),endpoint[1].strip(),float(slack[2])))
internal_slacks=[s for a,b,s in paths if a.startswith('core/') and b.startswith('core/')]
assert internal_slacks and min(internal_slacks)>0, 'Internal core has not met timing'
if not all_met:
    # Preserve an external synthetic-shell failure as a failure; do not mask it
    # or call this an all-constraints pass. The actual board has separate I/O.
    rows=re.findall(r'core_clk\s+core_clk\s+(-?\d+\.\d+)\s+(-?\d+\.\d+)\s+(\d+)\s+(\d+)',timing)
    assert int(rows[0][2])==1 and all(int(r[2])==0 for r in rows[1:])
    failing=[(a,b,s) for a,b,s in paths if s<0]
    assert len(failing)==1 and failing[0][1]=='serial_out (port)',failing
mapping=(work/'build.log').read_text(errors='replace')
resources={name:int(float(re.search(pattern,mapping)[1])) for name,pattern in {
    'LUT':r'Total LUTs:\s+(\d+)','FF':r'Total Registers:\s+(\d+)',
    'DRM':r'Total DRM =\s+([\d.]+)','APM':r'Total APMs =\s+([\d.]+)'}.items()}
stamp=datetime.now().isoformat(timespec='seconds')
result={'recorded_at':stamp,'device':'PG2L100H-6IFBG676',
    'core_clock_mhz':125,'standalone_all_constraints_met':all_met,'standalone_setup_wns_ns':wns,
    'standalone_internal_paths_meet_timing':True,'standalone_internal_setup_wns_ns':min(internal_slacks),
    'test_shell_external_output_constraint_passed':all_met,
    'standalone_resources_including_serial_test_shell':resources,
    'coordinate_pipeline_enabled_stages':30,'coordinate_pipeline_accepts_one_ray_per_cycle_when_ready':True,
    'coordinate_vectors_passed':81036,'composed_pixel_queries_passed':19086,
    'exact_multiplier_products_passed':18873,'simulation_results':logs,
    'model':'Brown-Conrady radial/tangential, synthetic test parameters',
    'pixel_format':'source RGB565 expanded by bit replication to RGB888',
    'coordinates':'Q15.8 pixels and focal lengths, Q1.30 inverse focal, Q9.22 rays/coefficients',
    'cache':{'lines':8,'line_bytes':512,'ddr_beats_per_fill':16,'ddr_address_unit_bytes':4,
             'four_neighbours':True,'independent_border_zero':True},
    'hardware_integrated':False,'hardware_programmed':False,'real_calibration_available':False,
    'source_sha256':{s:hashlib.sha256((root/s).read_bytes()).hexdigest().upper() for s in sources},
    'limits':'Standalone synthetic test shell only; actual DDR PHY/capture/HDMI integration timing and board correction remain unverified. No fisheye/rotation FPGA datapath. One ray/cycle describes coordinate arithmetic, not the serial DDR sampler or full-frame FPS.',
    'next':'Connect an output frame store and burst-owner read/write arbiters; export real camera frames, calibrate and compare held-out Brown/fisheye error.'}
(root/'results/brown-remap-core-20261006.json').write_text(json.dumps(result,indent=2)+'\n')
archive=root/'results/verified/brown-remap-core-20261006';archive.mkdir(parents=True,exist_ok=True)
for s in sources:
    dest=archive/s;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(root/s,dest)
shutil.copy2(timing_path,archive/'timing-summary.txt')
shutil.copy2(work/'report_timing/brown_remap_synthesis_top.rtr',archive/'timing-detail.rtr')
for target in logs:shutil.copy2(root/f'build/{target}/simulation.log',archive/f'{target}.log')
shutil.copy2(root/'results/brown-remap-core-20261006.json',archive/'manifest.json')
state=json.loads((root/'status.json').read_text(encoding='utf-8-sig'))
state['brown_remap_core']=result
state['verification'].update(brown_coordinate_vectors_passed=81036,brown_ddr_bilinear_queries_passed=19086,
    signed_mul32_full_range_products_passed=18873,brown_remap_standalone_125mhz_all_constraints_met=all_met,
    brown_remap_standalone_internal_paths_125mhz_passed=True)
state['not_yet_implemented']=[x for x in state['not_yet_implemented'] if x not in (
    'FPGA coordinate computation','arbitrary-neighbour DDR reader and cache')]
for missing in ('FPGA fisheye and output rotation coordinate paths','calibration-frame export from the actual OV5640 source'):
    if missing not in state['not_yet_implemented']:state['not_yet_implemented'].append(missing)
state['next_hardware_requirement']=result['next']
(root/'status.json').write_text(json.dumps(state,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
timing_note=(f'独立测试外壳快慢角全部约束通过，慢角建立 WNS={wns:.3f} ns。' if all_met else
             f'核心内部路径通过，内部最差建立余量约 {min(internal_slacks):.3f} ns；测试外壳 serial_out 外部输出仍超限 {abs(wns):.3f} ns，不能报告全部约束通过。')
report=f'''{stamp} 畸变矫正核心独立验证记录

新增 Brown 径向/切向逆坐标计算：30 段暂停一致的流水线，不使用映射表代替计算；正常接收能力每周期一个坐标。
新增四邻域 DDR 随机读取：8 条 512 字节缓存、逐邻域越界补黑、帧交接失效缓存、突发超时与协议错误隔离；接入 RGB888 双线性插值。
仿真：81,036 组坐标、19,086 组组合像素逐项匹配独立 Python 参考；18,873 组全范围有符号乘法与暂停测试通过。
时序：实际 PG2L100H-6IFBG676 器件布局布线，125 MHz；{timing_note}
改进：控制信号扇出限制、核心域复位同步释放、32×32 乘法拆为三段部分积流水线；测试外壳的输出寄存器打包进 IO 单元。时钟仍为 125 MHz，未用降频或屏蔽内部路径规避。
独立核心连测试外壳资源：FF={resources['FF']}、LUT={resources['LUT']}、APM={resources['APM']}、DRM={resources['DRM']}；不能与现有整板资源直接相加作为最终整板结果。
边界：本版没有生成/下载板卡位流，显示器运行的仍是用户确认正常的 live_video。组合仿真通过不代表真实镜头已校正；参数仍为合成测试值，FPGA fisheye/旋转尚未实现。
性能：每周期一个坐标只描述数学流水线，DDR 采样仍逐邻域串行。地址轨迹估计不能作为实测帧率或带宽。
标定板：已生成 A4 横向 9×6 内角点、10×7 方格、20mm 方格的 PDF；实际尺寸/100% 打印，平整固定，五格量出 100mm。渲染图通过 54 角点检测。
下一步：读写突发仲裁与处理结果双缓冲、核心接入；从真实 OV5640 导出棋盘帧并比较 Brown/fisheye 独立验证误差。
证据：distortion/results/brown-remap-core-20261006.json；results/verified/brown-remap-core-20261006。

以下保留此前过程记录，以最新状态为准：
----------------------------------------
'''
p=root/'results/progress-2026-10-06.txt';previous=p.read_text(encoding='utf-8-sig')
if '畸变矫正核心独立验证记录' in previous.split('\n',1)[0]:
    previous=previous.split('以下保留此前过程记录，以最新状态为准：\n----------------------------------------\n',1)[1].lstrip('\n')
p.write_text(report+previous,encoding='utf-8')
print(json.dumps({'recorded':True,'core_clock_mhz':125,'all_constraints_met':all_met,'setup_wns_ns':wns,'internal_setup_wns_ns':min(internal_slacks),'resources':resources,'hardware_integrated':False},indent=2))
