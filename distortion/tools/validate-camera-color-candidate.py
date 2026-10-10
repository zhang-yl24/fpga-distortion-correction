"""Check that diagnostic targets alter only startup delay or sensor test pattern."""
from pathlib import Path
import argparse,hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]

def validate(target):
    base=(ROOT/'board/gamma_capture.v').read_text()
    expected=base.replace('module gamma_capture(','module '+target+'(').replace(
        'capture_warmup sensor_warmup(','capture_warmup #(.DELAY_MS(8000)) sensor_warmup(')
    sources=json.loads((ROOT/'board/gamma_capture-sources.json').read_text())
    mapping={f'board/gamma_capture{suffix}':f'board/{target}{suffix}' for suffix in
        ('.v','.fdc','-pins.json','-sources.json')}
    mapping['board/build-gamma_capture.tcl']=f'board/build-{target}.tcl'
    if target=='gamma_capture_colorbars':
        work=ROOT/'build/camera_colorbars_sim'
        proof=json.loads((work/'source-sha256.json').read_text(encoding='utf-8-sig'))
        for name,digest in proof.items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest().upper()!=digest:
                raise ValueError('Colorbar simulation source changed: '+name)
        log=(work/'simulation.log').read_text()
        if 'PASS camera colorbars:' not in log or re.search(r'(?i)fatal:|error:',log):
            raise ValueError('Colorbar initialization regression did not pass')
        expected=expected.replace('ov5640_cadence_trial_init #','ov5640_colorbars_init #')
        original=(ROOT/'board/ov5640_cadence_trial_commands.vh').read_text()
        table=re.sub(r'CAMERA_COMMANDS\s*=\s*264','CAMERA_COMMANDS=265',original).replace(
            "9'd263: camera_command=32'h30080214;",
            "9'd263: camera_command=32'h503d8000;\n9'd264: camera_command=32'h30080214;")
        if (ROOT/'board/ov5640_colorbars_commands.vh').read_text()!=table:raise ValueError('Unexpected test-pattern sensor settings')
        init=(ROOT/'rtl/experimental/ov5640_cadence_trial_init.v').read_text().replace(
            'module ov5640_cadence_trial_init #(','module ov5640_colorbars_init #(').replace(
            'board/ov5640_cadence_trial_commands.vh','board/ov5640_colorbars_commands.vh').replace(
            "16'h4300,16'h501f,16'h4740:checkable_write=1;",
            "16'h4300,16'h501f,16'h4740,16'h503d:checkable_write=1;")
        if (ROOT/'rtl/experimental/ov5640_colorbars_init.v').read_text()!=init:raise ValueError('Unexpected colorbar initialization')
        mapping['rtl/experimental/ov5640_cadence_trial_init.v']='rtl/experimental/ov5640_colorbars_init.v'
        mapping['board/ov5640_cadence_trial_commands.vh']='board/ov5640_colorbars_commands.vh'
    if (ROOT/'board'/f'{target}.v').read_text()!=expected:raise ValueError('Diagnostic changed functional pipeline')
    for suffix in ('.fdc','-pins.json'):
        if (ROOT/'board'/f'{target}{suffix}').read_bytes()!=(ROOT/'board'/f'gamma_capture{suffix}').read_bytes():
            raise ValueError('Diagnostic pin/constraint differences')
    if json.loads((ROOT/'board'/f'{target}-sources.json').read_text())!=[mapping.get(n,n) for n in sources]:
        raise ValueError('Diagnostic source closure changed unexpectedly')
    print(json.dumps({'passed':True,'target':target,'startup_delay_ms':8000}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--target',required=True,choices=('gamma_capture_settled','gamma_capture_colorbars'))
    validate(p.parse_args().target)
