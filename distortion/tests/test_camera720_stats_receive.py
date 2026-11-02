"""Only mock streams; no real serial import, PDS, JTAG or board access."""
from collections import deque
import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import zlib

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import camera720_stats_receive as receiver

BUILD, PROFILE = "123456789abcdef0", "fedcba9876543210"


def packet(seq=0, *, ticks=None, counts=None, build=BUILD, profile=PROFILE):
    ticks = 125000000 * (seq + 1) if ticks is None else ticks
    counts = (15 * (seq + 1), 10 * (seq + 1), 9 * (seq + 1)) if counts is None else counts
    raw = bytearray(64)
    raw[:12] = b"PGFPS01\n\x01\x00\x40\x00"
    struct.pack_into("<IQIII", raw, 12, seq, ticks, *counts)
    struct.pack_into("<QQ", raw, 44, int(build, 16), int(profile, 16))
    struct.pack_into("<I", raw, 60, zlib.crc32(raw[:60]))
    return bytes(raw)


class Clock:
    def __init__(self):
        self.value = 10.0

    def __call__(self):
        return self.value


class Stream:
    def __init__(self, clock, chunks=(), *, close_error=None):
        self.clock, self.chunks = clock, deque(chunks)
        self.timeout = .25
        self.close_calls = 0
        self.close_error = close_error
        self.read_requests = []

    @property
    def in_waiting(self):
        return len(self.chunks[0]) if self.chunks and isinstance(self.chunks[0], bytes) else 0

    def read(self, count):
        self.read_requests.append(count)
        self.clock.value += min(.1 if self.chunks else .25, self.timeout)
        if not self.chunks:
            return b""
        value = self.chunks.popleft()
        if isinstance(value, BaseException):
            raise value
        if len(value) > count:
            self.chunks.appendleft(value[count:])
        return value[:count]

    def close(self):
        self.close_calls += 1
        if self.close_error:
            raise self.close_error

    def write(self, *args):
        pytest.fail("receive-only tool attempted UART TX")


def capture(tmp_path, chunks=(), **kwargs):
    clock = Clock()
    stream = Stream(clock, chunks, close_error=kwargs.pop("close_error", None))
    output = tmp_path / "session"
    result = receiver.receive_stream(lambda: stream, output, expected_build_id=BUILD,
        expected_profile_id=PROFILE, clock=clock, seconds=kwargs.pop("seconds", 1), **kwargs)
    return result, stream, output


def lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_clean_window_keeps_raw_bytes_unknown_status_and_host_time(tmp_path):
    raw = packet() + packet(1)
    result, stream, output = capture(tmp_path, [packet(), packet(1)])
    assert result["ReceptionAndIdentityPassed"]
    assert stream.close_calls == 1
    assert (output / "received-wire.bin").read_bytes() == raw
    assert result["SelectedWindows"]["SourceAcceptedFPS"] == 15
    assert result["SelectedWindows"]["ProcessedFPS"] == 10
    assert result["SelectedWindows"]["UniquePresentedFPS"] == 9
    assert result["Underflows"] is None and not result["UnderflowsAvailable"]
    assert result["KnownFaultObserved"] is None and not result["FaultFreeProven"]
    assert not result["HardwareAccessed"] and result["UARTTransmitBytes"] == 0
    records = lines(output / "packets.jsonl")
    assert records[0]["WireStart"] == 0 and records[1]["WireEnd"] == 128
    window = lines(output / "windows.jsonl")[0]
    assert window["HostTiming"]["HostToNominalDurationRatio"] == pytest.approx(.1)
    assert not window["HostTiming"]["HostTimesAreSnapshotTimes"]
    assert window["AssumesContinuousResetEpoch"] and not window["ResetEpochContinuityProven"]


def test_exact_byte_limit_does_not_read_the_next_packet(tmp_path):
    result, stream, output = capture(tmp_path, [packet() + packet(1) + packet(2)], max_bytes=128)
    assert result["EndReason"] == "byte_limit"
    assert result["BytesReceived"] == 128
    assert stream.chunks[0] == packet(2)
    assert max(stream.read_requests) <= 128
    # Two packets completed in one USB read have no fictitious host time gap.
    assert lines(output / "windows.jsonl")[0]["HostTiming"]["HostToNominalDurationRatio"] is None


def test_no_data_is_bounded_closed_and_not_a_zero_fps_success(tmp_path):
    result, stream, output = capture(tmp_path, seconds=30)
    assert result["ElapsedSecondsAfterOpen"] == 30
    assert result["ReadCalls"] == 120 and stream.close_calls == 1
    assert result["NoDataReceived"] and not result["ReceptionAndIdentityPassed"]
    assert result["SelectedWindows"]["ProcessedFPS"] is None
    assert (output / "received-wire.bin").read_bytes() == b""


