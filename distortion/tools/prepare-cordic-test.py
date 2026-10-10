from pathlib import Path
import json
import math
import sys
import numpy as np
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from model.rotation import cordic
work = root / 'build/cordic_sim';work.mkdir(parents=True, exist_ok=True)
phases = [0, 1, 0x3fffffff, 0x40000000, 0x40000001, 0x7fffffff, 0x80000000, 0xbfffffff, 0xc0000000, 0xc0000001, 0xffffffff]
phases += [int(p) for p in np.random.default_rng(20261006).integers(0, 1<<32, 1013)]
rows, errors = [], []
for phase in phases:
    c, s = cordic(phase)
    a = phase / (1 << 32) * 2 * math.pi
    errors.append(max(abs(c/(1<<30)-math.cos(a)), abs(s/(1<<30)-math.sin(a))))
    rows.append(f'{phase:08x}{c&0xffffffff:08x}{s&0xffffffff:08x}')
assert max(errors) < 2e-7
(work/'vectors.mem').write_text('\n'.join(rows)+'\n')
(work/'counts.vh').write_text(f'`define CORDIC_N {len(rows)}\n')
(work/'reference.json').write_text(json.dumps({'queries': len(rows), 'iterations': 24, 'max_abs_trig_error': max(errors), 'full_turn_phase_bits': 32, 'coefficient_fraction_bits': 30}, indent=2)+'\n')
print(f'Generated {len(rows)} full-turn CORDIC vectors; analytic maximum coefficient error {max(errors):.3g}.')
