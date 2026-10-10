"""Plot measured finite UART evidence only; no simulated FPS substitution."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parents[1];lab=root/'results/lab-20261007'
specs=[('原版','corrected-baseline-check.json'),('邻像素缓存','corrected-fast-check.json'),
       ('提前提交','early-zero-check.json'),('采集与计算\n重叠','overlap-zero-check.json'),('采集重叠\n新布局','overlap_route-zero-check.json'),('自适应分块','adaptive-zero-check.json'),('分块\n布局2','adaptive_seed2-zero-check.json'),('相机提速','cadence-zero-check.json')]
names=[];rates=[];milliseconds=[];sensor=[]
for name,file in specs:
    path=lab/file
    if not path.exists():continue
    data=json.loads(path.read_text(encoding='utf-8-sig'));assert data['passed'],file
    names.append(name);rates.append(data['approx_rates_per_second']['CF'])
    milliseconds.append(data.get('max_process_ms',data.get('max_process_ms_at_125mhz')))
    if 'scheduling' in data:sensor.append(data['scheduling']['approx_sensor_frame_rate_at_125mhz'])
assert len(names)>=3
plt.rcParams.update({'font.family':'Microsoft YaHei','text.color':'black','axes.labelcolor':'black','xtick.color':'black','ytick.color':'black'})
fig,axes=plt.subplots(1,2,figsize=(12.8,4.8),layout='constrained')
colors=['#5A8AC4','#679B8B','#A5A0CA','#7544AB','#CA6B35','#458372','#AD629C','#336DA3'][:len(names)]
for ax,values,label in zip(axes,(rates,milliseconds),('新增矫正帧率（fps）','采样中的最大处理时间（ms）')):
    bars=ax.bar(names,values,color=colors,width=.62);ax.set_ylabel(label)
    ax.spines[['top','right']].set_visible(False)
    for bar,value in zip(bars,values):ax.text(bar.get_x()+bar.get_width()/2,value,f'{value:.2f}',ha='center',va='bottom',color='black')
    ax.set_ylim(0,max(values)*1.24)
    ax.tick_params(axis='x',labelsize=10)
if sensor:
    value=sensor[-1];axes[0].axhline(value,color='black',ls='--',lw=1,label=f'最新相机帧周期估计：{value:.2f} fps')
    axes[0].set_ylim(0,max(max(rates),value)*1.25);axes[0].legend(frameon=False,fontsize=10)
fig.suptitle('640×480、零旋转：有限实板测试结果',fontsize=16)
fig.supxlabel('CF统计新完成的矫正帧；HDMI约60Hz包含重复刷新。不同短测的主机时间戳仅提供近似帧率，未证明长时间稳定性。',fontsize=10)
dest=lab/'physical-throughput.png';fig.savefig(dest,dpi=150);plt.close(fig)
print(str(dest))
