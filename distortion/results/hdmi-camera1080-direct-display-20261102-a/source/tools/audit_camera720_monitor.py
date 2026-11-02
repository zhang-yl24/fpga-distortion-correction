"""Pure-CPU structural checks for the current 720p monitor and synchronizers.

Native path queries are requests, never timing results. The held snapshot is
inventoried separately; topology alone cannot prove its complete handshake.
"""
from collections import defaultdict
import itertools
import re

import audit_camera_vga_cdc as base

require, one, canon = base.require, base.one, base.canon
PREFIX = 'camera_configuration/monitor/'


class Graph(base.Graph):
    def lut_gate(self, name, output, first, release):
        cell = self.cells[name]
        require(cell['Primitive'] == 'V_LUT6CARRY' and output in ('Z', 'Z5'), 'unsupported interstage gate')
        relevant, _ = immediate_support(cell, output)
        require(relevant == {first, release}, 'interstage gate has unrelated Boolean support')
        for a, b in itertools.product((0, 1), repeat=2):
            require(lut_value(cell, output, {first: a, release: b}) == (a & b),
                    'interstage LUT differs from first AND release')
        for other in ('Z', 'Z5', 'COUT'):
            if other != output and cell['Ports'].get(other):
                dependencies, _ = immediate_support(cell, other)
                require(first not in dependencies, 'first stage escapes shared native LUT/carry output')
        return {'Cell': name, 'Output': output, 'Truth': 'first_stage AND local_release',
                'ReleaseNet': release, 'ExhaustiveAssignments': 4,
                'FirstStageInputPins': [pin for pin, net in cell['Ports'].items() if net == first],
                'NativeLUTSelectorsChecked': True}


def support(g, net, active=()):
    """Exact scalar LUT support, stopping at registers and primary inputs."""
    require(net not in active, 'combinational cycle in monitor cone')
    if net in ("1'b0", "1'b1"):
        return set()
    drivers = g.outputs.get(net, [])
    if not drivers:
        return {('primary', net)}
    name, pin = one(drivers, 'monitor cone driver '+net)
    cell = g.cells[name]
    if name in g.ff:
        require(pin == 'Q', 'non-Q sequential source')
        return {('ff', name)}
    kind, ports = cell['Primitive'], cell['Ports']
    if kind in ('V_BUF', 'V_INV'):
        require(pin == 'Z', 'unexpected buffer output')
        return support(g, ports['I'], active+(net,))
    if kind in ('V_IBUF', 'V_INBUFG'):
        require(pin == 'O', 'unexpected input buffer output')
        return support(g, ports['I'], active+(net,))
    require(kind == 'V_LUT6CARRY' and pin in ('Z', 'Z5', 'COUT'),
            'unsupported monitor cone cell: '+name+'/'+pin)
    relevant, _ = immediate_support(cell, pin)
    result = set()
    for input_net in relevant:
        result |= support(g, input_net, active+(net,))
    return result


def cone_ff(g, net):
    leaves = support(g, net)
    require(all(kind == 'ff' for kind, _ in leaves), 'monitor cone includes an unreviewed primary input')
    return {name for _, name in leaves}


def possible_values(g, net, fixed, active=()):
    """Conservative Boolean cofactor: unknown leaves vary independently."""
    require(net not in active, 'cycle in sticky-fault cofactor')
    if net in fixed:
        return {fixed[net]}
    if net in ("1'b0", "1'b1"):
        return {int(net[-1])}
    drivers = g.outputs.get(net, [])
    if not drivers:
        return {0, 1}
    name, pin = one(drivers, 'cofactor driver')
    if name in g.ff:
        return {0, 1}
    c = g.cells[name]
    if c['Primitive'] in ('V_BUF', 'V_INV'):
        values = possible_values(g, c['Ports']['I'], fixed, active+(net,))
        return values if c['Primitive'] == 'V_BUF' else {1-v for v in values}
    if c['Primitive'] != 'V_LUT6CARRY' or pin not in ('Z', 'Z5', 'COUT'):
        # Opaque dependencies vary freely; a singleton result is still a proof.
        return {0, 1}
    relevant, _ = immediate_support(c, pin)
    values = {n: possible_values(g, n, fixed, active+(net,)) for n in relevant}
    names = sorted(values)
    result = set()
    for items in itertools.product(*(values[n] for n in names)):
        result.add(lut_value(c, pin, dict(zip(names, items))))
    return result


