"""Exact verified KEY1 candidate volatile-SRAM programming workflow.

Prepare/validate never touch hardware. Explicit execute requires current-session
board-power authorization and notification and retains owned-JTAG cleanup.
"""
import argparse
import json
import math
from pathlib import Path
import types

import camera720_view_toggle_bitstream as bit
import camera720_stats_delay_program as base
import program_native_raw as hw

prep=bit.prep
require,sha=bit.require,bit.sha
SELF=Path(__file__).resolve()
SCHEMA='camera720-view-toggle-sram-plan-v1'

for _name in ('scripts','recipe','prepare','validate','execution_authorization','execute','main'):
    _f=getattr(base,_name)
    globals()[_name]=types.FunctionType(bit.clone_code(_f.__code__),globals(),_name,_f.__defaults__,_f.__closure__)


_recipe = recipe
def recipe(bitwork,work):
    value,text=_recipe(bitwork,work)
    # The stable implementation remains an executable dependency even though
    # its code runs with this candidate's immutable globals.
    value['BoundInputSHA256'][str(Path(base.__file__).resolve())]=sha(base.__file__)
    value['Limits']+=' KEY1/C23 toggles requested raw/corrected view; LED0 is request only, picture waits for complete frame publication.'
    return value,text


if __name__=='__main__':
    raise SystemExit(main())
