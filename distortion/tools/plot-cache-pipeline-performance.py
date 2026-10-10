"""Matched native golden frames; explicit simulation-only cycle comparison."""
from pathlib import Path
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parents[1];lab=root/'results/lab-20261007'
specs=[('16拍分块','adaptive-native-check.json','adaptive_cycles'),
       ('8拍成对邻点','paired-cache-native-check.json','paired_cycles'),
       ('8拍命中流水','pipeline-hit-native-check.json','pipeline_cycles')]
versions=[]
for label,name,key in specs:
    path=lab/name;data=json.loads(path.read_text());assert data['passed']
    versions.append((label,data['frames'],key))
angles=[r['angle_deg'] for r in versions[-1][1]]
for _,frames,_ in versions:
    assert [f['angle_deg'] for f in frames]==angles
    assert [f['crc32'].upper() for f in frames]==[f['crc32'].upper() for f in versions[-1][1]]
plt.rcParams.update({'font.family':'Microsoft YaHei','text.color':'black','axes.labelcolor':'black','xtick.color':'black','ytick.color':'black'})
fig,ax=plt.subplots(figsize=(11,5),layout='constrained')
for i,(label,frames,key) in enumerate(versions):
    values=[r[key]/125000 for r in frames]
    ax.bar([j+(i-1)*.25 for j in range(6)],values,width=.23,label=label)
ax.set_xticks(range(6),[f'{a}°' for a in angles]);ax.set_ylabel('仿真处理周期折算时间（ms，125MHz）')
ax.set_title('同一组真实原图与整数参考：缓存架构的仿真对照',fontsize=15)
ax.spines[['top','right']].set_visible(False);ax.legend(frameon=False)
fig.supxlabel('每帧307,200像素及CRC一致，采用合成DDR暂停。命中流水使用额外RAM副本；未证明整板时序、实际帧率或温度。',fontsize=10)
out=lab/'cache-pipeline-simulation.png';fig.savefig(out,dpi=150);plt.close(fig)
print(str(out))
