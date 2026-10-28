"""Pinned-script synthetic log classification only; no CAD or device access."""
from pathlib import Path
import shutil
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import pds_gate_log_audit as audit


def fixture_log(tmp_path, target, role=None):
    if target == audit.MAIN and role != audit.CANONICAL_MAIN:
        source = ROOT / "build/offline-20261024/gamma-pipeline-reseed3-build-20261026-h/reseed.tcl"
        shutil.copyfile(source, tmp_path / "reseed.tcl")
    script, expected, commands = audit.script_context(tmp_path, target, role)
    lines = ["License checkout: fabric_shell from E:\\Pango\\test.lic", "Compiling architecture definition.", "", *expected,
             f"Analyzing project file '{tmp_path.as_posix()}/{target}.pds'."]
    for stage in audit.STAGES:
        lines.extend(("Executing : " + commands[stage], "Executing : " + commands[stage] + " successfully."))
    return script, expected, commands, lines


@pytest.mark.parametrize("target", [audit.MAIN, audit.RAW720])
def test_two_pinned_scripts_accept_only_post_build_log_audit(tmp_path, target):
    script, errors, commands, lines = fixture_log(tmp_path, target)
    result = audit.audit_text("\n".join(lines), "", work=tmp_path, target=target,
                              script=script, expected_errors=errors, commands=commands)
    assert result["Passed"] is True and len(result["ActualStages"]) == 6
    assert result["PreBitGateExecutionProven"] is False and result["ValidatedManifestWritten"] is False


@pytest.mark.parametrize("fault", ["unknown-prefix", "runtime-E", "runtime-F", "runtime-ERROR", "wrong-path", "wrong-line", "missing-stage", "wrong-project", "stderr"])
def test_unknown_errors_paths_or_incomplete_flow_are_rejected(tmp_path, fault):
    target = audit.RAW720
    script, errors, commands, lines = fixture_log(tmp_path, target)
    stderr = ""
    if fault == "unknown-prefix":
        lines.insert(1, "E: unexpected license/source failure")
    if fault == "runtime-E":
        lines.append("E: unexpected runtime fault")
    if fault == "runtime-F":
        lines.append("F: unexpected runtime fault")
    if fault == "runtime-ERROR":
        lines.append("I: internal ERROR has occurred")
    if fault == "wrong-path":
        lines = [line.replace("/report_timing/", "/wrong_report_timing/") for line in lines]
    if fault == "wrong-line":
        lines = [line.replace("at line 38.", "at line 39.") for line in lines]
    if fault == "missing-stage":
        lines.remove("Executing : " + commands["pnr"] + " successfully.")
    if fault == "wrong-project":
        lines = [line.replace(f"/{target}.pds'", "/another.pds'") for line in lines]
    if fault == "stderr":
        stderr = "runtime diagnostic"
    with pytest.raises(ValueError):
        audit.audit_text("\n".join(lines), stderr, work=tmp_path, target=target,
                         script=script, expected_errors=errors, commands=commands)


def test_script_pin_and_unknown_target_fail_closed(tmp_path):
    with pytest.raises(ValueError):
        audit.script_context(tmp_path, "unlisted-target")
    (tmp_path / "reseed.tcl").write_text("unreviewed source script")
    with pytest.raises(ValueError, match="script bytes changed"):
        audit.script_context(tmp_path, audit.MAIN)


def test_canonical_main_role_is_explicit_and_does_not_guess_from_files(tmp_path):
    (tmp_path/'reseed.tcl').write_text('unreviewed unrelated file')
    script, errors, commands, lines = fixture_log(tmp_path, audit.MAIN, audit.CANONICAL_MAIN)
    assert script == ROOT/'board/build-corrected_gamma_pipeline_d5.tcl'
    assert '/board/report_timing/' in errors[2]
    result = audit.audit_text('\n'.join(lines), '', work=tmp_path, target=audit.MAIN,
                              script=script, expected_errors=errors, commands=commands)
    assert result['Passed'] and result['PreBitGateExecutionProven'] is False
    with pytest.raises(ValueError, match='script bytes changed'):
        audit.script_context(tmp_path, audit.MAIN, audit.RESEEDED_MAIN)
    with pytest.raises(ValueError, match='target/script role'):
        audit.script_context(tmp_path, audit.RAW720, audit.CANONICAL_MAIN)


def test_real_latest_H_runtime_failure_still_rejected_and_raw720_still_audits():
    base = ROOT/'build/offline-20261024'
    with pytest.raises(ValueError, match='execution suffix'):
        audit.audit_gate_log(base/'gamma-pipeline-reseed3-build-20261026-h', audit.MAIN, audit.RESEEDED_MAIN)
    actual = audit.audit_gate_log(base/'raw720-cam2-build-20261026-a', audit.RAW720, audit.RAW720_ROLE)
    assert actual['Passed'] and actual['ExactGatePreparseErrorsAllowed'] == 12
    assert actual['CADScriptRole'] == audit.RAW720_ROLE
