"""Focused checks for the read-only HDMI observer export verifier."""
from pathlib import Path
import hashlib
import json
import sys

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import verify_hdmi_input_bitstream as verification


def header_bytes(**overrides):
    values = {
        "a": verification.prepare.TARGET,
        "b": "Logos2-PG2L100H--6-FBG676",
        "c": "10/30/26",
        "d": "11:01:12",
        "e": "Fabric Compiler",
        "f": "2023.2-SP3<154097>",
    }
    values.update(overrides)
    data = bytes.fromhex("00090ff00ff00ff00ff000") + b"PANGO MICROSYSTEMS, INC.\0\1"
    for tag in "abcdef":
        value = values[tag].encode("ascii") + b"\0"
        data += tag.encode("ascii") + len(value).to_bytes(2, "big") + value
    return data + b"ghi"


def native_log(work, *, extra=""):
    adf = work / "audited-final.adf"
    adf.write_bytes(b"ADF")
    return "\n".join([
        'Process "Report Timing" started.',
        'Process "Report Timing" done.',
        "HDMI_INPUT_PRE_BIT_AUDIT_PASS " + verification.prepare.ADF_SHA256,
        'Executing : gen_bit_stream -force_to_run -input_db_file {' + str(adf).replace('\\', '/') + '}',
        'Process "Generate Bitstream" started.',
        'Process "Generate Bitstream" done.',
        "HDMI_INPUT_BITSTREAM_COMPLETE",
        extra,
    ]) + "\n"


def test_bitstream_header_requires_exact_identity():
    values = verification.bitstream_header(header_bytes())
    assert values["Design"] == verification.prepare.TARGET
    assert values["Device"] == "Logos2-PG2L100H--6-FBG676"
    with pytest.raises(ValueError, match="identity differs"):
        verification.bitstream_header(header_bytes(b="Logos2-PG2L100H--6-FBG676-OTHER"))


def test_actual_stages_use_process_events_and_bind_generation_adf(tmp_path):
    text = native_log(tmp_path)
    result = verification.actual_stages(text, tmp_path)
    assert result["ActualStages"] == ["report_timing", "runtime_native_audit", "gen_bit_stream"]
    assert result["GenerationInputADF"] == str((tmp_path / "audited-final.adf").resolve())
    with pytest.raises(ValueError, match="actual stage order"):
        verification.actual_stages(text.replace("Process \"Report Timing\" done.", "Process \"Unexpected\" done."), tmp_path)


def test_actual_stages_reject_extra_errors_and_wrong_audit_marker(tmp_path):
    with pytest.raises(ValueError, match="pre-bit audit marker"):
        verification.actual_stages(native_log(tmp_path).replace(verification.prepare.ADF_SHA256, "0" * 64), tmp_path)
    with pytest.raises(ValueError, match="native stdout contains an error"):
        verification.actual_stages(native_log(tmp_path, extra="ERROR unexpected"), tmp_path)


def test_check_execution_preserves_and_reconciles_historical_classifier_failure(tmp_path):
    stdout = tmp_path / "native-stdout.log"
    stderr = tmp_path / "native-stderr.log"
    stdout.write_text(native_log(tmp_path), encoding="utf-8")
    stderr.write_bytes(b"")
    plan = {"Command": ["pds_shell.exe", "-file", "export.tcl"], "Target": verification.prepare.TARGET}
    receipt = {
        "Schema": "hdmi-input-bitstream-execution-v1", "Target": verification.prepare.TARGET,
        "Command": plan["Command"], "SourceADFSHA256": verification.prepare.ADF_SHA256,
        "ReturnCode": 0, "HardwareAccessed": False, "Passed": False,
        "Error": verification.CLASSIFIER_ERROR,
        "LogSHA256": {"native-stdout.log": hashlib.sha256(stdout.read_bytes()).hexdigest(),
                       "native-stderr.log": hashlib.sha256(b"").hexdigest()},
    }
    (tmp_path / "export-result.json").write_text(json.dumps(receipt), encoding="utf-8")
    result = verification.check_execution(tmp_path, plan)
    assert result["StageClassifierFailureReconciled"] is True
    assert result["PassedAsRecorded"] is False
    assert verification.CLASSIFIER_ERROR in result["ErrorAsRecorded"]


def test_check_execution_rejects_unrecognized_failed_receipt(tmp_path):
    stdout = tmp_path / "native-stdout.log"
    stderr = tmp_path / "native-stderr.log"
    stdout.write_text(native_log(tmp_path), encoding="utf-8")
    stderr.write_bytes(b"")
    plan = {"Command": ["pds_shell.exe"], "Target": verification.prepare.TARGET}
    receipt = {"Schema": "hdmi-input-bitstream-execution-v1", "Target": verification.prepare.TARGET,
               "Command": plan["Command"], "SourceADFSHA256": verification.prepare.ADF_SHA256,
               "ReturnCode": 0, "HardwareAccessed": False, "Passed": False, "Error": "different",
               "LogSHA256": {"native-stdout.log": hashlib.sha256(stdout.read_bytes()).hexdigest(),
                              "native-stderr.log": hashlib.sha256(b"").hexdigest()}}
    (tmp_path / "export-result.json").write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(ValueError, match="unrecognized execution receipt failure"):
        verification.check_execution(tmp_path, plan)


