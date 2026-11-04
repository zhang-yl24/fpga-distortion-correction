"""Freeze INDEX8 raw-build inputs after its own completed functional gates.

This creates no P: alias, build directory, EDA process or hardware action.
The shared cache unit and independent collision remain at their actual INDEX9
work paths; their evidence concerns the identical cache source, not INDEX8 STA.
"""
from pathlib import Path
import importlib.util
import json
import sys
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[2]
ROOT = REPO / 'distortion'
WORK = ROOT / 'work/hdmi-camera-fisheye-tile8df8-20261103-a'
PEER = ROOT / 'work/hdmi-camera-fisheye-tile8df9-20261103-a'
sys.path[:0] = [str(ROOT / 'tools'), str(REPO / '.venv/Lib/site-packages')]
import hdmi_camera_fisheye_tile8df8_build as build
import hdmi_camera_fisheye_tile8df8_native as native
import hdmi_camera_fisheye_tile8df8_scoped_native as scoped
import hdmi_camera_fisheye_directfill_contract as cache
import run_hdmi_camera_fisheye_tile8df8_system_sim as system


def main():
    target = WORK / 'build-provider-source-manifest-a.json'
    build.require(not target.exists() and not (WORK / 'build-a').exists(), 'fresh pre-build freeze required')
    plan, _ = build.recipe(WORK / 'build-a', require_alias=False)
    watched = {}

    def add(path, digest=None):
        build.add(watched, path, digest)

    def merge(rows):
        for path, digest in rows.items():
            add(path, digest)

    merge(plan['InputSHA256'])
    facts, inputs = cache.review()
    build.require(facts['Passed'] is True, 'shared exact cache source/unit contract required')
    merge(inputs)
    role_refs = {}
    for label, filename in (('SmallSystem', 'system-small-a'), ('NativeSystem', 'system-native-a')):
        path = WORK / filename / 'simulation.json'
        value, inputs = system.verify(path)
        build.require(value.get('Passed') is True and value.get('FunctionalPassed') is True
                      and value.get('CacheIndexBits') == 8 and value.get('DirectFillCache') is True
                      and value.get('InputDrift') == [], 'own complete INDEX8 system gate required')
        merge(inputs)
        role_refs[label] = build.ref(path)
    worker = WORK / 'run_build_native.py'
    spec = importlib.util.spec_from_file_location('reviewed_df8_raw_worker', worker)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    collision = module.bind_peer_collision()
    peer_path = PEER / 'directfill-independent-peer-review-a.json'
    peer = build.read(peer_path)
    build.require(peer.get('Passed') is True and peer.get('InputDrift') == []
                  and peer.get('Source') == build.ref(cache.SOURCE)
                  and peer.get('IndependentCollisionReceipt') == collision,
                  'same-cache independent source/collision review required')
    merge(peer['InputSHA256'])
    add(peer_path)
    helper = WORK / 'compress_completed_physical_v2_evidence_a.py'
    helper_manifest = WORK / 'physical-compression-helper-source-manifest-v2.json'
    build.require(build.ref(helper) == build.read(helper_manifest)['NewHelper'], 'completed-stage helper drift')
    for path in (build.SELF, native.SELF, scoped.SELF, worker, helper, helper_manifest,
                 Path(__file__).resolve(), cache.SELF):
        add(path)
    junit = REPO / 'output/tile8_next15h_20261103/source-contract-tests-d.xml'
    suites = ET.parse(junit).getroot().findall('testsuite')
    build.require(sum(int(s.attrib.get('tests', 0)) for s in suites) == 81
                  and all(int(s.attrib.get(k, 0)) == 0 for s in suites
                          for k in ('errors', 'failures', 'skipped')), 'actual 81 source contracts required')
    for path in (junit, ROOT / 'tests/test_hdmi_camera_fisheye_tile8df_source_contracts.py',
                 ROOT / 'tests/test_hdmi_camera_fisheye_directfill_contract.py'):
        add(path)
    build.require(all(build.sha(path) == digest for path, digest in watched.items()), 'pre-build input drift')
    manifest = build.read(ROOT / build.MANIFEST)
    value = {'Schema': 'hdmi-camera-fisheye-tile8df8-build-provider-source-freeze-v1',
             'Passed': True, 'FrozenUTC': build.utc(), 'Variant': 'tile8df8',
             'SelectedSourceSHA256': manifest['SourceSHA256'], 'InputSHA256': dict(sorted(watched.items())),
             'ProductionInputs': len(plan['SourceFiles']), 'FunctionalGates': role_refs,
             'ActualSourceContracts': build.ref(junit), 'ActualSourceContractTests': 81,
             'OwnCacheAndFullSystemPassed': True, 'SameCacheIndependentCommitCollisionPassed': True,
             'IndependentCommitCollisionReceipt': collision, 'CollisionExercisedIndexBits': 9,
             'CacheUnitIncludesIndexBits8': True, 'OriginalTile8SourcesModified': False,
             'PriorPhysicalTimingOrAcceptanceInherited': False, 'HardwareAccessed': False, 'EDAExecuted': False}
    with target.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'Manifest': build.ref(target), 'Inputs': len(watched), 'EDAExecuted': False}))


if __name__ == '__main__':
    main()
