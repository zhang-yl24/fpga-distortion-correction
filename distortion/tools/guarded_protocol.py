"""Version-two guarded commands/status and boundary-safe mixed UART decoding.

These checks provide framing, integrity and replay discipline, not cryptographic
authentication, physical identity or exposure timestamps. The original PGFRAME1
implementation is reused unchanged for pixel packets.
"""
from enum import IntEnum
from pathlib import Path
import json
import struct
import sys
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from frame_protocol import FrameParser, HEADER, MAGIC as FRAME_MAGIC, END as FRAME_END, FORMAT as FRAME_FORMAT

CORE_HZ = 125000000
BUILD_TAG = 0x52473201
CAM1_BUILD_TAG = 0x52473101
CAM2_BARS_BUILD_TAG = 0x52473242
CAM1_SCCB25_BUILD_TAG = 0x52473125
CAM1_ISOLATED_BUILD_TAG = 0x52473149
DECLARED_BUILD_TAGS = {'CAM2': BUILD_TAG, 'CAM1': CAM1_BUILD_TAG,
                       'CAM2_BARS': CAM2_BARS_BUILD_TAG, 'CAM1_SCCB25': CAM1_SCCB25_BUILD_TAG,
                       'CAM1_ISOLATED': CAM1_ISOLATED_BUILD_TAG}
STATUS_MAGIC = b'PGSTAT02'
STATUS_END = b'ST02'


class Opcode(IntEnum):
    OPEN = 0x0F
    GRANT = 0x10
    STOP = 0x11
    QUERY = 0x12


class Result(IntEnum):
    NONE = 0x00
    ACCEPTED = 0x01
    DUPLICATE = 0x02
    BAD_VERSION = 0x10
    BAD_CRC = 0x11
    RX_FRAMING = 0x12
    RX_TIMEOUT = 0x13
    NO_SESSION = 0x20
    SESSION_MISMATCH = 0x21
    OLD_SEQ = 0x22
    SEQ_CONFLICT = 0x23
    BAD_OPCODE = 0x30
    BAD_ARG = 0x31
    NOT_IDLE = 0x32
    FAULT = 0x33
    NOT_READY = 0x34
    GRANT_REJECTED = 0x35
    GRANT_TIMEOUT = 0x36
    BUSY = 0x37


class StopReason(IntEnum):
    NONE = 0
    FRAME_BUDGET = 1
    LEASE_EXPIRED = 2
    OPERATOR_STOP = 3
    INTERLOCK = 4
    CORE_FAULT = 5
    INVALID_GRANT = 6


FLAG_NAMES = ('camera_ready', 'ddr_ready', 'warmup_ready', 'safety_ok', 'armed', 'inflight',
    'bank_locked', 'raw_failed', 'requires_reset', 'draining', 'temp_valid', 'temp_failed',
    'temp_over_temp', 'temp_stale', 'camera_failed', 'core_idle')
