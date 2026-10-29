"""Source selection contracts only; no simulated or synthetic PDS success."""
from pathlib import Path
import copy
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import board1080_checked_profile as tool


def test_expected_selection_replaces_only_four_of_109_sources():
    actual = tool.expected_manifest()
    base = json.loads((tool.PROJECT / tool.BASE).read_text())
    assert len(actual['source_files']) == len(set(actual['source_files'])) == 109
    assert set(base['source_files']) - set(actual['source_files']) == set(tool.REPLACEMENTS)
    assert set(actual['source_files']) - set(base['source_files']) == set(tool.REPLACEMENTS.values())
    for name in set(base['source_files']) - set(tool.REPLACEMENTS):
        assert actual['SourceSHA256'][name] == base['SourceSHA256'][name]
    assert actual['Constraint'] == base['Constraint']
    assert actual['RouteConstraint'] == base['RouteConstraint']
    assert actual['BaseManifest']['SHA256'] == tool.sha(tool.PROJECT / tool.BASE)
    assert actual['ElectricalConstraintStatus'] == 'UnverifiedForSCLInout'
    for flag in ('CompiledIntegrationVerified', 'PDSExecuted', 'EligibleForPDSOrHardware',
                 'HardwareAccessed', 'TimingAccepted', 'HardwareReleaseAllowed',
                 'PreviousCandidateTimingReusable', 'PreviousCandidateBitstreamReusable'):
        assert actual[flag] is False


@pytest.mark.parametrize('mutation', ('old_driver', 'both_wrappers', 'wrong_hash', 'other_source',
                                    'constraint', 'base_hash', 'claim_timing', 'missing_audit'))
def test_changed_manifest_rejected(tmp_path, monkeypatch, mutation):
    expected = tool.expected_manifest()
    actual = copy.deepcopy(expected)
    if mutation == 'old_driver':
        actual['source_files'] = [next(iter(tool.REPLACEMENTS)) if n == next(iter(tool.REPLACEMENTS.values())) else n
                                  for n in actual['source_files']]
    elif mutation == 'both_wrappers': actual['source_files'].append('platform/video_base/source/hdmi/ms72xx_ctl.v')
    elif mutation == 'wrong_hash': actual['SourceSHA256']['board/board1080_checked_top.v'] = '0' * 64
    elif mutation == 'other_source': actual['source_files'][0] = 'rtl/unrelated.v'
    elif mutation == 'constraint': actual['Constraint'] = 'board/other.fdc'
    elif mutation == 'base_hash': actual['BaseManifest']['SHA256'] = '0' * 64
    elif mutation == 'claim_timing': actual['TimingAccepted'] = True
    else: actual.pop('CheckedTopSourceAudit')
    path = tmp_path / tool.MANIFEST
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(actual))
    monkeypatch.setattr(tool, 'expected_manifest', lambda _: expected)
    with pytest.raises(ValueError, match='four-source'):
        tool.validate_profile(tmp_path)


@pytest.mark.parametrize('auditor', ('top', 'tx'))
def test_unvalidated_controller_cannot_create_manifest(tmp_path, monkeypatch, auditor):
    base = tool.PROJECT / tool.BASE
    path = tmp_path / tool.BASE
    path.parent.mkdir(parents=True)
    path.write_bytes(base.read_bytes())
    monkeypatch.setattr(tool.hdmi30, 'validate_profile', lambda _: {})
    def reject(*_): raise ValueError('unvalidated ' + auditor)
    if auditor == 'top': monkeypatch.setattr(tool.top, 'audit', reject)
    else:
        monkeypatch.setattr(tool.top, 'audit', lambda _: dict(Baseline=tool.top.BASELINE, Candidate=tool.top.CANDIDATE))
        monkeypatch.setattr(tool.controller, 'audit_tx_copy', reject)
    with pytest.raises(ValueError, match='unvalidated'):
        tool.write_manifest(tmp_path)
    assert not (tmp_path / tool.MANIFEST).exists()


def test_manifest_writer_is_exclusive(tmp_path):
    path = tmp_path / tool.MANIFEST
    path.parent.mkdir(parents=True)
    path.write_text('existing selection')
    with pytest.raises(ValueError, match='exists'): tool.write_manifest(tmp_path)
    assert path.read_text() == 'existing selection'


def test_existing_pds_preparer_rejects_checked_top(tmp_path, monkeypatch):
    manifest = tool.expected_manifest()
    original = tool.hdmi30.timing.inside
    path = tmp_path / 'checked-selection.json'
    path.write_text(json.dumps(manifest))
    def inputs(project, name):
        return path if name == 'checked-selection.json' else original(project, name)
    monkeypatch.setattr(tool.hdmi30.timing, 'inside', inputs)
    with pytest.raises(ValueError):
        tool.hdmi30.timing.validate_manifest(tool.PROJECT, 'checked-selection.json')
