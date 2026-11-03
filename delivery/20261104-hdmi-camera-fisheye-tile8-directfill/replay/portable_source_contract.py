"""Read-only portable replay of finite cache source/unit/collision evidence.

The input map transports original Windows identities to explicit bundle paths.
It is not a publication or physical release receipt. No EDA, hardware, frozen
WORK.review(), simulator runner, or external executable is invoked.
"""
from pathlib import Path, PurePosixPath, PureWindowsPath
from types import ModuleType
import argparse
import hashlib
import json
import re
import zlib

SELF = Path(__file__).resolve()
SCHEMA = 'tile8-stage-d-portable-source-contract-map-v1'
ROLES = {'Source', 'Baseline', 'Helper', 'HelperTests', 'ProductionManifest', 'UnitReceipt', 'CollisionReceipt'}
FDC_SHA256 = 'e27a18c4a5f228ac8543e50c9b50a145f14bf1d4e640ff34361422d32f1bf78a'
COMMON = {'tools/run_fill8_rowpipe_cache_sim.py': '7511b32ca0d03b04ffa7126a98dce01d31c701a67f654a553985fb3af0a43885',
          'tools/simulation_tools.py': 'cb6f08cf764cce9c088ede89c65ce8f7da0cee447d95015b5685fde18de50a6e'}
