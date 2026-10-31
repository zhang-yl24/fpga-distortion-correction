"""Export the frozen camera routed functional netlist including FFloc attributes.

Uses original flow context with an explicit copied ADF. Runtime monitoring
permits only Report Timing and Generate Netlist, never fresh synthesis or PnR.
"""
import argparse
import json
from pathlib import Path

import run_camera_vga_physical as physical

MARKER = 'CAMERA_FUNCTIONAL_EXPORT_COMPLETE'
STAGES = ['Report Timing', 'Generate Netlist']


def render_tcl(original, original_work, work):
    target = physical.TARGET
    suffix = ('if {[file exists {' + original_work + '/place_route/' + target + '_pnr.adf}]} {\n'
              '    file copy {' + original_work + '/place_route/' + target + '_pnr.adf} {'
              + original_work + '/pre-sta-final.adf}\n}\n'
              'report_timing -force_to_run -delay_type min_max -max_path 20\n')
    physical.require(original.endswith(suffix) and original.count(suffix)==1, 'original stage suffix differs')
    prefix = original[:-len(suffix)]
    physical.require(prefix.endswith('pnr -optimize_multi_corner_timing -fix_hold_violation\n'),
                     'original placement context differs')
    aw = work.as_posix()
    return (prefix + 'report_timing -force_to_run -input_db_file {'+aw+'/input.adf} -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n'
            'if {[info script] ne {}} {\n'
            '    gen_netlist -force_to_run -input_db_file {'+aw+'/input.adf} -func_sim_only\n'
            '    puts {'+MARKER+'}\n    flush stdout\n}\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--maximum-seconds', type=int, default=240)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--validate-only', action='store_true')
    mode.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args(argv)
    work, maximum = physical.fresh_work(physical.ROOT/args.name), physical.deadline(args.maximum_seconds)
    plan, watched = physical.bind_inputs(extra=(Path(__file__).resolve(),))
    tcl = render_tcl((physical.BASE/'timing.tcl').read_text(encoding='ascii'), plan['AliasWorkDirectory'], work)
    if args.validate_only:
        print(json.dumps({'Validated': True, 'EDAExecuted': False, 'WorkDirectory': str(work),
                          'BaselineADFSHA256': physical.BASE_SHA, 'ExpectedActualStages': STAGES}))
        return 0
    result = physical.run_stage(work=work, source=physical.ORIGINAL, watched=watched, tcl=tcl, maximum=maximum,
        marker=MARKER, schema='camera-vga-functional-export-v1', expected_stages=STAGES,
        executor=Path(__file__).resolve(), prepare_only=args.prepare_only, require_netlist=True)
    print(json.dumps({k: result[k] for k in ('Prepared','ExecutionPassed','ElapsedSeconds','ExitCode',
                     'InputDrift','Diagnostics','ActualStages','Netlist','WorkDirectory') if k in result}), flush=True)
    return 0 if args.prepare_only or result['ExecutionPassed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
