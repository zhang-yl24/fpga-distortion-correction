"""All process and TCP ownership boundaries are mocked; no hardware is used."""
from pathlib import Path
import json
import sys
import types

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import execute_hdmi_input_program as execute_tool
import prepare_hdmi_input_program as prepare_tool

SCAN = "PG2L100H\nThe ID value is: 0x00602899\n"
PRE_SCAN = ("Executing : cfg_scan_chain\nPG2L100H\n"
            "This device configure situation (done bit): 1\n"
            "Executing : cfg_scan_chain successfully.\n")
PROGRAM_SUCCESS = "Executing : cfg_program -device_index 0 successfully.\n"
POST_SCAN = PRE_SCAN
DONE = PRE_SCAN + PROGRAM_SUCCESS + POST_SCAN


def save_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def files(tmp_path, monkeypatch):
    project = tmp_path / "project"
    approved = project / "build/offline-20261024"
    approved.mkdir(parents=True)
    bit_work = project / "build/hdmi-uart-diagnostic/input-bit-fixture"
    (bit_work / "generate_bitstream").mkdir(parents=True)
    bit = bit_work / "generate_bitstream" / (prepare_tool.TARGET + ".sbit")
    bit.write_bytes(b"SYNTHETIC BIT FIXTURE; NEVER PROGRAM")
    source = project / "source.v"
    source.write_bytes(b"SYNTHETIC SOURCE")
    evidence = bit_work / "evidence.json"
    evidence.write_text("{}", encoding="utf-8")
    adf = bit_work / "audited-final.adf"
    adf.write_bytes(b"SYNTHETIC ADF")
    (project / "tools").mkdir()
    for name in ("prepare_hdmi_input_program.py", "verify_hdmi_input_bitstream.py", "program_native_raw.py",
                 "execute_hdmi_input_program.py"):
        (project / "tools" / name).write_bytes(b"SYNTHETIC HELPER")
    plan = {"Target": prepare_tool.TARGET, "ProjectRoot": str(project), "WorkDirectory": str(bit_work),
            "FinalADFSHA256": prepare_tool.bit_export.ADF_SHA256,
            "ProjectInputSHA256": {"source.v": prepare_tool.hw.sha(source)},
            "WorkInputSHA256": {"audited-final.adf": prepare_tool.hw.sha(adf)}}
    save_json(bit_work / "bitstream-plan.json", plan)
    verified = {"Schema": "hdmi-input-bitstream-verification-v1", "Passed": True,
                "Target": prepare_tool.TARGET, "FinalADFSHA256": prepare_tool.bit_export.ADF_SHA256,
                "Bitstream": {"Path": str(bit), "Bytes": bit.stat().st_size,
                              "SHA256": prepare_tool.hw.sha(bit), "Header": {"Design": prepare_tool.TARGET}},
                "EvidenceSHA256": {"evidence.json": prepare_tool.hw.sha(evidence)},
                "HardwareAccessed": False, "HardwareReleaseAllowed": False}
    monkeypatch.setattr(prepare_tool, "ROOT", project)
    monkeypatch.setattr(prepare_tool, "APPROVED", approved)
    if hasattr(execute_tool, "ROOT"):
        monkeypatch.setattr(execute_tool, "ROOT", project)
    if hasattr(execute_tool, "APPROVED"):
        monkeypatch.setattr(execute_tool, "APPROVED", approved)
    monkeypatch.setattr(prepare_tool.verification, "verify", lambda work: verified)
    pds = tmp_path / "fake-pds"
    pds.mkdir()
    for name in ("cdt_js.exe", "cdt_cfg_shell.exe"):
        (pds / name).write_bytes(b"SYNTHETIC PLACEHOLDER; NEVER START")
    work = approved / "hdmi-input-program-fixture"
    prepared = prepare_tool.prepare(bit_work, work, pds_bin=pds)
    return {"project": project, "approved": approved, "bit_work": bit_work, "bit": bit,
            "source": source, "work": work, "pds": pds, "prepared": prepared,
            "plan_path": work / "plan.json"}


