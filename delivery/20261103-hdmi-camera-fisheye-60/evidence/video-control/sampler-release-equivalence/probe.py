from pathlib import Path
import argparse,hashlib,json,os,re,subprocess,time
p=argparse.ArgumentParser();p.add_argument('--work',type=Path,default=Path('D:/f60-work/video/sampler-release-proof'));args=p.parse_args()
P=Path('D:/f60/delivery/20261103-hdmi-camera-fisheye-60');W=args.work;W.mkdir(exist_ok=False)
src=P/'rtl/hdmi_camera_pixel_sampler.v';quant=Path('D:/f60/distortion/rtl/experimental/hdmi_camera_rgb565_quantizer.v')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
old=src.read_text();(W/'old.v').write_text(old.replace('module hdmi_camera_pixel_sampler','module hdmi_camera_pixel_sampler_old'),encoding='utf-8')
new=old.replace('module hdmi_camera_pixel_sampler','module hdmi_camera_pixel_sampler_new').replace('reg [1:0] p_reset=0','reg [2:0] p_reset=0').replace("p_reset<={p_reset[0],1'b1}","p_reset<={p_reset[1:0],1'b1}")
new=re.sub(r'    \(\* syn_preserve=1, syn_srlstyle="registers" \*\) reg sample_valid_hold;\n','',new)
new=new.replace(';sample_valid_hold<=0','').replace('            sample_valid_hold<=1;\n','').replace('p_reset[1] && sample_valid_hold','p_reset[2]')
assert 'sample_valid_hold' not in new
(W/'new.v').write_text(new,encoding='utf-8')
bench=Path('D:/f60-work/video/tb_sampler_release_equivalence.sv');shutil_path=W/'test.sv';shutil_path.write_bytes(bench.read_bytes())
files=[W/'old.v',W/'new.v',quant,shutil_path];snap={str(f):sha(f) for f in [src,quant,bench,*files]}
report={'scope':'Independent old/new digital equivalence experiment; live RTL unchanged; no native timing claim','passed':False,'source_sha256':snap,'commands':[]}
tmp=W/'temp';tmp.mkdir();env=dict(os.environ,TEMP=str(tmp),TMP=str(tmp));v=Path('D:/Vicado/Vivado/2017.4/bin')
try:
 for command in [['xvlog.bat','--sv',*map(str,files)],['xelab.bat','tb_sampler_release_equivalence','-s','sampler'],['xsim.bat','sampler','-runall']]:
  start=time.monotonic();r=subprocess.run([str(v/command[0]),*command[1:]],cwd=W,env=env,capture_output=True,text=True,timeout=240);out=r.stdout+r.stderr;log=W/(command[0]+'.log');log.write_text(out,encoding='utf-8');report['commands'].append({'argv':command,'returncode':r.returncode,'seconds':time.monotonic()-start,'log_sha256':sha(log)})
  if r.returncode or re.search(r'(?im)^\s*(error|fatal)(?:\s|:|\[)',out):raise RuntimeError(out[-5000:])
 if 'PASS SAMPLER RELEASE EQUIVALENCE' not in out:raise RuntimeError(out[-3000:])
 assert all(sha(Path(path))==h for path,h in snap.items()),'source drift'
 report['passed']=True;report['coverage']=json.loads((W/'coverage.json').read_text())
finally:(W/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report['coverage'],indent=2))
