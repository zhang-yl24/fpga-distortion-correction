"""Independent synthetic protocol and mocked receive-only lifecycle tests."""
from pathlib import Path
import json
import struct
import sys
import zlib

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import hdmi_status as status


def packet(*, flags=0x1BFF, sequence=7, cfg_error=0, input_fault=0, tick=0xFFFFFFF0,
           width=1920, height=1080, edges=74250, good=9, bad=0, age=6, transactions=333,
           address=0x1201, value=0x81, meta=1, tag=0x48444901):
    p = bytearray(64)
    p[:8] = b"PGHDMI01"
    struct.pack_into("<IIHBBHHIIII IHBBII", p, 8, sequence, tick, flags, cfg_error, input_fault,
                     width, height, edges, good, bad, age, transactions, address, value, meta, tag, 0)
    struct.pack_into("<I", p, 56, zlib.crc32(p[:56]))
    p[60:] = b"HM01"
    return bytes(p)


def repair_crc(p):
    p = bytearray(p)
    struct.pack_into("<I", p, 56, zlib.crc32(p[:56]))
    return bytes(p)


def test_valid_packet_preserves_fields_and_does_not_claim_phy_measurement():
    p = packet(flags=0x1BBF)
    frame = status.decode_packet(p)
    assert frame["sequence"] == 7 and frame["reference_ticks"] == 0xFFFFFFF0
    assert frame["width"] == 1920 and frame["height"] == 1080
    assert frame["pclk_edges_observed"] == 74250
    assert frame["completed_transactions"] == 333 and frame["last_address"] == 0x1201
    assert frame["last_value"] == 0x81 and frame["last_transaction_is_read"]
    assert frame["state"] == "digital_input_qualified"
    assert frame["phy_lock"] is None and frame["colour_format"] is None
    assert not frame["physical_timing_verified"] and not frame["hardware_release_allowed"]
    assert frame["wire_hex"] == p.hex()


def test_v1_freshness_fields_are_unavailable_not_reported_as_inactive():
    frame = status.decode_packet(packet())
    assert frame["monitor_freshness_mask"] is None
    assert frame["monitor_freshness"] is None


def test_v2_decodes_monitor_freshness_from_versioned_extension():
    p = bytearray(packet(tag=status.BUILD_TAG_V2))
    p[52] = 0b10101
    frame = status.decode_packet(repair_crc(p))
    assert frame["build_tag"] == status.BUILD_TAG_V2
    assert frame["monitor_freshness_mask"] == 0b10101
    assert frame["monitor_freshness"] == {
        "pclk": True, "vsync": False, "de": True, "frame": False, "snapshot": True,
    }


@pytest.mark.parametrize("offset,value", [(52, 0x20), (53, 1), (54, 1), (55, 1)])
def test_v2_rejects_unknown_extension_bits(offset, value):
    p = bytearray(packet(tag=status.BUILD_TAG_V2))
    p[offset] = value
    with pytest.raises(ValueError, match="reserved"):
        status.decode_packet(repair_crc(p))


@pytest.mark.parametrize("count", [0, 0x1234, 0xfffe, 0xffff])
def test_v3_decodes_reference_domain_vs_count_without_claiming_phy_lock(count):
    p = bytearray(packet(tag=status.BUILD_TAG_V3))
    p[52] = 0x15
    struct.pack_into("<H", p, 53, count)
    frame = status.decode_packet(repair_crc(p))
    assert frame["vs_edge_count_ref"] == count
    assert frame["monitor_freshness_mask"] == 0x15
    assert not frame["monitor_freshness"]["vsync"]
    assert frame["phy_lock"] is None and not frame["hardware_release_allowed"]


def test_v3_stream_retains_counter_wrap_for_modulo_interval_analysis():
    wire = bytearray()
    for sequence, count in enumerate((0xfffe, 0xffff, 0), start=1):
        p = bytearray(packet(sequence=sequence, tag=status.BUILD_TAG_V3))
        struct.pack_into("<H", p, 53, count)
        wire.extend(repair_crc(p))
    frames = status.FrameParser().feed(wire)
    counts = [frame["vs_edge_count_ref"] for frame in frames]
    assert counts == [0xfffe, 0xffff, 0]
    assert [(b - a) & 0xffff for a, b in zip(counts, counts[1:])] == [1, 1]


@pytest.mark.parametrize("offset,value", [(52, 0x20), (55, 1)])
def test_v3_rejects_only_unassigned_extension_bits(offset, value):
    p = bytearray(packet(tag=status.BUILD_TAG_V3))
    p[offset] = value
    with pytest.raises(ValueError, match="reserved"):
        status.decode_packet(repair_crc(p))


