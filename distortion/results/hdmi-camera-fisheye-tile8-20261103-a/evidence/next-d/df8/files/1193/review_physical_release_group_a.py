"""Owner source/contract review of the unfrozen df8 group; no native execution."""
from pathlib import Path
import argparse
import ast
import hashlib
import importlib
import json
import sys
import xml.etree.ElementTree as ET

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[1]
TOOLS = ROOT / 'tools'
PEER_WORK = WORK.with_name('hdmi-camera-fisheye-tile8df9-20261103-a')
sys.path[:0] = [str(TOOLS), str(ROOT.parent / '.venv/Lib/site-packages')]
OLD_WORK = ROOT / 'work/hdmi-camera-fisheye-tile8-20261103-a'
ROLES = ('physical', 'scoped_native', 'target_query', 'physical_checks', 'final', 'bitstream', 'program')
SUPPLEMENTS = ('macro_we_aliases', 'startup_timing', 'vendor_startup_bounded_b')


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    return {'Path': str(Path(path).resolve()), 'SHA256': sha(path)}


def renamed(text):
    return (text.replace('hdmi_camera_fisheye_tile8v2_', 'hdmi_camera_fisheye_tile8df8v2_')
            .replace('hdmi_camera_fisheye_tile8_', 'hdmi_camera_fisheye_tile8df8_')
            .replace('hdmi-camera-fisheye-tile8v2-', 'hdmi-camera-fisheye-tile8df8v2-')
            .replace('hdmi-camera-fisheye-tile8-', 'hdmi-camera-fisheye-tile8df8-')
            .replace('HDMI_CAMERA_FISHEYE_TILE8V2_', 'HDMI_CAMERA_FISHEYE_TILE8DF8V2_')
            .replace('tile8v2-bounded-b', 'tile8df8v2-bounded-b'))


