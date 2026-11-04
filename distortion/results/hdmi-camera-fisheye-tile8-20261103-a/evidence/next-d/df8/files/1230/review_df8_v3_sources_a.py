"""Independent source review of the isolated v3 budget/observation recovery.

This CPU-only review does not execute a native stage or grant physical acceptance.
The actual CPU run and two independent peer reviews must already exist.
"""
import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import sys

SELF = Path(__file__).resolve()
REPO = SELF.parents[2]
ROOT = REPO / 'distortion'
WORK = ROOT / 'work/hdmi-camera-fisheye-tile8df8-20261103-a'
TOOLS = ROOT / 'tools'
sys.path[:0] = [str(TOOLS), str(REPO / '.venv/Lib/site-packages')]
import hdmi_camera_fisheye_tile8df8_build as build
import hdmi_camera_fisheye_tile8df8v2_physical as old
import hdmi_camera_fisheye_tile8df8v3_physical as new
import hdmi_camera_fisheye_tile8df8v3_application_observer as observation

ORIGINAL = {
    WORK / 'physical-release-provider-source-manifest-a.json': '8914c4c46ab950866747400cf1d668f3436720e562f10d76870c4440019fb50d',
    WORK / 'root-independent-complete-source-review-a.json': '27e614d3e584d1a8a278254b12fba992462a19a76bda445d54528a70012a9374',
}
ROLES = ('physical', 'scoped_native', 'target_query', 'physical_checks', 'final', 'bitstream', 'program')
require = build.require


def normalized(text):
    return text.replace('tile8df8v3', 'tile8df8v2').replace('TILE8DF8V3', 'TILE8DF8V2')


def tree(text):
    return ast.dump(ast.parse(text), include_attributes=False)


