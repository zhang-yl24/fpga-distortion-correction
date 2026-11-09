"""Strict, read-only measurement of an AA capture. No device access.

Rates use PGSTAT02 hardware time, not UART arrival time or display scan rate.
An operator must independently confirm the capture's uninterrupted reset epoch.
"""
import argparse
import hashlib
import io
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


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def analyze_stream(stream, manifest, *, uninterrupted_reset_epoch=False):
    """Read bounded chunks; accept only after EOF, tail and full hash checks.

    Signature aggregation uses constant memory. Per-statistics-window output
    grows with requests, not the much larger number of decoded video packets.
    """
    if not uninterrupted_reset_epoch:
        raise ValueError('Operator must confirm no FPGA reset occurred during capture')
    if manifest.get('Status') != 'complete':
        raise ValueError('Capture is incomplete or failed; preserve raw evidence')
    if not manifest.get('KnownCleanResetBoundaryAttested') or not manifest.get('EpochLabel'):
        raise ValueError('Missing externally established initial packet boundary/reset epoch')
    if manifest.get('LoadedBitstreamSHA256OperatorSupplied') != AA_SHA256:
        raise ValueError('Capture is not identified as the released AA bitstream')
    expected_mode = {'raw': 0, 'corr': 1}.get(manifest.get('ExpectedMode'))
    if expected_mode is None:
        raise ValueError('ExpectedMode must be raw or corr')
    commands = [command_identity(e) for e in manifest['Requests']]
    arms = [c for c in commands if c[0] == 'SGA1']
    wanted = [c[1:] for c in commands if c[0] == 'SGT1']
    if len(arms) != 1 or len(wanted) < 2 or len(set(wanted)) != len(wanted):
        raise ValueError('Require one ARM and at least two distinct statistics requests')
    if commands[0][0] != 'SGA1':
        raise ValueError('ARM must be the first recorded request')
    if len({c[2] for c in commands}) != len(commands):
        raise ValueError('Every request must have a fresh nonzero nonce')
    if any(b[1] <= a[1] for a, b in zip(commands, commands[1:])):
        raise ValueError('Request tickets must increase without rollover')
    _, arm_ticket, arm_nonce = arms[0]
    parser = WireParser()
    digest = hashlib.sha256()
    packet_count = ack_count = stats_count = signature_count = unique = 0
    first_signature = previous_signature = previous_stats = None
    telemetry_max = dict.fromkeys(('DroppedTelemetry', 'AbortedTelemetry', 'MalformedTelemetry'), 0)
    windows = []
    totals = dict.fromkeys(COUNTERS, 0)
    total_ticks = 0
    for block in iter(lambda: stream.read(4096), b''):
        digest.update(block)
        for row in parser.feed(block):
            if packet_count == 0 and row['Kind'] != 'SGK1':
                raise ValueError('Initial quiet session must begin with its ARM acknowledgement')
            packet_count += 1
            value = row['Decoded']
            if row['Kind'] == 'SGK1':
                ack_count += 1
                if (ack_count != 1 or (value['Ticket'], value['Nonce'], value['Status']) !=
                        (arm_ticket, arm_nonce, '01')):
                    raise ValueError('Require exactly one matching ARMED acknowledgement')
            elif row['Kind'] == 'PGSTAT02':
                s = value
                if stats_count >= len(wanted) or (s['Ticket'], s['Nonce']) != wanted[stats_count]:
                    raise ValueError('Missing, duplicate, stale or unrelated statistics response')
                stats_count += 1
                if (s['NominalCoreHz'] != CORE_HZ or not s['LastCompletionValid'] or
                        s['completed_param_id'] != AA_PARAM_ID or s['completed_mode'] != expected_mode or
                        not s['completed_frame_id']):
                    raise ValueError('Statistics clock/completion/AA parameter/mode mismatch')
                if s['Failed'] or s['CoreFault'] or s['InputFault'] or s['ControllerFault']:
                    raise ValueError(f'Fault detail present at ticket {s["Ticket"]}: '
                                     f'failed={s["Failed"]}, core=0x{s["CoreFault"]:02x}, '
                                     f'input=0x{s["InputFault"]:02x}, controller=0x{s["ControllerFault"]:02x}; '
                                     'save first-fault evidence before recovery')
                if previous_stats is not None:
                    a = previous_stats
                    ticks = s['CoreTick'] - a['CoreTick']
                    if not 0 < ticks < UINT32 or s['Sequence'] <= a['Sequence']:
                        raise ValueError('Adjacent measurement time/sequence must advance without rollover '
                                         'and remain strictly below 2^32 core cycles')
                    if s['completed_frame_id'] < a['completed_frame_id']:
                        raise ValueError('Completed FrameID moved backward or rolled over')
                    delta = {k: (s[k] - a[k]) % UINT32 for k in COUNTERS}
                    if any(v > ticks for v in delta.values()):
                        raise ValueError('Counter delta exceeds one event per core cycle; possible reset')
                    for k, v in delta.items():
                        totals[k] += v
                    total_ticks += ticks
                    windows.append({'FirstTicket': a['Ticket'], 'SecondTicket': s['Ticket'],
                                    'CoreCycles': ticks, 'SecondsNominal': ticks / CORE_HZ,
                                    'Delta': delta,
                                    'NewPresentedFPSNominal': delta['presented_frames'] * CORE_HZ / ticks})
                previous_stats = s
            else:
                f = value
                if (not f['Complete1080'] or f['SessionID'] != arm_nonce or
                        f['ParameterID'] != AA_PARAM_ID or f['Mode'] != expected_mode):
                    raise ValueError('Signature completeness/session/AA parameter/mode mismatch')
                if previous_signature is not None:
                    a = previous_signature
                    if f['Sequence'] <= a['Sequence'] or f['ScanEpoch'] <= a['ScanEpoch']:
                        raise ValueError('Signature sequence/scan epoch did not advance without rollover')
                    if f['FrameID'] < a['FrameID']:
                        raise ValueError('FrameID moved backward or rolled over')
                if previous_signature is None or f['FrameID'] != previous_signature['FrameID']:
                    unique += 1
                signature_count += 1
                if first_signature is None:
                    first_signature = f
                previous_signature = f
                for key in telemetry_max:
                    telemetry_max[key] = max(telemetry_max[key], f[key])
    parser.finish()
    if digest.hexdigest() != manifest.get('RawSHA256'):
        raise ValueError('Raw capture SHA256 differs from manifest')
    if ack_count != 1:
        raise ValueError('Require exactly one matching ARMED acknowledgement')
    if stats_count != len(wanted):
        raise ValueError('Missing, duplicate, stale or unrelated statistics response')
    if signature_count < 2:
        raise ValueError('Need signature freshness crosscheck, not statistics alone')
    if unique < 2:
        raise ValueError('Repeated scans alone are not fresh video frames')
    rates = {k.replace('_frames', '') + '_fps_nominal': v * CORE_HZ / total_ticks
             for k, v in totals.items()}
    return {
        'Schema': 'AA_MEASUREMENT_2', 'EvidenceAcceptedForCalculation': True,
        'HardwarePassClaim': False, 'Sustained60FPSPassClaim': False,
        'ExternalIOTimingCDCOpticalOrLatencyPassClaim': False,
        'Mode': manifest['ExpectedMode'], 'ObservedModeConsistent': True,
        'EpochLabel': manifest['EpochLabel'], 'UninterruptedEpochOperatorAttested': True,
        'LoadedBitstreamIdentitySource': 'operator supplied, not read back from FPGA',
        'RawSHA256': manifest['RawSHA256'], 'NominalCoreHz': CORE_HZ,
        'CoreCycles': total_ticks, 'SecondsNominal': total_ticks / CORE_HZ,
        'CounterDeltaScope': 'Sum of individually checked adjacent uint32 modular windows',
        'AllCounterWindowsBelowUINT32Wrap': True,
        'Delta': totals, 'Rates': rates, 'Windows': windows,
        'SignatureCrosscheck': {
            'Packets': signature_count, 'DistinctPresentedFrameIDsObserved': unique,
            'RepeatedFrameIDPackets': signature_count - unique,
            'FirstFrameID': first_signature['FrameID'], 'LastFrameID': previous_signature['FrameID'],
            'DroppedTelemetryMax': telemetry_max['DroppedTelemetry'],
            'AbortedTelemetryMax': telemetry_max['AbortedTelemetry'],
            'MalformedTelemetryMax': telemetry_max['MalformedTelemetry'],
            'Scope': 'UART-delivered samples, not tick-aligned to statistics endpoints'},
        'Scope': 'Source admission, processing completion and new presentation are separate. '
                 'Rates use the declared nominal clock. Unobserved mode changes/reset cannot '
                 'be excluded by packets alone. No end-to-end latency is measured.'}


def analyze(raw, manifest, *, uninterrupted_reset_epoch=False):
    """Compatibility entry point for already-held bytes; parsing remains chunked."""
    return analyze_stream(io.BytesIO(raw), manifest,
                          uninterrupted_reset_epoch=uninterrupted_reset_epoch)


def analyze_file(path, manifest, *, uninterrupted_reset_epoch=False):
    with Path(path).open('rb') as stream:
        return analyze_stream(stream, manifest,
                              uninterrupted_reset_epoch=uninterrupted_reset_epoch)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('capture_dir', type=Path)
    ap.add_argument('--confirm-uninterrupted-epoch', action='store_true')
    args = ap.parse_args()
    try:
        manifest = json.loads((args.capture_dir / 'capture.json').read_text())
        result = analyze_file(args.capture_dir / 'camera-uart.raw.bin', manifest,
                              uninterrupted_reset_epoch=args.confirm_uninterrupted_epoch)
    except (ValueError, KeyError, OSError, TypeError) as error:
        ap.exit(2, f'Rejected: {error}\nRaw capture remains unchanged.\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
