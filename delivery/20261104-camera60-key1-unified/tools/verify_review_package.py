from pathlib import Path
import hashlib,json,re
root=Path(__file__).resolve().parents[1]
rows=json.loads((root/'PACKAGE_FILES.json').read_text(encoding='utf-8'))['files']
expected={r['path'] for r in rows}|{'PACKAGE_FILES.json'}
actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()}
assert actual==expected, 'Missing or unlisted files'
for r in rows:
 b=(root/r['path']).read_bytes()
 assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'],r['path']
 if r['path'].startswith('src/'):
  assert not re.search(rb'[A-Za-z]:[/\\]',b),'Absolute source path'
binding=json.loads((root/'RELEASE_BINDING.json').read_text(encoding='utf-8'))
assert binding['status']=='READY_FOR_ROOT_REVIEW' and binding['root_publish_go'] and binding['remote_review_pending']
bit=root/binding['bit_file']
assert bit.stat().st_size==binding['bit_bytes'] and hashlib.sha256(bit.read_bytes()).hexdigest()==binding['bit_sha256']
print('PASS_REVIEW_PACKAGE',len(rows),'files; no build or hardware operation')
