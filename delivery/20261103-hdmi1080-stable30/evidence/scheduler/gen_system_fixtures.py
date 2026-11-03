from pathlib import Path
import sys,json,hashlib,ast,types
import numpy as np
repo=Path('C:/Users/Lenovo/Documents/Codex/2026-11-02/2026-fpga/work/repo/distortion');sys.path.insert(0,str(repo/'tools'))
# Extract only the unchanged pure-numpy reference functions. OpenCV is only
# needed by inverse_map, which this bit-accurate synthetic test never uses.
reference=repo/'model/reference.py'
ref_ast=ast.parse(reference.read_text(encoding='utf-8'))
ref_scope={'np':np}
for node in ref_ast.body:
 if isinstance(node,ast.FunctionDef) and node.name in ('bilinear_u8','remap_fixed'):
  exec(compile(ast.Module(body=[node],type_ignores=[]),str(reference),'exec'),ref_scope)
cpu_path=repo/'tools/generate_1080_core_vectors.py'
cpu_ast=ast.parse(cpu_path.read_text(encoding='utf-8'))
cpu_ast.body=[n for n in cpu_ast.body if not (isinstance(n,ast.ImportFrom) and n.module=='model.reference')]
cpu=types.ModuleType('system_fixture_cpu');cpu.__file__=str(cpu_path);cpu.remap_fixed=ref_scope['remap_fixed']
exec(compile(cpu_ast,str(cpu_path),'exec'),cpu.__dict__)
root=Path('D:/fpga-stable/scheduler/system-small');root.mkdir(exist_ok=True)
c=cpu.parameters(32,16);a=cpu.texture(32,16,0);b=cpu.texture(32,16,1)
print(a.dtype,a.shape)
sources=[a,b,np.bitwise_xor(a,np.uint16(0x5a3c))]
for i,s in enumerate(sources):
 y,x=np.indices(s.shape,dtype=np.int64)
 sx,sy,bad,r2=cpu.project_integer(x*256,y*256,c)
 m=bad|(r2>2*cpu.Q)|(sx<=-256)|(sy<=-256)|(sx>=32*256)|(sy>=16*256)
 scalar=cpu.scalar_oracle()
 for yy in range(16):
  for xx in range(32):
   assert scalar.project(xx*256,yy*256,c)==(int(sx[yy,xx]),int(sy[yy,xx]),int(bad[yy,xx]))
 e=cpu.tone(cpu.pack565(cpu.remap_fixed(cpu.expand565(s),np.where(m,-(1<<23),sx)/256.,np.where(m,-(1<<23),sy)/256.)),m,0)
 for name,data,fmt in [('source',s,'%04x'),('expected',e,'%04x'),('masks',m.astype(np.uint8),'%01x')]:np.savetxt(root/f'{name}{i}.mem',data.reshape(-1),fmt=fmt)
 (root/f'sourcecrc{i}.mem').write_text(cpu.pixel_crc(s)+'\n');(root/f'crc{i}.mem').write_text(cpu.pixel_crc(e)+'\n')
lines=['localparam VEC_WIDTH=32,VEC_HEIGHT=16;','localparam VEC_RADIUS_GUARD_Q22=8388608;']
for n,v,bits in zip(cpu.NAMES,c,[24]*6+[32]*7):lines.append(f"localparam signed [{bits-1}:0] VEC_{n}={bits}'h{v&((1<<bits)-1):x};")
(root/'config.vh').write_text('\n'.join(lines)+'\n')
(root/'timing.vh').write_text('localparam integer SIM_HT=80,SIM_VT=40,SIM_HS=4,SIM_X0=10,SIM_Y0=3,SIM_VS=1,SIM_OUTPUT_PHASE_PS=17000,SIM_MAX_CYCLES=2000000,SIM_FRAMES=8,SIM_FAULT_PHASE=1;\n')
(root/'fixture-source.json').write_text(json.dumps({'config':c,'source':str(repo/'tools/generate_1080_core_vectors.py'),'scope':'Synthetic 32x16 nonzero radial/tangential independent CPU goldens; no new-camera calibration'},indent=2))