def encoded_sticky_fault(g, source, first, source_release, destination_release):
    """Audit the observed active-low fault-presence recoding, not its code bits."""
    cell = g.ff[source]
    q = cell['Ports']['Q']
    srq = g.ff[source_release]['Ports']['Q']
    drq = g.ff[destination_release]['Ports']['Q']
    require(canon(q) == PREFIX+'source_fault_reg[0]', 'unreviewed fault encoding')
    require(cell['Primitive'] == 'V_FFASYN' and cell['Parameters']['SET_RESET'] == '"SET"'
            and cell['Parameters']['INIT'] == "1'b1", 'encoded healthy state must reset to one')
    require(g.clear_expression(cell['Ports']['SR']) == g.clear_expression(g.ff[source_release]['Ports']['SR']),
            'encoded fault reset is not monitor reset')
    require(possible_values(g, cell['Ports']['D'], {q: 0, srq: 1}) == {0},
            'active-low encoded fault may deassert after failure')
    for source_value, released in itertools.product((0, 1), repeat=2):
        require(possible_values(g, g.ff[first]['Ports']['D'], {q: source_value, drq: released})
                == {(1-source_value) & released}, 'fault first-stage polarity/gating differs')
    return {'Encoding': 'active-low fault-present flag', 'ResetValue': 1,
            'StickyLowWhileSourceReleased': True, 'EnableMayHoldExistingFault': True,
            'FirstStageFunction': 'not encoded_fault AND destination_release',
            'OriginalNumericFaultCodeEquivalenceProved': False}


def chain(g, first, second, label, release=None):
    return g.chain(first, second, label, None if release is None else g.ff[release]['Ports']['Q'])


def monitor_gray(g):
    rows = []
    release = g.by_q(PREFIX+'r_reset[1]')
    for family, width in (('edge', 32), ('vs', 16), ('href', 16)):
        for bit in range(width):
            first = g.by_q(PREFIX+family+f'_meta[{bit}]')
            second = g.by_q(PREFIX+family+f'_sync[{bit}]')
            row = chain(g, first, second, family+f'[{bit}]', release)
            origins = cone_ff(g, g.ff[first]['Ports']['D'])
            sources = {n for n in origins if g.clock(g.ff[n]['Ports']['CK'])['Domain'] == 'camera_pclk'}
            source = one(sorted(sources), 'registered camera Gray origin')
            require(origins <= {source, release}, 'Gray first-stage cone includes unrelated registers')
            require(canon(g.ff[source]['Ports']['Q']) == PREFIX+family+f'_gray[{bit}]',
                    'Gray source register identity differs')
            require(row['DestinationClock'] == 'board27', 'monitor Gray destination is not reference clock')
            row.update(Source=source, SourcePorts=g.ff[source]['Ports'], SourceClock='camera_pclk',
                       Group=PREFIX+family+'_meta', Width=width, Bit=bit,
                       NativeEndpoint=base.native_parent(first)+'/D',
                       FirstStageConeRegisters=sorted(origins),
                       SourceRegisteredGrayRTLRequired=True)
            rows.append(row)
    return rows


def monitor_scalar(g):
    rows = []
    specs = [('request_sync', 'p_reset', 'snapshot_request', 'board27', 'camera_pclk'),
             ('ack_sync', 'r_reset', 'snapshot_ack', 'camera_pclk', 'board27'),
             ('healthy_sync', 'r_reset', 'source_healthy', 'camera_pclk', 'board27'),
             ('failed_sync', 'r_reset', None, 'camera_pclk', 'board27')]
    for field, reset, source_name, source_clock, destination in specs:
        first, second = (g.by_q(PREFIX+field+f'[{i}]') for i in (0, 1))
        release = g.by_q(PREFIX+reset+'[1]')
        row = chain(g, first, second, PREFIX+field, release)
        require(row['DestinationClock'] == destination, 'monitor scalar destination domain differs')
        origins = cone_ff(g, g.ff[first]['Ports']['D'])
        sources = {n for n in origins if g.clock(g.ff[n]['Ports']['CK'])['Domain'] == source_clock}
        require(sources and origins <= sources | {release}, 'scalar first-stage cone includes unrelated registers')
        if source_name:
            source = one(sorted(sources), 'scalar origin')
            require(canon(g.ff[source]['Ports']['Q']) == PREFIX+source_name, 'scalar origin identity differs')
        else:
            if len(sources) == 1 and canon(g.ff[next(iter(sources))]['Ports']['Q']) == PREFIX+'source_fault_reg[0]':
                row['NativeStickyFaultEncoding'] = encoded_sticky_fault(
                    g, next(iter(sources)), first, g.by_q(PREFIX+'p_reset[1]'), release)
            else:
                require(all(re.fullmatch(re.escape(PREFIX)+r'source_fault\[\d+\]', canon(g.ff[n]['Ports']['Q']))
                            for n in sources), 'failed synchronizer origin is not sticky fault register reduction')
        row.update(SourceClock=source_clock, SourceRegisters=sorted(sources),
                   FirstStageConeRegisters=sorted(origins),
                   SourceProtocol='sticky fault OR-reduction' if source_name is None else source_name,
                   SourceProtocolPhysicalProofComplete=False)
        rows.append(row)
    return rows


