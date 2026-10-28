"""Synthetic wire/mock thread/JTAG tests only; no COM/JTAG/PDS access."""
from pathlib import Path
import json
import queue
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import gamma_capture_k320_dev_session as session
from frame_protocol import encode


@pytest.fixture(scope="module")
def wire():
    pixels = b"\0" * 614400
    seed = session.candidate.GROUP_SEED << 4
    return b"".join(encode(640, 480, seed | ident, pixels) for ident in (0, 1, 6))


def test_strict_three_packet_selection_and_real_numerical_reader(wire):
    selected, record, where = session.extract_triplet(b"old quarantined line\n" + wire, 0)
    assert selected == wire and record["passed"] is True
    assert record["HardwareAccessed"] is False and record["SourceIsPhysicalReadbackAttested"] is False
    assert where["extra_bytes"] == 0
    old_pixels = wire[:32] + b"\0" * (614400 - 32)
    valid_old_packet = encode(640, 480, 0x123450, old_pixels)
    assert session.extract_triplet(valid_old_packet + wire, 0)[0] == wire
    assert session.extract_triplet(valid_old_packet + wire, 100)[0] == wire
    with pytest.raises(ValueError, match="same-seed"):
        session.extract_triplet(wire + wire, len(wire))
    for bad in (wire + b"x", wire[:-1], wire[:99] + bytes([wire[99] ^ 1]) + wire[100:]):
        with pytest.raises(ValueError):
            session.extract_triplet(bad, 0)


def test_default_session_plan_never_opens_devices(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "APPROVED", tmp_path)
    validation = {"build_dir": "mock", "bitstream_path": str(tmp_path / "never-download.sbit"),
                  "profile_binding": {"Identity": {}}}
    monkeypatch.setattr(session, "validate_target", lambda _: validation)
    monkeypatch.setattr(session, "validate_connection", lambda *a: {"mock": True})
    monkeypatch.setattr(session, "helpers", lambda: {})
    monkeypatch.setattr(session.idle, "validate_heartbeat", lambda: {})
    monkeypatch.setattr(session.hw, "resolve_pds_bin", lambda _: tmp_path)
    monkeypatch.setattr(session.idle, "prepare_plan", lambda *a, **k: {"target": "heartbeat"})
    monkeypatch.setattr(session, "serial_open", lambda _: pytest.fail("plan opened COM"))
    monkeypatch.setattr(session, "execute_program", lambda *a, **k: pytest.fail("plan touched JTAG"))
    plan = session.prepare_plan("mock", tmp_path, connection_binding="mock")
    assert plan["executed"] is False and plan["seconds_after_done"] == 45
    assert (Path(plan["workdir"]) / "plan.json").is_file()
    with pytest.raises(ValueError):
        session.limits("COM5", 61, "5MHz")
    with pytest.raises(ValueError):
        session.limits("COM5", 45, "100KHz")


class FakeSerial:
    def __init__(self):
        self.queue, self.closed = queue.Queue(), False
    def read(self, n):
        try:
            return self.queue.get(timeout=.005)
        except queue.Empty:
            return b""
    def close(self):
        self.closed = True
    def put(self, blob):
        for offset in range(0, len(blob), 65536):
            self.queue.put(blob[offset:offset + 65536])


@pytest.mark.parametrize("fault", [None, "program-unknown", "idle-fail", "extra", "all-before-done"])
def test_rx_precedes_program_and_every_exit_restores(tmp_path, monkeypatch, wire, fault):
    (tmp_path / "candidate-program").mkdir()
    monkeypatch.setattr(session, "verify_plan", lambda p: tmp_path)
    monkeypatch.setattr(session, "check_program", lambda p: None)
    monkeypatch.setattr(session, "helpers", lambda: {})
    monkeypatch.setattr(session.reader, "save_replay", lambda *a: {"passed": True, "HardwareAccessed": False})
    plan = {"port": "COM5", "seconds_after_done": 30, "helper_sha256": {}, "idle_plan": {},
            "program_plan": {"validation": {"bitstream_sha256": "b" * 64, "profile_binding": {"Identity": {"camera_id": "SYNTHETIC-MOCK"}}}}}
    link, restored, ticks = FakeSerial(), [], [0.]
    early_bytes = session.PACKET_BYTES + 1000
    pending = [None]
    def program(p, before_program):
        assert not link.closed
        before_program()
        blob = wire + (b"extra" if fault == "extra" else b"")
        if fault == "all-before-done":
            link.put(blob)
        else:
            link.put(blob[:early_bytes])
            pending[0] = blob[early_bytes:]
        deadline = time.monotonic() + 2
        while not link.queue.empty() and time.monotonic() < deadline:
            time.sleep(.001)
        if fault == "program-unknown":
            raise RuntimeError("mock interrupted cfg_program")
        receipt = {"target": session.TARGET, "passed": True, "done_confirmed": True,
                   "programming_attempted": True, "bitstream_sha256": "b" * 64}
        session.hw._new_json(tmp_path / "candidate-program/receipt.json", receipt)
        return receipt
    def restore(*a, **k):
        assert link.closed
        restored.append(True)
        return {"passed": fault != "idle-fail", "done_confirmed": fault != "idle-fail"}
    def sleep(n):
        if pending[0] is not None:
            link.put(pending[0])
            pending[0] = None
        ticks[0] += n
        time.sleep(.0001)
    result = session.execute_plan(plan, programmer=program, serial_factory=lambda _: link, restorer=restore,
                                  clock=lambda: ticks[0], sleeper=sleep)
    assert restored == [True] and link.closed
    assert result["passed"] is (fault is None)
    if fault is None:
        assert result["physical_uart_observation"]["bytes_received_before_done"] == early_bytes
        assert result["numeric_replay"]["HardwareAccessed"] is False
        assert result["SourceBoundPhysicalUARTObservation"] is True
        assert result["HardwareIdentityVerifiedOnWire"] is False
    if fault == "program-unknown":
        assert result["programming_state_unknown"] is True


