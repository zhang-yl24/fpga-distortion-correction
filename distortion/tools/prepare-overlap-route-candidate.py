"""Prepare a separate placement seed with identical video RTL.

PG2L100H rejects number_of_router_thread even though generic PDS help lists it.
Keep the device-supported default router configuration.
"""
from pathlib import Path
import hashlib,json,re,shutil
root=Path(__file__).resolve().parents[1];old='corrected_overlap';new='corrected_overlap_route'
top=(root/'board'/f'{old}.v').read_text().replace(f'module {old}(',f'module {new}(')
(root/'board'/f'{new}.v').write_text(top)
tcl=(root/'board'/f'build-{old}.tcl').read_text().replace(old,new)
tcl=tcl.replace('pnr -force_to_run','pnr -force_to_run -gplace_seed 2')
(root/'board'/f'build-{new}.tcl').write_text(tcl)
for suffix in ('.fdc','-pins.json'):shutil.copy2(root/'board'/(old+suffix),root/'board'/(new+suffix))
(root/'board'/f'program-{new}.tcl').write_text((root/'board'/f'program-{old}.tcl').read_text().replace(old,new))
sources=re.findall(r'^add_design \{([^}]+)\}',tcl,re.M)
sources+=[str(root/'board'/f'{new}.fdc'),str(root/'board'/f'build-{new}.tcl')]
sources+=[str(root/p) for p in ('board/calibration-trial.vh','board/ov5640_commands.vh','board/ms7210_commands.vh','rtl/video_crc32.vh','board/rotation-domain.vh','rtl/cordic-constants.vh')]
(root/'board'/f'{new}-sources.json').write_text(json.dumps([str(Path(p).relative_to(root)) for p in sources],indent=2)+'\n')
for name in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
    path=root/'tools'/name;text=path.read_text(encoding='utf-8-sig')
    text=re.sub(r"(?:@|ValidateSet)\(([^)\n]*'corrected_overlap'[^)\n]*)\)",lambda m:m[0] if f"'{new}'" in m[0] else m[0][:-1]+f",'{new}')",text)
    path.write_text(text,encoding='utf-8-sig')
proof={'hardware_accessed':False,'target':new,'placement_seed':2,'router_threads':'device default',
       'top_equal_except_module_name':top.replace(f'module {new}(',f'module {old}(')==(root/'board'/f'{old}.v').read_text(),
       'same_pin_map':(root/'board'/f'{old}-pins.json').read_bytes()==(root/'board'/f'{new}-pins.json').read_bytes(),
       'same_constraints':(root/'board'/f'{old}.fdc').read_bytes()==(root/'board'/f'{new}.fdc').read_bytes(),
       'common_video_rtl_sha256':hashlib.sha256((root/'rtl/experimental/ddr_overlap_video.v').read_bytes()).hexdigest(),
       'limits':'Alternative physical implementation only, no timing relaxation or frequency reduction. Complete build/source/timing/pin gates must pass before SRAM configuration.'}
assert proof['top_equal_except_module_name'] and proof['same_pin_map'] and proof['same_constraints']
(root/'results/lab-20261007/overlap-route-candidate.json').write_text(json.dumps(proof,indent=2)+'\n')
print('Prepared identical video RTL with seed 2 and device-default routing; active original sources are unchanged.')
