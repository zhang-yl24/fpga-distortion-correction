"""Reject incomplete 720p output evidence and independently corrupted scans."""
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import run_camera720_output_sim as output


def summary():
    return dict(passed=True, frames_processed=3, frames_unique_scanned=3,
        coordinates_compared=2764800, result_beats=172800, underflows=0,
        crc_mismatches=0, final_drain=True, source_bank_reuses=1, result_bank_reuses=1,
        scan_frames=3, pixels_compared=2764800, display_read_beats=172800,
        bank_releases=3, aw_stall_cycles=11, w_stall_cycles=13, ar_stall_cycles=17,
        fifo_peak=512, concurrent_process_display_cycles=29, read_contention_cycles=31,
        complete_hdmi_rasters=3, border_pixels_checked=3456000)


def test_full_720p_summary():
    output.validate_summary(summary())


@pytest.mark.parametrize("key,value", [
    ("frames_processed", True), ("coordinates_compared", 921600),
    ("source_bank_reuses", 0), ("result_bank_reuses", 0),
    ("read_contention_cycles", 0), ("concurrent_process_display_cycles", 0),
    ("final_drain", False), ("underflows", 1), ("fifo_peak", 513),
    ("scan_frames", 4), ("complete_hdmi_rasters", 2),
])
def test_incomplete_or_faulted_summary_rejected(key, value):
    record = summary()
    record[key] = value
    with pytest.raises(ValueError):
        output.validate_summary(record)


def test_all_neighbours_legal_but_mapping_is_nonlinear():
    config, guard, sx, sy, invalid, stats = output.geometry()
    assert config[8] and config[9] and config[10] and config[11] and config[12]
    assert stats["ScalarCoordinateCrosschecks"] == 221
    assert not invalid.any() and stats["MaximumRadiusSquaredQ22"] < guard
    assert np.max(np.abs(np.diff(sx[360], n=2))) > 0
    assert np.max(np.abs(np.diff(sy[:, 640], n=2))) > 0


@pytest.mark.parametrize("corruption", [None, "pixel", "epoch", "truncated", "extra"])
def test_actual_pixel_dump_is_independently_checked(tmp_path, monkeypatch, corruption):
    # Small fixtures exercise the post-run evidence reader, not the RTL.
    monkeypatch.setattr(output, "WIDTH", 4)
    monkeypatch.setattr(output, "HEIGHT", 4)
    monkeypatch.setattr(output, "PIXELS", 16)
    monkeypatch.setattr(output, "FRAME_COUNT", 1)
    golden = np.arange(16, dtype=np.uint16).reshape(4, 4)
    crc = output.crc(golden)
    records = [{"FrameID": 1, "SourceCRC32": "12345678", "ExpectedCRC32": crc}]
    rows = [dict(frame_id="1", pixels="16", result_beats="1", result_bank="0",
                 source_crc32="12345678", result_crc32=crc, reader_crc32=crc, scan_crc32=crc,
                 start_cycle="2", process_done_cycle="4", release_cycle="6")]
    lines = [f"1 {v:04x}\n" for v in golden.ravel()]
    if corruption == "pixel":
        lines[5] = "1 ffff\n"
    elif corruption == "epoch":
        lines[5] = "2 0005\n"
    elif corruption == "truncated":
        lines.pop()
    elif corruption == "extra":
        lines.append("1 1234\n")
    (tmp_path / "scan-pixels.mem").write_text("".join(lines), encoding="ascii", newline="\n")
    if corruption is None:
        output.validate_pixels(tmp_path, records, [golden], rows, {"scan_frames": 1})
    else:
        with pytest.raises(ValueError):
            output.validate_pixels(tmp_path, records, [golden], rows, {"scan_frames": 1})
