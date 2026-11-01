"""Candidate-bound raw-camera IO/CDC inventory and bounded physical checks.

This tool does not run EDA. Missing native IO or timing evidence is emitted as
an explicit blocker with an exact query plan. External AC and analog MTBF are
outside this digital diagnostic audit, even when the scoped checks pass.
"""
import argparse
from collections import Counter
import itertools
import json
from pathlib import Path
import re

import audit_camera_vga_cdc as cdc
import audit_camera_vga_io as io
import audit_raw_camera_delay_reset_effect as effect
import audit_raw_camera_delay_reset_netlist as reset_graph

derived, physical, inspect = effect.derived, effect.physical, effect.inspect
prep, require, sha = derived.prep, derived.require, derived.sha
SELF = Path(__file__).resolve()
SCHEMA = 'raw-camera-delay-io-cdc-audit-v1'
FIFO = 'pipeline/bridge/fifo/'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def watch_tools(watched):
    for module in (cdc, cdc.physical, cdc.physical.dialect, cdc.physical.hold, cdc.physical.native,
                   io, io.pin_parser, io.net_parser, effect, derived, physical, inspect, reset_graph):
        physical.add(watched, module.__file__)
    physical.add(watched, SELF)


def gray_structures(g):
    found = {}
    for name in g.ff:
        m = re.match(r'(.+/)(rd_gray_w1|wr_gray_r1)\[(\d+)\]/', name)
        if m and '/FFAPP' not in name:
            key = m[1], m[2], int(m[3])
            require(key not in found, 'duplicate raw Gray first stage')
            found[key] = name
    expected = {(FIFO, stage, bit) for stage in ('rd_gray_w1', 'wr_gray_r1') for bit in range(10)}
    require(set(found) == expected, 'raw FIFO must have exactly two ten-bit Gray chains')
    result = []
    for (prefix, stage, bit), first in sorted(found.items()):
        second = g.by_q(prefix + stage[:-1] + '2' + f'[{bit}]')
        row = g.chain(first, second, prefix + stage + f'[{bit}]')
        source, pin = g.driver(g.ff[first]['Ports']['D'])
        direction = stage[:2]
        expected_q = prefix + direction + ('_binary' if bit == 9 else '_gray') + f'[{bit}]'
        require(source in g.ff and pin == 'Q' and cdc.canon(g.ff[first]['Ports']['D']) == expected_q,
                'raw Gray origin is not the expected registered pointer bit')
        source_clock = g.clock(g.ff[source]['Ports']['CK'])['Domain']
        require(source_clock != row['DestinationClock'], 'Gray synchronizer does not cross clocks')
        row.update(Source=source, SourceClock=source_clock, SourcePorts=g.ff[source]['Ports'],
                   Width=10, Bit=bit, Group=prefix + stage, NativeEndpoint=cdc.native_parent(first) + '/D')
        result.append(row)
    return result


def scalar_structures(g):
    names = [('camera_ready_ddr[0]/', 'camera_ready_ddr[1]'),
             ('picture/cap_reset[0]/', 'picture/cap_reset[1]')]
    names += [(prefix + kind + '_meta/', prefix + kind + '_sampled')
              for prefix in ('camera/bus/', 'hdmi/bus/') for kind in ('scl', 'sda')]
    names += [(prefix + '[0]/', prefix + '[1]') for prefix in
              ('picture/ack_sync', 'picture/request_sync', 'pipeline/bridge/arm_sync', 'pipeline/bridge/done_sync')]
    rows = [g.chain(g.first_prefix(prefix), g.by_q(q), q) for prefix, q in names]
    require(len(rows) == 10, 'raw scalar chain count differs')
    return rows


def reset_structures(g):
    expected = {'ddr_reset_sync', 'picture/cam_reset_sync', 'picture/pix_reset_sync',
                'pipeline/bridge/cam_reset_sync', FIFO + 'rd_reset_sync', 'pipeline/reset_sync'}
    found = {n.rsplit('[0]/', 1)[0]: n for n in g.ff
             if not n.startswith('u_ddr3_test_h/') and '/FFAPP' not in n and
             re.search(r'reset(?:_sync)?\[0\]/', n) and
             not n.startswith(('test_reset_sync[', 'picture/cap_reset['))}
    require(set(found) == expected, 'raw application reset chain inventory differs')
    rows = []
    for label, first in sorted(found.items()):
        a = g.ff[first]
        require(g.constant_one(a['Ports']['D']) and a['Primitive'] == 'V_FFASYN'
                and a['Parameters'].get('INIT') == "1'b0" and a['Parameters'].get('SET_RESET') == '"RESET"',
                'raw async reset release contract differs')
        row = g.chain(first, g.by_q(label + '[1]'), label)
        rows.append(row)
    return rows


