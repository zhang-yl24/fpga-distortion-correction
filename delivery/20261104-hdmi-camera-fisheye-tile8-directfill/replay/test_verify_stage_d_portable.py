"""Finite delivery entry negative cases; no candidate archive is assembled."""
from pathlib import Path
import pytest
import verify_stage_d_portable as v


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'C:/drive', 'a\\alias', 'a//alias', './alias'])
def test_delivery_paths_are_canonical_and_stay_in_package(tmp_path, name):
    with pytest.raises(ValueError):
        v.inside(tmp_path, name)


def test_missing_stage_d_result_cannot_be_presented_as_delivery(tmp_path):
    with pytest.raises(FileNotFoundError):
        v.verify(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_published_C_alone_is_not_a_completed_D():
    repo = Path(__file__).resolve().parents[3]
    old = repo / 'distortion/work/tile8-publish-20261103/distortion/results/hdmi-camera-fisheye-tile8-20261103-a'
    with pytest.raises(FileNotFoundError):
        v.verify(old)


def test_duplicate_json_members_are_rejected(tmp_path):
    source = tmp_path / 'duplicate.json'
    source.write_text('{"Schema":"one","Schema":"two"}')
    with pytest.raises(ValueError, match='duplicate'):
        v.read(source)


def test_bundle_path_resolves_actual_saved_file(tmp_path):
    folder = tmp_path/'evidence';folder.mkdir();source=folder/'saved';source.write_bytes(b'local fixture')
    assert v.inside(tmp_path, 'evidence/saved') == source
