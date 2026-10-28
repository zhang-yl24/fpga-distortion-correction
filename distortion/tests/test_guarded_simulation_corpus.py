"""Frozen actual RTL wire corpus: parser regression, never physical evidence."""
from pathlib import Path
import hashlib
import json
import sys
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/'tools'))
import guarded_protocol as protocol
import audit_guarded_wire as independent


@pytest.mark.parametrize('chunk_size', [1, 7, 37, 4093])
def test_live_parser_and_independent_auditor_agree_on_rtl_wire(chunk_size):
    data = (HERE/'guarded-board-mixed-wire.synthetic.bin').read_bytes()
    provenance = json.loads((HERE/'guarded-board-mixed-wire.synthetic.json').read_text(encoding='utf-8'))
    assert not provenance['hardware_accessed']
    assert provenance['source_kind'] == 'synthetic_rtl_uart_corpus_not_physical_camera'
    assert hashlib.sha256(data).hexdigest() == provenance['fixture_sha256']
    result = independent.audit_bytes(data, expected_size=(32, 16))
    assert result['status_packets'] == provenance['status_packets'] == 17
    assert [frame['frame_id'] for frame in result['frames']] == [1, 2, 3]
    assert not result['trailing_partial_packet']
    assert not result['physical_provenance_verified_by_auditor']
    parser = protocol.GuardedStreamParser()
    events = []
    for start in range(0, len(data), chunk_size):
        events.extend(parser.feed(data[start:start+chunk_size]))
    assert parser.rejected == parser.discarded == 0 and not parser.buffer
    frames = [event['frame'] for event in events if event['kind'] == 'frame']
    statuses = [event['status'] for event in events if event['kind'] == 'status']
    assert len(frames) == 3 and len(statuses) == 17
    for live, manual, frozen in zip(frames, result['frames'], provenance['frames']):
        assert live.frame_id == manual['frame_id'] == frozen['frame_id']
        assert hashlib.sha256(live.payload).hexdigest() == manual['payload_sha256'] == frozen['payload_sha256']
        assert f'{live.source_crc:08X}' == manual['source_crc32'] == frozen['source_crc32']
    for live, manual in zip(statuses, result['statuses']):
        assert live['snapshot_seq'] == manual['snapshot_seq']
        assert live['session_id'] == manual['session_id']
        assert live['last_received_seq'] == manual['received_seq']
        assert live['last_accepted_seq'] == manual['accepted_seq']
        assert live['flag_bits'] == manual['flags']
        assert live['temperature_raw'] == manual['temp_raw']
        assert live['completed_frames'] == manual['completed_frames']