def input_delay_structures(g):
    """Exact pad/IBUF/delay/receiver graph; reject expressions and bypasses."""
    require(not re.search(r'\b(?:assign|always|initial|function|task|generate|tran|buf|not)\b',
                          g.g['ModuleDeclarations']), 'unparsed native aliases or procedural logic')
    delays = {n:c for n,c in g.cells.items() if c['Primitive'] == 'V_ZEROHOLDDELAY'}
    require(len(delays) == 8, 'exactly eight native input delay cells required')
    for c in g.cells.values():
        for value in c['Ports'].values():
            value = cdc.canon(value)
            if re.search(r'(?<![A-Za-z0-9_$/])(?:cam_data|capture_data)(?![A-Za-z0-9_$])', value):
                require(re.fullmatch(r'(?:cam_data|capture_data)\[[0-7]\]', value),
                        'camera bus used without one exact scalar bit')
    used, rows = set(), []
    for bit in range(8):
        pad, output = f'cam_data[{bit}]', f'capture_data[{bit}]'
        delay = cdc.one([n for n,c in delays.items() if c['Ports'].get('DO') == output], output + ' delay')
        cell = delays[delay]
        require(cell['Parameters'] == {'ZHOLD_SET':'"1500ps"'} and set(cell['Ports']) == {'DI','DO'},
                'native delay setting or ports differ')
        intermediate = cell['Ports']['DI']
        buffer = cdc.one([n for n,c in g.cells.items() if c['Primitive'] == 'V_IBUF'
                         and c['Ports'] == {'I':pad, 'O':intermediate}], pad + ' input buffer')
        require(g.cells[buffer]['Parameters'] == {'IOSTANDARD':'"LVCMOS33"', 'TERM_DDR':'"ON"'},
                'native input buffer electrical parameters differ')
        require(set(g.refs[pad]) == {(buffer,'I')}, 'camera pad bypasses its input buffer')
        require(set(g.refs[intermediate]) == {(buffer,'O'), (delay,'DI')}, 'camera input buffer bypasses its delay')
        prefixes = [f'{prefix}/{kind}[{index}]/' for prefix in ('picture/receiver', 'pipeline/bridge/capture')
                    for kind,index in (('first_byte',bit), ('pixel',bit+8))]
        receivers = []
        for prefix in prefixes:
            receiver = cdc.one([n for n,c in g.ff.items() if n.startswith(prefix)
                               and c['Ports']['D'] == output], 'delayed receiver ' + prefix)
            require(g.clock(g.ff[receiver]['Ports']['CK'])['Domain'] == 'camera_pclk',
                    'delayed camera data sampled by another domain')
            receivers.append(receiver)
        require(set(g.refs[output]) == {(delay,'DO')} | {(n,'D') for n in receivers},
                'delayed camera data has unexpected drivers or consumers')
        # refs indexes whole expressions. Explicitly reject a critical net
        # hidden in a concatenation, inversion, arithmetic expression or alias.
        critical = [cdc.canon(n) for n in (pad, intermediate, output)]
        for name,c in g.cells.items():
            for pin,value in c['Ports'].items():
                value = cdc.canon(value)
                for net in critical:
                    if re.search(r'(?<![A-Za-z0-9_$])' + re.escape(net) + r'(?![A-Za-z0-9_$])', value):
                        require(value == net, 'critical camera net used inside an unparsed expression')
        require(buffer not in used and delay not in used, 'input delay resources shared across bits')
        used.update((buffer,delay))
        rows.append({'Bit':bit, 'Pad':pad, 'InputBuffer':buffer, 'Intermediate':intermediate,
                     'DelayCell':delay, 'DelaySetting':'1500ps', 'Output':output,
                     'Receivers':receivers, 'ReceiverClock':'camera_pclk', 'NoBypass':True})
    return {'Passed':True, 'Bits':rows, 'NativeDelayCells':8, 'ReceiverEndpoints':32,
            'AllConsumersUseDelayedData':True, 'NominalDelayPS':1500,
            'ActualPVTDelayFromSettingAloneProven':False, 'ExternalACTimingAccepted':False}


