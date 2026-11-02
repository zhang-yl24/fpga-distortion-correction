"""The frozen B4 SGA1/SGK1/PGSIG001 protocol; no device access on import."""
import struct
import zlib


def make_arm(ticket, nonce):
    assert 0 < ticket < 2**32 and 0 < nonce < 2**32
    body = struct.pack('<4sBBHIII', b'SGA1', 1, 1, 24, ticket, nonce, 0)
    return body + struct.pack('<I', zlib.crc32(body))


def decode(data, nonce=None, ticket=None):
    acks, frames, invalid = [], [], []
    pos = 0
    while pos < len(data):
        starts = [(i, kind, size) for magic, kind, size in
                  [(b'SGK1', 'ack', 24), (b'PGSIG001', 'signature', 128)]
                  if (i := data.find(magic, pos)) >= 0]
        if not starts:
            break
        start, kind, size = min(starts)
        packet = data[start:start+size]
        if len(packet) != size:
            invalid.append({'Offset': start, 'Kind': kind, 'Reason': 'incomplete'})
            break
        crc_offset = 20 if kind == 'ack' else 120
        if zlib.crc32(packet[:crc_offset]) != struct.unpack_from('<I', packet, crc_offset)[0]:
            invalid.append({'Offset': start, 'Kind': kind, 'Reason': 'packet_crc'})
            pos = start + 1
            continue
        if kind == 'ack':
            version, status, length, rx_ticket, rx_nonce, epoch = struct.unpack_from('<BBHIII', packet, 4)
            schema = version == 1 and length == 24
            acks.append(dict(Offset=start, Version=version, Status=f'{status:02x}',
                             Ticket=rx_ticket, Nonce=rx_nonce, Epoch=epoch, CRCValid=True,
                             SchemaValid=schema,
                             MatchesCommand=(ticket is None or ticket == rx_ticket) and
                                            (nonce is None or nonce == rx_nonce)))
        else:
            version, encoding, tap, complete, length, samples, bank = struct.unpack_from('<BBBBHBB', packet, 8)
            fields = struct.unpack_from('<10I', packet, 16)
            width, height, sample_mask, mode = struct.unpack_from('<HHBB', packet, 56)
            schema = (version, encoding, tap, complete, length, samples) == (1, 2, 1, 1, 128, 8)
            schema = schema and packet[124:] == b'SG01'
            sample_values = [dict(x=struct.unpack_from('<H', packet, 64+i*7)[0],
                                  y=struct.unpack_from('<H', packet, 66+i*7)[0],
                                  rgb=packet[68+i*7:71+i*7].hex()) for i in range(8)]
            f = dict(zip(['SessionID', 'ScanEpoch', 'FrameID', 'ParameterID', 'Sequence',
                          'PixelCount', 'PixelCRC', 'DroppedTelemetry', 'AbortedTelemetry',
                          'MalformedTelemetry'], fields))
            f.update(Offset=start, Width=width, Height=height, SampleMask=sample_mask,
                     Mode=mode, Bank=bank, CRCValid=True, SchemaValid=schema,
                     PixelCRCHex=f'{f["PixelCRC"]:08x}', ParameterIDHex=f'{f["ParameterID"]:08x}',
                     MatchesSession=nonce is None or f['SessionID'] == nonce,
                     Complete1080=(schema and width == 1920 and height == 1080 and
                                   f['PixelCount'] == 2073600 and sample_mask == 255 and
                                   f['FrameID'] != 0 and mode < 4), Samples=sample_values)
            frames.append(f)
        pos = start + size
    return acks, frames, invalid


def distinct_complete(frames):
    return sorted({f['FrameID'] for f in frames if f['Complete1080'] and f['MatchesSession']})
