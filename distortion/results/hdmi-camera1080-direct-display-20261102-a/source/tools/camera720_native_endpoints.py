"""CPU-only logical FF to native packed timing endpoint inventory.

The native CLK pin may launch two different packed FFs.  A packed LUT input
may feed Z, Z5, COUT, or several of them.  Preserve both logical FF identities,
the actual launch output, and every relevant receiving boundary pin.  This
module never runs PDS and never accepts native timing or authorizes hardware.
"""
import argparse
from collections import defaultdict
import copy
from datetime import datetime, timezone
import json
from pathlib import Path

import audit_camera720_io_cdc as structure
import audit_camera_vga_routes as adif

monitor, base = structure.monitor, structure.cdc
require, canon, sha = base.require, base.canon, base.sha
SELF = Path(__file__).resolve()


def indexed(value):
    if isinstance(value, str):
        return canon(value)
    require(len(value) == 3 and value[0] == 'INDEXED', 'unsupported native indexed net')
    return canon(value[1])+'['+value[2]+']'


def route_objects(path, wanted):
    """Parse native interface definitions and complete selected connectivity.

    The full dump is lexed and balanced; unrelated route annotations are not
    interpreted as timing.  Selection is by exact instance identity, never a
    regex whose truncated get_pins output could look complete.
    """
    cells, instances, pins = {}, {}, {}
    active, held, depth = None, [], 0
    for line in Path(path).open(encoding='utf-8-sig'):
        tokens = adif.TOKEN.findall(line)
        require(not adif.TOKEN.sub('', line).strip(), 'unparsed route dump tokens')
        start = depth
        depth += tokens.count('(')-tokens.count(')')
        require(depth >= 0, 'unbalanced route dump')
        if active is None and tokens[:2] == ['(', 'CELL'] and tokens[2].startswith('gop'):
            active, held = ('CELL', start), []
        elif active is None and tokens[:2] == ['(', 'INSTANCE'] and canon(tokens[2]) in wanted:
            active, held = ('INSTANCE', start), []
        elif active is None and tokens[:2] == ['(', 'NET']:
            active, held = ('NET', start), []
        if active is None:
            continue
        held.extend(tokens)
        if depth != active[1]:
            continue
        node = adif.expression(held)
        if active[0] == 'CELL':
            require(node[1] not in cells, 'duplicate native cell')
            cells[node[1]] = node
        elif active[0] == 'INSTANCE':
            name = canon(node[1])
            require(name not in instances and node[2][:2] == ['VIEWREF', 'OPER'], 'ambiguous native instance')
            ref = node[2][2]
            require(ref[0] == 'CELLREF' and ref[2][0] == 'OPERAREF', 'unsupported native instance reference')
            instances[name] = {'Cell': ref[1], 'Operator': ref[2][1]}
        else:
            array = isinstance(node[1], list)
            if array:
                require(node[1][0] == 'ARRAY', 'unsupported native array net')
            for connect in node[2:]:
                if connect[0] == 'ATTRIBUTE':
                    require(len(connect) >= 3, 'malformed native net attribute: '+str(connect)[:250])
                    continue
                require(connect[0] == 'CONNECT', 'unreviewed native NET child: '+str(connect)[:250])
                refs = connect[1:]
                if array:
                    require(refs and refs[0][0] == 'NETREF', 'array connect needs indexed net')
                    net, refs = indexed(refs[0][1]), refs[1:]
                else:
                    net = indexed(node[1])
                for p in refs:
                    require(p[0] == 'PORTREF', 'unsupported native net connection')
                    if len(p) == 2:  # top-level pad
                        continue
                    require(len(p) == 3 and p[2][0] == 'INSTREF', 'unsupported native instance connection')
                    inst = canon(p[2][1])
                    if inst not in wanted:
                        continue
                    key = inst, indexed(p[1])
                    require(key not in pins, 'native pin connected more than once')
                    pins[key] = net
        active, held = None, []
    require(depth == 0 and active is None, 'incomplete route dump')
    require(set(instances) == set(wanted), 'missing selected native instance')
    definitions = {}
    for cell_name in {v['Cell'] for v in instances.values()}:
        require(cell_name in cells, 'selected concrete native cell missing')
        node = cells[cell_name]
        views = [x for x in node[3:] if x[0] == 'VIEW']
        require(len(views) == 1 and views[0][1] == 'OPER', 'native cell interface differs')
        interfaces = [x for x in views[0][2:] if x[0] == 'INTERFACE']
        require(len(interfaces) == 1, 'missing native cell interface')
        ports = {}
        for p in interfaces[0][1:]:
            require(p[0] == 'PORT' and isinstance(p[1], str), 'unsupported native packed port')
            direction = [x[1] for x in p[2:] if x[0] == 'DIRECTION']
            require(len(direction) == 1 and p[1] not in ports, 'ambiguous native port direction')
            ports[p[1]] = direction[0]
        definitions[cell_name] = {'Operator': node[2][1], 'Ports': ports,
                                 'Parameters': [x for x in node[3:] if x[0] == 'PARAMETER']}
    cells = definitions
    for inst, value in instances.items():
        require(value['Cell'] in cells and cells[value['Cell']]['Operator'] == value['Operator'],
                'missing/mismatched concrete native cell')
    for (inst, pin), net in pins.items():
        require(pin in cells[instances[inst]['Cell']]['Ports'], 'native pin not in concrete interface')
    return {'Cells': cells, 'Instances': instances, 'Pins': pins}


