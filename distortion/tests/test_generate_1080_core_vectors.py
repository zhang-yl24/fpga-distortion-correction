"""Small independent integer/sampling/format checks; no full-frame RTL/CAD/device run."""
from pathlib import Path
import json
import re
import sys
import zlib

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"tools"))
import generate_1080_core_vectors as vectors


def test_exact_native_model_and_nonzero_tangential_scalar_agreement():
    c = vectors.parameters()
    assert c == [245632, 138112, 245632, 138112, 245760, 248832,
                 1118481, 1104673, 335544, -62915, 8389, 4194, -2936]
    oracle = vectors.scalar_oracle()
    rng = np.random.default_rng(0x10802027)
    u = np.r_[np.array([-256, 0, 959*256+128, 1919*256, (1 << 23)-1]),
              rng.integers(-2000*256, 4000*256, 151)].astype(np.int64)
    v = rng.integers(-1500*256, 2800*256, len(u), dtype=np.int64)
    sx, sy, bad, _ = vectors.project_integer(u, v, c)
    for i in range(len(u)):
        assert (int(sx[i]), int(sy[i]), int(bad[i])) == oracle.project(int(u[i]), int(v[i]), c)


def test_sampler_rounds_once_and_partial_footprint_is_not_geometry_mask():
    # Half-way between pure red, green, blue and white: RGB888 mean=128,
    # then quantize to RGB565, not interpolate the packed uint16 words.
    source = np.array([[0xF800, 0x07E0], [0x001F, 0xFFFF]], dtype=np.uint16)
    rgb = vectors.expand565(source)
    sampled = vectors.remap_fixed(rgb, np.array([[.5, -.5]]), np.array([[.5, 0.]]))
    assert vectors.pack565(sampled).tolist() == [[0x8410, 0x8000]]
    result = vectors.tone(np.array([[0, 0xFFFF]], dtype=np.uint16), np.array([[False, True]]))
    assert result.tolist() == [[0, 0]]  # Pixel value alone cannot distinguish mask.


def test_gamma_formula_matches_all_committed_curve_entries_without_using_rtl_output():
    text = (ROOT/"rtl/experimental/gamma_curves.vh").read_text()
    for bits, width in ((5, 7), (6, 8)):
        rows = {int(index): int(value) for index, value in
                re.findall(rf"{width}'d(\d+):gamma{bits}={bits}'d(\d+);", text)}
        assert len(rows) == 3*(1 << bits)
        for mode in range(3):
            assert vectors.gamma_table(bits, mode).tolist() == [rows[mode*(1 << bits)+i] for i in range(1 << bits)]


def test_two_small_texture_banks_change_pixels_but_keep_exact_model_mask():
    a, ea, ma, sa = vectors.render_frame(96, 54, 0, chunk_rows=13)
    b, eb, mb, sb = vectors.render_frame(96, 54, 1, chunk_rows=17)
    assert np.unique(a).size > 500 and np.unique(a, axis=0).shape[0] == 54
    assert not np.array_equal(a, b) and not np.array_equal(ea, eb)
    np.testing.assert_array_equal(ma, mb)
    assert 0 < sa["MaskedPixels"] < a.size and sa["PartialBorderPixels"] > 0
    assert sa["MaskedPixels"] + sa["UnmaskedPixels"] == a.size
    assert sa["ArithmeticInvalidPixels"] == sb["ArithmeticInvalidPixels"] == 0
    # Chunking changes no arithmetic or pixels.
    _, again, mask_again, _ = vectors.render_frame(96, 54, 0, chunk_rows=7)
    np.testing.assert_array_equal(ea, again); np.testing.assert_array_equal(ma, mask_again)


def test_small_generated_mem_crc_scope_and_no_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(vectors, "APPROVED", tmp_path)
    work = tmp_path/"vectors"; work.mkdir()
    report = vectors.generate_vectors(work, variant=1, _test_size=(48, 28))
    loaded = json.loads((work/"vectors.json").read_text())
    assert loaded == report and report["PixelCount"] == 48*28
    words = [int(v, 16) for v in (work/"expected.mem").read_text().splitlines()]
    payload = b"".join(w.to_bytes(2, "little") for w in words)
    assert report["ExpectedPixelCRC32"] == f"{zlib.crc32(payload):08X}"
    assert len(words) == 48*28 and len((work/"masks.mem").read_text().splitlines()) == len(words)
    assert report["SyntheticInput"] and report["DevelopmentOnly"] and not report["CalibrationAccepted"]
    assert not report["HardwareReleaseAllowed"] and not report["RTLResultUsedForGolden"]
    assert report["Gamma"]["ExpectedMode"] == 0
    assert all(vectors.sha(work/n) == item["SHA256"] for n, item in report["Files"].items())
    assert report["ReferenceSHA256"] == report["ReferenceSHA256After"]
    before = vectors.sha(work/"vectors.json")
    with pytest.raises(ValueError, match="overwrite"):
        vectors.generate_vectors(work, variant=0, _test_size=(48, 28))
    assert vectors.sha(work/"vectors.json") == before
    with pytest.raises(ValueError, match="existing"):
        vectors.generate_vectors(tmp_path/"missing")
    with pytest.raises(ValueError, match="existing"):
        vectors.generate_vectors(tmp_path)


@pytest.mark.parametrize("value", [True, -1, 2, "0"])
def test_unknown_texture_variant_rejected(value):
    with pytest.raises(ValueError, match="variant"):
        vectors.texture(8, 8, value)
