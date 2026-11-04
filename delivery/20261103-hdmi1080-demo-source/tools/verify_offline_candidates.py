"""Check the source-only virtual closures; no EDA or hardware operations."""
from pathlib import Path
import json
from verify_package import ROOT,sha,safe_relative,verify

def verify_candidates():
    verify()
    root=ROOT/'offline-candidates/20261103-night'
    summary=json.loads((root/'SUMMARY.json').read_text(encoding='utf-8'))
    checked=0;deltas=0
    for candidate in summary['candidates']:
        name=candidate['candidate']
        folder=safe_relative(root,name)
        manifest=json.loads((folder/'source-manifest.json').read_text(encoding='utf-8'))
        if len(manifest['files'])!=manifest['source_count']:raise ValueError('Wrong source count')
        if candidate['hardware_acceptance'] or candidate['pure_corrected_hardware_fps'] is not None:
            raise ValueError('Diagnostic candidate promoted without measurement')
        if candidate['identities']['timing_signoff']:raise ValueError('Diagnostic timing marked accepted')
        for row in manifest['files']:
            kind=row['disposition']
            if kind=='external_dependency':
                if row['package_path'] is not None:raise ValueError('External dependency published')
                continue
            if kind not in ['baseline_source','candidate_source']:raise ValueError('Unknown disposition')
            path=safe_relative(ROOT,row['package_path'])
            if path.stat().st_size!=row['bytes'] or sha(path)!=row['sha256']:
                raise ValueError('Source closure missing/changed: '+name+'/'+row['path'])
            if kind=='candidate_source':deltas+=1
            checked+=1
    return {'candidates':len(summary['candidates']),'included_source_references_verified':checked,
            'included_delta_files_verified':deltas,'hardware_accessed':False,'eda_executed':False}

if __name__=='__main__':print(json.dumps(verify_candidates(),indent=2))
