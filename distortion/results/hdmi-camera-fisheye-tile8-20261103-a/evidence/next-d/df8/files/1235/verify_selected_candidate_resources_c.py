"""Read-only resource attribution for the isolated selected INDEX8 v3 release.

--draft permits only a clearly labelled completed raw-build resource report.
Without --draft, the real final proof, bit-generation verification and saved
volatile-SRAM scan/program/DONE chain must all exist and bind the same image.
This tool never invokes EDA, P: or hardware, and creates no release authority.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import argparse
import copy
import hashlib
import importlib
import json
import math
import os
import re
import sys
from publication import v3_authority as authority

OUT = Path(__file__).resolve().parent
REPO = OUT.parents[1]
ROOT = REPO / 'distortion'
TOOLS = ROOT / 'tools'
BASELINE_WORK = ROOT / 'work/hdmi-camera-fisheye-tile8-20261103-a'
BASELINE_BIT_SHA256 = '1236d82f113e1ddb1c5e24502ed1aa03e4758db0a7d6ff17bf9216f0fbd0e4f3'
EXPECTED_BASELINE = {'LUT': 13181, 'FF': 13987, 'DRM': 35.5, 'APM': 54}
TARGET = 'hdmi_camera_fisheye_top'
CANDIDATES = {name: ROOT / ('work/hdmi-camera-fisheye-tile8' + name + '-20261103-a')
              for name in ('df8', 'df9tp', 'df9tps4')}
PRIMARY = ('LUT', 'FF', 'DRM', 'APM', 'GPLL', 'USCM')
CLOCKS = ('GPLL', 'USCM', 'BKCL', 'CCS', 'HCKB', 'IOCKB', 'MRCKB', 'PPLL', 'RCKB', 'DDRPHY_IOCLK_DIV')
sys.path[:0] = [str(TOOLS), str(REPO / '.venv/Lib/site-packages')]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def local_io(path):
    """Use extended Windows byte IO while retaining ordinary D:/C: identity."""
    path = Path(path).absolute()
    require(path.drive.upper() != 'P:' and not str(path).startswith('\\\\?\\'),
            'resource identity must use original absolute paths, never P: or extended-path aliases')
    return Path('\\\\?\\' + str(path)) if os.name == 'nt' else path


def sha(path):
    digest = hashlib.sha256()
    with local_io(Path(path)).open('rb') as stream:
        for data in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(data)
    return digest.hexdigest()


def read(path):
    def unique(rows):
        value={}
        for name,item in rows:
            require(name not in value,'duplicate JSON member');value[name]=item
        return value
    return json.loads(local_io(Path(path)).read_text(encoding='utf-8-sig'),object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON: ' + value)))


def ref(path):
    path = Path(path).resolve()
    return {'Path': str(path), 'SHA256': sha(path)}


def add(watched, path, expected=None):
    path = Path(path).absolute()
    io = local_io(path)
    require(path == path.resolve() and io.is_file(), 'canonical actual resource input required: ' + str(path))
    if expected is not None:
        require(isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected), 'actual SHA256 required')
    if str(path) in watched:
        require(expected is None or watched[str(path)] == expected, 'conflicting resource identity: ' + str(path))
        return path
    actual = sha(path)
    require(expected is None or actual == expected, 'resource evidence SHA differs: ' + str(path))
    watched[str(path)] = actual
    return path


def merge(watched, inputs):
    for path, digest in inputs.items():
        add(watched, path, digest)


def binding(watched, value):
    require(isinstance(value, dict) and set(value) == {'Path', 'SHA256'}, 'exact actual Path/SHA256 binding required')
    return add(watched, value['Path'], value['SHA256'])


def parse_usage(text):
    require(text.count('Device Utilization Summary :') == 1, 'one actual device resource summary required')
    table = text.split('Device Utilization Summary :', 1)[1]
    result = {}
    parent = None
    for line in table.splitlines():
        match = re.fullmatch(r'\|\s*(.*?)\s*\|\s*([0-9]+(?:\.[0-9]+)?)\s*\|\s*([0-9]+(?:\.[0-9]+)?)\s*\|\s*([0-9]+(?:\.[0-9]+)?)\s*\|?\s*', line)
        if not match:
            if result and line.startswith('+'):
                break
            continue
        label, used, capacity, displayed = match.groups()
        if label.startswith('Use of '):
            parent = label[7:]
            key = parent
        else:
            require(parent is not None, 'orphan resource subcategory')
            key = parent + '.' + label
        values = list(map(float, (used, capacity, displayed)))
        require(key not in result and all(math.isfinite(n) for n in values)
                and 0 <= values[0] <= values[1] and 0 <= values[2] <= 100,
                'duplicate or invalid resource category: ' + key)
        result[key] = {'Used': values[0], 'Capacity': values[1], 'ToolDisplayedPercent': values[2]}
    for kind in ('LUT', 'FF'):
        a, b = (result.get(f'{family}.{kind}') for family in ('CLMA', 'CLMS'))
        require(a is not None and b is not None, 'both CLMA/CLMS resource totals required')
        result[kind] = {'Used': a['Used'] + b['Used'], 'Capacity': a['Capacity'] + b['Capacity']}
    require(all(name in result for name in (*PRIMARY, *CLOCKS)), 'complete logic/RAM/APM/clock resource table required')
    require(all(result[k]['Capacity'] == v for k, v in {'LUT': 66600, 'FF': 133200, 'DRM': 155, 'APM': 240}.items()),
            'resource report belongs to another device capacity')
    require(all(result[k]['Used'].is_integer() for k in (*PRIMARY, *CLOCKS) if k != 'DRM')
            and (2 * result['DRM']['Used']).is_integer(), 'actual resource units must be integral or DRM half blocks')
    for row in result.values():
        row['PercentExact'] = 100 * row['Used'] / row['Capacity'] if row['Capacity'] else 0
    return result


def parse_rur_top(text):
    require(text.count('Device Utilization Summary Of Each Module:') == 1, 'one routed hierarchy resource table required')
    table = text.split('Device Utilization Summary Of Each Module:', 1)[1]
    headings = None
    selected = []
    for line in table.splitlines():
        if line.startswith('| Module Inst Name'):
            headings = [field.strip() for field in line.strip().strip('|').split('|')]
        elif line.startswith('| ' + TARGET + ' '):
            fields = [field.strip() for field in line.strip().strip('|').split('|')]
            require(headings is not None and len(fields) == len(headings), 'complete top resource row required')
            selected.append(dict(zip(headings[1:], map(float, fields[1:]))))
    require(len(selected) == 1 and all(k in selected[0] for k in PRIMARY), 'one actual full top resource row required')
    return selected[0]


def compare_report_totals(optimize, routed_top):
    require(all(optimize[k]['Used'] == routed_top[k] for k in PRIMARY),
            'routed module and actual Route Optimize logic/RAM/APM/clock totals differ')


def parse_pins(text, expected):
    active = {}
    for line in text.splitlines():
        fields = line.strip().split('|')
        require(len(fields) == 7, 'unparsed actual route-optimize pin report row')
        pad, _, _, _, port, direction, fixed = fields
        if not port:
            continue
        require(port not in active and fixed == 'YES', 'duplicate/unfixed route-optimize port')
        active[port] = {'LOC': pad, 'DIRECTION': direction.upper()}
    require(set(active) == set(expected) and len(active) == 144 and all(
        active[name] == {key: row[key] for key in ('LOC', 'DIRECTION')} for name, row in expected.items()),
        'actual route-optimize pin identities differ from selected completed build')
    return active


def primitive_counts(text):
    require(re.findall(r'(?m)^module\s+(\w+)', text) == [TARGET], 'one flat current native top required')
    pattern = r'(?m)^\s*(?:\(\*[^\r\n]*?\*\)\s*)*(V_[A-Za-z0-9_]+)\s+(?:/\*[^\r\n]*?\*/\s*)?(?=#\(|[\\A-Za-z_])'
    counts = dict(sorted(Counter(re.findall(pattern, text)).items()))
    require(counts and all(type(n) is int and n > 0 for n in counts.values()), 'actual primitive inventory required')
    return counts


def check_native_totals(counts, resources):
    observed = {'FF': counts.get('V_FFSYN', 0) + counts.get('V_FFASYN', 0),
                'DRM': counts.get('V_DRM36K_E1', 0) + counts.get('V_DRM18K_E1', 0) / 2,
                'APM': counts.get('V_APM_E2', 0), 'GPLL': counts.get('V_GPLL', 0), 'USCM': counts.get('V_USCM', 0)}
    require(all(resources[k]['Used'] == n for k, n in observed.items()),
            'native FF/DRM/APM/PLL/buffer counts differ from Route Optimize usage')
    return observed


def same_primitives(before, after):
    require(bool(before) and before == after, 'per-class native primitive counts changed')


def final_flags(value):
    require(value.get('Target') == TARGET and all(value.get(key) is True for key in
        ('Passed', 'STAAllTenPassed', 'NetlistEquivalent', 'AllFFPlacementsEquivalent', 'RoutesUnchanged')),
        'actual final graph/FF placement/routes/all-ten physical proof required')


def sram_flags(value):
    require(all(value.get(key) is True for key in ('Passed', 'HardwareAccessed', 'ProgrammingAttempted',
        'DoneConfirmed', 'ExpectedDeviceAndIDConfirmed', 'UserConfirmedBoardPowered', 'UserNotifiedBeforeExecution'))
        and value.get('FlashWritten') is False and value.get('CleanupErrors') == [] and not value.get('Error'),
        'clean actual notified volatile-SRAM scan/program/DONE receipt required')


def baseline(watched):
    work = BASELINE_WORK
    log = add(watched, work / 'build-a/place_route/run_route_optimize.log')
    rur = add(watched, work / ('build-a/place_route/' + TARGET + '.rur'))
    prt = add(watched, work / ('build-a/place_route/' + TARGET + '_prr_route_optimize.prt'))
    resources = parse_usage(local_io(log).read_text(encoding='gb18030'))
    compare_report_totals(resources, parse_rur_top(local_io(rur).read_text(encoding='gb18030')))
    require(all(resources[k]['Used'] == n for k, n in EXPECTED_BASELINE.items()), 'published tile8 resource baseline changed')
    plan_path = add(watched, work / 'build-a/plan.json')
    parse_pins(local_io(prt).read_text(encoding='gb18030'), read(plan_path)['Pins']['PinInventory'])
    resource_path = add(watched, work / 'resource-report-a.json')
    old = read(resource_path)
    require(all(old['Resources'][k]['Used'] == resources[k]['Used'] for k in PRIMARY), 'published resource report differs from actual tables')
    proof_path = add(watched, work / 'final-proof-v2-a.json')
    proof = read(proof_path)
    final_flags(proof)
    bit_path = add(watched, work / ('bit-v2-a/generate_bitstream/' + TARGET + '.sbit'), BASELINE_BIT_SHA256)
    bit_plan = read(add(watched, work / 'bit-v2-a/bitstream-plan.json'))
    require(bit_plan['PhysicalProof'] == ref(proof_path) and bit_plan['FinalADF'] == proof['FinalADF'],
            'published baseline final proof/bit identity differs')
    program_plan_path = add(watched, work / 'program-v2-a/plan.json')
    program_plan = read(program_plan_path)
    receipt_path = add(watched, work / 'program-v2-a/receipt.json')
    receipt = read(receipt_path)
    sram_flags(receipt)
    require(receipt['PlanSHA256'] == sha(program_plan_path) and receipt['Bitstream']['SHA256'] == BASELINE_BIT_SHA256
            and program_plan['Bitstream'] == receipt['Bitstream'] and Path(receipt['Bitstream']['Path']) == bit_path
            and receipt['FinalADFSHA256'] == proof['FinalADF']['SHA256'], 'published baseline SRAM identity differs')
    hw = importlib.import_module('program_native_raw')
    add(watched, hw.__file__)
    for name in ('scan.out.log', 'program.out.log'):
        add(watched, work / 'program-v2-a' / name, receipt['Logs'][name])
    hw._check_scan((local_io(work / 'program-v2-a/scan.out.log')).read_text(encoding='utf-8', errors='replace'))
    hw._check_program((local_io(work / 'program-v2-a/program.out.log')).read_text(encoding='utf-8', errors='replace'))
    return {'Published15FPSBaseline': True, 'Bitstream': ref(bit_path), 'ProgramReceipt': ref(receipt_path),
            'FinalPhysicalProof': ref(proof_path), 'Resources': {k: resources[k] for k in (*PRIMARY, *CLOCKS)},
            'OriginalResourceReport': ref(resource_path), 'ActualTablesAndSavedSRAMIdentityRehashed': True,
            'ActualBaselineScanAndPostProgramDONELogParsed': True,
            'BaselineFullPhysicalProofRecomputedByThisTool': False}


def candidate_path(value):
    aliases = {'8': 'df8', '9tp': 'df9tp', 's4': 'df9tps4', '9tps4': 'df9tps4',
               'df8': 'df8', 'df9tp': 'df9tp', 'df9tps4': 'df9tps4'}
    if value in aliases:
        name = aliases[value]
        return name, CANDIDATES[name]
    path = Path(value).absolute()
    local_io(path)
    path = path.resolve()
    matches = [name for name, work in CANDIDATES.items() if path == work]
    require(len(matches) == 1, 'only this run own df8, df9tp or df9tps4 candidate work is allowed')
    return matches[0], path


def native_artifact(watched, receipt_path, value, basename):
    names = [name for name in value['Artifacts'] if Path(name).name == basename]
    require(len(names) == 1, 'one actual native artifact required: ' + basename)
    relative = Path(names[0])
    require(not relative.is_absolute() and '..' not in relative.parts, 'native artifact escaped actual work')
    return add(watched, receipt_path.parent / relative, value['Artifacts'][names[0]])


def check_saved_raw_identity(plan, receipt):
    require(plan.get('Schema') == 'hdmi-camera-fisheye-tile8df8-build-v1' and plan.get('Target') == TARGET and
            receipt.get('Schema') == 'hdmi-camera-fisheye-tile8df8-build-execution-v1' and receipt.get('Target') == TARGET and
            receipt.get('BuildCompleted') is True and receipt.get('EDAExecuted') is True and receipt.get('ExitCode') == 0 and
            receipt.get('InputDrift') == [] and receipt.get('NativeErrors') == [] and receipt.get('TimedOut') is False,
            'completed actual saved INDEX8 raw build required')


def saved_v3_release(work, watched):
    """Independently bind saved public results; never call their producers."""
    from publication import assemble_stage_d_c as assembly
    add(watched, assembly.__file__)
    authority.pins_ready()
    paths = {key: work / name for key, name in {
        'ProviderManifest':'physical-release-provider-source-manifest-v3-a.json',
        'RootSourceReview':'root-independent-complete-source-review-v3-a.json',
        'OriginalProviderManifest':'physical-release-provider-source-manifest-a.json',
        'OriginalRootSourceReview':'root-independent-complete-source-review-a.json',
        'FinalProof':'final-proof-v3-a.json','BitVerification':'bit-v3-a/verification.json',
        'BitPlan':'bit-v3-a/bitstream-plan.json','BitExecution':'bit-v3-a/execution-result.json',
        'PreBitGate':'bit-v3-a/pre-bit-audit.json','ReleaseGO':'physical-to-release-v3-go-a.json',
        'PrewarmAuthority':'release-prewarm-authority-v3-a.json',
        'PrewarmWrapper':'release-prewarm-wrapper-source-manifest-v3-a.json',
        'PrewarmTransition':'release-prewarm-authorized-transition-v3-a.json',
        'ReleaseInputManifest':'release-input-manifest-v3-a.json',
        'RequestSnapshot':'release-prewarm-bit-request-v3-a.snapshot.json',
        'RequestComparison':'release-prewarm-recreated-request-check-v3-a.json',
        'NormalNative':'system-native-a/simulation.json'}.items()}
    # These three exact roles are owned by the preserved existing release input
    # manifest; their original paths must agree with the actual seven-field plan.
    for key, path in paths.items(): add(watched, path)
    data = {key: read(path) for key, path in paths.items()}
    authority.check_source_freeze(ref(paths['ProviderManifest']),ref(paths['RootSourceReview']),
        ref(paths['PrewarmWrapper']),ref(paths['OriginalProviderManifest']),ref(paths['OriginalRootSourceReview']))
    manifest, peer = data['ProviderManifest'], data['RootSourceReview']
    require(manifest.get('Schema') == authority.PREFIX + 'provider-source-manifest-v1' and
        manifest.get('ProviderRevision') == peer.get('ProviderRevision') == authority.REVISION and
        manifest.get('Passed') is True and peer.get('Passed') is True and peer.get('IndependentPeerReviewPerformed') is True and
        manifest.get('InputDrift') == peer.get('InputDrift') == [] and
        manifest.get('PriorPhysicalTimingOrAcceptanceInherited') is False and peer.get('PhysicalAcceptanceInherited') is False,
        'actual pinned v3 source freeze/independent review required')
    for original in ('OriginalProviderManifest','OriginalRootSourceReview'):
        require(manifest['InputSHA256'].get(str(paths[original])) == sha(paths[original]) and
            peer['InputSHA256'].get(str(paths[original])) == sha(paths[original]), 'both v3 freezes must bind original provenance')
    for value in (manifest,peer):merge(watched,value['InputSHA256'])
    proof, verified, plan, execution, gate = (data[k] for k in ('FinalProof','BitVerification','BitPlan','BitExecution','PreBitGate'))
    require(proof.get('Schema') == authority.PREFIX + 'final-physical-proof-v1' and
        proof.get('NativeMaxPaths') == 10000 and proof.get('DataCDC',{}).get('Missing') == [] and
        proof.get('DataCDC',{}).get('Violations') == [], 'own full v3 native/CDC final proof required')
    assembly.flags(proof, assembly.PHYSICAL_FLAGS, 'complete saved v3 final proof')
    assembly.check_bit_execution(execution)
    require(plan.get('Schema') == authority.PREFIX + 'bitstream-plan-v1' and plan.get('Target') == TARGET and
        verified.get('Schema') == authority.PREFIX + 'bitstream-verification-v1' and verified.get('Verified') is True and
        verified.get('Target') == TARGET and verified['FinalADFSHA256'] == plan['FinalADFSHA256'] == proof['FinalADF']['SHA256'],
        'same actual v3 plan/proof/public verification required')
    assembly.flags(verified['FreshSTA'], ('STAAllTenPassed','ClockAndSummaryIdentityPreserved','AllExceptionPathsPreserved'),'saved fresh STA')
    assembly.flags(verified['GenerationEvidence'], assembly.GENERATION_FLAGS, 'saved actual generation')
    require(verified['ActualEvents'] == assembly.EXPECTED_EVENTS and gate.get('Schema') == authority.PREFIX + 'pre-bit-gate-v1' and
        gate.get('GatePassed') is True and gate['Checks'] == verified['FreshSTA'] and gate['FinalADFSHA256'] == verified['FinalADFSHA256'] and
        execution['PlanSHA256'] == sha(paths['BitPlan']) and execution['FinalADFSHA256'] == verified['FinalADFSHA256'] and
        datetime.fromisoformat(execution['StartedUTC']) <= datetime.fromisoformat(gate['CheckedUTC']) <= datetime.fromisoformat(execution['FinishedUTC']),
        'saved actual fresh gate/generation/chronology differs')
    bit_provider=TOOLS/'hdmi_camera_fisheye_tile8df8v3_bitstream.py'
    add(watched,bit_provider,manifest['InputSHA256'][str(bit_provider)])
    require(execution['ExecutorSHA256'] == sha(bit_provider), 'saved bit executor differs from v3 freeze')
    bit_path=binding(watched,{'Path':verified['Bitstream']['Path'],'SHA256':verified['Bitstream']['SHA256']})
    require(bit_path == work/'bit-v3-a/generate_bitstream/hdmi_camera_fisheye_top.sbit' and
        verified['Bitstream']['Bytes'] == 3791112 and verified['Bitstream']['SHA256'] != BASELINE_BIT_SHA256 and
        assembly.parse_bit_header(local_io(bit_path).read_bytes()) == verified['Bitstream']['Header'], 'actual selected v3 bit bytes/header differ')
    for role in ('MapperSimulation','IOSimulation','Profile'):
        paths[role]=binding(watched,plan[role])
    def append(path,expected=None,reason=None):return add(watched,path,expected)
    def bound(value,reason=None):return binding(watched,value)
    assembly.check_release_identity(work,paths,data,append,bound,None)
    for role in ('FinalProof','BitPlan'):
        merge(watched,data[role]['InputSHA256'])
    for name,h in gate['EvidenceSHA256'].items():
        relative=Path(name);require(not relative.is_absolute() and '..' not in relative.parts,'saved gate artifact escaped')
        add(watched,paths['PreBitGate'].parent/relative,h)
    require(verified['EvidenceSHA256']['execution-result.json'] == sha(paths['BitExecution']) and
        verified['EvidenceSHA256']['pre-bit-audit.json'] == sha(paths['PreBitGate']), 'saved public verification core artifacts differ')
    return proof,verified,plan,manifest,assembly,paths,execution


def attribute(candidate, work, draft):
    require(candidate == 'df8' and work == CANDIDATES['df8'], 'only selected INDEX8 raw source/v3 final release allowed')
    if not draft:
        authority.pins_ready()
    watched = {}
    add(watched, __file__)
    add(watched, authority.__file__)
    published = baseline(watched)
    prefix = 'hdmi_camera_fisheye_tile8' + candidate
    plan_path = add(watched, work / 'build-a/plan.json')
    receipt_path = add(watched, work / 'build-a/execution-result.json')
    plan, receipt = read(plan_path), read(receipt_path)
    check_saved_raw_identity(plan, receipt)
    require(receipt['PlanSHA256'] == sha(plan_path) and receipt.get('Cleanup',{}).get('Complete') is True,
            'saved actual raw plan/clean completion differs')
    merge(watched, plan['InputSHA256'])
    merge(watched, plan['PreparedSHA256'])
    build_adf = add(watched, receipt['ADF'], receipt['ADFSHA256'])
    require(build_adf == work / ('build-a/place_route/' + TARGET + '_pnr.adf'), 'resource source ADF is another candidate')
    log = add(watched, work / 'build-a/place_route/run_route_optimize.log',
              receipt['NativeLogSHA256']['place_route/run_route_optimize.log'])
    text = local_io(log).read_text(encoding='gb18030')
    require("Design '" + TARGET + "' has been routed successfully." in text and
            'Action route_optimize: Export DB successfully.' in text, 'actual own Route Optimize did not finish')
    rur = add(watched, work / ('build-a/place_route/' + TARGET + '.rur'))
    prt = add(watched, work / ('build-a/place_route/' + TARGET + '_prr_route_optimize.prt'))
    resources = parse_usage(text)
    compare_report_totals(resources, parse_rur_top(local_io(rur).read_text(encoding='gb18030')))
    pins = parse_pins(local_io(prt).read_text(encoding='gb18030'), plan['Pins']['PinInventory'])
    chain = {'BuildPlan': ref(plan_path), 'BuildReceipt': ref(receipt_path), 'SourceADF': ref(build_adf),
             'RouteOptimizeLog': ref(log), 'RoutedResourceTable': ref(rur), 'RouteOptimizePinReport': ref(prt),
             'ActualPinCount': len(pins), 'ResourceStage': 'completed own raw build Route Optimize',
             'RURMayPrecedeOptimizeCLMSitePacking': True, 'OptimizeLogIsAuthoritativeResourceTable': True}
    native_counts = None
    if not draft:
        proof, checked, bit_plan, manifest, assembly, release_paths, bit_execution = saved_v3_release(work,watched)
        audit = importlib.import_module(prefix + '_audit')
        add(watched,audit.__file__,manifest['InputSHA256'][str(Path(audit.__file__).resolve())])
        proof_path = release_paths['FinalProof']
        final_flags(proof)
        bit_work = work / 'bit-v3-a'
        require(proof['BuildPlan'] == ref(plan_path)
                and bit_plan['BuildPlan'] == ref(plan_path) and bit_plan['PhysicalProof'] == ref(proof_path)
                and bit_plan['FinalADF'] == proof['FinalADF']
                and checked['FinalADFSHA256'] == proof['FinalADF']['SHA256'],
                'raw build, actual final physical proof and bit generation are not the same image')
        for name, digest in checked['EvidenceSHA256'].items():
            relative = Path(name)
            require(not relative.is_absolute() and '..' not in relative.parts, 'verified bit evidence escaped work')
            add(watched, bit_work / relative, digest)
        app_path = binding(watched, proof['Application'])
        app = read(app_path)
        require(app_path == work/'physical-v3-a/result.json' and
                app.get('Schema') == authority.PREFIX+'physical-application-v1' and app.get('ExecutionPassed') is True and
                app.get('TimedOut') is False and app.get('InputDrift') == [] and app.get('Cleanup',{}).get('Complete') is True and
                app['BuildPlan'] == ref(plan_path) and app['SourceADF'] == ref(build_adf)
                and app['ResultADF'] == proof['FinalADF'] and app['RoutesAndPlacementUnchanged'] is True,
                'actual resource source ADF differs from applied final candidate')
        source_net = binding(watched, app['NativeNetlist'])
        raw_export_path = binding(watched, app['ExportReceipt'])
        raw_export = read(raw_export_path)
        require(raw_export['SourceADFSHA256'] == receipt['ADFSHA256'] and
                native_artifact(watched, raw_export_path, raw_export, TARGET + '_sim.v') == source_net,
                'resource source netlist was exported from another raw ADF')
        final_export_path = binding(watched, proof['FinalExport'])
        final_export = read(final_export_path)
        require(final_export['SourceADFSHA256'] == proof['FinalADF']['SHA256'], 'final netlist belongs to another ADF')
        final_net = native_artifact(watched, final_export_path, final_export, TARGET + '_sim.v')
        before_text = local_io(source_net).read_text(encoding='utf-8-sig')
        after_text = local_io(final_net).read_text(encoding='utf-8-sig')
        before = audit.functional(before_text)
        after = audit.functional(after_text)
        require(before == after and before['FFPlacement'] == after['FFPlacement'],
                'independent functional/declaration/FF placement comparison changed')
        native_counts = primitive_counts(before_text)
        final_counts = primitive_counts(after_text)
        same_primitives(native_counts, final_counts)
        require(native_counts == dict(sorted(Counter(cell['Primitive'] for cell in before['Cells'].values()).items()))
                and final_counts == dict(sorted(Counter(cell['Primitive'] for cell in after['Cells'].values()).items())),
                'independent complete primitive inventory differs from parsed actual graph')
        check_native_totals(native_counts, resources)
        semantics = importlib.import_module('camera720_stats_delay_reset_apply')
        add(watched,semantics.__file__,manifest['InputSHA256'][str(Path(semantics.__file__).resolve())])
        source_routes = binding(watched, app['RouteDump'])
        final_route_path = binding(watched, proof['FinalRoute'])
        final_route = read(final_route_path)
        require(final_route['SourceADFSHA256'] == proof['FinalADF']['SHA256'], 'final route dump belongs to another ADF')
        final_routes = native_artifact(watched, final_route_path, final_route, 'route-dump.txt')
        route_equivalence = semantics.compare_routes(source_routes, final_routes)
        require(route_equivalence.get('AllNETANNOTATEIdentical') is True and
                route_equivalence.get('AllNonConstraintNonRouteSemanticTokensIdentical') is True,
                'independent native route/placement annotations differ')
        sram_plan_path = add(watched, work / 'program-v3-a/plan.json')
        sram_plan = read(sram_plan_path)
        sram_receipt_path = add(watched, work / 'program-v3-a/receipt.json')
        sram = read(sram_receipt_path)
        require(sram_plan.get('Schema') == authority.PREFIX+'sram-plan-v1' and sram.get('Schema') == authority.PREFIX+'sram-execution-v1',
                'own SRAM namespace required')
        sram_flags(sram)
        program_provider=add(watched,TOOLS/'hdmi_camera_fisheye_tile8df8v3_program.py',
                             manifest['InputSHA256'][str(TOOLS/'hdmi_camera_fisheye_tile8df8v3_program.py')])
        require(sram['PlanSHA256'] == sha(sram_plan_path) and sram['ExecutorSHA256'] == sha(program_provider)
                and sram_plan['Operation'] == 'volatile_sram_only' and sram_plan['ExpectedDevice'] == 'PG2L100H'
                and sram_plan['ExpectedDeviceID'] == '0x00602899'
                and sram_plan['BitstreamWorkDirectory'] == str(bit_work)
                and sram_plan['Bitstream'] == sram['Bitstream'] == checked['Bitstream']
                and sram['FinalADFSHA256'] == sram_plan['FinalADFSHA256'] == proof['FinalADF']['SHA256'],
                'actual SRAM plan/executor/bit/final ADF identity chain differs')
        merge(watched, sram_plan['BoundInputSHA256'])
        assembly.check_program_identity(sram_plan,sram,work,Path(checked['Bitstream']['Path']),sha(program_provider),
                                       lambda value,reason=None:binding(watched,value))
        for name, digest in sram['Logs'].items():
            add(watched, sram_receipt_path.parent / name, digest)
        assembly.check_scan_program(local_io(sram_receipt_path.parent/'scan.out.log').read_text(encoding='utf-8',errors='replace'),
                                    local_io(sram_receipt_path.parent/'program.out.log').read_text(encoding='utf-8',errors='replace'))
        require(datetime.fromisoformat(sram['StartedUTC']) >= datetime.fromisoformat(bit_execution['FinishedUTC'])
                and datetime.fromisoformat(sram['EndedUTC']) >= datetime.fromisoformat(sram['StartedUTC']),
                'actual programming must follow this bit generation')
        chain.update(FinalPhysicalProof=ref(proof_path), PhysicalApplication=ref(app_path),
                     FinalADF=proof['FinalADF'], SourceNativeNetlist=ref(source_net), FinalNativeNetlist=ref(final_net),
                     PerPrimitiveCountsEquivalent=True, FunctionalGraphAndFFPlacementsIndependentlyEqual=True,
                     RouteTreesAndPlacementsIndependentlyEqual=True, Bitstream=checked['Bitstream'],
                     SavedPublicVerificationChecked=True, BitVerificationPublicAPIRecomputedByThisTool=False,
                     SavedPublicBitVerification=ref(release_paths['BitVerification']),ProgramPlan=ref(sram_plan_path),
                     SRAMReceipt=ref(sram_receipt_path), ActualProgramDeviceAndPostProgramDONELogsChecked=True,
                     BitwiseConfigurationReadbackPerformed=sram.get('BitwiseConfigurationReadbackPerformed', False))
        for module in (audit, semantics):
            add(watched, module.__file__)
    delta = {key: {'CandidateUsed': resources[key]['Used'], 'PublishedTile8Used': published['Resources'][key]['Used'],
                   'Delta': resources[key]['Used'] - published['Resources'][key]['Used'],
                   'Capacity': resources[key]['Capacity']} for key in PRIMARY}
    require(all(sha(path) == digest for path, digest in watched.items()), 'resource attribution evidence changed during verification')
    return {'Schema': 'tile8-next15h-independent-resource-attribution-v3', 'Candidate': candidate,
            'ReleaseFamily':authority.FAMILY,'ProviderRevision':authority.REVISION,
            'SavedPublicVerificationChecked':not draft,'PublicPhysicalOrBitAPIRecomputedByThisTool':False,
            'CandidateWork': str(work), 'CreatedUTC': datetime.now(timezone.utc).isoformat(),
            'Draft': draft, 'ExtractionPassed': True, 'FinalAttributionPassed': not draft,
            'OnBoardResourceBinding': not draft,
            'Label': '未上板：仅本候选已完成 raw Route Optimize 构建资源' if draft else '资源已绑定本候选实际 SRAM 下载位流',
            'Resources': {key: resources[key] for key in (*PRIMARY, *CLOCKS)},
            'NativePrimitiveCounts': native_counts, 'EvidenceChain': chain,
            'Published15FPSBaseline': published, 'ComparisonToPublishedTile8': delta,
            'EDAExecutedByThisTool': False, 'HardwareAccessedByThisTool': False, 'PDriveAccessed': False,
            'NewFPSClaimed': False, 'HardwareReleaseAuthorizedByThisTool': False,
            'InputDrift': [], 'InputSHA256': dict(sorted(watched.items()))}


def self_test():
    watched = {}
    add(watched, __file__)
    known = baseline(watched)
    text = (local_io(BASELINE_WORK / 'build-a/place_route/run_route_optimize.log')).read_text(encoding='gb18030')
    usage = parse_usage(text)
    cases = []

    def rejects(name, fn):
        try:
            fn()
        except ValueError:
            cases.append({'Name': name, 'RejectedAsRequired': True})
        else:
            raise AssertionError('negative case was accepted: ' + name)

    rejects('other_failed_df9_work_forbidden', lambda: candidate_path(str(ROOT / 'work/hdmi-camera-fisheye-tile8df9-20261103-a')))
    rejects('duplicate_resource_table', lambda: parse_usage(text + '\nDevice Utilization Summary :\n'))
    rejects('missing_drm_usage', lambda: parse_usage('\n'.join(line for line in text.splitlines() if 'Use of DRM ' not in line)))
    rejects('rur_totals_changed', lambda: compare_report_totals(usage, {key: usage[key]['Used'] + (key == 'LUT') for key in PRIMARY}))
    for field in ('NetlistEquivalent', 'AllFFPlacementsEquivalent', 'RoutesUnchanged', 'STAAllTenPassed'):
        proof = {'Target': TARGET, **{key: True for key in ('Passed', 'NetlistEquivalent', 'AllFFPlacementsEquivalent', 'RoutesUnchanged', 'STAAllTenPassed')}}
        proof[field] = False
        rejects('incomplete_final_' + field, lambda proof=proof: final_flags(proof))
    rejects('primitive_class_changed', lambda: same_primitives({'V_FFSYN': 2}, {'V_FFASYN': 2}))
    rejects('primitive_count_changed', lambda: same_primitives({'V_DRM18K_E1': 2}, {'V_DRM18K_E1': 1}))
    rejects('missing_actual_done', lambda: sram_flags({'Passed': True}))
    rejects('actual_published_bit_pin_changed', lambda: add(watched,
        BASELINE_WORK / ('bit-v2-a/generate_bitstream/' + TARGET + '.sbit'), '0' * 64))
    bad = copy.deepcopy(usage)
    bad['DRM']['Used'] += .5
    source_net = add(watched, BASELINE_WORK / ('export-a/generate_netlist/' + TARGET + '_sim.v'))
    counts = primitive_counts(local_io(source_net).read_text(encoding='utf-8-sig'))
    check_native_totals(counts, usage)
    rejects('native_drm_half_count_mismatch', lambda: check_native_totals(counts, bad))
    long_path = long_path_self_test(watched, rejects)
    require(all(sha(path) == digest for path, digest in watched.items()), 'baseline self-test read drift')
    return {'Schema': 'tile8-next15h-resource-verifier-selftest-v3', 'Passed': True, 'SelfTestOnly': True,
            'CandidateAccepted': False, 'OnBoardResourceBindingCreated': False,
            'RealPublishedBaselineReadonlyCheck': known, 'RealBaselineNativePrimitiveCounts': counts,
            'LongPathByteIOSelfTest': long_path,
            'NegativeCases': cases, 'NegativeCasesPassed': len(cases), 'EDAExecuted': False,
            'HardwareAccessed': False, 'PDriveAccessed': False, 'InputSHA256': watched}


def long_path_self_test(watched, rejects):
    """Actual frozen 269-byte vendor input plus a persistent >400-character fixture."""
    plan_path = CANDIDATES['df9tps4'] / 'build-a/plan.json'
    actual = None
    if local_io(plan_path).is_file():
        plan = read(add(watched, plan_path))
        rows = [row for row in plan['CompiledInputs'] if len(row['CompiledPath']) > 260]
        require(bool(rows), 'real S4 compiled long-path input required by this self-test')
        row = max(rows, key=lambda item: len(item['CompiledPath']))
        path = add(watched, row['CompiledPath'], row['CompiledSHA256'])
        data = local_io(path).read_bytes()
        require(hashlib.sha256(data).hexdigest() == row['CompiledSHA256']
                and plan['PreparedSHA256'].get(str(path)) == row['CompiledSHA256'],
                'real S4 prepared long-path bytes changed')
        actual = {'CompiledInput': ref(path), 'IdentityPathLength': len(str(path)),
                  'Source': row['Source'], 'CompleteBytesRead': len(data), 'S4Plan': ref(plan_path),
                  'CandidatePhysicalOrBitOrHardwareAccepted': False}
    fixture = OUT / 'resource-verifier-c-longpath-fixture-a' / ('nested_' + 'a' * 109) / ('nested_' + 'b' * 109) / ('nested_' + 'c' * 109) / 'fixture.json'
    payload = b'{"LongPathFixture":true,"BitAcceptanceClaimed":false}\n'
    require(len(str(fixture)) > 400 and fixture.resolve().is_relative_to(OUT),
            'own output directory bounded real long-path fixture required')
    if not local_io(fixture).is_file():
        local_io(fixture.parent).mkdir(parents=True, exist_ok=True)
        with local_io(fixture).open('xb') as stream:
            stream.write(payload)
    digest = hashlib.sha256(payload).hexdigest()
    add(watched, fixture, digest)
    require(read(fixture) == {'LongPathFixture': True, 'BitAcceptanceClaimed': False}
            and local_io(fixture).read_bytes() == payload
            and str(fixture) in watched and not any(name.startswith('\\\\?\\') for name in watched),
            'extended byte IO must retain canonical ordinary path identity')
    rejects('longpath_payload_wrong_sha', lambda: add({}, fixture, '0' * 64))
    rejects('longpath_cached_identity_conflict', lambda: add(watched, fixture, '0' * 64))
    rejects('longpath_missing_input', lambda: add({}, fixture.with_name('missing.json')))
    if os.name == 'nt':
        rejects('p_drive_identity_forbidden_before_io', lambda: add({}, 'P:/resource-no-read.json'))
        rejects('extended_alias_identity_forbidden', lambda: add({}, '\\\\?\\' + str(fixture)))
    for alias in ('s4', '9tps4', 'df9tps4'):
        require(candidate_path(alias) == ('df9tps4', CANDIDATES['df9tps4']), 'S4 alias selected another candidate')
    return {'Passed': True, 'WindowsExtendedPathIO': os.name == 'nt', 'CanonicalIdentityPreserved': True,
            'Fixture': ref(fixture), 'FixturePathLength': len(str(fixture)),
            'FixtureIsPersistentSelfTestInputOnly': True, 'RealFrozenS4LongCompiledInput': actual,
            'CandidateFinalProofOrBitVerificationExecuted': False, 'EDAExecuted': False, 'PDriveAccessed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate-work')
    parser.add_argument('--draft', action='store_true')
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    local_io(args.output)
    output = args.output.resolve()
    require(output.parent == OUT and output.suffix == '.json' and not output.exists(), 'fresh JSON under this output directory required')
    if args.self_test:
        require(args.candidate_work is None and not args.draft, 'self-test never accepts a candidate or draft')
        value = self_test()
    else:
        require(args.candidate_work is not None, '--candidate-work is required')
        candidate, work = candidate_path(args.candidate_work)
        value = attribute(candidate, work, args.draft)
    with local_io(output).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    print(json.dumps({'Report': ref(output), 'SelfTestOnly': args.self_test,
                      'Draft': value.get('Draft'), 'OnBoardResourceBinding': value.get('OnBoardResourceBinding', False)}))


if __name__ == '__main__':
    main()
