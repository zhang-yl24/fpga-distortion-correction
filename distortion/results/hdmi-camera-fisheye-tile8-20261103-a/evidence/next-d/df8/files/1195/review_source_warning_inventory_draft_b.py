"""Read-only integrity review of an UNSIGNED actual df8 warning draft.

Success means only that a draft matches recomputed completed-build evidence.
It never accepts a warning or creates the final warning inventory.
"""
from pathlib import Path
import argparse
import importlib.util
import json

WORK = Path(__file__).resolve().parent
PREPARE = WORK / 'prepare_source_warning_inventory_b.py'


def load_prepare():
    spec = importlib.util.spec_from_file_location('current_df8_actual_warning_draft_prepare_b', PREPARE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inspect_unsigned_draft(value, prepare=None):
    p = prepare or load_prepare()
    p.require(value.get('Schema') == p.DRAFT_SCHEMA and value.get('DraftComplete') is True,
              'complete current unsigned df8 warning draft required')
    p.require(value.get('RootReviewRequired') is True and value.get('NewBodiesRequireExplicitRootReview') is True,
              'explicit root review must remain required')
    for key in ('Passed', 'FinalInventoryWritten', 'PriorCompilerOrTimingAcceptanceInherited',
                'SourceDiagnosticReviewPassed', 'UnknownWarningsAccepted', 'TimingAccepted',
                'NativeEquivalent', 'CDCAccepted', 'HardwareReleaseAllowed', 'HardwareAccessed', 'EDAExecuted'):
        p.require(value.get(key) is False, 'unsigned warning draft overclaims: ' + key)
    inventory = value['ProposedInventory']
    p.require(inventory['Schema'] == 'hdmi-camera-fisheye-tile8df8-warning-inventory-v1' and
              inventory['Target'] == value['Target'] == 'hdmi_camera_fisheye_top' and
              inventory['BuildPlan'] == value['BuildPlan'] and
              inventory['SourceBuildReceipt'] == value['SourceBuildReceipt'],
              'proposed inventory/current actual build identity differs')
    p.validate_warning_map(inventory['WarningBodiesByLog'])
    bodies = {body for rows in inventory['WarningBodiesByLog'].values() for body in rows}
    difference = value['DifferenceFrom15FPSTile8']
    proposals = difference['BodyClassProposals']
    p.require(len(proposals) == len(bodies) and {row['Body'] for row in proposals} == bodies and
              all(row.get('RootReviewRequired') is True and row.get('AcceptedByThisTool') is False for row in proposals),
              'each actual warning requires an unaccepted root review proposal')
    unknown = sorted(row['Body'] for row in proposals if row['ProposedClass'] is None)
    classes = {row['Body']: row['ProposedClass'] for row in proposals if row['ProposedClass'] is not None}
    p.require(unknown == value['UnknownWarningBodies'] == difference['UnknownWarningBodies'] and
              classes == inventory['BodyClasses'] == difference['ProposedBodyClasses'],
              'unknown W bodies must remain visible and unaccepted')
    p.require(difference['RootReviewRequired'] is True and difference['AnyWarningAcceptedByThisTool'] is False,
              'difference proposal conferred acceptance')
    counts = p.Counter()
    for rows in inventory['WarningBodiesByLog'].values():
        for body, count in rows.items():
            counts[p.warning_code(body)] += count
    p.require(dict(counts) == inventory['Counts'] == difference['ActualCountsByCode'] and
              len(bodies) == inventory['UniqueBodies'] == difference['ActualUniqueBodies'],
              'actual warning multiplicity/unique inventory differs')
    p.require(value['SharePinSourceComparison']['SourceBytesEqual'] is True and
              value['SharePinSourceComparison']['BodiesDifferOnlyByEqualByteFilename'] is True and
              value['SharePinSourceComparison']['NativeElectricalAcceptanceConferred'] is False,
              'share-pin source comparison overclaims or differs')
    cache = value['UnchangedCacheSourceEvidence']
    p.require(cache['SourceSHA256'] == p.CACHE_SOURCE_SHA256 and
              cache['UnitReceipt'] == {'Path': str(p.UNIT_RECEIPT.resolve()), 'SHA256': p.UNIT_RECEIPT_SHA256} and
              cache['CollisionReceipt'] == {'Path': str(p.COLLISION_RECEIPT.resolve()), 'SHA256': p.COLLISION_RECEIPT_SHA256} and
              cache['ActualEvidenceWork'] == str(p.CACHE_EVIDENCE_WORK.resolve()) and
              cache['INDEX9NativeMappingOrTimingInherited'] is False and
              cache['INDEX8NativeTimingAccepted'] is False and cache['HardwareReleaseAllowed'] is False,
              'same-source cache evidence must keep its actual INDEX9 paths without native acceptance')
    return {'Schema': 'hdmi-camera-fisheye-tile8df8-unsigned-warning-draft-integrity-v1',
            'DraftIntegrityVerified': True, 'RootReviewRequired': True,
            'WarningDispositionAccepted': False, 'FinalInventoryWritten': False,
            'ActualUniqueBodies': len(bodies), 'UnknownWarningBodies': unknown,
            'ReadyForRootDispositionReview': not unknown,
            'TimingAccepted': False, 'HardwareReleaseAllowed': False,
            'HardwareAccessed': False, 'EDAExecuted': False}


def review(path, provider=None):
    p = load_prepare()
    path = Path(path).resolve()
    p.require(path.parent == WORK and path.name.startswith('source-warning-inventory-draft-') and path.is_file(),
              'existing current df8 warning draft required')
    saved_sha = p.sha(path)
    saved = json.loads(path.read_text(encoding='utf-8'))
    facts = inspect_unsigned_draft(saved, p)
    current, watched = p.derive_draft(provider)
    p.require(current == saved and p.sha(path) == saved_sha,
              'warning draft differs from actual fresh read-only recomputation')
    watched[str(path)] = saved_sha
    facts['ActualCompletedBuildRecomputed'] = True
    facts['Draft'] = {'Path': str(path), 'SHA256': saved_sha}
    return facts, watched


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--draft', type=Path, required=True)
    args = parser.parse_args(argv)
    facts, watched = review(args.draft)
    print(json.dumps({**facts, 'Watched': len(watched)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
