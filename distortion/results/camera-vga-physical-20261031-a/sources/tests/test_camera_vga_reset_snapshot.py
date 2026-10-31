from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import run_camera_vga_reset_snapshot as snapshot


RESET = 'set_false_path -from [get_pins -hierarchical -regexp {^(reset/CLK)$}] -to [get_pins -hierarchical -regexp {^(native/RS)$}]'


def test_snapshot_initializes_before_reset_and_never_runs_second_sta():
    text = snapshot.render(['show -design_net {_N188}', RESET], snapshot.repair.core.ROOT / 'snapshot-cpu-test')
    assert text.count('mpnr_report_timing ') == 1
    assert '-max_path 20 -nworst 4 -report_exception TRUE' in text
    assert '-max_path 1000' not in text
    assert text.index('mpnr -input ') < text.index('mpnr_report_timing ') < text.index(RESET)
    assert text.index(RESET) < text.index('save_adif') < text.index('file copy ') < text.index('.switch_db ')
    assert 'CAMERA_APPLY_SAVE_ONLY_NO_FINAL_STA' in text and snapshot.repair.MARKER in text


def test_snapshot_rejects_request_without_reset_scope():
    with pytest.raises(ValueError, match='requires exact reset scope'):
        snapshot.render(['show -design_net {_N188}'], snapshot.repair.core.ROOT / 'snapshot-cpu-test')


def test_snapshot_binds_own_bytes(monkeypatch):
    monkeypatch.setattr(snapshot.chain, 'prepare_request', lambda _: ({'ResetScope': {}}, None, {}, [RESET]))
    _, _, watched, _ = snapshot.prepare_request('unused')
    assert watched[snapshot.SELF] == snapshot.repair.core.sha(snapshot.SELF)


def test_snapshot_runtime_changes_are_restored():
    before = snapshot.repair.PINS, snapshot.repair.prepare_request, snapshot.repair.render
    with snapshot.snapshot_mode():
        assert snapshot.repair.render is snapshot.render
    assert before == (snapshot.repair.PINS, snapshot.repair.prepare_request, snapshot.repair.render)
