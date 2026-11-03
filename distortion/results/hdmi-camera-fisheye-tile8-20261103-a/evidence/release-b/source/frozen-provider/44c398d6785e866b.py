"""Prepare a standalone HDMI diagnostic build; no DDR/IP or shared FDC edits.

Only prepares a fresh project. Native reports must be reviewed separately;
bitstream generation is deliberately not part of this preparation.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'build/hdmi-uart-diagnostic'
TOP = 'hdmi_uart_diag'
SOURCES = (
    'board/hdmi_uart_diag.v', 'rtl/experimental/hdmi_diag_uart.v', 'rtl/uart_tx.v',
    'rtl/experimental/ms72xx_observed_ctl.v', 'rtl/experimental/ms7200_1080p30_ctl.v',
    'rtl/experimental/ms7210_checked_ctl.v', 'rtl/experimental/iic_dri_checked.v',
    'rtl/experimental/hdmi1080_input_status.v', 'rtl/experimental/dvp_mode_admission_monitor.v',
    'platform/video_base/ipcore/cfg_pll/cfg_pll.v', 'board/bringup_pll.v', 'rtl/video_pattern.v',
)
FDC_SOURCE = 'board/board1080-checked-i2c.fdc'
SINGLE_PORTS = ('clk_27m','reset_n','pixclk_in','vs_in','hs_in','de_in',
                'hd_scl','hd_sda','rstn_out','pix_clk','hs_out','vs_out','de_out')
PORTS = set(SINGLE_PORTS) | {f'{bus}[{i}]' for bus in ('r_out','g_out','b_out','led') for i in range(8)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def constraints():
    """Copy only the existing diagnostic's used ports, plus documented UART TX."""
    source = (ROOT / FDC_SOURCE).read_text(encoding='utf-8')
    names = {'board27', 'input_pixel', 'pixel_clk', 'cfg_clk'}
    clocks = [s for s in source.splitlines()
              if re.match(r'^create_(?:generated_)?clock -name (\w+) ', s)
              and re.match(r'^create_(?:generated_)?clock -name (\w+) ', s)[1] in names]
    if len(clocks) != 4 or {re.search(r'-name (\w+)', s)[1] for s in clocks} != names:
        raise ValueError('expected board27, input pixel, cfg and video PLL clocks')
    attrs = []
    pins = {}
    directions = {}
    for line in source.splitlines():
        m = re.fullmatch(r'define_attribute \{p:(.+)\} \{([^}]+)\} \{([^}]+)\}', line)
        if m and m[1] in PORTS:
            attrs.append(line)
            if m[2] == 'PAP_IO_LOC':
                if m[1] in pins:
                    raise ValueError('duplicate inherited pin')
                pins[m[1]] = m[3]
            if m[2] == 'PAP_IO_DIRECTION':
                directions[m[1]] = m[3]
    if set(pins) != PORTS or len(set(pins.values())) != len(pins):
        raise ValueError('incomplete/duplicate diagnostic port map')
    if any(directions.get(p) != 'INOUT' for p in ('hd_scl','hd_sda')):
        raise ValueError('both I2C pins must be bidirectional')
    if any(pins[k] != v for k,v in {'clk_27m':'D18','reset_n':'C22','hd_scl':'K22',
                                   'hd_sda':'K23','rstn_out':'G25','pixclk_in':'K21'}.items()):
        raise ValueError('documented primary board pins changed')
    if 'C24' in pins.values():
        raise ValueError('UART C24 pin collision')
    pins['uart_txd'] = 'C24'
    attrs += [f'define_attribute {{p:uart_txd}} {{{key}}} {{{value}}}' for key,value in (
        ('PAP_IO_LOC','C24'),('PAP_IO_DIRECTION','OUTPUT'),('PAP_IO_STANDARD','LVCMOS33'),
        ('PAP_IO_VCCIO','3.3'),('PAP_IO_DRIVE','4'),('PAP_IO_SLEW','SLOW'))]
    text = ('# Standalone diagnostic only. No DDR ports or shared constraint changes.\n'
            '# Inherits physical attributes, NOT external IO/CDC timing acceptance.\n'
            '# No fabricated IO delays, pullups or blanket false paths.\n'
            + '\n'.join(clocks + attrs) + '\n')
    return text, pins


def prepare(work):
    work = Path(work).resolve()
    if work.parent != BASE.resolve() or not work.is_dir() or any(work.iterdir()):
        raise ValueError('fresh empty child of distortion/build/hdmi-uart-diagnostic required')
    inputs = {s: sha(ROOT / s) for s in (*SOURCES,FDC_SOURCE,'tools/prepare_hdmi_uart_diagnostic.py')}
    fdc, pins = constraints()
    (work / 'hdmi_uart_diag.fdc').write_text(fdc,encoding='utf-8',newline='\n')
    tcl = [f'add_design {{{(ROOT / s).as_posix()}}}' for s in SOURCES]
    tcl += [f'add_constraint {{{(work / "hdmi_uart_diag.fdc").as_posix()}}}',
            'set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676',
            'compile -top_module hdmi_uart_diag', 'synthesize -ads -selected_syn_tool_opt 2',
            'dev_map', 'pnr -optimize_multi_corner_timing -fix_hold_violation '
            '-fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100 '
            '-fix_hold_violation_in_route TRUE',
            'report_timing -force_to_run -delay_type min_max -max_path 20']
    (work / 'build.tcl').write_text('\n'.join(tcl)+'\n',encoding='utf-8',newline='\n')
    config = json.loads((ROOT.parent/'team-config.local.json').read_text(encoding='utf-8-sig'))
    pds = Path(config['pds_bin'])/'pds_shell.exe'
    if not pds.is_file():
        raise ValueError('configured PDS executable is missing')
    plan = {'Schema':'hdmi-uart-diagnostic-build-v1','InputSHA256':inputs,'Pins':pins,
            'TclSHA256':sha(work/'build.tcl'),'FDCSHA256':sha(work/'hdmi_uart_diag.fdc'),
            'Command':[str(pds),'-file',str(work/'build.tcl'),'-work_dir',str(work),'-project_name',TOP],
            'SourceCount':len(SOURCES),'DDRIncluded':False,'HardwareAccessed':False,
            'BitstreamRequested':False,'HardwareReleaseAllowed':False,
            'Limits':'Preparation only; synthetic TX bars, no distortion processing. External IO/CDC and pullups unverified.'}
    (work/'build-plan.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
    return plan


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workdir',type=Path,required=True)
    args=p.parse_args()
    print(json.dumps(prepare(args.workdir),indent=2))
