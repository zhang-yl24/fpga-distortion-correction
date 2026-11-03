"""Owner review of isolated v3 sources and an actual source-bound CPU run."""
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
sys.path[:0] = [str(TOOLS), str(ROOT.parent / '.venv/Lib/site-packages')]
ROLES = ('physical', 'scoped_native', 'target_query', 'physical_checks', 'final', 'bitstream', 'program')
DRIVERS = ('run_physical', 'run_release', 'prewarm_release', 'compress_completed_physical')
ORIGINAL = WORK / 'physical-release-provider-source-manifest-a.json'
ORIGINAL_SHA = '8914c4c46ab950866747400cf1d668f3436720e562f10d76870c4440019fb50d'
OLD_REVIEW = WORK / 'root-independent-complete-source-review-a.json'
OLD_REVIEW_SHA = '27e614d3e584d1a8a278254b12fba992462a19a76bda445d54528a70012a9374'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    import os
    path = Path(path).absolute()
    source = Path('\\\\?\\' + str(path)) if os.name == 'nt' else path
    return hashlib.sha256(source.read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def ref(path):
    path = Path(path).resolve()
    return {'Path': str(path), 'SHA256': sha(path)}


def normalized(text):
    return text.replace('tile8df8v2', 'tile8df8v3').replace('TILE8DF8V2', 'TILE8DF8V3')


def dump(node):
    return ast.dump(node, include_attributes=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contracts', type=Path, required=True)
    parser.add_argument('--contract-run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(args.output.resolve().parent == WORK and not args.output.exists(), 'fresh owner review required')
    require(sha(ORIGINAL) == ORIGINAL_SHA and sha(OLD_REVIEW) == OLD_REVIEW_SHA, 'original v2 provenance differs')
    original = read(ORIGINAL)
    watched = {str(ORIGINAL): ORIGINAL_SHA, str(OLD_REVIEW): OLD_REVIEW_SHA}
    watched.update(original['InputSHA256'])
    for name, digest in read(OLD_REVIEW)['InputSHA256'].items():
        require(name not in watched or watched[name] == digest, 'conflicting original provenance SHA')
        watched[name] = digest
    rows = []
    changed = {'application_recipe', 'render_application', 'application_evidence', 'execute_application'}
    for role in ROLES:
        old = TOOLS / ('hdmi_camera_fisheye_tile8df8v2_' + role + '.py')
        new = TOOLS / ('hdmi_camera_fisheye_tile8df8v3_' + role + '.py')
        require(original['InputSHA256'].get(str(old)) == sha(old), 'original provider drift')
        before = ast.parse(normalized(old.read_text(encoding='utf-8-sig')))
        after = ast.parse(new.read_text(encoding='utf-8-sig'))
        if role == 'physical':
            before_functions = {n.name: n for n in before.body if isinstance(n, ast.FunctionDef)}
            after_functions = {n.name: n for n in after.body if isinstance(n, ast.FunctionDef)}
            require(set(before_functions) == set(after_functions), 'unexpected physical function changes')
            require(all(dump(before_functions[n]) == dump(after_functions[n]) for n in before_functions if n not in changed),
                    'non-authorized physical proof/binder/selector change')
            expected_recipe = normalized(old.read_text(encoding='utf-8-sig')).replace('60<=maximum<=600', '60<=maximum<=1800').replace('bounded60..600s', 'bounded60..1800s')
            recipe = next(n for n in ast.parse(expected_recipe).body if isinstance(n, ast.FunctionDef) and n.name == 'application_recipe')
            require(dump(after_functions['application_recipe']) == dump(recipe), 'budget change exceeds exact600 to1800')
            before.body = [n for n in before.body if not isinstance(n, ast.FunctionDef) or n.name not in changed]
            after.body = [n for n in after.body if (not isinstance(n, ast.FunctionDef) or n.name not in changed)
                          and not (isinstance(n, ast.Import) and any(a.name == 'hdmi_camera_fisheye_tile8df8v3_application_observer' for a in n.names))]
        require(dump(before) == dump(after), 'non-authorized module AST change: ' + role)
        watched[str(new)] = sha(new)
        rows.append({'Original': ref(old), 'New': ref(new), 'NamespaceASTEqualOutsideDeclaredChanges': True,
                     'ChangedFunctions': sorted(changed) if role == 'physical' else []})
    modules = {r: importlib.import_module('hdmi_camera_fisheye_tile8df8v3_' + r) for r in ROLES}
    physical, scoped, target, checks, final, bit, program = [modules[r] for r in ROLES]
    require(scoped.raw_native is importlib.import_module('hdmi_camera_fisheye_tile8df8_native') and
            physical.native is checks.native is checks.baseline is final.native is final.baseline is bit.native is scoped and
            checks.physical is final.application is physical and program.bit is bit,
            'seven new public module edges must close through v3 only')
    require(all(m.build is physical.build for m in (scoped, target, checks, final, bit)) and physical.build.WORK == WORK,
            'unchanged original INDEX8 build role required')
    prior_plan = read(WORK / 'physical-v2-a/stage-plan.json')
    old_physical = importlib.import_module('hdmi_camera_fisheye_tile8df8v2_physical')
    observer = importlib.import_module('hdmi_camera_fisheye_tile8df8v3_application_observer')
    stripped = observer.strip_markers(physical.render_application(prior_plan))
    require(stripped == normalized(old_physical.render_application(prior_plan)), 'actual complete v2 Tcl changed after strict marker removal')
    watched[str(Path(observer.__file__))] = sha(observer.__file__)
    watched[str(WORK / 'physical-v2-a/stage-plan.json')] = sha(WORK / 'physical-v2-a/stage-plan.json')
    root = ET.parse(args.contracts).getroot()
    suites = [root] if root.tag == 'testsuite' else root.findall('testsuite')
    count = sum(int(s.attrib['tests']) for s in suites)
    require(count >= 695 and all(int(s.attrib.get(k, 0)) == 0 for s in suites for k in ('failures', 'errors', 'skipped')),
            'every actual v3 CPU contract must pass without skip')
    run = read(args.contract_run)
    require(run.get('Schema') == 'tile8df8v3-physical-release-contract-run-v1' and run.get('Passed') is True and
            run.get('PytestExitCode') == 0 and run.get('InputDrift') == [] and run['JUnit'] == ref(args.contracts),
            'fresh completed source-bound v3 CPU run required')
    for name, digest in run['InputSHA256'].items():
        require(name not in watched or watched[name] == digest, 'CPU input cannot replace original provenance SHA')
        watched[name] = digest
    for path in (args.contracts.resolve(), args.contract_run.resolve(), Path(__file__).resolve(),
                 WORK / 'physical-compression-helper-source-manifest-v3.json'):
        watched[str(path)] = sha(path)
    require(all(sha(path) == digest for path, digest in watched.items()), 'owner review input drift')
    value = {'Schema': 'hdmi-camera-fisheye-tile8df8v3-physical-release-owner-review-v1', 'Passed': True,
             'SourceContractReviewOnly': True, 'IndependentPeerReviewPerformed': False,
             'OriginalProviderManifest': ref(ORIGINAL), 'OriginalRootReview': ref(OLD_REVIEW), 'Adapters': rows,
             'ActualOwnerContracts': count, 'ExactSevenClosedModuleEdgesChecked': True,
             'ActualFullApplicationTclEqualAfterStrictMarkerRemoval': True, 'ApplicationMaximumSeconds': 1800,
             'OriginalFrozenTile8ProvidersAndDriversUnchanged': True, 'OldPhysicalOrHardwareAcceptanceInherited': False,
             'ProviderManifestFrozen': False, 'IndependentCompleteSourceReviewStillRequired': True,
             'FreshApplicationAndAllDownstreamNativeProofRequired': True, 'EDAExecuted': False,
             'PDriveAccessed': False, 'HardwareAccessed': False, 'InputDrift': [], 'InputSHA256': dict(sorted(watched.items()))}
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')
    print(json.dumps({'Passed': True, 'OwnerReview': ref(args.output), 'ActualOwnerContracts': count,
                      'ProviderManifestFrozen': False, 'EDAExecuted': False}))


if __name__ == '__main__':
    main()
