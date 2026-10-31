"""CPU-only seed, fresh-stage gate, and artifact drift regression checks."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import camera_vga_upright_fast_bitstream as fast

SEED = fast.prep.WORK/'authority-seed-20261031-a.json'
SEED_SHA = 'c77c1014ae4d586e575bc6576109d08cf8e2681ad1e5e228e9234f98bba6d973'


def forbid_authority(*args, **kwargs):
    raise AssertionError('full authority must not be reentered')


def test_real_completed_seed_binds_without_authority(monkeypatch):
    monkeypatch.setattr(fast.bit, 'authority', forbid_authority)
    context, plan = fast.bind_seed(SEED, SEED_SHA)
    assert len(context['AuthorityInputSHA256']) == 479
    assert context['CandidateSHA256'] == plan['CandidateADFSHA256']
    work = fast.prep.WORK/'bit-fast-test-never-executed'
    new = fast.render(context, work)
    old = fast.bit.render(context, work)
    assert new.replace(fast.SELF.as_posix(), fast.bit.SELF.as_posix()) == old
    assert new.count('report_timing -force_to_run') == 1
    assert new.count('gen_bit_stream -force_to_run') == 1
    assert new.index('report_timing -force_to_run') < new.index('--gate') < new.index('gen_bit_stream -force_to_run')


@pytest.mark.parametrize('field,value', [('ExitCode', 1), ('Prepared', False),
    ('FullPrepareCompleted', False), ('OwnedExecSession', None), ('EDAExecuted', True)])
def test_seed_rejects_incomplete_original_prepare(monkeypatch, field, value):
    original_read = fast.bit.read
    def changed(path):
        result = original_read(path)
        if result.get('Schema') == fast.COMPLETION_SCHEMA:
            result[field] = value
        return result
    monkeypatch.setattr(fast.bit, 'read', changed)
    with pytest.raises(ValueError, match='completion'):
        fast.bind_seed(SEED, SEED_SHA)


@pytest.mark.parametrize('key', ['InputSHA256', 'ToolSHA256'])
def test_seed_rejects_dropped_authority_input_or_helper(monkeypatch, key):
    original_read = fast.bit.read
    def changed(path):
        result = original_read(path)
        if result.get('Schema') == fast.SEED_SCHEMA:
            result[key].pop(next(iter(result[key])))
        return result
    monkeypatch.setattr(fast.bit, 'read', changed)
    with pytest.raises(ValueError, match='closure'):
        fast.bind_seed(SEED, SEED_SHA)


def test_seed_rejects_changed_entry_hash():
    with pytest.raises(ValueError, match='hash mismatch'):
        fast.bind_seed(SEED, '0'*64)


def test_gate_rejects_failing_fresh_sta_before_writing(tmp_path, monkeypatch):
    monkeypatch.setattr(fast, 'validate', lambda w: ({'AuthoritySeed': {}}, {}))
    monkeypatch.setattr(fast, 'gate_evidence', lambda w: {'report': 'a'})
    def fail(*args):
        raise ValueError('fresh timing summary/clock identities differ')
    monkeypatch.setattr(fast.bit, 'compare_native', fail)
    with pytest.raises(ValueError, match='fresh timing'):
        fast.gate(tmp_path)
    assert not (tmp_path/'pre-bit-audit.json').exists()


def test_gate_rejects_report_drift_during_comparison(tmp_path, monkeypatch):
    monkeypatch.setattr(fast, 'validate', lambda w: ({'AuthoritySeed': {}}, {}))
    values = iter([{'report': 'a'}, {'report': 'b'}])
    monkeypatch.setattr(fast, 'gate_evidence', lambda w: next(values))
    monkeypatch.setattr(fast.bit, 'compare_native', lambda *args: {})
    with pytest.raises(ValueError, match='changed during'):
        fast.gate(tmp_path)


def test_diagnostic_regex_matches_indented_native_errors():
    import ast
    import re
    tree = ast.parse(fast.SELF.read_text())
    patterns = [v.value for v in ast.walk(tree) if isinstance(v, ast.Constant)
                and isinstance(v.value, str) and '(?:E:|F:|ERROR:|FATAL:|Traceback)' in v.value]
    assert len(patterns) == 1
    assert re.findall(patterns[0], '   ERROR: failed\n\tF: fatal\n') == ['   ERROR: failed', '\tF: fatal']
