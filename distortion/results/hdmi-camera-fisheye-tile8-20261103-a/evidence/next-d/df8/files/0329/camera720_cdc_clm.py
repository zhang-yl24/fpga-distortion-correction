"""CPU-only physical-CLM boundary derivation for packed carry paths.

This supplements, and does not mutate, the frozen per-BLE mapper. A native
logical CIN on BLE B/C/D is an internal carry wire, not a physical CLM timing
endpoint. Preserve the actual FF relation while expanding its local carry
cone to external I pins and BLE A CIN. No timing acceptance is made here.
"""
import copy
from pathlib import Path
import re

import camera720_native_endpoints as endpoints

require, canon, sha = endpoints.require, endpoints.canon, endpoints.sha
SELF = Path(__file__).resolve()
LUT = re.compile(r'(?P<attrs>\(\*[^*]*\*\)\s*)?'
    r'(?P<primitive>V_LUT6CARRY)\s*/\*\s*(?P<site>\w+)\s*\*/\s*'
    r'(?:#\s*\((?P<parameters>.*?)\)\s*)?'
    r'(?P<name>\\\S+|[A-Za-z_$][\w$]*)\s*\((?P<ports>.*?)\)\s*;', re.S)


def ble(placement):
    values = re.findall(r'PAP_BLE_DEF\s*=\s*"([ABCD])"', placement['Attributes'])
    require(len(values) == 1, 'one actual BLE placement required')
    return values[0]


def placed_luts(text, graph):
    """Bind LUT physical annotations to exactly the parsed functional cells."""
    result = {}
    for match in LUT.finditer(text):
        name = match['name'].lstrip('\\')
        require(name in graph.cells and name not in result, 'duplicate/unmatched placed LUT')
        actual = {'Primitive': match['primitive'],
                  'Parameters': endpoints.base.physical.dialect.bindings(match['parameters']),
                  'Ports': endpoints.base.physical.dialect.bindings(match['ports'])}
        require(actual == graph.cells[name], 'placed LUT differs from functional graph')
        result[name] = {'Site': match['site'],
                        'Attributes': ' '.join((match['attrs'] or '').split())}
        ble(result[name])
    require(set(result) == {n for n, c in graph.cells.items() if c['Primitive'] == 'V_LUT6CARRY'},
            'incomplete placed LUT evidence')
    return result


class Mapper(endpoints.Mapper):
    def __init__(self, graph, route, placements):
        super().__init__(graph, route)
        self.placements = placements
        self.carry_links = {}
        for name, placement in placements.items():
            require(name in graph.cells and graph.cells[name]['Primitive'] == 'V_LUT6CARRY',
                    'placement does not identify an actual carry LUT')
            ble(placement)

    def connection(self, name, pin):
        parent = name.rsplit('/', 2)[0]
        net = self.g.cells[name]['Ports'][pin]
        key = parent, pin
        require(key in self.route['Pins'], 'local LUT native input missing')
        cell = self.route['Cells'][self.route['Instances'][parent]['Cell']]
        require(cell['Ports'].get(pin) == 'INPUT', 'local LUT native pin is not input')
        native_net = self.route['Pins'][key]
        alias = None
        if native_net != canon(net):
            require(pin == 'CIN', 'functional/native LUT input connectivity differs')
            proven, alias = self.native_alias(net)
            require(native_net == proven, 'native carry driver does not reach destination CIN')
        return parent, net, native_net, alias

    def boundaries(self, target, pin):
        if pin != 'D':
            return super().boundaries(target, pin)
        key = target, pin
        if key in self.boundary_cache:
            return self.boundary_cache[key]
        target_site = self.g.g['FFPlacement'][target]['Site']
        target_parent = endpoints.base.native_parent(target)
        rows = {}

        def external(parent, native_pin, net, native_net, alias, trail):
            endpoint = parent+'/'+native_pin
            row = rows.setdefault(endpoint, {'Endpoint': endpoint, 'BoundaryNet': canon(net),
                'NativeBoundaryNet': native_net, 'NetAliasProof': alias,
                'FunctionalBoundaryNet': net, 'BoundaryToLogicalFF': [],
                'PhysicalCLMSite': target_site, 'BoundaryKind':
                'physical CLM CIN' if native_pin == 'CIN' else 'native external input'})
            require(row['FunctionalBoundaryNet'] == net and row['NativeBoundaryNet'] == native_net,
                    'native boundary has ambiguous functional net')
            row['BoundaryToLogicalFF'].append(trail)

        def visit(net, trail, active, consumer):
            require(net not in active, 'cycle inside physical CLM cone')
            if net in ("1'b0", "1'b1") or not self.support(net):
                return
            name, cpin = consumer
            if self.g.cells[name]['Primitive'] == 'V_LUT6CARRY':
                require(name in self.placements and self.placements[name]['Site'] == target_site,
                        'destination cone escaped physical CLM')
                parent, actual_net, native_net, alias = self.connection(name, cpin)
                require(actual_net == net, 'consumer input differs from traced net')
                if cpin != 'CIN' or ble(self.placements[name]) == 'A':
                    require(cpin in ('I0', 'I1', 'I2', 'I3', 'I4', 'I5', 'CIN'),
                            'unexpected native CLM input')
                    external(parent, cpin, net, native_net, alias, trail)
                    return
                driver, output = self.g.driver(net)
                require(driver in self.placements and output == 'COUT',
                        'internal CIN lacks actual LUT COUT driver')
                a, b = self.placements[driver], self.placements[name]
                require(a['Site'] == b['Site'] == target_site
                        and ord(ble(a))+1 == ord(ble(b)), 'internal CIN is not preceding BLE carry')
                driver_parent = driver.rsplit('/', 2)[0]
                require(self.route['Pins'].get((driver_parent, 'COUT')) == native_net,
                        'internal carry native COUT/CIN connection differs')
                driver_cell = self.route['Cells'][self.route['Instances'][driver_parent]['Cell']]
                require(driver_cell['Ports'].get('COUT') == 'OUTPUT', 'internal carry driver direction differs')
                proof = {'Site': target_site, 'SourceBLE': ble(a), 'DestinationBLE': ble(b),
                    'FunctionalDriver': driver+'/COUT', 'FunctionalConsumer': name+'/CIN',
                    'FunctionalNet': canon(net), 'NativeDriver': driver_parent+'/COUT',
                    'NativeConsumer': parent+'/CIN', 'NativeNet': native_net,
                    'NetAliasProof': alias}
                self.carry_links[parent+'/CIN'] = proof
                trail = copy.deepcopy(trail)
                trail[-1]['InternalCarryConnection'] = proof
            elif name in self.g.ff and cpin == 'D':
                candidates = self.inputs[target_parent].get(canon(net), [])
                if 'D' in candidates:
                    external(target_parent, 'D', net, self.route['Pins'][target_parent, 'D'], None, trail)
                    return
            driver, output = self.g.driver(net)
            require(driver not in self.g.ff, 'unqueryable internal sequential path in CLM data cone')
            cell = self.g.cells[driver]
            require(cell['Primitive'] in ('V_LUT6CARRY', 'V_BUF', 'V_INV'),
                    'unreviewed physical CLM cone primitive')
            if cell['Primitive'] == 'V_LUT6CARRY':
                require(driver in self.placements and self.placements[driver]['Site'] == target_site,
                        'destination cone escaped physical CLM without external input')
            for ip in endpoints.input_pins(cell, output):
                step = {'Cell': driver, 'Primitive': cell['Primitive'], 'Output': output,
                        'Input': ip, 'Parameters': cell['Parameters']}
                visit(cell['Ports'][ip], trail+[step], active+(net,), (driver, ip))

        visit(self.g.ff[target]['Ports']['D'], [], (), (target, 'D'))
        require(rows, 'no physical CLM boundary for logical consumer')
        self.boundary_cache[key] = [rows[k] for k in sorted(rows)]
        return self.boundary_cache[key]


