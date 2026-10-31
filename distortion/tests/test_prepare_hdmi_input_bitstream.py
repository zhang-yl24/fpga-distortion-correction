"""The bit export gate rejects changed native evidence and source bindings."""
from pathlib import Path
import gzip
import json
import re
import shutil
import sys

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import prepare_hdmi_input_bitstream as export

ROOT = TOOLS.parent
PACKAGE = ROOT / export.EVIDENCE


@pytest.fixture(scope="module")
def native(tmp_path_factory):
    work = tmp_path_factory.mktemp("native_hdmi_bit")
    # All fixtures are committed evidence, never a local build dependency.
    for source, name in (("scoped-cdc/hdmi_uart_input_diag.rtr.gz", "source.rtr"),
                         ("scoped-cdc/hdmi_uart_input_diag_exception.rtr.gz", "source_exception.rtr")):
        (work / name).write_bytes(gzip.decompress((PACKAGE / source).read_bytes()))
    return work / "source.rtr", work / "source_exception.rtr"


def altered_exception(tmp_path, native, transform):
    path = tmp_path / "candidate_exception.rtr"
    path.write_text(transform(export.read_text(native[1])), encoding="utf-8")
    return path


def test_native_recheck_keeps_max_bounds_and_precise_exceptions(native):
    result = export.compare_native(*native, *native)
    assert result["AllTenTimingTypesPassed"]
    assert result["MaxDelayCountPerCorner"] == {"slow": 167, "fast": 167}
    assert result["FalsePathCountPerCorner"]["slow"] == dict(setup=0, hold=167, recovery=4, removal=4)


def test_rejects_native_failing_summary_even_when_banner_passes(tmp_path, native):
    text = export.read_text(native[0]).split("Startpoint", 1)[0]
    text, count = re.subn(r"(cfg_clk\s+board27\s+)1\.079", r"\g<1>-1.079", text, count=1)
    assert count == 1
    report = tmp_path / "failed.rtr"
    report.write_text(text)
    with pytest.raises(ValueError, match="native timing check failed"):
        export.compare_native(*native, report, native[1])


def test_rejects_missing_native_corner_table(tmp_path, native):
    text = export.read_text(native[0]).split("Startpoint", 1)[0]
    text = text.replace("Minimum Pulse Width Summary(Fast Corner):", "Removed table:", 1)
    report = tmp_path / "incomplete.rtr"
    report.write_text(text)
    with pytest.raises(ValueError):
        export.compare_native(*native, report, native[1])


def test_rejects_relaxed_max_delay_bound(tmp_path, native):
    candidate = altered_exception(tmp_path, native, lambda s: s.replace("MaxDelay Path 8.000ns", "MaxDelay Path 9.000ns", 1))
    with pytest.raises(ValueError, match="8 ns"):
        export.compare_native(*native, native[0], candidate)


def test_rejects_missing_max_delay_endpoint(tmp_path, native):
    def drop(s):
        starts = list(re.finditer(r"^Startpoint", s, re.M))
        return s[:starts[0].start()] + s[starts[1].start():]
    candidate = altered_exception(tmp_path, native, drop)
    with pytest.raises(ValueError, match="unexpected exception count"):
        export.compare_native(*native, native[0], candidate)


def test_rejects_redirected_max_delay_path(tmp_path, native):
    candidate = altered_exception(tmp_path, native, lambda s: s.replace("Startpoint  : input_status/p_reset[1]/opit_0/CLK", "Startpoint  : input_status/p_reset[0]/opit_0/CLK", 1))
    with pytest.raises(ValueError, match="MaxDelay identities"):
        export.compare_native(*native, native[0], candidate)


def test_rejects_changed_max_delay_slack(tmp_path, native):
    candidate = altered_exception(tmp_path, native, lambda s: re.sub(r"( Slack \(MET\)\s+)6\.878", r"\g<1>6.879", s, count=1))
    with pytest.raises(ValueError, match="MaxDelay identities"):
        export.compare_native(*native, native[0], candidate)


def test_rejects_false_path_redirected_to_second_stage(tmp_path, native):
    def redirect(s):
        at = s.index("| Exception type  : set_false_path(hold)")
        prefix, suffix = s[:at], s[at:]
        suffix, count = re.subn(r"(Endpoint\s*:\s*input_status/geometry/edge_)meta(\[\d+\]/opit_0/D)", r"\1sync\2", suffix, count=1)
        assert count == 1
        return prefix + suffix
    candidate = altered_exception(tmp_path, native, redirect)
    with pytest.raises(ValueError, match="false-path identities"):
        export.compare_native(*native, native[0], candidate)


def test_evidence_decoder_checks_stored_and_decoded_hashes(tmp_path):
    package, entries = export.evidence_entries(ROOT)
    name = "scoped-cdc/input.adf.gz"
    data = export.evidence_bytes(package, entries, name)
    assert export.digest(data) == export.ADF_SHA256
    wrong = {name: dict(entries[name], SourceSHA256="0" * 64)}
    with pytest.raises(ValueError, match="decoded evidence changed"):
        export.evidence_bytes(package, wrong, name)
    wrong = {name: dict(entries[name], SHA256="0" * 64)}
    with pytest.raises(ValueError, match="stored evidence changed"):
        export.evidence_bytes(package, wrong, name)


def test_exact_manifest_and_workdir_are_required(tmp_path):
    with pytest.raises(ValueError, match="fresh input-bit"):
        export.prepare(tmp_path / "input-bit-a")
    package = tmp_path / export.EVIDENCE
    package.mkdir(parents=True)
    (package / "manifest.json").write_text("{}")
    with pytest.raises(ValueError, match="manifest changed"):
        export.evidence_entries(tmp_path)


def test_current_source_mismatch_prevents_preparation(tmp_path):
    project = tmp_path / "p"
    package = project / export.EVIDENCE
    (package / "native-build").mkdir(parents=True)
    # Only files read before source validation are needed; avoid copying deep
    # evidence trees into Windows pytest paths near MAX_PATH.
    for name in ("manifest.json", "native-build/build-plan.json"):
        shutil.copyfile(PACKAGE / name, package / name)
    build = json.loads((package / "native-build/build-plan.json").read_text())
    first = next(iter(build["InputSHA256"]))
    current = project / first
    current.parent.mkdir(parents=True)
    current.write_text("changed source\n")
    output = project / "build/hdmi-uart-diagnostic/input-bit-rejected"
    with pytest.raises(ValueError, match="current source differs"):
        export.prepare(output, project=project)
    assert not output.exists()


def test_runtime_source_change_blocks_gate_before_any_pass_receipt(tmp_path, monkeypatch):
    project = tmp_path / "project"
    work = project / "build/hdmi-uart-diagnostic/input-bit-a"
    work.mkdir(parents=True)
    source = project / "source.v"
    source.write_text("old")
    adf = work / "audited-final.adf"
    adf.write_bytes(b"changed adf")
    plan = dict(Target=export.TARGET, FinalADFSHA256=export.ADF_SHA256,
                ProjectRoot=str(project), WorkDirectory=str(work),
                ProjectInputSHA256={"source.v": export.sha(source)}, WorkInputSHA256={})
    (work / "bitstream-plan.json").write_text(json.dumps(plan))
    source.write_text("new")
    monkeypatch.setattr(export, "ROOT", project)
    with pytest.raises(ValueError, match="project input changed"):
        export.audit_work(work)
    assert not (work / "pre-bit-audit.json").exists()
