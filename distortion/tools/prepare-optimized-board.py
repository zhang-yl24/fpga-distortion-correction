"""Create isolated board variants and register the existing guarded tools."""
from pathlib import Path
import argparse
import json
import re

root = Path(__file__).resolve().parents[1]
board = root / 'board'

def register_targets():
    for name in ('build-pds.ps1', 'program-heartbeat.ps1', 'read-telemetry.ps1'):
        path = root / 'tools' / name
        text = path.read_text(encoding='utf-8-sig')
        def extend(match):
            value = match[0]
            for target in ('corrected_fast', 'corrected_rotate'):
                if "'"+target+"'" not in value:
                    value = value[:-1] + ",'"+target+"')"
            return value
        text = re.sub(r"(?:@|ValidateSet)\(([^)\n]*'corrected_video'[^)\n]*)\)", extend, text)
        path.write_text(text, encoding='utf-8-sig')

def prepare(target):
    assert target in ('corrected_fast', 'corrected_rotate')
    top = (board / 'corrected_video.v').read_text()
    top = top.replace('module corrected_video(', 'module '+target+'(')
    tcl = (board / 'build-corrected_video.tcl').read_text()
    tcl = tcl.replace('/board/corrected_video.v}', '/board/'+target+'.v}')
    tcl = tcl.replace('/board/corrected_video.fdc}', '/board/'+target+'.fdc}')
    tcl = tcl.replace('-top_module corrected_video', '-top_module '+target)
    tcl = tcl.replace('/rtl/ddr_neighbour_cache.v}', '/rtl/experimental/ddr_neighbour_cache_fast.v}')
    tcl = re.sub(r'^pnr.*$', 'pnr -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE', tcl, flags=re.M)
    # PDS parses Tcl file operations before queued flow commands execute.
    # Final routed timing is gated by build-pds.ps1 and the program guard;
    # opening the future report here would fail before report_timing runs.
    if target == 'corrected_rotate':
        from prepare_rotation_board import integrate
        top, tcl = integrate(root, top, tcl)
    # Rebuilds must not silently accept cached PDS flow status after sources
    # or primitive configuration change. Restore the full flow explicitly.
    tcl=re.sub(r'^(compile|synthesize|dev_map|pnr|report_timing|gen_bit_stream)\b',r'\1 -force_to_run',tcl,flags=re.M)
    (board / (target+'.v')).write_text(top)
    constraints=(board / 'corrected_video.fdc').read_text()
    pins=json.loads((board / 'corrected_video-pins.json').read_text())
    if target=='corrected_rotate':
        vendor=(root/'platform/video_base/HDMI_IN_DDR3_HDMI_OUT_top.fdc').read_text()
        key_constraints='\n'.join(line.replace('{p:rst_in}', '{p:key0_n}') for line in vendor.splitlines() if '{p:rst_in}' in line)
        assert '{C22}' in key_constraints and '{LVCMOS33}' in key_constraints
        constraints+='\n# Vendor rst_in / KEY0 input; exact inherited C22 constraint.\n'+key_constraints+'\n'
        constraints+='define_attribute {p:key0_n} {PAP_IO_PULLUP} {TRUE}\n'
        pins['key0_n']='C22'
    (board / (target+'.fdc')).write_text(constraints)
    (board / (target+'-pins.json')).write_text(json.dumps(pins,indent=2)+'\n')
    (board / ('build-'+target+'.tcl')).write_text(tcl)
    (board / ('program-'+target+'.tcl')).write_text((board / 'program-corrected_video.tcl').read_text().replace('corrected_video', target))
    sources = re.findall(r'^add_design \{([^}]+)\}', tcl, re.M)
    sources += [str(board / (target+'.fdc')), str(board / ('build-'+target+'.tcl')), str(board / 'calibration-trial.vh'), str(board / 'ov5640_commands.vh'), str(board / 'ms7210_commands.vh'), str(root / 'rtl/video_crc32.vh')]
    if target=='corrected_rotate':
        sources += [str(board/'rotation-domain.vh'),str(root/'rtl/cordic-constants.vh')]
    (board / (target+'-sources.json')).write_text(json.dumps([str(Path(p).relative_to(root)) for p in sources], indent=2)+'\n')
    register_targets()
    print('Prepared '+target+'; baseline board source and constraints remain reproducible.')

if __name__ == '__main__':
    p = argparse.ArgumentParser();p.add_argument('--target', choices=['corrected_fast','corrected_rotate'], default='corrected_fast')
    prepare(p.parse_args().target)
