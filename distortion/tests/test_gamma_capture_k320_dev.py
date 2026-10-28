"""Focused source/semantic boundaries; no temporary directory or hardware."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"tools"))
import prepare_gamma_capture_k320_dev as candidate
from frame_protocol import encode
import read_gamma_capture_k320_dev as replay


def test_isolated_real_development_binding_and_guard():
    info = candidate.verify()
    binding = info["ProfileBinding"]
    assert binding["DevelopmentOnly"] is True
    assert binding["CalibrationAccepted"] is False
    assert binding["HardwareReleaseAllowed"] is False
    assert binding["RadiusGuardQ22"] == 6530716
    assert binding["IntegerConfig"][:2] == [81792, 61312]
    assert binding["GroupSeed"] == int(binding["ProfileSHA256"][:7],16) == candidate.GROUP_SEED
    assert binding["Identity"]["camera_id"] == "replacement-20261026-cam2"
    assert len(info["Pins"]) == 128 and info["Pins"]["cam_data[5]"] == "AA23"
    assert "board/calibration-trial.vh" not in info["SourceSHA256"]
    assert "board/rotation-domain.vh" not in info["SourceSHA256"]


def test_stage_refuses_existing_candidate():
    with pytest.raises(ValueError, match="overwrite"):
        candidate.stage()


@pytest.mark.parametrize("size", [0, 3*replay.PACKET_BYTES-1, 3*replay.PACKET_BYTES+1])
def test_incomplete_or_extra_wire_rejected(size):
    with pytest.raises(ValueError, match="complete"):
        replay.check_wire(bytes(size))


def test_crc_failure_cannot_become_triplet():
    payload = bytes(640*480*2)
    wire = bytearray(b"".join(encode(640,480,i,payload) for i in (16,17,18)))
    wire[40] ^= 1
    with pytest.raises(ValueError, match="malformed"):
        replay.check_wire(bytes(wire))


def test_crc_valid_wrong_bypass_fails_numeric_check():
    zero, white = bytes(640*480*2), b"\xff\xff"*(640*480)
    base = candidate.GROUP_SEED << 4
    wire = encode(640,480,base,zero)+encode(640,480,base|1,white)+encode(640,480,base|2,white)
    record, _, _ = replay.check_wire(wire)
    assert record["passed"] is False
    assert record["bypass_mismatched_pixels"] == 307200
    assert record["HardwareAccessed"] is False


def test_old_group_one_is_rejected_even_with_valid_packet_crcs():
    payload = bytes(640*480*2)
    wire = b"".join(encode(640,480,i,payload) for i in (16,17,18))
    with pytest.raises(ValueError, match="group seed"):
        replay.check_wire(wire)