def logical_relationships(g):
    """Repeat current structure checks; retain FFAPP identity before merging."""
    gray = base.gray_structures(g)+monitor.monitor_gray(g)
    scalars = monitor.application_scalars(g)+monitor.monitor_scalar(g)
    resets = monitor.reset_chains(g)
    held = monitor.held_snapshot(g)
    held['AllFirstConsumers'] = monitor.held_first_sinks(g, held)
    rows, internal = {}, []

    def add(source, target, pin, label, purpose, old_endpoints):
        require(source in g.ff and target in g.ff and pin in ('D', 'CE', 'SR'), 'invalid logical FF pair')
        key = source, target, pin
        sc, dc = (g.clock(g.ff[n]['Ports']['CK'])['Domain'] for n in (source, target))
        item = rows.setdefault(key, {'SourceFF': source, 'DestinationFF': target,
            'DestinationPin': pin, 'SourceClock': sc, 'DestinationClock': dc,
            'Labels': [], 'Purposes': [], 'OriginalEndpoints': []})
        item['Labels'].append(label)
        item['Purposes'].append(purpose)
        item['OriginalEndpoints'].extend(old_endpoints)

    for row in gray:
        add(row['Source'], row['First'], 'D', row['Label'], 'registered Gray to first stage',
            [row['NativeEndpoint']])
    chains = gray+scalars+resets['SingleChains']+[c for r in resets['ReplicatedTrees'] for c in r['Chains']]
    for row in chains:
        if not row['NativeQueries']:
            require(row['SameBLE'], 'unqueried interstage relationship is not internal to one BLE')
            internal.append({'SourceFF': row['First'], 'DestinationFF': row['Second'],
                'DestinationPin': 'D', 'Label': row['Label'], 'Placement': row['FirstPlacement'],
                'Reason': 'Existing inventory treats same-BLE interstage as internal; no native timing acceptance added.'})
            continue
        add(row['First'], row['Second'], 'D', row['Label'], 'interstage',
            [q['Endpoint'] for q in row['NativeQueries']])
    for row in scalars:
        for source in row.get('SourceRegisters', []):
            add(source, row['First'], 'D', row['Label'], 'registered scalar to first stage',
                [base.native_parent(row['First'])+'/D'])
    for row in held['AllFirstConsumers']['Rows']:
        for target in row['Consumers']:
            add(row['Source'], target['Cell'], target['Pin'], 'held_snapshot['+str(row['Bit'])+']',
                'held snapshot to every first sequential consumer', [target['Endpoint']])
    for row in rows.values():
        for field in ('Labels', 'Purposes', 'OriginalEndpoints'):
            row[field] = sorted(set(row[field]))
    old = monitor.query_pairs(gray, scalars, resets, held)
    return [rows[k] for k in sorted(rows)], internal, old


