"""Audit saved words for a shared DVP wire failure across the two bytes."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
def analyze(path):
    if path.suffix=='.npy':a=np.load(path,allow_pickle=False).astype(np.uint16)
    else:a=np.frombuffer(path.read_bytes(),dtype='<u2').reshape(480,640)
    if a.shape!=(480,640):raise ValueError('Expected native VGA sensor words')
    counts=[int(np.count_nonzero(a&(1<<i))) for i in range(16)]
    result={'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest().upper(),
        'pixels':a.size,'one_counts_by_rgb565_bit':counts,
        'dvp_wire5_low_byte_one_fraction':counts[5]/a.size,
        'dvp_wire5_high_byte_one_fraction':counts[13]/a.size}
    if path.name=='raw.npy':
        comparison=json.loads((path.parent/'comparison.json').read_text())
        if result['sha256'].lower()!=comparison['files_sha256'][path.name].lower():raise ValueError('Saved raw pixels changed')
        summary=json.loads((path.parent.parent/'summary.json').read_text())
        result['target']=summary.get('target');result['input_origin']=summary.get('input_origin')
        if result['input_origin']=='sensor_internal_test_pattern':
            white=a[120:360,10:70];values,n=np.unique(white,return_counts=True);i=int(np.argmax(n))
            result['white_roi']={'dominant_rgb565':f'{values[i]:04X}','dominant_count':int(n[i]),'pixels':int(white.size),
                'd5_both_byte_bits_set_fraction':float(np.mean((white&0x2020)==0x2020)),
                'all_white_FFFF_fraction':float(np.mean(white==0xFFFF))}
    return result
def main():
    p=argparse.ArgumentParser();p.add_argument('--raw',action='append',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    paths=[p.resolve() for p in a.raw];out=a.output.resolve()
    if not all(p.is_relative_to(ROOT) for p in paths+[out]):raise ValueError('Audit outside project')
    result={'hardware_accessed':False,'wire_mapping':'DVP byte D5 -> RGB565 bits 5 and 13',
        'source_sha256':{'tools/check-dvp-bitplanes.py':hashlib.sha256(Path(__file__).read_bytes()).hexdigest().upper()},
        'captures':[analyze(p) for p in paths],
        'limits':'Bit excitation must come from a known pattern; a dark/uniform natural image alone does not establish a missing wire. Historical data remains valid as received but does not certify correct camera bus wiring.'}
    out.parent.mkdir(exist_ok=True,parents=True);out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps([{'path':r['path'],'bit5':r['one_counts_by_rgb565_bit'][5],'bit13':r['one_counts_by_rgb565_bit'][13],'white':r.get('white_roi')} for r in result['captures']]))
if __name__=='__main__':main()
