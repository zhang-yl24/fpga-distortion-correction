"""CPU-only local fixtures and malicious portable-map/trace regressions."""
from copy import deepcopy
from pathlib import Path
import json
import shutil

import pytest

import make_test_fixture as fixtures
import portable_source_contract as p

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(scope='session')
def saved_bundles(tmp_path_factory):
    root = tmp_path_factory.mktemp('tile8-portable-fixtures')
    result = {}
    for candidate in ('df9tp', 'df8'):
        folder = root / candidate
        path = fixtures.prepare(REPO, folder, candidate)
        result[candidate] = (folder, path)
    return result


@pytest.fixture
def bundle(tmp_path, saved_bundles):
    original, _ = saved_bundles['df9tp']
    folder = tmp_path / 'relocated bundle 中文'
    shutil.copytree(original, folder)
    return folder, folder / 'source-contract-map.json'


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def find_row(mapping, ending):
    return next(row for row in mapping['Files'] if row['OriginalPath'].replace('\\', '/').endswith(ending))


@pytest.mark.parametrize('candidate', ['df9tp', 'df8'])
def test_real_saved_source_and_110_input_closure_replays_without_original_work_review(saved_bundles, candidate):
    folder, path = saved_bundles[candidate]
    before = {str(file): p.sha(file) for file in folder.rglob('*') if file.is_file()}
    facts, watched = p.review(folder, path)
    assert facts['PortableSourceContractVerified'] and facts['ProductionSourcesVerified'] == 110
    assert facts['TagReadPipeline'] == (candidate == 'df9tp')
    assert len(facts['UnitCasesReparsed']) == 4
    assert facts['CollisionCasesVerified']['Cases'] == 4
    for key in ('HelperFullWORKReviewCalled', 'FrozenReceiptsRewritten', 'RTLReexecuted',
        'FullSystemRTLVerifiedHere', 'NativePhysicalAcceptanceRecomputed', 'BitstreamVerifiedHere',
        'BoardFPSVerifiedHere', 'PublicationComplete', 'EDAExecuted', 'HardwareAccessed', 'HardwareReleaseAllowed'):
        assert facts[key] is False
    assert before == {str(file): p.sha(file) for file in folder.rglob('*') if file.is_file()}
    assert len(watched) == facts['MappedFilesVerified'] + 1


def test_helper_snapshot_can_move_without_patching_its_frozen_bytes_or_baseline(bundle):
    folder, path = bundle; mapping = p.load_json(path)
    row = find_row(mapping, 'tools/hdmi_camera_fisheye_directfill_tagpipe_contract.py')
    old = folder / row['BundlePath']; new = folder / 'atoms/source/frozen_helper.py'
    new.parent.mkdir(parents=True); shutil.copyfile(old, new); old.unlink()
    row['BundlePath'] = new.relative_to(folder).as_posix(); save(path, mapping)
    facts, _ = p.review(folder, path)
    assert facts['PortableSourceContractVerified'] and p.sha(new) == p.CANDIDATES['df9tp']['HelperSHA256']


@pytest.mark.parametrize('bad', ['../outside', '/outside', 'C:/outside', 'payload\\bad',
    'payload/../bad', '', '.', 'payload//alias'])
def test_bundle_paths_cannot_escape_or_alias_original(bundle, bad):
    folder, path = bundle; value = p.load_json(path); value['Files'][0]['BundlePath'] = bad; save(path, value)
    with pytest.raises(ValueError): p.review(folder, path)


@pytest.mark.parametrize('bad', ['relative/file', 'D:relative', '\\\\host\\share\\file',
    'D:/safe/../outside', 'D:/safe/file:stream', 'D:/safe/line\nfile'])
def test_original_windows_identity_cannot_use_ambiguous_or_escaping_path(bundle, bad):
    folder, path = bundle; value = p.load_json(path); value['Files'][0]['OriginalPath'] = bad; save(path, value)
    with pytest.raises(ValueError): p.review(folder, path)


