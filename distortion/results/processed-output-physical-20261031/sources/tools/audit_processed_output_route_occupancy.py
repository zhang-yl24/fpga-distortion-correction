"""Independently inspect exact waypoint occupancy in native textual ADIF.

The dump uses numeric SITEREF coordinates, not SRB_x_y strings. Every physical
PORTREF in the sole ROUTING view must parse; known occupied pins cross-check
the baseline evidence. Absence is meaningful only within this complete view.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re


PROJECT = Path(__file__).resolve().parents[1]
NODE = re.compile(r'\(PORTREF (?:\(INDEXED ([^\s()]+) (\d+)\)|([^\s()]+)) '
                  r'\(DEVINSTREF ([^\s()]+) \(SITEREF (\d+) (\d+)\)\)\)')
TARGET = '(NETANNOTATE (NETREF _N107)'
SITES = {(342, 816), (348, 822), (342, 822), (348, 828)}
WIRE = Path('D:/pango/PDS_2023.2/arch/vendor/pango/logos2/pg2l100h/pattern/drawing/wirepattern.txt')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_routes(path):
    routes, occupied, target = {}, defaultdict(list), []
    routing, views, owner, block, nodes, total = False, 0, None, [], 0, 0
    for number, line in enumerate(Path(path).open(encoding='utf-8'), 1):
        if '(VIEWANNOTATE ' in line and ' ROUTING ' in line:
            views += 1
            require(views == 1, 'multiple ROUTING views are unsupported')
            routing = True
        if not routing:
            continue
        if line.startswith('      (NETANNOTATE (NETREF '):
            require(owner is None, 'unterminated native net route block')
            owner, block, nodes = line.strip(), [], 0
            require(owner not in routes, 'duplicate native route identity')
        if owner is None:
            require('(PORTREF ' not in line, 'physical PORTREF outside a route block')
            continue
        block.append(line)
        if '(PORTREF ' in line:
            match = NODE.search(line)
            require(match is not None, 'unparsed physical node at line ' + str(number))
            require(line.count('(PORTREF ') == 1, 'multiple physical nodes on a native line')
            port = match[3] or match[1] + '[' + match[2] + ']'
            kind, xy = match[4], (int(match[5]), int(match[6]))
            identity = f'{port}:{kind}_{xy[0]}_{xy[1]}'
            row = {'Line': number, 'Owner': owner, 'Node': identity, 'Native': line.strip()}
            if kind == 'SRB' and xy in SITES and port.startswith(('ZDNE[', 'IDNE[')):
                occupied[identity].append(row)
            if owner == TARGET:
                target.append(row)
            nodes += 1
            total += 1
        if line == '      )\n':
            require(nodes > 0 and sum('(ROUTE' in item for item in block) == 1,
                    'native route block lacks its physical tree')
            # Includes native nesting and every node, excludes mutable dump timestamp.
            routes[owner] = {'NodeCount': nodes,
                             'NativeTreeSHA256': hashlib.sha256(''.join(block).encode()).hexdigest()}
            owner, block = None, []
    require(views == 1 and owner is None and routes and target, 'incomplete native route inventory')
    return {'RouteCount': len(routes), 'PhysicalNodeCount': total, 'UnparsedPhysicalNodes': 0,
            'NativeRouteTrees': routes, 'SelectedOccupancy': dict(occupied), 'TargetRoute': target}


def audit(dump_path, output, *, baseline=False):
    dump = Path(dump_path).resolve()
    require(dump.is_file() and dump.is_relative_to(PROJECT / 'build/processed-output'),
            'dump must be in the isolated task build')
    receipt_path, adf = dump.parent / 'result.json', dump.parent / 'input.adf'
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    require(receipt.get('ExecutionPassed') is True and not receipt.get('InputDrift')
            and receipt.get('ResultADFSHA256') == sha(adf), 'native dump receipt/ADF differs')
    watched = {path: sha(path) for path in (dump, receipt_path, adf, WIRE, Path(__file__).resolve())}
    parsed = parse_routes(dump)
    require(parsed['RouteCount'] == 35847, 'candidate route inventory changed')
    wire = WIRE.read_text()
    candidates = []
    for start, end in (((342, 816), (348, 822)), ((342, 822), (348, 828))):
        for channel in range(4):
            a, b = f'ZDNE[{channel}]:SRB_{start[0]}_{start[1]}', f'IDNE[{channel}]:SRB_{end[0]}_{end[1]}'
            matching = [line for line in wire.splitlines() if line.startswith(f'ZDNE[{channel}] :')]
            require(len(matching) == 1 and f'[ IDNE[{channel}] ]' in matching[0], 'official wire rule changed')
            owners = [parsed['SelectedOccupancy'].get(pin, []) for pin in (a, b)]
            candidates.append({'Pins': [a, b], 'Owners': owners, 'BothPinsUnusedInDump': not any(owners),
                               'OfficialWireRule': matching[0]})
    if baseline:
        require(sha(adf) == '97df0e42848650499802b2cf0e4375f420b4c2c98cc55bd9e2dc97fb62a5b980',
                'baseline ADF identity differs')
        require(parsed['PhysicalNodeCount'] == 607829 and len(parsed['TargetRoute']) == 8,
                'baseline native route inventory differs')
        require(candidates[1]['BothPinsUnusedInDump'] and not candidates[0]['BothPinsUnusedInDump'],
                'known occupied/unused baseline channel evidence differs')
        require(all('ddrphy_dqs_rddata_align/N124' in row['Owner']
                    for owners in candidates[0]['Owners'] for row in owners),
                'known native Route-0027 occupied owner differs')
    result = {'Schema': 'processed-output-native-route-inventory-v1', 'AuditPassed': True,
              'Baseline': baseline, 'NativeSourceADF': str(adf), 'NativeSourceADFSHA256': sha(adf),
              'InputSHA256': {str(path): digest for path, digest in watched.items()},
              **parsed, 'WaypointCandidates': candidates, 'HardwareAccessed': False,
              'TimingAccepted': False,
              'Limit': 'Unused pins and a wire pattern establish a candidate route segment; only native routing and STA establish feasibility and timing.'}
    require(all(sha(path) == digest for path, digest in watched.items()), 'audit input changed')
    output = Path(output).resolve()
    require(output.parent == dump.parent and not output.exists(), 'output must be new in the native dump directory')
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'AuditPassed': True, 'Output': str(output), 'SHA256': sha(output),
                      'RouteCount': parsed['RouteCount'], 'PhysicalNodeCount': parsed['PhysicalNodeCount'],
                      'TargetRouteNodes': len(parsed['TargetRoute'])}))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dump', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', action='store_true')
    args = parser.parse_args()
    audit(args.dump, args.output, baseline=args.baseline)
