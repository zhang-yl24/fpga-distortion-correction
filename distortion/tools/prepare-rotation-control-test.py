from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from model.rotation import cordic,phase_from_degrees
work=root/'build/rotation_control_sim';work.mkdir(parents=True,exist_ok=True)
(work/'vectors.mem').write_text(''.join(f'{phase_from_degrees(i*30):08x}{c&0xffffffff:08x}{s&0xffffffff:08x}\n' for i in range(12) for c,s in [cordic(phase_from_degrees(i*30))]))
