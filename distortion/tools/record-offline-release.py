"""Create a verified offline release and finite lab handoff; no board access."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib,json,re,shutil
root=Path(__file__).resolve().parents[1]
now=datetime.now(ZoneInfo('Asia/Shanghai'));tag=now.strftime('%Y%m%d-%H%M%S')
archive=root/'results/verified'/('offline-release-'+tag);archive.mkdir(parents=True)
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest().upper()
def copy(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);assert sha(src)==sha(dst)
builds={}
for target in ('corrected_fast','corrected_rotate'):
    build=root/'build'/target;manifest_path=build/'validated-build.json';manifest=read(manifest_path)
    bit=Path(manifest['Bitstream']);report=Path(manifest['TimingReport'])
    assert sha(bit)==manifest['SHA256'] and sha(report)==manifest['TimingSHA256']
    text=report.read_text();assert 'Design Summary : All Constraints Met.' in text
    pins=read(root/'board'/(target+'-pins.json'))
    routed=(build/'place_route'/(target+'_prr.prt')).read_text()
    for port,pin in pins.items():assert re.search(r'^'+re.escape(pin)+r'\|[^\r\n]*\|'+re.escape(port)+r'\|',routed,re.M)
    timing={}
    for marker in ('Setup Summary(Slow Corner):','Hold Summary(Fast Corner):'):
        section=text.split(marker,1)[1].split('===',1)[0]
        clocks=re.findall(r'^\s*(\w+)\s+(\w+)\s+(-?\d+\.\d+)\s+',section,re.M)
        assert clocks and min(float(r[2]) for r in clocks)>=0
        timing[marker]={'minimum_slack_ns':min(float(r[2]) for r in clocks),'clock_pairs':{a+' -> '+b:float(v) for a,b,v in clocks}}
    resources=(build/'multiseed_summary.csv').read_text().split('Device Map Resource Usage Summary:',1)[1].split('Device Map Process',1)[0].strip()
    for rel,digest in manifest['SourceSHA256'].items():
        src=root/rel;assert sha(src)==digest;copy(src,archive/'source'/rel)
    copy(root/'board'/(target+'-sources.json'),archive/'source/board'/(target+'-sources.json'))
    kit=root/'results/ready-for-lab'/('20261006-'+target.replace('_','-'));kit.mkdir(parents=True,exist_ok=True)
    files={}
    for src in (bit,report,manifest_path,root/'board'/(target+'-pins.json')):
        copy(src,kit/src.name);copy(src,archive/target/src.name);files[src.name]=sha(src)
    for name in ('build.log','multiseed_summary.csv'):
        copy(build/name,archive/target/name)
    if target=='corrected_fast':
        for name in ('build-parse-error-preserved.log','repair-final.tcl'):copy(build/name,archive/target/name)
    handoff={'recorded_at':now.isoformat(),'target':target,'hardware_accessed':False,'downloaded':False,
        'device':'PG2L100H-6IFBG676','ddr_mhz':125,'jtag_mhz':5,'files':files,'timing':timing,
        'verified_pins':len(pins),'resource_usage_csv':resources,'bitstream_sha256':manifest['SHA256'],
        'preflight':'powershell -NoProfile -ExecutionPolicy Bypass -File tools/program-heartbeat.ps1 -Target '+target+' -ValidateOnly',
        'scope':'Native 640x480 calibrated bounded radial approximation, arithmetic coordinates, one bilinear interpolation. Final optical accuracy/high-resolution throughput unproven.',
        'features':'adjacent-neighbour same-beat cache reuse'+('; CORDIC full-circle rotation, KEY0 30-degree steps and long-press demo, ADC temperature telemetry' if target=='corrected_rotate' else '')}
    (kit/'handoff.json').write_text(json.dumps(handoff,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    builds[target]=handoff
checks={
    'native_rotation':('rotated_native_sim','PASS rotated native regression:'),
    'composed_domain_and_faults':('rotated_query_sim','PASS composed rotation'),
    'three_clock_video':('rotated_video_sim','PASS rotated DDR video:'),
    'rotation_control':('rotation_control_sim','PASS rotation control:'),
    'cordic_full_circle':('cordic_sim','PASS'),
    'temperature_adapter':('adc_reader_sim','PASS ADC readback'),
    'temperature_wrapper_digital_stub':('temperature_monitor_sim','PASS temperature wrapper')}
for name,(folder,signature) in checks.items():
    src=root/'build'/folder/'simulation.log';log=src.read_text()
    assert signature in log and 'Fatal:' not in log
    copy(src,archive/'simulation'/folder/'simulation.log')
    for file in ('reference.json','cycles.csv'):
        src=root/'build'/folder/file
        if src.exists():copy(src,archive/'simulation'/folder/file)
for folder in ('rtl','tests','model','tools'):
    for src in (root/folder).rglob('*'):
        if src.is_file() and src.suffix in ('.v','.vh','.sv','.py','.ps1','.json','.tcl') and '__pycache__' not in src.parts:
            copy(src,archive/'source'/src.relative_to(root))
for src in (root/'platform/video_base/ipcore/ddr3_test').rglob('*'):
    if src.is_file() and src.suffix in ('.v','.vp','.sdc','.fdc','.idf'):
        copy(src,archive/'source'/src.relative_to(root))
evidence_names=('cache-native-regression-20261006.json','rotated-native-regression-20261006.json',
    'rotation-domain-20261006.json','cache-locality-study-20261006.json','offline-acceptance-gates-20261006.json',
    'corrected-pair-check-20261006.json','rotation-key-evidence-20261006.json','rotation-preview-20261006.png')
for name in evidence_names:copy(root/'results'/name,archive/'results'/name)
for pair in read(root/'results/corrected-pair-check-20261006.json')['pairs']:
    pair_dir=Path(pair['directory'])
    for src in pair_dir.iterdir():
        if src.is_file() and src.suffix in ('.rgb565','.json'):
            copy(src,archive/'captures'/pair_dir.name/src.name)
preserved=root/'build/preserved-corrected_rotate-20261006-231748-002'
for name in ('obsolete-before-alarm-sync.log','cached-netlist-rejected.log'):
    src=preserved/name
    if src.exists():copy(src,archive/'corrected_rotate/diagnostics'/name)
cache=read(root/'results/cache-native-regression-20261006.json');rotation=read(root/'results/rotated-native-regression-20261006.json')
progress={'recorded_at':now.isoformat(),'hardware_accessed':False,'board_available':False,'archive':str(archive),
    'board_builds':builds,'cache_cycle_reduction_percent_in_native_simulation':cache['mean_cycle_reduction_percent'],
    'rotation_regression':rotation,'simulation_checks_passed':list(checks),
    'composed_queries':2322,'masked_domain_or_overflow_queries':1511,
    'adc_reader_protocol_verified':True,'actual_temperature_measured':False,
    'remaining_lab_checks':['冷却、散热片和通风；取得内部 ADC 温度。若有红外、热像仪或温度探头则交叉核对，否则标记未外部校准。',
        '先以 5MHz 下载 corrected_fast 做短时连续矫正 HDMI/UART 对比，再下载 corrected_rotate。',
        'KEY0 短按切换角度、长按自动演示；核对画面方向、边缘黑区、帧切换和角度状态。',
        '采集不少于 12 秒 UART，核对新增帧率 CF、HDMI 刷新 PF、处理周期 CY、错误计数和新鲜温度。',
        '记录真实性能，再决定是否引入 8×8 分块与重排缓存；随后推进高分辨率和最终光学精度验证。'],
    'unverified':['本轮新位流未实板下载','连续矫正和旋转画面的真实新帧率、延迟、温度、长时间稳定性','1080p 或 60fps','最终光学标定质量'],
    'cache_locality_study':'Address trace suggests 8x8 traversal plus 16-line cache reduces +30/+90 burst counts by 86.5/86.8%; requires reorder buffer, not integrated and not measured FPS.'}
out=root/'results/offline-development-20261006.json';out.write_text(json.dumps(progress,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
status_path=root/'status.json';status=read(status_path);status['offline_development']=progress
status['current_sram_target']=None;status['current_connection']['available_for_testing']=False
status['current_connection']['session_state']='offline_no_board_user_confirmed'
status['offline_release']=str(archive)
status_path.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
thermal=read(root/'results/temperature-monitor-plan-20261006.json')
thermal.update({'actual_temperature_measured':False,'integrated_target':'corrected_rotate','adapter_simulation_passed':True,
    'temperature_word_extraction':'0x40 status word bits[15:4], visually verified against official register Fig16',
    'configuration':'Internal reference, temperature-only continuous scan, offset calibration, 64-sample average, oscillator divide34, temperature alarm and default OT alarm enabled with synchronized status; startup settle and first two conversion indications discarded.',
    'limits':'Analog behavior, absolute temperature accuracy and alarm behavior require lab verification. Internal-reference ADC readings are approximate until cross-checked; over_temp alone gives no numeric temperature.'})
(root/'results/temperature-monitor-plan-20261006.json').write_text(json.dumps(thermal,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
plan_path=root/'results/offline-plan-20261006.json';plan=read(plan_path)
for item in plan['offline_priorities']:item['current_state']='本轮离线实现、独立回归和板级构建已完成；详见最新检查点。'
plan['latest_progress']=str(out);plan['next_lab_sequence']=progress['remaining_lab_checks']
plan_path.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
note=f'''## 最新离线检查点（{now.isoformat()}）

本轮未连接开发板。缓存优化版 corrected_fast 与旋转/测温版 corrected_rotate 均保留 DDR 125MHz，最终路由数据库慢角建立、快角保持全部约束通过，分别核对128/129引脚，位流/时序/源码哈希已封存。新位流尚未实板下载。

原生640×480的六角度完整帧回归通过，共1,843,200像素；复用已采集真实原图，独立整数参考逐像素及CRC一致。2,322条组合查询包括1,511条标定域/溢出黑色处理，通过暂停、异常DDR响应和复位检查。三时钟视频集成、KEY0控制、全圆CORDIC和ADC读回协议仿真均通过。

缓存同拍邻居复用使零旋转真实图回归的处理周期下降{cache['mean_cycle_reduction_percent']:.2f}%。+30°约50.17ms，+90°约68.97ms，是125MHz和合成DDR暂停下的帧引擎周期，不能代替实板帧率。地址轨迹进一步表明单纯扩大缓存无改善，8×8分块与16行缓存可显著减少突发；重排缓冲尚未实现，须先测真实性能。

KEY0短按步进30°，长按约1秒开关每3秒步进的自动演示。串口RA为已完成结果的Q32圈相位，AU为自动模式，TV为温度有效，TR为0x40原始字，TF为读回故障，TA为27MHz样本年龄，AL高位为valid/failed/over_temp及5位报警。code12=TR>>4，近似温度=code12×0.1219−273.15℃；需在实验室与外部仪器核对。

证据：{archive}
复测包：results/ready-for-lab/20261006-corrected-fast 与 20261006-corrected-rotate。
复测步骤：results/lab-handoff-20261006.txt；详细数据：results/offline-development-20261006.json。
仍须验证真实连续画面、温度、角度操作、有效新帧率、延迟、稳定性、高分辨率和最终光学精度。
'''
readme_path=root/'README.md';text=readme_path.read_text(encoding='utf-8')
start='<!-- CURRENT_OFFLINE_RELEASE_BEGIN -->';end='<!-- CURRENT_OFFLINE_RELEASE_END -->'
block=start+'\n'+note+'\n'+end
if start in text:text=re.sub(re.escape(start)+'.*?'+re.escape(end),lambda _:block,text,flags=re.S)
else:text=text.replace('## 已完成与边界（此前阶段记录）',block+'\n\n## 已完成与边界（此前阶段记录）',1)
readme_path.write_text(text,encoding='utf-8')
(root/'results/progress-2026-10-06.txt').open('a',encoding='utf-8').write('\n'+note)
lab='''下次实验室复测（本文件不执行硬件操作）

1. 断电做好散热和通风。保持摄像头J2、3.3V选择、HDMI OUT与UART接法；先冷却再短时测试。
2. 在 D:/English/FPGA/distortion 执行离线校验：
   powershell -NoProfile -ExecutionPolicy Bypass -File tools/program-heartbeat.ps1 -Target corrected_fast -ValidateOnly
3. 开发板连接后，由当次实验室会话明确开始下载：
   powershell -NoProfile -ExecutionPolicy Bypass -File tools/program-heartbeat.ps1 -Target corrected_fast -Frequency 5MHz
   powershell -NoProfile -ExecutionPolicy Bypass -File tools/read-telemetry.ps1 -Target corrected_fast -Seconds 16
   查看矫正实时画面和WF/CF/PF、UF/MF/OW/X；先与原版比较，PF包括重复显示，CF才是新增处理帧。
4. 旋转/测温版：
   powershell -NoProfile -ExecutionPolicy Bypass -File tools/program-heartbeat.ps1 -Target corrected_rotate -ValidateOnly
   powershell -NoProfile -ExecutionPolicy Bypass -File tools/program-heartbeat.ps1 -Target corrected_rotate -Frequency 5MHz
   按KEY0：短按30°，长按约1秒开启/关闭自动演示，每3秒换角度。
   powershell -NoProfile -ExecutionPolicy Bypass -File tools/read-telemetry.ps1 -Target corrected_rotate -Seconds 16
   python tools/analyze-rotation-telemetry.py build/corrected_rotate/telemetry-timed.json --output results/rotated-video-lab-check.json
5. 先确认TV=1、TF=0、TA小于54000000；TR高12位近似转换温度。若有红外仪、热像仪或温度探头则交叉核对；没有则标记未外部校准。内部参考ADC未经实测校准，85℃是本验收工具可调整的诊断上限，不是芯片额定温度结论。TV=0/TF非零不能当作正常温度；过热先断电处理。
6. 核对每个角度、黑色边界、帧切换、按键复位/重新上电，记录新增处理帧率与实际可见延迟。光学质量另用中心/边缘棋盘数据评估。

以上命令只有在开发板重新连接、实验室会话开始后执行。本次发布已通过离线检查，仍未实板验证旋转与温度。
'''
(root/'results/lab-handoff-20261006.txt').write_text(lab,encoding='utf-8')
copy(out,archive/'results'/out.name);copy(root/'results/lab-handoff-20261006.txt',archive/'results/lab-handoff-20261006.txt')
files={str(p.relative_to(archive)):sha(p) for p in archive.rglob('*') if p.is_file()}
(archive/'archive-files-sha256.json').write_text(json.dumps(files,indent=2)+'\n')
print(json.dumps({'archive':str(archive),'targets':list(builds),'hardware_accessed':False}))
