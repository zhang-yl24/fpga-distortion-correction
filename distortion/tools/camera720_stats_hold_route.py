"""Measured DVP control hold branches on an isolated statistics ADF copy.

All carry failures are traced to actual input leaves in the placed functional
graph. Only those leaves are rerouted; carry wires and all other leaves remain
exact. This is an implementation experiment, not timing or hardware approval.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import camera720_stats_inspect as inspect
import camera720_stats_io_cdc as graph_tools
import camera720_hold_route as waypoint_helper
import camera720_calibrated_hold_route as lifecycle
import camera720_calibrated_route_reassessment as metadata
import audit_camera720_hold as hold
import audit_raw_camera_routes as routes

prep, require, sha = inspect.prep, inspect.require, inspect.sha
SELF = Path(__file__).resolve()
SCHEMA = 'camera720-calibrated-stats-hold-route-application-v1'
REQUEST_SCHEMA = 'camera720-calibrated-stats-hold-route-request-v1'
MARKER = 'CAMERA720_CALIBRATED_STATS_HOLD_ROUTE_SAVED'
INIT = inspect.INIT
DUMMY = lifecycle.DUMMY
ARTIFACT_SUFFIXES = lifecycle.ARTIFACT_SUFFIXES
ORIGINAL_ADF = 'fc1f129f5156f9eaaec135075a18480b2a72d5410798d78d333549bbe22d8460'
NETS = {'nt_cam_href', 'nt_cam_vsync', '_N48'}
read, ref = lifecycle.read, lifecycle.ref


def add(watched, path, expected=None):
    path = Path(path).absolute()
    wire = Path(routes.common.WIRE_DEFAULT).resolve()
    require(path == path.resolve() and path.is_file() and
            (path.is_relative_to(prep.PROJECT) or path == wire or path in watched), 'canonical bound input required')
    digest = sha(path)
    require(expected is None or digest == expected, 'input SHA differs: '+str(path))
    require(path not in watched or watched[path] == digest, 'conflicting input SHA')
    watched[path] = digest
    return path


def binding(value, watched):
    require(isinstance(value, dict) and set(value) == {'Path', 'SHA256'}, 'exact Path/SHA reference required')
    return add(watched, value['Path'], value['SHA256'])


def report_identity(path):
    with Path(path).open(encoding='utf-8-sig') as stream:
        text = ''.join(stream.readline() for _ in range(16))
    require(re.findall(r'(?m)^\| Design\s*:\s*(\S+)\s*$', text) == [prep.TARGET], 'wrong statistics native report')


def logical_connections(tree):
    """Preserve attributes in full semantic audit; extract one exact CONNECT."""
    require(tree[0] == 'NET' and len(tree) >= 3, 'native NET required')
    connects = [item for item in tree[2:] if isinstance(item, list) and item and item[0] == 'CONNECT']
    require(len(connects) == 1, 'one CONNECT required')
    for item in tree[2:]:
        require(item[0] in ('CONNECT', 'FILEID', 'LINENUM', 'ATTRIBUTE'), 'unknown native NET field')
        if item[0] in ('FILEID', 'LINENUM'):
            require(len(item) == 2 and item[1].isdigit(), 'invalid source location')
        elif item[0] == 'ATTRIBUTE':
            require(len(item) == 3 and isinstance(item[2], list) and item[2][0] == 'STRING'
                    and len(item[2]) == 2, 'invalid native net attribute')
    result = []
    for item in connects[0][1:]:
        require(len(item) == 3 and item[0] == 'PORTREF' and item[2][0] == 'INSTREF'
                and len(item[2]) == 2, 'invalid native connection')
        result.append({'Instance': item[2][1].lstrip('\\'), 'Pin': routes.common.port_name(item[1])})
    require(len({(r['Instance'], r['Pin']) for r in result}) == len(result), 'duplicate logical net connection')
    return result


def inspect_routes(path, targets):
    before = sha(path)
    parsed = routes.common.inspect(Path(path), {})
    require(targets and len({(t['Net'], t['ToRoutePin']) for t in targets}) == len(targets), 'duplicate route target')
    blocks = routes.target_tokens(path, {t['Net'] for t in targets})
    inventories = {}
    for name, tree in blocks['NETANNOTATE'].items():
        require(len(tree) == 3 and tree[0] == 'NETANNOTATE', 'unexpected route annotation')
        leaves = routes.route_leaves(tree[2])
        connections = logical_connections(blocks['NET'][name])
        for target in [t for t in targets if t['Net'] == name]:
            require(target['ToRoutePin'] in leaves and leaves[target['ToRoutePin']][0] == target['FromRoutePin'],
                    'STA source/load differs from actual native route')
            instance, pin = target['Endpoint'].rsplit('/', 1)
            require({'Instance': instance, 'Pin': pin} in connections, 'selected input is absent from actual net')
            require(len(connections) == target['Fanout']+1, 'actual fanout differs')
        inventories[name] = {'Leaves': leaves, 'LogicalConnections': connections}
    require(sha(path) == before, 'native route changed during parsing')
    return {**parsed, 'BranchInventory': inventories}


def carry_input_leaves(graph, placements, output, source_net, site):
    """Resolve packed COUT back through only actual local Boolean dependencies."""
    parent, pin = output.rsplit('/', 1)
    require(pin == 'COUT', 'only carry output trace may elide its input leaf')
    matches = [name for name in placements if name.rsplit('/', 2)[0] == parent]
    require(len(matches) == 1 and placements[matches[0]]['Site'] == site, 'actual placed carry output missing')
    found, steps = set(), []

    def visit(name, outpin, active):
        require((name, outpin) not in active, 'carry cone cycle')
        require(name in placements and placements[name]['Site'] == site, 'carry trace leaves actual CLM')
        cell = graph.cells[name]
        require(cell['Primitive'] == 'V_LUT6CARRY', 'carry output lacks actual LUT')
        for ip in graph_tools.cdc.endpoints.input_pins(cell, outpin):
            net = cell['Ports'][ip]
            if net == source_net:
                require(re.fullmatch(r'I[0-5]', ip), 'control input must be actual LUT input')
                native = name.rsplit('/', 2)[0]+'/'+ip
                physical = graph_tools.cdc.clm.ble(placements[name])+ip[1:]+':'+site
                found.add((native, physical))
                steps.append({'Cell': name, 'Output': outpin, 'Input': ip, 'Net': net, 'PhysicalInput': physical})
            elif ip == 'CIN' and net not in ("1'b0", "1'b1"):
                drivers = graph.outputs.get(net, [])
                require(len(drivers) == 1, 'local carry input lacks unique driver')
                driver, driver_pin = drivers[0]
                if driver in placements and placements[driver]['Site'] == site:
                    require(driver_pin == 'COUT' and ord(graph_tools.cdc.clm.ble(placements[driver]))+1 ==
                            ord(graph_tools.cdc.clm.ble(placements[name])), 'nonadjacent internal carry link')
                    steps.append({'Cell': name, 'Input': ip, 'Driver': driver, 'DriverPin': driver_pin, 'Net': net})
                    visit(driver, driver_pin, active+((name, outpin),))
    visit(matches[0], 'COUT', ())
    require(len(found) == 1, 'actual selected carry path has ambiguous/missing source control leaf')
    native, physical = next(iter(found))
    return {'Endpoint': native, 'ToRoutePin': physical, 'NativeCarryOutput': output, 'Steps': steps}


def selected_branch(path, graph, placements):
    trace = path['DataTrace']
    if trace[-2]['Name'] == '_N48':
        row = trace[-2]
        require(path['Source'] == 'cam_vsync (port)' and row['Fanout'] == 1, 'unexpected isolated vsync branch')
        return {'Net': row['Name'], 'FromRoutePin': row['FromRoutePin'], 'ToRoutePin': row['ToRoutePin'],
                'Endpoint': path['Endpoint'], 'Fanout': 1}, {'Kind': 'exact terminal single-load branch'}
    port = path['Source'].removesuffix(' (port)')
    require(port in ('cam_href', 'cam_vsync'), 'unsupported failing source')
    indices = [i for i, row in enumerate(trace) if row['Type'] == 'net' and row['Name'] == 'nt_'+port]
    require(len(indices) == 1, 'one direct DVP control net required')
    index = indices[0]; row = trace[index]; previous, following = trace[index-1], trace[index+1]
    require(previous['Type'] == following['Type'] == 'pin', 'control net lacks adjacent physical pins')
    endpoint, target = following['LogicalResource'], following['RoutePin']
    proof = {'Kind': 'actual direct native input'}
    if following['Pin'] == 'COUT':
        proof = carry_input_leaves(graph, placements, endpoint, row['Name'], following['Site'])
        endpoint, target = proof['Endpoint'], proof['ToRoutePin']
    else:
        require(re.fullmatch(r'I[0-5]', endpoint.rsplit('/', 1)[1]), 'unexpected direct control endpoint')
    return {'Net': row['Name'], 'FromRoutePin': previous['RoutePin'], 'ToRoutePin': target,
            'Endpoint': endpoint, 'Fanout': row['Fanout']}, proof


def select_waypoints(parsed, targets):
    """Unused official pairs beyond each long input route's receiving site.

    Coordinate distance is only a routing experiment, never a delay estimate.
    The sole short internal net uses the established nearby-source search.
    """
    wire = Path(routes.common.WIRE_DEFAULT).resolve()
    lines = wire.read_text().splitlines(); rules = {}
    for channel in range(4):
        hits = [{'Line': i+1, 'Text': line} for i, line in enumerate(lines)
                if line.startswith(f'ZDNE[{channel}] :')]
        require(len(hits) == 1 and f'[ IDNE[{channel}] ]' in hits[0]['Text'], 'official NE connection rule differs')
        rules[channel] = hits[0]
    selections, reserved = [], set()
    for target in targets:
        branch = parsed['BranchInventory'][target['Net']]['Leaves'][target['ToRoutePin']]
        sites = [tuple(map(int, re.search(r':SRB_(\d+)_(\d+)$', pin).groups())) for pin in branch if ':SRB_' in pin]
        require(sites, 'actual target lacks routing sites')
        if target['Net'].startswith('nt_cam_'):
            cx, cy = sites[-1][0]+96, sites[-1][1]+96
        else:
            cx, cy = sites[0][0]-12, sites[0][1]-24
        choices = []
        for (x, y, dx, dy), proof in parsed['_ObservedNE'].items():
            for channel in range(4):
                pins = [f'ZDNE[{channel}]:SRB_{x}_{y}', f'IDNE[{channel}]:SRB_{dx}_{dy}']
                if all(not parsed['_Occupied'].get(pin) and pin not in reserved for pin in pins):
                    choices.append({'Pins': pins, 'Distance': abs(x-cx)+abs(y-cy),
                                    'CoordinateProof': proof[0], 'OfficialWireRule': rules[channel]})
        require(choices, 'no unused officially connected observed-coordinate pair')
        choice = min(choices, key=lambda row: (row['Distance'], row['Pins']))
        reserved.update(choice['Pins'])
        selections.append({'Target': target, 'SearchCentre': [cx, cy], 'Selected': choice})
    return selections, wire


def derive(discovery_path, export_path):
    discovery_path, export_path = Path(discovery_path).resolve(), Path(export_path).resolve()
    discovery, watched = inspect.bind_receipt(discovery_path)
    export, bound = inspect.bind_receipt(export_path)
    for path, digest in bound.items():
        require(path not in watched or watched[path] == digest, 'conflicting export closure')
        watched[path] = digest
    require(discovery['Mode'] == 'query' and export['Mode'] == 'export', 'actual discovery/export required')
    for key in ('Target', 'BuildPlan', 'BuildPlanSHA256', 'SourceADF', 'SourceADFSHA256', 'BuildDiagnosticsReview'):
        require(discovery[key] == export[key], 'discovery/export identity differs')
    require(discovery['SourceADFSHA256'] == ORIGINAL_ADF, 'current original statistics ADF required')
    full = Path(discovery['TimingReport']['Path']); report_identity(full)
    initial, tables, _ = hold.common.read_report(full)
    identities = {hold.common.identity(p) for p in initial}
    require(len(identities) == 16, 'current full negative hold inventory differs')
    for table in tables:
        if table['Kind'] == 'hold' and table['FailingChecks']:
            keys = {hold.common.identity(p) for p in initial if (p['Corner'], p['LaunchClock'], p['CaptureClock']) ==
                    (table['Corner'], table['LaunchClock'], table['CaptureClock'])}
            require(len(keys) == table['FailingChecks'], 'full detail/summary hold coverage differs')
    reports = sorted(discovery_path.parent.glob('report_path_timing/*/report_timing/'+prep.TARGET+'.rtr'))
    require(len(reports) == 2, 'exact two source-group reports required')
    cases, provenance = [], []
    for report in reports:
        relative = report.relative_to(discovery_path.parent).as_posix()
        require(discovery['Artifacts'].get(relative) == sha(report), 'targeted report is not receipt bound')
        report_identity(report)
        paths, _, record = hold.common.read_report(report, identities)
        provenance.append(record)
        cases.extend(hold.detailed(p) for p in paths)
    relation_rows = []
    for key in sorted(identities):
        selected = [p for p in cases if hold.common.identity(p) == key]
        require({(p['Corner'], p['Kind']) for p in selected} == {(c, k) for c in ('slow', 'fast') for k in ('setup', 'hold')},
                'missing exact current setup/hold corner')
        require(all(p['SlackNS'] > 3.0 for p in selected if p['Kind'] == 'setup'), 'insufficient exact setup margin')
        relation_rows.append({'Identity': list(key), 'Cases': [{k: v for k, v in p.items() if k != '_Text'} for p in selected]})
    netlist = Path(export['Netlist']['Path']); add(watched, netlist, export['Netlist']['SHA256'])
    text = netlist.read_text(encoding='ascii'); graph = graph_tools.graph(text)
    placements = graph_tools.cdc.clm.placed_luts(text, graph)
    targets, branches, proofs = {}, defaultdict(set), []
    for path in cases:
        if path['Kind'] != 'hold' or path['SlackNS'] >= 0:
            continue
        target, proof = selected_branch(path, graph, placements)
        key = target['Net'], target['ToRoutePin']
        require(key not in targets or targets[key] == target, 'ambiguous selected physical leaf')
        targets[key] = target; branches[key].add(tuple(hold.common.identity(path)))
        proofs.append({'PathSHA256': path['PathSHA256'], 'Target': target, 'Proof': proof})
    targets = [targets[key] for key in sorted(targets)]
    require(len(targets) == 8 and {t['Net'] for t in targets} == NETS, 'current minimal control branch inventory differs')
    require(set().union(*branches.values()) == identities, 'negative hold relationship not covered by selected branch')
    dump = discovery_path.parent/'route-dump.txt'
    require(discovery['Artifacts']['route-dump.txt'] == sha(dump), 'full route dump is unbound')
    parsed = inspect_routes(dump, targets)
    selections, wire = select_waypoints(parsed, targets)
    audit = {'Schema': 'camera720-calibrated-stats-measured-control-branches-v1', 'Target': prep.TARGET,
             'SourceADF': ref(discovery['SourceADF']), 'DiscoveryReceipt': ref(discovery_path), 'ExportReceipt': ref(export_path),
             'InputReports': provenance, 'FullReport': ref(full), 'Netlist': ref(netlist),
             'HoldIdentityCount': len(identities), 'NegativeDetailedCases': len(proofs), 'SelectedBranchCount': len(targets),
             'Relations': relation_rows, 'Targets': targets, 'NegativePathBranchProofs': proofs,
             'Branches': [{'Target': target, 'AffectedFailingIdentities': [list(v) for v in sorted(branches[(target['Net'], target['ToRoutePin'])])]}
                          for target in targets], 'MissingExactSetup': [],
             'CarryWiresChanged': False, 'ExternalInputBudgetChanged': False, 'TimingAccepted': False}
    for module in (inspect, inspect.prep, inspect.diagnostic, inspect.diagnostic.cleanup, graph_tools,
                   graph_tools.video, graph_tools.cdc, graph_tools.cdc.clm, graph_tools.cdc.endpoints,
                   graph_tools.structure.monitor, hold, hold.common, routes, routes.common,
                   waypoint_helper, lifecycle, metadata):
        add(watched, module.__file__)
    add(watched, lifecycle.SERIALIZER); add(watched, wire); add(watched, SELF)
    require(not inspect.drift(watched), 'derivation input drift')
    return discovery, watched, audit, targets, parsed, selections, wire


def route_commands(rows, targets, occupied):
    require(len(rows) == len(targets), 'all selected branches required')
    expected = {(t['Net'], t['ToRoutePin']) for t in targets}; seen, reserved, commands = set(), set(), []
    for row in rows:
        require(set(row) == {'Net', 'Branch', 'Pins'}, 'exact route fields required')
        key = row['Net'], row['Branch']
        require(key in expected and key not in seen and row['Net'] in NETS, 'unmeasured/duplicate net or branch')
        require(re.fullmatch(lifecycle.route_helpers.WAYPOINT, row['Branch'])
                and re.fullmatch(lifecycle.route_helpers.CHAIN, row['Pins']), 'one exact official waypoint pair required')
        pins = row['Pins'].rstrip(';').split('>')
        require(len(set(pins)) == 2 and not reserved.intersection(pins), 'shared requested waypoint')
        require(all(not occupied.get(pin) for pin in pins), 'occupied waypoint')
        seen.add(key); reserved.update(pins)
        commands += ['show -design_net {'+row['Net']+'}', 'unroute -branch {'+row['Net']+':'+row['Branch']+';}',
                     'manual_route -net {'+row['Net']+'} -branch {'+row['Branch']+'} -pins {'+row['Pins']+'}',
                     'show -design_net {'+row['Net']+'}']
    require(seen == expected, 'missing selected branch')
    return commands


def compare_inventory(before, after, targets, requested):
    require(set(before['NetAnnotations']) == set(after['NetAnnotations']), 'native net inventory changed')
    changed = {n for n, h in before['NetAnnotations'].items() if after['NetAnnotations'][n] != h}
    require({routes.annotation_name(n) for n in changed} == {t['Net'] for t in targets}, 'unrequested route changed or requested route unchanged')
    checks = []
    for net, old in before['BranchInventory'].items():
        new = after['BranchInventory'][net]
        require(old['LogicalConnections'] == new['LogicalConnections'] and set(old['Leaves']) == set(new['Leaves']), 'logical connections or leaves changed')
        selected = {t['ToRoutePin'] for t in targets if t['Net'] == net}
        for leaf, chain in old['Leaves'].items():
            if leaf not in selected:
                require(chain == new['Leaves'][leaf], 'unrequested sibling path changed: '+net+':'+leaf)
        checks.append({'Net': net, 'TotalLeaves': len(old['Leaves']), 'RequestedLeaves': len(selected),
                       'UnrequestedSiblingsPreserved': len(old['Leaves'])-len(selected)})
    require(len(requested) == len(targets), 'route comparison coverage differs')
    for target, row in zip(targets, requested):
        require((target['Net'], target['ToRoutePin']) == (row['Net'], row['Branch']), 'route order differs')
        old = before['BranchInventory'][target['Net']]['Leaves'][target['ToRoutePin']]
        new = after['BranchInventory'][target['Net']]['Leaves'][target['ToRoutePin']]
        pins = row['Pins'].rstrip(';').split('>')
        require(new != old and any(new[i:i+len(pins)] == pins for i in range(len(new)-len(pins)+1)), 'requested contiguous detour absent')
    return changed, checks


def compare_route_dumps(original, derived, targets, requested):
    before, after = inspect_routes(original, targets), inspect_routes(derived, targets)
    changed, checks = compare_inventory(before, after, targets, requested)
    parser = lifecycle.serialization_module()
    a, b = parser.extract(Path(original)), parser.extract(Path(derived))
    refs = parser.reference_comparison(a, b)
    for key in ('DefinitionsEqual', 'ParentObjectsEqual', 'AllFullEntriesEqualWithinParent',
                'AllResolvedEntriesEqualWithinParent', 'OtherNonRouteTokensEqual'):
        require(refs[key] is True, 'functional/placement/constraint change: '+key)
    require(a['ExcludedBlocks']['CDB']['TokenSHA256'] == b['ExcludedBlocks']['CDB']['TokenSHA256'], 'CDB definitions changed')
    if a['ExcludedBlocks']['FILETABLE']['Tokens'] == b['ExcludedBlocks']['FILETABLE']['Tokens']:
        require(a['SourceAnnotationsOutsideCDBEntries'] == b['SourceAnnotationsOutsideCDBEntries'], 'source location metadata changed')
        source_metadata = {'Identical': True}
    else:
        source_metadata = metadata.metadata_change(a, b)
    return {'Passed': True, 'ChangedNets': sorted(changed), 'ChangedNetCount': len(changed),
            'RouteCount': len(before['NetAnnotations']), 'AllOtherRoutesUnchanged': True,
            'BranchChecks': checks, 'FunctionalAndPlacementSemanticsUnchanged': True,
            'FullCDBDefinitionsAndPerParentReferencesIdentical': True,
            'CDBDefinitionCount': refs['DefinitionCountBefore'], 'CDBReferenceCount': refs['EntryCountBefore'],
            'CDBParentCount': len(refs['ParentChecks']), 'SourceMetadataDisposition': source_metadata,
            'StrictNonRouteTokensIdentical': before['NonRouteSemanticSHA256'] == after['NonRouteSemanticSHA256'],
            'TimingAcceptanceImplied': False}


def bind_request(request_path):
    watched = {}; request_path = add(watched, request_path); request = read(request_path)
    require(set(request) == {'Schema', 'Target', 'DiscoveryReceipt', 'ExportReceipt'}
            and request['Schema'] == REQUEST_SCHEMA and request['Target'] == prep.TARGET, 'exact statistics route request required')
    discovery_path = binding(request['DiscoveryReceipt'], watched)
    export_path = binding(request['ExportReceipt'], watched)
    value, bound, audit, targets, parsed, selections, wire = derive(discovery_path, export_path)
    watched.update(bound)
    rows = [{'Net': row['Target']['Net'], 'Branch': row['Target']['ToRoutePin'],
             'Pins': '>'.join(row['Selected']['Pins'])+';'} for row in selections]
    lifecycle.route_helpers.validate_waypoint_evidence({'Schema': 'raw-camera-waypoint-selection-v1',
        'WirePattern': ref(wire), 'Selections': selections}, rows, targets, parsed)
    commands = route_commands(rows, targets, parsed['_Occupied'])
    expanded = {**request, 'BuildPlan': ref(value['BuildPlan']), 'BuildDiagnosticsReview': value['BuildDiagnosticsReview'],
                'RouteDump': ref(discovery_path.parent/'route-dump.txt'), 'Routes': rows, 'Audit': audit,
                'Waypoints': selections, 'WirePattern': ref(wire)}
    return expanded, read(value['BuildPlan']), Path(value['SourceADF']), targets, commands, watched


def render(commands,work):
    w=work.as_posix()
    return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
            'add_design {'+w+'/dummy.v}\nif {[info script] ne {}} {\n    mpnr -input {'+w+'/input.adf}\n'
            '    '+INIT+'\n    file copy {'+w+'/input.adf} {'+w+'/post-init.adf}\n'
            +'\n'.join(commands)+'\n    save_adif\n'
            '    file copy {'+w+'/input.adf} {'+w+'/saved-route.adf}\n'
            '    .switch_db -route -input {'+w+'/input.adf} -output {'+w+'/route-dump.txt}\n'
            '    puts {'+MARKER+'}\n    flush stdout\n}\n')


def recipe(request,work,maximum=300):
    work=prep.work_path(work);require(type(maximum)is int and 120<=maximum<=300,'bound must be120..300 seconds')
    r,build,source,targets,commands,watched=bind_request(request)
    tcl=render(commands,work)
    value={'Schema':SCHEMA,'Target':prep.TARGET,'Mode':'save-route-only','WorkDirectory':str(work),
        'Request':{'Path':str(Path(request).absolute()),'SHA256':sha(request)},
        'BuildPlan':r['BuildPlan']['Path'],'BuildPlanSHA256':r['BuildPlan']['SHA256'],
        'SourceADF':str(source),'SourceADFSHA256':ORIGINAL_ADF,'BuildDiagnosticsReview':r['BuildDiagnosticsReview'],
        'BuildExecutionCompletedWithoutError':False,'BuildDiagnosticsCleared':False,
        'OriginalRouteDump':r['RouteDump'],'Routes':r['Routes'],'MeasuredTargets':targets,
        'OriginalExportReceipt':r['ExportReceipt'],'MeasuredHoldAudit':r['Audit'],
        'Waypoints':r['Waypoints'],'WirePattern':r['WirePattern'],
        'ExactRouteCommands':commands,'ExactResetCommands':[],'ResetProof':None,
        'MaximumSeconds':maximum,'ExpectedActualStages':[],
        'InputSHA256':{str(p):h for p,h in watched.items()},'TclSHA256':hashlib.sha256(tcl.encode('ascii')).hexdigest(),
        'Command':[build['PDS']['Executable'],'-file',(work/'stage.tcl').as_posix(),'-work_dir',work.as_posix(),'-project_name',prep.TARGET],
        'HardwareAccessed':False,'BitstreamRequested':False,'TimingAccepted':False,'HardwareReleaseAllowed':False,
        'FinalSTAExecuted':False,'DataTimingWaiverAllowed':False,'ConstraintsApplied':False,'DiagnosticCopyOnly':True}
    return value,tcl,watched


def prepare(request,work,maximum=300):
    value,tcl,watched=recipe(request,work,maximum);work=Path(value['WorkDirectory'])
    require(not work.exists() and not inspect.drift(watched),'fresh stage and stable inputs required');work.mkdir()
    shutil.copyfile(value['SourceADF'],work/'input.adf');shutil.copyfile(SELF,work/'executor-snapshot.py')
    (work/'stage.tcl').write_text(tcl,encoding='ascii',newline='\n')
    (work/'dummy.v').write_text(DUMMY,encoding='ascii',newline='\n')
    value['PreparedUTC']=inspect.utc();inspect.diagnostic.write(work/'stage-plan.json',value)
    return work/'stage-plan.json'


def bound_plan(path,fresh):
    path=inspect.canonical(path,prep.WORK);work=prep.work_path(path.parent);value=read(path)
    require(path.name=='stage-plan.json' and value.get('Schema')==SCHEMA,'exact statistics hold-route stage-plan required')
    expected,tcl,watched=recipe(value['Request']['Path'],work,value['MaximumSeconds'])
    require(set(value)==set(expected)|{'PreparedUTC'} and isinstance(value['PreparedUTC'],str) and value['PreparedUTC']
            and {k:v for k,v in value.items() if k!='PreparedUTC'}==expected,'physical plan differs from exact recipe')
    files={'stage-plan.json','stage.tcl','dummy.v','input.adf','executor-snapshot.py'}
    if fresh:require({p.name for p in work.iterdir()}==files,'physical stage contaminated or reused')
    require((work/'stage.tcl').read_bytes()==tcl.encode('ascii') and (work/'dummy.v').read_bytes()==DUMMY.encode('ascii')
            and sha(work/'executor-snapshot.py')==sha(SELF),'physical stage instruction drift')
    if fresh:require(sha(work/'input.adf')==ORIGINAL_ADF,'physical input copy differs')
    for name in files-{'input.adf'}:add(watched,work/name)
    require(not inspect.drift(watched),'physical stage input drift')
    return value,watched


def validate_prepared(path):return bound_plan(path,True)


def artifact_hashes(work):
    return {p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()
            and p.suffix in ARTIFACT_SUFFIXES and p.name!='result.json'}


def execution_ok(value):
    return (value.get('Schema')==SCHEMA and value.get('Target')==prep.TARGET and value.get('ExitCode')==0
        and value.get('EDAExecuted') is True and not value.get('Error') and value.get('TimedOut') is False
        and value.get('StoppedForUnexpectedStage') is False and value.get('InputDrift')==[]
        and value.get('Diagnostics')==[] and value.get('ActualEvents')==[] and value.get('CompletionMarker') is True
        and value.get('InitializationPreservedADF') is True and value.get('SavedADFReadbackMatches') is True
        and value.get('ResultADFChanged') is True and value.get('Cleanup',{}).get('Complete') is True
        and value.get('RouteComparison',{}).get('Passed') is True)


def bind_completed(path,watched):
    path=inspect.canonical(path,prep.WORK);work=path.parent;value=read(path)
    require(path.name=='result.json' and value.get('ExecutionPassed') is True and execution_ok(value),'clean current statistics hold-route save required')
    plan,bound=bound_plan(work/'stage-plan.json',False);watched.update(bound)
    require(all(value.get(k)==v for k,v in plan.items()) and value['StagePlanSHA256']==sha(work/'stage-plan.json'),
            'physical receipt differs from exact plan')
    require(value['Artifacts']==artifact_hashes(work),'physical artifact inventory/bytes differ')
    for name,digest in value['Artifacts'].items():add(watched,inspect.canonical(work/name,work),digest)
    require(inspect.scan_diagnostics(work)==[],'physical critical/error diagnostics present')
    log=(work/'stdout.log').read_text(encoding='gb18030',errors='replace')
    require(inspect.diagnostic.stage_events(log)==[] and MARKER in log,'physical stage events/marker differ')
    require(sha(work/'post-init.adf')==ORIGINAL_ADF and sha(work/'input.adf')==sha(work/'saved-route.adf')==value['ResultADFSHA256']
            and value['ResultADFSHA256']!=ORIGINAL_ADF,
            'physical ADF initialization/save chain differs')
    for name in ('input.adf','post-init.adf','saved-route.adf'):
        p=work/name
        require(value['ADFReadback'][name]=={'Path':str(p),'SHA256':sha(p),'Bytes':p.stat().st_size},'ADF readback record differs')
    require(value['ResultADF']==value['ADFReadback']['input.adf'],'result ADF record differs')
    require(value.get('NativeRouteDump')==ref(work/'route-dump.txt'),'saved native route reference differs')
    comparison=compare_route_dumps(value['OriginalRouteDump']['Path'],work/'route-dump.txt',
                                   value['MeasuredTargets'],value['Routes'])
    require(value['RouteComparison']==comparison,'saved route preservation proof differs from actual full dumps')
    add(watched,path);require(not inspect.drift(watched),'physical completed evidence drift')
    return value


def execute(path):
    value,watched=validate_prepared(path);work=Path(value['WorkDirectory'])
    require(os.name=='nt','native PDS requires Windows')
    result={**value,'StagePlanSHA256':sha(path),'StartedUTC':inspect.utc(),'EDAExecuted':False,'ExecutionPassed':False,
            'TimedOut':False,'StoppedForUnexpectedStage':False,'ExitCode':None}
    inspect.diagnostic.write(work/'execution-start.json',result);process=None;started=time.monotonic()
    try:
        with (work/'stdout.log').open('xb') as out,(work/'stderr.log').open('xb') as err:
            process=subprocess.Popen(value['Command'],cwd=work,stdout=out,stderr=err,shell=False,
                                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));result.update(EDAExecuted=True,OwnedPID=process.pid)
            while process.poll() is None:
                remaining=value['MaximumSeconds']-(time.monotonic()-started)
                if remaining<=0:result['TimedOut']=True;break
                try:process.wait(timeout=min(2,remaining))
                except subprocess.TimeoutExpired:pass
                if inspect.diagnostic.stage_events((work/'stdout.log').read_text(encoding='gb18030',errors='replace')):
                    result['StoppedForUnexpectedStage']=True;break
    except BaseException as error:result['Error']=type(error).__name__+': '+str(error)
    finally:
        if process is not None:
            result['Cleanup']=(inspect.diagnostic.cleanup.stop_owned_tree(process,work,'bounded statistics hold-route only') if process.poll() is None
                               else {'Complete':True,'OwnedPID':process.pid,'ParentExited':True,'DescendantLivenessIndependentlyVerified':False})
            result['ExitCode']=process.poll()
        else:result['Cleanup']={'Complete':True,'Required':False}
    try:
        log=(work/'stdout.log').read_text(encoding='gb18030',errors='replace') if (work/'stdout.log').exists() else ''
        adfs={n:{'Path':str(work/n),'SHA256':sha(work/n),'Bytes':(work/n).stat().st_size}
              for n in ('input.adf','post-init.adf','saved-route.adf') if (work/n).is_file()}
        final=adfs.get('input.adf',{}).get('SHA256')
        result.update(ActualEvents=inspect.diagnostic.stage_events(log),InputDrift=inspect.drift(watched),
            Diagnostics=inspect.scan_diagnostics(work),CompletionMarker=MARKER in log,ADFReadback=adfs,
            ResultADF=adfs.get('input.adf'),ResultADFSHA256=final,
            NativeRouteDump=ref(work/'route-dump.txt') if (work/'route-dump.txt').is_file() else None,
            InitializationPreservedADF=adfs.get('post-init.adf',{}).get('SHA256')==ORIGINAL_ADF,
            SavedADFReadbackMatches=bool(final) and adfs.get('saved-route.adf',{}).get('SHA256')==final,
            ResultADFChanged=bool(final) and final!=ORIGINAL_ADF,Artifacts=artifact_hashes(work))
        require(result['ExitCode']==0 and not result.get('Error') and not result['TimedOut']
                and not result['StoppedForUnexpectedStage'] and result['Diagnostics']==[]
                and result['ActualEvents']==[] and result['CompletionMarker'] and result['InputDrift']==[]
                and result['InitializationPreservedADF'] and result['SavedADFReadbackMatches'] and result['ResultADFChanged'],
                'native route initialization/save failed; preservation cannot be claimed')
        result['RouteComparison']=compare_route_dumps(value['OriginalRouteDump']['Path'],work/'route-dump.txt',
                                                       value['MeasuredTargets'],value['Routes'])
    except Exception as error:result['Error']=type(error).__name__+': '+str(error)
    result.update(FinishedUTC=inspect.utc(),ElapsedSeconds=round(time.monotonic()-started,3))
    result['ExecutionPassed']=execution_ok(result)
    inspect.diagnostic.write(work/'result.json',result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',type=Path);p.add_argument('--name')
    p.add_argument('--stage-plan',type=Path);p.add_argument('--maximum-seconds',type=int,default=300)
    mode=p.add_mutually_exclusive_group();mode.add_argument('--prepare-only',action='store_true');mode.add_argument('--execute',action='store_true');mode.add_argument('--validate-only',action='store_true')
    a=p.parse_args()
    if a.stage_plan:
        require(not a.request and not a.name and not a.prepare_only,'stage plan only accepts validation or execution')
        if a.execute:value=execute(a.stage_plan)
        else:validate_prepared(a.stage_plan);value={'Validated':True,'EDAExecuted':False}
    else:
        require(a.request and a.name and not a.execute,'prepare exact request first; execute only stage-plan')
        if a.prepare_only:value={'Prepared':True,'StagePlan':str(prepare(a.request,prep.WORK/a.name,a.maximum_seconds)),'EDAExecuted':False}
        else:recipe(a.request,prep.WORK/a.name,a.maximum_seconds);value={'Validated':True,'EDAExecuted':False}
    print(json.dumps({k:value[k] for k in ('Prepared','Validated','StagePlan','ExecutionPassed','ExitCode','ResultADFSHA256','EDAExecuted') if k in value}))
    return 0 if value.get('ExecutionPassed',True) else 1


if __name__=='__main__':raise SystemExit(main())
