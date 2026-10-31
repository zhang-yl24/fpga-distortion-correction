"""Bound upright offline bit generation to explicit current-candidate evidence.

prepare/validate/verify are CPU-only. Explicit execute runs a fresh native STA,
then a CPU gate, then bit generation from the same copied ADF. No programming,
UART, physical routing edits, inherited candidate authority or board access.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import run_camera_vga_upright_inspect as inspect
import audit_camera_vga_upright_io_cdc as interfaces
import audit_camera_vga_physical as timing

prep=inspect.prep
require,sha=prep.require,prep.sha
SELF=Path(__file__).resolve()
PYTHON=prep.PROJECT.parent/'.venv/Scripts/python.exe'
REQUEST_SCHEMA='camera-vga-upright-bitstream-request-v1'
PLAN_SCHEMA='camera-vga-upright-bitstream-plan-v1'
EXEC_SCHEMA='camera-vga-upright-bitstream-execution-v1'
STAGES=['Report Timing','Generate Bitstream']
COMPLETE='CAMERA_VGA_UPRIGHT_BITSTREAM_COMPLETE'
REPORT='report_timing/'+prep.TARGET+'.rtr'
EXCEPTIONS='report_timing/'+prep.TARGET+'_exception.rtr'
BIT='generate_bitstream/'+prep.TARGET+'.sbit'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def add(watched,path,digest=None,pds=None):
    p=Path(path).absolute()
    require(p==p.resolve() and p.is_file() and (p.is_relative_to(prep.PROJECT.parent) or p==pds),'evidence path outside repository/PDS')
    actual=sha(p);require(digest is None or digest==actual,'evidence hash mismatch: '+str(p))
    require(p not in watched or watched[p]==actual,'conflicting evidence identity')
    watched[p]=actual;return p


def ref(value,watched,pds=None):
    require(isinstance(value,dict) and set(value)=={'Path','SHA256'} and isinstance(value['SHA256'],str)
            and re.fullmatch('[0-9a-f]{64}',value['SHA256']),'exact Path/SHA256 binding required')
    return add(watched,value['Path'],value['SHA256'],pds)


def evidence(value,watched,pds):
    for key in ('InputSHA256','ToolSHA256'):
        require(isinstance(value.get(key),dict) and value[key],'evidence hash inventory missing: '+key)
        for path,h in value[key].items():
            if key=='ToolSHA256':require(value['InputSHA256'].get(path)==h,'evidence tool not input-bound')
            add(watched,path,h,pds)


def passed_tables(report):
    tables,clocks=timing.summaries(report)
    require(set(tables)=={(c,k) for c in ('slow','fast') for k in ('setup','hold','recovery','removal','mpw')}
            and all(tables.values()) and clocks,'all ten upright timing tables and clocks required')
    require(all(row['FailingChecks']==0 and row['WorstSlackNS']>=0 and row['TotalNegativeSlackNS']==0
                for rows in tables.values() for row in rows.values()),'all ten upright timing tables must pass')
    return tables,clocks


def false_paths(path):
    with Path(path).open(encoding='gb18030') as f:return timing.native.parse_false_paths(f)


def final_export(path,candidate_sha,build_sha,watched):
    value=read(path)
    if value.get('Schema')=='camera-vga-upright-derived-inspection-v1':
        import run_camera_vga_upright_derived_inspect as derived
        value=derived.bind_receipt(path,watched)
        require(value.get('Target')==prep.TARGET and value.get('Mode')=='export'
                and value.get('SourceADFSHA256')==candidate_sha and value.get('BuildPlanSHA256')==build_sha,
                'derived final export identity differs')
        add(watched,Path(derived.__file__).resolve())
        return value
    return interfaces.receipt(path,'export',candidate_sha,build_sha,watched)[1]


def authority(request_path):
    watched={};request_path=add(watched,request_path);r=read(request_path)
    fields={'Schema','Target','BuildPlan','CandidateADF','FinalInspectionReceipt','FinalIOCDCProof','ResetApplicationReceipt','ResetEffectAudit'}
    require(set(r)==fields and r['Schema']==REQUEST_SCHEMA and r['Target']==prep.TARGET,'exact upright bit request schema/fields required')
    plan_path=ref(r['BuildPlan'],watched);plan=read(plan_path)
    pds=Path(plan['PDS']['Executable']);base=plan_path.parent
    original=base/'place_route'/(prep.TARGET+'_pnr.adf')
    plan,build_inputs=inspect.bind(plan_path,original,sha(original));watched.update(build_inputs)
    candidate=ref(r['CandidateADF'],watched);candidate_sha=sha(candidate)
    er=ref(r['FinalInspectionReceipt'],watched)
    export=final_export(er,candidate_sha,sha(plan_path),watched)
    require(sha(candidate)==sha(er.parent/'input.adf'),'final export clone differs from requested candidate')
    report=interfaces.artifact(er,export,prep.TARGET+'.rtr')
    exceptions=interfaces.artifact(er,export,prep.TARGET+'_exception.rtr')
    netlist=interfaces.artifact(er,export,prep.TARGET+'_sim.v')
    require(export.get('NativeNetlistWithFFloc') is True and export['Netlist']['SHA256']==sha(netlist),'final upright netlist missing/binding differs')
    passed_tables(report)
    false=false_paths(exceptions)
    require(all(not rows for (corner,kind),rows in false.items() if kind in ('setup','hold')),'data setup/hold false paths forbidden')
    if candidate_sha==sha(original):
        require(r['ResetApplicationReceipt'] is None and r['ResetEffectAudit'] is None,'original candidate cannot claim a reset derivative')
        require(all(not rows for rows in false.values()),'original candidate has unexplained false paths')
    else:
        import run_camera_vga_upright_physical as physical
        application_path=ref(r['ResetApplicationReceipt'],watched);application=read(application_path)
        routed=application.get('Schema')=='camera-vga-upright-route-reset-application-v1'
        require((application.get('Schema')==physical.SCHEMA or routed) and application.get('Target')==prep.TARGET
                and application.get('ExecutionPassed') is True and physical.execution_ok(application)
                and application.get('BuildPlanSHA256')==sha(plan_path)
                and application.get('SourceADFSHA256')==sha(original)
                and application.get('ResultADFSHA256')==candidate_sha,'clean exact reset derivative receipt required')
        if routed:
            import run_camera_vga_upright_route_reset as route_reset
            application=route_reset.bind_completed(application_path,watched)
            add(watched,Path(route_reset.__file__).resolve())
        proof_binding=application['ResetProof']
        require(isinstance(proof_binding,dict),'final bit requires independently proved recovery scope')
        _,source,proof,fdc,commands,proof_inputs=physical.bind_proof(plan_path,proof_binding['Path'],proof_binding['SHA256'])
        watched.update(proof_inputs)
        if routed:
            expected,script,_=route_reset.recipe(application['Request']['Path'],application_path.parent,application['MaximumSeconds'])
        else:
            expected,script,_=physical.recipe(plan_path,proof_binding['Path'],proof_binding['SHA256'],application_path.parent,application['MaximumSeconds'])
        stage_path=application_path.parent/'stage-plan.json';stage=read(add(watched,stage_path,application['StagePlanSHA256']))
        require({k:v for k,v in stage.items() if k!='PreparedUTC'}==expected and all(application.get(k)==v for k,v in expected.items()),
                'reset application recipe/receipt changed')
        require((application_path.parent/'stage.tcl').read_bytes()==script.encode('ascii'),'reset application Tcl differs')
        for p,h in application['InputSHA256'].items():add(watched,p,h,pds)
        for p,h in application['Artifacts'].items():
            child=inspect.canonical(application_path.parent/p,application_path.parent);add(watched,child,h,pds)
        add(watched,application_path.parent/'input.adf',candidate_sha)
        inventory=read(Path(proof_binding['Path']).parent/'current-recovery-inventory.json')
        expected_false={c:{tuple(v[k] for k in (*timing.KEYS,'LaunchEdge','CaptureEdge'))
            for check in inventory['Corners'][c]['Checks'] for v in check['NativeVariants']} for c in ('slow','fast')}
        timing.native.validate_exception_sets(false,expected_false)
        before=interfaces.functional(Path(proof['CurrentNetlist']['Path']).read_text(encoding='utf-8-sig'))
        after=interfaces.functional(netlist.read_text(encoding='utf-8-sig'))
        require(before==after,'reset derivative changed actual functional graph/FF placement')
        effect_path=ref(r['ResetEffectAudit'],watched);effect=read(effect_path)
        require(effect.get('Schema')=='camera-vga-upright-reset-effect-audit-v1' and effect.get('Target')==prep.TARGET
                and all(effect.get(k) is True for k in ('AuditPassed','ResetEffectVerified','FunctionalGraphIdentical',
                    'AllFFPlacementsIdentical','ExactResetExceptionUnionVerified')),
                'separate exact reset effect/route audit required')
        if routed:
            require(effect.get('RoutingUnchanged') is False and effect.get('OnlyRequestedRoutingChanges') is True
                    and effect.get('ChangedNets')==[application['Route']['Net']], 'single actual route effect proof required')
            import audit_camera_vga_route_reset_scope as route_scope
            request=read(application['Request']['Path'])
            base_dump=ref(request['RouteDump'],watched,pds)
            final_dump=application_path.parent/'route-dump.txt'
            add(watched,final_dump,application['Artifacts']['route-dump.txt'],pds)
            targets={application['Route']['Net']:application['MeasuredTarget']}
            old_route=route_reset.routes.inspect(base_dump,targets);new_route=route_reset.routes.inspect(final_dump,targets)
            require(set(old_route['NetAnnotations'])==set(new_route['NetAnnotations']), 'route inventory differs')
            changed=sorted(n for n,h in old_route['NetAnnotations'].items() if new_route['NetAnnotations'][n]!=h)
            require(changed==[application['Route']['Net']] and old_route['TargetConnectivity']==new_route['TargetConnectivity'],
                    'unexpected changed route or logical connectivity')
            before_scope=route_scope.constraint_separated(base_dump);after_scope=route_scope.constraint_separated(final_dump)
            require(before_scope['NonConstraintNonRouteSHA256']==after_scope['NonConstraintNonRouteSHA256'],
                    'nonconstraint logic/placement semantics changed')
            add(watched,Path(route_scope.__file__).resolve());add(watched,Path(route_reset.routes.__file__).resolve())
        else:
            require(effect.get('RoutingUnchanged') is True,'reset-only candidate changed routing')
        ref(effect['SourceADF'],watched,pds);ref(effect['ResultADF'],watched,pds)
        require(effect['SourceADF']['SHA256']==sha(original) and effect['ResultADF']['SHA256']==candidate_sha,
                'reset effect ADF identities differ')
        evidence(effect,watched,pds)
        require(effect['InputSHA256'].get(str(candidate))==candidate_sha,'reset effect does not bind requested final ADF')
        add(watched,Path(physical.__file__).resolve())
    proof_path=ref(r['FinalIOCDCProof'],watched);proof=read(proof_path)
    require(proof.get('Schema')=='camera-vga-upright-io-cdc-native-v1' and proof.get('Target')==prep.TARGET
            and proof.get('StructuralAuditPassed') is True and proof.get('NativeAuditPassed') is True
            and proof.get('CandidateADF',{}).get('SHA256')==candidate_sha,'complete current upright IO/CDC proof required')
    for key in ('NativeInterstageTimingComplete','GrayDatapathBoundComplete'):
        require(proof.get('Scope',{}).get(key) is True,'upright IO/CDC proof incomplete: '+key)
    for key in ('FinalNativeSiteMappingPassed','FinalFunctionalPadSiteMappingPassed'):
        require(proof.get('Pins',{}).get(key) is True,'upright final IO site proof missing: '+key)
    ref(proof['CandidateADF'],watched,pds)
    top=(prep.PROJECT/prep.TOP).read_text()
    normalized,count=re.subn(r'module\s+'+prep.TARGET+r'\s*#\(.*?\)\s*\(', 'module board1080_top(',top,count=1,flags=re.S)
    require(count==1 and proof['Pins']['TopPortCount']==len(interfaces.io.pin_parser.top_ports(normalized)),
            'upright actual port inventory differs')
    evidence(proof,watched,pds)
    require(proof['InputSHA256'].get(str(netlist))==sha(netlist),'IO/CDC proof does not bind actual final export')
    for p in (SELF,PYTHON,Path(inspect.__file__).resolve(),Path(interfaces.__file__).resolve(),
              Path(timing.__file__).resolve(),Path(timing.native.__file__).resolve(),Path(timing.hold.__file__).resolve()):
        add(watched,p)
    require(not inspect.drift(watched),'upright bit authority drift')
    return {'Request':r,'RequestPath':request_path,'Build':plan,'PlanPath':plan_path,'Candidate':candidate,
            'CandidateSHA256':candidate_sha,'FinalReport':report,'FinalExceptions':exceptions,'Watched':watched}


def render(context,work):
    base=context['PlanPath'].parent
    rendered=inspect.render('export',(base/'timing.tcl').read_text(encoding='ascii'),base,work)
    boundary='report_timing -force_to_run -input_db_file '
    require(rendered.count(boundary)==1,'one fresh native report context required')
    prefix=rendered[:rendered.index(boundary)];w=work.as_posix();marker='CAMERA_VGA_UPRIGHT_GATE_PASS '+context['CandidateSHA256']
    return (prefix+boundary+'{'+w+'/audited-final.adf} -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n'
        'if {[info script] ne {}} {\n    set checked [exec {'+PYTHON.as_posix()+'} -B {'+SELF.as_posix()+'} --gate {'+w+'}]\n'
        '    puts $checked\n    if {[string first {'+marker+'} $checked] < 0} {error {Missing upright pre-bit gate}}\n'
        '    gen_bit_stream -force_to_run -input_db_file {'+w+'/audited-final.adf} -scbv {High Voltage} -unused_io_status UNUSED\n'
        '    puts {'+COMPLETE+'}\n    flush stdout\n}\n')


def recipe(request_path,work,maximum=900):
    work=prep.work_path(work);require(work.name.startswith('bit-'),'upright bit-* stage required')
    require(type(maximum) is int and 60<=maximum<=900,'bit deadline must be60..900 seconds')
    c=authority(request_path);tcl=render(c,work)
    plan={'Schema':PLAN_SCHEMA,'Target':prep.TARGET,'Request':{'Path':str(c['RequestPath']),'SHA256':sha(c['RequestPath'])},
        'WorkDirectory':str(work),'CandidateADFSHA256':c['CandidateSHA256'],'MaximumSeconds':maximum,
        'InputSHA256':{str(p):h for p,h in c['Watched'].items()},'ExpectedActualStages':STAGES,
        'TclSHA256':prep.baseline.paths.sha_bytes(tcl.encode('ascii')),
        'Command':[c['Build']['PDS']['Executable'],'-file',(work/'bitstream.tcl').as_posix(),'-work_dir',work.as_posix(),'-project_name',prep.TARGET],
        'HardwareAccessed':False,'HardwareReleaseAllowed':False,'ExternalACTimingAccepted':False,'DiagnosticOnly':True,
        'BitstreamRequested':True,'EDAExecutedByPreparer':False}
    return plan,tcl,c


def prepare(request_path,work,maximum=900):
    plan,tcl,c=recipe(request_path,work,maximum);work=Path(plan['WorkDirectory'])
    require(not work.exists(),'fresh bit stage required');work.mkdir()
    shutil.copyfile(c['Candidate'],work/'audited-final.adf');shutil.copyfile(SELF,work/'tool-snapshot.py')
    (work/'bitstream.tcl').write_text(tcl,encoding='ascii',newline='\n')
    plan['PreparedUTC']=prep.utc();inspect.diagnostic.write(work/'bitstream-plan.json',plan)
    validate(work);return plan


def validate(work):
    work=prep.work_path(work);plan=read(work/'bitstream-plan.json')
    expected,tcl,c=recipe(plan['Request']['Path'],work,plan['MaximumSeconds'])
    require(set(plan)==set(expected)|{'PreparedUTC'} and {k:v for k,v in plan.items() if k!='PreparedUTC'}==expected,'upright bit plan recipe drift')
    require((work/'bitstream.tcl').read_bytes()==tcl.encode('ascii') and sha(work/'audited-final.adf')==c['CandidateSHA256']
            and sha(work/'tool-snapshot.py')==sha(SELF),'upright bit prepared artifact drift')
    return plan,c


def compare_native(c,report,exceptions):
    require(passed_tables(report)==passed_tables(c['FinalReport']),'fresh timing summary/clock identities differ')
    normalize=lambda d:{k:Counter(json.dumps(r,sort_keys=True) for r in v) for k,v in d.items()}
    require(normalize(false_paths(exceptions))==normalize(false_paths(c['FinalExceptions'])),'fresh false-path identities differ')
    require(timing.exceptions(exceptions,set())==timing.exceptions(c['FinalExceptions'],set()),'fresh non-false exception paths differ')
    return {'AllTenTimingTablesPassed':True,'ClockAndSummaryIdentityPreserved':True,'AllExceptionPathsPreserved':True}


def gate(work):
    plan,c=validate(work);work=Path(work);checks=compare_native(c,work/REPORT,work/EXCEPTIONS);validate(work)
    result={'Schema':'camera-vga-upright-pre-bit-gate-v1','GatePassed':True,'Target':prep.TARGET,
        'CandidateADFSHA256':c['CandidateSHA256'],'CheckedUTC':prep.utc(),**checks,
        'EvidenceSHA256':{n:sha(work/n) for n in ('bitstream-plan.json','audited-final.adf','bitstream.tcl',REPORT,EXCEPTIONS)}}
    inspect.diagnostic.write(work/'pre-bit-audit.json',result);return result


def events(text,digest):
    result=[];marker='CAMERA_VGA_UPRIGHT_GATE_PASS '+digest
    for line in text.splitlines():
        line=line.strip();m=re.fullmatch(r'Process "([^"]+)" (started|done)\.',line)
        if m:result.append(m.groups())
        elif line.startswith('CAMERA_VGA_UPRIGHT_GATE_PASS'):
            require(line==marker,'wrong upright gate marker');result.append(('Runtime gate','passed'))
        elif line==COMPLETE:result.append(('Bitstream','complete'))
    expected=[('Report Timing','started'),('Report Timing','done'),('Runtime gate','passed'),
              ('Generate Bitstream','started'),('Generate Bitstream','done'),('Bitstream','complete')]
    require(result==expected,'fresh STA, CPU gate, bit generation order differs');return result


def bit_header(data):
    prefix=bytes.fromhex('00090ff00ff00ff00ff000')+b'PANGO MICROSYSTEMS, INC.\0\1'
    require(data.startswith(prefix),'invalid native bit prefix');offset=len(prefix);values={}
    for tag,name in zip(b'abcdef',('Design','Device','Date','Time','Generator','Version')):
        require(offset+3<=len(data) and data[offset]==tag,'missing bit header field')
        size=int.from_bytes(data[offset+1:offset+3],'big');raw=data[offset+3:offset+3+size]
        require(size>0 and len(raw)==size and raw[-1:]==b'\0' and b'\0' not in raw[:-1],'invalid bit header text')
        values[name]=raw[:-1].decode('ascii');offset+=3+size
    require(data[offset:offset+3]==b'ghi' and len(data)>1000000,'truncated native programming payload')
    for k,v in {'Design':prep.TARGET,'Device':'Logos2-PG2L100H--6-FBG676','Generator':'Fabric Compiler','Version':'2023.2-SP3<154097>'}.items():
        require(values[k]==v,'upright bit identity differs: '+k)
    return values


def verify(work):
    plan,c=validate(work);work=Path(work);receipt=read(work/'execution-result.json')
    require(receipt.get('Schema')==EXEC_SCHEMA and receipt.get('ExitCode')==0 and receipt.get('InputDrift')==[]
            and receipt.get('Diagnostics')==[] and not receipt.get('Error') and receipt.get('TimedOut') is False
            and receipt.get('StoppedForUnexpectedStage') is False and receipt.get('Command')==plan['Command']
            and receipt.get('CandidateADFSHA256')==c['CandidateSHA256'] and receipt.get('Cleanup',{}).get('Complete') is True,'unclean upright bit execution')
    for n,h in receipt['Artifacts'].items():require(sha(inspect.canonical(work/n,work))==h,'native bit artifact drift')
    text=(work/'stdout.log').read_text(encoding='gb18030');actual=events(text,c['CandidateSHA256'])
    checks=compare_native(c,work/REPORT,work/EXCEPTIONS);proof=read(work/'pre-bit-audit.json')
    require(proof.get('GatePassed') is True and proof.get('CandidateADFSHA256')==c['CandidateSHA256']
            and all(proof.get(k)==v for k,v in checks.items()),'pre-bit runtime gate differs')
    require(proof['EvidenceSHA256']=={n:sha(work/n) for n in ('bitstream-plan.json','audited-final.adf','bitstream.tcl',REPORT,EXCEPTIONS)},'pre-bit evidence drift')
    commands=[s for s in re.findall(r'(?m)^Executing : (gen_bit_stream .+)$',text) if not s.endswith(' successfully.')]
    require(len(commands)==1 and '-input_db_file '+(work/'audited-final.adf').as_posix() in commands[0],'bit generation input differs')
    bgr=work/'generate_bitstream'/(prep.TARGET+'.bgr')
    require('Generating Programming File done.' in bgr.read_text(encoding='gb18030'),'programming report not complete')
    data=(work/BIT).read_bytes();header=bit_header(data);validate(work)
    return {'Schema':'camera-vga-upright-bitstream-verification-v1','Verified':True,'Target':prep.TARGET,'CheckedUTC':prep.utc(),
        'CandidateADFSHA256':c['CandidateSHA256'],'NativeTiming':checks,'ActualEvents':actual,
        'Bitstream':{'Path':str(work/BIT),'SHA256':sha(work/BIT),'Bytes':len(data),'Header':header},
        'EvidenceSHA256':{n:sha(work/n) for n in ('bitstream-plan.json','pre-bit-audit.json','execution-result.json','stdout.log','stderr.log',REPORT,EXCEPTIONS,BIT)},
        'VerifierSHA256':sha(SELF),'HardwareAccessed':False,'HardwareReleaseAllowed':False,'ExternalACTimingAccepted':False,'DiagnosticOnly':True}


def execute(work):
    plan,c=validate(work);work=Path(work);require(os.name=='nt','native upright bit execution requires Windows')
    require({p.name for p in work.iterdir()}=={'audited-final.adf','tool-snapshot.py','bitstream.tcl','bitstream-plan.json'},'fresh prepared bit directory required')
    watched=c['Watched'];watched.update({p:sha(p) for p in work.iterdir()})
    result={'Schema':EXEC_SCHEMA,'StartedUTC':prep.utc(),'Target':prep.TARGET,'Command':plan['Command'],
        'CandidateADFSHA256':c['CandidateSHA256'],'MaximumSeconds':plan['MaximumSeconds'],'HardwareAccessed':False,
        'TimedOut':False,'StoppedForUnexpectedStage':False,'ExitCode':None,'EDAExecuted':False}
    inspect.diagnostic.write(work/'execution-start.json',result);process=None;started=time.monotonic()
    expected=[(s,e) for s in STAGES for e in ('started','done')]
    try:
        with (work/'stdout.log').open('xb') as out,(work/'stderr.log').open('xb') as err:
            process=subprocess.Popen(plan['Command'],cwd=work,stdout=out,stderr=err,shell=False,
                                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            result.update(EDAExecuted=True,OwnedPID=process.pid)
            while process.poll() is None:
                remaining=plan['MaximumSeconds']-(time.monotonic()-started)
                if remaining<=0:result['TimedOut']=True;break
                try:process.wait(timeout=min(3,remaining))
                except subprocess.TimeoutExpired:pass
                current=inspect.diagnostic.stage_events((work/'stdout.log').read_text(encoding='gb18030',errors='replace'))
                if current!=expected[:len(current)]:result['StoppedForUnexpectedStage']=True;break
    except BaseException as error:result['Error']=type(error).__name__+': '+str(error)
    finally:
        if process is not None:
            if process.poll() is None:result['Cleanup']=inspect.diagnostic.cleanup.stop_owned_tree(process,work,'bounded upright bit')
            else:result['Cleanup']={'Complete':True,'OwnedPID':process.pid,'ParentExited':True,'DescendantLivenessIndependentlyVerified':False}
            result['ExitCode']=process.poll()
        else:result['Cleanup']={'Complete':True,'Required':False}
    diagnostics=[]
    for p in work.rglob('*.log'):
        diagnostics += [p.relative_to(work).as_posix()+': '+line.strip() for line in re.findall(
            r'(?m)^\s*(?:E:|F:|ERROR:|FATAL:|Traceback).*$',p.read_text(encoding='gb18030',errors='replace'))]
    result.update(FinishedUTC=prep.utc(),ElapsedSeconds=round(time.monotonic()-started,3),InputDrift=inspect.drift(watched),
        Diagnostics=diagnostics,Artifacts={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()
        and p.suffix in ('.log','.rtr','.sbit','.bgr','.tcl')})
    inspect.diagnostic.write(work/'execution-result.json',result)
    verification=verify(work);inspect.diagnostic.write(work/'verification.json',verification);return verification


def main():
    p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group(required=True)
    for name in ('prepare','validate','execute','gate','verify'):m.add_argument('--'+name,type=Path)
    p.add_argument('--request',type=Path);p.add_argument('--maximum-seconds',type=int,default=900);a=p.parse_args()
    if a.prepare:
        require(a.request is not None,'explicit reviewed request required');r=prepare(a.request,a.prepare,a.maximum_seconds)
        print(json.dumps({'Prepared':True,'Command':r['Command'],'EDAExecuted':False}))
    elif a.gate:
        r=gate(a.gate);print('CAMERA_VGA_UPRIGHT_GATE_PASS '+r['CandidateADFSHA256'])
    elif a.validate:
        r,_=validate(a.validate);print(json.dumps({'Validated':True,'Target':prep.TARGET,'EDAExecuted':False}))
    else:
        r=execute(a.execute) if a.execute else verify(a.verify)
        print(json.dumps({'Verified':r['Verified'],'Bitstream':r['Bitstream']}))


if __name__=='__main__':main()
