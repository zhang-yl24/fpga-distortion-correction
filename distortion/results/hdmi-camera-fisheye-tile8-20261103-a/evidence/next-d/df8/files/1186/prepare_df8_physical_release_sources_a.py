"""Create fresh df8 adapters from the prepared df9 source family; no EDA/tests.

The source-identical global direct-fill cache keeps its real unit, collision
and independent peer evidence in WORK9. Those records are never relabelled.
"""
from pathlib import Path
import ast
import hashlib
import json

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[1]
TOOLS = ROOT / 'tools'
PEER_WORK = WORK.with_name('hdmi-camera-fisheye-tile8df9-20261103-a')
ROLES = ('physical', 'scoped_native', 'target_query', 'physical_checks', 'final', 'bitstream', 'program')
SUPPLEMENTS = ('macro_we_aliases', 'startup_timing', 'vendor_startup_bounded_b')
DRIVERS = ('run_physical_v2_a.py', 'run_release_v2_a.py', 'prewarm_release_v2_a.py',
           'compress_completed_physical_v2_evidence_a.py')


def adapt(text):
    return text.replace('tile8df9', 'tile8df8').replace('TILE8DF9', 'TILE8DF8')


def fresh(path, source):
    ast.parse(source)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(source)


def ref(path):
    return {'Path': str(path), 'SHA256': hashlib.sha256(path.read_bytes()).hexdigest()}


def bit_index8(source):
    return (source.replace("get('CacheIndexBits')==9", "get('CacheIndexBits')==8")
            .replace("'CacheIndexBits':9", "'CacheIndexBits':8")
            .replace('INDEX9', 'INDEX8')
            .replace('system-sustained-native-b', 'system-sustained-native-a'))


def main():
    rows = []
    for role in ROLES:
        original = TOOLS / ('hdmi_camera_fisheye_tile8df9v2_' + role + '.py')
        target = TOOLS / ('hdmi_camera_fisheye_tile8df8v2_' + role + '.py')
        text = adapt(original.read_text(encoding='utf-8-sig'))
        fresh(target, bit_index8(text) if role == 'bitstream' else text)
        rows.append({'PreparedDF9Source': ref(original), 'NewDF8Source': ref(target)})
    for role in SUPPLEMENTS:
        original = TOOLS / ('hdmi_camera_fisheye_tile8df9_' + role + '.py')
        target = TOOLS / ('hdmi_camera_fisheye_tile8df8_' + role + '.py')
        fresh(target, adapt(original.read_text(encoding='utf-8-sig')))
        rows.append({'PreparedDF9Source': ref(original), 'NewDF8Source': ref(target)})
    for name in DRIVERS:
        fresh(WORK / name, adapt((PEER_WORK / name).read_text(encoding='utf-8-sig')))
    compression_path = WORK / 'physical-compression-helper-source-manifest-v2.json'
    compression = json.loads(adapt((PEER_WORK / compression_path.name).read_text()))
    compression['NewHelper'] = ref(WORK / 'compress_completed_physical_v2_evidence_a.py')
    with compression_path.open('x', encoding='utf-8') as stream:
        json.dump(compression, stream, indent=2)
        stream.write('\n')
    for name in ('review_physical_release_group_a.py', 'run_physical_release_contracts_a.py',
                 'freeze_complete_physical_release_a.py', 'bind_selected_four_roles_a.py'):
        source = adapt((PEER_WORK / name).read_text(encoding='utf-8-sig'))
        source = source.replace('INDEX9', 'INDEX8').replace("'CacheIndexBits': 9", "'CacheIndexBits': 8")
        source = source.replace("get('CacheIndexBits') == 9", "get('CacheIndexBits') == 8")
        source = source.replace('system-sustained-native-b', 'system-sustained-native-a')
        fresh(WORK / name, source)
    tests = WORK / 'physical-release-tests-a'
    tests.mkdir(exist_ok=False)
    for original in (PEER_WORK / tests.name).glob('*.py'):
        source = adapt(original.read_text(encoding='utf-8-sig'))
        source = bit_index8(source).replace("'CacheIndexBits': 9", "'CacheIndexBits': 8")
        if original.name == 'revision_test_directfill_simulation_gate.py':
            source = source.replace("'CacheIndexBits': 8,", "'CacheIndexBits': 9,")
        if original.name == 'revision_test_sustained_simulation_gate.py':
            source = source.replace('system-sustained-native-b', 'system-sustained-native-a')
            source = source.replace("('CacheIndexBits', 8)", "('CacheIndexBits', 9)")
        if original.name == 'revision_test_root_source_binding.py':
            source = source.replace('index9', 'index8').replace('.INDEX_BITS(9)', '.INDEX_BITS(8)')
            source = source.replace("for replacement in ('.INDEX_BITS(8)'", "for replacement in ('.INDEX_BITS(9)'")
            source = source.replace("result['CacheIndexBits'] == 9", "result['CacheIndexBits'] == 8")
            source = source.replace('== 131072', '== 65536')
            source = source.replace("path = WORK / 'cache-unit-a/simulation.json'",
                "path = WORK.with_name('hdmi-camera-fisheye-tile8df9-20261103-a') / 'cache-unit-a/simulation.json'")
            source = source.replace("receipt['Cases']['1920-i9']", "receipt['Cases']['1920-i8']")
            source = source.replace("case['index_bits'] == 9", "case['index_bits'] == 8")
        fresh(tests / original.name, source)
    peer_tests = WORK / 'directfill-peer-tests-a'
    peer_tests.mkdir(exist_ok=False)
    for original in (PEER_WORK / peer_tests.name).glob('test_*.py'):
        source = original.read_text(encoding='utf-8-sig')
        source = source.replace("path = WORK / 'cache-commit-collision-a/simulation.json'",
            "path = WORK.with_name('hdmi-camera-fisheye-tile8df9-20261103-a') / 'cache-commit-collision-a/simulation.json'")
        fresh(peer_tests / original.name, source)
    value = {'Schema': 'tile8df8-physical-release-source-preparation-v1', 'Prepared': True,
             'Adapters': rows, 'OriginalDF9SourcesModified': False,
             'SameCacheSourceEvidenceLivesInActualWORK9': True, 'SameCacheCollisionIndexBits': 9,
             'OwnDF8SystemAndSustainedEvidenceRequired': True, 'FinalContractsExecuted': False,
             'ProviderManifestFrozen': False, 'EDAExecuted': False, 'HardwareAccessed': False}
    with (WORK / 'physical-release-adaptation-prebuild-a.json').open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'PreparedAdapters': len(rows), 'PreparedDrivers': len(DRIVERS),
                      'PreparedTestFiles': len(list(tests.glob('*.py'))), 'EDAExecuted': False,
                      'TestsExecuted': False, 'ManifestFrozen': False}))


if __name__ == '__main__':
    main()
