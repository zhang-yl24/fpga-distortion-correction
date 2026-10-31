"""Apply exact camera routes/reset scopes, save, and defer STA to a new process.

ExecutionPassed means only apply/save/snapshot completed. TimingAccepted stays
false; the initial max20 report initializes native pin objects before reset
constraints, and does not analyze the modified final ADF.
"""
from contextlib import contextmanager
from pathlib import Path

import run_camera_vga_chain_repair as chain

repair = chain.repair
SELF = Path(__file__).resolve()
ORIGINAL_RENDER = repair.render
FINAL_STA = 'mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n'


def render(commands, work):
    repair.core.require(any(c.startswith('set_false_path ') for c in commands), 'reset snapshot requires exact reset scope')
    text = ORIGINAL_RENDER(commands, work)
    repair.core.require(text.count(FINAL_STA) == 1, 'final STA command differs from frozen repair renderer')
    repair.core.require(text.index(FINAL_STA) > text.index('save_adif\n'), 'unexpected final STA position')
    return (text.replace(FINAL_STA, '')
            .replace('save_adif\n', 'puts {CAMERA_APPLY_SAVE_ONLY_NO_FINAL_STA}\nsave_adif\n'))


def prepare_request(request_path):
    request, source, watched, commands = chain.prepare_request(request_path)
    repair.core.require(request['ResetScope'] is not None, 'reset snapshot requires exact reset proof')
    watched[repair.core.canonical_file(SELF)] = repair.core.sha(SELF)
    repair.core.require(not repair.core.check_inputs(watched), 'snapshot wrapper input drift')
    return request, source, watched, commands


@contextmanager
def snapshot_mode():
    pins, prepare, renderer = repair.PINS, repair.prepare_request, repair.render
    repair.PINS, repair.prepare_request, repair.render = chain.PINS, prepare_request, render
    try:
        yield
    finally:
        repair.PINS, repair.prepare_request, repair.render = pins, prepare, renderer


def main(argv=None):
    with snapshot_mode():
        return repair.main(argv)


if __name__ == '__main__':
    raise SystemExit(main())