def test_bad_crc_is_saved_and_breaks_only_its_adjacent_window(tmp_path):
    bad = bytearray(packet(1))
    bad[25] ^= 1
    raw = packet() + bytes(bad) + packet(2) + packet(3)
    result, stream, output = capture(tmp_path, [raw])
    assert stream.close_calls == 1
    assert (output / "received-wire.bin").read_bytes() == raw
    assert result["RejectedPackets"] == 1 and not result["ReceptionAndIdentityPassed"]
    windows = lines(output / "windows.jsonl")
    assert [w["ValidCounterWindow"] for w in windows] == [False, True]
    assert windows[0]["Rates"]["Reason"] == "corrupt_or_unframed_bytes_between_packets"


@pytest.mark.parametrize("wrong", [{"build": "1111111111111111"}, {"profile": "2222222222222222"}])
def test_old_identity_is_retained_but_never_mixed_into_expected_measurement(tmp_path, wrong):
    result, stream, output = capture(tmp_path, [packet() + packet(1, **wrong) + packet(2) + packet(3)])
    assert result["IdentityMismatches"] == 1 and not result["ReceptionAndIdentityPassed"]
    assert not lines(output / "packets.jsonl")[1]["ExpectedIDsMatch"]
    assert [w["ValidCounterWindow"] for w in lines(output / "windows.jsonl")] == [False, False, True]
    assert result["SelectedWindows"]["FrameDeltas"]["SourceAccepted"] == 15


def test_sequence_gap_uses_real_tick_interval_not_assumed_one_second(tmp_path):
    result, _, output = capture(tmp_path, [packet(), packet(3)])
    window = lines(output / "windows.jsonl")[0]
    assert window["Rates"]["NominalSeconds"] == 3
    assert window["Rates"]["SkippedTelemetrySamples"] == 2
    assert result["SelectedWindows"]["SourceAcceptedFPS"] == 15


def test_observed_reset_splits_windows_without_claiming_hidden_reset_detection(tmp_path):
    result, _, output = capture(tmp_path, [packet(7), packet(), packet(1)])
    windows = lines(output / "windows.jsonl")
    assert [w["ValidCounterWindow"] for w in windows] == [False, True]
    assert windows[0]["Rates"]["Reason"] == "reset_duplicate_or_out_of_order"
    assert result["SelectedWindows"]["NominalSeconds"] == 1
    assert not result["SelectedWindows"]["IsWholeHostSessionAverage"]
    assert not result["ResetEpochContinuityProven"]


def test_one_packet_is_not_enough_to_report_fps(tmp_path):
    result, _, _ = capture(tmp_path, [packet()])
    assert result["MatchingPackets"] == 1
    assert not result["ReceptionAndIdentityPassed"]
    assert result["SelectedWindows"]["ProcessedFPS"] is None


def test_extreme_frequency_aggregate_retains_failure_record_and_cleanup(tmp_path):
    frames = [packet(i, ticks=i + 1, counts=(0, 0, 0)) for i in range(3)]
    result, stream, output = capture(tmp_path, frames, nominal_core_hz=1e-308)
    assert stream.close_calls == 1 and not result["ReceptionAndIdentityPassed"]
    assert "AggregateNumericError" in result
    assert result["SelectedWindows"]["NominalSeconds"] is None
    assert json.loads((output / "session.json").read_text())["AggregateNumericError"]


def test_partial_tail_never_becomes_a_record(tmp_path):
    raw = packet() + packet(1) + packet(2)[:20]
    result, _, output = capture(tmp_path, [raw], max_bytes=len(raw))
    assert result["CompletePackets"] == 2 and result["TrailingPartialBytes"] == 20
    assert result["ReceptionAndIdentityPassed"]
    assert (output / "received-wire.bin").read_bytes() == raw


def test_read_error_retains_data_and_closes_owned_stream(tmp_path):
    result, stream, output = capture(tmp_path, [packet(), packet(1), OSError("synthetic read failure")])
    assert stream.close_calls == 1 and "synthetic read failure" in result["Error"]
    assert not result["ReceptionAndIdentityPassed"]
    assert (output / "received-wire.bin").read_bytes() == packet() + packet(1)
    assert json.loads((output / "session.json").read_text())["Error"] == result["Error"]


def test_keyboard_interrupt_closes_stream_and_records_partial_session(tmp_path):
    result, stream, output = capture(tmp_path, [packet(), KeyboardInterrupt()])
    assert stream.close_calls == 1 and "KeyboardInterrupt" in result["Error"]
    assert (output / "received-wire.bin").read_bytes() == packet()
    assert not result["ReceptionAndIdentityPassed"]


def test_close_error_cannot_be_hidden_by_successful_packets(tmp_path):
    result, stream, _ = capture(tmp_path, [packet(), packet(1)], close_error=OSError("synthetic close failure"))
    assert stream.close_calls == 1
    assert "synthetic close failure" in result["CloseError"]
    assert not result["ReceptionAndIdentityPassed"]


