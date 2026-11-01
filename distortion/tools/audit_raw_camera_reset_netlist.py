"""Prove the registered raw candidate's narrow DDR reset connectivity.

This is a strict functional-export audit, not timing-exception approval. It
accepts only an initialized sticky startup FF, exact inversion of its Q for
DDR clear, the actual two-stage LOCK synchronizer, and current query targets.
It does not assume an external reset_n port or use a historical target count.
"""
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import json
import re

import audit_ddr_entry_reset_netlist as syntax
import prepare_raw_camera_reset_scope as reference

TARGET = 'raw_camera_capture_cam2_reset'
require, sha = reference.require, reference.sha


def lut_support(init, constants):
    """Exact Boolean support after tied inputs; inspect all remaining rows."""
    addresses = [a for a in range(64) if all(((a >> i) & 1) == v for i, v in constants.items())]
    return [i for i in range(6) if i not in constants and
            any(((init >> a) & 1) != ((init >> (a ^ (1 << i))) & 1) for a in addresses)]


def audit_text(text, queries):
    require(re.findall(r'(?m)^module\s+(\w+)\b', text) == [TARGET], 'one exact raw-reset module required')
    normalized = re.sub(r'(?m)^(module\s+)' + TARGET + r'\b', r'\1board1080_top', text, count=1)
    clean, cells = syntax.parse(normalized)
    refs = defaultdict(list)
    for cell in cells:
        for pin, value in cell.ports.items():
            for net in set(syntax.TOKEN.findall(value)):
                refs[net].append((cell, pin))

    def one(values, label):
        require(len(values) == 1, label + ' must match once')
        return values[0]

    def driver(net, primitive, pin):
        return one([c for c, p in refs[net] if c.primitive == primitive and p == pin and c.ports[p] == net],
                   primitive + '.' + pin + ' driver for ' + net)

    def record(cell):
        return {'Name': cell.name, 'Primitive': cell.primitive, 'Parameters': cell.parameters,
                'Ports': cell.ports, 'Line': clean.count('\n', 0, cell.offset) + 1}

    require(isinstance(queries, list) and queries, 'current native reset queries required')
    require(all(isinstance(q, dict) and isinstance(q.get('Targets'), list)
                and len(q['Targets']) == len(set(q['Targets'])) == q.get('ExpectedTargetCount')
                and q.get('ExpectedFromCount') == 1 for q in queries), 'invalid query inventory')
    require(len({q['Source'] for q in queries}) == len(queries), 'duplicate native source query')
    entry_groups = [q for q in queries if q.get('EntryRDC') is True]
    require(len(entry_groups) == 1 and len(entry_groups[0]['Targets']) == 1, 'one report-derived entry pair required')
    entry = entry_groups[0]
    require(entry.get('Family') == 'entry_rdc' and
            entry['Source'].rsplit('/', 2)[0] == 'startup/power_ready' and entry['Source'].endswith('/CLK'),
            'entry source must be current registered startup FF')
    power = one([c for c in cells if c.name.startswith(entry['Source'].rsplit('/', 1)[0] + '/')
                 and c.primitive in ('V_FFSYN', 'V_FFASYN')], 'native power-ready FF')
    require(set(power.ports) == {'Q', 'CE', 'CK', 'D', 'SR'}, 'unexpected power-ready ports')
    require(power.parameters.get('GRS_EN') == '"TRUE"' and power.parameters.get('INIT') == "1'b0"
            and power.parameters.get('SET_RESET') == '"RESET"'
            and power.parameters.get('LRS_EN') in ('"TRUE"', '"FALSE"'), 'startup FF initialization/reset differs')
    power_net = power.ports['Q']
    require(syntax.TOKEN.fullmatch(power_net), 'startup Q must be one scalar net')
    require(not any(n in clean for n in ('nt_reset_n', 'input reset_n')), 'raw candidate unexpectedly uses external reset_n')

    cone_cells, cone_nets, lut_support_records = {}, set(), {}

    def boolean(net, ready, stack=()):
        if net in ("1'b0", "1'b1"):
            return int(net[-1])
        if net == power_net:
            return ready
        require(syntax.TOKEN.fullmatch(net) and net not in stack and len(stack) < 32,
                'non-scalar, cyclic, or excessively deep reset cone')
        options = []
        for cell, pin in refs[net]:
            if cell.ports[pin] == net and pin == 'Z' and cell.primitive in ('V_BUF', 'V_INV', 'V_LUT6CARRY'):
                options.append(cell)
        cell = one(options, 'allowed boolean driver for ' + net)
        cone_cells[cell.name] = cell
        cone_nets.add(net)
        require(len(cone_cells) <= 64, 'unexpectedly large raw reset cone')
        if cell.primitive in ('V_BUF', 'V_INV'):
            require(set(cell.ports) == {'I', 'Z'} and not cell.parameters, 'unsupported scalar buffer/inverter')
            value = boolean(cell.ports['I'], ready, (*stack, net))
            return value if cell.primitive == 'V_BUF' else 1 - value
        require(cell.parameters.get('I5_TO_LUT') == '"TRUE"' and
                re.fullmatch(r"64'h[0-9a-fA-F]{16}", cell.parameters.get('INIT', '')),
                'unproved carry-mode/LUT reset function')
        inputs = [cell.ports.get('I' + str(i), '') for i in range(6)]
        init = int(cell.parameters['INIT'][4:], 16)
        constants = {i: int(v[-1]) for i, v in enumerate(inputs) if v in ("1'b0", "1'b1")}
        support = lut_support(init, constants)
        # Packed LUT6/LUT5 may use the other output for unrelated DDR data.
        # Prove irrelevance of unused inputs over every selected truth-table row.
        index = sum(v << i for i, v in constants.items())
        index += sum(boolean(inputs[i], ready, (*stack, net)) << i for i in support)
        lut_support_records[cell.name] = {'Output': 'Z', 'TiedInputs': constants,
                                         'EffectiveSupportPins': ['I' + str(i) for i in support]}
        return (init >> index) & 1

    # This deliberately rejects an unrecognized synthesized sticky shape. A
    # constant-one D and inactive SR prove Q can only hold or become one for
    # any CE behavior; exact startup latency is established by source-bound RTL
    # simulation separately, not inferred from the FF's name.
    require([boolean(power.ports['D'], ready) for ready in (0, 1)] == [1, 1],
            'startup sticky property requires proved constant-one D')
    require([boolean(power.ports['SR'], ready) for ready in (0, 1)] == [0, 0],
            'startup FF has an active or unproved local reset')

    power_clock_nets = set()

    def clock_to_board(net, seen=()):
        require(net not in seen and len(seen) < 12, 'clock path is cyclic or too deep')
        power_clock_nets.add(net)
        candidates = [c for c, p in refs[net] if c.ports[p] == net and
                      (c.primitive, p) in (('V_BUF', 'Z'), ('V_USCM', 'CLKOUT'), ('V_IBUF', 'O'))]
        cell = one(candidates, 'startup clock driver')
        if cell.primitive == 'V_IBUF':
            require(cell.ports.get('I') == 'clk_27m', 'startup clock is not clk_27m')
            return [record(cell)]
        if cell.primitive == 'V_USCM':
            require(cell.parameters.get('USCM_MODE') == '"BUF_A"', 'startup clock mux is not fixed BUF_A')
            upstream = cell.ports.get('CLK0', '')
        else:
            require(set(cell.ports) == {'I', 'Z'} and not cell.parameters, 'startup clock buffer differs')
            upstream = cell.ports['I']
        return [record(cell)] + clock_to_board(upstream, (*seen, net))

    power_clock = clock_to_board(power.ports['CK'])
    entry_cells = [c for c in cells if c.name.startswith(syntax.SYNC)]
    chain = [c for c in entry_cells if c.primitive in ('V_FFASYN', 'V_FFSYN')]
    entry_helpers = [c for c in entry_cells if c not in chain]
    require(all(c.primitive in ('V_INV', 'V_BUF') for c in entry_helpers),
            'unproved extra logic in packed entry synchronizer')
    require(len(chain) == 2 and all(c.primitive == 'V_FFASYN' for c in chain), 'two asynchronous FF stages required')
    first = one([c for c in chain if c.ports.get('D') == syntax.LOCK], 'LOCK first stage')
    second = one([c for c in chain if c.ports.get('Q') == syntax.OUTPUT], 'second stage output')
    require(first is not second and first.ports['Q'] == second.ports['D'], 'direct two-stage cascade required')
    for cell in chain:
        require(set(cell.ports) == {'Q', 'CE', 'CK', 'D', 'SR'} and cell.ports['CE'] == "1'b1", 'unexpected stage controls')
        require(cell.parameters == {'GRS_EN': '"TRUE"', 'SET_RESET': '"RESET"', 'LRS_EN': '"TRUE"', 'INIT': "1'b0"},
                'stage must be an initialized asynchronous-clear FF')
    require(first.ports['CK'] == second.ports['CK'] and first.ports['SR'] == second.ports['SR'],
            'stages must share clock and clear')
    middle = first.ports['Q']
    require({(c.name, pin) for c, pin in refs[middle]} == {(first.name, 'Q'), (second.name, 'D')},
            'first-stage functional fanout must only be second stage')
    leaf = driver(first.ports['CK'], 'V_BUF', 'Z')
    require(leaf.ports == {'Z': first.ports['CK'], 'I': syntax.RST_CLOCK}, 'wrong entry clock buffer')
    mux = driver(syntax.RST_CLOCK, 'V_USCM', 'CLKOUT')
    require(mux.parameters.get('USCM_MODE') == '"BUF_A"', 'rst clock is muxed')
    pll = driver(syntax.LOCK, 'V_GPLL', 'LOCK')
    require(mux.ports.get('CLK0') == pll.ports.get('CLKOUT0'), 'entry clock and LOCK use different PLLs')
    require({(c.name, pin) for c, pin in refs[syntax.LOCK]} == {(pll.name, 'LOCK'), (first.name, 'D')},
            'LOCK has feedback or extra fanout')
    clear_records = []
    for net in sorted({first.ports['SR'], pll.ports['RST']}):
        truth = [boolean(net, ready) for ready in (0, 1)]
        require(truth == [1, 0], 'raw DDR clear is not exact inversion of registered power_ready')
        clear_records.append({'Net': net, 'TruthAtReady0And1': truth,
                              'Loads': [{'Name': c.name, 'Primitive': c.primitive, 'Pin': pin} for c, pin in refs[net]]})
    require(all(c.name in cone_cells for c in entry_helpers),
            'packed entry helper is outside the proved reset cone')
    require(first.name.startswith(entry['Targets'][0].rsplit('/', 1)[0] + '/')
            and entry['Targets'][0].endswith('/RS'), 'entry query target is not the actual first stage')
    output_loads = [(c, pin) for c, pin in refs[syntax.OUTPUT] if (c.name, pin) != (second.name, 'Q')]
    require(output_loads and all(c.primitive == 'V_INV' and pin == 'I' and c.name.startswith(
            (syntax.PREFIX + 'ddrphy_reset_ctrl/', syntax.PREFIX + 'u_ddrphy_gpll_phase/')) for c, pin in output_loads),
            'synchronized output has unexpected fanout')

    groups = []
    for query in queries:
        if query['EntryRDC']:
            continue
        require(query.get('Family') in ('dqs_reset', 'iol_reset', 'training_reset', 'cpd_reset'), 'unknown internal reset family')
        targets, target_nets = [], set()
        for target in query['Targets']:
            require(reference.SAFE.fullmatch(target), 'unsafe internal target')
            family = reference.classify({'Source': query['Source'], 'Endpoint': target,
                                         'LaunchClock': 'ddrphy_sysclk' if query['Family'] == 'training_reset' else 'rst_clk',
                                         'CaptureClock': 'phy_dq_sysclk_0' if query['Family'] == 'cpd_reset' else 'phy_dq_clk_0'})
            require(family == query['Family'], 'internal query family differs from actual named reset role')
            parent, pin = target.rsplit('/', 1)
            kinds = {'ISR_IOLHR': ('V_ISERDES_E2', 'RST'), 'OSR_IOLHR': ('V_OSERDES_E2', 'RST'),
                     'TSR': ('V_OSERDES_E2', 'RST'), 'RST_TRAINING_N': ('V_DDC_E2', 'RST_TRAINING_N'),
                     'RST': ('V_CLKPD' if 'cpd_inst' in parent else 'V_DDC_E2', 'RST')}
            require(pin in kinds, 'unsupported internal reset target pin')
            kind, exported = kinds[pin]
            cell = one([c for c in cells if c.name.startswith(parent + '/') and c.primitive == kind],
                       'actual direct reset target ' + target)
            net = cell.ports.get(exported, '')
            require(syntax.TOKEN.fullmatch(net), 'reset target is not a direct scalar net')
            target_nets.add(net)
            targets.append({'NativeTarget': target, 'FunctionalCell': cell.name,
                            'Primitive': cell.primitive, 'Pin': exported, 'Net': net})
        require(len(target_nets) == 1, 'native group targets do not share one reset net')
        net = target_nets.pop()
        source = driver(net, 'V_FFASYN', 'Q')
        require(source.name.startswith(query['Source'].rsplit('/', 1)[0] + '/'), 'native source differs from functional FF')
        clock = driver(source.ports['CK'], 'V_BUF', 'Z')
        expected_clock = 'core_clk' if query['Family'] == 'training_reset' else syntax.RST_CLOCK
        require(clock.ports == {'Z': source.ports['CK'], 'I': expected_clock}, 'internal reset source clock differs')
        require(sum(token == net for token in syntax.TOKEN.findall(clean)) == 1 + len(refs[net]),
                'unparsed alias/reference to internal reset ' + net)
        groups.append({'NativeSource': query['Source'], 'FunctionalSource': record(source),
                       'ClockBuffer': record(clock), 'TargetCount': len(targets), 'Targets': targets})
    critical = {middle, syntax.OUTPUT, syntax.LOCK, first.ports['CK'], syntax.RST_CLOCK,
                mux.ports['CLK0'], power_net, *cone_nets, *power_clock_nets}
    counts = Counter(token for token in syntax.TOKEN.findall(clean) if token in critical)
    for net in critical:
        require(counts[net] == 1 + len(refs[net]), 'unparsed alias/reference to ' + net)
    return {'Status': 'pass', 'Target': TARGET, 'ParsedPrimitiveCellCount': len(cells),
            'Stages': [record(first), record(second)], 'FirstStageFunctionalFanout': 1,
            'ClockBuffer': record(leaf), 'ClockMux': record(mux), 'StartupPLL': record(pll),
            'PowerReadyFF': record(power), 'PowerReadyClockPath': power_clock,
            'RegisteredStickyPropertyVerified': True, 'RawClearFunction': '~registered_power_ready',
            'ExternalResetPortAssumed': False, 'ClearRoots': clear_records,
            'BooleanConeCells': [record(c) for c in cone_cells.values()],
            'BooleanLUTCofactors': lut_support_records,
            'OutputLoadCount': len(output_loads), 'InternalDriverGroups': groups,
            'InternalFunctionalTargetsVerified': sum(g['TargetCount'] for g in groups),
            'CriticalNetReferenceCounts': dict(counts), 'AnalogMTBFProven': False,
            'FullStartupDelayNetlistEquivalenceProven': False, 'VendorResetContractProven': False,
            'OtherGlobalResetConsumersOnlyInventoried': True, 'TimingExceptionApplied': False,
            'TimingExceptionApproved': False, 'HardwareReleaseAllowed': False,
            'HeaderOnlyAdapter': TARGET + ' to board1080_top for strict V_* parsing'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('netlist', type=Path)
    parser.add_argument('--scope-plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.scope_plan.read_text(encoding='utf-8-sig'))
    require(plan.get('Schema') == 'raw-camera-reset-scope-proposal-v1' and plan.get('Target') == TARGET
            and plan.get('Complete') is True, 'complete raw scope proposal required')
    before = {str(p.resolve()): sha(p) for p in (args.netlist, args.scope_plan, Path(__file__))}
    result = audit_text(args.netlist.read_text(encoding='utf-8-sig'), plan['NativeQueries'])
    require(all(sha(path) == digest for path, digest in before.items()), 'input drift during graph audit')
    result['InputSHA256'] = before
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'Status': result['Status'], 'RegisteredStickyPropertyVerified': True,
                      'TimingExceptionApproved': False, 'HardwareReleaseAllowed': False}))


if __name__ == '__main__':
    main()
