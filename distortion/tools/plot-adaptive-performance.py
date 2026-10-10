"""Plot measured simulation cycles, explicitly separated from live frame rate."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
root=Path(__file__).resolve().parents[1];lab=root/'results/lab-20261007'
data=json.loads((lab/'adaptive-native-check.json').read_text())
assert data['passed'] and not data['hardware_accessed']
font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
frames=data['frames'];x=list(range(6))
fig,ax=plt.subplots(1,2,figsize=(12,5))
for a in ax:
    a.spines[['top','right']].set_visible(False)
    a.tick_params(colors='black')
baseline=[r['baseline_cycles']/125000 for r in frames]
new=[r['adaptive_cycles']/125000 for r in frames]
ax[0].bar([v-.19 for v in x],baseline,width=.38,color='#b6cad8',label='原逐行路径')
ax[0].bar([v+.19 for v in x],new,width=.38,color='#704acc',label='自适应分块')
ax[0].set_xticks(x,[f"{r['angle_deg']}°" for r in frames])
ax[0].set_ylim(0,85);ax[0].set_ylabel('仿真处理周期折合毫秒（125 MHz）',fontproperties=font)
ax[0].set_title('完整帧处理时间',fontproperties=font)
ax[0].legend(prop=font,frameon=False)
for i,r in enumerate(frames):ax[0].text(i,max(baseline[i],new[i])+2,f"{r['process_cycle_reduction_percent']:.1f}%",ha='center',fontsize=9,color='black')
ax[1].bar([v-.19 for v in x],[r['baseline_read_bursts']/1000 for r in frames],width=.38,color='#b6cad8')
ax[1].bar([v+.19 for v in x],[r['adaptive_read_bursts']/1000 for r in frames],width=.38,color='#704acc')
ax[1].set_xticks(x,[f"{r['angle_deg']}°" for r in frames]);ax[1].set_ylim(0,275)
ax[1].set_ylabel('每帧源图读取突发（千次）',fontproperties=font)
ax[1].set_title('DDR 源图读取次数',fontproperties=font)
for i,r in enumerate(frames):ax[1].text(i,r['baseline_read_bursts']/1000+8,f"{r['read_burst_reduction_percent']:.1f}%",ha='center',fontsize=9,color='black')
fig.suptitle('640×480 · 六角度共 1,843,200 像素与 CRC 一致',fontproperties=font,fontsize=15,color='black')
fig.text(.5,.04,'以上为真实原图、合成 DDR 暂停条件下的仿真；柱上标注为减少比例。实板新增帧率另行测量。',ha='center',fontproperties=font,fontsize=10,color='black')
fig.tight_layout(rect=[0,.08,1,.93]);out=lab/'adaptive-simulation-performance.png';fig.savefig(out,dpi=160);plt.close(fig)
print(str(out))
