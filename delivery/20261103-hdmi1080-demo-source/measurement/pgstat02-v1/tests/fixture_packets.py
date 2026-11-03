"""Synthetic serialized wire fixtures. No hardware or measured values."""
from pathlib import Path
import hashlib
import json
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / 'reference/MEASUREMENT_BUILD_MANIFEST.json').read_text(encoding='utf-8'))
PLAN = json.loads((ROOT / 'reference/canonical-requests/PLAN.json').read_text(encoding='utf-8'))


def ack():
    c = PLAN['Commands'][0]
    body = struct.pack('<4sBBHIII', b'SGK1', 1, 1, 24, c['Ticket'], c['Nonce'], 9)
    return body + struct.pack('<I', zlib.crc32(body))


def signature(frame_id=2000, mode=1, embedded_magic=False):
    c = PLAN['Commands'][0]
    b = bytearray(128)
    b[:8] = b'PGSIG001'
    struct.pack_into('<BBBBHBB', b, 8, 1, 2, 1, 1, 128, 8, 0)
    struct.pack_into('<10I', b, 16, c['Nonce'], 7, frame_id, MANIFEST['param_id'], 100,
                     2073600, 0x12345678, 0, 0, 0)
    struct.pack_into('<HHBB', b, 56, 1920, 1080, 255, mode)
    if embedded_magic:
        b[64:76] = b'SGK1PGSTAT02'
    struct.pack_into('<I', b, 120, zlib.crc32(b[:120]))
    b[124:] = b'SG01'
    return bytes(b)


def stat(index, ticks, sequence, frame_id, counts, raw_cycles, hz=125000000, mode=1, nonce=None, version=2, flags=0x12):
    c = PLAN['Commands'][index + 1]
    body = struct.pack('<8sBBHIIIIIQ', b'PGSTAT02', version, 1, 84, c['Ticket'],
                       c['Nonce'] if nonce is None else nonce, 7, hz, sequence, ticks)
    body += struct.pack('<10I', raw_cycles, frame_id, MANIFEST['param_id'], mode, *counts, flags)
    assert len(body) == 80
    return body + struct.pack('<I', zlib.crc32(body))


def run(first=None, second=None, *, prefix=b'', tail=b'', embedded_magic=False):
    if first is None:
        first = dict(ticks=(1 << 32) - 100000000, sequence=17, frame_id=2000,
                     counts=(401, 400, 350, 100, 2), raw_cycles=6249999)
    if second is None:
        second = dict(ticks=first['ticks'] + 2500000000, sequence=(first['sequence'] + 1) % (1 << 32),
                      frame_id=2400, counts=(801, 800, 650, 400, 4), raw_cycles=6374999)
    selected = ack() + signature(embedded_magic=embedded_magic) + stat(0, **first) + signature(frame_id=2400) + stat(1, **second)
    raw = prefix + selected + tail
    attestation = dict(loaded_firmware_sha256=MANIFEST['firmware_sha256'],
                       load_receipt_evidence='SYNTHETIC fixture, not a real load receipt',
                       epoch_label='SYNTHETIC_OFFLINE_EPOCH', uninterrupted_reset_epoch=True,
                       known_packet_boundary_offset=len(prefix),
                       boundary_evidence='Synthetic packet concatenation boundary, not a physical observation',
                       input_description='SYNTHETIC serialized packets only; no camera or board')
    meta = dict(capture_kind='SYNTHETIC_OFFLINE_FIXTURE', raw_sha256=hashlib.sha256(raw).hexdigest(),
                validated_analysis_end_offset=len(prefix) + len(selected), host_elapsed_seconds=0.001)
    return raw, dict(MANIFEST), dict(PLAN), attestation, meta


def write_default():
    raw, manifest, plan, attestation, meta = run(prefix=b'PREFIX_NOT_AN_ATTESTED_PACKET', tail=b'PGSIG001\x01\x02')
    out = ROOT / 'fixtures'
    (out / 'synthetic_mixed_uart.bin').write_bytes(raw)
    for name, data in (('synthetic_run_attestation.json', attestation), ('synthetic_capture_meta.json', meta)):
        (out / name).write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    write_default()