def test_open_error_still_writes_failed_session_without_fake_hardware_access(tmp_path):
    def fail():
        raise OSError("synthetic open failure")
    result = receiver.receive_stream(fail, tmp_path / "session", expected_build_id=BUILD, expected_profile_id=PROFILE)
    assert not result["StreamOpened"] and not result["HardwareAccessed"]
    assert "synthetic open failure" in result["Error"]


def test_decode_error_closes_stream_and_retains_entire_already_read_chunk(tmp_path, monkeypatch):
    def fail(*args):
        raise RuntimeError("synthetic decoder failure")
    monkeypatch.setattr(receiver.decoder_module.StreamDecoder, "feed", fail)
    result, stream, output = capture(tmp_path, [packet()])
    assert stream.close_calls == 1 and result["BytesReceived"] == 64
    assert (output / "received-wire.bin").read_bytes() == packet()
    assert not result["ReceptionAndIdentityPassed"]


@pytest.mark.parametrize("override", [{"seconds": 0}, {"seconds": float("nan")}, {"seconds": 301},
    {"max_bytes": 63}, {"max_bytes": 4194305}, {"max_bytes": True}, {"expected_build_id": "0" * 16},
    {"expected_profile_id": "bad"}, {"nominal_core_hz": float("inf")}])
def test_invalid_limits_or_identity_never_open_a_stream(tmp_path, override):
    values = {"expected_build_id": BUILD, "expected_profile_id": PROFILE, **override}
    with pytest.raises(ValueError):
        receiver.receive_stream(lambda: pytest.fail("invalid input opened stream"), tmp_path / "session", **values)
    assert not (tmp_path / "session").exists()


def test_existing_output_and_decoder_drift_fail_before_open(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="fresh session"):
        receiver.receive_stream(lambda: pytest.fail("opened"), tmp_path, expected_build_id=BUILD, expected_profile_id=PROFILE)
    monkeypatch.setattr(receiver, "DECODER_SHA", "0" * 64)
    with pytest.raises(ValueError, match="frozen statistics decoder"):
        receiver.receive_stream(lambda: pytest.fail("opened"), tmp_path / "new", expected_build_id=BUILD, expected_profile_id=PROFILE)


def test_source_drift_during_receive_prevents_session_pass_without_editing_sources(tmp_path, monkeypatch):
    original = receiver.sha
    self_reads = 0
    def changing_digest(path):
        nonlocal self_reads
        if Path(path).resolve() == receiver.SELF:
            self_reads += 1
            if self_reads > 1:
                return "0" * 64
        return original(path)
    monkeypatch.setattr(receiver, "sha", changing_digest)
    result, stream, _ = capture(tmp_path, [packet(), packet(1)])
    assert stream.close_calls == 1
    assert result["SourceDrift"] == [str(receiver.SELF)]
    assert not result["ReceptionAndIdentityPassed"]


def test_receive_defaults_match_current_stats_rtl_without_opening_device(tmp_path, monkeypatch):
    def inspect(factory, output, **kwargs):
        assert kwargs["serial_configuration"]["Port"] == "COM7"
        assert kwargs["serial_configuration"]["Baud"] == 115200
        assert kwargs["seconds"] == 30
        return {"Checked": True}
    monkeypatch.setattr(receiver, "receive_stream", inspect)
    assert receiver.receive(tmp_path / "session", expected_build_id=BUILD, expected_profile_id=PROFILE)["Checked"]


def test_serial_adapter_configures_lines_before_open_and_sends_no_data(monkeypatch):
    calls = []
    class Port:
        def __init__(self, **kwargs):
            calls.append(kwargs)
        def open(self):
            assert self.dtr is False and self.rts is False and self.port == "COM7"
            calls.append("open")
        def close(self):
            calls.append("close")
        def write(self, data):
            pytest.fail("UART TX attempted")
    monkeypatch.setitem(sys.modules, "serial", SimpleNamespace(Serial=Port))
    port = receiver.open_serial("COM7", 115200)
    assert calls[0]["port"] is None and calls[0]["baudrate"] == 115200
    assert not calls[0]["rtscts"] and not calls[0]["dsrdtr"] and not calls[0]["xonxoff"]
    port.close()
    assert calls[-2:] == ["open", "close"]


def test_serial_open_and_close_errors_both_survive(monkeypatch):
    class Port:
        def __init__(self, **kwargs):
            pass
        def open(self):
            raise OSError("open-primary")
        def close(self):
            raise OSError("close-secondary")
    monkeypatch.setitem(sys.modules, "serial", SimpleNamespace(Serial=Port))
    with pytest.raises(RuntimeError, match="open-primary.*close-secondary"):
        receiver.open_serial("COM7", 115200)
