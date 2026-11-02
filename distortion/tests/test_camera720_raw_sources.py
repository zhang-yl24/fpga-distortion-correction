"""Source-mode and full-size raw pixel contracts; no PDS/serial access."""
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import prepare_camera720_raw_sources as source
import run_camera720_raw_sim as sim
from frame_protocol import encode


def test_current_mode_retains_parent_input_reset_and_exact_source_inventory():
    roles = source.validate_sources()
    manifest = roles["Manifest"]
    assert len(roles["Sources"]) == 101 and len(roles["ExplicitDesigns"]) == 21
    assert manifest["RawCaptureContract"]["image_size"] == [1280, 720]
    assert manifest["Preview"]["WordsPerFrame"] < manifest["Preview"]["WordsPerBank"]
    for name in ("rtl/experimental/raw_camera_input_delay.v", "rtl/experimental/raw_camera_power_ready.v"):
        assert manifest["SourceSHA256"][name] == source.parent()["SourceSHA256"][name]
    assert "rtl/camera_preview.v" not in roles["Sources"]
    assert "rtl/experimental/ov5640_cadence_upright_init.v" not in roles["Sources"]
    assert roles["ExplicitDesigns"].count("platform/video_base/ipcore/ddr3_test/ddr3_test.idf") == 1
    assert not any(n.endswith(".vp") for n in roles["ExplicitDesigns"])


def test_top_changes_beyond_mode_parameters_are_rejected(monkeypatch):
    original = source.expected_top
    monkeypatch.setattr(source, "expected_top", lambda: original().replace(b".rst_n(ddr_reset_sync[1])", b".rst_n(camera_ready)", 1))
    with pytest.raises(ValueError, match="exact derivative"):
        source.validate_sources()


def test_parent_drift_is_rejected(monkeypatch):
    original = source.sha
    monkeypatch.setattr(source, "sha", lambda path: "0" * 64 if Path(path).name == "raw_camera_input_delay.v" else original(path))
    with pytest.raises(ValueError, match="parent source changed"):
        source.validate_sources()


@pytest.fixture
def wire_path(tmp_path):
    pixels = ((np.arange(921600, dtype=np.uint32) * 53) ^ 0x4321).astype("<u2")
    path = tmp_path / "wire.bin"
    path.write_bytes(encode(1280, 720, 41, pixels.tobytes()))
    return path


def test_all_720_pixels_and_existing_host_parser(wire_path):
    result = sim.audit_wire(wire_path)
    assert result["PixelsCompared"] == 921600 and result["HostParserPassed"]


def test_last_pixel_corruption_with_repaired_crc_is_not_accepted(wire_path):
    wire = wire_path.read_bytes()
    payload = bytearray(wire[32:-12]);payload[-1] ^= 1
    wire_path.write_bytes(encode(1280, 720, 41, payload))
    with pytest.raises(ValueError, match="pixels differ"):
        sim.audit_wire(wire_path)


def test_truncation_cannot_be_complete_frame(wire_path):
    wire_path.write_bytes(wire_path.read_bytes()[:-1])
    with pytest.raises(ValueError, match="wire length"):
        sim.audit_wire(wire_path)


def test_vga_frame_cannot_be_relabelled720(wire_path):
    wire_path.write_bytes(encode(640, 480, 41, bytes(614400)))
    with pytest.raises(ValueError, match="wire length"):
        sim.audit_wire(wire_path)
