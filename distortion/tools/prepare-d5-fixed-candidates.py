"""Correct proven camera connector mapping in isolated builds, preserving old evidence."""
from pathlib import Path
import argparse,hashlib,json,re
from pds_source_manifest import expand_sources
ROOT=Path(__file__).resolve().parents[1]
TARGETS={'gamma_capture_colorbars_d5':'gamma_capture_colorbars',
    'gamma_capture_settled_d5':'gamma_capture_settled','corrected_gamma_d5':'corrected_gamma'}
def expected(target):
    old=TARGETS[target]
    top=(ROOT/f'board/{old}.v').read_text().replace('module '+old+'(','module '+target+'(')
    fdc=(ROOT/f'board/{old}.fdc').read_text()
    old_line='define_attribute {p:cam_data[5]} {PAP_IO_LOC} {AA22}'
    if fdc.count(old_line)!=1:raise ValueError('Unexpected original D5 constraint')
    fdc=fdc.replace(old_line,'define_attribute {p:cam_data[5]} {PAP_IO_LOC} {AA23}')
    pins=json.loads((ROOT/f'board/{old}-pins.json').read_text())
    if pins['cam_data[5]']!='AA22' or 'AA23' in pins.values():raise ValueError('Unexpected/occupied D5 pin')
    pins['cam_data[5]']='AA23'
    names=[n.replace('\\','/') for n in json.loads((ROOT/f'board/{old}-sources.json').read_text())]
    mapping={f'board/{old}{s}':f'board/{target}{s}' for s in ('.v','.fdc','-pins.json','-sources.json')}
    mapping[f'board/build-{old}.tcl']=f'board/build-{target}.tcl'
    names=[mapping.get(n,n) for n in names]
    for n in (f'board/{target}-pins.json',f'board/{target}-sources.json'):
        if n not in names:names.append(n)
    tcl=(ROOT/f'board/build-{old}.tcl').read_text()
    for a,b in mapping.items():tcl=tcl.replace(a,b)
    tcl=re.sub(r'(-top_module\s+)'+old+r'\b',lambda m:m[1]+target,tcl)
    return names,top,fdc,pins,tcl
def validate(target):
    names,top,fdc,pins,tcl=expected(target)
    for suffix,value in (('.v',top),('.fdc',fdc)):
        if (ROOT/f'board/{target}{suffix}').read_text()!=value:raise ValueError('Unexpected D5 candidate change')
    if json.loads((ROOT/f'board/{target}-pins.json').read_text())!=pins:raise ValueError('Unexpected candidate pins')
    if json.loads((ROOT/f'board/{target}-sources.json').read_text())!=expand_sources(ROOT,names):raise ValueError('D5 candidate source closure changed')
    if (ROOT/f'board/build-{target}.tcl').read_text()!=tcl:raise ValueError('Unexpected D5 build options')
    # No numerical datapath, ISP table or timing constraint change.
    print(json.dumps({'passed':True,'target':target,'only_functional_change':'cam_data[5] AA22 -> AA23'}))
def stage():
    for target,old in TARGETS.items():
        if (ROOT/f'build/{target}/{target}.pds').exists():raise ValueError('Do not regenerate built D5 candidate')
        names,top,fdc,pins,tcl=expected(target)
        (ROOT/f'board/{target}.v').write_text(top)
        (ROOT/f'board/{target}.fdc').write_text(fdc)
        (ROOT/f'board/{target}-pins.json').write_text(json.dumps(pins,indent=2)+'\n')
        (ROOT/f'board/build-{target}.tcl').write_text(tcl)
        (ROOT/f'board/{target}-sources.json').write_text('[]\n')
        names=expand_sources(ROOT,names)
        (ROOT/f'board/{target}-sources.json').write_text(json.dumps(names,indent=2)+'\n')
        (ROOT/f'board/program-{target}.tcl').write_text((ROOT/f'board/program-{old}.tcl').read_text().replace(old,target))
        validate(target)
    for filename in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
        p=ROOT/'tools'/filename;txt=p.read_text(encoding='utf-8-sig')
        for target,old in TARGETS.items():
            if "'"+target+"'" not in txt:
                txt=txt.replace("'"+old+"'","'"+old+"','"+target+"'")
                # Single-target old guard cannot apply to a different top/pin clone.
                txt=txt.replace("$Target -eq '"+old+"','"+target+"'","$Target -eq '"+old+"'")
        if filename=='program-heartbeat.ps1':
            txt=txt.replace("if($Target -in @('gamma_capture_settled','gamma_capture_settled_d5','gamma_capture_colorbars','gamma_capture_colorbars_d5'))", "if($Target -in @('gamma_capture_settled','gamma_capture_colorbars'))")
            marker="if($Target -in @('corrected_video'"
            at=txt.index(marker)
            txt=txt[:at]+'''if($Target -in @('gamma_capture_settled_d5','gamma_capture_colorbars_d5','corrected_gamma_d5')) {
    & 'C:\\Users\\22955\\AppData\\Local\\Programs\\Python\\Python313\\python.exe' (Join-Path $PSScriptRoot 'prepare-d5-fixed-candidates.py') --validate --target $Target
    if($LASTEXITCODE -ne 0){throw 'D5 correction isolation gate failed'}
}
'''+txt[at:]
            pin_line="foreach($p in $pinMap.PSObject.Properties){$pins[$p.Name]=$p.Value}"
            txt=txt.replace(pin_line,pin_line+'''
    if(!$ValidateOnly -and $pins.ContainsKey('cam_data[5]') -and $pins['cam_data[5]'] -ne 'AA23') {
        throw 'Known D5 mapping defect: old AA22 camera builds are historical validation only; program an AA23 correction target'
    }
''')
        p.write_text(txt,encoding='utf-8-sig')
    p=ROOT/'tools/capture-gamma-triplets.py';txt=p.read_text()
    txt=txt.replace("choices=('gamma_capture','gamma_capture_settled','gamma_capture_colorbars')", "choices=('gamma_capture','gamma_capture_settled','gamma_capture_colorbars','gamma_capture_settled_d5','gamma_capture_colorbars_d5')")
    txt=txt.replace("args.target=='gamma_capture_colorbars'","args.target.startswith('gamma_capture_colorbars')")
    p.write_text(txt)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--validate',action='store_true');p.add_argument('--target',choices=tuple(TARGETS))
    a=p.parse_args()
    if a.validate:validate(a.target)
    else:stage()
