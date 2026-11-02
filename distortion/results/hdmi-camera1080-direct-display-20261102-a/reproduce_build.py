"""Stage this exact seven-RTL frozen build in a fresh ASCII path. No tool runs.

The initial constraints intentionally omit the later placement-specific proof
exceptions. A fresh implementation needs its own native physical audit. The
accepted final ADF can instead be restored byte-for-byte for licensed native
inspection. This script never accesses hardware or writes Flash.
"""
import argparse
import gzip
import json
from pathlib import Path
import shutil

from verify_bundle import Bundle,verify,require


def stage(package,output):
    package=Path(package).resolve();output=Path(output).absolute()
    require(output==output.resolve()and not output.exists()and not output.is_relative_to(package),
        'fresh output directory outside release package required')
    require(str(output).isascii()and not any(c in str(output)for c in '{}\r\n'),'ASCII Tcl-safe staging directory required')
    checked=verify(package);b=Bundle(package);build=b.json('BuildPlan');output.mkdir(parents=True)
    for row in b.manifest['SourceSnapshots']:
        path=output/'compiled'/row['Source'];path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(package/row['CompiledFile'],path)
    literal=lambda path:'{'+path.as_posix()+'}'
    context='set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
    context+='\n'.join('add_design '+literal(output/'compiled'/name)for name in build['SourceRoles']['ExplicitDesigns'])+'\n'
    context+='add_constraint '+literal(output/'compiled/board/hdmi-camera-direct-internal.fdc')+'\n'
    tcl=context+'compile -top_module hdmi_camera_direct_top\nsynthesize -ads -selected_syn_tool_opt 2\ndev_map\n'
    tcl+='pnr -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE\n'
    tcl+='report_timing -force_to_run -delay_type min_max -max_path 10000 -nworst 4 -report_exception TRUE\n'
    (output/'build.tcl').write_text(tcl,encoding='ascii',newline='\n')
    (output/'accepted-final.adf').write_bytes(b.role('FinalADF'))
    (output/'inspect-final.tcl').write_text(context+'report_timing -force_to_run -input_db_file '+
        literal(output/'accepted-final.adf')+' -delay_type min_max -max_path 10000 -nworst 4 -report_exception TRUE\n',encoding='ascii',newline='\n')
    result={'PreparedOnly':True,'ToolExecuted':False,'HardwareAccessed':False,'Directory':str(output),
        'BuildTcl':str(output/'build.tcl'),'InspectAcceptedADFTcl':str(output/'inspect-final.tcl'),
        'Requirements':'Locally installed licensed Pango PDS2023.2-SP3 build154097 for PG2L100H-6 FBG676. '
            'New implementation/route requires a new complete native timing/pin/reset/CDC audit; no bitwise reproducibility claim.',
        'OriginalWorkingDirectoryRequired':False,'Verification':checked}
    (output/'staged.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--package',type=Path,default=Path(__file__).resolve().parent);a=p.parse_args()
    print(json.dumps(stage(a.package,a.output)))
