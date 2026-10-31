"""Strict, bounded PGSIG001 file decoder. Never opens serial/JTAG or hardware.

Example:
 python host/decoder.py capture.bin --golden expected.rgb --width 1920 --height 1080 \
   --session 0x1234 --param 0xabcd --mode 1
An acquisition may skip packets; duplicates/reorder/stale-session are rejected.
"""
from dataclasses import asdict, dataclass
from pathlib import Path
import argparse
import json
import struct
import sys
import zlib

MAGIC = b'PGSIG001'
TAIL = b'SG01'
PACKET_BYTES = 128

class ProtocolError(ValueError):
    pass

class IdentityError(ValueError):
    pass

class GoldenMismatch(ValueError):
    pass

@dataclass(frozen=True)
class Record:
    session_id: int
    scan_epoch: int
    frame_id: int
    param_id: int
    sequence: int
    pixel_count: int
    pixel_crc: int
    dropped: int
    aborted: int
    malformed: int
    width: int
    height: int
    bank: int
    mode: int
    samples: tuple

def sample_coordinates(width, height):
    # Protocol schema, separately implemented from the image oracle.
    return [(0, 0), (width-1, 0), (0, height-1), (width-1, height-1),
            (width//2, height//2), (width//2-1, height//2),
            (width//2, height//2-1), (1, 1)]

def decode_packet(packet):
    if len(packet) != 128 or packet[:8] != MAGIC or packet[124:] != TAIL:
        raise ProtocolError('packet framing')
    if zlib.crc32(packet[:120]) != struct.unpack_from('<I', packet, 120)[0]:
        raise ProtocolError('packet CRC; pixel CRC has not been checked')
    if tuple(packet[8:12]) != (1, 2, 1, 1):
        raise ProtocolError('unsupported version/format/tap/flags')
    if struct.unpack_from('<H', packet, 12)[0] != 128 or packet[14] != 8:
        raise ProtocolError('length/sample count')
    if packet[15] > 1 or packet[60] != 255 or packet[61] & ~3 or packet[62:64] != b'\0\0':
        raise ProtocolError('bank/sample mask/mode/reserved')
    values = struct.unpack_from('<10I', packet, 16)
    if values[0] == 0 or values[2] == 0:
        raise ProtocolError('unknown session or invalid scanner frame ID')
    width, height = struct.unpack_from('<HH', packet, 56)
    if not 4 <= width <= 65535 or not 4 <= height <= 65535 or values[5] != width*height:
        raise ProtocolError('complete pixel count/geometry')
    samples = tuple(struct.unpack_from('<HHBBB', packet, 64+7*i) for i in range(8))
    if [s[:2] for s in samples] != sample_coordinates(width, height):
        raise ProtocolError('sample coordinates')
    return Record(*values, width, height, packet[15], packet[61], samples)

class StreamDecoder:
    """Keep at most 128 undecoded bytes, including across malformed/truncated packets."""
    def __init__(self):
        self.buffer = bytearray()
        self.bad_packets = 0
        self.discarded_bytes = 0
        self.max_buffer = 0

    def feed(self, data):
        result = []
        for value in data:
            self.buffer.append(value)
            self.max_buffer = max(self.max_buffer, len(self.buffer))
            while self.buffer and not MAGIC.startswith(self.buffer[:min(8, len(self.buffer))]):
                del self.buffer[0]
                self.discarded_bytes += 1
            if len(self.buffer) == 128:
                try:
                    record = decode_packet(bytes(self.buffer))
                except ProtocolError:
                    self.bad_packets += 1
                    del self.buffer[0]
                    self.discarded_bytes += 1
                    # Resynchronize on the next full/partial magic already buffered.
                    while self.buffer and not MAGIC.startswith(self.buffer[:min(8, len(self.buffer))]):
                        del self.buffer[0]
                        self.discarded_bytes += 1
                else:
                    result.append(record)
                    self.buffer.clear()
        return result

class SequenceTracker:
    def __init__(self, expected_session):
        if not 0 < expected_session <= 0xffffffff:
            raise IdentityError('a known nonzero fresh acquisition session is required')
        self.expected_session = expected_session
        self.last = None

    def accept(self, record):
        if record.session_id != self.expected_session:
            raise IdentityError('unexpected acquisition/reset session')
        gap = 0
        if self.last is not None:
            old = self.last
            ds = (record.sequence-old.sequence) & 0xffffffff
            de = (record.scan_epoch-old.scan_epoch) & 0xffffffff
            df = (record.frame_id-old.frame_id) & 0xffffffff
            if not 0 < ds < 0x80000000:
                raise IdentityError('duplicate/reordered sequence or ambiguous half-range')
            if not 0 < de < 0x80000000 or df >= 0x80000000:
                raise IdentityError('stale/reordered scan epoch or frame ID')
            if any(getattr(record, k) < getattr(old, k) for k in ('dropped', 'aborted', 'malformed')):
                raise IdentityError('counter rollback: reset needs a new session')
            if df == 0 and (record.param_id, record.mode, record.bank, record.pixel_crc,
                            record.width, record.height, record.samples) != (
                            old.param_id, old.mode, old.bank, old.pixel_crc,
                            old.width, old.height, old.samples):
                raise IdentityError('repeated frame ID changed identity/content')
            gap = ds-1
        self.last = record
        return gap

def compare_golden(record, expected, *, session_id, param_id, mode,
                   frame_id=None, scan_epoch=None, bank=None):
    for name, value in [('session_id', session_id), ('param_id', param_id), ('mode', mode),
                        ('frame_id', frame_id), ('scan_epoch', scan_epoch), ('bank', bank)]:
        if value is not None and getattr(record, name) != value:
            raise IdentityError(f'{name} does not match the requested golden identity')
    differences = [key for key in ('width', 'height', 'pixel_count', 'pixel_crc', 'samples')
                   if getattr(record, key) != expected[key]]
    if differences:
        raise GoldenMismatch('golden mismatch: ' + ', '.join(differences))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--golden', type=Path, required=True)
    parser.add_argument('--width', type=int, required=True)
    parser.add_argument('--height', type=int, required=True)
    parser.add_argument('--golden-format', choices=['rgb888', 'rgb565le'], default='rgb888')
    parser.add_argument('--session', type=lambda s: int(s, 0), required=True)
    parser.add_argument('--param', type=lambda s: int(s, 0), required=True)
    parser.add_argument('--mode', type=lambda s: int(s, 0), required=True)
    parser.add_argument('--frame-id', type=lambda s: int(s, 0))
    parser.add_argument('--scan-epoch', type=lambda s: int(s, 0))
    args = parser.parse_args()
    try:
        from .oracle import from_file
    except ImportError:
        from oracle import from_file
    expected = from_file(args.golden, args.width, args.height, args.golden_format)
    decoder, tracker = StreamDecoder(), SequenceTracker(args.session)
    checked, gaps = 0, 0
    with args.capture.open('rb') as handle:
        while chunk := handle.read(4096):
            for record in decoder.feed(chunk):
                gaps += tracker.accept(record)
                compare_golden(record, expected, session_id=args.session, param_id=args.param,
                               mode=args.mode, frame_id=args.frame_id, scan_epoch=args.scan_epoch)
                checked += 1
                print(json.dumps(asdict(record)))
    report = {'checked_records': checked, 'sequence_gaps': gaps, 'bad_packets': decoder.bad_packets,
              'discarded_bytes': decoder.discarded_bytes, 'trailing_bytes': len(decoder.buffer)}
    print(json.dumps(report))
    if not checked or decoder.bad_packets or decoder.discarded_bytes or decoder.buffer:
        raise SystemExit(2)  # A recovered valid packet does not hide link corruption.

if __name__ == '__main__':
    try:
        main()
    except (IdentityError, GoldenMismatch, ProtocolError) as error:
        print(json.dumps({'status': 'rejected', 'reason': str(error)}), file=sys.stderr)
        raise SystemExit(2)