def derive(graph, route, inventory, placements):
    """Return remapped relations/queries; caller binds original bytes and policy."""
    require(inventory.get('Schema') == 'camera720-native-endpoints-v1', 'wrong endpoint inventory schema')
    old_rows = inventory['LogicalRelationships']
    requirements = {}
    for query in inventory['Queries']:
        for i in query['LogicalRelationships']:
            require(0 <= i < len(old_rows), 'query logical index out of range')
            previous = requirements.setdefault(i, query['Requirements'])
            require(previous == query['Requirements'], 'logical relationship timing requirements differ')
    require(set(requirements) == set(range(len(old_rows))), 'old inventory lacks logical relationship coverage')
    mapper = Mapper(graph, route, placements)
    mappings, queries, changes = [], {}, []
    seen = set()
    for i, old in enumerate(old_rows):
        logical_key = old['SourceFF'], old['DestinationFF'], old['DestinationPin']
        require(logical_key not in seen, 'duplicate logical relationship')
        seen.add(logical_key)
        mapped = mapper.map(old)
        require(all(mapped[k] == old[k] for k in ('SourceLogicalQ', 'SourceNativeClockPin',
                    'SourceNativeOutputPin', 'DestinationLogicalQ', 'SourcePlacement', 'DestinationPlacement')),
                'logical launch/destination identity drift')
        previous = sorted(b['Endpoint'] for b in old['NativeBoundaries'])
        current = sorted(b['Endpoint'] for b in mapped['NativeBoundaries'])
        mapped['PreviousBLEBoundaryEndpoints'] = previous
        mappings.append(mapped)
        if previous != current:
            changes.append({'LogicalRelationship': i, 'SourceFF': old['SourceFF'],
                'DestinationFF': old['DestinationFF'], 'PreviousEndpoints': previous, 'PhysicalEndpoints': current})
        for b in mapped['NativeBoundaries']:
            k = mapped['SourceNativeClockPin'], mapped['SourceNativeOutputPin'], b['Endpoint']
            q = queries.setdefault(k, {'Source': k[0], 'LaunchOutput': k[1], 'Endpoint': k[2],
                'Requirements': copy.deepcopy(requirements[i]), 'LogicalRelationships': []})
            require(q['Requirements'] == requirements[i], 'physical query merges conflicting timing requirements')
            q['LogicalRelationships'].append(i)
    bindings = endpoints.native_lut_bindings(graph, route, mappings)
    return {'Schema': 'camera720-physical-clm-boundaries-v1',
        'Producer': {'Path': str(SELF), 'SHA256': sha(SELF)},
        'Mapper': {'Path': str(endpoints.SELF), 'SHA256': sha(endpoints.SELF)},
        'CandidateADF': inventory['CandidateADF'], 'BuildPlanSHA256': inventory['BuildPlanSHA256'],
        'LogicalRelationships': mappings, 'Queries': [queries[k] for k in sorted(queries)],
        'ChangedLogicalRelationships': changes, 'InternalCarryConnections': mapper.carry_links,
        'NativeLUTBindings': bindings, 'ActualLUTPlacements':
            {n: placements[n] for n in bindings},
        'PhysicalBoundaryDerivationPassed': True, 'NativeTimingAccepted': False,
        'PhysicalTimingAggregationProved': False, 'HardwareReleaseAllowed': False,
        'CallerMustBindActualGraphAndRoute': True}
