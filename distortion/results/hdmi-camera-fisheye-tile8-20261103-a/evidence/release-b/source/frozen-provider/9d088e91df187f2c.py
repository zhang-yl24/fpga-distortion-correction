"""Audit three current camera data routes without changing a native database.

Targets and physical endpoints come from this candidate's hold audit. Every
NETANNOTATE is hashed; complete target trees must be linear, with two logical
connections. Only explicit output/timestamp/source-file metadata is normalized.
The compare mode rejects changed constraints or any other semantic content.
Unused waypoint pins are candidates, not proof of route feasibility or delay.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from audit_camera_vga_hold import require, sha

TOKEN=re.compile(r'"(?:[^"\\]|\\.)*"|\\[^\s]+|[()]|[^\s()]+')
NODE=re.compile(r'\(PORTREF (?:\(INDEXED ([^\s()]+) (\d+)\)|([^\s()]+)) '
                r'\(DEVINSTREF ([^\s()]+) \(SITEREF (\d+) (\d+)\)\)\)')
WIRE_DEFAULT=Path('D:/pango/PDS_2023.2/arch/vendor/pango/logos2/pg2l100h/pattern/drawing/wirepattern.txt')

def feed(digest,tokens):
    if tokens:
        digest.update(('\0'.join(tokens)+'\0').encode())

def expression(tokens):
    stack,roots=[],[]
    for token in tokens:
        if token=='(':
            value=[]
            if stack:stack[-1].append(value)
            else:roots.append(value)
            stack.append(value)
        elif token==')':
            require(stack,'unbalanced native expression');stack.pop()
        else:
            require(stack,'atom outside native expression');stack[-1].append(token)
    require(not stack and len(roots)==1,'one complete expression required')
    return roots[0]

def port_name(value):
    if isinstance(value,list):
        require(len(value)==3 and value[0]=='INDEXED' and value[2].isdigit(),'bad indexed port')
        return value[1]+'['+value[2]+']'
    return value

def linear_tree(tokens,name,expected):
    tree=expression(tokens)
    require(len(tree)==3 and tree[:2]==['NETANNOTATE',['NETREF',name]]
            and tree[2][0]=='ROUTE' and len(tree[2])==2,'one target ROUTE required')
    node,pins=tree[2][1],[]
    while True:
        require(isinstance(node,list) and len(node) in (1,2),'target route branches')
        item=node[0]
        require(len(item)==3 and item[0]=='PORTREF','target port missing')
        dev=item[2]
        require(len(dev)==3 and dev[0]=='DEVINSTREF' and len(dev[2])==3
                and dev[2][0]=='SITEREF' and all(v.isdigit() for v in dev[2][1:]),'bad target site')
        pins.append(port_name(item[1])+':'+dev[1]+'_'+'_'.join(dev[2][1:]))
        if len(node)==1:break
        node=node[1]
    require(len(pins)==len(set(pins)),'repeated target physical pin')
    require((pins[0],pins[-1])==(expected['FromRoutePin'],expected['ToRoutePin']),
            'target physical endpoints differ from actual STA: '+name)
    return pins

def logical_net(tokens,name,expected):
    tree=expression(tokens)
    require(len(tree)==3 and tree[:2]==['NET',name] and tree[2][0]=='CONNECT','unexpected target NET')
    connections=[]
    for item in tree[2][1:]:
        require(len(item)==3 and item[0]=='PORTREF' and len(item[2])==2 and item[2][0]=='INSTREF',
                'unexpected target logical connection')
        connections.append({'Instance':item[2][1].lstrip('\\'),'Pin':port_name(item[1])})
    require(len(connections)==2,'target must have exactly two logical connections')
    expected_load=expected['Endpoint'].rsplit('/',1)
    require({'Instance':expected_load[0],'Pin':expected_load[1]} in connections,
            'STA target missing from actual net connectivity')
    require(sum(v['Pin']=='CR' and v['Instance'].startswith('CLKROUTE_') for v in connections)==1,
            'target lacks one actual CLKROUTE CR source')
    return connections

def targets_from_audit(path):
    report=json.loads(Path(path).read_text(encoding='utf-8'))
    require(report['ExtractionComplete'] is True and report['HoldFailingPathCount']==3,'need actual three-path hold audit')
    targets={}
    for p in report['Paths']:
        target=dict(p['PhysicalRepairCandidate']);target['Endpoint']=p['Endpoint']
        targets[target['Net']]=target
    require(set(targets)=={'_N101','_N188','_N78'},'scope is only the three measured camera nets')
    return targets

def receipt_provenance(dump):
    dump=Path(dump).resolve();receipt=dump.parent/'result.json'
    if not receipt.is_file():
        return {'Verified':False,'Reason':'No adjacent native result.json; dump content only.'}
    value=json.loads(receipt.read_text(encoding='utf-8'))
    require(value.get('ExecutionPassed') is True and not value.get('InputDrift')
            and value.get('ExitCode')==0,'native execution receipt failed/drifted')
    require(value.get('Artifacts',{}).get(dump.name)==sha(dump),'dump differs from native receipt')
    input_adf=dump.parent/'input.adf'
    require(input_adf.is_file() and value.get('ResultADFSHA256')==sha(input_adf),
            'native result ADF differs from receipt')
    return {'Verified':True,'Receipt':str(receipt),'ReceiptSHA256':sha(receipt),
            'InputADF':str(input_adf),'InputADFSHA256':sha(input_adf),
            'OriginalSourceADFSHA256':value.get('SourceADFSHA256'),
            'ExecutionPassed':True,'InputDrift':[],'ArtifactSHA256':sha(dump)}

def inspect(path,targets):
    path=Path(path).resolve();before=sha(path)
    semantic=hashlib.sha256();metadata={'OutputPath':0,'Timestamp':0,'SourceAttribute':0}
    annotations,excluded,target_tokens,logical_tokens={},{},{},{}
    occupied=defaultdict(list);observed_edges=defaultdict(list)
    depth=0;active=None;active_depth=None;active_name=None;active_hash=None;tokens_hold=[]
    logical_capture=None;logical_depth=None;logical_hold=[]
    route_views=0;physical_nodes=0;previous=None;source_metadata=hashlib.sha256();source_counts={'FILEID':0,'LINENUM':0}
    for number,line in enumerate(path.open(encoding='utf-8-sig'),1):
        tokens=TOKEN.findall(line)
        require(not TOKEN.sub('',line).strip(),'unparsed ADIF tokens')
        start=depth;depth+=tokens.count('(')-tokens.count(')')
        require(depth>=0,'unbalanced ADIF')
        if '(VIEWANNOTATE ' in line and ' ROUTING ' in line:route_views+=1
        if logical_capture is None and len(tokens)>=3 and tokens[:2]==['(','NET'] and tokens[2] in targets:
            logical_capture=tokens[2];logical_depth=start;logical_hold=[]
        if logical_capture is not None:
            logical_hold.extend(tokens)
            if depth==logical_depth:
                require(logical_capture not in logical_tokens,'duplicate logical target net')
                logical_tokens[logical_capture]=logical_hold;logical_capture=None
        if active is None:
            if start==1 and tokens[:2] in (['(','CDB'],['(','FILETABLE']):
                active='excluded';active_name=tokens[1];active_depth=start;active_hash=hashlib.sha256()
                require(active_name not in excluded,'duplicate metadata/constraint section')
            elif tokens[:2]==['(','NETANNOTATE']:
                require(tokens[2:4]==['(','NETREF'] and tokens[-1]==')' and depth==start+1,'bad net annotation header')
                active='route';active_name=' '.join(tokens[4:-1]);active_depth=start;active_hash=hashlib.sha256();tokens_hold=[];previous=None
                require(active_name not in annotations,'duplicate net annotation')
            elif number==1:
                require(tokens[:2]==['(','ADIF'] and len(tokens)==3,'ADIF header missing')
                tokens[2]='"<OUTPUT_PATH>"';metadata['OutputPath']+=1
            elif tokens[:2]==['(','TIMESTAMP']:
                require(len(tokens)==4,'timestamp dialect differs');tokens[2]='"<TIMESTAMP>"';metadata['Timestamp']+=1
            elif tokens[:2]==['(','ATTR_FN']:
                require(len(tokens)==4,'source attribute dialect differs');tokens[2]='<SOURCE_PATH>';metadata['SourceAttribute']+=1
            elif tokens[:2] in (['(','FILEID'],['(','LINENUM']):
                require(len(tokens)==4 and tokens[2].isdigit(),'source-location dialect differs')
                source_counts[tokens[1]]+=1;feed(source_metadata,tokens);continue
        if active is not None:
            feed(active_hash,tokens)
            if active=='route':
                if active_name in targets:tokens_hold.extend(tokens)
                if '(PORTREF ' in line:
                    matches=list(NODE.finditer(line));require(len(matches)==1 and line.count('(PORTREF ')==1,'unparsed physical port')
                    match=matches[0];port=match[3] or match[1]+'['+match[2]+']'
                    x,y=int(match[5]),int(match[6]);pin=f'{port}:{match[4]}_{x}_{y}'
                    occupied[pin].append(active_name);physical_nodes+=1
                    indent=len(line)-len(line.lstrip());cur=(port,match[4],x,y,indent,number,pin)
                    if previous and port.startswith('IDNE[') and previous[0]=='Z'+port[1:] and indent==previous[4]+2:
                        observed_edges[(previous[2],previous[3],x,y)].append(
                            {'From':previous[6],'To':pin,'Owner':active_name,'Line':previous[5]})
                    previous=cur
            if depth==active_depth:
                if active=='route':
                    annotations[active_name]=active_hash.hexdigest()
                    if active_name in targets:target_tokens[active_name]=tokens_hold
                else:excluded[active_name]=active_hash.hexdigest()
                active=None
        else:feed(semantic,tokens)
    require(depth==0 and active is None and logical_capture is None,'truncated native dump')
    require(route_views==1 and len(annotations)>1000 and physical_nodes>1000,'incomplete native route inventory')
    require(set(target_tokens)==set(logical_tokens)==set(targets),'target net/route inventory incomplete')
    require(set(excluded)=={'CDB','FILETABLE'} and metadata=={'OutputPath':1,'Timestamp':1,'SourceAttribute':1},'metadata inventory differs')
    routes={n:linear_tree(t,n,targets[n]) for n,t in target_tokens.items()}
    connectivity={n:logical_net(t,n,targets[n]) for n,t in logical_tokens.items()}
    require(sha(path)==before,'native dump changed during audit')
    return {'Path':str(path),'SHA256':before,'RouteCount':len(annotations),'PhysicalNodeCount':physical_nodes,
            'NonRouteSemanticSHA256':semantic.hexdigest(),'NetAnnotations':annotations,'TargetRoutes':routes,
            'TargetConnectivity':connectivity,'ExcludedBlockSHA256':excluded,'NormalizedMetadataCounts':metadata,
            'SourceLocationMetadata':{'Counts':source_counts,'SHA256':source_metadata.hexdigest()},
            '_Occupied':occupied,'_ObservedNE':observed_edges}

def waypoint_inventory(parsed,wire):
    before=sha(wire);lines=Path(wire).read_text().splitlines();rules={}
    for channel in range(4):
        hits=[(i+1,l) for i,l in enumerate(lines) if l.startswith(f'ZDNE[{channel}] :')]
        require(len(hits)==1 and f'[ IDNE[{channel}] ]' in hits[0][1],'official NE wire rule differs')
        rules[channel]={'Line':hits[0][0],'Text':hits[0][1]}
    # Search centres are relative to this build's actual source/load SRBs.
    # Use an observed edge on another channel to prove actual coordinate gaps.
    selected={};occupied=parsed['_Occupied']
    for net,pins in parsed['TargetRoutes'].items():
        sites=[tuple(map(int,re.search(r':SRB_(\d+)_(\d+)$',pin).groups())) for pin in pins if ':SRB_' in pin]
        sx,sy=sites[0];tx,ty=sites[-1]
        centres=[(sx-48,sy-36),(tx-48,ty+24)] if ty-sy>60 else [(sx-6,sy-42)] if ty>=sy else [(sx-12,sy-24)]
        segments=[]
        for cx,cy in centres:
            candidates=[]
            for (x,y,dx,dy),proof in parsed['_ObservedNE'].items():
                for channel in range(4):
                    pair=[f'ZDNE[{channel}]:SRB_{x}_{y}',f'IDNE[{channel}]:SRB_{dx}_{dy}']
                    if not any(pin in occupied for pin in pair):
                        candidates.append({'Pins':pair,'DistanceFromSearchCentre':abs(x-cx)+abs(y-cy),
                                           'OccupiedBy':[],'BothPinsUnused':True,
                                           'CoordinateProof':proof[0],'OfficialWireRule':rules[channel]})
            candidates.sort(key=lambda v:(v['DistanceFromSearchCentre'],v['Pins']))
            require(candidates,'no unused observed-coordinate waypoint')
            segments.append({'SearchCentre':[cx,cy],'Preferred':candidates[0],'Alternatives':candidates[1:4]})
        selected[net]={'PhysicalSource':pins[0],'PhysicalLoad':pins[-1],
                       'OriginalRouteNodes':len(pins),'Segments':segments,
                       'NativeRouteAndSTARequired':True}
    require(sha(wire)==before,'wire pattern changed during audit')
    return {'WirePattern':str(Path(wire).resolve()),'WirePatternSHA256':before,'Candidates':selected}

def public_inventory(value):
    output={k:v for k,v in value.items() if not k.startswith('_') and k!='NetAnnotations'}
    output['AllOtherNetAnnotationsSHA256']=hashlib.sha256(json.dumps(
        {k:v for k,v in value['NetAnnotations'].items() if k not in value['TargetRoutes']},
        sort_keys=True,separators=(',',':')).encode()).hexdigest()
    output['TargetAnnotationSHA256']={n:value['NetAnnotations'][n] for n in value['TargetRoutes']}
    return output

def compare(before,after,targets):
    require(before['NonRouteSemanticSHA256']==after['NonRouteSemanticSHA256'],'non-route semantic tokens changed')
    require(before['ExcludedBlockSHA256']['CDB']==after['ExcludedBlockSHA256']['CDB'],'native constraint block changed')
    require(before['TargetConnectivity']==after['TargetConnectivity'],'target logical connectivity changed')
    require(before['NetAnnotations'].keys()==after['NetAnnotations'].keys(),'net annotation inventory changed')
    changed=sorted(n for n,v in before['NetAnnotations'].items() if after['NetAnnotations'][n]!=v)
    require(set(changed)==set(targets),'unexpected changed routes or incomplete requested repair: '+str(changed))
    return {'ChangedNets':changed,'OnlyRequestedNetsChanged':True,'AllOtherNETANNOTATEIdentical':True,
            'AllNonRouteSemanticTokensIdentical':True,'NativeConstraintBlockIdentical':True,
            'LogicalConnectivityIdentical':True,'SingleDriverSingleLoadTreesVerified':True}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dump',type=Path,required=True)
    parser.add_argument('--hold-audit',type=Path,required=True)
    parser.add_argument('--candidate',type=Path)
    parser.add_argument('--wire',type=Path,default=WIRE_DEFAULT)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();require(not args.output.exists(),'fresh JSON output required')
    targets=targets_from_audit(args.hold_audit);baseline=inspect(args.dump,targets)
    result={'Schema':'camera-vga-native-route-audit-v1','AuditedUTC':datetime.now(timezone.utc).isoformat(),
            'AuditPassed':True,'HoldAuditSHA256':sha(args.hold_audit),'ToolSHA256':sha(__file__),
            'ImportedHoldToolSHA256':sha(Path(__file__).with_name('audit_camera_vga_hold.py')),
            'NativeProvenance':receipt_provenance(args.dump),
            'Baseline':public_inventory(baseline),'HardwareAccessed':False,'EDAExecuted':False,'TimingAccepted':False}
    if args.candidate:
        candidate=inspect(args.candidate,targets)
        result.update(Comparison=compare(baseline,candidate,targets),Candidate=public_inventory(candidate),
                      CandidateNativeProvenance=receipt_provenance(args.candidate))
    else:result['WaypointInventory']=waypoint_inventory(baseline,args.wire)
    result['ExcludedFromSemanticComparison']=['ADIF output pathname','STATUS timestamp','ATTR_FN source pathname',
        'FILEID/LINENUM source location metadata (counts/hash retained)','FILETABLE source path table (hash retained)']
    result['Limitations']='Only native router and full two-corner STA prove waypoint feasibility and delay. Constraint block is compared exactly; no timing exception is authorized.'
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({'AuditPassed':True,'Output':str(args.output.resolve()),'Routes':baseline['RouteCount'],
                      'PhysicalNodes':baseline['PhysicalNodeCount'],'Comparison':result.get('Comparison')}))

if __name__=='__main__':main()
