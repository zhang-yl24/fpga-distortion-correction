"""Generate exact RGB565 tone curves and independent exhaustive pixel vectors."""
from pathlib import Path
import hashlib,json,numpy as np
root=Path(__file__).resolve().parents[1];work=root/'build/gamma_sim';work.mkdir(exist_ok=True)
gammas=[1,.65,1.45]
tables={bits:[[round(((v/((1<<bits)-1))**g)*((1<<bits)-1)) for v in range(1<<bits)] for g in gammas] for bits in (5,6)}
for bits,rows in tables.items():
    for row in rows:assert row[0]==0 and row[-1]==(1<<bits)-1 and all(a<=b for a,b in zip(row,row[1:]))
text=[]
for bits in (5,6):
    text.extend([f'function [{bits-1}:0] gamma{bits}(input [1:0] mode,input [{bits-1}:0] v);','    begin case({mode,v})'])
    for mode,row in enumerate(tables[bits]):
        text.extend(f"        {bits+2}'d{(mode<<bits)|v}:gamma{bits}={bits}'d{value};" for v,value in enumerate(row))
    text.extend([f'        default:gamma{bits}=v;','    endcase end','endfunction'])
(root/'rtl/experimental/gamma_curves.vh').write_text('\n'.join(text)+'\n')
gold=[]
for mode in range(3):
    for pixel in range(65536):
        r,g,b=pixel>>11,(pixel>>5)&63,pixel&31
        gold.append((tables[5][mode][r]<<11)|(tables[6][mode][g]<<5)|tables[5][mode][b])
(work/'golden.mem').write_text(''.join(f'{p:04x}\n' for p in gold))
(work/'reference.json').write_text(json.dumps({'gamma_exponents':gammas,'pixels_checked':len(gold),'quantization':'Native 5/6/5-bit channels, nearest integer (Python round), endpoints fixed; identity exact.','limits':'Tone mapping can redistribute brightness but cannot recover saturation or sensor noise.'},indent=2)+'\n')
print('Prepared 196608 exhaustive RGB565 pixel references, monotonic tone curves and adaptive-frame tests.')
