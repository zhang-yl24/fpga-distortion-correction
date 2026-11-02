"""Compare hold-repaired and reset-scoped camera native dumps.

All routes, placements and functional semantics must match. Only the native
CDB and CDBENTRY constraint records may differ; this tool records that delta
and does not approve its timing/reset scope. Independent full STA and exact
exception verification are required. The frozen route auditor is not modified.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import audit_camera_vga_routes as native


def constraint_separated(path):
    path=Path(path).resolve();before=native.sha(path)
    digest=hashlib.sha256();depth=0;active=None;active_depth=None;held=[]
    entries=[];metadata={'OutputPath':0,'Timestamp':0,'SourceAttribute':0}
    excluded=Counter();source_locations=hashlib.sha256();source_counts=Counter()
    for number,line in enumerate(path.open(encoding='utf-8-sig'),1):
        tokens=native.TOKEN.findall(line)
        native.require(not native.TOKEN.sub('',line).strip(),'unparsed ADIF tokens')
        start=depth;depth+=tokens.count('(')-tokens.count(')')
        native.require(depth>=0,'unbalanced ADIF')
        if active is None:
            if start==1 and tokens[:2] in (['(','CDB'],['(','FILETABLE']):
                active=tokens[1];active_depth=start;excluded[active]+=1
            elif tokens[:2] in (['(','NETANNOTATE'],['(','CDBENTRY']):
                active=tokens[1];active_depth=start;excluded[active]+=1;held=[]
            elif number==1:
                native.require(tokens[:2]==['(','ADIF'] and len(tokens)==3,'ADIF header missing')
                tokens[2]='"<OUTPUT_PATH>"';metadata['OutputPath']+=1
            elif tokens[:2]==['(','TIMESTAMP']:
                native.require(len(tokens)==4,'timestamp dialect differs')
                tokens[2]='"<TIMESTAMP>"';metadata['Timestamp']+=1
            elif tokens[:2]==['(','ATTR_FN']:
                native.require(len(tokens)==4,'source-path dialect differs')
                tokens[2]='<SOURCE_PATH>';metadata['SourceAttribute']+=1
            elif tokens[:2] in (['(','FILEID'],['(','LINENUM']):
                native.require(len(tokens)==4 and tokens[2].isdigit(),'source-location dialect differs')
                source_counts[tokens[1]]+=1;native.feed(source_locations,tokens);continue
        if active is not None:
            if active=='CDBENTRY':held.extend(tokens)
            if depth==active_depth:
                if active=='CDBENTRY':
                    entries.append({'Tokens':held,'SHA256':hashlib.sha256(('\0'.join(held)+'\0').encode()).hexdigest()})
                active=None
        else:native.feed(digest,tokens)
    native.require(depth==0 and active is None,'truncated native dump')
    native.require(excluded['CDB']==excluded['FILETABLE']==1 and excluded['NETANNOTATE']>1000,
                   'missing native scope sections')
    native.require(metadata=={'OutputPath':1,'Timestamp':1,'SourceAttribute':1},'metadata inventory differs')
    native.require(native.sha(path)==before,'native dump changed during comparison')
    return {'Path':str(path),'SHA256':before,'NonConstraintNonRouteSHA256':digest.hexdigest(),
            'ConstraintPinReferences':entries,'ExcludedSectionCounts':dict(excluded),
            'NormalizedMetadataCounts':metadata,
            'SourceLocations':{'Counts':dict(source_counts),'SHA256':source_locations.hexdigest()}}


def verify(before,after,before_separated,after_separated):
    native.require(before['NetAnnotations']==after['NetAnnotations'],'route inventory or annotation changed')
    native.require(before['TargetRoutes']==after['TargetRoutes'],'actual target tree changed')
    native.require(before['TargetConnectivity']==after['TargetConnectivity'],'target logical connectivity changed')
    native.require(before_separated['NonConstraintNonRouteSHA256']==after_separated['NonConstraintNonRouteSHA256'],
                   'functional/placement/non-constraint semantic tokens changed')
    old=Counter(v['SHA256'] for v in before_separated['ConstraintPinReferences'])
    new=Counter(v['SHA256'] for v in after_separated['ConstraintPinReferences'])
    return {'AllNETANNOTATEIdentical':True,'AllTargetTreesIdentical':True,
            'AllNonConstraintNonRouteSemanticTokensIdentical':True,
            'CDBChanged':before['ExcludedBlockSHA256']['CDB']!=after['ExcludedBlockSHA256']['CDB'],
            'ConstraintPinReferenceAdded':dict(new-old),'ConstraintPinReferenceRemoved':dict(old-new),
            'ConstraintScopeAccepted':False,'TimingAccepted':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline',type=Path,required=True)
    parser.add_argument('--candidate',type=Path,required=True)
    parser.add_argument('--hold-audit',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();native.require(not args.output.exists(),'fresh output required')
    targets=native.targets_from_audit(args.hold_audit)
    baseline=native.inspect(args.baseline,targets);candidate=native.inspect(args.candidate,targets)
    bscope=constraint_separated(args.baseline);cscope=constraint_separated(args.candidate)
    comparison=verify(baseline,candidate,bscope,cscope)
    bprovenance=native.receipt_provenance(args.baseline);cprovenance=native.receipt_provenance(args.candidate)
    native.require(bprovenance['Verified'] and cprovenance['Verified'],'native execution provenance required')
    result={'Schema':'camera-vga-route-reset-scope-v1','AuditPassed':True,
            'AuditedUTC':datetime.now(timezone.utc).isoformat(),'Comparison':comparison,
            'Baseline':native.public_inventory(baseline),'Candidate':native.public_inventory(candidate),
            'BaselineConstraintSeparated':bscope,'CandidateConstraintSeparated':cscope,
            'BaselineProvenance':bprovenance,'CandidateProvenance':cprovenance,
            'InputToolSHA256':{str(Path(__file__).resolve()):native.sha(__file__),
                str(Path(native.__file__).resolve()):native.sha(native.__file__)},
            'HoldAuditSHA256':native.sha(args.hold_audit),'HardwareAccessed':False,'EDAExecuted':False,
            'Limits':'Constraint CDB and CDBENTRY differences are recorded, not approved. Full exact STA/exception audit must independently approve the reset scope.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({'AuditPassed':True,'Output':str(args.output.resolve()),
                      'AllRoutesIdentical':True,'ConstraintScopeAccepted':False}))

if __name__=='__main__':main()