@pytest.mark.parametrize("tag", [status.BUILD_TAG, status.BUILD_TAG_V2])
def test_older_versions_have_no_vs_counter_measurement(tag):
    assert status.decode_packet(packet(tag=tag))["vs_edge_count_ref"] is None


@pytest.mark.parametrize("cut", range(1, 64))
def test_every_single_split_and_multi_packet_chunk(cut):
    p, q = packet(sequence=1), packet(sequence=2)
    parser = status.FrameParser()
    assert parser.feed(p[:cut]) == []
    result = parser.feed(p[cut:] + q)
    assert [f["sequence"] for f in result] == [1, 2]
    assert parser.accepted == 2 and parser.rejected == 0 and not parser.buffer


def test_noise_buffer_bounded_and_one_byte_feeds_recover():
    parser = status.FrameParser()
    assert parser.feed(b"noise" * 10000) == []
    assert len(parser.buffer) <= 7
    frames = []
    for value in packet():
        frames.extend(parser.feed(bytes([value])))
        assert len(parser.buffer) < 64
    assert len(frames) == 1 and parser.rejected == 0
    assert parser.noise_bytes == 50000


def test_magic_inside_valid_payload_is_not_a_new_frame():
    p = bytearray(packet())
    p[24:32] = b"PGHDMI01"
    parser = status.FrameParser()
    frames = parser.feed(repair_crc(p) + packet(sequence=8))
    assert [f["sequence"] for f in frames] == [7, 8]
    assert parser.rejected == 0


@pytest.mark.parametrize("offset,reason", [(24, "crc32"), (60, "trailer")])
def test_corruption_rejected_then_resynchronizes(offset, reason):
    damaged = bytearray(packet())
    damaged[offset] ^= 1
    parser = status.FrameParser()
    frames = parser.feed(damaged + packet(sequence=8))
    assert [f["sequence"] for f in frames] == [8]
    assert parser.rejected == 1 and parser.error_counts[reason] == 1


@pytest.mark.parametrize("offset,value,reason", [(17, 0x80, "reserved"), (18, 0x10, "reserved"),
    (47, 4, "reserved"), (52, 1, "reserved"), (48, 4, "build_tag")])
def test_reserved_and_version_rejected_even_with_valid_crc(offset, value, reason):
    p = bytearray(packet())
    p[offset] = value
    with pytest.raises(ValueError, match=reason):
        status.decode_packet(repair_crc(p))


def test_reset_truncation_recovery_and_sequence_wrap_are_not_source_proofs():
    parser = status.FrameParser()
    stream = packet(sequence=0xFFFFFFFF) + packet(sequence=55)[:31] + packet(sequence=0) + packet(sequence=1)
    frames = parser.feed(stream)
    assert [f["sequence"] for f in frames] == [0xFFFFFFFF, 0, 1]
    assert parser.rejected == 1
    assert all(not f["hardware_release_allowed"] for f in frames)


@pytest.mark.parametrize("flags,state", [(0, "configuration_snapshot_missing"),
    (1, "configuration_snapshot_stale"), (3 | (1 << 6), "i2c_failure"),
    (3, "waiting_for_input_or_configuration"), (3 | (1 << 4), "waiting_for_transmitter_configuration"),
    (3 | (1 << 4) | (1 << 5), "waiting_for_digital_input_qualification"),
    (3 | (1 << 10), "digital_input_fault")])
def test_state_is_diagnostic_not_assumed_lock(flags, state):
    frame = status.decode_packet(packet(flags=flags, edges=0))
    assert frame["state"] == state
    assert frame["pclk_edges"] == 0 and frame["pclk_edges_observed"] is None
    assert frame["phy_lock"] is None


def test_semantically_inconsistent_status_is_retained_but_not_qualified():
    frame = status.decode_packet(packet(flags=3 | (1 << 9)))
    assert frame["flags_decoded"]["input_qualified"]
    assert "inconsistent_input_qualification" in frame["semantic_issues"]
    assert frame["state"] != "digital_input_qualified"


class FakePort:
    def __init__(self, *, fail_open=False, fail_read=False):
        self.events = []
        self.fail_open = fail_open
        self.fail_read = fail_read
        self.dtr = self.rts = True
        self.port = None

    def open(self):
        self.events.append(("open", self.dtr, self.rts, self.port))
        if self.fail_open:
            raise OSError("open failure")

    def read(self, size):
        self.events.append(("read", size))
        if self.fail_read:
            raise OSError("read failure")
        return packet()

    def close(self):
        self.events.append(("close",))

    def write(self, data):
        raise AssertionError("receiver must never transmit")