class BooleanCone:
    """Exact local LUT cofactors; unknown FF values remain independent leaves."""
    def __init__(self, graph):
        self.g = graph
        self.cache = {}

    def expression(self, net, visited=()):
        if net in self.cache:
            return self.cache[net]
        require(net not in visited, 'Boolean cone cycle')
        if net in ("1'b0", "1'b1"):
            result = ('constant', int(net[-1]))
        else:
            name, pin = self.g.driver(net)
            cell = self.g.cells[name]; kind, ports = cell['Primitive'], cell['Ports']
            if kind in cdc.FF_TYPES:
                require(pin == 'Q', 'unreviewed FF Boolean output')
                result = ('variable', cdc.canon(net))
            elif kind in ('V_BUF', 'V_INV'):
                child = self.expression(ports['I'], visited + (net,))
                result = child if kind == 'V_BUF' else ('not', child)
            else:
                require(kind == 'V_LUT6CARRY' and pin in ('Z', 'Z5'), 'unreviewed Boolean driver ' + name)
                init = int(cell['Parameters']['INIT'][4:], 16)
                constants = {i:int(ports['I' + str(i)][-1]) for i in range(6)
                             if ports['I' + str(i)] in ("1'b0", "1'b1")}
                if pin == 'Z5':
                    constants[5] = 0
                support = reset_graph.lut_support(init, constants)
                children = {i:self.expression(ports['I' + str(i)], visited + (net,)) for i in support}
                result = ('lut', init, constants, children)
        self.cache[net] = result
        return result

    @staticmethod
    def evaluate(expr, values):
        kind = expr[0]
        if kind == 'constant': return {expr[1]}
        if kind == 'variable': return {values[expr[1]]} if expr[1] in values else {0, 1}
        if kind == 'not': return {1 - v for v in BooleanCone.evaluate(expr[1], values)}
        init, constants, children = expr[1:]
        choices = [BooleanCone.evaluate(children[i], values) if i in children else {constants.get(i, 0)} for i in range(6)]
        return {(init >> sum(bit << i for i, bit in enumerate(bits))) & 1 for bits in itertools.product(*choices)}

    def exact(self, net, values, expected):
        require(self.evaluate(self.expression(net), values) == {expected}, 'native Boolean protocol condition differs')


