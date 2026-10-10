"""Stage isolated longer-startup and internal-colorbar captures; no hardware writes."""
from pathlib import Path
import hashlib,json,re,shutil
ROOT=Path(__file__).resolve().parents[1]

def main():
    old='gamma_capture'
    for target in ('gamma_capture_settled','gamma_capture_colorbars'):
        if (ROOT/'build'/target/(target+'.pds')).exists():
            raise ValueError('Do not regenerate an already built candidate')
        text=(ROOT/'board/gamma_capture.v').read_text()
        assert 'capture_warmup sensor_warmup(' in text
        text=text.replace('module gamma_capture(','module '+target+'(')
        text=text.replace('capture_warmup sensor_warmup(','capture_warmup #(.DELAY_MS(8000)) sensor_warmup(')
        sources=json.loads((ROOT/'board/gamma_capture-sources.json').read_text())
        mapping={f'board/{old}{suffix}':f'board/{target}{suffix}' for suffix in
            ('.v','.fdc','-pins.json','-sources.json')}
        mapping[f'board/build-{old}.tcl']=f'board/build-{target}.tcl'
        if target.endswith('colorbars'):
            init=ROOT/'rtl/experimental/ov5640_cadence_trial_init.v'
            new_init='rtl/experimental/ov5640_colorbars_init.v'
            new_table='board/ov5640_colorbars_commands.vh'
            init_text=init.read_text().replace('module ov5640_cadence_trial_init #(',
                'module ov5640_colorbars_init #(').replace('board/ov5640_cadence_trial_commands.vh',new_table)
            init_text=init_text.replace("16'h4300,16'h501f,16'h4740:checkable_write=1;",
                "16'h4300,16'h501f,16'h4740,16'h503d:checkable_write=1;")
            if "16'h503d:checkable_write=1;" not in init_text:
                raise ValueError('Colorbar enable must be read back')
            (ROOT/new_init).write_text(init_text)
            table=(ROOT/'board/ov5640_cadence_trial_commands.vh').read_text()
            table,count=re.subn(r'CAMERA_COMMANDS\s*=\s*264', 'CAMERA_COMMANDS=265',table)
            assert count==1
            table=table.replace("9'd263: camera_command=32'h30080214;",
                "9'd263: camera_command=32'h503d8000;\n9'd264: camera_command=32'h30080214;")
            assert 'CAMERA_COMMANDS=265' in table
            (ROOT/new_table).write_text(table)
            text=text.replace('ov5640_cadence_trial_init #','ov5640_colorbars_init #')
            mapping['rtl/experimental/ov5640_cadence_trial_init.v']=new_init
            mapping['board/ov5640_cadence_trial_commands.vh']=new_table
        (ROOT/'board'/f'{target}.v').write_text(text)
        for suffix in ('.fdc','-pins.json'):
            shutil.copy2(ROOT/'board'/f'{old}{suffix}',ROOT/'board'/f'{target}{suffix}')
        tcl=(ROOT/'board/build-gamma_capture.tcl').read_text()
        for a,b in mapping.items():tcl=tcl.replace(a,b)
        tcl=tcl.replace('compile -top_module gamma_capture','compile -top_module '+target)
        (ROOT/'board'/f'build-{target}.tcl').write_text(tcl)
        (ROOT/'board'/f'program-{target}.tcl').write_text(
            (ROOT/'board/program-gamma_capture.tcl').read_text().replace(old,target))
        sources=[mapping.get(name,name) for name in sources]
        (ROOT/'board'/f'{target}-sources.json').write_text(json.dumps(sources,indent=2)+'\n')
        if not all((ROOT/p).is_file() for p in sources):raise ValueError('Missing isolated source')
        proof={'target':target,'hardware_accessed':False,'startup_delay_ms':8000,
            'sensor_generated_pattern':target.endswith('colorbars'),
            'source_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest().upper() for p in sources}}
        (ROOT/'results/lab-20261008'/f'{target}-candidate.json').write_text(json.dumps(proof,indent=2)+'\n')
    # Include every new target in all existing timing, pin, source and options gates.
    for name in ('build-pds.ps1','program-heartbeat.ps1'):
        path=ROOT/'tools'/name;script=path.read_text(encoding='utf-8-sig')
        if "'gamma_capture_settled'" in script:continue
        if name=='program-heartbeat.ps1':
            script=script.replace("$Target -eq 'gamma_capture'","$Target -in @('gamma_capture')")
        script=script.replace("'gamma_capture'","'gamma_capture','gamma_capture_settled','gamma_capture_colorbars'")
        if name=='program-heartbeat.ps1':
            marker="if($Target -in @('corrected_video'"
            position=script.index(marker)
            script=script[:position]+'''if($Target -in @('gamma_capture_settled','gamma_capture_colorbars')) {
    & 'C:\\Users\\22955\\AppData\\Local\\Programs\\Python\\Python313\\python.exe' (Join-Path $PSScriptRoot 'validate-camera-color-candidate.py') --target $Target
    if($LASTEXITCODE -ne 0){throw 'Isolated camera-color guard failed; refusing hardware access'}
}
'''+script[position:]
        path.write_text(script,encoding='utf-8-sig')
    print('Staged two isolated targets; original camera and gamma_capture sources unchanged.')

if __name__=='__main__':main()