CANDIDATES = {
    'df9tp': {
        'Source': 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill_tagpipe.v',
        'SourceSHA256': 'cc47c00bf2458491c1def0c5be3a2f8d209269a57dc2259d46ce7ce1054486a1',
        'Baseline': 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v',
        'BaselineSHA256': 'd4730a733bc8f84886d268fcc90bb702db035a41867c812d6119694fbbf35b1e',
        'Helper': 'tools/hdmi_camera_fisheye_directfill_tagpipe_contract.py',
        'HelperSHA256': '30bd584d6cb4b4b0c0caa98f4045470496c0f6e28ee24cdb5357f00a6ace4fbd',
        'HelperTests': 'tests/test_hdmi_camera_fisheye_directfill_tagpipe_contract.py',
        'HelperTestsSHA256': 'dd6e8b6979377004e35204ff2671cef984834b8be8d8702d8cdcada8d25216fb',
        'ProductionManifestSHA256': 'c71b1c5c823361e594b58cb919698f1849186be0c1edd00ff18b53cd6bcdac42',
        'EngineSHA256': '59a6ed684d10e8fe8c116be6bfbcd46c376ad1922e15d263869e976a9a6be440',
        'UnitWork': 'work/hdmi-camera-fisheye-tile8df9-tagpipe-20261103-a/cache-unit-a',
        'CollisionWork': 'work/hdmi-camera-fisheye-tile8df9-tagpipe-20261103-a/cache-commit-collision-a',
        'UnitReceiptSHA256': '496330b2bc5254de40527c415a0f52c216721a5c7ed639c13f20dd28a2532dc8',
        'CollisionReceiptSHA256': '0cb4fe3cd6ebb510d7f53a7f8ff6dc7ee2cb8b55a071d383dc34bad3b3c54761',
        'UnitSchema': 'tile8-directfill-tagpipe-independent-cache-simulation-v1',
        'CollisionSchema': 'tile8-directfill-tagpipe-independent-commit-collision-v1',
        'Bench': 'tests/tb_directfill_tagpipe_cache.sv',
        'BenchSHA256': 'b1c1888674f13f64ca988811a67ed6a54faa90d8946e94aa223c063720decaf8',
        'Runner': 'tools/run_directfill_tagpipe_cache_sim.py',
        'RunnerSHA256': '1087bcb8e434e5607333e56f626edb6a5169edc42de1cea539a518a8b4f71169',
        'CollisionBench': 'tests/tb_directfill_tagpipe_commit_collision.sv',
        'CollisionBenchSHA256': '67aeb2a24a108f43889fbfaefc0a28080e4099d6811131964c75d0e4c1900ec9',
        'CollisionRunner': 'tools/run_directfill_tagpipe_commit_collision_sim.py',
        'CollisionRunnerSHA256': '8834177bd14d615cf8d2581d0a07c79b4d23c378ec4deebf7fa7eb65e31c6f2e',
        'UnitMarker': 'PASS TAGPIPE complete independent cache regression',
        'OutputsPerCase': 390, 'WarmLatency': 5, 'IndexBits': 9, 'TagReadPipeline': True,
    },
    'df8': {
        'Source': 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v',
        'SourceSHA256': 'd4730a733bc8f84886d268fcc90bb702db035a41867c812d6119694fbbf35b1e',
        'Baseline': 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_fill8r3.v',
        'BaselineSHA256': 'ccddbc0293698184a3695744d7fca88350969ccc5f69cb1762b39eac84a0d294',
        'Helper': 'tools/hdmi_camera_fisheye_directfill_contract.py',
        'HelperSHA256': '83381ed5787597d4a91d97dfd834cb8c1341c72225a8b4b685b72c25f810e910',
        'HelperTests': 'tests/test_hdmi_camera_fisheye_directfill_contract.py',
        'HelperTestsSHA256': '7d35a1f87aafab46d8b28739734bfc59bf8e2737e48021c5245d09d7a58ff8e8',
        'ProductionManifestSHA256': 'ef5758832793f0ebcc0e8ee77a8410ac74baa87517256497615438f6dc5bd559',
        'EngineSHA256': '3b7b35186f6dba412e8e41b8798f63e6530cc750281b3041f8a837b421ad5a28',
        'UnitWork': 'work/hdmi-camera-fisheye-tile8df9-20261103-a/cache-unit-a',
        'CollisionWork': 'work/hdmi-camera-fisheye-tile8df9-20261103-a/cache-commit-collision-a',
        'UnitReceiptSHA256': '3340fb27a7d6953e10e98cf07dba0cb8ed85181beaaf049eb392d8fc72870b27',
        'CollisionReceiptSHA256': '2ceef24b77af4243907ce7dc343ce321f10e02384e7966aba910b95b1aef02d3',
        'UnitSchema': 'tile8-directfill-independent-cache-simulation-v1',
        'CollisionSchema': 'tile8-directfill-independent-peer-commit-collision-v1',
        'Bench': 'tests/tb_directfill_rowpipe_cache.sv',
        'BenchSHA256': '1095a80958e59950fe2ff49a8ff10401e4a17ddb5a32e1c817515cf05c20f5f4',
        'Runner': 'tools/run_directfill_rowpipe_cache_sim.py',
        'RunnerSHA256': 'e86fa646130c74b6eb98b2bfb888042251d6698d1e950a9935a47e2b7c9911a6',
        'CollisionBench': 'tests/tb_directfill_commit_collision_peer.sv',
        'CollisionBenchSHA256': 'bd7736f98ec4ac8ebd24df1bf3e72dffa8ea72d09aad1e4d818be882d740f2ab',
        'CollisionRunner': 'tools/run_directfill_commit_collision_peer_sim.py',
        'CollisionRunnerSHA256': 'b6ede92990f23defbfc86b7920da84ecb05f9dd5da70b6be18e64afcb3976b84',
        'UnitMarker': 'PASS DIRECTFILL complete independent cache regression',
        'OutputsPerCase': 386, 'WarmLatency': 4, 'IndexBits': 8, 'TagReadPipeline': False,
    },
}


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=unique)


def windows_identity(name):
    require(type(name) is str and name and not any(ord(c) < 32 for c in name), 'invalid original Windows identity')
    path = PureWindowsPath(name)
    require(path.is_absolute() and re.fullmatch(r'[A-Za-z]:', path.drive) is not None and
            '..' not in path.parts and ':' not in ''.join(path.parts[1:]),
            'original identity must be an absolute drive path without traversal')
    return str(path).casefold()


def relative_artifact(name):
    require(type(name) is str and name and not any(ord(c) < 32 for c in name), 'invalid saved artifact name')
    path = PureWindowsPath(name)
    require(not path.anchor and not path.drive and '..' not in path.parts and ':' not in name,
            'saved artifact escaped its receipt directory')
    return path


def bundle_file(bundle, name):
    require(type(name) is str and name and '\\' not in name and ':' not in name and
            not any(ord(c) < 32 for c in name), 'bundle target must be a POSIX relative path')
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and '..' not in relative.parts and relative.parts and
            relative.as_posix() == name and name not in ('.', ''), 'bundle target escaped or is not canonical')
    path = bundle.joinpath(*relative.parts).resolve(strict=True)
    require(path.is_relative_to(bundle) and path.is_file(), 'bundle target escaped or is not a file')
    return path


