"""Audit shipped baseline files and source hashes without invoking tools or hardware."""
from pathlib import Path
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'distortion/tools'))
from pds_source_manifest import expand_sources

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()

def main():
    results=[]
    for folder in sorted((ROOT/'handoff/baseline').iterdir()):
        if not folder.is_dir():
            continue
        target=folder.name
        manifest=json.loads((folder/'validated-build.json').read_text(encoding='utf-8-sig'))
        bitstream=folder/'generate_bitstream'/f'{target}.sbit'
        if sha(bitstream)!=manifest['SHA256']:
            raise ValueError('Bitstream differs: '+target)
        hashes=manifest.get('SourceSHA256') or {}
        for name, expected in hashes.items():
            if sha(ROOT/'distortion'/name)!=expected:
                raise ValueError('Bound source differs: '+name)
        source_file=ROOT/'distortion/board'/f'{target}-sources.json'
        closure=[]
        if source_file.is_file():
            names=json.loads(source_file.read_text())
            closure=expand_sources(ROOT/'distortion',names)
            if set(closure)!=set(n.replace('\\','/') for n in names):
                raise ValueError('IP dependency closure is incomplete: '+target)
        timing=folder/'report_timing'/f'{target}.rtr'
        if not timing.is_file():
            timing=folder/'place_route'/f'{target}_timing_summary_after_hold_fix.txt'
        text=timing.read_text(errors='replace')
        if 'All Constraints Met' not in text:
            raise ValueError('Timing did not pass: '+target)
        if manifest.get('TimingSHA256') and sha(timing)!=manifest['TimingSHA256']:
            raise ValueError('Timing hash differs: '+target)
        pin_file=ROOT/'distortion/board'/f'{target}-pins.json'
        if pin_file.is_file():
            pins=json.loads(pin_file.read_text())
            if 'cam_data[5]' in pins and pins['cam_data[5]']!='AA23':
                raise ValueError('Incorrect camera D5: '+target)
        results.append({'target':target,'source_hashes':len(hashes),
                        'dependency_closure':len(closure),'bitstream_sha256':manifest['SHA256']})
    print(json.dumps({'passed':True,'hardware_accessed':False,'baselines':results},indent=2))

if __name__=='__main__':
    main()
