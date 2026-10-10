"""Fail closed if the diagnostic SCCB observer differs from tested read-only source."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]

def main():
    work=ROOT/'build/camera_state_scan_sim'
    hashes=json.loads((work/'source-sha256.json').read_text(encoding='utf-8-sig'))
    for name,digest in hashes.items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest().upper()!=digest:
            raise ValueError('Probe simulation input changed: '+name)
    log=(work/'simulation.log').read_text()
    if 'PASS camera state scan:' not in log or re.search(r'(?i)fatal:|error:',log):
        raise ValueError('Read-only scanner regression did not pass')
    top=(ROOT/'board/camera_isp_probe.v').read_text()
    if '.enabled(camera_ready && !camera_failed)' not in top or 'ov5640_state_scan scan(' not in top:
        raise ValueError('Probe was not wired behind initialization readiness')
    print(json.dumps({'passed':True,'read_only_sccb':True,'registers_per_scan':24}))

if __name__=='__main__':main()