def application_scalars(g):
    """New initializer hierarchy; all application chains use current graph."""
    rows = []
    direct = [('board_failed_core[0]/', 'board_failed_core[1]')]
    for prefix in ('camera_configuration/initializer/bus/', 'hdmi_configuration/bus/'):
        direct += [(prefix+x+'_meta/', prefix+x+'_sampled') for x in ('scl', 'sda')]
    direct += [('system/'+x+'[0]/', 'system/'+x+'[1]') for x in
               ('done_sync', 'grant_ack_sync', 'request_sync', 'scan_abort_sync', 'scan_failed_sync')]
    direct += [('system/scan_enable_sync[1]/', 'system/scan_enable_sync[1]')]
    direct += [('system/output_video/'+x+'[0]/', 'system/output_video/'+x+'[1]')
               for x in ('done_ack_sync', 'grant_sync')]
    for prefix, q in direct:
        rows.append(g.chain(g.first_prefix(prefix), g.by_q(q), q))
    gated = [('ddr_ready_ref[0]', 'nt_led[1]', 'ref_reset[1]'),
             ('video_lock_ref[0]', 'nt_led[2]', 'ref_reset[1]'),
             ('system_failed_ref[0]', 'system_failed_ref[1]', 'ref_reset[1]'),
             ('processed_bit_ref[0]', 'nt_led[6]', 'ref_reset[1]'),
             ('captured_bit_ref[0]', 'nt_led[5]', 'ref_reset[1]')]
    gated += [(base.CAP+x+'[0]', base.CAP+x+'[1]', base.CAP+'cam_reset[1]')
              for x in ('ack_sync', 'grant_sync', 'enable_cam')]
    gated += [(base.CAP+'done_sync[0]', base.CAP+'done_sync[1]', 'system/input_link/input_dma/sys_reset[1]')]
    for first_q, second_q, release in gated:
        rows.append(chain(g, g.by_q(first_q), g.by_q(second_q), first_q, g.by_q(release)))
    return rows


def reset_chains(g):
    rows, replicas = [], []
    for first in sorted(g.ff):
        if first.startswith('u_ddr3_test_h/') or '/FFAPP' in first or not re.search(r'reset(?:_sync)?\[0\]/', first):
            continue
        cell, p = g.ff[first], g.ff[first]['Ports']
        require(g.constant_one(p['D']), 'reset first stage must shift constant one')
        require(cell['Primitive'] == 'V_FFASYN' and cell['Parameters'].get('INIT') == "1'b0"
                and cell['Parameters'].get('SET_RESET') == '"RESET"', 'reset first stage is not async clear')
        loads = [(n, pin) for n, pin in g.refs[p['Q']] if (n, pin) != (first, 'Q')]
        require(loads and all(n in g.ff and pin == 'D' for n, pin in loads), 'reset first stage functional fanout')
        chains = [g.chain(first, n, first, replicated=len(loads) > 1) for n, _ in loads]
        if len(loads) == 1:
            rows.extend(chains)
        else:
            replicas.append({'First': first, 'SecondStageCount': len(chains), 'Chains': chains,
                             'SeparateReleaseEdgesPossible': True, 'FirstStageOnlyFeedsSecondStages': True})
    require(rows, 'no application reset structures found')
    for family in ('p_reset', 'r_reset'):
        require(any(row['First'].startswith(PREFIX+family+'[0]/') for row in rows)
                or any(row['First'].startswith(PREFIX+family+'[0]/') for row in replicas),
                'missing new monitor reset family '+family)
    return {'SingleChains': rows, 'ReplicatedTrees': replicas}


