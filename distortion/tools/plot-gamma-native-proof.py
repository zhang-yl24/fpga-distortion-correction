"""Visualize a sealed synthetic native tone regression, never an optical claim."""
from pathlib import Path
import hashlib,json,sys,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from model.rotation import cordic,phase_from_degrees
from model.reference import remap_fixed
work=root/'build/gamma_native_tone_sim';lab=root/'results/lab-20261007'
check=json.loads((lab/'gamma-tone-simulation-check.json').read_text());assert check['passed']
for rel,digest in check['source_sha256'].items():assert hashlib.sha256((root/rel).read_bytes()).hexdigest().upper()==digest
ref=json.loads((work/'reference.json').read_text());i=2
def frame(name):
    rows=(work/name).read_text().splitlines()[i*19200:(i+1)*19200]
    return np.frombuffer(b''.join(int(s,16).to_bytes(32,'little') for s in rows),dtype='<u2').reshape(480,640)
def expand(p):
    r=p>>11;g=(p>>5)&63;b=p&31
    return np.stack(((r<<3)|(r>>2),(g<<2)|(g>>4),(b<<3)|(b>>2)),axis=-1).astype(np.uint8)
src=frame('source.mem');final=frame('result.mem')
c=json.loads((root/'results/calibration-fpga-candidate-20261006/candidate.json').read_text())['integer_config']
bound=json.loads((root/'results/rotation-domain-20261006.json').read_text())['guard_radius_squared_q22']
y,x=np.indices((480,640),dtype=np.int64);rs=lambda v,n:(v+(1<<(n-1)))>>n
co,si=cordic(phase_from_degrees(ref['frames'][i]['angle_deg']))
u=rs(co*(x*256-81792)+si*(y*256-61312),30)+81792;v=rs(-si*(x*256-81792)+co*(y*256-61312),30)+61312
nx=rs((u-c[0])*c[6],16);ny=rs((v-c[1])*c[7],16)
xx=rs(nx*nx,22);yy=rs(ny*ny,22);xy=rs(nx*ny,22);r2=xx+yy
rad=2**22+rs((c[8]+rs((c[9]+rs(c[10]*r2,22))*r2,22))*r2,22)
tx=rs(2*c[11]*xy+c[12]*(r2+2*xx),22);ty=rs(c[11]*(r2+2*yy)+2*c[12]*xy,22)
sx=rs((rs(nx*rad,22)+tx)*c[4],22)+c[2];sy=rs((rs(ny*rad,22)+ty)*c[5],22)+c[3]
mask=(r2>bound)|(sx<=-256)|(sy<=-256)|(sx>=640*256)|(sy>=480*256)
rgb=remap_fixed(expand(src),np.where(r2>bound,-(1<<23),sx)/256,np.where(r2>bound,-(1<<23),sy)/256).astype(np.uint16)
p=((rgb[...,0]>>3)<<11)|((rgb[...,1]>>2)<<5)|(rgb[...,2]>>3)
tables={bits:np.array([round((v/((1<<bits)-1))**.65*((1<<bits)-1)) for v in range(1<<bits)]) for bits in (5,6)}
expected=((tables[5][p>>11]<<11)|(tables[6][(p>>5)&63]<<5)|tables[5][p&31]).astype('<u2');expected[mask]=0
assert np.array_equal(expected,final)
pair_dir=lab/'gamma-synthetic-pair';pair_dir.mkdir(exist_ok=True)
np.save(pair_dir/'before.npy',p.astype(np.uint16));np.save(pair_dir/'after.npy',final.astype(np.uint16));np.save(pair_dir/'mask.npy',mask)
(pair_dir/'manifest.json').write_text(json.dumps({'source_kind':'synthetic_same_source','source_frame_identity':'gamma-native-tone-frame-2','before_source_frame_identity':'gamma-native-tone-frame-2','after_source_frame_identity':'gamma-native-tone-frame-2','angle_deg':ref['frames'][i]['angle_deg'],'mode':1,'source_reference':'build/gamma_native_tone_sim/reference.json','physical_low_light_capture':False},indent=2)+'\n',encoding='utf-8')
before=expand(p);after=expand(final)
mean=lambda a:float(((77*a[...,0].astype(np.int64)+150*a[...,1].astype(np.int64)+29*a[...,2].astype(np.int64))>>8)[~mask].mean())
plt.rcParams.update({'font.sans-serif':['Microsoft YaHei'],'axes.unicode_minus':False,'text.color':'black'})
fig,axes=plt.subplots(1,2,figsize=(12,5.4),dpi=160)
for ax,img,title in zip(axes,[before,after],['同一矫正图：增强前的独立整数参考','增强后的 RTL 校验结果：Gamma 0.65']):
    ax.imshow(img);ax.set_title(title,fontsize=13);ax.axis('off')
fig.suptitle('640×480 合成暗场回归，角度 −23.45°',fontsize=17)
fig.text(.5,.025,'相机数据经合成降亮；排除几何黑边后平均亮度 '+f'{mean(before):.1f} → {mean(after):.1f}'+'。这是功能回归，未证明真实低光画质改善。',ha='center',fontsize=10)
fig.tight_layout(rect=(0,.065,1,.93));fig.savefig(lab/'gamma-synthetic-native-proof.png');plt.close(fig)
(lab/'gamma-synthetic-preview-check.json').write_text(json.dumps({'passed':True,'hardware_accessed':False,'enhanced_pixels_match_native_rtl_golden':True,'nonmasked_mean_luminance_before':mean(before),'nonmasked_mean_luminance_after':mean(after),'synthetic_source':True,'limits':'Mean brightness redistribution only; no physical low-light recovery, noise, saturation, optical quality or throughput claim.'},indent=2)+'\n')
print('PASS exact synthetic native preview; nonmasked mean luminance:',mean(before),'->',mean(after))
