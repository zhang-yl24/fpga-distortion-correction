"""Inspect this candidate's real synchronizers and routed Gray-pointer bounds.

This is a bounded structural/physical audit, not a universal CDC checker or
analog MTBF proof. Held mailbox protocols are referenced to the unchanged RTL
and integration evidence. No EDA or hardware operation is performed.
"""
from collections import defaultdict, Counter
from pathlib import Path
import argparse
import hashlib
import itertools
import json
import re

import audit_processed_output_physical as physical

PROJECT = Path(__file__).resolve().parents[1]
FINAL = PROJECT / 'build/processed-output/physical-final-report-20261031-a'
EXPORT = PROJECT / 'build/processed-output/export-final-20261031-a'
CAP = 'system/input_link/input_dma/capture/'
FIFOS = [('system/display_fifo/', 10, 'pixel_clk', 'ddrphy_sysclk'),
         (CAP + 'pixels/', 7, 'ddrphy_sysclk', 'board27')]
PERIOD = {'board27': 37.037, 'pixel_clk': 13.468, 'ddrphy_sysclk': 8.0}
NUM = r'[-+]?\d+(?:\.\d+)?'
require, sha = physical.require, physical.sha


def canonical_net(value):
    return value.replace('\\', '').replace(' ', '')


def index_graph(graph):
    ff, outputs, refs = {}, defaultdict(list), defaultdict(list)
    for name, cell in graph['Cells'].items():
        primitive, ports = cell['Primitive'], cell['Ports']
        if primitive in ('V_FFASYN', 'V_FFSYN'):
            ff[name] = cell
            outputs[ports['Q']].append((name, 'Q'))
        elif primitive == 'V_LUT6CARRY':
            for pin in ('Z', 'Z5', 'COUT'):
                if ports.get(pin):
                    outputs[ports[pin]].append((name, pin))
        elif primitive in ('V_BUF', 'V_INV'):
            if ports.get('Z'):
                outputs[ports['Z']].append((name, 'Z'))
        for pin, net in ports.items():
            if net:
                refs[net].append((name, pin))
    return ff, outputs, refs


def one(values, label):
    require(len(values) == 1, label + ' must match exactly once')
    return values[0]


def by_q(ff, value):
    return one([name for name, cell in ff.items()
                if canonical_net(cell['Ports']['Q']) == value], value)


def lut_matches(graph, name, output, first, release):
    """Exhaust all reachable shared-LUT inputs, including unrelated packed FFs."""
    lut = graph['Cells'][name]
    require(lut['Primitive'] == 'V_LUT6CARRY' and output in ('Z', 'Z5'), 'unsupported interstage logic')
    ports = lut['Ports']
    names = sorted({ports['I' + str(i)] for i in range(6)} - {"1'b0", "1'b1"})
    require(first in names and release in names, 'interstage LUT lacks first stage/reset release')
    init = int(lut['Parameters']['INIT'][4:], 16)
    def value(pin, values):
        width = 5 if pin == 'Z5' else 6
        address = sum(values[ports['I' + str(i)]] << i for i in range(width))
        return (init >> address) & 1
    for vector in itertools.product((0, 1), repeat=len(names)):
        values = dict(zip(names, vector))
        values.update({"1'b0": 0, "1'b1": 1})
        require(value(output, values) == values[first] & values[release],
                'interstage LUT is not first_stage AND local_release')
        for other in ('Z','Z5'):
            if other != output and ports.get(other):
                flipped = dict(values); flipped[first] ^= 1
                require(value(other, values) == value(other, flipped),
                        'first stage affects another shared-LUT output')
        require(not ports.get('COUT'), 'unreviewed shared-LUT carry fanout')
    return {'Cell': name, 'Output': output, 'Truth': 'first_stage AND local_release',
            'Inputs': names, 'ExhaustiveAssignments': 2 ** len(names)}


def clock_domain(graph, outputs, net):
    roots = {'core_clk':'ddrphy_sysclk', 'ntclkbufg_0':'board27', 'ntclkbufg_1':'pixel_clk'}
    seen = set()
    while net not in roots:
        require(net not in seen, 'clock buffer cycle')
        seen.add(net)
        name,pin=one(outputs[net],'clock buffer')
        cell=graph['Cells'][name]
        require(cell['Primitive']=='V_BUF' and pin=='Z', 'unexpected register clock topology')
        net=cell['Ports']['I']
    return roots[net]


