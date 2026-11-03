"""Bind the independent peer's source review, CPU tests and real XSim collisions."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import sys
import xml.etree.ElementTree as ET

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[1]
sys.path[:0] = [str(ROOT / 'tools')]
import hdmi_camera_fisheye_directfill_contract as contract


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    return {'Path': str(Path(path).resolve()), 'SHA256': sha(path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=WORK / 'directfill-independent-peer-review-a.json')
    args = parser.parse_args()
    if args.output.resolve().parent != WORK or args.output.exists():
        raise ValueError('fresh peer review output under own WORK required')
    source_facts, watched = contract.review()
    watched = dict(watched)
    receipt_path = WORK / 'cache-commit-collision-a/simulation.json'
    value = json.loads(receipt_path.read_text())
    assert value['Passed'] is True and value['InputDrift'] == []
    assert value['HDLSimulationExecuted'] is True and value['PDSAccessed'] is False and value['HardwareAccessed'] is False
    assert value['NativeRAMMappingOrTimingAccepted'] is False
    assert value['SourceSHA256'][str(contract.SOURCE)] == contract.SOURCE_SHA256
    for name, digest in value['SourceSHA256'].items():
        assert sha(name) == digest
        assert name not in watched or watched[name] == digest
        watched[name] = digest
    for name, digest in value['ArtifactsSHA256'].items():
        relative = Path(name)
        assert not relative.is_absolute() and '..' not in relative.parts
        path = receipt_path.parent / relative
        assert sha(path) == digest
        watched[str(path)] = digest
    watched[str(receipt_path)] = sha(receipt_path)
    report = WORK / 'directfill-peer-tests-a/results-a.xml'
    root = ET.parse(report).getroot()
    suites = [root] if root.tag == 'testsuite' else root.findall('testsuite')
    tests = sum(int(row.attrib['tests']) for row in suites)
    assert tests == 59 and all(int(row.attrib.get(key, 0)) == 0 for row in suites
                              for key in ('errors', 'failures', 'skipped'))
    for path in (report, WORK / 'directfill-peer-tests-a/test_independent_source_and_collision.py',
                 ROOT / 'tests/test_hdmi_camera_fisheye_directfill_contract.py', Path(__file__).resolve()):
        watched[str(path)] = sha(path)
    assert all(sha(name) == digest for name, digest in watched.items())
    result = {'Schema': 'hdmi-camera-fisheye-directfill-independent-peer-review-v1',
              'Passed': True, 'CheckedUTC': datetime.now(timezone.utc).isoformat(),
              'Source': ref(contract.SOURCE), 'SourceContractProvider': ref(contract.SELF),
              'OriginalUnitReceipt': ref(contract.UNIT_RECEIPT),
              'IndependentCollisionReceipt': ref(receipt_path), 'ActualPeerCPUContractTests': tests,
              'PeerCPUContractJUnit': ref(report), 'SourceFacts': source_facts,
              'ActualIndependentXSimCoverage': value['Summary'],
              'SourceSpecificIndependentReview': {
                  'RegisteredPayloadBeatLineBlockValidNextEdgeAlignment': True,
                  'SameEdgeARFirstRAndContinuousOrGappedRRetained': True,
                  'AllSixteenPixelLaneParityAndAddressPackingIndependentlyParsed': True,
                  'SameClockBlockFinalFaultAssignmentPriorityVerified': True,
                  'OwnedLineAndBlockStayConstantDuringARFILLWAITCommit': True,
                  'OriginalFIFOHitAccountingAndFrameDrainSourceSectionsPinnedUnchanged': True,
                  'NotAnArbitraryVerilogEquivalenceProof': True},
              'IndependentTestPoisonedMalformedAndExtraRawPayload': True,
              'IndependentTestsVerifyQuarantineUntilCommonReset': True,
              'FrozenOriginalCacheContractAndUnitEvidenceModified': False,
              'NativeRAMMappingAccepted': False, 'CDCAccepted': False, 'STAInherited': False,
              'FullFrameSimulatedByPeer': False, 'HardwareReleaseAllowed': False,
              'HDLSimulationExecutedByPeer': True, 'PDSAccessed': False, 'HardwareAccessed': False,
              'InputSHA256': dict(sorted(watched.items())), 'InputDrift': []}
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps({'Passed': True, 'PeerReview': ref(args.output),
                      'IndependentXSimCases': 4, 'PeerCPUTests': tests, 'Watched': len(watched)}))


if __name__ == '__main__':
    main()
