"""Render measured same-source frames with correctly scoped distribution metrics."""
from pathlib import Path
import argparse,json,sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from frozen_gamma_analysis import metrics

p=argparse.ArgumentParser();p.add_argument('group',type=Path);args=p.parse_args()
folder=args.group.resolve();record=json.loads((folder/'comparison.json').read_text(encoding='utf-8-sig'))
root=Path(__file__).resolve().parents[1]
if not folder.is_relative_to(root.resolve()):raise ValueError('Figure must stay within the project')
fig,axes=plt.subplots(1,3,figsize=(12,4.3),layout='constrained')
for ax,name,title in zip(axes,('raw','before','after'),('Raw source','Geometric correction',f'Gamma result (mode {record["mode"]})')):
    image=np.load(folder/(name+'.npy'),allow_pickle=False)
    ax.imshow(metrics.expand(image).astype(np.uint8));ax.set_axis_off();ax.set_title(title,color='black',fontsize=12)
tone=record['tone'];before,after=tone['before'],tone['after']
kind='Physical camera capture' if tone['provenance']['source_kind']=='physical_same_source' else 'Synthetic regression capture'
summary=folder.parent/'summary.json'
if summary.exists() and json.loads(summary.read_text(encoding='utf-8-sig')).get('input_origin')=='sensor_internal_test_pattern':
    kind='Sensor-generated colorbar capture (synthetic input on hardware)'
fig.suptitle(f'{kind} | same immutable input | group {record["group_id"]}',fontsize=13,color='black')
fig.supxlabel(f'Mean Y: {before["mean_luminance_code"]:.2f} -> {after["mean_luminance_code"]:.2f}; '
    f'valid samples: {tone["valid_samples"]:,}; '
    f'pixel mismatches: {record["bypass_mismatched_pixels"]} / {tone["mismatched_pixels"]}\n'
    'Brightness statistics are not optical resolution or recovered detail.',fontsize=10,color='black')
fig.savefig(folder/'comparison-panel.png',dpi=160,facecolor='white');plt.close(fig)
print(str(folder/'comparison-panel.png'))
