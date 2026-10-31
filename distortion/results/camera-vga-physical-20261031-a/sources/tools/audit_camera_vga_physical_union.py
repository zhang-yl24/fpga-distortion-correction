"""Run the frozen camera physical audit with a separately proved exception union.

The original summary, exact false-path scope, data-check, functional graph and
17,417 FF-location checks all run unchanged. Only the old top-N exception hash
comparison is replaced by a current, fully hash-bound strict union proof.
"""
import argparse
import json
from pathlib import Path

import audit_camera_vga_physical as physical
import audit_camera_vga_exception_union as union

require=physical.require
sha=physical.sha


def load_proof(path,args):
    path=Path(path).resolve();proof=json.loads(path.read_text())
    require(proof.get('Schema')=='camera-vga-exception-union-comparison-v1' and
            proof.get('AuditPassed') is True and proof.get('MembershipCompletedFromBothUnions') is True,
            'successful strict exception union proof required')
    require(set(proof['RouteChain']['OnlyChangedNets'])==union.NETS and proof['RouteChain']['Verified'],
            'route scope proof differs')
    require(Path(proof['BaselineExceptions']).resolve()==Path(args.baseline_exceptions).resolve() and
            Path(proof['CandidateExceptions']).resolve()==Path(args.candidate_exceptions).resolve(),
            'union proof reports differ from physical audit')
    for key in ('InputSHA256','ToolSHA256'):
        require(proof[key],'empty union proof bindings')
        for name,h in proof[key].items():require(sha(name)==h,'union proof input/tool drift: '+name)
    require(proof['ToolSHA256'].get(str(Path(union.__file__).resolve()))==sha(union.__file__),
            'proof not produced by current union audit')
    require(sha(args.candidate_adf)==proof['RouteChain']['CandidateADFSHA256'],
            'candidate ADF differs from union route proof')
    return proof,{str(path):sha(path),**proof['InputSHA256'],**proof['ToolSHA256']}


def audit(args,proof_path):
    proof,watched=load_proof(proof_path,args)
    expected={Path(args.baseline_exceptions).resolve(),Path(args.candidate_exceptions).resolve()}
    called=[]
    token={'Method':'ExactTwoSidedUnionWithVerifiedRouteScope','Proof':str(Path(proof_path).resolve()),
           'ProofSHA256':sha(proof_path),'Sections':proof['Sections'],
           'ChangedIdentityCount':proof['ChangedIdentityCount'],
           'ComparedUnionPathCount':proof['ComparedUnionPathCount'],
           'PrintedRoundingPathCount':proof['PrintedRoundingPathCount']}
    original=physical.exceptions
    def verified_exceptions(path,targets):
        resolved=Path(path).resolve()
        require(resolved in expected and resolved not in called,'unexpected exception audit invocation')
        require(sha(resolved)==proof['InputSHA256'][str(resolved)],'exception report drift')
        called.append(resolved)
        return token
    try:
        physical.exceptions=verified_exceptions
        result=physical.audit(args)
    finally:physical.exceptions=original
    require(set(called)==expected and len(called)==2,'frozen audit did not compare both exception reports')
    require(all(sha(p)==h for p,h in watched.items()),'union proof evidence drift during full audit')
    result['Schema']='camera-vga-physical-union-comparison-v1'
    result['ExceptionUnionComparison']=token
    result['ExceptionUnionProof']=proof
    result['InputSHA256'].update(watched)
    result['ToolSHA256'][str(Path(__file__).resolve())]=sha(__file__)
    result['ToolSHA256'][str(Path(union.__file__).resolve())]=sha(union.__file__)
    return result


def physical_parser():
    p=argparse.ArgumentParser(add_help=False)
    for name in ('baseline-report','candidate-report','baseline-exceptions','candidate-exceptions',
                 'baseline-netlist','candidate-netlist','hold-analysis','candidate-adf','snapshot','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--reset-inventory',type=Path)
    p.add_argument('--baseline-target-report',type=Path,action='append',default=[])
    p.add_argument('--candidate-target-report',type=Path,action='append',default=[])
    return p


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--arguments-json',type=Path,required=True)
    p.add_argument('--exception-proof',type=Path,required=True)
    outer=p.parse_args();argv=json.loads(outer.arguments_json.read_text())
    require(isinstance(argv,list) and all(isinstance(v,str) for v in argv),'physical arguments must be a string list')
    args=physical_parser().parse_args(argv)
    require(not args.output.exists(),'fresh physical audit output required')
    before=sha(outer.arguments_json);result=audit(args,outer.exception_proof)
    require(sha(outer.arguments_json)==before,'physical arguments changed during audit')
    result['InputSHA256'][str(outer.arguments_json.resolve())]=before
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:result[k] for k in ('AuditPassed','AllInternalChecksMet','CornerSummaries','FunctionalComparison')}))


if __name__=='__main__':main()
