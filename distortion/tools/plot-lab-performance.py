"""Plot measured processing cycles separately from host-timed new-frame rate."""
from pathlib import Path
import json,re,statistics,csv
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
root=Path(__file__).resolve().parents[1];lab=root/'results/lab-20261007'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
font=FontProperties(fname='C:/Windows/Fonts/msyh.ttc')
plt.rcParams.update({'text.color':'black','axes.labelcolor':'black','xtick.color':'black','ytick.color':'black','font.size':10})
capture=read(lab/'rotation-stability-telemetry-timed.json')
groups={}
for item in capture['Samples']:
    f={k:int(v,16) for k,v in re.findall(r'\b(\w+)=([0-9A-F]+)\b',item['Line'])}
    groups.setdefault(round(f['RA']*360/(1<<32))%360,[]).append(f['CY']/125000)
angles=sorted(groups);med=[statistics.median(groups[a]) for a in angles]
low=[m-min(groups[a]) for a,m in zip(angles,med)];high=[max(groups[a])-m for a,m in zip(angles,med)]
base=read(lab/'corrected-baseline-check.json');fast=read(lab/'corrected-fast-check.json')
fig,ax=plt.subplots(1,2,figsize=(12,5),gridspec_kw={'width_ratios':[1,2.1]})
times=[r['mean_process_cycles']/125000 for r in (base,fast)]
ax[0].bar([0,1],times,color=['#6046a5','#2684ba'],width=.55)
ax[0].set_xticks([0,1],['原版','缓存优化版'],fontproperties=font)
ax[0].set_ylim(0,55);ax[0].set_ylabel('每帧处理时间（毫秒）',fontproperties=font)
ax[0].set_title('零角度：真实 FPGA 周期对照',fontproperties=font)
for x,y,r in zip([0,1],times,(base,fast)):
    ax[0].text(x,y+1,f'{y:.2f} ms',ha='center')
    ax[0].text(x,2,f"新增帧约 {r['approx_rates_per_second']['CF']:.2f} fps",ha='center',fontproperties=font,fontsize=9)
ax[1].bar(range(len(angles)),med,color='#2684ba',yerr=[low,high],capsize=2)
ax[1].set_xticks(range(len(angles)),[f'{a}°' for a in angles],rotation=45)
ax[1].set_ylim(0,135);ax[1].set_ylabel('每帧处理时间（毫秒）',fontproperties=font)
ax[1].set_title('自动旋转：各角度实测中位数与范围',fontproperties=font)
for x,y in enumerate(med):ax[1].text(x,y+3,f'{y:.1f}',ha='center',fontsize=8)
for a in ax:a.spines[['top','right']].set_visible(False)
fig.suptitle('640×480 实板性能 · 125 MHz 用户时钟 · 2026-10-07',fontproperties=font,fontsize=16)
fig.text(.5,.035,'数据来自有限串口采样；处理周期不等于端到端帧率。HDMI 约 60 Hz，可重复显示同一结果帧。',ha='center',fontproperties=font,fontsize=10)
fig.tight_layout(rect=[0,.08,1,.92]);fig.savefig(lab/'measured-performance.png',dpi=160);plt.close(fig)
with (lab/'rotation-process-times.csv').open('w',newline='',encoding='utf-8') as out:
    w=csv.writer(out);w.writerow(['angle_deg','samples','minimum_process_ms','median_process_ms','maximum_process_ms'])
    for a in angles:w.writerow([a,len(groups[a]),min(groups[a]),statistics.median(groups[a]),max(groups[a])])
print(str(lab/'measured-performance.png'))