def held_structures(g):
    cone = BooleanCone(g)
    rows = []
    flag = g.by_q('pipeline/bridge/done_held'); flag_ports = g.ff[flag]['Ports']
    done = g.by_q('pipeline/source_done'); done_ports = g.ff[done]['Ports']
    require(g.constant_one(flag_ports['D']) and g.constant_one(done_ports['D']), 'raw done flags must set one')
    sync_first = g.first_prefix('pipeline/bridge/done_sync[0]/')
    require(g.ff[sync_first]['Ports']['D'] == flag_ports['Q'], 'metadata done synchronizer has wrong source')
    cone.exact(flag_ports['CE'], {'pipeline/bridge/done_held':1}, 0)
    for b in (0, 1):
        for d in (0, 1):
            cone.exact(done_ports['CE'], {'pipeline/bridge/done_sync[1]':b, 'pipeline/source_done':d}, b & (1-d))
    pairs = [(f'pipeline/bridge/checksum_held[{i}]', f'pipeline/source_crc[{i}]') for i in range(32)]
    pairs.append(('pipeline/bridge/valid_held', 'pipeline/source_valid'))
    for source_q, dest_q in pairs:
        source, dest = g.by_q(source_q), g.by_q(dest_q)
        a, b = g.ff[source]['Ports'], g.ff[dest]['Ports']
        require(b['D'] == a['Q'] and cone.expression(a['CE']) == cone.expression(flag_ports['CE'])
                and a['CK'] == flag_ports['CK'],
                'metadata must launch with frozen flag and feed exact destination')
        require(g.clock(a['CK'])['Domain'] == 'camera_pclk' and
                g.clock(b['CK'])['Domain'] == 'ddrphy_sysclk', 'metadata clock domains differ')
        for source_ff in (source, flag):
            require(g.ff[source_ff]['Parameters']['SET_RESET'] == '"RESET"' and
                    g.ff[source_ff]['Parameters']['INIT'] == "1'b0", 'metadata source reset value differs')
            for released in (0, 1):
                cone.exact(g.ff[source_ff]['Ports']['SR'], {'pipeline/bridge/cam_reset_sync[1]':released}, 1-released)
        for dest_ff in (dest, done):
            require(g.ff[dest_ff]['Parameters']['SET_RESET'] == '"RESET"' and
                    g.ff[dest_ff]['Parameters']['INIT'] == "1'b0", 'metadata destination reset value differs')
            for released, active in itertools.product((0, 1), repeat=2):
                cone.exact(g.ff[dest_ff]['Ports']['SR'], {'pipeline/reset_sync[1]':released,
                           'pipeline/transaction_active':active}, 1-(released & active))
        for flag_value, done_value in itertools.product((0,1), repeat=2):
            cone.exact(b['CE'], {'pipeline/bridge/done_sync[1]':flag_value, 'pipeline/source_done':done_value},
                       flag_value & (1-done_value))
        rows.append({'Label':source_q, 'Source':source, 'Destination':dest,
                     'NativeSource':cdc.native_parent(source) + '/CLK', 'NativeEndpoint':cdc.native_parent(dest) + '/D',
                     'SourceClock':g.clock(a['CK'])['Domain'], 'DestinationClock':g.clock(b['CK'])['Domain'],
                     'ControlSecondStage':'pipeline/bridge/done_sync[1]', 'MinimumDestinationPeriodsBeforeUse':2,
                     'SourceFrozenAfterFlag':True, 'NativeDestinationEnableVerified':True})
    source, dest = g.by_q('picture/held_bank'), g.by_q('picture/read_bank')
    a, b = g.ff[source]['Ports'], g.ff[dest]['Ports']
    request, ack = g.ff[g.by_q('picture/request')]['Ports'], g.ff[g.by_q('picture/acknowledge')]['Ports']
    require(g.ff[g.first_prefix('picture/request_sync[0]/')]['Ports']['D'] == request['Q'] and
            g.ff[g.first_prefix('picture/ack_sync[0]/')]['Ports']['D'] == ack['Q'],
            'preview request/ack synchronizer source differs')
    require(a['CE'] == request['CE'] and a['CK'] == request['CK'] and a['SR'] == request['SR']
            and b['CE'] == ack['CE'] and b['CK'] == ack['CK'] and b['SR'] == ack['SR']
            and b['D'] == a['Q'] and cdc.canon(ack['D']) == 'picture/request_sync[1]',
            'preview bank launch/ack contract differs')
    for value in (0, 1):
        cone.exact(request['D'], {'picture/request':value}, 1-value)
        cone.exact(b['CE'], {'picture/request_sync[1]':value, 'picture/acknowledge':value}, 0)
    rows.append({'Label':'picture/held_bank', 'Source':source, 'Destination':dest,
                 'NativeSource':cdc.native_parent(source) + '/CLK', 'NativeEndpoint':cdc.native_parent(dest) + '/D',
                 'SourceClock':g.clock(a['CK'])['Domain'], 'DestinationClock':g.clock(b['CK'])['Domain'],
                 'ControlSecondStage':'picture/request_sync[1]', 'MinimumDestinationPeriodsBeforeUse':2,
                 'SourceFrozenAfterFlag':False, 'SourceHoldRequiresReviewedToggleAckRTL':True,
                 'NativeDestinationEnableVerified':True})
    require(len(rows) == 34, 'held-data bit inventory differs')
    return rows


def coverage(rows, report, constraints, pairs, gray=False):
    paths, stats = cdc.max_delay_paths(report, {r['NativeEndpoint'] for r in rows})
    result, missing = [], []
    for row in rows:
        pair = row['SourceClock'], row['DestinationClock']
        require(pair in pairs and pairs[pair]['BoundNS'] == 8.0, 'raw crossing lacks exact 8ns max-delay')
        source = cdc.native_parent(row['Source']) + '/CLK'
        for corner in ('slow', 'fast'):
            found = [p for p in paths if p['Corner'] == corner and p['Endpoint'] == row['NativeEndpoint']]
            if not found:
                missing.append({'Source':source, 'Endpoint':row['NativeEndpoint'], 'Corner':corner, 'Label':row['Label']})
                continue
            require(len(found) == 1 and found[0]['Source'] == source and found[0]['BoundNS'] == 8.0,
                    'crossing timing source/budget differs')
            limit = constraints['PeriodsNS'][pair[0]] if gray else 2 * constraints['PeriodsNS'][pair[1]]
            require(0 <= found[0]['ArrivalNS'] < limit, 'crossing exceeds conservative propagation window')
            result.append({**found[0], 'Label':row['Label'], 'ConservativeWindowNS':limit})
    return result, missing, stats