def factory(port):
    def create(**kwargs):
        assert kwargs == dict(port=None, baudrate=115200, bytesize=8, parity="N", stopbits=1,
                             timeout=0.1, write_timeout=1, xonxoff=False, rtscts=False, dsrdtr=False)
        return port
    return create


def test_receive_only_serial_opens_with_control_lines_low_and_always_closes():
    port = FakePort()
    ticks = iter([0, .1, .2, 1.1])
    chunks = list(status.serial_chunks("COM7", 1, serial_factory=factory(port), monotonic=lambda: next(ticks)))
    assert chunks == [packet(), packet()]
    assert port.events[0] == ("open", False, False, "COM7")
    assert port.events[-1] == ("close",)


@pytest.mark.parametrize("mode", ["open", "read", "consumer"])
def test_serial_is_closed_on_open_read_or_consumer_error(mode):
    port = FakePort(fail_open=mode == "open", fail_read=mode == "read")
    chunks = status.serial_chunks("COM7", 1, serial_factory=factory(port), monotonic=lambda: 0)
    if mode == "consumer":
        assert next(chunks) == packet()
        chunks.close()
    else:
        with pytest.raises(OSError):
            next(chunks)
    assert port.events[-1] == ("close",)


@pytest.mark.parametrize("seconds", [0, -1, 31, float("inf"), float("nan"), True])
def test_invalid_serial_duration_never_constructs_a_port(seconds):
    def forbidden(**kwargs):
        raise AssertionError("must validate before serial access")
    with pytest.raises(ValueError):
        list(status.serial_chunks("COM7", seconds, serial_factory=forbidden))


def test_replay_receipt_is_offline_and_exclusive(tmp_path):
    replay, output = tmp_path / "wire.bin", tmp_path / "status.json"
    replay.write_bytes(packet(flags=0x1BBF))
    report = status.capture(output, replay=replay)
    assert report["passed"] and not report["hardware_accessed"]
    assert report["source_kind"] == "offline_uart_replay" and report["bytes_written"] == 0
    assert json.loads(output.read_text())["accepted_packets"] == 1
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        status.capture(output, replay=replay)
    assert output.read_bytes() == before


def test_live_receipt_preserves_wire_and_closes_generator(tmp_path, monkeypatch):
    events = []
    def chunks(port, seconds):
        try:
            events.append((port, seconds))
            yield packet()
            yield packet(sequence=8)
        finally:
            events.append("closed")
    monkeypatch.setattr(status, "serial_chunks", chunks)
    output = tmp_path / "live.json"
    report = status.capture(output, port="COM7", seconds=1)
    assert report["passed"] and report["hardware_accessed"] and report["bytes_written"] == 0
    assert output.with_suffix(".raw.bin").read_bytes() == packet() + packet(sequence=8)
    assert events[-1] == "closed"


def test_consumer_error_closes_serial_generator_and_preserves_raw(tmp_path, monkeypatch):
    events = []
    def chunks(port, seconds):
        try:
            yield packet()
            raise AssertionError("must close after decode failure")
        finally:
            events.append("closed")
    def fail_decode(self, chunk):
        raise RuntimeError("synthetic consumer failure")
    monkeypatch.setattr(status, "serial_chunks", chunks)
    monkeypatch.setattr(status.FrameParser, "feed", fail_decode)
    output = tmp_path / "consumer.json"
    report = status.capture(output, port="COM7")
    assert not report["passed"] and events == ["closed"]
    assert "synthetic consumer failure" in report["error"]
    assert output.with_suffix(".raw.bin").read_bytes() == packet()


def test_invalid_live_request_does_not_create_files_or_open_port(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("invalid request must not access UART")
    monkeypatch.setattr(status, "serial_chunks", forbidden)
    output = tmp_path / "invalid.json"
    with pytest.raises(ValueError):
        status.capture(output, port="/dev/ttyUSB0")
    assert not output.exists() and not output.with_suffix(".raw.bin").exists()


def test_live_error_is_preserved_in_receipt(tmp_path, monkeypatch):
    def chunks(port, seconds):
        yield packet()
        raise OSError("synthetic read failure")
    monkeypatch.setattr(status, "serial_chunks", chunks)
    output = tmp_path / "live.json"
    report = status.capture(output, port="COM7")
    assert not report["passed"] and report["accepted_packets"] == 1
    assert "synthetic read failure" in report["error"]
    assert output.with_suffix(".raw.bin").read_bytes() == packet()
