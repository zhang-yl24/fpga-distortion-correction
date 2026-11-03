from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parent
def verify():
    files=json.loads((ROOT/'PACKAGE_FILES.json').read_text(encoding='utf-8'))
    for r in files:
        b=(ROOT/r['path']).read_bytes()
        assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256'],r['path']
    binding=json.loads((ROOT/'SOURCE_BINDING.json').read_text(encoding='utf-8'))
    assert binding['native_inputs']==147 and len(binding['exports'])==66 and len(binding['dependencies'])==83
    for r in binding['exports']:
        assert hashlib.sha256((ROOT/r['export']).read_bytes()).hexdigest()==r['export_sha256']
    s=json.loads((ROOT/'STATUS.json').read_text(encoding='utf-8'))
    assert s['bit_sha256']=='99f8a734161364618e18800de2ebdc01f4c7261c2c6579a8be2b11df870708a9'
    assert s['board']['NewProcessedDelta']==s['board']['NewPresentedDelta']==1890
    assert all(v['FailingEndpoints']==0 for c in s['timing'].values()for v in c.values())
    assert not s['global_physical_signoff'] and s['optical_E2E'] is None
    return {'published_project_inputs':66,'external_dependencies':83,'all_payload_hashes':True,'hardware_or_EDA_run':False}
if __name__=='__main__':print(json.dumps(verify()))
