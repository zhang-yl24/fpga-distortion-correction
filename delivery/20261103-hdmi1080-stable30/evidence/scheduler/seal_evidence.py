from pathlib import Path
import json,hashlib,shutil,csv
root=Path('D:/fpga-stable/scheduler'); final=root/'system-three-final'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
verified=json.loads((final/'verification.json').read_text())
assert verified['passed'] and verified['source_bank_mask']==7
for name,digest in verified['evidence_sha256'].items():assert sha(final/name)==digest,name
bindings=json.loads((final/'compile-sources.json').read_text())
for item in bindings['sources']:assert sha(item['path'])==item['sha256'],item['path']
preparation=Path('D:/fpga-stable/build/stable-a/preparation.json')
prepared=json.loads(preparation.read_text())
headers={}
for item in prepared['files']:
 if item['path'].endswith('.vh'):
  p=preparation.parent/'native'/item['path']
  assert sha(p)==item['compile_sha256'],str(p)
  headers[item['path']]=item['compile_sha256']
(root/'included-header-bindings.json').write_text(json.dumps({'basis':'Included native headers checked against the integration preparation manifest created before compilation','preparation_sha256':sha(preparation),'headers':headers},indent=2)+'\n')
frames=list(csv.DictReader((final/'frames.csv').open(newline='')))
assert len(frames)==8
assert [int(r['source_bank']) for r in frames]==[0,1,0,2,1,0,2,1]
assert frames[3]['source_crc32']!=frames[6]['source_crc32']
assert frames[3]['scan_crc32']!=frames[6]['scan_crc32']
manifest=json.loads((root/'overlay-manifest.json').read_text())
for name,hashes in manifest.items():
 assert sha(root/'overlay'/name)==hashes['candidate_sha256'],name
 assert sha(Path('D:/fpga-build/both-final/native')/name)==hashes['base_sha256'],name
core_relative='source/build/offline-20261024/geometry-bypass-parallel-20261029-coordination/lens1080_bank_core_geometry_bypass.v'
original_core=Path('D:/fpga-build/both-final/native')/core_relative
assert (root/'bank-current.v').read_text()==original_core.read_text()
(root/'scheduler-source-bindings.json').write_text(json.dumps({'baseline_original_sha256':sha(original_core),'baseline_compiled_copy_sha256':sha(root/'bank-current.v'),'baseline_newline_normalized_text_equal':True,'candidate_compiled_copy_sha256':sha(root/'bank-three.v'),'candidate_overlay_sha256':manifest[core_relative]['candidate_sha256'],'engine_stub_sha256':sha(root/'engine-stub.v'),'bench_sha256':sha(root/'tb_scheduler.sv')},indent=2)+'\n')
assert sha(root/'bank-three.v')==manifest['source/build/offline-20261024/geometry-bypass-parallel-20261029-coordination/lens1080_bank_core_geometry_bypass.v']['candidate_sha256']
rows=json.loads((root/'scheduler-results.json').read_text());assert len(rows)==30
for r in rows:
 log=(root/f"sim{r['banks']}"/f"p{r['process']}-phase{r['phase']}.log").read_text()
 assert 'Fatal:' not in log and f"STUB_PROCESS={r['process']}" in log and r['measured_process']==r['process']+1
 if r['banks']==3:assert r['shown']==240 and r['no_bank']==0 and r['repeats']==0
for r in json.loads((root/'boundary-results.json').read_text()):
 log=(root/'sim3'/f"boundary-p{r['process']}-out{r['out_period']}-phase{r['phase']}.log").read_text()
 assert 'Fatal:' not in log and f"STUB_PROCESS={r['process']}" in log and r['measured_process']==r['process']+1
out=root/'evidence-frozen';out.mkdir(exist_ok=False)
files=[p for p in root.iterdir() if p.suffix in ('.md','.py','.sv','.v','.json')]
files+=[p for p in (root/'overlay').rglob('*') if p.is_file()]
for name in ('sim2','sim3'):
 files+=list((root/name).glob('p*.log'))+list((root/name).glob('boundary-*.log'))+[root/name/'compile.log',root/name/'elaborate.log']
for name in ('dma-three','link-three'):files+=[root/name/f'{i}.log' for i in range(3)]
for name in ('system-small','system-three-final'):
 files+=[p for p in (root/name).iterdir() if p.suffix in ('.sv','.mem','.vh','.csv','.json') or p.name in ('compile.log','elaborate.log','simulate.log','compile-paths.txt')]
digests={}
for p in sorted(set(files)):
 relative=p.relative_to(root);dest=out/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest);assert sha(p)==sha(dest)
 digests[relative.as_posix()]={'sha256':sha(dest),'bytes':dest.stat().st_size}
(out/'evidence-manifest.json').write_text(json.dumps({'scope':'Frozen scheduling, DMA/link and 32x16 real-system digital evidence; no native 1080p FPS/PHY/STA claim','files':digests},indent=2)+'\n')
print('FROZEN',out,'files',len(digests),'manifest SHA256',sha(out/'evidence-manifest.json'))