def dump(tree):
    return ast.dump(tree, include_attributes=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contracts', type=Path, required=True)
    parser.add_argument('--contract-run', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=WORK / 'physical-release-group-owner-review-a.json')
    args = parser.parse_args()
    require(args.output.resolve().parent == WORK and not args.output.exists(), 'fresh review path in own WORK required')
    original_manifests = [OLD_WORK / 'physical-release-provider-source-manifest-a.json',
                          OLD_WORK / 'release-prewarm-wrapper-source-manifest-a.json']
    baseline = {}
    watched = {}
    for path in original_manifests:
        value = read(path)
        for name, digest in value['InputSHA256'].items():
            require(name not in baseline or baseline[name] == digest, 'conflicting original frozen provenance')
            baseline[name] = digest
        watched[str(path)] = sha(path)
    rows = []
    for old_name, new_name in [
        *((f'hdmi_camera_fisheye_tile8v2_{role}.py', f'hdmi_camera_fisheye_tile8df8v2_{role}.py') for role in ROLES),
        *((f'hdmi_camera_fisheye_tile8_{role}.py', f'hdmi_camera_fisheye_tile8df8_{role}.py') for role in SUPPLEMENTS),
    ]:
        original, new = TOOLS / old_name, TOOLS / new_name
        require(baseline.get(str(original)) == sha(original), 'original frozen provider drift: ' + old_name)
        before = ast.parse(renamed(original.read_text(encoding='utf-8-sig')))
        new_source = new.read_text(encoding='utf-8-sig')
        after = ast.parse(new_source)
        bit = new_name.endswith('_bitstream.py')
        if bit:
            old_functions = {node.name for node in before.body if isinstance(node, ast.FunctionDef)}
            new_functions = {node.name for node in after.body if isinstance(node, ast.FunctionDef)}
            require(new_functions == old_functions | {'directfill_frame_counts', 'bind_sustained'},
                    'unexpected bit provider function change')
            call = '    sustained=bind_sustained(plan,watched)\n'
            result = ",'SustainedSimulation':sustained"
            require(new_source.count(call) == new_source.count(result) == 1,
                    'exact mandatory sustained gate call and context binding required')
            after = ast.parse(new_source.replace(call, '', 1).replace(result, '', 1))
            before.body = [node for node in before.body if not isinstance(node, ast.FunctionDef) or node.name != 'bind_simulation']
            after.body = [node for node in after.body if not isinstance(node, ast.FunctionDef)
                          or node.name not in ('bind_simulation', 'directfill_frame_counts', 'bind_sustained')]
        require(dump(before) == dump(after), 'non-authorized AST change: ' + new_name)
        rows.append({'Original': ref(original), 'New': ref(new),
                     'CompleteASTEqualAfterExactNamespaceMapping': not bit,
                     'ChangedFunctions': ['bind_simulation', 'directfill_frame_counts', 'bind_sustained',
                                          'audit_request:exact-sustained-call-and-context-only'] if bit else []})
        watched[str(original)] = sha(original)
        watched[str(new)] = sha(new)

    modules = {role: importlib.import_module('hdmi_camera_fisheye_tile8df8v2_' + role) for role in ROLES}
    build = importlib.import_module('hdmi_camera_fisheye_tile8df8_build')
    raw = importlib.import_module('hdmi_camera_fisheye_tile8df8_native')
    audit = importlib.import_module('hdmi_camera_fisheye_tile8df8_audit')
    physical, scoped, target, checks, final, bit, program = [modules[role] for role in ROLES]
    require(all(module.build is build for module in (physical, scoped, target, checks, final, bit)), 'new build module edge differs')
    require(scoped.raw_native is raw and physical.native is checks.native is checks.baseline is final.native
            is final.baseline is bit.native is scoped, 'new scoped/raw module closure differs')
    require(checks.physical is final.application is physical and checks.audit is audit and program.bit is bit,
            'new physical/audit/program module closure differs')
    require(build.WORK == WORK and bit.PROOF_SCHEMA == final.SCHEMA and
            physical.AUDIT_SCHEMA == 'hdmi-camera-fisheye-tile8df8-native-audit-v1' and
            bit.SIMULATIONS['SystemSimulation'] == 'run_hdmi_camera_fisheye_tile8df8_system_sim',
            'candidate namespace/work/schema identity differs')
    require(build.REQUIRED_MODULES['ddr_neighbour_cache_scatter16_rowpipe'] ==
            'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v' and
            build.REQUIRED_MODULES['hdmi_camera_fisheye_engine_tile8'] ==
            'rtl/experimental/hdmi_camera_fisheye_engine_tile8df8.v', 'candidate source paths differ')

    driver_rows = []
    for name in ('run_physical_v2_a.py', 'run_release_v2_a.py', 'prewarm_release_v2_a.py',
                 'compress_completed_physical_v2_evidence_a.py'):
        original, new = OLD_WORK / name, WORK / name
        require(baseline.get(str(original)) == sha(original), 'original frozen driver drift: ' + name)
        require(dump(ast.parse(renamed(original.read_text(encoding='utf-8-sig')))) ==
                dump(ast.parse(new.read_text(encoding='utf-8-sig'))), 'unexpected driver AST change: ' + name)
        driver_rows.append({'Original': ref(original), 'New': ref(new), 'NormalizedASTIdentical': True})
        watched[str(original)] = sha(original)
        watched[str(new)] = sha(new)
    root = ET.parse(args.contracts).getroot()
    suites = [root] if root.tag == 'testsuite' else root.findall('testsuite')
    count = sum(int(s.attrib['tests']) for s in suites)
    require(count >= 413 and all(int(s.attrib.get(key, 0)) == 0 for s in suites
                                for key in ('failures', 'errors', 'skipped')), 'all actual owner contracts must pass')
    contract_run_path = args.contract_run.resolve()
    contract_run = read(contract_run_path)
    require(contract_run.get('Passed') is True and contract_run.get('PytestExitCode') == 0 and
            contract_run.get('InputDrift') == [] and contract_run.get('JUnit') == ref(args.contracts),
            'actual input-bound contract runner receipt required')
    require(all(sha(path) == digest for path, digest in contract_run['InputSHA256'].items()),
            'contract runner source changed after the actual test run')
    watched[str(contract_run_path)] = sha(contract_run_path)
    watched.update(contract_run['InputSHA256'])
    for path in (WORK / 'physical-release-tests-a').glob('*.py'):
        watched[str(path)] = sha(path)
    watched[str(args.contracts.resolve())] = sha(args.contracts)
    watched[str(Path(__file__).resolve())] = sha(__file__)
    watched[str(PEER_WORK / 'cache-unit-a/simulation.json')] = sha(PEER_WORK / 'cache-unit-a/simulation.json')
    for name in ('build', 'native', 'scoped_native', 'audit', 'protocol', 'startup', 'warnings'):
        path = TOOLS / ('hdmi_camera_fisheye_tile8df8_' + name + '.py')
        watched[str(path)] = sha(path)
    require(all(sha(path) == digest for path, digest in watched.items()), 'owner source review input drift')
    value = {'Schema': 'hdmi-camera-fisheye-tile8df8v2-physical-release-owner-review-v1',
             'Passed': True, 'SourceContractReviewOnly': True, 'IndependentPeerReviewPerformed': False,
             'Adapters': rows, 'Drivers': driver_rows, 'ActualOwnerContracts': count,
             'ExactTenClosedModuleEdgesChecked': True, 'NewSourcePathsAndSimulationProviderBound': True,
             'DirectFillSimulationRequirements': {'CacheIndexBits': 8, 'ScatterCyclesPerFill': 0,
                                                  'CacheRAMWriteCyclesPerFill': 8,
                                                  'OneFinalValidCommitPerFill': True},
             'SameCacheSourceEvidenceWork': str(PEER_WORK), 'IndependentCollisionExecutedIndexBits': 9,
             'OwnINDEX8SystemAndSustainedEvidenceStillRequired': True,
             'OriginalFrozenTile8ProvidersAndDriversUnchanged': True,
             'ActualNativeMacroTopologyAndStartupProofStillRequired': True,
             'ActualTenSTAAndFinalPhysicalProofStillRequired': True,
             'IndependentPeerReviewBeforeFreezeStillRequired': True,
             'ProviderManifestFrozen': False, 'OldPhysicalOrHardwareAcceptanceInherited': False,
             'EDAExecuted': False, 'PDriveAccessed': False, 'HardwareAccessed': False,
             'InputSHA256': dict(sorted(watched.items()))}
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(value, output, indent=2)
        output.write('\n')
    print(json.dumps({'Passed': True, 'Adapters': len(rows), 'Contracts': count,
                      'OwnerReview': ref(args.output), 'ProviderManifestFrozen': False}))


if __name__ == '__main__':
    main()
