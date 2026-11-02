"""Verify packaged copies and replay saved UART bytes; no hardware or EDA access."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    manifest = read(ROOT/'manifest.json')
    expected = set()
    for row in manifest['Files']:
        name = row['Path']
        path = ROOT/name
        require(not Path(name).is_absolute() and path.resolve().is_relative_to(ROOT), 'invalid manifest path')
        require(name not in expected, 'duplicate manifest path')
        expected.add(name)
        require(path.is_file() and path.stat().st_size == row['Bytes'] and digest(path) == row['SHA256'], 'copy drift: '+name)
    actual = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file() and p.name != 'manifest.json' and '__pycache__' not in p.parts}
    require(actual == expected, 'bundle inventory differs')
    originals = read(ROOT/'copied-originals.json')['Files']
    for row in originals:
        require(row['CopiedWithoutModification'] and digest(ROOT/row['Path']) == row['SHA256'], 'original copy differs')
    bit = read(ROOT/'bit/verification.json')
    program = read(ROOT/'program/receipt.json')
    status = read(ROOT/'status.json')
    bit_path = ROOT/'bit/generate_bitstream/camera720_calibrated_stats_delay_top.sbit'
    require(bit['Verified'] and program['Passed'] and program['DoneConfirmed'] and not program['FlashWritten'], 'bit/program receipt not passed')
    require(bit['Bitstream']['SHA256'] == program['Bitstream']['SHA256'] == status['BitstreamSHA256'] == digest(bit_path), 'bit/program identity differs')
    require(bit['CandidateADFSHA256'] == program['CandidateADFSHA256'] == status['CandidateADFSHA256'], 'candidate differs')
    cdc = read(ROOT/'evidence/cdc-final-proof-c.json')
    require(cdc['CandidateADFSHA256'] == status['CandidateADFSHA256'], 'CDC candidate differs')
    require(cdc['ExpectedCases'] == cdc['ObservedCases'] == 2486 and cdc['Missing'] == cdc['Violations'] == [] and cdc['ScopedDigitalChecksPassed'], 'CDC summary differs')
    source = read(ROOT/'evidence/source-c/source-plan.json')
    require(source['BuildID'] == status['BuildID'] and source['ProfileID'] == status['ProfileID'], 'source labels differ')
    spec = importlib.util.spec_from_file_location('packaged_camera720_stats', ROOT/'tools/camera720_stats.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    captures = []
    for name in ('30s','120s'):
        base = ROOT/'uart'/name
        session = read(base/'session.json')
        require(session['ReceptionAndIdentityPassed'] and session['SourceDrift'] == [], 'capture receipt not passed')
        for artifact, row in session['Artifacts'].items():
            require(Path(artifact).name == artifact and digest(base/artifact) == row['SHA256'], 'UART artifact differs')
        replay = module.read_file(base/'received-wire.bin', session['NominalCoreHz'])
        require(replay['RejectedPackets'] == replay['DiscardedBytes'] == replay['TrailingPartialBytes'] == 0, 'UART decoder rejected saved bytes')
        records = replay['Records']
        saved = [json.loads(line)['Packet'] for line in (base/'packets.jsonl').read_text().splitlines()]
        require(records == saved and len(records) == session['CompletePackets'], 'replayed packets differ')
        require(all(r['BuildID'] == status['BuildID'] and r['ProfileID'] == status['ProfileID'] for r in records), 'UART labels differ')
        intervals = replay['Intervals']
        saved_windows = [json.loads(line)['Rates'] for line in (base/'windows.jsonl').read_text().splitlines()]
        require(intervals == saved_windows, 'replayed rate windows differ')
        require(all(r['RatesAvailable'] and r['SequenceDelta'] == 1 for r in intervals), 'invalid or missing telemetry sequence')
        ticks = sum(r['CoreTickDelta'] for r in intervals)
        frames = {k: sum(r['FrameDeltas'][k] for r in intervals) for k in ('SourceAccepted','Processed','UniquePresented')}
        aggregate = session['SelectedWindows']
        require(ticks == aggregate['CoreTicks'] and frames == aggregate['FrameDeltas'] and len(intervals) == aggregate['Count'], 'replayed aggregate differs')
        rates = {k+'FPS': frames[k] / (ticks/session['NominalCoreHz']) for k in frames}
        require(all(v == aggregate[k] == 15.0 for k,v in rates.items()), 'FPS aggregate differs')
        captures.append({'Capture':name,'Packets':len(records),'ValidWindows':len(intervals),'FrameDeltas':frames,**rates})
    return {'BundleCopiesVerified':True,'Files':len(expected),'CopiedOriginals':len(originals),
            'BitstreamSHA256':digest(bit_path),'CDCRecordedCases':2486,'UARTOfflineReplay':captures,
            'HardwareAccessed':False,'EDAExecuted':False,'FullPhysicalAuditReplayed':False,
            'Limits':'Copy verification and saved UART replay only; not a new board test, physical closure, optical acceptance, or independent time measurement.'}


if __name__ == '__main__':
    print(json.dumps(verify(), ensure_ascii=False, indent=2))