def pin_audit(top, exported, fdc, pcf, prt, official, cam_reference, cam_pins):
    # The shared IO parser accepts an ANSI header with an optional parameter
    # group. An empty group adds no ports/parameters and is stripped by it.
    top_text, n = re.subn(r'\bmodule\s+' + prep.TARGET + r'\s*\(', 'module camera_vga_output_top #()(', top, count=1)
    # Raw DDR ports use constant N-1 widths. Fold only this exact unsigned
    # literal form; no arbitrary Verilog expression or evaluation is accepted.
    top_text = re.sub(r'\[\s*(\d+)\s*-\s*1\s*:\s*0\s*\]',
                      lambda match:'[' + str(int(match[1])-1) + ':0]', top_text)
    net_text, m = re.subn(r'\bmodule\s+' + prep.TARGET + r'\b', 'module camera_vga_output_top', exported, count=1)
    require(n == m == 1, 'raw IO parser header adaptation ambiguous')
    result = io.pin_audit(top_text, fdc, pcf, prt, net_text, official, cam_reference, cam_pins)
    require(next(r for r in result['PinInventory'] if r['Port'] == 'uart_txd')['LOC'] == 'C24', 'raw UART TX pad differs')
    result['ParserAdapter'] = 'In memory only: module identifier, empty formal parameter group and unsigned literal N-1 range folding; original bytes retained.'
    return result


def protocol_sources(watched):
    paths = [prep.PROJECT / 'rtl/camera_live_bridge.v', prep.PROJECT / 'rtl/camera_preview.v',
             prep.PROJECT / 'rtl/raw_camera_capture.v', prep.PROJECT / 'rtl/video_async_fifo.v']
    result = {}
    reviewed = {'camera_live_bridge.v':'29a62abed4dcc0e422434cb85847ab66104b1e6388c5e3799535334f962c0e33',
                'camera_preview.v':'9cc0a8344a3245f2c986d6ac7bb3abea721fbb04de4404c2025b1db361a17681'}
    for path in paths:
        physical.add(watched, path)
        if path.name in reviewed:
            require(sha(path) == reviewed[path.name], 'static protocol review requires unchanged complete source')
        result[path.name] = {'Path':str(path), 'SHA256':sha(path)}
    bridge = prep.normalized(paths[0].read_text(encoding='utf-8-sig'))
    preview = prep.normalized(paths[1].read_text(encoding='utf-8-sig'))
    for token in ('if(!frozen&&cap_rst_n&&started&&(frame_invalid||(line_end&&odd)||frame_complete))begin',
                  'frozen<=1;done_held<=1;', 'checksum_held<=~checksum;',
                  'done_sync<={done_sync[0],done_held};',
                  'if(done_sync[1]&&!source_done)beginsource_done<=1;source_valid<=valid_held;source_checksum<=checksum_held;'):
        require(bridge.count(token) == 1, 'reviewed raw metadata protocol differs')
    for token in ('held_bank<=write_bank;request<=!request;writing<=0;',
                  'elseif(request==ack_sync[1])beginwrite_bank<=!held_bank;writing<=1;',
                  'request_sync<={request_sync[0],request};',
                  'if(x==0&&y==0&&request_sync[1]!=acknowledge)beginread_bank<=held_bank;acknowledge<=request_sync[1];'):
        require(preview.count(token) == 1, 'reviewed preview toggle/ack protocol differs')
    return {'Sources':result, 'Metadata':'Launch data and sticky flag together; freeze until shared transaction reset; consume after two-stage flag.',
            'Preview':'Launch held bank with request toggle; writing stops; next write bank waits for synchronized acknowledgement; consume only at display frame boundary.',
            'Review':'Bounded static RTL and local native enable truth checks; not universal formal CDC proof.',
            'FullSequentialEquivalenceProven':False, 'AnalogMTBFProven':False}