def verify_map(bundle, mapping_path):
    bundle, mapping_path = Path(bundle).resolve(strict=True), Path(mapping_path).resolve(strict=True)
    require(bundle.is_dir() and mapping_path.is_relative_to(bundle), 'input mapping must be inside bundle')
    value = load_json(mapping_path)
    require(set(value) == {'Schema', 'Candidate', 'Roles', 'Files'} and value['Schema'] == SCHEMA and
            value['Candidate'] in CANDIDATES and set(value['Roles']) == ROLES,
            'exact candidate/source-contract mapping schema and roles required')
    require(isinstance(value['Files'], list) and value['Files'], 'nonempty explicit file map required')
    files, targets, watched = {}, set(), {str(mapping_path): sha(mapping_path)}
    # Verify every mapped size/SHA before loading any trusted helper code.
    for row in value['Files']:
        require(set(row) == {'OriginalPath', 'BundlePath', 'SHA256', 'Bytes'}, 'exact mapped-file fields required')
        key = windows_identity(row['OriginalPath'])
        require(type(row['BundlePath']) is str and key not in files and row['BundlePath'].casefold() not in targets,
                'duplicate original identity or bundle target')
        require(type(row['Bytes']) is int and row['Bytes'] >= 0 and
                type(row['SHA256']) is str and re.fullmatch('[0-9a-f]{64}', row['SHA256']) is not None,
                'exact SHA and integer byte size required')
        path = bundle_file(bundle, row['BundlePath'])
        require(path.stat().st_size == row['Bytes'] and sha(path) == row['SHA256'],
                'mapped file byte size/SHA drift: ' + row['BundlePath'])
        files[key] = {**row, 'ResolvedPath': path}
        targets.add(row['BundlePath'].casefold()); watched[str(path)] = row['SHA256']
    roles = {name: windows_identity(original) for name, original in value['Roles'].items()}
    require(all(key in files for key in roles.values()) and len(set(roles.values())) == len(roles),
            'every role needs its own explicitly mapped identity')
    return value, files, roles, watched


def pixel(x, y, bank, epoch, width, height):
    if x < 0 or y < 0 or x >= width or y >= height:
        return 0
    position = y * width + x
    word = (position * 109 + (position >> 3) * 53 + (position ^ (position >> 9)) * 17 +
            0xac37 + bank * 0x2513 + epoch * 0x149b) & 65535
    red, green, blue = word >> 11, (word >> 5) & 63, word & 31
    return ((red << 3 | red >> 2) << 16 | (green << 2 | green >> 4) << 8 | blue << 3 | blue >> 2)


def validate_trace(text, width, height):
    pending, accepted_order, actual, expected, outputs = {}, [], bytearray(), bytearray(), 0
    for line in text.splitlines():
        fields = line.split()
        require(bool(fields), 'empty independent trace line')
        if fields[0] == 'Q':
            require(len(fields) == 6, 'query trace field count')
            x, y, tag, bank, epoch = map(int, fields[1:])
            require(-(1 << 23) <= x < 1 << 23 and -(1 << 23) <= y < 1 << 23 and
                    0 <= tag < 1 << 25 and bank in (0, 1) and epoch > 0 and tag not in pending,
                    'invalid or duplicate independent query identity')
            pending[tag] = (x, y, bank, epoch)
            if tag != 500: accepted_order.append(tag)
        elif fields[0] == 'O':
            require(len(fields) == 8, 'output trace field count')
            values = [int(item, 16) for item in fields[1:]]
            p00, p10, p01, p11, fx, fy, tag = values
            require(tag in pending and all(0 <= p < 1 << 24 for p in values[:4]) and
                    0 <= fx < 256 and 0 <= fy < 256, 'output lacks a valid accepted query')
            require(accepted_order and tag == accepted_order.pop(0), 'independent output query order differs')
            x, y, bank, epoch = pending.pop(tag); x0, y0 = x // 256, y // 256
            pixels = [pixel(x0 + dx, y0 + dy, bank, epoch, width, height)
                      for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1))]
            require(values[:4] == pixels and fx == x % 256 and fy == y % 256,
                    'independent pixel/fraction/epoch oracle differs')
            for words, target in ((values[:4], actual), (pixels, expected)):
                for word in words: target.extend(word.to_bytes(3, 'big'))
                target.extend((fx, fy)); target.extend(tag.to_bytes(4, 'big'))
            outputs += 1
        else:
            raise ValueError('unknown independent trace record')
    require(set(pending) == {500} and not accepted_order and outputs > 250 and actual == expected,
            'only the deliberate final-commit reset query may remain canceled')
    require(zlib.crc32(actual) == zlib.crc32(expected), 'independent trace CRC differs')
    return {'Outputs': outputs, 'OracleBytes': len(actual), 'CRC32': f'{zlib.crc32(actual):08x}',
            'SHA256': hashlib.sha256(actual).hexdigest(), 'ResetCanceledQueries': 1,
            'ActualMatchesIndependentPixelOracle': True}


