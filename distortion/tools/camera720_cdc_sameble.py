"""CPU supplement for routed interstages hidden by a same-BLE label.

Inputs must be the final functional graph/native route parsed and bound by the
calling auditor. This module adds no timing exception and accepts no timing.
"""
from pathlib import Path

import camera720_native_endpoints as endpoints

require, canon, sha = endpoints.require, endpoints.canon, endpoints.sha
SELF = Path(__file__).resolve()


def derive(graph, route, inventory):
    """Reclassify each actual same-BLE pair without a hardcoded path list."""
    require(inventory.get('Schema') == 'camera720-native-endpoints-v1', 'wrong endpoint inventory schema')
    rows = inventory.get('SameBLEInterstageInventory')
    require(isinstance(rows, list) and rows, 'same-BLE inventory missing')
    mapper = endpoints.Mapper(graph, route)
    direct, mappings, queries, seen = [], [], [], set()
    inventoried = {(r['SourceFF'], r['DestinationFF'], r['DestinationPin'])
                  for r in rows+inventory.get('LogicalRelationships', [])}
    for row in rows:
        source, target = row['SourceFF'], row['DestinationFF']
        key = source, target, row['DestinationPin']
        require(key not in seen and source != target and key[2] == 'D', 'duplicate/invalid same-BLE pair')
        seen.add(key)
        require(source in graph.ff and target in graph.ff, 'same-BLE pair missing actual FF')
        a, b = graph.ff[source]['Ports'], graph.ff[target]['Ports']
        parent = endpoints.base.native_parent(source)
        require(parent == endpoints.base.native_parent(target), 'same-BLE pair has different native parents')
        require(graph.g['FFPlacement'][source] == graph.g['FFPlacement'][target] == row['Placement'],
                'same-BLE placement differs from actual FFs')
        sc, dc = graph.clock(a['CK']), graph.clock(b['CK'])
        require(sc['Domain'] == dc['Domain'] and sc['Root'] == dc['Root'] and a['CK'] == b['CK'],
                'same-BLE clock identity differs')
        require(route['Pins'].get((parent, 'CLK')) == canon(a['CK']), 'same-BLE native CLK net differs')
        native_cell = route['Cells'][route['Instances'][parent]['Cell']]
        q_inputs = [pin for (inst, pin), net in route['Pins'].items()
                    if inst == parent and net == canon(a['Q']) and native_cell['Ports'][pin] == 'INPUT']
        if a['Q'] == b['D']:
            loads = [(n, p) for n, p in graph.refs[a['Q']] if (n, p) != (source, 'Q')]
            replicated = len(loads) > 1
            if replicated:
                cell = graph.ff[source]
                require(cell['Primitive'] == 'V_FFASYN' and cell['Parameters'].get('INIT') == "1'b0"
                        and cell['Parameters'].get('SET_RESET') == '"RESET"' and graph.constant_one(a['D']),
                        'unreviewed direct-chain replication')
                require(all(n in graph.ff and p == 'D' and (source, n, p) in inventoried for n, p in loads),
                        'replicated reset fanout lacks complete inventory')
                for n, _ in loads:
                    graph.chain(source, n, row['Label'], replicated=True)
            chain = graph.chain(source, target, row['Label'], replicated=replicated)
            require(chain['SameBLE'] and chain['InterstageLogic'] is None and not q_inputs,
                    'direct internal FF chain has a native input route')
            direct.append({**row, 'SourceLogicalQ': canon(a['Q']), 'DestinationLogicalQ': canon(b['Q']),
                           'Clock': sc['Domain'], 'DirectQToD': True, 'NativeReceivingInputs': [],
                           'NativeInstance': parent, 'NativeOperator': native_cell['Operator'],
                           'SourceOnlyFeedsSecondStage': chain['FirstStageOnlyFeedsSecondStage'],
                           'ReplicatedResetSecondStages': sorted(n for n, _ in loads) if replicated else [],
                           'TimingAccepted': False})
            continue
        origins = mapper.support(b['D'])
        require(source in origins and len(origins) == 2, 'same-BLE LUT path has unexpected register support')
        release = next(iter(origins - {source}))
        require(graph.clock(graph.ff[release]['Ports']['CK'])['Domain'] == dc['Domain'],
                'same-BLE interstage release is not local')
        chain = graph.chain(source, target, row['Label'], graph.ff[release]['Ports']['Q'])
        require(chain['SameBLE'] and chain['InterstageLogic'] is not None, 'same-BLE routed LUT proof missing')
        logical = {'SourceFF': source, 'DestinationFF': target, 'DestinationPin': 'D',
                   'SourceClock': sc['Domain'], 'DestinationClock': dc['Domain'],
                   'Labels': [row['Label']], 'Purposes': ['ordinary routed interstage within same BLE'],
                   'OriginalEndpoints': [], 'SupplementalSameBLE': True,
                   'OriginalSameBLEInventoryRow': row, 'LocalReleaseFF': release,
                   'InterstageLogic': chain['InterstageLogic']}
        mapped = mapper.map(logical)
        number = len(mappings)
        mappings.append(mapped)
        require(q_inputs, 'same-BLE routed interstage has no native receiving input')
        require({b['Endpoint'].removeprefix(parent+'/') for b in mapped['NativeBoundaries']} == set(q_inputs),
                'same-BLE mapped endpoints differ from actual source-Q receiving pins')
        for boundary in mapped['NativeBoundaries']:
            queries.append({'Source': mapped['SourceNativeClockPin'], 'LaunchOutput': mapped['SourceNativeOutputPin'],
                            'Endpoint': boundary['Endpoint'],
                            'Requirements': {'Clock': dc['Domain'], 'CheckKinds': ['setup', 'hold'],
                                             'Corners': ['slow', 'fast']},
                            'LogicalRelationships': [number], 'SupplementalSameBLE': True})
    require(len(direct)+len(mappings) == len(rows), 'same-BLE classification incomplete')
    keys = [(q['Source'], q['LaunchOutput'], q['Endpoint']) for q in queries]
    require(len(keys) == len(set(keys)), 'duplicate supplemental query')
    existing = {(q['Source'], q['LaunchOutput'], q['Endpoint']) for q in inventory['Queries']}
    require(not existing.intersection(keys), 'supplemental query duplicates existing inventory')
    bindings = endpoints.native_lut_bindings(graph, route, mappings) if mappings else {}
    return {'Schema': 'camera720-sameble-supplement-v1',
            'Producer': {'Path': str(SELF), 'SHA256': sha(SELF)},
            'Mapper': {'Path': str(endpoints.SELF), 'SHA256': sha(endpoints.SELF)},
            'CandidateADF': inventory['CandidateADF'], 'BuildPlanSHA256': inventory['BuildPlanSHA256'],
            'LogicalRelationships': mappings, 'Queries': queries, 'DirectInternalRows': direct,
            'NativeLUTBindings': bindings, 'ClassifiedRelationships': len(rows),
            'DirectInternalRelationships': len(direct), 'SupplementalInterstageRelationships': len(mappings),
            'SupplementalApplicableCases': sum(len(q['Requirements']['CheckKinds'])*len(q['Requirements']['Corners'])
                                               for q in queries),
            'CallerMustBindActualGraphAndRoute': True, 'StructuralClassificationPassed': True,
            'NativeTimingAccepted': False, 'HardwareReleaseAllowed': False}
