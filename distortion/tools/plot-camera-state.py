"""Plot actual SCCB gain readbacks; do not infer calibrated optical quality."""
from pathlib import Path
import argparse,json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('probe',type=Path);a=p.parse_args()
folder=a.probe.resolve()
if not folder.is_relative_to(ROOT.resolve()):raise ValueError('Output outside project')
probe=json.loads((folder/'summary.json').read_text())
if not probe['passed']:raise ValueError('Probe did not complete')
scans=probe['scans'];times=[s['first_ms']/1000 for s in scans]
fig,axes=plt.subplots(2,1,figsize=(8,5),layout='constrained')
for i,(name,color) in enumerate((('R','#cc2222'),('G','#168533'),('B','#2244cc'))):
    axes[0].plot(times,[int(s['non_atomic_rgb_gain_codes'][i],16) for s in scans],'.-',label=name,color=color)
axes[0].set_ylabel('AWB gain register code',color='black');axes[0].legend()
axes[1].plot(times,[int(s['non_atomic_agc_code'],16) for s in scans],'.-',color='black')
axes[1].set_ylabel('AGC register code',color='black');axes[1].set_xlabel('Seconds since sensor readiness',color='black')
for ax in axes:ax.tick_params(colors='black');ax.grid(alpha=.15)
fig.suptitle('Physical OV5640 readback | automatic AWB, AEC and AGC enabled',color='black')
fig.supxlabel('Each scan reads 24 registers sequentially; multi-byte values are non-atomic.\nUnattended illumination; readbacks do not prove calibrated color or earlier-frame causality.',fontsize=9,color='black')
fig.savefig(folder/'color-state-timeline.png',dpi=160,facecolor='white');plt.close(fig)
print(folder/'color-state-timeline.png')