def bind_effect(path, export_path, export, watched):
    path = physical.add(watched, path); value = read(path)
    require(value.get('Schema') == effect.SCHEMA and value.get('Target') == prep.TARGET
            and all(value.get(k) is True for k in ('AuditPassed', 'ResetEffectVerified', 'AllInternalChecksMet',
                                                  'FunctionalGraphIdentical', 'AllFFPlacementsIdentical', 'NoDataFalsePaths')),
            'passed current raw reset-effect receipt required')
    require(value['CandidateExportReceipt'] == effect.file_binding(export_path)
            and value['ResultADF']['SHA256'] == export['SourceADFSHA256'], 'effect belongs to another export/ADF')
    require(value.get('InputSHA256') and value.get('ToolSHA256'), 'effect input/tool closure missing')
    pds = Path(export['Command'][0])
    for name, digest in value['InputSHA256'].items(): physical.add(watched, name, digest, pds)
    for name, digest in value['ToolSHA256'].items(): physical.add(watched, name, digest, pds)
    require(str(effect.SELF) in value['ToolSHA256'] and value['ToolSHA256'][str(effect.SELF)] == sha(effect.SELF),
            'effect implementation differs')
    return {'Receipt':effect.file_binding(path), 'InputsRehashed':True, 'ComputationReexecuted':False}


