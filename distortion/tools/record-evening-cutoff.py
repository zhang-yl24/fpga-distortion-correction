"""Save the user-requested midnight hardware cutoff and next-session handoff."""
from pathlib import Path
import json
root=Path(__file__).resolve().parents[1];lab=root/'results/lab-20261007'
path=lab/'next-session.txt';text=path.read_text(encoding='utf-8')
marker='\n今晚断电前补充：'
if marker in text:text=text.split(marker)[0]
text+=marker+'''
两次白纸/台灯测试仅读到恒等模式，压暗未激活；第二轮零角度约18.39新增帧/s、视频错误0且显示正常。不是压暗或强光画质通过。
诊断原图/矫正配对307200像素匹配，但画面为衣服/背景；它不是白纸场景，并使用旧相机时序。
一次P-ON重启后重新下载Gamma，33.375°命令与新增帧获确认，约15.55新增帧/s、视频错误0，用户确认实时画面恢复；未验证Flash自主启动或重复冷启动。
冻结采集原型：同一原图两个旁路统计预热，导出原图/增强前图后复用原图计算增强图；小图3场景9数据包4608像素/CRC通过，组装器9项截断/重复/乱序测试通过。
640×480原生回归仍在运行，部分前缀证据见gamma-frozen-native-partial-check.json；只有xsim最终PASS与独立9包验证后才可记完整回归通过。
板级gamma_capture仅准备隔离候选，未构建/下载，未接入通用硬件脚本；候选使用标定半径边界，需对应参考向量、最终时序/管脚/源码/位流校验。
下次建立新的实验日期目录，保留今晚原始记录。完成native与标定边界捕获回归后再构建gamma_capture，先采同源真实暗场，再做强光。
今晚23:50后不再重载，23:55前收尾；用户计划00:00断电。当前已实际下载heartbeat，尚未独立观测用户最终断电。
'''
path.write_text(text,encoding='utf-8')
policy={'user_power_cutoff':'2026-10-08T00:00:00+08:00','no_new_heavy_tests_after':'2026-10-07T23:50:00+08:00','agent_wrapup_by':'2026-10-07T23:55:00+08:00','actual_user_power_off_observed':False,'next_heavy_test_requires_new_user_hardware_availability':True}
(lab/'evening-cutoff-policy.json').write_text(json.dumps(policy,indent=2)+'\n',encoding='utf-8')
print('Saved cutoff and next-session handoff; no hardware accessed.')