def chain(graph, ff, outputs, refs, first, second, label, release=None):
    a, b = ff[first], ff[second]
    pa, pb = a['Ports'], b['Ports']
    require(first != second and pa['CK'] == pb['CK'], 'synchronizer stage clocks differ')
    require(pa['CE'] == pb['CE'] == "1'b1", 'synchronizer CE must be constant')
    require(pa['SR'] == pb['SR'], 'synchronizer stage resets differ')
    require(a['Primitive'] == b['Primitive'] and a['Parameters'] == b['Parameters'],
            'synchronizer reset/initial values differ')
    logic = None
    if pb['D'] == pa['Q']:
        allowed = {(first, 'Q'), (second, 'D')}
    else:
        require(release is not None, 'unexpected combinational logic between stages: ' + label)
        n, pin = one(outputs[pb['D']], 'second D driver')
        logic = lut_matches(graph, n, pin, pa['Q'], release)
        allowed = {(first, 'Q')} | {(n, p) for p, net in graph['Cells'][n]['Ports'].items() if net == pa['Q']}
    require(set(refs[pa['Q']]) == allowed, 'first-stage functional fanout escaped its second stage: ' + label)
    return {'Label': label, 'First': first, 'Second': second, 'FirstPorts': pa, 'SecondPorts': pb,
            'FirstStageOnlyFeedsSecondStage': True, 'InterstageLogic': logic,
            'FirstPlacement': graph['FFPlacement'][first], 'SecondPlacement': graph['FFPlacement'][second],
            'SameSite': graph['FFPlacement'][first]['Site'] == graph['FFPlacement'][second]['Site'],
            'SameBLE': graph['FFPlacement'][first] == graph['FFPlacement'][second]}


def structures(graph):
    ff, outputs, refs = index_graph(graph)
    rows, gray = [], []
    for prefix, width, read_clock, write_clock in FIFOS:
        for source, stage, destination, source_clock, dest_clock in (
                ('rd', 'rd_gray_w1', 'rd_gray_w2', read_clock, write_clock),
                ('wr', 'wr_gray_r1', 'wr_gray_r2', write_clock, read_clock)):
            for bit in range(width):
                first_prefix = prefix + stage + f'[{bit}]/'
                first = one([n for n in ff if n.startswith(first_prefix) and '/FFAPP' not in n], 'Gray first stage')
                second = by_q(ff, prefix + destination + f'[{bit}]')
                row = chain(graph, ff, outputs, refs, first, second, prefix + stage + f'[{bit}]')
                require(row['SameBLE'], 'Gray synchronizer is not in the same native BLE')
                q = ff[first]['Ports']['D']
                origin, output = one(outputs[q], 'registered Gray origin')
                require(origin in ff and output == 'Q', 'Gray origin is not a register')
                expected = prefix + (source + '_binary' if bit == width - 1 else source + '_gray') + f'[{bit}]'
                require(canonical_net(q) == expected, 'Gray source bit/merged MSB differs')
                require(clock_domain(graph,outputs,ff[origin]['Ports']['CK'])==source_clock
                        and clock_domain(graph,outputs,ff[first]['Ports']['CK'])==dest_clock,
                        'Gray actual clock domain differs')
                row.update(Source=origin, SourcePorts=ff[origin]['Ports'], Width=width, Bit=bit,
                           SourceClock=source_clock, DestinationClock=dest_clock,
                           SourcePeriodNS=PERIOD[source_clock],
                           NativeEndpoint=first.rsplit('/', 2)[0] + '/D')
                gray.append(row)
    # Direct/two-FF packed scalar synchronizers, including ordinary I2C inputs.
    direct = [
        ('board_failed_core[0]/', 'board_failed_core[1]'),
        ('hdmi_configuration/bus/scl_meta/', 'hdmi_configuration/bus/scl_sampled'),
        ('hdmi_configuration/bus/sda_meta/', 'hdmi_configuration/bus/sda_sampled'),
        ('system/done_sync[0]/', 'system/done_sync[1]'),
        ('system/grant_ack_sync[0]/', 'system/grant_ack_sync[1]'),
        ('system/request_sync[0]/', 'system/request_sync[1]'),
        ('system/scan_abort_sync[0]/', 'system/scan_abort_sync[1]'),
        ('system/scan_failed_sync[0]/', 'system/scan_failed_sync[1]'),
        ('system/scan_enable_sync[1]/', 'system/scan_enable_sync[1]'),
        ('system/output_video/done_ack_sync[0]/', 'system/output_video/done_ack_sync[1]'),
        ('system/output_video/grant_sync[0]/', 'system/output_video/grant_sync[1]')]
    for prefix, q in direct:
        first = one([n for n in ff if n.startswith(prefix) and '/FFAPP' not in n], 'scalar first')
        rows.append(chain(graph, ff, outputs, refs, first, by_q(ff, q), prefix))
    gated = [('ddr_ready_ref[0]', 'nt_led[1]', 'ref_reset[1]'),
             ('video_lock_ref[0]', 'nt_led[2]', 'ref_reset[1]'),
             ('system_failed_ref[0]', 'system_failed_ref[1]', 'ref_reset[1]'),
             ('processed_bit_ref[0]', 'nt_led[6]', 'ref_reset[1]'),
             (CAP + 'ack_sync[0]', CAP + 'ack_sync[1]', CAP + 'pix_reset[1]'),
             (CAP + 'done_sync[0]', CAP + 'done_sync[1]', 'system/input_link/input_dma/sys_reset[1]'),
             (CAP + 'grant_sync[0]', CAP + 'grant_sync[1]', CAP + 'pix_reset[1]'),
             (CAP + 'enable_pix[0]', CAP + 'enable_pix[1]', CAP + 'pix_reset[1]')]
    for first_q, second_q, reset_q in gated:
        first, second, reset = by_q(ff, first_q), by_q(ff, second_q), by_q(ff, reset_q)
        rows.append(chain(graph, ff, outputs, refs, first, second, first_q, ff[reset]['Ports']['Q']))
    require(len(gray) == 34 and len(rows) == 19, 'synchronizer inventory changed')
    return gray, rows