@pytest.fixture
def exported(tmp_path, monkeypatch):
    project = tmp_path / "project"
    work = project / "build/hdmi-uart-diagnostic/input-bit-fixture"
    work.mkdir(parents=True)
    native = {"AllTenTimingTypesPassed": True, "ExactFalsePathsUnchanged": True,
              "MaxDelayCountPerCorner": {"slow": 167, "fast": 167}}
    text = native_log(work)
    (work / "native-stdout.log").write_text(text, encoding="utf-8")
    (work / "native-stderr.log").write_bytes(b"")
    (work / "export.tcl").write_text("gen_bit_stream -input_db_file {" +
                                   str(work / "audited-final.adf").replace("\\", "/") + "}\n", encoding="utf-8")
    for name in (verification.REPORT, verification.EXCEPTIONS):
        (work / name).parent.mkdir(parents=True, exist_ok=True)
        (work / name).write_bytes(b"SYNTHETIC REPORT")
    plan = {"ProjectRoot": str(project), "WorkDirectory": str(work), "Target": verification.prepare.TARGET,
            "ProjectInputSHA256": {}, "WorkInputSHA256": {"export.tcl": verification.sha(work / "export.tcl")},
            "SourceNativeAudit": native, "Command": ["fixture-pds"]}
    (work / "bitstream-plan.json").write_text(json.dumps(plan), encoding="utf-8")
    audit = dict(Schema="hdmi-input-pre-bit-audit-v1", AuditPassed=True, Target=verification.prepare.TARGET,
                 FinalADFSHA256=verification.prepare.ADF_SHA256, HardwareAccessed=False,
                 HardwareReleaseAllowed=False, **native)
    audit["EvidenceSHA256"] = {name: verification.sha(work / name) for name in verification.PRE_BIT_EVIDENCE}
    (work / "pre-bit-audit.json").write_text(json.dumps(audit), encoding="utf-8")
    receipt = {"Schema": "hdmi-input-bitstream-execution-v1", "Target": verification.prepare.TARGET,
               "Command": plan["Command"], "SourceADFSHA256": verification.prepare.ADF_SHA256,
               "ReturnCode": 0, "HardwareAccessed": False, "Passed": False, "Error": verification.CLASSIFIER_ERROR,
               "LogSHA256": {name: verification.sha(work / name) for name in ("native-stdout.log", "native-stderr.log")}}
    (work / "export-result.json").write_text(json.dumps(receipt), encoding="utf-8")
    data = header_bytes() + b"SYNTHETIC BITSTREAM; NEVER PROGRAM"
    (work / verification.BITSTREAM).parent.mkdir()
    (work / verification.BITSTREAM).write_bytes(data)
    monkeypatch.setattr(verification.prepare, "ROOT", project)
    monkeypatch.setattr(verification.prepare, "verify_inputs", lambda *args: None)
    monkeypatch.setattr(verification.prepare, "compare_native", lambda *args: native)
    monkeypatch.setattr(verification, "BIT_BYTES", len(data))
    monkeypatch.setattr(verification, "BIT_SHA256", hashlib.sha256(data).hexdigest())
    return work


def test_complete_verifier_is_read_only_and_records_relative_evidence(exported):
    before = {str(path): path.read_bytes() for path in exported.rglob("*") if path.is_file()}
    result = verification.verify(exported)
    assert result["Passed"] and result["ExecutionReceipt"]["StageClassifierFailureReconciled"]
    assert result["HardwareAccessed"] is False and result["HardwareReleaseAllowed"] is False
    assert result["Bitstream"]["Path"] == str(exported / verification.BITSTREAM)
    assert all(not Path(name).is_absolute() for name in result["EvidenceSHA256"])
    assert before == {str(path): path.read_bytes() for path in exported.rglob("*") if path.is_file()}


@pytest.mark.parametrize("case,match", [("bit", "bitstream bytes"), ("pre_bit", "audit evidence hashes"),
    ("audit_value", "audit value"), ("log", "log hashes"), ("exit", "did not exit zero"),
    ("bgr", "did not succeed"), ("tcl_adf", "source ADF path")])
def test_complete_verifier_rejects_changed_output_or_receipt(exported, case, match):
    if case == "bit":
        (exported / verification.BITSTREAM).write_bytes(b"DIFFERENT")
    elif case == "pre_bit":
        (exported / verification.REPORT).write_bytes(b"CHANGED REPORT")
    elif case == "audit_value":
        path = exported / "pre-bit-audit.json"
        value = json.loads(path.read_text())
        value["AllTenTimingTypesPassed"] = False
        path.write_text(json.dumps(value))
    elif case == "log":
        (exported / "native-stdout.log").write_text("CHANGED LOG")
    elif case == "exit":
        path = exported / "export-result.json"
        value = json.loads(path.read_text())
        value["ReturnCode"] = 1
        path.write_text(json.dumps(value))
    elif case == "bgr":
        (exported / "generate_bitstream" / (verification.prepare.TARGET + ".bgr")).write_text("ERROR failed")
    else:
        path = exported / "export.tcl"
        path.write_text("gen_bit_stream -input_db_file {wrong.adf}\n")
        audit = exported / "pre-bit-audit.json"
        value = json.loads(audit.read_text())
        value["EvidenceSHA256"]["export.tcl"] = verification.sha(path)
        audit.write_text(json.dumps(value))
    with pytest.raises(ValueError, match=match):
        verification.verify(exported)


def test_cli_writes_only_new_receipt(exported, tmp_path):
    output = tmp_path / "verification.json"
    assert verification.main(["--workdir", str(exported), "--output", str(output)]) == 0
    before = output.read_bytes()
    with pytest.raises(SystemExit):
        verification.main(["--workdir", str(exported), "--output", str(output)])
    assert output.read_bytes() == before