def held_snapshot_inventory(g):
    bits = {}
    for name, cell in g.ff.items():
        match = re.fullmatch(re.escape(PREFIX)+r'held_snapshot\[(\d+)\]', canon(cell['Ports']['Q']))
        if match:
            bit = int(match[1])
            require(bit not in bits and 0 <= bit <= 104, 'duplicate/outside held snapshot register')
            require(g.clock(cell['Ports']['CK'])['Domain'] == 'camera_pclk', 'held snapshot in wrong domain')
            bits[bit] = name
    require(set(range(73, 105)) <= set(bits), 'held good-frame count has missing native bits')
    rows = []
    for bit, name in sorted(bits.items()):
        destinations = []
        # Record exact logical first-level consumers; query planning below
        # requires further sequential traversal and does not call this timing.
        for cell, pin in g.refs[g.ff[name]['Ports']['Q']]:
            if (cell, pin) != (name, 'Q'):
                destinations.append({'Cell': cell, 'Pin': pin, 'Primitive': g.cells[cell]['Primitive']})
        rows.append({'Bit': bit, 'Source': name, 'Ports': g.ff[name]['Ports'],
                     'FirstLevelConsumers': destinations})
    return {'LogicalWidth': 105, 'SurvivingBits': sorted(bits), 'Rows': rows,
            'AbsentLogicalBits': sorted(set(range(105))-set(bits)),
            'AbsentBitsClassifiedAsOptimizedDiagnostics': False,
            'HandshakeRTL': 'source updates held bus with snapshot_ack after request_sync; destination waits ack_sync then settle; new request waits ack_seen',
            'HeldBusEndpointTraversalComplete': False, 'HeldBusPhysicalBoundComplete': False,
            'NativeHandshakeConeProofComplete': False,
            'Limits': 'Inventory only. Missing diagnostic fields and combinational consumers need explicit review; no handshake or physical acceptance.'}


def held_snapshot(g):
    result = held_snapshot_inventory(g)
    q = lambda name: g.ff[g.by_q(PREFIX+name)]['Ports']['Q']
    ports = lambda name: g.ff[g.by_q(PREFIX+name)]['Ports']
    p_release, r_release = q('p_reset[1]'), q('r_reset[1]')
    request, ack = q('request_sync[1]'), q('snapshot_ack')
    ack_ports = ports('snapshot_ack')
    require(set(range(73, 105)) | {0, 1, 2, 3, 5} == set(result['SurvivingBits']),
            'surviving held fields differ from consumed good/healthy/fault bits')
    for source_request, acknowledged in itertools.product((0, 1), repeat=2):
        fixed = {p_release: 1, request: source_request, ack: acknowledged}
        require(possible_values(g, ack_ports['CE'], fixed) == {source_request ^ acknowledged},
                'snapshot ack clock enable does not encode pending request')
        require(possible_values(g, ack_ports['D'], fixed) == {source_request}, 'snapshot ack value differs from request')
    for row in result['Rows']:
        p = row['Ports']
        require(p['CK'] == ack_ports['CK'], 'held field and acknowledgement clocks differ')
        for source_request, acknowledged in itertools.product((0, 1), repeat=2):
            fixed = {p_release: 1, request: source_request, ack: acknowledged}
            require(possible_values(g, p['CE'], fixed) == {source_request ^ acknowledged},
                    'held field enable differs from snapshot acknowledgement')
        row['SourceAckResetExpressionIdentical'] = (g.clear_expression(p['SR']) == g.clear_expression(ack_ports['SR']))
    dest_request, ack_seen, ack_sync, settle = (q(n) for n in ('snapshot_request', 'ack_seen', 'ack_sync[1]', 'settle'))
    for seen, synchronized, settled in itertools.product((0, 1), repeat=3):
        fixed = {r_release: 1, ack_seen: seen, ack_sync: synchronized, settle: settled}
        require(possible_values(g, ports('settle')['D'], fixed) == {(seen ^ synchronized) & (1-settled)},
                'destination settle cycle differs')
        require(possible_values(g, ports('ack_seen')['CE'], fixed) == {settled}, 'ack_seen can change outside capture')
        require(possible_values(g, ports('ack_seen')['D'], fixed) == {synchronized}, 'ack_seen does not capture synchronized ack')
    for req, seen, settled in itertools.product((0, 1), repeat=3):
        if req != seen or settled:
            fixed = {r_release: 1, dest_request: req, ack_seen: seen, settle: settled}
            require(possible_values(g, ports('snapshot_request')['D'], fixed) == {req},
                    'new request may issue before held snapshot is consumed')
    data_pairs = []
    for row in result['Rows']:
        bit = row['Bit']
        destination = 'good_frames['+str(bit-73)+']' if bit >= 73 else ('held_healthy' if bit == 0 else 'held_fault['+str(bit-1)+']')
        d = ports(destination)
        require(g.clock(d['CK'])['Domain'] == 'board27', 'held destination outside reference clock')
        for settled, value in itertools.product((0, 1), repeat=2):
            fixed = {r_release: 1, settle: settled, row['Ports']['Q']: value}
            require(possible_values(g, d['CE'], fixed) == {settled}, 'held field destination enable differs')
            require(possible_values(g, d['D'], fixed) == {value}, 'held field data mapping differs')
        data_pairs.append({'Bit': bit, 'Source': row['Source'], 'Destination': g.by_q(PREFIX+destination),
                           'DestinationPorts': d, 'DataMatchesWhenReleased': True})
    result.update(NativeHandshakeConeProofComplete=True,
                  NormalReleasedOperationOnly=True, SourceHoldsUntilNextRequest=True,
                  DestinationAddsSettleCycleAfterAck=True, NewRequestWaitsForAckSeen=True,
                  CapturePairs=data_pairs,
                  AbsentBitsClassifiedAsOptimizedDiagnostics=True,
                  AbsentBitClasses={'UnusedDiagnosticOutputs': list(range(9, 73)),
                                    'ConstantFaultCodeZeroBits': [4, 6, 7, 8]},
                  HeldBusPhysicalBoundComplete=False,
                  Limits='Released-operation Boolean handshake topology only. Physical source-to-all-consumer delay/reset recovery and analog metastability remain separate.')
    return result


