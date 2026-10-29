"""Keep the HDMI30 candidate isolated from the accepted baseline and its hashes."""
from pathlib import Path
import copy
import json
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_board1080_hdmi30 as tool


def test_real_profile_replaces_one_controller_and_preserves_other_108_sources():
    roles = tool.validate_profile()
    base = tool.timing.validate_manifest(tool.PROJECT, tool.BASE)
    assert len(roles["Sources"]) == 109
    assert set(roles["Sources"]) - set(base["Sources"]) == {tool.REPLACEMENT}
    assert set(base["Sources"]) - set(roles["Sources"]) == {tool.ORIGINAL}
    assert roles["ConstraintSHA256"] == base["ConstraintSHA256"]
    assert set(roles["ExplicitDesigns"]) - set(base["ExplicitDesigns"]) == {tool.REPLACEMENT}
    assert len(roles["IDFExpandedSources"]) == 74
    assert roles["SourceSHA256"]["board/board1080_rowpipe_top.v"] == base["SourceSHA256"]["board/board1080_rowpipe_top.v"]


@pytest.mark.parametrize("mutation", ("both_controllers", "old_controller", "wrong_hash", "wrong_constraint", "different_top"))
def test_edited_manifest_cannot_smuggle_other_changes(tmp_path, monkeypatch, mutation):
    expected = tool.expected_manifest()
    changed = copy.deepcopy(expected)
    if mutation == "both_controllers": changed["source_files"].append(tool.ORIGINAL)
    elif mutation == "old_controller":
        changed["source_files"] = [tool.ORIGINAL if name == tool.REPLACEMENT else name for name in changed["source_files"]]
    elif mutation == "wrong_hash": changed["SourceSHA256"][tool.REPLACEMENT] = "0" * 64
    elif mutation == "wrong_constraint": changed["Constraint"] = "board/unsafe.fdc"
    else: changed["Target"] = "camera_top"
    path = tmp_path / tool.MANIFEST
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(changed), encoding="utf-8")
    monkeypatch.setattr(tool, "expected_manifest", lambda _: expected)
    with pytest.raises(ValueError, match="single-controller"):
        tool.validate_profile(tmp_path)


def test_manifest_does_not_claim_old_timing_or_bitstream_for_new_source():
    profile = tool.expected_manifest()
    assert profile["HDMIControllerReplacement"]["PriorTimingOrBitstreamReusable"] is False
    assert profile["BaseManifest"]["SHA256"] == tool.timing.sha(tool.PROJECT / tool.BASE)


def test_profile_preparation_requires_valid_profile_before_any_build_writes(tmp_path, monkeypatch):
    def invalid(_): raise ValueError("unverified EDID")
    monkeypatch.setattr(tool, "validate_profile", invalid)
    with pytest.raises(ValueError, match="unverified EDID"):
        tool.prepare(tmp_path, tmp_path / "work")
    assert not (tmp_path / "work").exists()