def source_review():
    facts = []
    for role in ROLES:
        before = (TOOLS / ('hdmi_camera_fisheye_tile8df8v2_' + role + '.py')).read_text(encoding='utf-8')
        after = normalized((TOOLS / ('hdmi_camera_fisheye_tile8df8v3_' + role + '.py')).read_text(encoding='utf-8'))
        if role != 'physical':
            require(tree(before) == tree(after), 'unexpected non-namespace public provider change: ' + role)
            facts.append({'Role': role, 'OnlyNamespaceASTAdaptation': True})
            continue
        left, right = ast.parse(before), ast.parse(after)
        lf = {n.name: n for n in left.body if isinstance(n, ast.FunctionDef)}
        rf = {n.name: n for n in right.body if isinstance(n, ast.FunctionDef)}
        require(set(lf) == set(rf), 'physical public function set changed')
        changed = {'application_recipe', 'render_application', 'application_evidence', 'execute_application'}
        for name in set(lf) - changed:
            require(ast.dump(lf[name]) == ast.dump(rf[name]), 'physical acceptance logic changed: ' + name)
        expected = ast.get_source_segment(before, lf['application_recipe'])
        expected = expected.replace('maximum<=600', 'maximum<=1800').replace('bounded60..600s', 'bounded60..1800s')
        require(tree(expected) == ast.dump(ast.Module(body=[rf['application_recipe']], type_ignores=[])),
                'application recipe must differ only by truthful bounded budget')
        def outside(nodes):
            return [n for n in nodes if not (isinstance(n, ast.FunctionDef) and n.name in changed)
                    and not (isinstance(n, ast.Import) and any(a.name.endswith('_application_observer') for a in n.names))]
        require(ast.dump(ast.Module(body=outside(left.body), type_ignores=[])) ==
                ast.dump(ast.Module(body=outside(right.body), type_ignores=[])), 'unexpected physical module declaration change')
        facts.append({'Role': role, 'AllAcceptanceFunctionsExceptThreeObservedFunctionsASTPreserved': True,
                      'ApplicationRecipeOnlyBudget60To1800': True})
    return facts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('owner', 'contract-run', 'junit', 'provider-peer', 'driver-peer'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    target = WORK / 'root-independent-complete-source-review-v3-a.json'
    require(not target.exists(), 'fresh v3 root source review required')
    watched = {}
    new.add(watched, SELF)
    def bind(path):
        new.add(watched, path)
        return build.read(path)
    for path, digest in ORIGINAL.items():
        new.add(watched, path, digest)
        value = build.read(path)
        require(value.get('Passed') is True and value.get('InputDrift') == [], 'original source authority incomplete')
        new.merge(watched, value['InputSHA256'])
    require(len(build.read(next(iter(ORIGINAL)))['InputSHA256']) == 991, 'actual original 991-input manifest required')
    facts = source_review()
    recipe = bind(WORK / 'physical-v2-a/stage-plan.json')
    require(recipe['SourceADF']['SHA256'] == 'c2a317d360315d1c955a91844e1fe2428fcc82432e2e76f72fdf23c2e893cc66',
            'original routed ADF identity differs')
    query_count = Counter(re.findall(r'get_pins -hierarchical -regexp \{([^{}]+)\}',
                                    recipe['QueryBody'] + '\n' + '\n'.join(recipe['ExactCommands'])))
    require(len(recipe['NativeSelectors']) == 650 and sum(query_count.values()) == 3343
            and len(recipe['ExactCommands']) == 1096, 'original complete selector/command obligations differ')
    value = {**recipe, 'WorkDirectory': str(WORK / 'physical-v3-a')}
    rendered = new.render_application(value)
    require(observation.strip_markers(rendered) == old.render_application(value).replace('TILE8DF8V2', 'TILE8DF8V3'),
            'new application changes more than literal observation markers and namespace')
    freeze_path = WORK / 'freeze_complete_physical_release_v3_a.py'
    spec = importlib.util.spec_from_file_location('root_reviewed_v3_freezer', freeze_path)
    freezer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(freezer)
    static = freezer.bind_static_sources(watched)
    counts = freezer.bind_final_contracts(watched, args.owner.resolve(), args.contract_run.resolve(), args.junit.resolve())
    peer_refs = []
    peer_paths = (args.provider_peer.resolve(), args.driver_peer.resolve())
    require(peer_paths[0] != peer_paths[1], 'two distinct independent source peer reviews required')
    provider_inputs = [TOOLS / ('hdmi_camera_fisheye_tile8df8v3_' + role + '.py') for role in ROLES]
    provider_inputs.append(TOOLS / 'hdmi_camera_fisheye_tile8df8v3_application_observer.py')
    driver_inputs = [WORK / name for name in (*freezer.DRIVERS, *freezer.SCRIPT_NAMES,
                    'run_physical_release_contracts_v3_a.py', 'review_physical_release_group_v3_a.py')]
    for path, required in zip(peer_paths, (provider_inputs, driver_inputs)):
        peer = bind(path)
        require(peer.get('Passed') is True and peer.get('IndependentPeerReviewPerformed') is True
                and peer.get('InputDrift') == [] and peer.get('ProviderRevision') == 'tile8df8v3-budget1800-a',
                'fresh complete independent v3 peer source review required')
        require(all(peer['InputSHA256'].get(str(p)) == build.sha(p) for p in required),
                'independent peer does not cover its complete selected source group')
        new.merge(watched, peer['InputSHA256'])
        peer_refs.append(new.ref(path))
    new.merge(watched, static)
    forbidden = {str(target), *(str(p) for p in freezer.FUTURE)}
    require(not (forbidden & {str(p) for p in watched}),
            'self or future physical/release evidence entered source review')
    require(new.baseline_drift(watched) == [], 'v3 root source-review input drift')
    result = {'Schema': 'hdmi-camera-fisheye-tile8df8v3-complete-source-independent-peer-review-v1',
              'Passed': True, 'IndependentPeerReviewPerformed': True, 'ProviderRevision': 'tile8df8v3-budget1800-a',
              'CheckedUTC': datetime.now(timezone.utc).isoformat(), 'ProviderAdaptationReview': facts,
              'OriginalProviderManifest': new.ref(WORK / 'physical-release-provider-source-manifest-a.json'),
              'OriginalRootReview': new.ref(WORK / 'root-independent-complete-source-review-a.json'),
              'Exact650Selectors3343Occurrences1096CommandsRetained': True,
              'RenderedTclIdenticalAfterOnlyLiteralObservationRemovalAndNamespace': True,
              'ActualCPUCounts': counts, 'IndependentPeerReviews': peer_refs,
              'InputSHA256': {str(p): h for p, h in watched.items()}, 'InputDrift': [],
              'OriginalPhysicalAcceptanceInherited': False, 'PhysicalAcceptanceInherited': False,
              'EDAExecuted': False, 'HardwareAccessed': False,
              'PhysicalPassed': False, 'SourceContractReviewOnly': True}
    with target.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'Passed': True, 'Output': str(target), 'SHA256': build.sha(target), 'Inputs': len(watched)}))


if __name__ == '__main__':
    main()