def validate_case(case, summary, config):
    require({k: v for k, v in case.items() if k != 'IndependentTrace'} == summary,
            'case receipt differs from actual summary artifact')
    exact = {'passed': True, 'normal_outputs': config['OutputsPerCase'], 'commits_per_fill': 8,
        'reset_before_last_commit': 1, 'fault_cases': 6, 'warm_stream_outputs': 64,
        'warm_span_cycles': 63, 'warm_first_valid_latency': config['WarmLatency']}
    require(all(type(case.get(k)) is type(v) and case[k] == v for k, v in exact.items()),
            'exact independent pixel/fault/warm-II coverage differs')
    positive = ('complete_fills', 'same_cycle_first_beats', 'delayed_first_beats', 'continuous_commit_pairs',
        'ar_stalls', 'r_gaps', 'output_stalls', 'input_stalls', 'queue_full', 'frame_pending',
        'fast_queries', 'slow_queries', 'frame_drains')
    require(all(type(case.get(k)) is int and case[k] > 0 for k in positive) and
            case['ram_pixels_checked'] == case['complete_fills'] * 128,
            'real RAM commit or handshake coverage is vacuous')
    if config['TagReadPipeline']:
        require(all(type(case.get(k)) is int and case[k] > 0 for k in ('lookup_miss_overlap', 'query_refreshes',
            'stale_valid_refreshes', 'result_stall_metadata_cycles', 'slow_lookup_cycles')) and
            case['query_refreshes'] == case['lookup_miss_overlap'],
            'tagpipe stale/held-metadata/refresh coverage is insufficient')


