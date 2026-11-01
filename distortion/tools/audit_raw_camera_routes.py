"""Inspect multi-branch native data routes; compare every unaffected branch.

The original semantic/occupancy parser is reused without its linear-only
target assumptions. Targets come from current native timing, not old net IDs.
"""
from pathlib import Path
import re

import audit_camera_vga_routes as common

require, sha = common.require, common.sha


def net_name(value):
    return common.port_name(value).lstrip('\\')


def annotation_name(value):
    return net_name(common.expression(common.TOKEN.findall(value)) if value.startswith('(') else value)


def route_leaves(tree):
    require(isinstance(tree, list) and len(tree) == 2 and tree[0] == 'ROUTE', 'one native route root required')
    leaves = {}

    def walk(node, prefix):
        require(isinstance(node, list) and node, 'empty route node')
        item = node[0]
        require(isinstance(item, list) and len(item) == 3 and item[0] == 'PORTREF', 'route node missing PORTREF')
        device = item[2]
        require(isinstance(device, list) and len(device) == 3 and device[0] == 'DEVINSTREF'
                and isinstance(device[2], list) and len(device[2]) == 3 and device[2][0] == 'SITEREF'
                and all(v.isdigit() for v in device[2][1:]), 'invalid route device/site')
        pin = common.port_name(item[1]) + ':' + device[1] + '_' + '_'.join(device[2][1:])
        require(pin not in prefix, 'cyclic route path')
        path = prefix + [pin]
        if len(node) == 1:
            require(pin not in leaves, 'ambiguous repeated route leaf')
            leaves[pin] = path
        for child in node[1:]:
            walk(child, path)

    walk(tree[1], [])
    require(leaves, 'route has no terminal branches')
    return leaves


def target_tokens(path, names):
    found = {'NET': {}, 'NETANNOTATE': {}}
    depth, active, start, saved = 0, None, None, []
    for line in Path(path).open(encoding='utf-8-sig'):
        tokens = common.TOKEN.findall(line)
        require(not common.TOKEN.sub('', line).strip(), 'unparsed native tokens')
        previous = depth
        depth += tokens.count('(') - tokens.count(')')
        require(depth >= 0, 'unbalanced route dump')
        if active is None and tokens[:2] in (['(', 'NET'], ['(', 'NETANNOTATE']):
            active, start, saved = tokens[1], previous, []
        if active is not None:
            saved.extend(tokens)
            if depth == start:
                tree = common.expression(saved)
                if active == 'NET':
                    if isinstance(tree[1], list) and tree[1][0] == 'ARRAY':
                        array = tree[1]
                        require(len(array) == 4 and all(v.isdigit() for v in array[2:]), 'invalid net ARRAY')
                        low, high = sorted(map(int, array[2:]))
                        for item in tree[2:]:
                            if item[0] != 'CONNECT':
                                continue
                            require(item[1][0] == 'NETREF', 'array connection lacks indexed reference')
                            index = item[1][1]
                            require(isinstance(index, list) and len(index) == 3 and index[0] == 'INDEXED'
                                    and index[1] == array[1] and index[2].isdigit()
                                    and low <= int(index[2]) <= high, 'array member outside declaration')
                            member = net_name(index)
                            if member in names:
                                require(member not in found['NET'], 'duplicate indexed connection')
                                found['NET'][member] = ['NET', member, ['CONNECT', *item[2:]]]
                        active = None
                        continue
                    name = net_name(tree[1])
                else:
                    require(len(tree) >= 2 and tree[1][0] == 'NETREF', 'missing NETREF')
                    name = net_name(tree[1][1])
                if name in names:
                    require(name not in found[active], 'duplicate target net/route')
                    found[active][name] = tree
                active = None
    require(depth == 0 and active is None, 'truncated route dump')
    require(set(found['NET']) == set(found['NETANNOTATE']) == set(names), 'target inventory missing')
    return found


def inspect(path, targets):
    """targets is a list so two distinct branches on the same net stay distinct."""
    path = Path(path).resolve()
    before = sha(path)
    parsed = common.inspect(path, {})
    names = {t['Net'] for t in targets}
    require(targets and len({(t['Net'], t['ToRoutePin']) for t in targets}) == len(targets), 'duplicate target branch')
    blocks = target_tokens(path, names)
    inventories = {}
    for name in sorted(names):
        tree = blocks['NETANNOTATE'][name]
        require(len(tree) == 3 and tree[0] == 'NETANNOTATE', 'unexpected route annotation')
        leaves = route_leaves(tree[2])
        logical = blocks['NET'][name]
        require(len(logical) == 3 and logical[0] == 'NET' and logical[2][0] == 'CONNECT', 'unexpected logical net')
        connections = []
        for item in logical[2][1:]:
            require(len(item) == 3 and item[0] == 'PORTREF' and item[2][0] == 'INSTREF'
                    and len(item[2]) == 2, 'invalid logical connection')
            connections.append({'Instance': item[2][1].lstrip('\\'), 'Pin': common.port_name(item[1])})
        for target in [t for t in targets if t['Net'] == name]:
            end = target['ToRoutePin']
            require(end in leaves and leaves[end][0] == target['FromRoutePin'], 'STA physical source/target differs')
            instance, pin = target['Endpoint'].rsplit('/', 1)
            require({'Instance': instance, 'Pin': pin} in connections, 'STA logical target absent from native net')
            require(len(connections) == target['Fanout'] + 1, 'actual logical fanout differs from STA')
        inventories[name] = {'Leaves': leaves, 'LogicalConnections': connections}
    require(sha(path) == before, 'route dump changed')
    return {**parsed, 'BranchInventory': inventories}


def compare(before, after, targets, allow_constraint_change=False):
    require(before['NonRouteSemanticSHA256'] == after['NonRouteSemanticSHA256'], 'functional/placement semantics changed')
    require(set(before['NetAnnotations']) == set(after['NetAnnotations']), 'native net inventory changed')
    require(before['ExcludedBlockSHA256']['FILETABLE'] == after['ExcludedBlockSHA256']['FILETABLE'], 'native file table changed')
    if not allow_constraint_change:
        require(before['ExcludedBlockSHA256']['CDB'] == after['ExcludedBlockSHA256']['CDB'], 'constraint database changed')
    changed = {name for name, digest in before['NetAnnotations'].items() if after['NetAnnotations'][name] != digest}
    # Scalar identifiers may have the native escape prefix; indexed identifiers
    # retain the same spelling in both raw annotation inventories.
    normalized_changed = {annotation_name(name) for name in changed}
    permitted = {t['Net'] for t in targets}
    require(normalized_changed <= permitted, 'unrequested net routes changed: ' + repr(normalized_changed - permitted))
    checks = []
    for name, old in before['BranchInventory'].items():
        new = after['BranchInventory'][name]
        require(old['LogicalConnections'] == new['LogicalConnections'], 'logical connections changed')
        require(set(old['Leaves']) == set(new['Leaves']), 'physical route leaves changed')
        requested = {t['ToRoutePin'] for t in targets if t['Net'] == name}
        for leaf, path in old['Leaves'].items():
            if leaf not in requested:
                require(path == new['Leaves'][leaf], 'unrequested sibling branch changed: ' + name + ':' + leaf)
        checks.append({'Net': name, 'UnchangedOtherBranches': len(old['Leaves']) - len(requested)})
    return {'Passed': True, 'ChangedNetCount': len(changed), 'ChangedNets': sorted(changed),
            'OtherBranchChecks': checks, 'AllOtherRoutesUnchanged': True,
            'FunctionalAndPlacementSemanticsUnchanged': True, 'TimingAcceptanceImplied': False}
