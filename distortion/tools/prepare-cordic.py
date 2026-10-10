"""Generate constants for sequential full-turn CORDIC parameter computation."""
from pathlib import Path
import math
root = Path(__file__).resolve().parents[1]
lines = ['// atan(2^-i) as signed phase units, one full turn = 2^32.', 'function signed [31:0] atan_phase(input [4:0] index);', '    case(index)']
for i in range(24):
    value = math.floor(math.atan(2**-i)/(2*math.pi)*(1<<32)+.5)
    lines.append(f"        5'd{i}:atan_phase=32'sh{value:08x};")
lines += ["        default:atan_phase=0;", '    endcase', 'endfunction']
(root / 'rtl/cordic-constants.vh').write_text('\n'.join(lines)+'\n')
print('Generated 24 CORDIC angle constants; no pixel-coordinate lookup table.')
