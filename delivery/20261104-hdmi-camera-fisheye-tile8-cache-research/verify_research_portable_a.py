"""Finite saved research replay. Never run HDL/EDA/native providers/hardware."""
import argparse
import collections
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import random
import re
import struct
import zlib

MODEL_SHA = 'fa3e572f457b34bb0123decece435ad923f5e64c8f9f60e2f5e465fde6ab8df2'
ASSOC_SHA = '745f4f2cbc26f733d991eca2998484542a131c47f2d747504194f8ecaca95f0b'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inside(root, name):
    require(isinstance(name, str) and name and '\\' not in name and ':' not in name, 'canonical POSIX bundle path required')
    relative = PurePosixPath(name)
    require(not relative.is_absolute() and relative.as_posix() == name and all(p not in ('', '.', '..') for p in relative.parts), 'noncanonical/escaping bundle path')
    path = root.joinpath(*relative.parts)
    require(path.resolve().is_relative_to(root.resolve()) and path.is_file() and not path.is_symlink(), 'missing/escaping bundle file')
    return path


def pixel(x, y, bank, epoch, width, height):
    if not (0 <= x < width and 0 <= y < height):
        return 0
    pos = y * width + x
    word = (pos * 109 + (pos >> 3) * 53 + (pos ^ (pos >> 9)) * 17 + 0xac37 + bank * 0x2513 + epoch * 0x149b) & 65535
    r, g, b = word >> 11, (word >> 5) & 63, word & 31
    return ((r << 3 | r >> 2) << 16) | ((g << 2 | g >> 4) << 8) | (b << 3 | b >> 2)


def replay_unit_trace(text, width, height):
    pending = collections.deque()
    seen = set()
    output = bytearray()
    count = canceled = 0
    for raw in text.splitlines():
        fields = raw.split()
        require(fields, 'empty trace row')
        if fields[0] == 'Q':
            require(len(fields) == 6, 'bad accepted-query trace')
            x, y, tag, bank, epoch = map(int, fields[1:])
            require(tag not in seen and 0 <= tag < (1 << 25) and bank in (0, 1) and epoch >= 0, 'duplicate/invalid accepted-query metadata')
            require(-(1 << 23) <= x < (1 << 23) and -(1 << 23) <= y < (1 << 23), 'query coordinates exceed signed input')
            seen.add(tag)
            pending.append((x, y, tag, bank, epoch))
        else:
            require(fields[0] == 'O' and len(fields) == 8 and pending, 'bad/unowned output trace')
            got = [int(n, 16) for n in fields[1:]]
            if pending[0][2] == 500:
                require(canceled == 0 and got[-1] == 501, 'only reset query500 may be canceled immediately before501')
                pending.popleft()
                canceled += 1
            require(pending, 'unowned output after canceled query')
            x, y, tag, bank, epoch = pending.popleft()
            x0, y0 = x // 256, y // 256
            expected = [pixel(x0 + dx, y0 + dy, bank, epoch, width, height) for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1))]
            require(got == expected + [x & 255, y & 255, tag], 'ordered independent pixel/fraction/tag oracle differs')
            for value in expected:
                output.extend(value.to_bytes(3, 'big'))
            output.extend((x & 255, y & 255))
            output.extend(tag.to_bytes(4, 'big'))
            count += 1
    require(not pending and canceled == 1 and count > 250, 'incomplete unit query/output/reset closure')
    return dict(Outputs=count, OracleBytes=len(output), CRC32=f'{zlib.crc32(output):08x}', SHA256=sha(output), ResetCanceledQueries=canceled)


