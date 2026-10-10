"""Isolated seed-4 placement attempt; retain tested pipeline arithmetic and clocks."""
from pathlib import Path
import argparse, hashlib, json, re
from datetime import datetime, timezone
from pds_source_manifest import expand_sources
ROOT=Path(__file__).resolve().parents[1]
OLD='corrected_pipeline_hit'
TARGET='corrected_pipeline_cadence_seed4'

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def expected():
    mapping={f'board/{OLD}{s}':f'board/{TARGET}{s}' for s in ('.v','.fdc','-pins.json','-sources.json')}
    mapping[f'board/build-{OLD}.tcl']=f'board/build-{TARGET}.tcl'
    mapping['rtl/ov5640_init.v']='rtl/experimental/ov5640_cadence_trial_init.v'
    mapping['board/ov5640_commands.vh']='board/ov5640_cadence_trial_commands.vh'
    names=[n.replace('\\','/') for n in json.loads((ROOT/f'board/{OLD}-sources.json').read_text())]
    names=[mapping.get(n,n) for n in names]
    names+= [f'board/{TARGET}-pins.json',f'board/{TARGET}-sources.json']
    names=expand_sources(ROOT,names)
    top=(ROOT/f'board/{OLD}.v').read_text().replace('module '+OLD+'(', 'module '+TARGET+'(').replace('ov5640_init #','ov5640_cadence_trial_init #')
    tcl=(ROOT/f'board/build-{OLD}.tcl').read_text()
    for a,b in mapping.items():tcl=tcl.replace(a,b)
    tcl=tcl.replace(' -top_module '+OLD,' -top_module '+TARGET).replace('-gplace_seed 2','-gplace_seed 4')
    return names,top,tcl

def validate():
    names,top,tcl=expected()
    if (ROOT/f'board/{TARGET}.v').read_text()!=top:raise ValueError('Unexpected pipeline board change')
    if (ROOT/f'board/build-{TARGET}.tcl').read_text()!=tcl:raise ValueError('Unexpected build options')
    for suffix in ('.fdc','-pins.json'):
        if (ROOT/f'board/{TARGET}{suffix}').read_bytes()!=(ROOT/f'board/{OLD}{suffix}').read_bytes():raise ValueError('Changed pins or clocks')
    if json.loads((ROOT/f'board/{TARGET}-sources.json').read_text())!=names:raise ValueError('Incomplete source closure')
    proof=json.loads((ROOT/'results/lab-20261007/pipeline-twelve-native-check.json').read_text())
    if not proof['passed'] or proof['pixels_checked']!=3686400 or proof['angles']!=list(range(0,360,30)):raise ValueError('Missing native regression')
    for name,sha in proof['source_sha256'].items():
        if digest(ROOT/name)!=sha.lower():raise ValueError('Native regression input changed: '+name)
    log=ROOT/'build/pipeline_twelve_native_sim/simulation.log'
    if digest(log)!=proof['simulation_sha256'].lower():raise ValueError('Native log hash changed')
    txt=log.read_text()
    if 'PASS pipeline twelve native regression: 3686400 real-camera pixels' not in txt or re.search(r'(?i)fatal:|error:',txt):raise ValueError('Native regression failed')
    print(json.dumps({'passed':True,'target':TARGET,'source_count':len(names),'native_pixels_checked':proof['pixels_checked']}))

def stage():
    if (ROOT/f'build/{TARGET}/{TARGET}.pds').exists():raise ValueError('Already built; do not regenerate')
    # Create the manifest first so IDF expansion can require every source to exist.
    names=json.loads((ROOT/f'board/{OLD}-sources.json').read_text())
    for suffix in ('.v','.fdc','-pins.json','-sources.json'):
        text=(ROOT/f'board/{OLD}{suffix}').read_text()
        if suffix=='.v':text=text.replace('module '+OLD+'(', 'module '+TARGET+'(').replace('ov5640_init #','ov5640_cadence_trial_init #')
        (ROOT/f'board/{TARGET}{suffix}').write_text(text)
    (ROOT/f'board/build-{TARGET}.tcl').write_text((ROOT/f'board/build-{OLD}.tcl').read_text())
    expanded,top,tcl=expected()
    (ROOT/f'board/{TARGET}.v').write_text(top)
    (ROOT/f'board/build-{TARGET}.tcl').write_text(tcl)
    (ROOT/f'board/{TARGET}-sources.json').write_text(json.dumps(expanded,indent=2)+'\n')
    (ROOT/f'board/program-{TARGET}.tcl').write_text((ROOT/f'board/program-{OLD}.tcl').read_text().replace(OLD,TARGET))
    for filename in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
        p=ROOT/'tools'/filename;txt=p.read_text(encoding='utf-8-sig')
        if "'"+TARGET+"'" not in txt:
            txt=txt.replace("'"+OLD+"'","'"+OLD+"','"+TARGET+"'")
        if filename=='program-heartbeat.ps1' and 'prepare-pipeline-cadence-candidate.py' not in txt:
            at=txt.index("if($Target -in @('corrected_video'")
            txt=txt[:at]+f'''if($Target -eq '{TARGET}') {{
    & 'C:\\Users\\22955\\AppData\\Local\\Programs\\Python\\Python313\\python.exe' (Join-Path $PSScriptRoot 'prepare-pipeline-cadence-candidate.py') --validate
    if($LASTEXITCODE -ne 0){{throw 'Pipeline candidate regression guard failed'}}
}}
'''+txt[at:]
        p.write_text(txt,encoding='utf-8-sig')
    validate()

def record():
    validate()
    names,_,_=expected()
    proof={'recorded_utc':datetime.now(timezone.utc).isoformat(),'target':TARGET,'hardware_accessed':False,
        'source_sha256':{n:digest(ROOT/n).upper() for n in names},
        'changes':'Validated camera cadence initialization and place seed 4 only; pipeline arithmetic and timing constraints retained',
        'regression_proof_sha256':digest(ROOT/'results/lab-20261007/pipeline-twelve-native-check.json').upper(),
        'final_timing_passed':False,'hardware_performance_verified':False}
    path=ROOT/'results/lab-20261008/pipeline-cadence-candidate.json'
    path.write_text(json.dumps(proof,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--validate',action='store_true');p.add_argument('--record',action='store_true')
    args=p.parse_args()
    if args.record:record()
    elif args.validate:validate()
    else:stage()
