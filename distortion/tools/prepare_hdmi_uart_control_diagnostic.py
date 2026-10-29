"""Prepare configuration-only HDMI UART diagnostic, retaining the full candidate."""
from pathlib import Path
import argparse
import json
import re
import prepare_hdmi_uart_diagnostic as full

ROOT=full.ROOT
TOP='hdmi_uart_control_diag'
SOURCES=tuple('board/hdmi_uart_control_diag.v' if s=='board/hdmi_uart_diag.v' else s
              for s in full.SOURCES if s not in (
                  'rtl/experimental/hdmi1080_input_status.v',
                  'rtl/experimental/dvp_mode_admission_monitor.v'))


def prepare(work):
    work=Path(work).resolve()
    if work.parent!=full.BASE.resolve() or not work.is_dir() or any(work.iterdir()):
        raise ValueError('fresh empty child of build/hdmi-uart-diagnostic required')
    fdc,pins=full.constraints()
    omitted={'pixclk_in','vs_in','hs_in','de_in'}
    lines=[]
    for line in fdc.splitlines():
        if line.startswith('create_clock -name input_pixel '):continue
        m=re.match(r'define_attribute \{p:([^}]+)\}',line)
        if m and m[1] in omitted:continue
        lines.append(line)
    pins={k:v for k,v in pins.items() if k not in omitted}
    fdc_path=work/(TOP+'.fdc')
    fdc_path.write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    tcl=[f'add_design {{{(ROOT/s).as_posix()}}}' for s in SOURCES]
    tcl += [f'add_constraint {{{fdc_path.as_posix()}}}',
            'set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676',
            f'compile -top_module {TOP}', 'synthesize -ads -selected_syn_tool_opt 2', 'dev_map',
            'pnr -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 '
            '-fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE',
            'report_timing -force_to_run -delay_type min_max -max_path 20']
    (work/'build.tcl').write_text('\n'.join(tcl)+'\n',encoding='utf-8',newline='\n')
    config=json.loads((ROOT.parent/'team-config.local.json').read_text(encoding='utf-8-sig'))
    pds=Path(config['pds_bin'])/'pds_shell.exe'
    inputs=(*SOURCES, full.FDC_SOURCE, 'tools/prepare_hdmi_uart_diagnostic.py',
            'tools/prepare_hdmi_uart_control_diagnostic.py')
    plan={'Schema':'hdmi-uart-control-diagnostic-build-v1','Target':TOP,
          'InputSHA256':{s:full.sha(ROOT/s) for s in inputs},'Pins':pins,
          'TclSHA256':full.sha(work/'build.tcl'),'FDCSHA256':full.sha(fdc_path),
          'FDC':str(fdc_path),'Command':[str(pds),'-file',str(work/'build.tcl'),
              '-work_dir',str(work),'-project_name',TOP],
          'SourceCount':len(SOURCES),'DDRIncluded':False,'InputObserverIncluded':False,
          'HardwareAccessed':False,'BitstreamRequested':False,'HardwareReleaseAllowed':False,
          'Limits':'Configuration progress and synthetic TX bars only. No input timing/mode measurement, image processing or optical acceptance.'}
    (work/'build-plan.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
    return plan


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workdir',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(prepare(a.workdir),indent=2))