def max_paths(path):
    rows, block, section = [], [], None
    def finish():
        if not block or section != 'set_max_delay(setup)':
            return
        text = ''.join(block)
        def find(pattern):
            return one(re.findall(pattern, text, re.M), 'max-delay field')
        if 'Timing Exception  :  MaxDelay Path' not in text:
            return
        row = {'Source': find(r'^Startpoint\s*:\s*(\S+)\s*$'),
               'Endpoint': find(r'^Endpoint\s*:\s*(\S+)\s*$'),
               'Clock': find(r'^Path Group\s*:\s*(\S+)\s*$'),
               'Corner': find(r'^Path Type\s*:\s*max \((slow|fast) corner\)\s*$'),
               'BoundNS': float(find(r'^Timing Exception\s*:\s*MaxDelay Path (' + NUM + r')ns -datapath_only\s*$')),
               'SlackNS': float(find(r'^ Slack \(MET\)\s+(' + NUM + r')\s*$')),
               'ArrivalNS': float(find(r'^ Data arrival time\s+(' + NUM + r')\s+Logic Levels:.*$')),
               'BodySHA256': hashlib.sha256(text.encode()).hexdigest()}
        require(row['BoundNS'] == 8 and row['SlackNS'] >= 0, '8ns max-delay check failed')
        rows.append(row)
    with Path(path).open(encoding='gb18030', errors='strict') as stream:
        for line in stream:
            match = re.fullmatch(r'\| Exception type\s*:\s*(\S+)\s*\n?', line)
            if match:
                finish(); block = []; section = match[1]
            elif line.startswith('Startpoint'):
                finish(); block = [line]
            elif block:
                block.append(line)
    finish()
    require(Counter(r['Corner'] for r in rows) == {'slow':1504, 'fast':1504},
            'complete candidate max-delay/setup path inventory differs')
    return rows