def input_pins(cell, output):
    """Exact local Boolean support, retaining tied relevant physical inputs.

    Correlation between external cones is deliberately not used to prune paths.
    Constant and mux-inactive inputs are excluded by the exported primitive.
    """
    relevant, _ = monitor.immediate_support(cell, output)
    ports = cell['Ports']
    if cell['Primitive'] in ('V_BUF', 'V_INV'):
        return ['I'] if ports['I'] in relevant else []
    require(cell['Primitive'] == 'V_LUT6CARRY', 'unsupported local boundary primitive')
    pins = ('I0', 'I1', 'I2', 'I3', 'I4', 'I5', 'CIN')
    independent = copy.deepcopy(cell)
    for pin in pins:
        if ports[pin] not in ("1'b0", "1'b1"):
            independent['Ports'][pin] = '@'+pin
    pin_support, _ = monitor.immediate_support(independent, output)
    return [p for p in pins if ports[p] in relevant and '@'+p in pin_support]


class Mapper:
    def __init__(self, graph, route):
        self.g, self.route = graph, route
        self.support_cache, self.boundary_cache = {}, {}
        self.inputs = defaultdict(lambda: defaultdict(list))
        self.outputs = defaultdict(lambda: defaultdict(list))
        for (inst, pin), net in route['Pins'].items():
            cell = route['Cells'][route['Instances'][inst]['Cell']]
            table = self.inputs if cell['Ports'][pin] == 'INPUT' else self.outputs
            table[inst][net].append(pin)
        self.net_aliases = {canon(n): n for n in graph.refs}
        require(len(self.net_aliases) == len(graph.refs), 'functional canonical net collision')

    def support(self, net, active=()):
        require(net not in active, 'cyclic source dependency')
        if net in self.support_cache:
            return self.support_cache[net]
        if net in ("1'b0", "1'b1"):
            value = set()
        else:
            drivers = self.g.outputs.get(net, [])
            require(len(drivers) == 1, 'source dependency lacks unique functional driver: '+net)
            name, pin = drivers[0]
            cell = self.g.cells[name]
            if name in self.g.ff:
                require(pin == 'Q', 'unreviewed sequential launch')
                value = {name}
            else:
                require(cell['Primitive'] in ('V_LUT6CARRY', 'V_BUF', 'V_INV'),
                        'unreviewed source dependency primitive: '+name)
                value = set()
                for p in input_pins(cell, pin):
                    value |= self.support(cell['Ports'][p], active+(net,))
        self.support_cache[net] = value
        return value

    def native_alias(self, net):
        """Prove renamed intra-CLM carry wires from their unique driver pin.

        Final functional export replaces some logical carry net names by site
        wires.  The native COUT -> CIN connection is authoritative for that
        rename; a same-site guess or numerical bit ordering is insufficient.
        """
        name, output = self.g.driver(net)
        cell = self.g.cells[name]
        require(cell['Primitive'] == 'V_LUT6CARRY' and output == 'COUT',
                'unreviewed functional/native boundary net rename: '+net)
        parent = name.rsplit('/', 2)[0]
        key = parent, 'COUT'
        require(key in self.route['Pins'] and
                self.route['Cells'][self.route['Instances'][parent]['Cell']]['Ports']['COUT'] == 'OUTPUT',
                'native carry alias lacks actual driver output')
        return self.route['Pins'][key], {'FunctionalNet': canon(net), 'NativeNet': self.route['Pins'][key],
            'FunctionalDriver': name+'/COUT', 'NativeDriver': parent+'/COUT',
            'Reason': 'Unique functional carry driver and native COUT-to-CIN connectivity'}

    def boundaries(self, target, pin):
        key = target, pin
        if key in self.boundary_cache:
            return self.boundary_cache[key]
        parent = base.native_parent(target)
        rows = {}

        def visit(net, trail, active, consumer=None):
            require(net not in active, 'cycle inside destination packed instance')
            if net in ("1'b0", "1'b1"):
                return
            if not self.support(net):
                return
            alias = None
            candidates = self.inputs[parent].get(canon(net), [])
            if candidates and pin in ('CE', 'SR'):
                expected = {'CE': 'CE', 'SR': 'RS'}[pin]
                require(expected in candidates, 'control path reached unrelated packed input')
                candidates = [expected]
            if consumer is not None:
                cname, cpin = consumer
                if cname in self.g.ff and cpin == 'D' and 'D' in candidates:
                    candidates = ['D']
                elif cname.startswith(parent+'/') and self.g.cells[cname]['Primitive'] == 'V_LUT6CARRY':
                    # Native boundary pin identity must also match its connected
                    # net; never infer a packed input from a parent name alone.
                    if cpin not in candidates and cpin == 'CIN':
                        native_net, alias = self.native_alias(net)
                        require(self.route['Pins'].get((parent, cpin)) == native_net,
                                'native carry driver does not reach destination CIN')
                        candidates = [cpin]
                    require(cpin in candidates, 'functional/native LUT input connectivity differs: '+cname+'/'+cpin)
                    candidates = [cpin]
            if candidates:
                require('CLK' not in candidates, 'data dependency reaches clock boundary')
                for endpoint_pin in candidates:
                    endpoint = parent+'/'+endpoint_pin
                    rows.setdefault(endpoint, {'Endpoint': endpoint, 'BoundaryNet': canon(net),
                        'NativeBoundaryNet': self.route['Pins'][parent, endpoint_pin],
                        'NetAliasProof': alias, 'FunctionalBoundaryNet': net,
                        'BoundaryToLogicalFF': []})['BoundaryToLogicalFF'].append(trail)
                return
            name, output = self.g.driver(net)
            require(name not in self.g.ff, 'internal sequential path unexpectedly needs native boundary: '+target)
            require(name.startswith(parent+'/') or self.g.cells[name]['Primitive'] in ('V_BUF', 'V_INV'),
                    'destination cone escaped packed boundary without native port: '+name)
            cell = self.g.cells[name]
            for ip in input_pins(cell, output):
                step = {'Cell': name, 'Primitive': cell['Primitive'], 'Output': output, 'Input': ip,
                        'Parameters': cell['Parameters']}
                visit(cell['Ports'][ip], trail+[step], active+(net,), (name, ip))

        visit(self.g.ff[target]['Ports'][pin], [], (), (target, pin))
        require(rows, 'no native data/control boundary for logical consumer')
        self.boundary_cache[key] = [rows[k] for k in sorted(rows)]
        return self.boundary_cache[key]

    def map(self, row):
        source, target = row['SourceFF'], row['DestinationFF']
        parent = base.native_parent(source)
        q = canon(self.g.ff[source]['Ports']['Q'])
        launch = self.outputs[parent].get(q, [])
        require(len(launch) == 1, 'logical launch Q lacks unique native output: '+source)
        require((parent, 'CLK') in self.route['Pins'], 'native launch clock pin missing')
        sinks = [r for r in self.boundaries(target, row['DestinationPin'])
                 if source in self.support(r['FunctionalBoundaryNet'])]
        require(sinks, 'logical source reaches no selected destination boundary: '+source+' -> '+target)
        return {**row, 'SourceLogicalQ': q, 'SourceNativeClockPin': parent+'/CLK',
                'SourceNativeOutputPin': parent+'/'+launch[0], 'DestinationLogicalQ': canon(self.g.ff[target]['Ports']['Q']),
                'NativeBoundaries': sinks, 'SourcePlacement': self.g.g['FFPlacement'][source],
                'DestinationPlacement': self.g.g['FFPlacement'][target]}


