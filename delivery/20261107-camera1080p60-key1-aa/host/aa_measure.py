"""Strict, read-only measurement of an AA capture. No device access.

Rates use PGSTAT02 hardware time, not UART arrival time or display scan rate.
An operator must independently confirm the capture's uninterrupted reset epoch.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

from aa_protocol import parse

AA_SHA256 = '1665586da54bdbf5ed8cefa7d0bbe35f3cbb0219e03ae060fa68f6dfdb717f8a'
AA_PARAM_ID = 0xadfb7264
CORE_HZ = 125000000
UINT32 = 1 << 32
COUNTERS = ('captured_frames', 'processed_frames', 'presented_frames',
            'scan_repeat_frames', 'dropped_frames')


class WireParser:
    """Incremental parser from a known packet boundary; never resynchronizes."""
    def __init__(self):
        self.buffer = bytearray()
        self.offset = 0

    def feed(self, data):
        self.buffer.extend(data)
        rows = []
        while len(self.buffer) >= 8:
            magic = bytes(self.buffer[:8])
            if magic == b'PGSTAT02':
                size = 84
            elif magic == b'PGSIG001':
                size = 128
            elif magic[:4] == b'SGK1':
                size = 24
            else:
                raise ValueError(f'Unknown packet boundary at byte {self.offset}')
            if len(self.buffer) < size:
                break
            row = parse(bytes(self.buffer[:size]))[0]
            row['Offset'] = self.offset
            rows.append(row)
            del self.buffer[:size]
            self.offset += size
        return rows

    def finish(self):
        if self.buffer:
            raise ValueError(f'Truncated packet at byte {self.offset}')

    def bytes_needed(self):
        """Bytes to finish just the current packet, without consuming its next."""
        if len(self.buffer) < 8:
            return 8 - len(self.buffer)
        magic = bytes(self.buffer[:8])
        size = 84 if magic == b'PGSTAT02' else 128 if magic == b'PGSIG001' else 24
        return size - len(self.buffer)


def command_identity(entry):
    packet = bytes.fromhex(entry['PacketHex'])
    if (len(packet) != 24 or zlib.crc32(packet[:20]) !=
            struct.unpack_from('<I', packet, 20)[0]):
        raise ValueError('Invalid recorded request length/CRC')
    magic, version, domain, size, ticket, nonce, reserved = struct.unpack(
        '<4sBBHIII', packet[:20])
    if ((version, domain, size, reserved) != (1, 1, 24, 0) or
            not ticket or not nonce or magic not in (b'SGA1', b'SGT1')):
        raise ValueError('Invalid recorded request schema')
    if entry.get('Outcome') != 'sent':
        raise ValueError('Request did not complete a full write')
    return magic.decode(), ticket, nonce


def analyze(raw, manifest, *, uninterrupted_reset_epoch=False):
    if not uninterrupted_reset_epoch:
        raise ValueError('Operator must confirm no FPGA reset occurred during capture')
    if manifest.get('Status') != 'complete':
        raise ValueError('Capture is incomplete or failed; preserve raw evidence')
    if not manifest.get('KnownCleanResetBoundaryAttested') or not manifest.get('EpochLabel'):
        raise ValueError('Missing externally established initial packet boundary/reset epoch')
    if manifest.get('LoadedBitstreamSHA256OperatorSupplied') != AA_SHA256:
        raise ValueError('Capture is not identified as the released AA bitstream')
    if hashlib.sha256(raw).hexdigest() != manifest.get('RawSHA256'):
        raise ValueError('Raw capture SHA256 differs from manifest')
    expected_mode = {'raw': 0, 'corr': 1}.get(manifest.get('ExpectedMode'))
    if expected_mode is None:
        raise ValueError('ExpectedMode must be raw or corr')
    commands = [command_identity(e) for e in manifest['Requests']]
    arms = [c for c in commands if c[0] == 'SGA1']
    wanted = [c[1:] for c in commands if c[0] == 'SGT1']
    if len(arms) != 1 or len(wanted) < 2 or len(set(wanted)) != len(wanted):
        raise ValueError('Require one ARM and at least two distinct statistics requests')
    if len({c[2] for c in commands}) != len(commands):
        raise ValueError('Every request must have a fresh nonzero nonce')
    if any(b[1] <= a[1] for a, b in zip(commands, commands[1:])):
        raise ValueError('Request tickets must increase without rollover')
    parser = WireParser()
    rows = parser.feed(raw)
    parser.finish()
    acks = [r['Decoded'] for r in rows if r['Kind'] == 'SGK1']
    _, arm_ticket, arm_nonce = arms[0]
    if (len(acks) != 1 or (acks[0]['Ticket'], acks[0]['Nonce'], acks[0]['Status']) !=
            (arm_ticket, arm_nonce, '01')):
        raise ValueError('Require exactly one matching ARMED acknowledgement')
    if not rows or rows[0]['Kind'] != 'SGK1':
        raise ValueError('Initial quiet session must begin with its ARM acknowledgement')
    stats = [r['Decoded'] for r in rows if r['Kind'] == 'PGSTAT02']
    if [(s['Ticket'], s['Nonce']) for s in stats] != wanted:
        raise ValueError('Missing, duplicate, stale or unrelated statistics response')
    signatures = [r['Decoded'] for r in rows if r['Kind'] == 'PGSIG001']
    if len(signatures) < 2:
        raise ValueError('Need signature freshness crosscheck, not statistics alone')
    for s in stats:
        if (s['NominalCoreHz'] != CORE_HZ or not s['LastCompletionValid'] or
                s['completed_param_id'] != AA_PARAM_ID or s['completed_mode'] != expected_mode or
                not s['completed_frame_id']):
            raise ValueError('Statistics clock/completion/AA parameter/mode mismatch')
        if s['Failed'] or s['CoreFault'] or s['InputFault'] or s['ControllerFault']:
            raise ValueError(f'Fault detail present at ticket {s["Ticket"]}: '
                             f'failed={s["Failed"]}, core=0x{s["CoreFault"]:02x}, '
                             f'input=0x{s["InputFault"]:02x}, controller=0x{s["ControllerFault"]:02x}; '
                             'save first-fault evidence before recovery')
    for f in signatures:
        if (not f['Complete1080'] or f['SessionID'] != arm_nonce or
                f['ParameterID'] != AA_PARAM_ID or f['Mode'] != expected_mode):
            raise ValueError('Signature completeness/session/AA parameter/mode mismatch')
    for a, b in zip(signatures, signatures[1:]):
        if b['Sequence'] <= a['Sequence'] or b['ScanEpoch'] <= a['ScanEpoch']:
            raise ValueError('Signature sequence/scan epoch did not advance without rollover')
        if b['FrameID'] < a['FrameID']:
            raise ValueError('FrameID moved backward or rolled over')
    unique = len({f['FrameID'] for f in signatures})
    if unique < 2:
        raise ValueError('Repeated scans alone are not fresh video frames')
    windows = []
    totals = dict.fromkeys(COUNTERS, 0)
    total_ticks = stats[-1]['CoreTick'] - stats[0]['CoreTick']
    if not 0 < total_ticks < UINT32:
        raise ValueError('Entire measurement must be positive and below 2^32 core cycles')
    for a, b in zip(stats, stats[1:]):
        ticks = b['CoreTick'] - a['CoreTick']
        if not 0 < ticks < UINT32 or b['Sequence'] <= a['Sequence']:
            raise ValueError('Statistics time/sequence moved backward, repeated or rolled over')
        if b['completed_frame_id'] < a['completed_frame_id']:
            raise ValueError('Completed FrameID moved backward or rolled over')
        delta = {k: (b[k] - a[k]) % UINT32 for k in COUNTERS}
        if any(v > ticks for v in delta.values()):
            raise ValueError('Counter delta exceeds one event per core cycle; possible reset')
        for k, v in delta.items():
            totals[k] += v
        windows.append({'FirstTicket': a['Ticket'], 'SecondTicket': b['Ticket'],
                        'CoreCycles': ticks, 'SecondsNominal': ticks / CORE_HZ,
                        'Delta': delta,
                        'NewPresentedFPSNominal': delta['presented_frames'] * CORE_HZ / ticks})
    rates = {k.replace('_frames', '') + '_fps_nominal': v * CORE_HZ / total_ticks
             for k, v in totals.items()}
    return {
        'Schema': 'AA_MEASUREMENT_1', 'EvidenceAcceptedForCalculation': True,
        'HardwarePassClaim': False, 'Sustained60FPSPassClaim': False,
        'ExternalIOTimingCDCOpticalOrLatencyPassClaim': False,
        'Mode': manifest['ExpectedMode'], 'ObservedModeConsistent': True,
        'EpochLabel': manifest['EpochLabel'], 'UninterruptedEpochOperatorAttested': True,
        'LoadedBitstreamIdentitySource': 'operator supplied, not read back from FPGA',
        'RawSHA256': manifest['RawSHA256'], 'NominalCoreHz': CORE_HZ,
        'CoreCycles': total_ticks, 'SecondsNominal': total_ticks / CORE_HZ,
        'Delta': totals, 'Rates': rates, 'Windows': windows,
        'SignatureCrosscheck': {
            'Packets': len(signatures), 'DistinctPresentedFrameIDsObserved': unique,
            'RepeatedFrameIDPackets': len(signatures) - unique,
            'FirstFrameID': signatures[0]['FrameID'], 'LastFrameID': signatures[-1]['FrameID'],
            'DroppedTelemetryMax': max(f['DroppedTelemetry'] for f in signatures),
            'AbortedTelemetryMax': max(f['AbortedTelemetry'] for f in signatures),
            'MalformedTelemetryMax': max(f['MalformedTelemetry'] for f in signatures),
            'Scope': 'UART-delivered samples, not tick-aligned to statistics endpoints'},
        'Scope': 'Source admission, processing completion and new presentation are separate. '
                 'Rates use the declared nominal clock. Unobserved mode changes/reset cannot '
                 'be excluded by packets alone. No end-to-end latency is measured.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('capture_dir', type=Path)
    ap.add_argument('--confirm-uninterrupted-epoch', action='store_true')
    args = ap.parse_args()
    try:
        manifest = json.loads((args.capture_dir / 'capture.json').read_text())
        result = analyze((args.capture_dir / 'camera-uart.raw.bin').read_bytes(), manifest,
                         uninterrupted_reset_epoch=args.confirm_uninterrupted_epoch)
    except (ValueError, KeyError, OSError, TypeError) as error:
        ap.exit(2, f'Rejected: {error}\nRaw capture remains unchanged.\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