STATUS_FIELDS = (
    ('uptime_ms', 16, 'I'), ('session_id', 20, 'I'), ('last_received_seq', 24, 'H'),
    ('last_accepted_seq', 26, 'H'), ('last_opcode', 28, 'B'), ('last_result', 29, 'B'), ('flag_bits', 30, 'H'),
    ('accepted_commands', 32, 'I'), ('rejected_commands', 36, 'I'), ('duplicate_commands', 40, 'I'), ('rx_errors', 44, 'I'),
    ('admitted_frames', 48, 'I'), ('completed_frames', 52, 'I'), ('remaining_frames', 56, 'I'),
    ('remaining_cycles', 60, 'I'), ('held_frame_id', 64, 'I'), ('source_crc32', 68, 'I'), ('written_beats', 72, 'I'),
    ('temperature_raw', 76, 'H'), ('temperature_code', 78, 'H'), ('temperature_age_27mhz', 80, 'I'),
    ('temperature_samples', 84, 'I'), ('temperature_conversions', 88, 'I'), ('sensor_id', 92, 'H'),
    ('camera_error', 94, 'B'), ('raw_fault', 95, 'B'), ('camera_failed_address', 96, 'H'),
    ('camera_observed', 98, 'B'), ('camera_expected', 99, 'B'), ('camera_writes', 100, 'H'), ('camera_noacks', 102, 'H'),
    ('stop_reason', 104, 'B'), ('raw_state', 105, 'B'), ('adc_fault', 106, 'B'), ('adc_alarm', 107, 'B'),
    ('snapshot_seq', 108, 'I'), ('safety_snapshot_age_core', 112, 'I'),
    ('requested_frames', 116, 'H'), ('lease_ms', 118, 'H'),
)
GUARDED_CONTROL_CONTRACT = {
    'protocol': 'PGGUARD02', 'version': 2, 'command_magic': 'A55A', 'command_bytes': 16,
    'command_crc': 'CRC16/CCITT-FALSE', 'command_crc_cover_start': 2, 'command_crc_cover_end_exclusive': 14,
    'status_magic': 'PGSTAT02', 'status_bytes': 128, 'status_crc': 'CRC32-IEEE',
    'status_crc_cover_start': 0, 'status_crc_cover_end_exclusive': 120, 'status_trailer': 'ST02',
    'build_tag': BUILD_TAG, 'core_clock_hz': CORE_HZ, 'max_grant_frames': 3, 'max_lease_ms': 24000,
    'sequence_policy': 'same_session_half_range_forward_consumes_semantic_rejections',
    'grant_ack_policy': 'actual_lease_feedback_only', 'open_policy': 'idle_no_fault_nonzero_session',
    'query_renews_lease': False, 'cryptographic_authentication': False,
}


def crc16_ccitt_false(data):
    crc = 0xFFFF
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ (0x1021 if crc & 0x8000 else 0)) & 0xFFFF
    return crc


def _uint(value, bits, name):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < (1 << bits):
        raise ValueError(name+' must be an unsigned '+str(bits)+'-bit integer')
    return value


def encode_command(opcode, seq, session, arg=0):
    body = struct.pack('<BBHII', 2, _uint(opcode, 8, 'opcode'), _uint(seq, 16, 'seq'),
                       _uint(session, 32, 'session'), _uint(arg, 32, 'arg'))
    return b'\xA5\x5A'+body+struct.pack('<H', crc16_ccitt_false(body))


def grant_argument(frames, lease_ms):
    if type(frames) is not int or not 1 <= frames <= 3 or type(lease_ms) is not int or not 1 <= lease_ms <= 24000:
        raise ValueError('grant requires 1..3 frames and 1..24000 milliseconds')
    return (lease_ms << 8) | frames


def encode_open(seq, session):
    if session == 0:
        raise ValueError('OPEN requires a nonzero session')
    return encode_command(Opcode.OPEN, seq, session)


def encode_grant(seq, session, frames, lease_ms):
    return encode_command(Opcode.GRANT, seq, session, grant_argument(frames, lease_ms))


def encode_stop(seq, session):
    return encode_command(Opcode.STOP, seq, session)


def encode_query(seq, session):
    return encode_command(Opcode.QUERY, seq, session)


def decode_command(data):
    if len(data) != 16 or data[:2] != b'\xA5\x5A':
        raise ValueError('guarded command must be exactly 16 bytes with A55A magic')
    if crc16_ccitt_false(data[2:14]) != struct.unpack_from('<H', data, 14)[0]:
        raise ValueError('guarded command CRC16 mismatch')
    version, opcode, seq, session, arg = struct.unpack_from('<BBHII', data, 2)
    if version != 2:
        raise ValueError('only guarded command version 2 is supported')
    return {'version': version, 'opcode': opcode, 'seq': seq, 'session': session, 'arg': arg,
            'requested_frames': arg & 255, 'lease_ms': arg >> 8}


def _build_tag(value):
    _uint(value, 32, 'build_tag')
    if value not in DECLARED_BUILD_TAGS.values():
        raise ValueError('only explicitly declared guarded build tags are supported')
    return value