NATIVE_LUT_REFERENCE = {
    'RelativePDSPath': 'arch/vendor/pango/verilog/bsim/V_LUT6CARRY.v',
    'SHA256': 'aa7ca57e8ce35845b0d61b02358d4a546facc52be65ec1ca5e68fe37a8bdcf98',
    'Scope': 'Two-state Boolean truth, explicit I5_TO_LUT/CARRY selectors; no timing/unknown simulation.'}


def lut_value(cell, output, assignment):
    """Independent Boolean implementation of the recorded native primitive."""
    p, parameters = cell['Ports'], cell['Parameters']
    lut_select = parameters.get('I5_TO_LUT', '"FALSE"')
    carry_select = parameters.get('I5_TO_CARRY', '"TRUE"')
    require(lut_select in ('"TRUE"', '"FALSE"') and carry_select in ('"TRUE"', '"FALSE"'),
            'unknown native LUT/carry selector')
    values = {**assignment, "1'b0": 0, "1'b1": 1}
    bit = lambda name: values.get(p[name], 0)
    index = sum(bit('I'+str(i)) << i for i in range(5))
    init = int(parameters['INIT'][4:], 16)
    low, high = (init >> index) & 1, (init >> (32+index)) & 1
    if output == 'Z5':
        return low
    if output == 'Z':
        selector = bit('I5') if lut_select == '"TRUE"' else bit('CIN')
        return high if selector else low
    require(output == 'COUT', 'unknown native LUT output')
    alternate = bit('I5') if carry_select == '"TRUE"' else high
    return bit('CIN') if low else alternate


def immediate_support(cell, output):
    kind, ports = cell['Primitive'], cell['Ports']
    if kind in ('V_BUF', 'V_INV'):
        require(output == 'Z', 'unreviewed buffer output')
        return {ports['I']}, False
    require(kind == 'V_LUT6CARRY', 'unreviewed held-bus fanout primitive')
    names = sorted({ports[p] for p in ('I0', 'I1', 'I2', 'I3', 'I4', 'I5', 'CIN')}
                   - {"1'b0", "1'b1"})
    relevant = set()
    for bits in itertools.product((0, 1), repeat=len(names)):
        assignment = dict(zip(names, bits))
        expected = lut_value(cell, output, assignment)
        for name in names:
            if expected != lut_value(cell, output, {**assignment, name: 1-assignment[name]}):
                relevant.add(name)
    return relevant, False


