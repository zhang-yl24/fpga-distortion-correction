"""New-target report comparator counterexamples use committed evidence only."""
from pathlib import Path
import gzip
import json
import re
import sys

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import audit_hdmi_trained_native as audit
import prepare_hdmi_input_bitstream as original

PACKAGE = TOOLS.parent / "results/hdmi-input-observer-20261030/scoped-cdc"


@pytest.fixture(scope="module")
def native(tmp_path_factory):
    work = tmp_path_factory.mktemp("trained_native")
    report = gzip.decompress((PACKAGE / "hdmi_uart_input_diag.rtr.gz").read_bytes()).decode("utf-8")
    # Timing summaries and clocks precede detailed paths. Preserve all of that
    # native text and replace only the declared design in the test fixture.
    report = report.replace("\r\n", "\n").replace("\r", "\n").split("Startpoint", 1)[0]
    report, count = re.subn(r"(?m)^(\| Design\s*:\s*)hdmi_uart_input_diag\s*$", r"\g<1>" + audit.TARGET, report)
    assert count == 1
    exceptions = gzip.decompress((PACKAGE / "hdmi_uart_input_diag_exception.rtr.gz").read_bytes())
    (work / "baseline.rtr").write_text(report, encoding="utf-8")
    (work / "exceptions.rtr").write_bytes(exceptions)
    return work / "baseline.rtr", work / "exceptions.rtr"


def candidate(tmp_path, path, transform):
    altered = tmp_path / path.name
    text = audit.read_text(path)
    changed = transform(text)
    assert changed != text
    altered.write_text(changed, encoding="utf-8")
    return altered


def test_native_new_target_passes_exact_scope(native):
    result = audit.compare(*native, *native)
    assert result["AuditPassed"] and result["AllTenTimingTypesPassed"]
    assert result["Target"] == "hdmi_uart_trained_diag"
    assert result["MaxDelayCountPerCorner"] == dict(slow=167, fast=167)
    assert result["FalsePathCountPerCorner"] == {c: dict(setup=0, hold=167, recovery=4, removal=4) for c in ("slow", "fast")}
    assert result["HardwareAccessed"] is result["HardwareReleaseAllowed"] is False
    assert audit.exception_inventory is original.exception_inventory


@pytest.mark.parametrize("transform, message", [
    (lambda text: text.replace(audit.TARGET, "hdmi_uart_input_diag", 1), "design/device mismatch"),
    (lambda text: text.replace("| Device       : PG2L100H", "| Device       : PG2L50H", 1), "design/device mismatch"),
    (lambda text: text.replace("All Constraints Met.", "Constraints Not Met.", 1), "all-constraints-met"),
    (lambda text: text.replace("Minimum Pulse Width Summary(Fast Corner):", "Removed corner:", 1), "all ten"),
    (lambda text: re.sub(r"(board27\s+board27\s+)22\.557", r"\g<1>-0.001", text, count=1), "timing check failed"),
    (lambda text: re.sub(r"(board27\s+board27\s+22\.557\s+0\.000\s+)0", r"\g<1>1", text, count=1), "timing check failed"),
    (lambda text: re.sub(r"(board27\s+board27\s+22\.557\s+)0\.000", r"\g<1>-0.001", text, count=1), "timing check failed"),
    (lambda text: re.sub(r"(board27\s+board27\s+22\.557\s+0\.000\s+0\s+)2974", r"\g<1>0", text, count=1), "timing check failed"),
    (lambda text: text.replace("37.0370", "37.0380", 1), "summary or clock inventory"),
    (lambda text: re.sub(r"(cfg_clk\s+board27\s+)1\.079", r"\g<1>1.080", text, count=1), "summary or clock inventory"),
])
def test_rejects_wrong_target_missing_corner_failure_or_changed_clock(tmp_path, native, transform, message):
    report = candidate(tmp_path, native[0], transform)
    with pytest.raises(ValueError, match=message):
        audit.compare(*native, report, native[1])


def test_rejects_ambiguous_design_header(tmp_path, native):
    report = candidate(tmp_path, native[0], lambda text: text.replace("| Device", "| Design       : " + audit.TARGET + "\n| Device", 1))
    with pytest.raises(ValueError, match="design/device mismatch"):
        audit.compare(*native, report, native[1])


@pytest.mark.parametrize("transform, message", [
    (lambda text: text.replace("MaxDelay Path 8.000ns", "MaxDelay Path 9.000ns", 1), "8 ns"),
    (lambda text: text.replace("input_status/p_reset[1]/opit_0/CLK", "input_status/p_reset[0]/opit_0/CLK", 1), "MaxDelay identities"),
    (lambda text: re.sub(r"( Slack \(MET\)\s+)6\.878", r"\g<1>6.879", text, count=1), "MaxDelay identities"),
    (lambda text: text.replace("| Exception type  : set_max_delay(recovery)", "| Exception type  : unsupported(recovery)", 1), "all 24"),
])
def test_rejects_changed_bound_source_slack_or_exception_inventory(tmp_path, native, transform, message):
    exceptions = candidate(tmp_path, native[1], transform)
    with pytest.raises(ValueError, match=message):
        audit.compare(*native, native[0], exceptions)


def test_rejects_missing_max_delay_path(tmp_path, native):
    def drop(text):
        starts = list(re.finditer(r"^Startpoint", text, re.M))
        return text[:starts[0].start()] + text[starts[1].start():]
    exceptions = candidate(tmp_path, native[1], drop)
    with pytest.raises(ValueError, match="unexpected exception count"):
        audit.compare(*native, native[0], exceptions)


@pytest.mark.parametrize("kind", ["hold", "recovery", "removal"])
def test_rejects_redirected_false_path(tmp_path, native, kind):
    def redirect(text):
        at = text.index("| Exception type  : set_false_path(" + kind + ")")
        prefix, suffix = text[:at], text[at:]
        suffix, count = re.subn(r"(Endpoint\s*:\s*)(\S+)", r"\g<1>unexpected/second_stage/D", suffix, count=1)
        assert count == 1
        return prefix + suffix
    exceptions = candidate(tmp_path, native[1], redirect)
    with pytest.raises(ValueError, match="false-path identities"):
        audit.compare(*native, native[0], exceptions)


def test_invalid_baseline_is_rejected_even_if_candidate_matches_it(tmp_path, native):
    exceptions = candidate(tmp_path, native[1], lambda text: text.replace("MaxDelay Path 8.000ns", "MaxDelay Path 9.000ns", 1))
    with pytest.raises(ValueError, match="8 ns"):
        audit.compare(native[0], exceptions, native[0], exceptions)


def test_cli_preserves_existing_receipt(tmp_path, native):
    output = tmp_path / "audit.json"
    args = ["--baseline-report", str(native[0]), "--baseline-exceptions", str(native[1]),
            "--report", str(native[0]), "--exceptions", str(native[1]), "--output", str(output)]
    assert audit.main(args) == 0
    before = output.read_bytes()
    assert json.loads(before)["AuditPassed"]
    with pytest.raises(SystemExit):
        audit.main(args)
    assert output.read_bytes() == before
