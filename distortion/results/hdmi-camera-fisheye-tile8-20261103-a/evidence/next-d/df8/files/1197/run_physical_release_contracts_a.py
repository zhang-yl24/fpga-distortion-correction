"""Rerun source-bound CPU contracts in a fresh tagged output; never EDA/hardware."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[1]
TOOLS = ROOT / 'tools'
PEER_WORK = WORK.with_name('hdmi-camera-fisheye-tile8df9-20261103-a')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    if not re.fullmatch('[a-z][a-z0-9-]{0,30}', args.tag):
        raise ValueError('simple fresh source-contract tag required')
    xml_path = WORK / 'physical-release-tests-a' / ('results-' + args.tag + '.xml')
    receipt = WORK / ('physical-release-contract-run-' + args.tag + '.json')
    claim = WORK / ('physical-release-contract-run-' + args.tag + '.claim.json')
    if any(path.exists() for path in (xml_path, receipt, claim)):
        raise ValueError('contract output tag already used')
    physical_files = sorted((WORK / 'physical-release-tests-a').glob('*.py'))
    peer_files = sorted((WORK / 'directfill-peer-tests-a').glob('test_*.py'))
    directfill_files = [ROOT / 'tests/test_hdmi_camera_fisheye_directfill_contract.py', *peer_files]
    warning_files = [ROOT / 'tests/test_tile8df8_actual_warning_draft_b.py']
    files = [*physical_files, *directfill_files, *warning_files]
    watched = [*files, *TOOLS.glob('hdmi_camera_fisheye_tile8df8v2_*.py')]
    watched += [TOOLS / ('hdmi_camera_fisheye_tile8df8_' + name + '.py') for name in (
        'macro_we_aliases', 'startup_timing', 'vendor_startup_bounded_b', 'build',
        'native', 'scoped_native', 'audit', 'protocol', 'startup', 'warnings')]
    watched += [WORK / name for name in (
        'run_physical_v2_a.py', 'run_release_v2_a.py', 'prewarm_release_v2_a.py',
        'compress_completed_physical_v2_evidence_a.py', 'run_physical_release_contracts_a.py')]
    watched += [ROOT / 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v',
                ROOT / 'rtl/experimental/hdmi_camera_fisheye_engine_tile8df8.v',
                PEER_WORK / 'cache-unit-a/simulation.json']
    peer_review_path = PEER_WORK / 'directfill-independent-peer-review-a.json'
    peer_review = json.loads(peer_review_path.read_text(encoding='utf-8'))
    if peer_review.get('Passed') is not True or peer_review.get('InputDrift') != []:
        raise ValueError('actual saved independent direct-fill peer review required')
    for name, digest in peer_review['InputSHA256'].items():
        if sha(Path(name)) != digest:
            raise ValueError('saved independent peer evidence drift: ' + name)
        watched.append(Path(name))
    watched += [peer_review_path, WORK / 'review_physical_release_group_a.py',
                WORK / 'freeze_complete_physical_release_a.py', WORK / 'bind_selected_four_roles_a.py',
                WORK / 'prepare_df8_physical_release_sources_a.py',
                WORK / 'prepare_source_warning_inventory_b.py', WORK / 'review_source_warning_inventory_draft_b.py']
    before = {str(path): sha(path) for path in watched}
    started = datetime.now(timezone.utc).isoformat()
    with claim.open('x', encoding='utf-8') as stream:
        json.dump({'Schema': 'tile8df8-physical-release-contract-run-claim-v1',
                   'StartedUTC': started, 'InputSHA256': before,
                   'EDAExecuted': False, 'HardwareAccessed': False}, stream, indent=2)
    sys.path[:0] = [str(ROOT.parent / '.venv/Lib/site-packages')]
    import pytest
    code = pytest.main(['-q', '-p', 'no:cacheprovider', *map(str, files), '--junitxml=' + str(xml_path)])
    after = {str(path): sha(path) for path in watched}
    drift = [path for path in before if before[path] != after[path]]
    root = ET.parse(xml_path).getroot()
    suites = [root] if root.tag == 'testsuite' else root.findall('testsuite')
    counts = {key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
              for key in ('tests', 'errors', 'failures', 'skipped')}
    passed = code == 0 and not drift and counts['tests'] >= 695 and all(
        counts[key] == 0 for key in ('errors', 'failures', 'skipped'))
    value = {'Schema': 'tile8df8-physical-release-contract-run-v1', 'Passed': passed,
             'StartedUTC': started, 'EndedUTC': datetime.now(timezone.utc).isoformat(),
             'PytestExitCode': code, 'InputSHA256': before, 'InputDrift': drift,
             'JUnit': {'Path': str(xml_path), 'SHA256': sha(xml_path)}, 'Counts': counts,
             'PhysicalContractFiles': list(map(str, physical_files)),
             'DirectFillContractAndPeerFiles': list(map(str, directfill_files)),
             'WarningInventoryContractFiles': list(map(str, warning_files)),
             'HardwareAccessed': False, 'EDAExecuted': False, 'PDriveAccessed': False}
    with receipt.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'Passed': passed, **counts, 'Receipt': str(receipt)}))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