@pytest.fixture
def fake_processes(monkeypatch):
    hw = prepare_tool.hw
    state = {"processes": [], "scan": SCAN, "program": DONE,
             "scan_code": 0, "program_code": 0, "stderr": b"", "conflict": None,
             "conflict_after_scan": None, "server_exit_after_scan": False, "on_scan": None,
             "timeout_stage": None, "cleanup_failure": False}

    class Process:
        def __init__(self, stage, code):
            self.stage, self.code = stage, code
            self.pid = 8100 + len(state["processes"])
            self.ended = False
            self.terminated = False
            self.killed = False

        def poll(self):
            return self.code if self.ended else None

        def wait(self, timeout=None):
            if state["timeout_stage"] == self.stage and not self.terminated:
                raise hw.subprocess.TimeoutExpired(self.stage, timeout)
            self.ended = True
            if self.stage == "scan":
                if state["server_exit_after_scan"]:
                    state["processes"][0].ended = True
                if state["on_scan"] is not None:
                    state["on_scan"]()
            return self.code

        def terminate(self):
            if state["cleanup_failure"]:
                raise OSError("SYNTHETIC cleanup failure")
            self.terminated = True
            self.ended = True

        def kill(self):
            self.killed = True
            self.ended = True

    def popen(command, **kwargs):
        name = Path(command[0]).name
        assert name in ("cdt_js.exe", "cdt_cfg_shell.exe")
        if name == "cdt_js.exe":
            stage = "server-program" if Path(kwargs["stdout"].name).name.startswith("server-program.") else "server"
        else:
            stage = Path(command[command.index("-file") + 1]).stem
        assert stage in ("server", "server-program", "scan", "program")
        process = Process(stage, state.get(stage + "_code", 0))
        state["processes"].append(process)
        kwargs["stdout"].write(("SYNTHETIC OWNED SERVER" if stage.startswith("server") else state[stage]).encode())
        if not stage.startswith("server"):
            kwargs["stderr"].write(state["stderr"])
        return process

    def listeners(port):
        assert port == hw.PORT
        if state["conflict"] is not None:
            return set(state["conflict"])
        if state["conflict_after_scan"] is not None and any(p.stage == "scan" and p.ended for p in state["processes"]):
            return set(state["conflict_after_scan"])
        return {p.pid for p in state["processes"] if p.stage.startswith("server") and p.poll() is None}

    monkeypatch.setattr(hw.subprocess, "Popen", popen)
    monkeypatch.setattr(hw, "listening_pids", listeners)
    monkeypatch.setitem(sys.modules, "serial", types.SimpleNamespace(Serial=lambda *a, **k: pytest.fail("no serial access")))
    return state