def native_lut_bindings(graph, route, mappings):
    """Cross-check LUT INIT and retain the native operator/mux parameters."""
    rows = {}
    for mapping in mappings:
        for boundary in mapping['NativeBoundaries']:
            for trail in boundary['BoundaryToLogicalFF']:
                for step in trail:
                    if step['Primitive'] != 'V_LUT6CARRY' or step['Cell'] in rows:
                        continue
                    name = step['Cell']
                    parent = name.rsplit('/', 2)[0]
                    native = route['Cells'][route['Instances'][parent]['Cell']]
                    inits = [p for p in native['Parameters'] if p[1] == 'INIT']
                    require(len(inits) == 1 and len(inits[0]) == 4
                            and inits[0][2] == ['DATATYPE', 'BITVEC'], 'native LUT INIT missing/ambiguous')
                    value = inits[0][3]
                    require(value[0] == 'BITVEC' and len(value) == 2 and value[1][:2] == ['B', '64'],
                            'unsupported native LUT INIT representation')
                    bits = value[1][2].strip('"')
                    require(len(bits) == 64 and set(bits) <= {'0', '1'}, 'native LUT INIT is not 64 bits')
                    exported = graph.cells[name]['Parameters']
                    require(int(bits, 2) == int(exported['INIT'][4:], 16), 'functional/native LUT INIT differs')
                    rows[name] = {'NativeInstance': parent, 'NativeCell': route['Instances'][parent]['Cell'],
                        'NativeOperator': native['Operator'], 'NativeParameters': native['Parameters'],
                        'FunctionalParameters': exported, 'INITMatches': True,
                        'BooleanMuxSemantics': monitor.NATIVE_LUT_REFERENCE}
    require(rows, 'no local LUT bindings derived')
    return rows