def decode_status(data, expected_build_tag=BUILD_TAG):
    expected_build_tag = _build_tag(expected_build_tag)
    if len(data) != 128 or data[:8] != STATUS_MAGIC or data[124:] != STATUS_END:
        raise ValueError('PGSTAT02 status length/magic/trailer mismatch')
    length, version, tag = struct.unpack_from('<HHI', data, 8)
    if length != 128 or version != 2 or tag != expected_build_tag:
        raise ValueError('status schema/build tag mismatch')
    if zlib.crc32(data[:120]) != struct.unpack_from('<I', data, 120)[0]:
        raise ValueError('status CRC32 mismatch')
    result = {name: struct.unpack_from('<'+kind, data, offset)[0] for name, offset, kind in STATUS_FIELDS}
    result.update(version=version, length=length, build_tag=tag)
    result['flags'] = {name: bool(result['flag_bits'] & (1 << index)) for index, name in enumerate(FLAG_NAMES)}
    result['last_result_name'] = Result(result['last_result']).name if result['last_result'] in Result._value2member_map_ else 'UNKNOWN'
    result['remaining_lease_ms_ceil'] = (result['remaining_cycles']+124999)//125000
    result['frame_id_is_sensor_exposure_counter'] = False
    return result


def encode_status(fields, build_tag=BUILD_TAG):
    """Synthetic/golden packet builder; this does not establish hardware provenance."""
    build_tag = _build_tag(build_tag)
    data = bytearray(128)
    data[:8] = STATUS_MAGIC
    struct.pack_into('<HHI', data, 8, 128, 2, build_tag)
    for name, offset, kind in STATUS_FIELDS:
        value = fields.get(name, 0)
        struct.pack_into('<'+kind, data, offset, _uint(value, struct.calcsize(kind)*8, name))
    struct.pack_into('<I', data, 120, zlib.crc32(data[:120]))
    data[124:] = STATUS_END
    return bytes(data)


class GuardedStreamParser:
    """Parse only packet boundaries; a valid frame header owns its whole payload."""
    def __init__(self, expected_build_tag=BUILD_TAG):
        self.expected_build_tag = _build_tag(expected_build_tag)
        self.buffer = bytearray()
        self.rejected = 0
        self.discarded = 0

    def feed(self, data):
        self.buffer.extend(data)
        events = []
        while True:
            positions = [(self.buffer.find(magic), magic) for magic in (STATUS_MAGIC, FRAME_MAGIC)]
            positions = [(where, magic) for where, magic in positions if where >= 0]
            if not positions:
                count = max(0, len(self.buffer)-7)
                self.discarded += count
                del self.buffer[:count]
                break
            where, magic = min(positions, key=lambda item: item[0])
            if where:
                self.discarded += where
                del self.buffer[:where]
            if magic == STATUS_MAGIC:
                if len(self.buffer) < 16:
                    break
                if struct.unpack_from('<HHI', self.buffer, 8) != (128, 2, self.expected_build_tag):
                    self.rejected += 1
                    del self.buffer[0]
                    continue
                if len(self.buffer) < 128:
                    break
                packet = bytes(self.buffer[:128])
                try:
                    status = decode_status(packet, expected_build_tag=self.expected_build_tag)
                except ValueError:
                    self.rejected += 1
                    del self.buffer[0]
                    continue
                events.append({'kind': 'status', 'status': status, 'wire': packet})
                del self.buffer[:128]
            else:
                if len(self.buffer) < 32:
                    break
                _, width, height, ident, count, source, fmt, hcrc = HEADER.unpack(self.buffer[:32])
                if not (0 < width <= 1920 and 0 < height <= 1080 and count == width*height*2 and fmt == FRAME_FORMAT and zlib.crc32(self.buffer[:28]) == hcrc):
                    self.rejected += 1
                    del self.buffer[0]
                    continue
                total = 32+count+12
                if len(self.buffer) < total:
                    break
                packet = bytes(self.buffer[:total])
                parser = FrameParser()
                frames = parser.feed(packet)
                if len(frames) != 1 or parser.rejected or parser.discarded or parser.buffer:
                    # A valid header owned this full packet. Never interpret
                    # a fake status/frame magic inside its corrupted pixels.
                    self.rejected += 1
                    self.discarded += total
                    del self.buffer[:total]
                    continue
                events.append({'kind': 'frame', 'frame': frames[0], 'wire': packet})
                del self.buffer[:total]
        return events