def reset_structures(graph):
    ff, outputs, refs = index_graph(graph)
    rows = []
    for prefix in ('key_reset_sync[0]/', 'ref_reset[0]/', 'core_reset[0]/',
                   'pattern/reset_sync[0]/', CAP + 'pix_reset[0]/',
                   'system/input_link/input_dma/sys_reset[0]/',
                   'system/display_fifo/rd_reset_sync[0]/'):
        first = one([n for n in ff if n.startswith(prefix) and '/FFAPP' not in n], 'reset first')
        second = one([n for n in ff if n.startswith(prefix) and '/FFAPP' in n], 'reset second')
        row = chain(graph, ff, outputs, refs, first, second, prefix)
        require(row['SameBLE'], 'reset release stages must share BLE')
        value = ff[first]['Ports']['D']
        if value != "1'b1":
            driver, pin = one(outputs[value], 'constant reset data driver')
            cell = graph['Cells'][driver]
            require(pin == 'Z' and ((cell['Primitive'] == 'V_BUF' and cell['Ports']['I'] == "1'b1")
                    or (cell['Primitive'] == 'V_LUT6CARRY' and cell['Parameters'].get('INIT') == "64'hFFFFFFFFFFFFFFFF")),
                    'reset release does not shift a constant one')
        require(ff[first]['Primitive'] == 'V_FFASYN'
                and ff[first]['Parameters']['SET_RESET'] == '"RESET"'
                and ff[first]['Parameters']['INIT'] == "1'b0", 'reset FF type/initial state differs')
        rows.append(row)
    prefix = 'system/bank_core/engine/core/reset_sync'
    first = one([n for n in ff if n.startswith(prefix + '[0]/') and '/FFAPP' not in n], 'replicated reset first')
    q, a = ff[first]['Ports']['Q'], ff[first]
    consumers = [(n,p) for n,p in refs[q] if (n,p) != (first,'Q')]
    require(len(consumers) == 28 and all(p == 'D' and n.startswith(prefix) and n in ff for n,p in consumers),
            'replicated reset first-stage fanout changed')
    reset_pins = {ff[n]['Ports']['SR'] for n,p in consumers} | {a['Ports']['SR']}
    resets = []
    for net in reset_pins:
        driver, pin = one(outputs[net], 'replicated reset clear driver')
        cell = graph['Cells'][driver]
        require(cell['Primitive'] == 'V_INV' and pin == 'Z'
                and cell['Ports'] == {'Z':net,'I':'core_reset[1]'},
                'replicated reset clear is not the same core-local release')
        resets.append({'Cell':driver,'Net':net,'Input':'core_reset[1]'})
    for n,p in consumers:
        b=ff[n]
        require(b['Primitive'] == a['Primitive'] == 'V_FFASYN' and b['Parameters'] == a['Parameters']
                and b['Ports']['CK'] == a['Ports']['CK'] and b['Ports']['CE'] == a['Ports']['CE'] == "1'b1"
                and a['Ports']['D'] == "1'b1", 'replicated reset stages differ')
    return {'PackedTwoStageChains':rows, 'PackedChains':7,
            'CoreResetReplication':{'First':first, 'FirstPorts':a['Ports'], 'SecondCopies':[
                {'Name':n,'Ports':ff[n]['Ports'],'Placement':graph['FFPlacement'][n]} for n,p in consumers],
                'EquivalentClearInverters':resets, 'FirstStageOnlyFeedsSecondStages':True,
                'SameCoreClockAndClearFunction':True, 'SecondStageCount':28,
                'SeparateReleaseEdgesPossible':True,
                'Scope':'Same-domain reset tree; controller grants remain held through independent local releases.'}}


