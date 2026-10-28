"""Read-only regressions against optional sealed local campaign evidence.

The counterexamples substitute only in-memory metadata/ZIP views. They never
rewrite a receipt, archive or hardware interface. Missing local artifacts skip.
"""
from pathlib import Path
from datetime import datetime
import copy
import json
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import catalog_guarded_campaign as catalog


def _require_local_run(run):
    required = [run/name for name in ('result.json','plan.json','received-wire.bin',
                'tx-commands.jsonl','status-events.jsonl','implementation-snapshot.json',
                'implementation-snapshot.zip')]
    if not all(path.is_file() for path in required):
        pytest.skip('optional sealed local run evidence is incomplete: '+run.name)
    result = catalog.load(run/'result.json')
    for receipt in (result['guarded_program'], result['idle_program']):
        files = [Path(path) for path in receipt['logs']]
        files.append(Path(receipt['workdir'])/'receipt.json')
        if not all(path.is_file() for path in files):
            pytest.skip('optional local programming receipt/logs are unavailable: '+run.name)


@pytest.fixture
def campaign():
    path = ROOT/'output/project/guarded-campaign-20261025-v1.json'
    if not path.is_file():
        pytest.skip('optional sealed local campaign catalog is unavailable')
    value = catalog.load(path)
    for row in value['runs'][:2]:
        _require_local_run(Path(row['run']))
    return value


def test_existing_eight_runs_keep_failures_and_historical_helper_versions(campaign):
    refreshed = []
    old_plan_count = 0
    stable_keys = ('target','scenario','scenario_passed','failure','source_kind','status_packets','raw_frames',
                   'result_sha256','plan_sha256','wire_sha256','original_source_files',
                   'original_helper_sha256','bitstream_sha256','snapshot','last_confirmed_sram_event')
    for expected in campaign['runs']:
        run = Path(expected['run'])
        _require_local_run(run)
        actual = catalog.catalog_run(run)
        for key in stable_keys:
            assert actual[key] == expected[key]
        for name,digest in expected['analysis_sha256'].items():
            assert actual['analysis_sha256'][name] == digest
        assert actual['evidence_integrity_passed'] is True
        assert actual['optical_acceptance_inferred'] is False
        old_plan_count += 'target' not in catalog.load(run/'plan.json')
        refreshed.append(actual)
    assert len(refreshed) == 8 and old_plan_count == 6
    assert sum(row['scenario_passed'] for row in refreshed) == 7
    failed = [row for row in refreshed if not row['scenario_passed']]
    assert len(failed) == 1 and failed[0]['target'] == 'raw_camera_capture_cam1_guarded'
    bars = next(row for row in refreshed if row['target'].endswith('_bars'))
    assert bars['scenario_passed'] is True  # Transport scenario, not level acceptance.
    for name in ('digital-colorbar-audit.json','digital-colorbar-audit-v2.json'):
        assert catalog.load(Path(bars['run'])/name)['digital_pattern_checks_passed'] is False
    latest = max((row['last_confirmed_sram_event'] for row in refreshed),
                 key=lambda event: datetime.fromisoformat(event['receipt_checked_at_utc']))
    assert latest == campaign['last_confirmed_sram_event']
    assert latest['receipt_checked_at_utc'] == '2026-10-25T11:33:01.266486+00:00'
    assert campaign['all_selected_scenarios_passed'] is False


def test_neighboring_same_source_run_snapshot_cannot_be_reused(campaign, monkeypatch):
    first, second = [Path(row['run']) for row in campaign['runs'][:2]]
    original_load = catalog.load
    other_snapshot = original_load(second/'implementation-snapshot.json')
    def substituted(path):
        if Path(path).resolve() == (first/'implementation-snapshot.json').resolve():
            return copy.deepcopy(other_snapshot)
        return original_load(path)
    monkeypatch.setattr(catalog, 'load', substituted)
    with pytest.raises(ValueError):
        catalog.catalog_run(first)


def _archive_view(monkeypatch, run, *, omit=None, duplicate=False):
    """Model a self-consistent inventory omission without modifying disk bytes."""
    original_zip = catalog.zipfile.ZipFile
    original_load = catalog.load
    snapshot = original_load(run/'implementation-snapshot.json')
    with original_zip(snapshot['archive_path']) as archive:
        manifest = json.loads(archive.read('SNAPSHOT-MANIFEST.json'))
        members = archive.namelist()
    if omit is not None:
        assert omit in members
        manifest['files'] = [row for row in manifest['files'] if row['archive_path'] != omit]
        members = [name for name in members if name != omit]
        snapshot = dict(snapshot, verified_files=snapshot['verified_files']-1)
    if duplicate:
        members.append(members[0])
    class ArchiveView:
        def __init__(self, *args, **kwargs):
            self.original = original_zip(*args, **kwargs)
        def __enter__(self): return self
        def __exit__(self, *args): self.original.close()
        def namelist(self): return list(members)
        def read(self, name, *args, **kwargs):
            if name == 'SNAPSHOT-MANIFEST.json':
                return json.dumps(manifest).encode()
            if name == omit:
                raise KeyError(name)
            return self.original.read(name, *args, **kwargs)
        def __getattr__(self, name): return getattr(self.original, name)
    def substituted(path):
        if Path(path).resolve() == (run/'implementation-snapshot.json').resolve():
            return copy.deepcopy(snapshot)
        return original_load(path)
    monkeypatch.setattr(catalog.zipfile, 'ZipFile', ArchiveView)
    monkeypatch.setattr(catalog, 'load', substituted)


def test_duplicate_zip_member_is_rejected(campaign, monkeypatch):
    run = Path(campaign['runs'][0]['run'])
    _archive_view(monkeypatch, run, duplicate=True)
    with pytest.raises(ValueError):
        catalog.catalog_run(run)


@pytest.mark.parametrize('missing', ['result','program_receipt','idle_receipt'])
def test_missing_required_run_evidence_is_rejected(campaign, monkeypatch, missing):
    run = Path(campaign['runs'][0]['run'])
    result = catalog.load(run/'result.json')
    path = (run/'result.json' if missing == 'result' else
            Path(result['guarded_program' if missing == 'program_receipt' else 'idle_program']['workdir'])/'receipt.json')
    _archive_view(monkeypatch, run, omit=path.relative_to(ROOT).as_posix())
    with pytest.raises(ValueError):
        catalog.catalog_run(run)