def protocol_spec():
    return {'contract': GUARDED_CONTROL_CONTRACT,
        'opcodes': {item.name: int(item) for item in Opcode}, 'results': {item.name: int(item) for item in Result},
        'stop_reasons': {item.name: int(item) for item in StopReason},
        'status_fields': [{'name': name, 'offset': offset, 'bytes': struct.calcsize(kind), 'format': '<'+kind} for name, offset, kind in STATUS_FIELDS],
        'status_flags': {name: index for index, name in enumerate(FLAG_NAMES)}}


class GuardedCommandModel:
    """Pure command/sequence/feedback oracle. It neither runs nor renews a lease."""
    def __init__(self, *, rx_timeout_cycles=1250000, grant_timeout_cycles=1024):
        if type(rx_timeout_cycles) is not int or rx_timeout_cycles < 1 or type(grant_timeout_cycles) is not int or grant_timeout_cycles < 1:
            raise ValueError('timeouts must be positive cycle counts')
        self.rx_timeout_cycles, self.grant_timeout_cycles = rx_timeout_cycles, grant_timeout_cycles
        self.session_id = self.last_received_seq = self.last_accepted_seq = 0
        self.last_opcode = 0
        self.last_result = Result.NONE
        self.accepted_count = self.rejected_count = self.duplicate_count = self.rx_error_count = 0
        self.requested_frames = self.lease_ms = 0
        self.last_tuple, self.pending = None, None
        self.buffer = bytearray()
        self.rx_age = self.grant_age = 0

    @property
    def command_busy(self):
        return bool(self.buffer or self.pending)

    def _event(self, result, *, opcode=None, accepted_seq=None, duplicate=False, rx_error=False, stop=False, grant=None):
        if opcode is not None:
            self.last_opcode = int(opcode)
        self.last_result = Result(result)
        if accepted_seq is not None:
            self.accepted_count = (self.accepted_count+1) & 0xFFFFFFFF
            self.last_accepted_seq = accepted_seq
        elif duplicate:
            self.duplicate_count = (self.duplicate_count+1) & 0xFFFFFFFF
        elif rx_error:
            self.rx_error_count = (self.rx_error_count+1) & 0xFFFFFFFF
        elif result != Result.NONE:
            self.rejected_count = (self.rejected_count+1) & 0xFFFFFFFF
        return {'result': Result(result), 'reply': result != Result.NONE, 'stop': stop, 'grant': grant,
                'last_received_seq': self.last_received_seq, 'last_accepted_seq': self.last_accepted_seq}

    def handle_packet(self, packet, *, core_idle=True, fault_active=False, can_grant=True, grant_ready=True):
        try:
            command = decode_command(packet)
        except ValueError:
            code = Result.BAD_VERSION if len(packet) == 16 and packet[:2] == b'\xa5\x5a' and crc16_ccitt_false(packet[2:14]) == int.from_bytes(packet[14:16], 'little') else Result.BAD_CRC
            return self._event(code, rx_error=True)
        opcode, seq, session, arg = (command[name] for name in ('opcode', 'seq', 'session', 'arg'))
        command_tuple = (opcode, seq, session, arg)
        if opcode == Opcode.OPEN and (not self.session_id or session != self.session_id):
            if session == 0 or arg != 0:
                return self._event(Result.BAD_ARG, opcode=opcode)
            if self.pending:
                return self._event(Result.BUSY, opcode=opcode)
            if fault_active:
                return self._event(Result.FAULT, opcode=opcode)
            if not core_idle:
                return self._event(Result.NOT_IDLE, opcode=opcode)
            self.session_id, self.last_received_seq, self.last_tuple = session, seq, command_tuple
            return self._event(Result.ACCEPTED, opcode=opcode, accepted_seq=seq)
        if not self.session_id:
            return self._event(Result.NO_SESSION, opcode=opcode)
        if session != self.session_id:
            return self._event(Result.SESSION_MISMATCH, opcode=opcode)
        delta = (seq-self.last_received_seq) & 0xFFFF
        if delta == 0:
            return self._event(Result.DUPLICATE if command_tuple == self.last_tuple else Result.SEQ_CONFLICT,
                               opcode=opcode, duplicate=command_tuple == self.last_tuple)
        if delta >= 0x8000:
            return self._event(Result.OLD_SEQ, opcode=opcode)
        self.last_received_seq, self.last_tuple = seq, command_tuple
        if opcode == Opcode.GRANT:
            frames, milliseconds = arg & 255, arg >> 8
            self.requested_frames, self.lease_ms = frames, milliseconds & 65535
            if not 1 <= frames <= 3 or not 1 <= milliseconds <= 24000:
                return self._event(Result.BAD_ARG, opcode=opcode)
            if self.pending:
                return self._event(Result.BUSY, opcode=opcode)
            if fault_active:
                return self._event(Result.FAULT, opcode=opcode)
            if not can_grant or not grant_ready:
                return self._event(Result.NOT_READY, opcode=opcode)
            self.pending, self.grant_age = {'seq': seq, 'frames': frames, 'cycles': milliseconds*125000}, 0
            return self._event(Result.NONE, opcode=opcode, grant=dict(self.pending))
        if opcode not in (Opcode.OPEN, Opcode.STOP, Opcode.QUERY):
            return self._event(Result.BAD_OPCODE, opcode=opcode)
        if arg != 0:
            return self._event(Result.BAD_ARG, opcode=opcode)
        if opcode == Opcode.STOP:
            if self.pending:
                self.rejected_count = (self.rejected_count+1) & 0xFFFFFFFF
                self.pending = None
            return self._event(Result.ACCEPTED, opcode=opcode, accepted_seq=seq, stop=True)
        if self.pending:
            return self._event(Result.BUSY, opcode=opcode)
        if opcode == Opcode.OPEN:
            if fault_active:
                return self._event(Result.FAULT, opcode=opcode)
            if not core_idle:
                return self._event(Result.NOT_IDLE, opcode=opcode)
        return self._event(Result.ACCEPTED, opcode=opcode, accepted_seq=seq)

    def grant_feedback(self, *, accepted=False, rejected=False):
        if not self.pending or not (accepted or rejected):
            return None
        pending, self.pending = self.pending, None
        return self._event(Result.GRANT_REJECTED if rejected else Result.ACCEPTED,
            opcode=Opcode.GRANT, accepted_seq=None if rejected else pending['seq'])

    def tick(self, cycles=1):
        if type(cycles) is not int or cycles < 0:
            raise ValueError('cycles must be a nonnegative integer')
        events = []
        if self.pending:
            self.grant_age += cycles
            if self.grant_age >= self.grant_timeout_cycles:
                self.pending = None
                events.append(self._event(Result.GRANT_TIMEOUT, opcode=Opcode.GRANT, stop=True))
        if self.buffer:
            self.rx_age += cycles
            if self.rx_age >= self.rx_timeout_cycles:
                self.buffer.clear()
                self.rx_age = 0
                events.append(self._event(Result.RX_TIMEOUT, rx_error=True))
        return events

    def feed(self, data, *, framing_error=False, **state):
        events = []
        if framing_error:
            self.buffer.clear()
            self.rx_age = 0
            return [self._event(Result.RX_FRAMING, rx_error=True)]
        for value in data:
            self.rx_age = 0
            if not self.buffer:
                if value == 0xA5:
                    self.buffer.append(value)
            elif len(self.buffer) == 1:
                if value == 0x5A:
                    self.buffer.append(value)
                elif value != 0xA5:
                    self.buffer.clear()
            else:
                self.buffer.append(value)
                if len(self.buffer) == 16:
                    packet = bytes(self.buffer)
                    self.buffer.clear()
                    events.append(self.handle_packet(packet, **state))
        return events