@pytest.mark.parametrize('change', ['windows_case', 'target_case', 'old_cache', 'wrong_candidate',
    'missing_role', 'extra_role', 'claims_release', 'size_bool', 'negative_size', 'bad_sha'])
def test_map_rejects_duplicate_identities_rebound_sources_and_release_claims(bundle, change):
    folder, path = bundle; value = p.load_json(path)
    if change == 'windows_case':
        row = deepcopy(value['Files'][0]); row['OriginalPath'] = row['OriginalPath'].upper()
        row['BundlePath'] = 'different-target'; value['Files'].append(row)
    elif change == 'target_case': value['Files'][1]['BundlePath'] = value['Files'][0]['BundlePath'].upper()
    elif change == 'old_cache': value['Roles']['Source'] = value['Roles']['Baseline']
    elif change == 'wrong_candidate': value['Candidate'] = 'df8'
    elif change == 'missing_role': del value['Roles']['Baseline']
    elif change == 'extra_role': value['Roles']['AcceptedPhysicalProof'] = value['Roles']['Source']
    elif change == 'claims_release': value['HardwareReleaseAllowed'] = True
    elif change == 'size_bool': value['Files'][0]['Bytes'] = True
    elif change == 'negative_size': value['Files'][0]['Bytes'] = -1
    else: value['Files'][0]['SHA256'] = 'CallerSaysSafe'
    save(path, value)
    with pytest.raises(ValueError): p.review(folder, path)


@pytest.mark.parametrize('update_map', [False, True])
def test_changed_trace_cannot_pass_by_refreshing_only_transport_hash(bundle, update_map):
    folder, path = bundle; value = p.load_json(path)
    row = find_row(value, 'cache-unit-a/trace-1920-i9.txt'); target = folder / row['BundlePath']
    text = target.read_text(); first = next(line for line in text.splitlines() if line.startswith('O '))
    words = first.split(); words[1] = '000000'; target.write_text(text.replace(first, ' '.join(words), 1))
    if update_map: row['SHA256'], row['Bytes'] = p.sha(target), target.stat().st_size
    save(path, value)
    with pytest.raises(ValueError): p.review(folder, path)


def test_unit_receipt_cannot_be_forged_after_rehashing_transport(bundle):
    folder, path = bundle; value = p.load_json(path)
    row = find_row(value, 'cache-unit-a/simulation.json'); target = folder / row['BundlePath']
    receipt = p.load_json(target); receipt['Cases']['1920-i9']['stale_valid_refreshes'] = 0; save(target, receipt)
    row['SHA256'], row['Bytes'] = p.sha(target), target.stat().st_size; save(path, value)
    with pytest.raises(ValueError, match='wrong SHA'): p.review(folder, path)


def test_missing_actual_trace_mapping_is_rejected_without_filename_fallback(bundle):
    folder, path = bundle; value = p.load_json(path)
    row = find_row(value, 'cache-unit-a/trace-1920-i9.txt'); value['Files'].remove(row); save(path, value)
    with pytest.raises(ValueError, match='missing explicit'): p.review(folder, path)


def test_unreferenced_mapped_file_is_rejected(bundle):
    folder, path = bundle; value = p.load_json(path)
    target = folder / 'unrelated.txt'; target.write_text('unrelated history')
    value['Files'].append({'OriginalPath': 'D:/unrelated/history.txt', 'BundlePath': 'unrelated.txt',
                          'SHA256': p.sha(target), 'Bytes': target.stat().st_size}); save(path, value)
    with pytest.raises(ValueError, match='unreferenced'): p.review(folder, path)


def test_duplicate_json_keys_are_rejected_before_helper_load(bundle):
    folder, path = bundle; text = path.read_text(); text = text.replace('"Candidate": "df9tp"', '"Candidate": "df9tp", "Candidate": "df8"')
    path.write_text(text)
    with pytest.raises(ValueError, match='duplicate JSON'): p.review(folder, path)