def held_first_sinks(g, held):
    rows, cache, queries = [], {}, []
    for item in held['Rows']:
        seen, active, sinks, carries = set(), set(), set(), set()
        def visit(net, driver):
            require(net not in active, 'held bus combinational cycle')
            if net in seen:
                return
            active.add(net)
            for name, pin in g.refs[net]:
                if (name, pin) == driver:
                    continue
                c = g.cells[name]
                if name in g.ff:
                    require(pin in ('D', 'CE', 'SR'), 'held bus reaches nondata sequential pin')
                    require(name.startswith(PREFIX) and g.clock(c['Ports']['CK'])['Domain'] == 'board27',
                            'held bus first consumer escaped monitor/reference clock')
                    sinks.add((name, pin))
                    continue
                require(c['Primitive'] in ('V_LUT6CARRY', 'V_BUF', 'V_INV'), 'unreviewed held bus primitive: '+name)
                outputs = ('Z', 'Z5', 'COUT') if c['Primitive'] == 'V_LUT6CARRY' else ('Z',)
                for output in outputs:
                    next_net = c['Ports'].get(output)
                    if not next_net:
                        continue
                    key = (name, output)
                    if key not in cache:
                        cache[key] = immediate_support(c, output)
                    inputs, conservative = cache[key]
                    if net in inputs:
                        if conservative:
                            carries.add(name)
                        visit(next_net, (name, output))
            active.remove(net)
            seen.add(net)
        visit(item['Ports']['Q'], (item['Source'], 'Q'))
        require(sinks, 'held snapshot bit has no first sequential consumer')
        consumers = []
        for name, pin in sorted(sinks):
            endpoint = base.native_parent(name)+'/'+pin
            consumers.append({'Cell': name, 'Pin': pin, 'Endpoint': endpoint,
                              'Ports': g.ff[name]['Ports'], 'DestinationClock': 'board27'})
            queries.append({'Label': PREFIX+f"held_snapshot[{item['Bit']}] -> "+canon(g.ff[name]['Ports']['Q']),
                            'Source': base.native_parent(item['Source'])+'/CLK', 'Endpoint': endpoint,
                            'SourceClock': 'camera_pclk', 'DestinationClock': 'board27',
                            'Purpose': 'held bus source to every first sequential consumer; native LUT/carry Boolean dependency traversal'})
        rows.append({'Bit': item['Bit'], 'Source': item['Source'], 'Consumers': consumers,
                     'VisitedNets': len(seen), 'ConservativeCarryCells': sorted(carries)})
    return {'Rows': rows, 'Queries': queries, 'FirstSequentialPathPairs': len(queries),
            'TraversalCompleteWithinReviewedPrimitiveSet': True,
            'CarrySensitizationProved': True, 'NativeLUTReference': NATIVE_LUT_REFERENCE, 'PhysicalBoundComplete': False}


def query_pairs(gray, scalars, resets, held=None):
    queries = []
    for row in gray:
        queries.append({'Label': row['Label'], 'Source': base.native_parent(row['Source'])+'/CLK',
                        'Endpoint': row['NativeEndpoint'], 'Purpose': 'registered Gray source to first stage',
                        'SourceClock': row['SourceClock'], 'DestinationClock': row['DestinationClock']})
    chains = gray+scalars+resets['SingleChains']+[c for r in resets['ReplicatedTrees'] for c in r['Chains']]
    for row in chains:
        queries.extend(row['NativeQueries'])
    for row in scalars:
        # New monitor source registers are explicitly traced through the
        # normal release gate, so query their asynchronous first-stage paths
        # as well as ordinary first-to-second-stage timing.
        for source in row.get('SourceRegisters', []):
            queries.append({'Label': row['Label'], 'Source': base.native_parent(source)+'/CLK',
                            'Endpoint': base.native_parent(row['First'])+'/D',
                            'SourceClock': row['SourceClock'], 'DestinationClock': row['DestinationClock'],
                            'Purpose': 'monitor registered scalar source to first synchronizer stage'})
    if held is not None:
        for row in held['CapturePairs']:
            queries.append({'Label': PREFIX+'held_snapshot['+str(row['Bit'])+']',
                            'Source': base.native_parent(row['Source'])+'/CLK',
                            'Endpoint': base.native_parent(row['Destination'])+'/D',
                            'SourceClock': 'camera_pclk', 'DestinationClock': 'board27',
                            'Purpose': 'held snapshot data to capture register; additional comparison consumers pending'})
        if 'AllFirstConsumers' in held:
            queries.extend(held['AllFirstConsumers']['Queries'])
    seen = {}
    for query in queries:
        key = (query['Source'], query['Endpoint'])
        if key not in seen:
            seen[key] = query
    return [seen[key] for key in sorted(seen)]
