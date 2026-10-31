"""Plan preparation validates source bindings and never starts hardware tools."""
from pathlib import Path
import json
import sys

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import prepare_hdmi_input_program as program


@pytest.fixture
def files(tmp_path, monkeypatch):
    root = tmp_path / "project"
    approved = root / "build/offline-20261024"
    approved.mkdir(parents=True)
    bit_work = root / "build/hdmi-uart-diagnostic/input-bit-fixture"
    (bit_work / "generate_bitstream").mkdir(parents=True)
    bit = bit_work / "generate_bitstream" / (program.TARGET + ".sbit")
    bit.write_bytes(b"SYNTHETIC BIT FIXTURE; NEVER PROGRAM")
    source = root / "source.v"
    source.write_bytes(b"SYNTHETIC SOURCE")
    evidence = bit_work / "evidence.json"
    evidence.write_text("{}", encoding="utf-8")
    adf = bit_work / "audited-final.adf"
    adf.write_bytes(b"SYNTHETIC ADF")
    (root / "tools").mkdir()
    for name in ("prepare_hdmi_input_program.py", "verify_hdmi_input_bitstream.py", "program_native_raw.py"):
        (root / "tools" / name).write_bytes(b"SYNTHETIC HELPER")
    plan = {"ProjectRoot": str(root), "WorkDirectory": str(bit_work),
            "ProjectInputSHA256": {"source.v": program.hw.sha(source)},
            "WorkInputSHA256": {"audited-final.adf": program.hw.sha(adf)}}
    (bit_work / "bitstream-plan.json").write_text(json.dumps(plan), encoding="utf-8")
    verified = {"Schema": "hdmi-input-bitstream-verification-v1", "Passed": True,
                "Target": program.TARGET, "FinalADFSHA256": program.bit_export.ADF_SHA256,
                "Bitstream": {"Path": str(bit), "Bytes": bit.stat().st_size,
                              "SHA256": program.hw.sha(bit), "Header": {"Design": program.TARGET}},
                "EvidenceSHA256": {"evidence.json": program.hw.sha(evidence)}}
    calls = []
    def verify(work):
        assert work == bit_work
        calls.append(work)
        return verified
    monkeypatch.setattr(program, "ROOT", root)
    monkeypatch.setattr(program, "APPROVED", approved)
    monkeypatch.setattr(program.verification, "verify", verify)
    monkeypatch.setattr(program.hw.subprocess, "Popen", lambda *a, **k: pytest.fail("no process start permitted"))
    pds = tmp_path / "fake-pds"
    pds.mkdir()
    for name in ("cdt_js.exe", "cdt_cfg_shell.exe"):
        (pds / name).write_bytes(b"SYNTHETIC PLACEHOLDER; NEVER START")
    return {"root": root, "approved": approved, "bit_work": bit_work, "bit": bit,
            "work": approved / "hdmi-input-program-fixture", "pds": pds,
            "verified": verified, "calls": calls, "source": source, "evidence": evidence}


def prepare(files):
    return program.prepare(files["bit_work"], files["work"], pds_bin=files["pds"])


def test_cli_writes_separate_source_bound_scan_and_program_plans_only(files, capsys):
    assert program.main(["--bit-work", str(files["bit_work"]), "--workdir", str(files["work"]),
                         "--pds-bin", str(files["pds"])]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["HardwareAccessed"] is False and summary["ExecutionSupported"] is False
    result = json.loads((files["work"] / "plan.json").read_text())
    assert files["calls"] == [files["bit_work"]]
    assert {path.name for path in files["work"].iterdir()} == {"scan.tcl", "program.tcl", "plan.json"}
    assert result["Bitstream"] == files["verified"]["Bitstream"]
    assert result["Operation"] == "volatile_sram_only"
    assert all(result[name] is False for name in ("HardwareAccessed", "Executed", "ProgrammingAttempted",
                                                "DoneConfirmed", "FlashWritten", "ExecutionSupported",
                                                "HardwareReleaseAllowed"))
    assert result["BoundInputSHA256"][str(files["source"])] == program.hw.sha(files["source"])
    assert result["BoundInputSHA256"][str(files["bit"])] == program.hw.sha(files["bit"])
    scan, script = [(files["work"] / (name + ".tcl")).read_text() for name in ("scan", "program")]
    assert "cfg_program" not in scan and "cfg_assign_file" not in scan
    assert script.count("cfg_program -device_index 0") == 1 and script.count("cfg_scan_chain") == 2
    assert str(files["bit"]).replace("\\", "/") in script
    assert "flash" not in script.lower() and "erase" not in script.lower()


@pytest.mark.parametrize("case", ("bit", "source", "evidence", "target", "adf", "failed", "bit_path", "evidence_escape"))
def test_changed_or_mismatched_verification_rejects_before_plan_creation(files, case):
    if case in ("bit", "source", "evidence"):
        files[case].write_bytes(b"CHANGED FIXTURE")
    elif case == "target":
        files["verified"]["Target"] = "heartbeat"
    elif case == "adf":
        files["verified"]["FinalADFSHA256"] = "0" * 64
    elif case == "failed":
        files["verified"]["Passed"] = False
    elif case == "bit_path":
        files["verified"]["Bitstream"]["Path"] = str(files["source"])
    else:
        files["verified"]["EvidenceSHA256"] = {str(files["source"]): program.hw.sha(files["source"])}
    with pytest.raises(ValueError):
        prepare(files)
    assert not files["work"].exists()


def test_verifier_failure_is_propagated_without_creating_plan(files, monkeypatch):
    def fail(work):
        raise ValueError("native verifier refused")
    monkeypatch.setattr(program.verification, "verify", fail)
    with pytest.raises(ValueError, match="native verifier refused"):
        prepare(files)
    assert not files["work"].exists()


def test_existing_plan_is_never_overwritten(files):
    files["work"].mkdir()
    marker = files["work"] / "prior.txt"
    marker.write_bytes(b"KEEP")
    with pytest.raises(ValueError, match="must be new"):
        prepare(files)
    assert marker.read_bytes() == b"KEEP" and files["calls"] == []


def test_workdir_must_be_a_named_child_of_the_existing_scratch_root(files):
    with pytest.raises(ValueError, match="child"):
        program.prepare(files["bit_work"], files["approved"].parent / "hdmi-input-program-escaped", pds_bin=files["pds"])
    assert files["calls"] == []


def test_execute_flag_is_not_supported(files):
    with pytest.raises(SystemExit) as error:
        program.main(["--bit-work", str(files["bit_work"]), "--workdir", str(files["work"]), "--execute"])
    assert error.value.code == 2 and files["calls"] == []