def test_all_mapped_files_are_verified_before_loading_any_helper(bundle, monkeypatch):
    folder, path = bundle; mapping = p.load_json(path); row = mapping['Files'][-1]
    target = folder / row['BundlePath']; target.write_bytes(target.read_bytes() + b'changed')
    calls = []; original = p.ModuleType
    def observed(name):
        calls.append(name)
        return original(name)
    monkeypatch.setattr(p, 'ModuleType', observed)
    with pytest.raises(ValueError, match='byte size/SHA drift'): p.review(folder, path)
    assert calls == []


def test_rehashed_untrusted_helper_is_never_executed(bundle):
    folder, path = bundle; mapping = p.load_json(path)
    row = find_row(mapping, 'tools/hdmi_camera_fisheye_directfill_tagpipe_contract.py')
    target = folder / row['BundlePath']; marker = folder / 'untrusted-code-was-executed'
    target.write_bytes(target.read_bytes() + ('\nopen(' + repr(str(marker)) + ', "w").write("bad")\n').encode())
    row['SHA256'], row['Bytes'] = p.sha(target), target.stat().st_size; save(path, mapping)
    with pytest.raises(ValueError, match='wrong SHA'): p.review(folder, path)
    assert not marker.exists()


@pytest.mark.parametrize('field', ['lookup_miss_overlap', 'query_refreshes', 'stale_valid_refreshes',
    'result_stall_metadata_cycles', 'slow_lookup_cycles'])
def test_semantic_tagpipe_coverage_check_rejects_vacuity_even_when_summary_agrees(saved_bundles, field):
    folder, path = saved_bundles['df9tp']; mapping = p.load_json(path)
    row = find_row(mapping, 'cache-unit-a/simulation.json')
    case = deepcopy(p.load_json(folder / row['BundlePath'])['Cases']['1920-i9'])
    case[field] = 0; summary = {k: v for k, v in case.items() if k != 'IndependentTrace'}
    with pytest.raises(ValueError, match='stale/held'): p.validate_case(case, summary, p.CANDIDATES['df9tp'])


@pytest.mark.parametrize('change', ['pixel', 'fraction', 'wrong_epoch', 'duplicate_query', 'missing_output', 'out_of_order', 'unknown_record'])
def test_independent_oracle_rejects_pixel_metadata_and_stream_faults(saved_bundles, change):
    folder, path = saved_bundles['df9tp']; row = find_row(p.load_json(path), 'cache-unit-a/trace-1920-i9.txt')
    lines = (folder / row['BundlePath']).read_text().splitlines()
    if change in ('pixel', 'fraction'):
        index = next(i for i, line in enumerate(lines) if line.startswith('O ')); fields = lines[index].split()
        position = 1 if change == 'pixel' else 5; fields[position] = f'{int(fields[position],16)^1:x}'; lines[index] = ' '.join(fields)
    elif change == 'wrong_epoch':
        fields = lines[0].split(); fields[-1] = '7'; lines[0] = ' '.join(fields)
    elif change == 'duplicate_query': lines.insert(1, lines[0])
    elif change == 'missing_output': lines.pop(next(i for i, line in enumerate(lines) if line.startswith('O ')))
    elif change == 'out_of_order':
        positions = [i for i, line in enumerate(lines) if line.startswith('O ')][:2]
        lines[positions[0]], lines[positions[1]] = lines[positions[1]], lines[positions[0]]
    else: lines.append('CALLER_ASSERTS_PASSED')
    with pytest.raises(ValueError): p.validate_trace('\n'.join(lines), 1920, 1080)


def test_fixture_map_is_only_input_data_and_no_publication_receipt(saved_bundles):
    folder, path = saved_bundles['df9tp']; value = p.load_json(path)
    assert set(value) == {'Schema', 'Candidate', 'Roles', 'Files'}
    assert not list(folder.glob('*receipt*.json'))
    assert not list(folder.glob('portable-evidence-manifest-*.json'))