def test_default_cli_only_validates(files, fake_processes, capsys):
    assert execute_tool.main(["--plan", str(files["plan_path"])]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["HardwareAccessed"] is False
    assert fake_processes["processes"] == []
    assert not (files["work"] / "receipt.json").exists()


@pytest.mark.parametrize("case", ("bit", "source", "script"))
def test_changed_inputs_reject_before_any_process(files, fake_processes, case):
    path = files[case] if case != "script" else files["work"] / "program.tcl"
    path.write_bytes(b"CHANGED FIXTURE")
    with pytest.raises(ValueError):
        execute_tool.execute(files["plan_path"])
    assert fake_processes["processes"] == []
    assert not (files["work"] / "receipt.json").exists()


def test_updating_script_hash_cannot_authorize_different_commands(files, fake_processes):
    path = files["work"] / "program.tcl"
    path.write_text(path.read_text() + "cfg_program_another_target\n", encoding="utf-8")
    plan = json.loads(files["plan_path"].read_text())
    plan["Tcl"]["program"]["SHA256"] = prepare_tool.hw.sha(path)
    save_json(files["plan_path"], plan)
    with pytest.raises(ValueError, match="fixed SRAM-only Tcl"):
        execute_tool.execute(files["plan_path"])
    assert fake_processes["processes"] == []


@pytest.mark.parametrize("scan", ("PG2L50H\nThe ID value is: 0x00602899\n",
    "PG2L100H\nThe ID value is: 0x00000000\n", SCAN + "PG2L100H\n"))
def test_wrong_or_multiple_device_never_programs(files, fake_processes, scan):
    fake_processes["scan"] = scan
    result = execute_tool.execute(files["plan_path"])
    assert not result["Passed"] and not result["ProgrammingAttempted"] and not result["DoneConfirmed"]
    assert [p.stage for p in fake_processes["processes"]] == ["server", "scan"]
    assert fake_processes["processes"][0].terminated


def test_foreign_listener_starts_and_stops_nothing(files, fake_processes):
    fake_processes["conflict"] = {99123}
    result = execute_tool.execute(files["plan_path"])
    assert not result["Passed"] and not result["HardwareAccessed"]
    assert fake_processes["processes"] == []


def test_source_drift_after_scan_prevents_program(files, fake_processes):
    fake_processes["on_scan"] = lambda: files["source"].write_bytes(b"CHANGED AFTER SCAN")
    result = execute_tool.execute(files["plan_path"])
    assert not result["Passed"] and not result["ProgrammingAttempted"]
    assert [p.stage for p in fake_processes["processes"]] == ["server", "scan"]


@pytest.mark.parametrize("text,code", [(DONE, 1), ("cfg_program failed\n", 0),
    (PRE_SCAN + PROGRAM_SUCCESS + POST_SCAN.replace("done bit): 1", "done bit): 0"), 0),
    (PRE_SCAN + PROGRAM_SUCCESS, 0)])
def test_program_failure_or_preexisting_done_cannot_confirm_new_done(files, fake_processes, text, code):
    fake_processes["program"], fake_processes["program_code"] = text, code
    result = execute_tool.execute(files["plan_path"])
    assert not result["Passed"] and not result["DoneConfirmed"] and result["ProgrammingAttempted"]
    assert fake_processes["processes"][0].terminated


def test_valid_mock_configuration_preserves_plan_and_cleans_owned_processes(files, fake_processes):
    before = files["plan_path"].read_bytes()
    result = execute_tool.execute(files["plan_path"])
    assert result["Passed"] and result["DoneConfirmed"] and result["ProgrammingAttempted"]
    assert result["FlashWritten"] is False
    assert [p.stage for p in fake_processes["processes"]] == ["server", "scan", "program"]
    assert files["plan_path"].read_bytes() == before
    assert fake_processes["processes"][0].terminated
    assert all(p.pid in result["OwnedPIDs"] for p in fake_processes["processes"] if p.terminated or p.killed)
    saved = json.loads((files["work"] / "receipt.json").read_text())
    assert saved["Passed"] and saved["DoneConfirmed"]


def test_scan_server_exit_restarts_one_owned_program_server(files, fake_processes):
    fake_processes["server_exit_after_scan"] = True
    result = execute_tool.execute(files["plan_path"])
    assert result["Passed"] and result["DoneConfirmed"]
    assert [p.stage for p in fake_processes["processes"]] == ["server", "scan", "server-program", "program"]
    assert fake_processes["processes"][2].terminated


def test_foreign_listener_after_scan_never_restarts_or_programs(files, fake_processes):
    fake_processes["server_exit_after_scan"] = True
    fake_processes["conflict_after_scan"] = {99881}
    result = execute_tool.execute(files["plan_path"])
    assert not result["Passed"] and not result["ProgrammingAttempted"]
    assert [p.stage for p in fake_processes["processes"]] == ["server", "scan"]


def test_timeout_still_cleans_only_owned_processes(files, fake_processes):
    fake_processes["timeout_stage"] = "scan"
    result = execute_tool.execute(files["plan_path"], timeout_seconds=0.01)
    assert not result["Passed"] and not result["ProgrammingAttempted"]
    assert all(p.terminated for p in fake_processes["processes"])


def test_owned_cleanup_failure_does_not_leave_passed_receipt(files, fake_processes):
    fake_processes["cleanup_failure"] = True
    result = execute_tool.execute(files["plan_path"])
    assert not result["Passed"] and result["CleanupErrors"]


@pytest.mark.parametrize("seconds", (True, 0, -1, float("nan"), float("inf")))
def test_invalid_timeout_never_starts_process(files, fake_processes, seconds):
    with pytest.raises(ValueError):
        execute_tool.execute(files["plan_path"], timeout_seconds=seconds)
    assert fake_processes["processes"] == []