def review(bundle, mapping_path):
    value, files, roles, watched = verify_map(bundle, mapping_path)
    config, used = CANDIDATES[value['Candidate']], set(roles.values())
    original_source = PureWindowsPath(value['Roles']['Source'])
    suffix = PurePosixPath(config['Source']).parts
    require(tuple(part.casefold() for part in original_source.parts[-len(suffix):]) ==
            tuple(part.casefold() for part in suffix), 'selected cache role uses another source path')
    project = PureWindowsPath(*original_source.parts[:-len(suffix)])

    def mapped(original, expected=None):
        key = windows_identity(str(original)); require(key in files, 'missing explicit original-path mapping: ' + str(original))
        row = files[key]; require(expected is None or row['SHA256'] == expected, 'mapped original identity has wrong SHA')
        used.add(key); return row['ResolvedPath']

    for role in ROLES:
        mapped(value['Roles'][role], config[role + 'SHA256'])
    for role in ('Source', 'Baseline', 'Helper', 'HelperTests'):
        require(roles[role] == windows_identity(str(project / config[role])), 'incorrect candidate source/helper role')
    require(roles['ProductionManifest'] == windows_identity(str(project / f'board/hdmi-camera-fisheye-tile8{value["Candidate"]}-build-sources.json')),
            'candidate manifest role is not this namespace')
    require(roles['UnitReceipt'] == windows_identity(str(project / config['UnitWork'] / 'simulation.json')) and
            roles['CollisionReceipt'] == windows_identity(str(project / config['CollisionWork'] / 'simulation.json')),
            'saved unit/collision role changed from its actual original WORK')
    manifest = load_json(mapped(value['Roles']['ProductionManifest']))
    require(manifest['Schema'] == f'hdmi-camera-fisheye-tile8{value["Candidate"]}-source-closure-v1' and
            len(manifest['source_files']) == len(set(manifest['source_files'])) == 110 and
            set(manifest['source_files']) == set(manifest['SourceSHA256']), 'exact 110-source manifest required')
    for name in manifest['source_files']:
        relative_artifact(name); mapped(project / name, manifest['SourceSHA256'][name])
    require(manifest['SourceSHA256'].get(config['Source']) == config['SourceSHA256'], 'production manifest binds another cache')
    engine_name = f'rtl/experimental/hdmi_camera_fisheye_engine_tile8{value["Candidate"]}.v'
    engine = mapped(project / engine_name, config['EngineSHA256'])
    require(engine.read_text(encoding='utf-8').count(f'.INDEX_BITS({config["IndexBits"]})') == 1,
            'engine cache capacity differs')
    fdc_name = f'board/hdmi-camera-fisheye-tile8{value["Candidate"]}-internal.fdc'
    mapped(project / fdc_name, FDC_SHA256)
    difference = manifest['CSourceDifferenceReview']
    require(difference['CacheIndexBits'] == config['IndexBits'] and difference['DirectFillCache'] is True and
            (not config['TagReadPipeline'] or difference.get('TagReadPipeline') is True), 'manifest candidate cache declarations differ')
    helper_path = mapped(value['Roles']['Helper']); helper = ModuleType('frozen_portable_cache_source_helper')
    helper.__file__ = str(helper_path)
    # The code is an exact trusted SHA and only its pure source function is used.
    # Rebind its baseline path in memory; never change frozen helper/receipt bytes.
    helper_bytes = helper_path.read_bytes()
    require(hashlib.sha256(helper_bytes).hexdigest() == config['HelperSHA256'],
            'trusted pure source helper changed before loading')
    exec(compile(helper_bytes, str(helper_path), 'exec'), helper.__dict__)
    helper.BASELINE = mapped(value['Roles']['Baseline'])
    facts = helper.review_source(mapped(value['Roles']['Source']).read_bytes().decode('utf-8'))
    require(facts['SourceSHA256'] == config['SourceSHA256'] and
            bool(facts.get('TagReadPipeline', False)) == config['TagReadPipeline'], 'frozen source contract identifies another cache')

    def saved_receipt(role, prefix):
        original = value['Roles'][role]; path = mapped(original)
        receipt = load_json(path)
        require(receipt['Schema'] == config[prefix + 'Schema'] and receipt.get('Passed') is True and
                receipt.get('InputDrift') == [] and receipt.get('PDSAccessed') is False and
                receipt.get('HardwareAccessed') is False and not receipt.get('Error'), 'clean completed small receipt required')
        bench_key, runner_key = ('Bench', 'Runner') if prefix == 'Unit' else ('CollisionBench', 'CollisionRunner')
        expected = {windows_identity(str(project / name)): h for name, h in {
            config['Source']: config['SourceSHA256'], config[bench_key]: config[bench_key + 'SHA256'],
            config[runner_key]: config[runner_key + 'SHA256'], **COMMON}.items()}
        actual = {windows_identity(name): h for name, h in receipt['SourceSHA256'].items()}
        require(len(actual) == len(receipt['SourceSHA256']) and actual == expected,
                'saved source/bench/runner closure differs from selected cache')
        for name, h in receipt['SourceSHA256'].items(): mapped(name, h)
        artifacts = {}
        for name, h in receipt['ArtifactsSHA256'].items():
            item = relative_artifact(name)
            normalized = str(item).casefold(); require(normalized not in artifacts, 'duplicate saved artifact identity')
            artifacts[normalized] = mapped(PureWindowsPath(original).parent / item, h)
        require('simulation.log' in artifacts, 'actual simulation log not bound')
        log = artifacts['simulation.log'].read_text(encoding='utf-8', errors='strict')
        marker = config['UnitMarker'] if prefix == 'Unit' else 'PASS DIRECTFILL PEER real final-commit/fault/reset collisions'
        require(marker in log and '$finish called' in log and not re.search(r'(?im)^\s*(?:fatal|error):', log),
                'actual RTL completion marker absent')
        return receipt, artifacts, log

    unit, artifacts, log = saved_receipt('UnitReceipt', 'Unit')
    require(unit.get('FullFrameSimulated') is False and set(unit['Cases']) == {'639-i3', '1920-i7', '1920-i8', '1920-i9'},
            'declared finite unit geometries differ')
    replayed = {}
    for name, case in unit['Cases'].items():
        width, index = map(int, name.split('-i')); height = 480 if width == 639 else 1080
        require(case['width'] == width and case['height'] == height and case['index_bits'] == index,
                'case geometry differs')
        summary_name, trace_name = f'summary-{name}.json', f'trace-{name}.txt'
        require(summary_name in artifacts and trace_name in artifacts, 'actual summary/trace not bound')
        validate_case(case, load_json(artifacts[summary_name]), config)
        trace = validate_trace(artifacts[trace_name].read_text(encoding='utf-8'), width, height)
        require(trace == case['IndependentTrace'] and trace['Outputs'] == case['normal_outputs'],
                'reparsed pixel stream CRC/SHA/count differs from receipt')
        require(f'WIDTH{width} INDEX{index} fills{case["complete_fills"]} outputs{case["normal_outputs"]} faults6' in log,
                'actual RTL case marker differs from summary')
        replayed[name] = {'IndependentTrace': trace, 'CompleteFills': case['complete_fills'],
            'RAMPixelsChecked': case['ram_pixels_checked'], 'WarmOutputs': 64, 'WarmSpanCycles': 63,
            'WarmFirstValidLatency': config['WarmLatency'], 'TagReadPipeline': config['TagReadPipeline']}
    collision, artifacts, _ = saved_receipt('CollisionReceipt', 'Collision')
    expected = {'Passed': True, 'IndexBits': 9, 'Cases': 4, 'SuccessfulCommonResetRecoveries': 4,
        'IndependentRAMPixelsChecked': 864, 'NinthRAndLastCommitCollision': True, 'MalformedFinalRID': True,
        'MissingFinalRLAST': True, 'ResetBeforeFinalRAMCommit': True, 'FaultQuarantineChecked': True}
    require(collision.get('HDLSimulationExecuted') is True and collision.get('NativeRAMMappingOrTimingAccepted') is False and
            collision['Summary'] == expected, 'independent collision/reset coverage differs')
    require('peer-commit-summary.json' in artifacts and 'peer-commit-cases.csv' in artifacts and
            load_json(artifacts['peer-commit-summary.json']) == expected, 'collision summary artifact differs')
    require(artifacts['peer-commit-cases.csv'].read_text(encoding='utf-8').splitlines() == [
        'case,kind,checked_pixels,fault,last_valid', '0,ninth_R_vs_last_commit,128,4,0',
        '1,malformed_final_R,112,3,0', '2,malformed_final_R,112,3,0', '3,common_reset_vs_last_commit,0,0,0'],
        'actual independent fault/last-valid collision CSV differs')
    require(used == set(files), 'unreferenced files in source-contract bundle map')
    require(all(sha(path) == h for path, h in watched.items()), 'replay-time input byte drift')
    return {'Schema': 'tile8-stage-d-portable-finite-source-replay-v1', 'Candidate': value['Candidate'],
        'PortableSourceContractVerified': True, 'TagReadPipeline': config['TagReadPipeline'],
        'ProductionSourcesVerified': 110, 'MappedFilesVerified': len(files), 'SourceFacts': facts,
        'UnitCasesReparsed': replayed, 'CollisionCasesVerified': expected,
        'HelperFullWORKReviewCalled': False, 'FrozenReceiptsRewritten': False,
        'WarmIIFromSavedRTLAssertionsAndSummary': True, 'RTLReexecuted': False,
        'FullSystemRTLVerifiedHere': False, 'NativePhysicalAcceptanceRecomputed': False,
        'BitstreamVerifiedHere': False, 'BoardFPSVerifiedHere': False, 'PublicationComplete': False,
        'EDAExecuted': False, 'HardwareAccessed': False, 'HardwareReleaseAllowed': False}, watched


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--mapping', type=Path, required=True)
    args = parser.parse_args(argv)
    facts, watched = review(args.bundle, args.mapping)
    print(json.dumps({key: facts[key] for key in ('Candidate', 'PortableSourceContractVerified',
        'ProductionSourcesVerified', 'MappedFilesVerified', 'PublicationComplete', 'EDAExecuted',
        'HardwareAccessed', 'HardwareReleaseAllowed')} | {'Watched': len(watched)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
