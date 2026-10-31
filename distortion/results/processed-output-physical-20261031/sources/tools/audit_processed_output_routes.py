"""Compare complete native ADIF dumps around the single _N107 data detour.

Streams the actual textual database. Every NETANNOTATE is compared, and all
remaining functional/placement/library tokens must match after excluding only
the named metadata and CDB blocks. CDB effects require the separate STA audit.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import re

TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|\\[^\s]+|[()]|[^\s()]+')
TARGET = '_N107'
FIRST_PIN = 'CR2:CLMA_345_852'
LAST_PIN = 'M3:CLMS_339_847'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def feed(digest, tokens):
    if tokens:
        digest.update(('\0'.join(tokens) + '\0').encode('utf-8'))


def expression(tokens):
    stack, roots = [], []
    for token in tokens:
        if token == '(':
            value = []
            if stack:
                stack[-1].append(value)
            else:
                roots.append(value)
            stack.append(value)
        elif token == ')':
            require(stack, 'unbalanced route expression')
            stack.pop()
        else:
            require(stack, 'atom outside route expression')
            stack[-1].append(token)
    require(not stack and len(roots) == 1, 'one complete route expression required')
    return roots[0]


def linear_route(tokens):
    tree = expression(tokens)
    require(len(tree) == 3 and tree[0] == 'NETANNOTATE' and tree[1] == ['NETREF',TARGET]
            and tree[2][0] == 'ROUTE' and len(tree[2]) == 2,
            'target annotation must contain exactly its net reference and one route')
    node, pins = tree[2][1], []
    while True:
        require(isinstance(node,list) and len(node) in (1,2), 'target route has a branch or malformed node')
        port = node[0]
        require(isinstance(port,list) and len(port) == 3 and port[0] == 'PORTREF', 'route port missing')
        name, device = port[1], port[2]
        if isinstance(name,list):
            require(len(name) == 3 and name[0] == 'INDEXED' and name[2].isdigit(), 'invalid indexed route pin')
            name = name[1] + '[' + name[2] + ']'
        require(isinstance(device,list) and len(device) == 3 and device[0] == 'DEVINSTREF'
                and len(device[2]) == 3 and device[2][0] == 'SITEREF'
                and all(v.isdigit() for v in device[2][1:]), 'invalid route device site')
        pins.append(name + ':' + device[1] + '_' + '_'.join(device[2][1:]))
        if len(node) == 1:
            break
        node = node[1]
    require(pins[0] == FIRST_PIN and pins[-1] == LAST_PIN, 'target physical driver/load changed')
    require(len(set(pins)) == len(pins), 'target route contains a repeated pin')
    return pins


def inspect_dump(path):
    path = Path(path).resolve()
    original = sha(path)
    global_digest = hashlib.sha256()
    annotations, exclusions, target_tokens, constraint_refs = {}, {}, [], []
    source_metadata = {'FILEID':0, 'LINENUM':0}
    source_digest = hashlib.sha256()
    active_tokens = []
    depth, line_count = 0, 0
    active, active_depth, active_digest, active_name = None, None, None, None
    metadata = {'OutputPath':0, 'Timestamp':0, 'SourceAttribute':0}
    with path.open(encoding='utf-8-sig', errors='strict') as stream:
        for line_count, line in enumerate(stream, 1):
            tokens = TOKEN.findall(line)
            require(not TOKEN.sub('',line).strip(), 'unparsed ADIF text')
            start_depth = depth
            depth += tokens.count('(') - tokens.count(')')
            require(depth >= 0, 'unbalanced ADIF closing parentheses')
            if active is None:
                if start_depth == 1 and tokens[:2] in (['(','CDB'], ['(','FILETABLE']):
                    active, active_name, active_depth, active_digest = 'excluded', tokens[1], start_depth, hashlib.sha256()
                    require(active_name not in exclusions, 'duplicate excluded top-level block')
                elif tokens[:2] == ['(','CDBENTRY']:
                    active, active_name, active_depth, active_digest = 'constraint-ref', 'CDBENTRY', start_depth, hashlib.sha256()
                    active_tokens = []
                elif tokens[:2] == ['(','NETANNOTATE']:
                    require(tokens[2:4] == ['(','NETREF'], 'native net annotation lacks NETREF')
                    active, active_depth, active_digest = 'annotation', start_depth, hashlib.sha256()
                    # The complete NETREF is on the opening line in this native dialect.
                    require(tokens[-1] == ')' and depth == start_depth + 1, 'multiline/ambiguous NETREF header')
                    active_name = ' '.join(tokens[4:-1])
                    require(active_name not in annotations, 'duplicate NETANNOTATE identity')
                elif line_count == 1:
                    require(tokens[:2] == ['(','ADIF'] and len(tokens) == 3 and tokens[2].startswith('"'),
                            'native ADIF header missing')
                    metadata['OutputPath'] += 1
                    tokens[2] = '"<OUTPUT_PATH>"'
                elif tokens[:2] == ['(','TIMESTAMP']:
                    require(len(tokens) == 4 and tokens[-1] == ')', 'unsupported timestamp metadata')
                    metadata['Timestamp'] += 1
                    tokens[2] = '"<TIMESTAMP>"'
                elif tokens[:2] == ['(','ATTR_FN']:
                    require(len(tokens) == 4 and tokens[-1] == ')', 'unsupported source-path metadata')
                    metadata['SourceAttribute'] += 1
                    tokens[2] = '<SOURCE_PATH>'
                elif tokens[:2] in (['(','FILEID'], ['(','LINENUM']):
                    require(len(tokens) == 4 and tokens[-1] == ')' and tokens[2].isdigit(),
                            'unsupported source location metadata')
                    source_metadata[tokens[1]] += 1
                    feed(source_digest, tokens)
                    continue
            if active is not None:
                feed(active_digest, tokens)
                if active == 'annotation' and active_name == TARGET:
                    target_tokens.extend(tokens)
                if active == 'constraint-ref':
                    active_tokens.extend(tokens)
                if depth == active_depth:
                    if active == 'annotation':
                        annotations[active_name] = active_digest.hexdigest()
                    elif active == 'constraint-ref':
                        constraint_refs.append({'Tokens':active_tokens, 'SHA256':active_digest.hexdigest()})
                    else:
                        exclusions[active_name] = active_digest.hexdigest()
                    active = active_depth = active_digest = active_name = None
            else:
                feed(global_digest, tokens)
    require(depth == 0 and active is None, 'truncated native ADIF')
    require(metadata == {'OutputPath':1,'Timestamp':1,'SourceAttribute':1}, 'unexpected metadata inventory')
    require(set(exclusions) == {'CDB','FILETABLE'} and TARGET in annotations and len(annotations) > 1000,
            'incomplete routed annotation database')
    pins = linear_route(target_tokens)
    require(sha(path) == original, 'native dump changed during audit')
    return {'Path':str(path), 'SHA256':original, 'Lines':line_count,
            'NonRouteSemanticSHA256':global_digest.hexdigest(),
            'NetAnnotations':annotations, 'TargetPins':pins,
            'ExcludedBlockSHA256':exclusions, 'NormalizedMetadataCounts':metadata,
            'ExcludedSourceLocations':{'Counts':source_metadata, 'SHA256':source_digest.hexdigest()},
            'ExcludedConstraintPinReferences':constraint_refs}


def compare(baseline, candidate):
    before, after = inspect_dump(baseline), inspect_dump(candidate)
    require(before['NonRouteSemanticSHA256'] == after['NonRouteSemanticSHA256'],
            'functional/library/placement/non-route native tokens changed')
    require(before['NetAnnotations'].keys() == after['NetAnnotations'].keys(), 'native net annotation set changed')
    changed = [name for name,digest in before['NetAnnotations'].items() if after['NetAnnotations'][name] != digest]
    require(changed == [TARGET], 'expected only one changed net annotation: ' + str(changed[:12]))
    require(before['TargetPins'] != after['TargetPins'], 'target route did not change')
    for value in (before,after):
        value['NetAnnotationCount'] = len(value['NetAnnotations'])
        value['TargetAnnotationSHA256'] = value['NetAnnotations'][TARGET]
        value['AllOtherNetAnnotationsSHA256'] = hashlib.sha256(json.dumps(
            {k:v for k,v in value['NetAnnotations'].items() if k != TARGET},
            sort_keys=True,separators=(',',':')).encode()).hexdigest()
        del value['NetAnnotations']
    return {'Schema':'processed-output-native-route-comparison-v1',
            'AuditedUTC':datetime.now(timezone.utc).isoformat(), 'AuditPassed':True,
            'OnlyChangedNetAnnotation':TARGET, 'AllOtherNetAnnotationsIdentical':True,
            'AllNonRouteSemanticTokensIdentical':True, 'TargetIsSingleDriverSingleLoadRoute':True,
            'TargetPhysicalDriver':FIRST_PIN, 'TargetPhysicalLoad':LAST_PIN,
            'Baseline':before, 'Candidate':after,
            'ToolSHA256':sha(__file__), 'HardwareAccessed':False, 'TimingAccepted':False,
            'ExcludedFromSemanticComparison':['ADIF output pathname','STATUS timestamp','UATTR ATTR_FN source pathname',
                                              'FILEID/LINENUM source location metadata (recorded counts/hash)',
                                              'CDBENTRY constraint pin references (all recorded verbatim tokens/hash)',
                                              'Top-level CDB constraint block','Top-level FILETABLE path table'],
            'Limits':['CDB constraints and timing effects must be checked by the separate native timing/exception audit.',
                      'This proves dump content equivalence outside the stated route and exclusions; dump-to-ADF provenance is separate.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',required=True,type=Path)
    parser.add_argument('--candidate',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args = parser.parse_args()
    result = compare(args.baseline,args.candidate)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(result,stream,indent=2)
        stream.write('\n')
    print(json.dumps({'AuditPassed':True,'OnlyChangedNetAnnotation':TARGET,
                      'ComparedNetAnnotations':result['Baseline']['NetAnnotationCount']}))


if __name__ == '__main__':
    main()