def lru_oracle(groups, runs, bits, ways):
    banks = [collections.OrderedDict() for _ in range((1 << bits) // ways)]
    fast = slow = fills = samples = 0
    hist = collections.Counter()
    for query, run in zip(groups, runs):
        for _ in range(run):
            valid = [b for b in query if b >= 0]
            samples += len(valid)
            all_hit = all(b in banks[b % len(banks)] for b in valid)
            fast += all_hit
            slow += not all_hit
            missed = 0
            for b in valid:
                bank = banks[b % len(banks)]
                if b in bank:
                    bank.move_to_end(b)
                else:
                    if len(bank) == ways:
                        bank.popitem(last=False)
                    bank[b] = None
                    fills += 1
                    missed += 1
            if not all_hit:
                hist[str(missed)] += 1
    data = b''.join(struct.pack('<i', b) for bank in banks for b in reversed(bank))
    return dict(FastQueries=fast, SlowQueries=slow, Fills=fills, InBoundsNeighbourSamples=samples,
                InBoundsNeighbourHits=samples - fills, SlowQueriesByFillCount=dict(hist), FinalResidentFullTagsSHA256=sha(data))


def finite_capacity_replay(model_path):
    require(sha(model_path.read_bytes()) == MODEL_SHA, 'actual frozen capacity model differs')
    spec = importlib.util.spec_from_file_location('saved_research_capacity_model', model_path)
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    rng = random.Random(20261104)
    pool = [-1, 0, 1, 255, 256, 511, 512, 1023, 1024, 2048, 4096, 8192, 16384]
    groups = [[rng.choice(pool) for _ in range(4)] for _ in range(250)]
    runs = [rng.randrange(1, 8) for _ in groups]
    results = []
    for bits in (8, 9, 10):
        for ways in (1, 2, 4):
            expected = lru_oracle(groups, runs, bits, ways)
            actual = model.replay(groups, runs, bits, ways)
            require(all(actual[k] == value for k, value in expected.items()), 'finite uncompressed full-tag LRU oracle differs')
            results.append(dict(IndexBits=bits, Ways=ways, Queries=sum(runs), Fills=actual['Fills']))
    return results


def review(bundle, manifest_path):
    bundle = Path(bundle).resolve()
    value = json.loads(Path(manifest_path).read_text(encoding='utf-8-sig'))
    require(value.get('Schema') == 'tile8-cache-research-portable-map-v1' and value.get('ResearchOnly') is True,
            'research portable map required')
    require(value.get('EDAReexecuted') is False and value.get('BoardOrReleaseAcceptanceConferred') is False, 'portable map overclaims')
    require(isinstance(value.get('Files'), list) and value['Files'], 'complete file list required')
    files = {}
    for row in value['Files']:
        name = row['BundlePath']
        require(name.casefold() not in files and type(row['Bytes']) is int and row['Bytes'] >= 0
                and isinstance(row['SHA256'], str) and re.fullmatch('[0-9a-f]{64}', row['SHA256']), 'duplicate/bad map identity')
        path = inside(bundle, name)
        data = path.read_bytes()
        require(len(data) == row['Bytes'] and sha(data) == row['SHA256'], 'bundle SHA/size drift: ' + name)
        files[name.casefold()] = path

    def mapped(name):
        require(isinstance(name, str) and name.casefold() in files, 'role absent from verified file map')
        return files[name.casefold()]

    require(sha(mapped(value['AssocCacheSource']).read_bytes()) == ASSOC_SHA, 'wrong frozen two-way cache bound')
    require(value.get('UnitReceipts'), 'saved unit receipts required')
    units = []
    for group in value['UnitReceipts']:
        receipt = json.loads(mapped(group['Receipt']).read_text())
        require(receipt.get('Schema') == 'tile8-assoc2-tagpipe-independent-cache-simulation-v1'
                and receipt.get('Passed') is True and receipt.get('InputDrift') == [], 'saved actual unit did not pass')
        require(ASSOC_SHA in receipt['SourceSHA256'].values(), 'saved unit has wrong cache identity')
        require(len(group['Cases']) == 3, 'all three unit geometries required')
        require({(r['Width'], r['Height'], r['IndexBits']) for r in group['Cases']} ==
                {(2048, 480, 5), (639, 480, 6), (1920, 1080, 10)}, 'distinct required unit geometries absent')
        log_path = mapped(group['SimulationLog'])
        require(sha(log_path.read_bytes()) == receipt['ArtifactsSHA256']['simulation.log'], 'saved unit log not bound to original receipt')
        log = log_path.read_text(errors='replace')
        require('PASS TAGPIPE complete independent cache regression' in log and '$finish called' in log
                and not re.search(r'(?im)^\s*(fatal|error):', log), 'saved complete unit log required')
        for row in group['Cases']:
            case = receipt['Cases'][row['Case']]
            require((case['width'], case['height'], case['index_bits']) == (row['Width'], row['Height'], row['IndexBits']), 'unit geometry differs')
            require(case['warm_stream_outputs'] == 64 and case['warm_span_cycles'] == 63 and case['warm_first_valid_latency'] == 5
                    and case['fault_cases'] == 6 and case['commits_per_fill'] == 8, 'saved unit coverage weakened')
            require(all(case['AssociativeOracle'][k] > 0 for k in ('LRUVictimWay0Choices', 'LRUVictimWay1Choices',
                        'InvalidWay0Choices', 'InvalidWay1Choices', 'Way0Fills', 'Way1Fills', 'FastWay1Touches')), 'two-way coverage absent')
            summary_path = mapped(row['Summary'])
            require(sha(summary_path.read_bytes()) == receipt['ArtifactsSHA256'][summary_path.name], 'raw unit summary not bound')
            summary = json.loads(summary_path.read_text())
            require(summary == {k: n for k, n in case.items() if k not in ('IndependentTrace', 'AssociativeOracle')}, 'raw summary and receipt case differ')
            lru_rows = re.findall(r'ASSOC_ORACLE WIDTH(\d+) INDEX(\d+) checks(\d+) fillways(\d+)/(\d+) fastway1(\d+) invalid(\d+)/(\d+) lru(\d+)/(\d+)', log)
            matching = [tuple(map(int, r)) for r in lru_rows if int(r[0]) == row['Width'] and int(r[1]) == row['IndexBits']]
            keys = ('Width', 'IndexBits', 'SlowOracleChecks', 'Way0Fills', 'Way1Fills', 'FastWay1Touches',
                    'InvalidWay0Choices', 'InvalidWay1Choices', 'LRUVictimWay0Choices', 'LRUVictimWay1Choices')
            require(len(matching) == 1 and dict(zip(keys, matching[0])) == case['AssociativeOracle'], 'raw LRU log and receipt differ')
            trace_path = mapped(row['Trace'])
            require(sha(trace_path.read_bytes()) == receipt['ArtifactsSHA256'][trace_path.name], 'original saved trace identity differs')
            actual = replay_unit_trace(trace_path.read_text(), row['Width'], row['Height'])
            require(all(case['IndependentTrace'][k] == n for k, n in actual.items()), 'saved CRC/stream summary differs')
            units.append(dict(Case=row['Case'], **actual))
    require(len(value.get('BoundaryReceipts', [])) == 1, 'one complete saved boundary receipt required')
    for group in value['BoundaryReceipts']:
        receipt = json.loads(mapped(group['Receipt']).read_text())
        require(receipt.get('Schema') == 'tile8-assoc2-tagpipe-independent-boundary-simulation-v1'
                and receipt.get('Passed') is True and receipt.get('InputDrift') == []
                and ASSOC_SHA in receipt['SourceSHA256'].values(), 'saved boundary source/status differs')
        raw = mapped(group['CommitCSV'])
        require(sha(raw.read_bytes()) == receipt['ArtifactsSHA256']['commit/peer-commit-cases.csv'], 'original boundary CSV differs')
        require(raw.read_text().splitlines()[1:] == ['0,ninth_R_vs_last_commit,128,4,0', '1,malformed_final_R,112,3,0',
                '2,malformed_final_R,112,3,0', '3,common_reset_vs_last_commit,0,0,0'], 'saved actual boundary rows differ')
        require(receipt['CheckWay1FaultBoundary'] == dict(Passed=True, IndexBits=10, NormalIndependentPixelOutputs=2,
                UnownedRAtWay1HitCHECK=True, ChosenWay1Invalidated=True, OtherWay0Preserved=True,
                StickyQuarantineCycles=20, HierarchyForced=False), 'saved chosen-way CHECK fault scope differs')
    finite = finite_capacity_replay(mapped(value['CapacityModel']))
    return dict(Schema='tile8-cache-research-portable-review-v1', Passed=True, ResearchOnly=True,
                FilesVerified=len(files), SavedUnitCases=units, SavedBoundaryCases=5, FiniteCapacityLRUCases=finite,
                FullTraceReexecuted=False, HDLReexecuted=False, FullSystemReexecuted=False,
                NativeProviderInvoked=False, EDAReexecuted=False, HardwareAccessed=False,
                BoardOrReleaseAcceptanceConferred=False,
                Scope='Copied bytes + saved ordered unit pixel/CRC oracle + nine finite address/LRU cases only. Large native artifacts are indexed, not recreated.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--map', type=Path)
    args = parser.parse_args()
    print(json.dumps(review(args.bundle, args.map or args.bundle / 'source-map.json'), indent=2))