def run(export_path, output_dir, effect_path=None, io_query=None):
    export_path = inspect.canonical(export_path, prep.WORK); watched = {}; claimed = read(export_path)
    watch_tools(watched)
    baseline = claimed.get('Schema') == inspect.SCHEMA
    if baseline:
        require(effect_path is None and io_query is None, 'baseline scope inventory cannot claim derived effect/native queries')
        export = effect.audit.inspection_receipt(export_path, 'export', Path(claimed['BuildPlan']),
                                                 Path(claimed['SourceADF']), claimed['SourceADFSHA256'], watched)
    else:
        export = derived.bind_receipt(export_path, watched)
        require(export['Mode'] == 'export', 'native functional export required')
    effect_binding = bind_effect(effect_path, export_path, export, watched) if effect_path else None
    build_plan = Path(export['BuildPlan']); plan = read(build_plan); build = build_plan.parent
    net = effect.artifact(export_path, export, prep.TARGET + '_sim.v', watched)
    report = effect.artifact(export_path, export, prep.TARGET + '_exception.rtr', watched)
    text = net.read_text(encoding='utf-8-sig'); g = cdc.Graph(effect.functional(text))
    input_delays = input_delay_structures(g)
    primitive = plan['TechnologyPrimitiveSource']
    pds = Path(plan['PDS']['Executable'])
    library = pds.parent.parent / 'arch/vendor/pango/logos2/common/lib/gtp_lib.v'
    require(primitive == prep.validate_primitive_library(library), 'input delay primitive library proof differs')
    physical.add(watched, library, primitive['SHA256'], pds)
    gray, scalar, resets = gray_structures(g), scalar_structures(g), reset_structures(g)
    held = held_structures(g); protocols = protocol_sources(watched)
    fdc = physical.add(watched, plan['Constraints']['FDC'], plan['Constraints']['SHA256'])
    constraints, pairs = cdc.constraint_inventory(fdc)
    gray_paths, gray_missing, stats = coverage(gray, report, constraints, pairs, gray=True)
    held_paths, held_missing, _ = coverage(held, report, constraints, pairs)
    paths = {'top':prep.PROJECT / prep.TOP, 'pcf':build / 'device_map' / (prep.TARGET + '.pcf'),
             'prt':build / 'place_route' / (prep.TARGET + '_prr_route_optimize.prt'),
             'official':prep.PROJECT / 'platform/video_base/HDMI_IN_DDR3_HDMI_OUT_top.fdc',
             'cam_reference':prep.PROJECT / 'board/raw_camera_capture_cam2_ref.fdc',
             'cam_pins':prep.PROJECT / 'board/raw_camera_capture_cam2_ref-pins.json'}
    texts = {key:physical.add(watched, p).read_text(encoding='utf-8-sig') for key, p in paths.items()}
    pins = pin_audit(texts['top'], text, fdc.read_text(), texts['pcf'], texts['prt'], texts['official'],
                     texts['cam_reference'], json.loads(texts['cam_pins']))
    if io_query:
        qr = derived.bind_receipt(io_query, watched)
        require(qr['Mode'] == 'query' and qr['SourceADFSHA256'] == export['SourceADFSHA256'], 'native IO query belongs to another candidate')
        log = effect.artifact(io_query, qr, 'stdout.log', watched)
        io.apply_native_sites(pins, log.read_text(encoding='gb18030'))
    queries = {(r['Source'], r['Endpoint']):r for r in gray_missing + held_missing}
    interstage = [q for r in gray + scalar + resets for q in r['NativeQueries']]
    for r in gray + scalar + resets:
        for q in r['NativeQueries']: queries[(q['Source'], q['Endpoint'])] = q
    body = ['# Raw candidate only. Inspector initializes native STA once.']
    for key in sorted(queries):
        source, endpoint = key
        body.append('report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {' + source + '} -to {' + endpoint + '}')
    body += ['show -dev_instance {' + site + '}' for site in sorted({p['Site'] for p in pins['PinInventory']})]
    body = '\n'.join(body) + '\n'; inspect.query_commands(body)
    blockers = []
    if baseline or not effect_binding: blockers.append('Final derived candidate with bound passing reset-effect audit is required.')
    if gray_missing: blockers.append('Missing two-corner Gray max-delay paths: ' + str(len(gray_missing)))
    if held_missing: blockers.append('Missing two-corner held-data max-delay paths: ' + str(len(held_missing)))
    if interstage: blockers.append('Non-BLE interstage native setup/hold query verification remains required: ' + str(len(interstage)))
    if not pins['FinalNativeSiteMappingPassed']: blockers.append('Final native IO site query is required.')
    watch_tools(watched)
    require(not inspect.drift(watched), 'raw IO/CDC audit input/tool drift')
    result = {'Schema':SCHEMA, 'Target':prep.TARGET, 'CreatedUTC':prep.utc(), 'StructuralAuditPassed':True,
              'ScopedDigitalChecksPassed':not blockers, 'Blockers':blockers,
              'ExportReceipt':effect.file_binding(export_path), 'EffectReceipt':effect_binding,
              'CandidateADFSHA256':export['SourceADFSHA256'], 'BaselineDiagnosticOnly':baseline,
              'ActualCellCount':len(g.cells), 'ActualFFCount':len(g.ff), 'GrayBitSynchronizers':gray,
              'ScalarSynchronizers':scalar, 'ResetReleaseChains':resets, 'HeldData':held,
              'HeldProtocolReview':protocols, 'GrayTiming':gray_paths, 'HeldDataTiming':held_paths,
              'InputDelayMapping':input_delays, 'TechnologyPrimitiveSource':primitive,
              'PendingInterstageCases':interstage,
              'MissingGrayCases':gray_missing, 'MissingHeldCases':held_missing, 'Pins':pins,
              'Summary':{'GrayBits':len(gray), 'ScalarChains':len(scalar), 'ResetChains':len(resets),
                         'HeldDataBits':len(held), 'NativeInputDelayBits':8, 'NativeQueryPairs':len(queries), 'PinCount':pins['TopPortCount'], **stats},
              'InputSHA256':{str(p):h for p,h in watched.items()},
              'ExternalACTimingAccepted':False, 'NativeElectricalSettingsVerified':False,
              'AnalogMTBFProven':False, 'AllCDCUniversallyProven':False, 'HardwareReleaseAllowed':False,
              'HardwareAccessed':False, 'EDAExecuted':False,
              'Limits':'Scoped application CDC and native mapping only. Shared reset/protocol assumptions, external PCLK/data budgets, analog behavior and board acceptance remain separate.'}
    output_dir = prep.work_path(output_dir); require(not output_dir.exists(), 'fresh raw IO/CDC output directory required')
    output_dir.mkdir()
    inspect.diagnostic.write(output_dir / 'io-cdc.json', result)
    (output_dir / 'query-body.tcl').write_text(body, encoding='ascii', newline='\n')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--export-receipt', type=Path, required=True)
    p.add_argument('--effect', type=Path)
    p.add_argument('--io-query', type=Path)
    p.add_argument('--output-dir', type=Path, required=True)
    a = p.parse_args(); r = run(a.export_receipt, a.output_dir, a.effect, a.io_query)
    print(json.dumps({k:r[k] for k in ('StructuralAuditPassed', 'ScopedDigitalChecksPassed', 'Blockers', 'Summary')}))


if __name__ == '__main__': main()