def audit(netlist, exceptions):
    graph = physical.functional_export(netlist)
    gray, scalar = structures(graph)
    resets = reset_structures(graph)
    paths = max_paths(exceptions)
    groups = []
    for prefix, width, rd_clock, wr_clock in FIFOS:
        for stage, source_clock in (('rd_gray_w1', rd_clock), ('wr_gray_r1', wr_clock)):
            target = {r['NativeEndpoint'] for r in gray if r['Label'].startswith(prefix + stage)}
            for corner in ('slow', 'fast'):
                records = [r for r in paths if r['Corner'] == corner and r['Endpoint'] in target]
                require(Counter(r['Endpoint'] for r in records) == Counter({k:1 for k in target}),
                        'every Gray bit requires one complete max-delay path per corner')
                require(all(r['ArrivalNS'] < PERIOD[source_clock] for r in records),
                        'Gray physical delay exceeds source period')
                # All nonnegative data-path delays <= one source period imply
                # max-min bus skew <= that period; this bound includes tCQ.
                groups.append({'Group':prefix + stage, 'Width':width, 'Corner':corner,
                               'SourceClock':source_clock, 'SourcePeriodNS':PERIOD[source_clock],
                               'MinArrivalNS':min(r['ArrivalNS'] for r in records),
                               'MaxArrivalNS':max(r['ArrivalNS'] for r in records),
                               'ConservativeSkewUpperBoundNS':max(r['ArrivalNS'] for r in records),
                               'AllBitsBoundedByOneSourcePeriod':True, 'Paths':records})
    return {'Schema':'processed-output-cdc-structural-physical-v1', 'AuditPassed':True,
            'GrayBitSynchronizers':gray, 'ScalarSynchronizers':scalar, 'GrayPhysicalGroups':groups,
            'ResetReleaseStructure':resets,
            'GrayBits':34, 'ScalarChains':19, 'AuditedSynchronizerFFs':106,
            'AllGrayChainsSameBLE':True,
            'ScalarSameSite':sum(r['SameSite'] for r in scalar),
            'ScalarSameBLE':sum(r['SameBLE'] for r in scalar),
            'MaxDelaySetupPathsPerCorner':1504, 'MaxDelaySetupAllNonnegative':True,
            'MaxReportedCDCDatapathArrivalNS':max(p['ArrivalNS'] for p in paths),
            'HeldMailboxReview':{
                'Publication':'Data and toggle launch on the same source edge; data holds until returned two-stage acknowledgment.',
                'CaptureGrant':'DMA grant bank/ID held while grant_busy; next grant waits capture completion.',
                'CaptureDone':'end_* held while end_wait; DMA captures once, adds end_settle=3, and only then drains/completes acknowledgment.',
                'DisplayRequest':'request_epoch changes at a frame boundary; no new healthy request until grant/current lease is handled.',
                'DisplayGrant':'grant_* held while response_busy; output samples after two-stage grant toggle.',
                'DisplayDone':'done_* held until two-stage done_ack; independent sticky failure vetoes bank release.',
                'FaultBundles':'board_fault/system_fault are latched with sticky fault and observed after two-stage flag.',
                'EightNSBoundVsEarliestTwoCycleConsumptionNS':{'ddrphy_sysclk':16.0,'board27':74.074,'pixel_clk':26.936},
                'StaticRTLReviewOnly':True, 'IntegrationEvidence':'build/processed-output-integration/top-20261031-g/processed-output-simulation.json'},
            'AllCDCUniversallyProven':False, 'AnalogMTBFProven':False,
            'HardwareAccessed':False, 'HardwareReleaseAllowed':False,
            'Limitations':['Bounded inventory of current Gray/scalar synchronizers; not a universal CDC/RDC checker.',
                           'Held-mailbox stability and reset epoch protocol require unchanged RTL/integration evidence.',
                           'Nonlocal scalar interstage timing still needs targeted native path details; complete MTBF is not proven.',
                           'All 1504 reported max-delay/setup paths are checked, but path enumeration alone is not a universal proof of every mailbox bit.',
                           'Core-local reset second-stage replication is explicitly inventoried; no independent runtime reset recovery is claimed.']}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    netlist=EXPORT/'generate_netlist/processed_output_top_sim.v'
    exceptions=FINAL/'processed_output_top_exception.rtr'
    inputs=[netlist,exceptions,FINAL/'input.adf',FINAL/'result.json',EXPORT/'export-result.json',
            Path(__file__),Path(physical.__file__),PROJECT/'rtl/video_async_fifo.v',
            PROJECT/'rtl/experimental/hdmi1080_capture_cdc.v',
            PROJECT/'rtl/experimental/hdmi1080_video_system_cdc_reset.v',
            PROJECT/'rtl/experimental/ddr_video_output_1080_board.v',
            PROJECT/'board/processed_output_top.v']
    watched={str(p.resolve()):sha(p) for p in inputs}
    receipt=json.loads((EXPORT/'export-result.json').read_text())
    native=json.loads((FINAL/'result.json').read_text())
    require(receipt['ExecutionPassed'] is True and receipt['InputDrift'] == []
            and receipt['SourceADFSHA256'] == '1d19936ede917ea1268a17a11fb3b0b34ff84753abefb062ae26d8a2c7c7550b'
            and sha(FINAL/'input.adf') == receipt['SourceADFSHA256']
            and sha(netlist) == receipt['Netlist']['SHA256'], 'netlist/ADF execution binding differs')
    require(native['ExecutionPassed'] is True and native['InputDrift'] == []
            and native['ResultADFSHA256'] == receipt['SourceADFSHA256']
            and sha(exceptions) == native['Artifacts']['processed_output_top_exception.rtr'],
            'native exception/ADF binding differs')
    result=audit(netlist,exceptions)
    require(all(sha(p)==h for p,h in watched.items()),'audit inputs changed')
    result['InputSHA256']=watched
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2); stream.write('\n')
    print(json.dumps({k:result[k] for k in ('AuditPassed','GrayBits','ScalarChains','ScalarSameSite')}))


if __name__=='__main__':
    main()
