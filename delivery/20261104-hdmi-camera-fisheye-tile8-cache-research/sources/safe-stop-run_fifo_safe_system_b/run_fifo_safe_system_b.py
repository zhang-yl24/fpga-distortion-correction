"""Isolated 2-way/256-KiB research system replay, with saved unit/boundary gates.

Only the cache, the engine's INDEX_BITS=10, and the fixture's observation
SIM_CACHE_INDEX_BITS=10 differ from the frozen direct-fill system inputs.
No public provider run/verify, EDA, bitstream, UART, or hardware is used.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import re
import sys
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DIST = REPO / 'distortion'
BASE = DIST / 'work/hdmi-camera-fisheye-tile8df8-20261103-a'
ASSOC_BASE = HERE.parent / 'assoc2way256-a'
SOURCE = ASSOC_BASE / 'rtl/ddr_neighbour_cache_scatter16_rowpipe_assoc2_tagpipe_b.v'
UNIT = ASSOC_BASE / 'unit-c/simulation.json'
BOUNDARY = ASSOC_BASE / 'boundary-a/simulation.json'
FIFO_UNIT = HERE / 'unit-a/simulation.json'
CONTRACT = HERE / 'system-source-contract-safe-b.json'
STOP_HELPER = HERE / 'run_tail_stop_probe_a.py'
STOP_HELPER_SHA = '001e8826ad79a6abfd4719e5cd2287a294cbca9e191c994e68c905be62f1e1bd'
OLD_STOP = 'wait(unique_total==STRESS_ACCEPTED);@(negedge core_clk);scan_enable=0;wait_drain();'
SAFE_STOP = 'wait(unique_total==STRESS_ACCEPTED);\n        begin : complete_scan_before_stop\n            integer stop_after_sequence;\n            stop_after_sequence=scan_sequence;\n            wait(scan_sequence>stop_after_sequence);\n        end\n        @(negedge core_clk);scan_enable=0;wait_drain();'
STOP_CASE_PINS = {'old': '3049ccdca2062e8171935b7e982136b4b5e408d6cf29b88e2b01671e5dde4a0d', 'safe': '3b8302ef1ae2aff83ef79110f5ba3ea25ae061380aa4cb2b30438b6213021d81'}
ENGINE_SOURCE = HERE / 'rtl/hdmi_camera_fisheye_engine_index10_fifo_a.v'
BASE_ENGINE_SOURCE = ASSOC_BASE / 'rtl/hdmi_camera_fisheye_engine_index10_a.v'
BASE_ENGINE_PIN = 'f5cacc66d2f51a273ed947a107380805461c7ef823b49c46a3c628ebdd027bd8'
ENGINE_PIN = 'd17d5659a8818427d55951d8b0e5807dd21bc9da1ca9d903a56e53f65977804e'
FINAL_PINS = {
    SOURCE: '745f4f2cbc26f733d991eca2998484542a131c47f2d747504194f8ecaca95f0b',
    UNIT: '1c14772b24377b60c96ad2dd2ff01643e85dd91dcb8fb842bdc6ced3714a3339',
    BOUNDARY: '6b4656881c44cec0d60bb53a00919af28fe7873b1b730858058d231164da698f',
}
FINAL_PINS[FIFO_UNIT] = 'be3d4200226336c966f55d28e922bd33d63bbd6974078c3e96cbd7e8ea959e75'
GATE_SCHEMAS = {
    FIFO_UNIT: 'tile8-assoc2-engine-twoentry-fifo-simulation-v1',
    UNIT: 'tile8-assoc2-tagpipe-independent-cache-simulation-v1',
    BOUNDARY: 'tile8-assoc2-tagpipe-independent-boundary-simulation-v1',
}
CACHE = 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v'
ENGINE = 'rtl/experimental/hdmi_camera_fisheye_engine_tile8df8.v'
SCHEMA = 'tile8-assoc2way256-fifo-safe-stop-system-simulation-v1'
CONTRACT_SCHEMA = 'tile8-assoc2way256-fifo-safe-stop-source-contract-v1'
BASE_PINS = {
    ('normal', 'small'): '110f441230504528168cb730e4445354b90164a156154281507a8130e69141e9',
    ('normal', 'native'): '38e2b9e860ec04fa5fecce64ce1a977c7ecb56d435df0ffc44c7387ff4356465',
    ('sustained', 'small'): 'ac7a9838df45c2cc3d5276aa5104ddfc4444d0948fc25dba4b6f98349e7af0b1',
    ('sustained', 'native'): '7cbf1c64700193df6fb29aae911a3c227d2d8a9e62617753655594a5f0124e52',
}
FAMILIES = {
    'normal': 'run_hdmi_camera_fisheye_tile8df8_system_sim',
    'sustained': 'run_hdmi_camera_fisheye_tile8df8_sustained_sim',
}
HELPER_PINS = {
    DIST / ('tools/' + FAMILIES['normal'] + '.py'): 'b2e222d14fc30e64b903ef714aee287c89595bbae3947564630c893e1d46e3d7',
    DIST / ('tools/' + FAMILIES['sustained'] + '.py'): 'a5155524505ce28fa074ea239e778e4a9f865ba9fa912656e9aa3b6e642b38b7',
    DIST / 'tools/run_fill8_rowpipe_cache_sim.py': '7511b32ca0d03b04ffa7126a98dce01d31c701a67f654a553985fb3af0a43885',
    DIST / 'tools/simulation_tools.py': 'cb6f08cf764cce9c088ede89c65ce8f7da0cee447d95015b5685fde18de50a6e',
}
OUTPUTS = ('summary.json', 'frames.csv', 'scans.csv', 'events.csv',
           'performance.csv', 'simulation.log', 'compile-stdout.log',
           'compile-stderr.log', 'elaborate-stdout.log', 'elaborate-stderr.log',
           'simulate-stdout.log', 'simulate-stderr.log')


def require(value, message):
    if not value:
        raise ValueError(message)


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return digest(Path(path).read_bytes())


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')


def ref(path):
    return {'Path': str(Path(path).resolve()), 'SHA256': sha(path)}


def sha_type(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value),
            'exact lowercase SHA256 required')
    return value


class Evidence:
    def __init__(self):
        self.inputs = {}

    def add(self, path, expected=None):
        path = Path(path).resolve()
        actual = sha(path)
        require(expected is None or actual == expected, 'input SHA drift: ' + str(path))
        require(str(path) not in self.inputs or self.inputs[str(path)] == actual,
                'conflicting input SHA: ' + str(path))
        self.inputs[str(path)] = actual
        return ref(path)

    def merge(self, mapping):
        require(isinstance(mapping, dict) and mapping, 'complete nonempty saved input map required')
        for path, expected in mapping.items():
            require(isinstance(path, str) and Path(path).is_absolute(), 'absolute saved input required')
            self.add(path, sha_type(expected))

    def drift(self):
        return [path for path, expected in self.inputs.items()
                if not Path(path).is_file() or sha(path) != expected]


def change_engine(data):
    old, new = b'.INDEX_BITS(8)', b'.INDEX_BITS(10)'
    require(data.count(old) == 1 and new not in data, 'unique original engine INDEX_BITS=8 required')
    return data.replace(old, new)


def change_config(data):
    old, new = b'SIM_CACHE_INDEX_BITS=8', b'SIM_CACHE_INDEX_BITS=10'
    require(data.count(old) == 1 and new not in data, 'unique original observation width=8 required')
    return data.replace(old, new)


def gate_inputs(value):
    mapping = value.get('InputSHA256', value.get('SourceSHA256'))
    require(isinstance(mapping, dict) and mapping, 'actual saved gate source map required')
    return mapping


def gate(path, expected, evidence):
    evidence.add(path, sha_type(expected))
    value = read(path)
    require(value.get('Schema') == GATE_SCHEMAS[path] and
            value.get('Passed') is True and value.get('InputDrift') == [],
            'actual completed no-drift gate required: ' + str(path))
    evidence.merge(gate_inputs(value))
    artifacts = value.get('ArtifactsSHA256', {})
    require(isinstance(artifacts, dict), 'saved gate artifact map must be a dictionary')
    for name, expected_artifact in artifacts.items():
        relative = Path(name)
        require(not relative.is_absolute() and '..' not in relative.parts,
                'gate artifact path escaped')
        evidence.add(path.parent / relative, sha_type(expected_artifact))
    return value


def freeze_contract(args):
    require(not CONTRACT.exists(), 'new contract required; do not replace historical contracts')
    evidence = Evidence()
    evidence.add(Path(__file__))
    require(args.cache_sha == FINAL_PINS[SOURCE] and args.unit_sha == FINAL_PINS[UNIT] and
            args.boundary_sha == FINAL_PINS[BOUNDARY], 'final actual RTL-b/unit-c/boundary pins required')
    evidence.add(SOURCE, sha_type(args.cache_sha))
    evidence.add(ENGINE_SOURCE, ENGINE_PIN)
    evidence.add(BASE_ENGINE_SOURCE, BASE_ENGINE_PIN)
    require(FINAL_PINS[FIFO_UNIT] is not None and args.fifo_unit_sha == FINAL_PINS[FIFO_UNIT],
            'actual completed same-engine FIFO unit pin required')
    for path, pin in HELPER_PINS.items():
        evidence.add(path, pin)
    refs = {}
    for role, path, pin in (('Unit', UNIT, args.unit_sha),
                            ('IndependentBoundary', BOUNDARY, args.boundary_sha),
                            ('FifoUnit', FIFO_UNIT, args.fifo_unit_sha)):
        saved = gate(path, pin, evidence)
        require(gate_inputs(saved).get(str(ENGINE_SOURCE) if role == 'FifoUnit' else str(SOURCE)) ==
                (ENGINE_PIN if role == 'FifoUnit' else args.cache_sha),
                'actual same-file cache SHA missing from ' + role + ' gate')
        refs[role] = ref(path)
    evidence.add(STOP_HELPER, STOP_HELPER_SHA)
    for case, pin in STOP_CASE_PINS.items():
        path = HERE / ('stop-' + case + '-small-a/simulation.json')
        evidence.add(path, pin)
        diagnostic = read(path)
        require(diagnostic['Passed'] is True and diagnostic['InputDrift'] == [] and diagnostic['Case'] == case, 'actual stop diagnosis required')
        require(diagnostic.get('ExpectedOriginalStopFailureActuallyReproduced') is (case == 'old') and diagnostic.get('CompleteSystemPassed') is (case == 'safe'), 'old-failure/new-pass causal gate differs')
        evidence.merge(diagnostic['InputSHA256'])
        for name, digest in diagnostic['ArtifactsSHA256'].items():
            evidence.add(path.parent / name, digest)
        refs['StopDiagnostic_' + case] = ref(path)
    require(not evidence.drift(), 'contract inputs changed during review')
    value = {'Schema': CONTRACT_SCHEMA, 'Passed': True, 'FrozenUTC': utc(),
             'Source': ref(SOURCE), 'EngineSource': ref(ENGINE_SOURCE),
             **refs, 'Runner': ref(Path(__file__)),
             'CacheIndexBits': 10, 'SetIndexBits': 9, 'Ways': 2,
             'CacheCapacityBytes': 262144, 'CapacityAndAssociativityBothChanged': False,
             'CacheOrganizationAndCapacityRetainedFromAssocB': True,
             'InputSHA256': evidence.inputs, 'InputDrift': [],
             'FullSystemSimulationClaimed': False, 'XSimExecutedByContractFreeze': False,
             'NativeEDAExecuted': False, 'HardwareAccessed': False,
             'TimingOrBoardAcceptance': False}
    write(CONTRACT, value)
    print(json.dumps({'Contract': ref(CONTRACT), 'Inputs': len(evidence.inputs)}))


def bind_contract(expected, evidence):
    evidence.add(CONTRACT, sha_type(expected))
    value = read(CONTRACT)
    require(value.get('Schema') == CONTRACT_SCHEMA and value.get('Passed') is True and
            value.get('InputDrift') == [] and value.get('Runner') == ref(Path(__file__)) and
            value.get('Source', {}).get('Path') == str(SOURCE) and
            value.get('Source', {}).get('SHA256') == FINAL_PINS[SOURCE] and
            value.get('EngineSource') == {'Path': str(ENGINE_SOURCE), 'SHA256': ENGINE_PIN} and
            value.get('CacheIndexBits') == 10 and value.get('SetIndexBits') == 9 and
            value.get('Ways') == 2 and value.get('CacheCapacityBytes') == 262144 and
            value.get('TimingOrBoardAcceptance') is False, 'frozen source contract differs')
    evidence.merge(value['InputSHA256'])
    evidence.add(SOURCE, value['Source']['SHA256'])
    evidence.add(ENGINE_SOURCE, ENGINE_PIN)
    for role, path in (('Unit', UNIT), ('IndependentBoundary', BOUNDARY), ('FifoUnit', FIFO_UNIT)):
        require(value[role]['Path'] == str(path), 'actual gate role path differs')
        require(value[role]['SHA256'] == FINAL_PINS[path], 'actual final gate SHA differs')
        saved = gate(path, value[role]['SHA256'], evidence)
        require(gate_inputs(saved).get(str(ENGINE_SOURCE) if role == 'FifoUnit' else str(SOURCE)) ==
                (ENGINE_PIN if role == 'FifoUnit' else value['Source']['SHA256']),
                'gate source identity differs')
    return value


def family(kind, evidence):
    for path, pin in HELPER_PINS.items():
        evidence.add(path, pin)
    sys.path.insert(0, str(REPO / '.venv/Lib/site-packages'))
    sys.path.insert(0, str(DIST / 'tools'))
    return importlib.import_module(FAMILIES[kind])


def baseline(kind, mode, evidence):
    work = BASE / ('system-' + ('sustained-' if kind == 'sustained' else '') + mode + '-a')
    path = work / 'simulation.json'
    evidence.add(path, BASE_PINS[kind, mode])
    value = read(path)
    require(value.get('Passed') is True and value.get('InputDrift') == [] and
            value.get('Mode') == mode and value.get('CacheIndexBits') == 8 and
            value.get('DirectFillCache') is True, 'actual completed original INDEX8 baseline required')
    evidence.merge(value['InputSHA256'])
    for name, pin in value['SourceSHA256'].items():
        evidence.add(DIST / name, pin)
    return work, path, value


def inputs(kind, mode, work, contract, evidence):
    original, baseline_path, saved = baseline(kind, mode, evidence)
    compiled, payloads, closure, changes = [], {}, {}, []
    require(len(saved['CompileSnapshot']) == 22 and CACHE in saved['CompileSnapshot'] and
            ENGINE in saved['CompileSnapshot'], 'original complete 22-source closure required')
    for name, row in saved['CompileSnapshot'].items():
        evidence.add(row['Path'], row['SHA256'])
        data = Path(row['Path']).read_bytes()
        if name == CACHE:
            data = SOURCE.read_bytes()
            require(digest(data) == contract['Source']['SHA256'], 'actual replacement cache changed')
            changes.append(name)
        elif name == ENGINE:
            data = change_engine(data)
            require(data == BASE_ENGINE_SOURCE.read_bytes() and digest(data) == BASE_ENGINE_PIN,
                    'original INDEX10 A-B reference engine differs')
            data = ENGINE_SOURCE.read_bytes()
            require(digest(data) == ENGINE_PIN, 'actual FIFO engine differs')
            changes.append(name)
        if name == 'tests/tb_hdmi_camera_fisheye_tile8df8_sustained.sv':
            require(data.count(OLD_STOP.encode()) == 1, 'original unique stop statement required')
            data = data.replace(OLD_STOP.encode(), SAFE_STOP.encode())
        target = work / 'compiled-sources' / name
        payloads[target] = data
        compiled.append(target)
        closure[name] = digest(data)
    require(changes == [name for name in saved['CompileSnapshot'] if name in (CACHE, ENGINE)],
            'only cache and engine prepared bytes may differ')
    fixture_names = {'config.vh', 'timing.vh'} | {
        stem + str(index) + '.mem' for stem in ('source', 'expected', 'masks', 'crc', 'sourcecrc')
        for index in range(3)}
    require(set(saved['FixtureSHA256']) == fixture_names and
            saved['FixtureSHA256'] == saved['Fixture']['FixtureSHA256'], 'complete 17-fixture oracle required')
    for name, pin in saved['FixtureSHA256'].items():
        evidence.add(original / name, pin)
        data = (original / name).read_bytes()
        payloads[work / name] = change_config(data) if name == 'config.vh' else data
    header_names = {'rtl/video_crc32.vh', 'board/hdmi-camera-fisheye-profile.vh',
                    'board/hdmi-camera-fisheye-radial-table.vh'}
    headers = sorted((original / 'relocated-headers').rglob('*.vh'))
    require({path.relative_to(original / 'relocated-headers').as_posix() for path in headers} ==
            header_names, 'exact three relocated headers required')
    for path in headers:
        name = path.relative_to(original / 'relocated-headers').as_posix()
        evidence.add(path, saved['SourceSHA256'][name])
        data = path.read_bytes()
        payloads[work / path.relative_to(original)] = data
        closure['headers/' + name] = digest(data)
    canonical = {'CacheSourceSHA256': contract['Source']['SHA256'],
                 'SourceContractSHA256': sha(CONTRACT), 'CacheIndexBits': 10,
                 'SetIndexBits': 9, 'Ways': 2, 'PreparedSourceAndHeaderSHA256': closure}
    return saved, baseline_path, payloads, compiled, canonical


def assess_saved(work, saved_baseline, selected_family, mode):
    log = (work / 'simulation.log').read_text(errors='replace')
    require(selected_family.MARKER in log and '$finish called' in log and
            not re.search(r'(?im)^\s*(fatal|error):', log), 'original PASS/finish/assertions failed')
    summary, rows = selected_family.assess(work, saved_baseline['Fixture'], 'directfill')
    with (work / 'performance.csv').open(encoding='utf-8-sig', newline='') as stream:
        performance = list(csv.DictReader(stream))
    reset = selected_family.reset_probe(log, mode)
    return summary, rows, performance, reset


def bind_small(kind, source_closure, contract, selected_family, evidence):
    work = HERE / ('system-' + kind + '-small-b')
    path = work / 'simulation.json'
    receipt_ref = evidence.add(path)
    value = read(path)
    require(value.get('Schema') == SCHEMA and value.get('Passed') is True and
            value.get('Kind') == kind and value.get('Mode') == 'small' and
            value.get('InputDrift') == [] and value.get('SourceContract') == ref(CONTRACT) and
            value.get('SourceClosure') == source_closure and value.get('UnitGate') == contract['Unit'] and
            value.get('IndependentBoundaryGate') == contract['IndependentBoundary'] and
            value.get('CacheSource') == contract['Source'] and value.get('TimingOrBoardAcceptance') is False,
            'completed same-kind/same-canonical-source small gate required')
    for role_ref in (ref(CONTRACT), contract['Source'], contract['Unit'], contract['IndependentBoundary']):
        require(value['InputSHA256'].get(role_ref['Path']) == role_ref['SHA256'],
                'small input map omitted a required source/unit/boundary/contract reference')
    require(value.get('Commands') == [{'Stage': stage, 'ReturnCode': 0}
                                      for stage in ('compile', 'elaborate', 'simulate')],
            'small must have completed all original simulator stages')
    require([item['Stage'] for item in value['StageChecks']] ==
            [prefix + stage for stage in ('compile', 'elaborate', 'simulate')
             for prefix in ('before-', 'after-')] and
            all(item['InputDrift'] == [] for item in value['StageChecks']),
            'small stage input hashes were not preserved')
    require(set(value['OutputSHA256']) == set(OUTPUTS), 'small actual output inventory incomplete')
    evidence.merge(value['InputSHA256'])
    for name in OUTPUTS:
        evidence.add(work / name, value['OutputSHA256'][name])
    original, basepath, base = baseline(kind, 'small', evidence)
    require(value['BaselineReceipt'] == ref(basepath), 'small original baseline differs')
    _, _, payloads, _, small_closure = inputs(kind, 'small', work, contract, evidence)
    require(small_closure == source_closure, 'small/native canonical source closure differs')
    for path, data in payloads.items():
        evidence.add(path, digest(data))
    summary, rows, performance, reset = assess_saved(work, base, selected_family, 'small')
    require((summary, rows, performance, reset) ==
            (value['Summary'], value['Frames'], value['Performance'], value['ResetProbe']),
            'small saved-output CRC/counter/reset replay differs')
    require(reset.get('Exercised') is True, 'small two-edge local-reset probe was not exercised')
    return receipt_ref


def bind_ab_reference(kind, payloads, work, evidence):
    old_work = HERE / ('system-' + kind + '-small-a')
    path = old_work / 'simulation.json'
    value = read(path)
    require(value.get('Passed') is True and value.get('InputDrift') == [], 'actual original FIFO small required')
    evidence.add(path)
    evidence.merge(value['InputSHA256'])
    for name, pin in value['OutputSHA256'].items():
        evidence.add(old_work / name, pin)
    differences = []
    for target, data in payloads.items():
        relative = target.relative_to(work)
        original = old_work / relative
        evidence.add(original)
        old = original.read_bytes()
        if data != old:
            differences.append(relative.as_posix())
            require(kind == 'sustained' and relative.as_posix() == 'compiled-sources/tests/tb_hdmi_camera_fisheye_tile8df8_sustained.sv' and
                    old.count(OLD_STOP.encode()) == 1 and data == old.replace(OLD_STOP.encode(), SAFE_STOP.encode()),
                    'only the final complete-scan stopping stimulus may differ')
    require(len(differences) == int(kind == 'sustained'), 'unexpected safe-stop A-B difference count')
    return ref(path)


def run(args):
    require(args.mode == 'small' or (args.mode == 'native' and args.kind == 'sustained'), 'only sustained native is authorized')
    started = time.monotonic()
    evidence = Evidence()
    evidence.add(Path(__file__))
    contract = bind_contract(args.source_contract_sha, evidence)
    selected_family = family(args.kind, evidence)
    work = HERE / ('system-' + args.kind + '-' + args.mode + '-b')
    require(not work.exists(), 'fresh isolated system experiment directory required')
    base, basepath, payloads, compiled, source_closure = inputs(
        args.kind, args.mode, work, contract, evidence)
    ab_ref = bind_ab_reference(args.kind, payloads, work, evidence)
    small_ref = bind_small(args.kind, source_closure, contract, selected_family, evidence) \
        if args.mode == 'native' else None
    maximum = 300 if args.mode == 'small' else 3600
    # Native budget begins before all actual simulator stages. Source/gate
    # validation is CPU only and does not silently extend an active XSim budget.
    deadline = started + maximum
    require(time.monotonic() < deadline, 'source/gate validation exhausted total experiment budget')
    work.mkdir()
    for path, data in payloads.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(data)
        evidence.add(path, digest(data))
    report = {'Schema': SCHEMA, 'Passed': False, 'Kind': args.kind, 'Mode': args.mode,
              'StartedUTC': utc(), 'SourceContract': ref(CONTRACT),
              'CacheSource': contract['Source'], 'UnitGate': contract['Unit'],
              'IndependentBoundaryGate': contract['IndependentBoundary'],
              'FifoUnitGate': contract['FifoUnit'], 'SmallGate': small_ref,
              'PriorAssocSmallABReference': ab_ref, 'OnlyABPreparedDifference': 'final complete-good-scan stop stimulus only; production cache/engine unchanged',
              'BaselineReceipt': ref(basepath), 'SourceClosure': source_closure,
              'CacheIndexBits': 10, 'SetIndexBits': 9, 'Ways': 2, 'CacheCapacityBytes': 262144,
              'CapacityAndAssociativityBothChanged': False,
              'CacheOrganizationAndCapacityRetainedFromAssocB': True,
              'PreparedLogicChanges': [CACHE, ENGINE],
              'EngineChange': 'INDEX10 retained; one-entry elastic buffer to two-entry occupancy-only-ready FIFO',
              'FixtureChanges': ['config.vh: only SIM_CACHE_INDEX_BITS=8 to 10'],
              'OriginalProduction20OtherSourcesUnchanged': True, 'SustainedBenchOnlyFinalStopStimulusChanged': True,
              'OriginalThreeHeadersAnd16OtherFixturesUnchanged': True,
              'OriginalAllPixelCRCOracleAndOwnershipAssertionsRetained': True, 'OriginalBadDoneAssertionRetained': True,
              'OriginalProductionRTLModified': False, 'MaximumSeconds': maximum,
              'InputSHA256': evidence.inputs, 'InputDrift': [], 'StageChecks': [],
              'Commands': [], 'NativeEDAExecuted': False, 'HardwareAccessed': False,
              'PhysicalSignoff': False, 'TimingOrBoardAcceptance': False,
              'ResearchOnly': True, 'ReleaseAllowed': False,
              'Limits': 'Engine result FIFO only differs from the completed assoc2way256 small A-B reference; cache, INDEX10 configuration, bench, headers, fixtures, pixel oracle and all assertions are unchanged. The original INDEX8 cycle comparison is historical context, not this single-variable A-B control. Small 32x16 results prove finite pixel/ownership/reset/drain behavior, not full-1080 performance, STA or board FPS.'}

    def checkpoint(stage):
        drift = evidence.drift()
        item = {'Stage': stage, 'UTC': utc(), 'InputCount': len(evidence.inputs), 'InputDrift': drift}
        report['StageChecks'].append(item)
        print(json.dumps(item), flush=True)
        require(not drift, 'input changed at stage ' + stage)

    try:
        from run_fill8_rowpipe_cache_sim import run_tool
        from simulation_tools import resolve_vivado_bin
        tool_dir = resolve_vivado_bin(REPO)
        snapshot = 'assoc2way256_fifo_safe_' + args.kind + '_b'
        for executable, argv, stage in (
                ('xvlog.bat', ['--sv', *map(str, compiled)], 'compile'),
                ('xelab.bat', [selected_family.TOP, '-s', snapshot], 'elaborate'),
                ('xsim.bat', [snapshot, '-runall', '-log', 'simulation.log'], 'simulate')):
            checkpoint('before-' + stage)
            run_tool(tool_dir, executable, argv, work, deadline, stage)
            report['Commands'].append({'Stage': stage, 'ReturnCode': 0})
            checkpoint('after-' + stage)
        summary, rows, performance, reset = assess_saved(work, base, selected_family, args.mode)
        report.update(Summary=summary, Frames=rows, Performance=performance, ResetProbe=reset)
        require(len(base['Frames']) == len(rows), 'complete baseline frame count required')
        report['ProcessingCycleComparison'] = [
            {'FrameID': int(new['frame_id']), 'OriginalSourceIndex': old.get('input_source_index'),
             'NewSourceIndex': new.get('input_source_index'),
             'OldCycles': int(old['hardware_process_cycles']),
             'NewCycles': int(new['hardware_process_cycles']),
             'SavedCycles': int(old['hardware_process_cycles']) - int(new['hardware_process_cycles'])}
            for old, new in zip(base['Frames'], rows)]
        report['Passed'] = True
    except BaseException as error:
        report['Error'] = type(error).__name__ + ': ' + str(error)
    report['InputDrift'] = evidence.drift()
    report['Passed'] = report['Passed'] and not report['InputDrift']
    report['OutputSHA256'] = {name: sha(work / name) for name in OUTPUTS if (work / name).is_file()}
    report['Passed'] = report['Passed'] and set(report['OutputSHA256']) == set(OUTPUTS)
    report['ElapsedSeconds'] = round(time.monotonic() - started, 3)
    report['EndedUTC'] = utc()
    write(work / 'simulation.json', report)
    print(json.dumps({key: report.get(key) for key in ('Passed', 'Kind', 'Mode', 'Error',
                     'ElapsedSeconds', 'InputDrift', 'ProcessingCycleComparison')}), flush=True)
    return 0 if report['Passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--freeze-contract', action='store_true')
    action.add_argument('--run', action='store_true')
    parser.add_argument('--cache-sha')
    parser.add_argument('--unit-sha')
    parser.add_argument('--boundary-sha')
    parser.add_argument('--fifo-unit-sha')
    parser.add_argument('--source-contract-sha')
    parser.add_argument('--kind', choices=('normal', 'sustained'))
    parser.add_argument('--mode', choices=('small', 'native'))
    args = parser.parse_args()
    if args.freeze_contract:
        freeze_contract(args)
        return 0
    require(args.kind and args.mode and args.source_contract_sha,
            'kind/mode/exact frozen source-contract SHA required')
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
