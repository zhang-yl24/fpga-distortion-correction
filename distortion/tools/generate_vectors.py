from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model.reference import bilinear_u8

def main():
    dest=Path(__file__).resolve().parents[1]/'build'/'sim'
    dest.mkdir(parents=True,exist_ok=True)
    rng=np.random.default_rng(20261004)
    lines=[]
    for i in range(8192):
        p=rng.integers(0,256,(4,3),dtype=np.uint8)
        fx,fy=map(int,rng.integers(0,256,2))
        if i<256: p[:]=i; fx=i; fy=255-i
        if 256<=i<512: p[:]=[[0,255,0],[255,0,255],[255,0,255],[0,255,0]]; fx=i-256; fy=i-256
        if 512<=i<576: fx=[0,1,128,255][i%4]; fy=[0,1,128,255][(i//4)%4]
        black=int(i%17==0)
        out=np.zeros(3,dtype=np.uint8) if black else bilinear_u8(*p,fx,fy)
        n=0
        for row in p:
            for ch in row: n=(n<<8)|int(ch)
        n=(n<<8)|fx; n=(n<<8)|fy; n=(n<<1)|black
        for ch in out: n=(n<<8)|int(ch)
        lines.append(f'{n:035x}')
    (dest/'bilinear.mem').write_text('\n'.join(lines)+'\n',encoding='ascii')
    print(f'Generated {len(lines)} deterministic RGB test vectors')

if __name__=='__main__':main()
