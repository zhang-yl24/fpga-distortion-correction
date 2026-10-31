"""Use one continuous native pin chain per camera route branch.

The frozen repair runner retains all source/evidence/deadline checks. This
wrapper changes only the pin-chain grammar in memory and adds its own bytes
to the input hashes. Semicolons separate native list entries, so a single
net/branch requires exactly one terminal semicolon rather than several pairs.
"""
from contextlib import contextmanager
from pathlib import Path

import run_camera_vga_repair as repair

SELF = Path(__file__).resolve()
PINS = repair.WAYPOINT + r'(?:>' + repair.WAYPOINT + r'){1,63};'
ORIGINAL_PREPARE_REQUEST = repair.prepare_request


def prepare_request(request_path):
    previous = repair.PINS
    repair.PINS = PINS
    try:
        request, source, watched, commands = ORIGINAL_PREPARE_REQUEST(request_path)
        watched[repair.core.canonical_file(SELF)] = repair.core.sha(SELF)
        repair.core.require(not repair.core.check_inputs(watched), 'chain wrapper input drift')
        return request, source, watched, commands
    finally:
        repair.PINS = previous


@contextmanager
def chain_mode():
    previous_pins, previous_prepare = repair.PINS, repair.prepare_request
    repair.PINS, repair.prepare_request = PINS, prepare_request
    try:
        yield
    finally:
        repair.PINS, repair.prepare_request = previous_pins, previous_prepare


def main(argv=None):
    with chain_mode():
        return repair.main(argv)


if __name__ == '__main__':
    raise SystemExit(main())
