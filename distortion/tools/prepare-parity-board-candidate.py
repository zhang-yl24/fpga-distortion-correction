"""Compile isolated parity cache, preserving the tested board interface and clocks."""
from pathlib import Path
import argparse,hashlib,json
from pds_source_manifest import expand_sources
from importlib.util import spec_from_file_location,module_from_spec
ROOT=Path(__file__).resolve().parents[1]
OLD='corrected_pipeline_cadence_seed4'
TARGET='corrected_pipeline_parity_cadence'
def expected():
    mapping={f'board/{OLD}{s}':f'board/{TARGET}{s}' for s in ('.v','.fdc','-pins.json','-sources.json')}
    mapping[f'board/build-{OLD}.tcl']=f'board/build-{TARGET}.tcl'
    mapping['rtl/experimental/ddr_pipeline_hit_cache.v']='rtl/experimental/ddr_pipeline_parity_cache.v'
    names=json.loads((ROOT/f'board/{OLD}-sources.json').read_text())
    names=[mapping.get(n,n) for n in names]
    top=(ROOT/f'board/{OLD}.v').read_text().replace('module '+OLD+'(','module '+TARGET+'(')
    tcl=(ROOT/f'board/build-{OLD}.tcl').read_text()
    for a,b in mapping.items():tcl=tcl.replace(a,b)
    tcl=tcl.replace('-top_module '+OLD,'-top_module '+TARGET).replace('-gplace_seed 4','-gplace_seed 2')
    return names,top,tcl
def validate():
    names,top,tcl=expected()
    if (ROOT/f'board/{TARGET}.v').read_text()!=top or (ROOT/f'board/build-{TARGET}.tcl').read_text()!=tcl:raise ValueError('Unexpected parity board changes')
    for suffix in ('.fdc','-pins.json'):
        if (ROOT/f'board/{TARGET}{suffix}').read_bytes()!=(ROOT/f'board/{OLD}{suffix}').read_bytes():raise ValueError('Changed pins or clocks')
    if json.loads((ROOT/f'board/{TARGET}-sources.json').read_text())!=names:raise ValueError('Incomplete parity source closure')
    spec=spec_from_file_location('parity_check',ROOT/'tools/record-pipeline-parity-regression.py')
    mod=module_from_spec(spec);spec.loader.exec_module(mod);result=mod.validate()
    print(json.dumps({'passed':True,'target':TARGET,'source_count':len(names),'pixels_checked':result['pixels_checked']}))
def stage():
    if (ROOT/f'build/{TARGET}/{TARGET}.pds').exists():raise ValueError('Do not regenerate built candidate')
    names,top,tcl=expected()
    for suffix in ('.fdc','-pins.json'):(ROOT/f'board/{TARGET}{suffix}').write_bytes((ROOT/f'board/{OLD}{suffix}').read_bytes())
    (ROOT/f'board/{TARGET}.v').write_text(top)
    (ROOT/f'board/build-{TARGET}.tcl').write_text(tcl)
    (ROOT/f'board/{TARGET}-sources.json').write_text(json.dumps(names,indent=2)+'\n')
    if expand_sources(ROOT,names)!=names:raise ValueError('Source closure not expanded')
    (ROOT/f'board/program-{TARGET}.tcl').write_text((ROOT/f'board/program-{OLD}.tcl').read_text().replace(OLD,TARGET))
    for filename in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
        p=ROOT/'tools'/filename;txt=p.read_text(encoding='utf-8-sig')
        if "'"+TARGET+"'" not in txt:txt=txt.replace("'"+OLD+"'","'"+OLD+"','"+TARGET+"'")
        # Equality branch for the old guard must stay single-target.
        txt=txt.replace("$Target -eq '"+OLD+"','"+TARGET+"'","$Target -eq '"+OLD+"'")
        if filename=='program-heartbeat.ps1' and 'prepare-parity-board-candidate.py' not in txt:
            at=txt.index("if($Target -in @('corrected_video'")
            txt=txt[:at]+f'''if($Target -eq '{TARGET}') {{
    & 'C:\\Users\\22955\\AppData\\Local\\Programs\\Python\\Python313\\python.exe' (Join-Path $PSScriptRoot 'prepare-parity-board-candidate.py') --validate
    if($LASTEXITCODE -ne 0){{throw 'Parity candidate full native regression gate failed'}}
}}
'''+txt[at:]
        p.write_text(txt,encoding='utf-8-sig')
    print('Staged parity board; hardware programming requires all three regressions')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--validate',action='store_true')
    if p.parse_args().validate:validate()
    else:stage()
