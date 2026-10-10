"""Describe verified physical RGB565 frames and table differences, without color correction."""
from pathlib import Path
import hashlib,json,re
import numpy as np
from frozen_gamma_analysis import metrics

ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()

def commands(path):
    rows=[(int(i),int(word,16)) for i,word in re.findall(
        r"9'd(\d+): camera_command=32'h([0-9a-fA-F]{8});",path.read_text())]
    if len(rows)!=264 or [i for i,_ in rows]!=list(range(264)):
        raise ValueError('Unexpected sensor table shape')
    return rows

def stats(rgb):
    pixels=rgb.reshape(-1,3).astype(np.float64)
    return {'samples':len(pixels),'mean_rgb':pixels.mean(axis=0).tolist(),
        'median_rgb':np.median(pixels,axis=0).tolist(),
        'mean_green_minus_red':float(np.mean(pixels[:,1]-pixels[:,0])),
        'mean_green_minus_blue':float(np.mean(pixels[:,1]-pixels[:,2]))}

def main():
    base=ROOT/'board/ov5640_commands.vh'
    trial=ROOT/'board/ov5640_cadence_trial_commands.vh'
    original,current=commands(base),commands(trial)
    differences=[]
    for (i,a),(j,b) in zip(original,current):
        if i!=j or a>>16!=b>>16 or (a&255)!=(b&255):
            raise ValueError('Cadence table altered address order or command delay')
        if a!=b:
            differences.append({'index':i,'address':f'{a>>16:04X}',
                'baseline':f'{a>>8&255:02X}','cadence':f'{b>>8&255:02X}'})
    # These are source-table comparisons, not current physical register readbacks.
    selected=lambda address:0x3400<=address<=0x3406 or 0x3500<=address<=0x3503 or \
        0x5180<=address<=0x519e or address in (0x5000,0x5001,0x4300,0x501f)
    checked={word>>16:word>>8&255 for _,word in current if selected(word>>16)}
    report={'hardware_accessed':False,'source_tables_sha256':{
        str(p.relative_to(ROOT)):sha(p) for p in (base,trial)},
        'table_differences':differences,
        'selected_register_final_written_values':{f'{a:04X}':f'{v:02X}' for a,v in checked.items()},
        'selected_register_commands_same_as_baseline':all(not selected(int(d['address'],16)) for d in differences),
        'captures':[],
        'limits':'ROI RGB code differences are descriptive, not calibrated color error. ROIs are fixed geometry, not confirmed neutral paper masks. Source tables do not prove live sensor readbacks. Lighting spectrum, startup adaptation, sensor settings and physical acquisition must be isolated before changing gains.'}
    for label in ('physical-bright-20261008','physical-bright-warmed-20261008','physical-dark-warmed-20261008'):
        folder=ROOT/'captures/gamma-triplets'/label/'group-00000001'
        comparison=read(folder/'comparison.json')
        images={}
        for name in ('raw','before','after'):
            path=folder/(name+'.npy')
            if sha(path)!=comparison['files_sha256'][path.name].upper():
                raise ValueError('Capture no longer matches recorded pixels')
            frame=np.load(path,allow_pickle=False)
            if frame.shape!=(480,640) or frame.dtype!=np.uint16:
                raise ValueError('Unexpected native RGB565 shape/type')
            rgb=metrics.expand(frame)
            images[name]={'whole_frame':stats(rgb),'central_quarter':stats(rgb[120:360,160:480])}
        report['captures'].append({'label':label,'mode':comparison['mode'],'images':images,
            'comparison_sha256':sha(folder/'comparison.json')})
    output=ROOT/'results/lab-20261008/camera-color-audit.json'
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'table_differences':len(differences),'selected_commands_same':report['selected_register_commands_same_as_baseline'],
        'central_raw_rgb':{c['label']:c['images']['raw']['central_quarter']['mean_rgb'] for c in report['captures']}}))

if __name__=='__main__':main()
