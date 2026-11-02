"""Verify selected original evidence bytes; no PDS, UART or JTAG access."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify(package, summary=None):
    package = Path(package).resolve()
    manifest_path = package/'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    assert manifest['Schema'] == 'camera720-view-toggle-evidence-manifest-v1'
    names = set()
    decoded = {}
    for row in manifest['Files']:
        name = row['File']
        path = (package/name).resolve()
        assert path.is_relative_to(package) and name not in names, 'invalid or duplicate stored path'
        names.add(name)
        stored = path.read_bytes()
        assert len(stored) == row['Bytes'] and sha(stored) == row['SHA256'], name
        assert row['Encoding'] in ('identity','gzip')
        raw = gzip.decompress(stored) if row['Encoding'] == 'gzip' else stored
        assert len(raw) == row['SourceBytes'] and sha(raw) == row['SourceSHA256'], name
        decoded[name.removesuffix('.gz')] = raw
    load = lambda name:json.loads(decoded[name].decode('utf-8-sig'))
    programmed = load('native/program-a/receipt.json')
    assert programmed['Passed'] and programmed['DoneConfirmed'] and programmed['FlashWritten'] is False
    assert programmed['CleanupErrors'] == []
    uart = load('uart/live-a/session.json')
    assert uart['ReceptionAndIdentityPassed'] and uart['UARTTransmitBytes'] == 0
    assert uart['IdentityMismatches'] == uart['RejectedPackets'] == 0
    simulation = load('simulation/camera720-view-toggle-simulation.json')
    assert simulation['Passed'] and simulation['SimulationExecuted']
    assert simulation['ActualScanPixelsCompared'] == 3686400 and simulation['Summary']['final_drain']
    proof = load('evidence/cdc-final-proof-b.json')
    assert proof['ScopedDigitalChecksPassed'] and proof['Missing'] == proof['Violations'] == []
    assert proof['ObservedCases'] == proof['ExpectedCases'] == 2486 and proof['Pins']['TopPortCount'] == 130
    assert sha(decoded['candidate/camera720_view_toggle_top.sbit']) == programmed['Bitstream']['SHA256']
    assert sha(decoded['candidate/camera720_view_toggle_top.adf']) == programmed['CandidateADFSHA256']
    if summary:
        summary = json.loads(Path(summary).read_text(encoding='utf-8'))
        assert summary['EvidenceManifest']['SHA256'] == sha(manifest_path.read_bytes())
        assert summary['CPUChecks']['Failed'] == 0
    return {'Passed':True,'FilesAndDecodedHashesVerified':len(names),'HardwareAccessed':False,
            'Limits':'Selected original evidence integrity and recorded assertions; no new native timing or hardware execution.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--summary',type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.package,args.summary)))