def test_wrong_device_never_enters_program(tmp_path, monkeypatch):
    monkeypatch.setattr(session, "check_program", lambda p: None)
    monkeypatch.setattr(session.hw, "listening_pids", lambda _: set())
    monkeypatch.setattr(session.hw, "_await_owned_server", lambda p: None)
    monkeypatch.setattr(session.hw, "_owned_server_check", lambda p: None)
    calls = []
    class Process:
        pid = 12345
    def start(command, work, owned, stage):
        p = Process()
        owned.append(p)
        return p
    monkeypatch.setattr(session.hw, "_start_owned", start)
    def client(plan, stage, owned, timeout):
        calls.append(stage)
        return "PG2L200H\nThe ID value is:0x00602899\n"
    monkeypatch.setattr(session.hw, "_client", client)
    monkeypatch.setattr(session.hw, "_stop_owned", lambda owned: ([p.pid for p in owned], []))
    plan = {"workdir": str(tmp_path), "pds_bin": "mock", "validation": {"bitstream_sha256": "f" * 64}}
    result = session.execute_program(plan)
    assert result["passed"] is False and result["programming_attempted"] is False and calls == ["scan"]


def test_rx_close_joins_even_when_serial_close_raises(tmp_path):
    link = FakeSerial()
    def broken_close():
        link.closed = True
        raise OSError("mock close failure")
    link.close = broken_close
    drain = session.RXDrain(link, tmp_path)
    drain.start()
    with pytest.raises(RuntimeError, match="after RX thread joined"):
        drain.close()
    assert not drain.thread.is_alive()


def test_preflight_rejects_frequency_and_unusable_exit(tmp_path, monkeypatch):
    program, exit_dir = tmp_path / "candidate-program", tmp_path / "idle"
    program.mkdir(); exit_dir.mkdir()
    monkeypatch.setattr(session, "APPROVED", tmp_path)
    monkeypatch.setattr(session, "helpers", lambda: {})
    monkeypatch.setattr(session, "check_program", lambda p: None)
    monkeypatch.setattr(session, "check_scripts", lambda *a: None)
    connection = {"path": "mock"}
    monkeypatch.setattr(session, "validate_connection", lambda *a: connection)
    monkeypatch.setattr(session.idle, "validate_heartbeat", lambda: {})
    plan = {"target": session.TARGET, "operation": "finite_k320_one_shot_then_fixed_heartbeat",
            "workdir": str(tmp_path), "port": "COM5", "seconds_after_done": 45., "frequency": "5MHz",
            "baud": session.BAUD, "group_seed": session.candidate.GROUP_SEED, "helper_sha256": {},
            "connection_review": connection, "program_plan": {"workdir": str(program), "frequency": "5MHz",
                "validation": {"profile_binding": {}}},
            "idle_plan": {"target": "heartbeat", "operation": "volatile_sram_only", "frequency": "5MHz",
                "workdir": str(exit_dir), "validation": {}}}
    def write():
        (tmp_path / "plan.json").write_text(json.dumps(plan))
    write()
    assert session.verify_plan(plan) == tmp_path
    plan["program_plan"]["frequency"] = "10MHz"
    write()
    with pytest.raises(ValueError):
        session.verify_plan(plan)
    plan["program_plan"]["frequency"] = "5MHz"
    plan["idle_plan"]["operation"] = "wrong"
    write()
    with pytest.raises(ValueError):
        session.verify_plan(plan)
    plan["idle_plan"]["operation"] = "volatile_sram_only"
    (exit_dir / "receipt.json").write_text("{}")
    write()
    with pytest.raises(ValueError):
        session.verify_plan(plan)
