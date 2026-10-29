"""Synthetic native reports exercise acceptance failures without PDS/hardware."""
from pathlib import Path
import hashlib
import json
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import audit_hdmi_uart_build as audit

KINDS = ("Setup", "Hold", "Recovery", "Removal", "Minimum Pulse Width")


def timing_text(*, declaration="All Constraints Met.", omit=None, duplicate=None,
                replacement=None):
    text = "Design Summary : " + declaration + "\n"
    for corner in ("Slow", "Fast"):
        for kind in KINDS:
            key = (kind, corner)
            if key == omit:
                continue
            clocks = "board27" if kind == "Minimum Pulse Width" else "board27 board27"
            row = clocks + " 0.125 0.000 0 8"
            if replacement and key == replacement[0]:
                row = replacement[1]
            section = f"{kind} Summary({corner} Corner):\n********\n{row}\n========\n"
            text += section
            if key == duplicate:
                text += section
    return text


@pytest.fixture
def native(tmp_path, monkeypatch):
    project = tmp_path / "source"
    project.mkdir()
    source = project / "source.v"
    source.write_text("module unchanged; endmodule\n", encoding="ascii")
    monkeypatch.setattr(audit, "ROOT", project)
    work = tmp_path / "build"
    (work / "place_route").mkdir(parents=True)
    (work / "report_timing").mkdir()
    target = "hdmi_uart_diag"
    pins = {"clk_27m": "D18", "uart_txd": "C24", "hd_scl": "K22", "hd_sda": "K23"}
    directions = {"clk_27m": "input", "uart_txd": "output", "hd_scl": "inout", "hd_sda": "inout"}
    fdc = work / (target + ".fdc")
    fdc.write_text("\n".join(
        f"define_attribute {{p:{port}}} {{PAP_IO_DIRECTION}} {{{directions[port].upper()}}}\n"
        f"define_attribute {{p:{port}}} {{PAP_IO_LOC}} {{{pad}}}" for port, pad in pins.items()), encoding="ascii")
    tcl = work / "build.tcl"
    tcl.write_text("# synthetic audit fixture; never run\n", encoding="ascii")
    for name in ("native-stdout.log", "native-stderr.log", f"place_route/{target}_pnr.adf", f"report_timing/{target}_rtp.adf"):
        (work / name).write_bytes(b"")
    report = work / "report_timing" / (target + ".rtr")
    report.write_text(timing_text(), encoding="ascii")
    pin_report = work / "place_route" / (target + "_prr_route_optimize.prt")
    pin_report.write_text("\n".join(f"{pad}|IOB|BANK|DIFF|{port}|{directions[port]}|YES" for port, pad in pins.items()), encoding="ascii")
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    plan = {"Target": target, "Pins": pins, "InputSHA256": {"source.v": digest(source)},
            "FDC": str(fdc), "FDCSHA256": digest(fdc), "TclSHA256": digest(tcl)}
    (work / "build-plan.json").write_text(json.dumps(plan), encoding="utf-8")
    (work / "execution.json").write_text('{"ReturnCode":0}', encoding="ascii")
    return work, report, pin_report, source


def refused(work):
    try:
        result = audit.audit(work)
    except ValueError:
        return True
    return not result["AuditPassed"]


def test_complete_native_reports_are_accepted_only_as_offline_evidence(native):
    result = audit.audit(native[0])
    assert result["AuditPassed"] and result["NativeTimingPassed"] and result["PinMapPassed"]
    assert result["AllTenTimingTypesChecked"] and len(result["TimingSummaries"]) == 10
    assert result["AllPinDirectionsChecked"] and result["ActualDirections"] == result["ExpectedDirections"]
    assert not result["HardwareAccessed"] and not result["HardwareReleaseAllowed"]


def test_missing_fast_corner_is_not_zero_failures(native):
    work, report, _, _ = native
    report.write_text(timing_text(omit=("Hold", "Fast")), encoding="ascii")
    assert refused(work)


def test_duplicate_native_table_is_not_a_second_corner(native):
    work, report, _, _ = native
    report.write_text(timing_text(duplicate=("Setup", "Slow")), encoding="ascii")
    assert refused(work)


def test_negative_hold_is_rejected_even_when_tool_exited_zero(native):
    work, report, _, _ = native
    report.write_text(timing_text(declaration="Some Constraints Violated.",
        replacement=(("Hold", "Fast"), "board27 board27 -0.015 -0.015 1 8")), encoding="ascii")
    result = audit.audit(work)
    assert result["BuildCompleted"] and not result["NativeTimingPassed"] and not result["AuditPassed"]


def test_positive_rows_cannot_override_violated_design_summary(native):
    work, report, _, _ = native
    report.write_text(timing_text(declaration="Some Constraints Violated."), encoding="ascii")
    assert refused(work)


def test_contradictory_or_nonfinite_row_cannot_hide_failure(native):
    work, report, _, _ = native
    for row in ("board27 board27 0.125 -0.250 0 8", "board27 board27 0.125 nan 0 8",
                "board27 board27 inf 0.000 0 8", "board27 board27 0.125 0.000 0 -8",
                "board27 board27 0.125 0.000 0 0", "board27 board27 0.125 0.000 -1 8",
                "board27 board27 -0.125 -0.500 9 8", "board27 board27 0.125 0.500 0 8",
                "board27 board27 0.125 0.000 0 8\nboard27 board27 nan 0.000 0 8"):
        report.write_text(timing_text(replacement=(("Hold", "Fast"), row)), encoding="ascii")
        assert refused(work), "invalid native row was accepted: " + row


def test_wrong_pad_and_wrong_clock_direction_both_fail(native):
    work, _, pins, _ = native
    original = pins.read_text(encoding="ascii")
    pins.write_text(original.replace("C24|", "C25|"), encoding="ascii")
    assert refused(work)
    pins.write_text(original.replace("clk_27m|input|", "clk_27m|output|"), encoding="ascii")
    assert refused(work), "clock input routed as output must fail direction audit"
    pins.write_text(original, encoding="ascii")
    fdc=work/'hdmi_uart_diag.fdc'
    text=fdc.read_text(encoding='ascii')
    for changed in (text.replace('define_attribute {p:clk_27m} {PAP_IO_DIRECTION} {INPUT}\n',''),
                    text+'\ndefine_attribute {p:clk_27m} {PAP_IO_DIRECTION} {INPUT}\n'):
        fdc.write_text(changed,encoding='ascii')
        plan=json.loads((work/'build-plan.json').read_text(encoding='utf-8'))
        plan['FDCSHA256']=hashlib.sha256(fdc.read_bytes()).hexdigest()
        (work/'build-plan.json').write_text(json.dumps(plan),encoding='utf-8')
        assert refused(work), 'missing or duplicate direction must not be inferred'


def test_source_drift_rejects_otherwise_good_timing_and_pins(native):
    work, _, _, source = native
    source.write_text("module changed; endmodule\n", encoding="ascii")
    result = audit.audit(work)
    assert result["NativeTimingPassed"] and result["PinMapPassed"]
    assert not result["AuditPassed"] and result["SourceDrift"] == ["source.v"]