def build(netlist, dump, plan_path, output):
    paths = [Path(p).resolve() for p in (netlist, dump, plan_path)]
    watched = {str(p): sha(p) for p in paths}
    plan = json.loads(paths[2].read_text(encoding='utf-8-sig'))
    require(Path(plan['Netlist']['Path']).resolve() == paths[0] and plan['Netlist']['SHA256'] == watched[str(paths[0])],
            'functional export differs from bound logical plan')
    export_path = Path(plan['ExportReceipt']['Path'])
    require(sha(export_path) == plan['ExportReceipt']['SHA256'], 'bound export receipt drift')
    export = json.loads(export_path.read_text(encoding='utf-8-sig'))
    require(export['ExecutionPassed'] is True and export['ExitCode'] == 0 and not export.get('InputDrift'),
            'successful final native export required')
    route_provenance = adif.receipt_provenance(paths[1])
    require(route_provenance['Verified'] and route_provenance['InputADFSHA256'] == plan['CandidateADF']['SHA256'],
            'route dump is not bound to final logical candidate')
    watched[str(export_path.resolve())] = sha(export_path)
    watched[str(Path(route_provenance['Receipt']).resolve())] = route_provenance['ReceiptSHA256']
    graph = monitor.Graph(structure.functional(paths[0].read_text(encoding='utf-8-sig')))
    rows, internal, old = logical_relationships(graph)
    pairs = {(r['Source'], r['Endpoint']) for r in old}
    require(pairs == {(r['Source'], r['Endpoint']) for r in plan['Queries']}, 'old inventory not completely regenerated')
    parents = {base.native_parent(r[k]) for r in rows for k in ('SourceFF', 'DestinationFF')}
    parents |= {n.rsplit('/', 2)[0] for n, c in graph.cells.items()
                if c['Primitive'] == 'V_LUT6CARRY' and c['Ports'].get('COUT')}
    route = route_objects(paths[1], parents)
    mapper = Mapper(graph, route)
    mappings = [mapper.map(row) for row in rows]
    lut_bindings = native_lut_bindings(graph, route, mappings)
    represented = {(r['SourceNativeClockPin'], endpoint) for r in mappings for endpoint in r['OriginalEndpoints']}
    require(represented == pairs, 'old inventory lost/expanded logical provenance')
    requirements = {(r['Source'], r['Endpoint']): r for r in plan['Queries']}
    queries = {}
    for number, row in enumerate(mappings):
        original = [requirements[row['SourceNativeClockPin'], e] for e in row['OriginalEndpoints']]
        fields = ('CheckKinds', 'Corners', 'MaximumNS', 'MinimumNS', 'SourcePeriodNS', 'Clock', 'SourceClock', 'DestinationClock')
        requirement = {k: original[0][k] for k in fields if k in original[0]}
        require(all({k:r[k] for k in fields if k in r} == requirement for r in original), 'logical provenance has conflicting timing constraints')
        for boundary in row['NativeBoundaries']:
            key = row['SourceNativeClockPin'], row['SourceNativeOutputPin'], boundary['Endpoint']
            item = queries.setdefault(key, {'Source': key[0], 'LaunchOutput': key[1], 'Endpoint': key[2],
                'Requirements': requirement, 'LogicalRelationships': []})
            require(item['Requirements'] == requirement, 'native query merges different timing requirements')
            item['LogicalRelationships'].append(number)
    for helper in structure.local_helpers((structure, adif)):
        watched[str(helper)] = sha(helper)
    watched[str(SELF)] = sha(SELF)
    require(all(sha(p) == digest for p, digest in watched.items()), 'native mapping input drift')
    result = {'Schema': 'camera720-native-endpoints-v1', 'CreatedUTC': datetime.now(timezone.utc).isoformat(),
        'CandidateADF': plan['CandidateADF'], 'BuildPlanSHA256': plan['BuildPlanSHA256'],
        'InputSHA256': watched, 'ExportReceipt': plan['ExportReceipt'], 'RouteProvenance': route_provenance,
        'OriginalPhysicalPairs': len(pairs), 'LogicalRelationships': mappings,
        'SameBLEInterstageInventory': internal, 'Queries': [queries[k] for k in sorted(queries)],
        'NativeLUTBindings': lut_bindings,
        'Summary': {'LogicalFFRelationships': len(mappings), 'LaunchQualifiedQueries': len(queries),
            'ClockEndpointPairs': len({(q['Source'], q['Endpoint']) for q in queries.values()}),
            'LegacyPlannedCornerKindCases': sum(len(q['Requirements']['Corners'])*len(q['Requirements']['CheckKinds'])
                                           for q in queries.values()),
            'SameBLEInterstageRelationships': len(internal)},
        'TimingRequirementsStatus': 'Requirements preserve the legacy plan verbatim. Native datapath-only max-delay suppresses hold; crossing minimum applicability must be resolved from the bound native exception semantics by the timing collector, never counted as an inferred pass.',
        'MappingPassed': True, 'NativeTimingAccepted': False, 'HardwareReleaseAllowed': False,
        'EDAExecuted': False, 'HardwareAccessed': False,
        'Scope': 'Logical FF provenance and all locally sensitizable native boundary dependencies; no timing acceptance.',
        'Limits': ['CLK may alias two launches: native path must include the specified LaunchOutput.',
            'All selected boundary pins are required; top-N reports cannot silently waive missing pins.',
            'Reconvergent external cones are conservatively included; no path false-path exemption is added.',
            'Same-BLE relationships preserve the existing structural inventory; no new native internal timing acceptance.',
            'Adjacent successful receipts and hashes checked; full transitive native authorization must be bound by the caller.']}
    output = Path(output).resolve()
    require(not output.exists(), 'fresh mapping output required')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--netlist', type=Path, required=True)
    parser.add_argument('--route-dump', type=Path, required=True)
    parser.add_argument('--batch-plan', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = build(args.netlist, args.route_dump, args.batch_plan, args.output)
    print(json.dumps({'MappingPassed': result['MappingPassed'], 'OriginalPhysicalPairs': result['OriginalPhysicalPairs'],
        'LogicalRelationships': len(result['LogicalRelationships']), 'NativeQueries': len(result['Queries']),
        'NativeTimingAccepted': False, 'HardwareReleaseAllowed': False}))


if __name__ == '__main__':
    main()
