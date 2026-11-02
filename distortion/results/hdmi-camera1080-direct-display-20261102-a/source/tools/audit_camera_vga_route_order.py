"""Strict camera route comparison with native CDBENTRY sibling ordering normalized.

The native save may reorder consecutive constraint-pin CDBENTRY siblings. Only
that sibling order is normalized; their entire token contents remain exact,
and their enclosing parent/location remains in the semantic token stream.
The frozen route auditor remains unchanged. No constraint is waived.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import audit_camera_vga_routes as native


def ordered_semantics(path):
    path=Path(path).resolve();before=native.sha(path)
    digest=hashlib.sha256();depth=0;active=None;active_depth=None;held=[]
    group=[];group_depth=None;groups=[];raw_cdb=hashlib.sha256()
    metadata={'OutputPath':0,'Timestamp':0,'SourceAttribute':0}
    sections={'CDB':0,'FILETABLE':0,'NETANNOTATE':0};entry_count=0
    def flush_group():
        nonlocal group,group_depth
        if not group:return
        canonical=sorted(group,key=lambda value:tuple(value['Tokens']))
        groups.append({'EnclosingSemanticPrefixSHA256':digest.copy().hexdigest(),
                       'Depth':group_depth,'Entries':group,
                       'OrderChangedByNormalization':[v['Tokens'] for v in canonical]!=[v['Tokens'] for v in group]})
        for item in canonical:native.feed(digest,item['Tokens'])
        group=[];group_depth=None
    for number,line in enumerate(path.open(encoding='utf-8-sig'),1):
        tokens=native.TOKEN.findall(line)
        native.require(not native.TOKEN.sub('',line).strip(),'unparsed native tokens')
        start=depth;depth+=tokens.count('(')-tokens.count(')')
        native.require(depth>=0,'unbalanced native dump')
        if active is None and tokens:
            is_entry=tokens[:2]==['(','CDBENTRY']
            if group and (not is_entry or start!=group_depth):flush_group()
            if is_entry:
                active='CDBENTRY';active_depth=start;held=[];entry_line=number;entry_count+=1
            elif start==1 and tokens[:2] in (['(','CDB'],['(','FILETABLE']):
                active=tokens[1];active_depth=start;sections[active]+=1
            elif tokens[:2]==['(','NETANNOTATE']:
                active='NETANNOTATE';active_depth=start;sections[active]+=1
            elif number==1:
                native.require(tokens[:2]==['(','ADIF'] and len(tokens)==3,'ADIF header missing')
                tokens[2]='"<OUTPUT_PATH>"';metadata['OutputPath']+=1
            elif tokens[:2]==['(','TIMESTAMP']:
                native.require(len(tokens)==4,'timestamp dialect differs');tokens[2]='"<TIMESTAMP>"';metadata['Timestamp']+=1
            elif tokens[:2]==['(','ATTR_FN']:
                native.require(len(tokens)==4,'source attribute dialect differs');tokens[2]='<SOURCE_PATH>';metadata['SourceAttribute']+=1
            elif tokens[:2] in (['(','FILEID'],['(','LINENUM']):
                native.require(len(tokens)==4 and tokens[2].isdigit(),'source-location dialect differs');continue
        if active is not None:
            if active=='CDBENTRY':held.extend(tokens)
            if active=='CDB':raw_cdb.update(line.encode('utf-8'))
            if depth==active_depth:
                if active=='CDBENTRY':
                    if not group:group_depth=active_depth
                    native.require(group_depth==active_depth,'constraint group crosses parent depth')
                    group.append({'Tokens':held,'ReportLine':entry_line,
                                  'SHA256':hashlib.sha256(('\0'.join(held)+'\0').encode()).hexdigest()})
                active=None
        else:native.feed(digest,tokens)
    flush_group()
    native.require(depth==0 and active is None,'truncated native dump')
    native.require(sections['CDB']==sections['FILETABLE']==1 and sections['NETANNOTATE']>1000,'incomplete native scope')
    native.require(metadata=={'OutputPath':1,'Timestamp':1,'SourceAttribute':1},'metadata inventory differs')
    native.require(native.sha(path)==before,'native dump changed during audit')
    return {'Path':str(path),'SHA256':before,'OrderedNonRouteSemanticSHA256':digest.hexdigest(),
            'CDBRawTextSHA256':raw_cdb.hexdigest(),'CDBENTRYCount':entry_count,
            'SiblingGroups':groups,'SectionCounts':sections,'MetadataCounts':metadata}


def validate(before,after,bordered,aordered,targets):
    native.require(bordered['OrderedNonRouteSemanticSHA256']==aordered['OrderedNonRouteSemanticSHA256'],
                   'non-route semantics differ beyond CDBENTRY sibling order')
    native.require(before['ExcludedBlockSHA256']['CDB']==after['ExcludedBlockSHA256']['CDB'],
                   'native constraint block tokens changed')
    native.require(bordered['CDBRawTextSHA256']==aordered['CDBRawTextSHA256'],'raw CDB text changed')
    native.require(before['TargetConnectivity']==after['TargetConnectivity'],'target logical connectivity changed')
    native.require(before['NetAnnotations'].keys()==after['NetAnnotations'].keys(),'net inventory changed')
    changed=sorted(n for n,v in before['NetAnnotations'].items() if after['NetAnnotations'][n]!=v)
    native.require(set(changed)==set(targets),'changed route scope differs: '+str(changed))
    return {'ChangedNets':changed,'AllOtherNETANNOTATEIdentical':True,
            'AllNonRouteSemanticsIdenticalAfterSiblingOrderNormalization':True,
            'CDBExactTokensIdentical':True,'CDBRawTextIdentical':True,
            'TargetLogicalConnectivityIdentical':True,'TargetSingleDriverSingleLoadVerified':True,
            'TimingAccepted':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--hold-audit',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();native.require(not args.output.exists(),'fresh output required')
    targets=native.targets_from_audit(args.hold_audit)
    before=native.inspect(args.baseline,targets);after=native.inspect(args.candidate,targets)
    border=ordered_semantics(args.baseline);aorder=ordered_semantics(args.candidate)
    comparison=validate(before,after,border,aorder,targets)
    bp=native.receipt_provenance(args.baseline);ap=native.receipt_provenance(args.candidate)
    native.require(bp['Verified'] and ap['Verified'],'native provenance required')
    result={'Schema':'camera-vga-route-order-comparison-v1','AuditPassed':True,
            'AuditedUTC':datetime.now(timezone.utc).isoformat(),'Comparison':comparison,
            'Baseline':native.public_inventory(before),'Candidate':native.public_inventory(after),
            'BaselineOrderedSemantics':border,'CandidateOrderedSemantics':aorder,
            'BaselineProvenance':bp,'CandidateProvenance':ap,
            'ToolSHA256':native.sha(__file__),'FrozenRouteToolSHA256':native.sha(native.__file__),
            'HoldAuditSHA256':native.sha(args.hold_audit),'HardwareAccessed':False,'EDAExecuted':False,
            'Normalization':'Only consecutive CDBENTRY siblings at the same parent are sorted by their complete token sequence; all parent/context tokens and entry contents remain exact. Original groups recorded.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({'AuditPassed':True,'Output':str(args.output.resolve()),'Comparison':comparison}))

if __name__=='__main__':main()
