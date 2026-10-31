"""Prepare/validate an offline camera bit, or explicitly run fresh STA and generation.

One fresh native process uses the camera's original direct-path flow context,
an explicit independent final ADF, one report_timing, a CPU gate, then bit
generation. No mpnr mutation, programmer, UART, or board access is performed.
"""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import time

import audit_camera_vga_physical as comparison
import run_camera_vga_export as export
import run_camera_vga_physical as core

PROJECT, BUILD, BASE = core.PROJECT, core.ROOT, core.BASE
SELF = Path(__file__).resolve()
TARGET = core.TARGET
FINAL = BUILD/'physical-final-report-20261031-a'
ADF = FINAL/'input.adf'
ADF_SHA = 'daa2a9221238d09398ba325acef561b604dcb5643571301ba8831f76736dfd9f'
AUDIT = BUILD/'physical-comparison-20261031-a.json'
AUDIT_SHA = '17d68f155e2c7585ccc45e14d9aad7c32ab4f8c25debe40578c660021996938f'
PYTHON = PROJECT.parent/'.venv/Scripts/python.exe'
PDS = core.PDS
MARKER = 'CAMERA_VGA_PRE_BIT_AUDIT_PASS '+ADF_SHA
COMPLETE = 'CAMERA_VGA_BITSTREAM_COMPLETE'
STAGES = ['Report Timing','Generate Bitstream']
REPORT = 'report_timing/'+TARGET+'.rtr'
EXCEPTIONS = 'report_timing/'+TARGET+'_exception.rtr'
BIT = 'generate_bitstream/'+TARGET+'.sbit'
require,sha,write_json = core.require,core.sha,core.write_json


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def utc():
    return datetime.now(timezone.utc).isoformat()


def work_path(value,*,exists=True):
    path=Path(value).absolute()
    require(path==path.resolve() and path.parent==BUILD and re.fullmatch(r'bit-[A-Za-z0-9_-]+',path.name),
            'canonical bit-* direct camera workspace child required')
    require(path.is_dir() if exists else not path.exists(),'work directory existence differs')
    return path


def authority():
    require(sha(ADF)==ADF_SHA and sha(AUDIT)==AUDIT_SHA,'fixed final camera ADF/audit changed')
    original,watched=core.bind_inputs(extra=(SELF,Path(export.__file__).resolve(),Path(comparison.__file__).resolve()))
    audited=load(AUDIT)
    require(audited.get('Schema')=='camera-vga-physical-union-comparison-v1' and
            audited.get('AuditPassed') is True and audited.get('AllInternalChecksMet') is True and
            audited.get('ClockDefinitionsAndLoadsUnchanged') is True and audited.get('NoDataFalsePaths') is True,
            'complete passing camera physical comparison required')
    graph=audited['FunctionalComparison']
    require(graph.get('FunctionalGraphIdentical') is True and graph.get('AllFFPlacementsIdentical') is True and
            graph.get('Cells')==36469 and graph.get('FFCount')==17417,'camera functional/FF evidence differs')
    require(len(audited['CornerSummaries'])==10 and all(v['FailingChecks']==0 and v['WorstSlackNS']>=0
            for v in audited['CornerSummaries'].values()),'all ten internal timing tables must pass')
    require(audited['InputSHA256'].get(str(ADF))==ADF_SHA,'physical comparison final ADF differs')
    union=audited['ExceptionUnionProof']
    require(union.get('AuditPassed') is True and union['RouteChain']['CandidateADFSHA256']==ADF_SHA,
            'strict exception proof final ADF differs')
    for evidence in (audited,union):
        for group in ('InputSHA256','ToolSHA256'):
            for name,digest in evidence[group].items():
                p=Path(name).absolute()
                require(p==p.resolve() and p.is_file() and (p.is_relative_to(PROJECT.parent) or p.is_relative_to(PDS.parent)),
                        'unexpected audit input location')
                require(sha(p)==digest,'bound camera audit input/tool drift: '+name)
                watched[p]=digest
    for p in (SELF,PYTHON,AUDIT,ADF,Path(export.__file__).resolve(),Path(comparison.__file__).resolve(),
              Path(comparison.hold.__file__).resolve(),Path(comparison.native.__file__).resolve(),
              FINAL/(TARGET+'.rtr'),FINAL/(TARGET+'_exception.rtr')):
        watched[p]=sha(p)
    require(not core.check_inputs(watched),'authority input drift')
    return original,watched


def render_tcl(original,original_work,work):
    rendered=export.render_tcl(original,original_work,work)
    boundary='report_timing -force_to_run -input_db_file '
    require(rendered.count(boundary)==1,'single explicit fresh STA context required')
    prefix=rendered[:rendered.index(boundary)]
    w=work.as_posix()
    return (prefix+boundary+'{'+w+'/audited-final.adf} -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n'
            'if {[info script] ne {}} {\n'
            '    set checked [exec {'+PYTHON.as_posix()+'} -B {'+SELF.as_posix()+'} --gate {'+w+'}]\n'
            '    puts $checked\n'
            '    if {[string first {'+MARKER+'} $checked] < 0} {error {Missing camera pre-bit gate}}\n'
            '    gen_bit_stream -force_to_run -input_db_file {'+w+'/audited-final.adf} -scbv {High Voltage} -unused_io_status UNUSED\n'
            '    puts {'+COMPLETE+'}\n    flush stdout\n}\n')


def prepare(work):
    work=work_path(work,exists=False);original,watched=authority()
    tcl=render_tcl((BASE/'timing.tcl').read_text(encoding='ascii'),original['AliasWorkDirectory'],work)
    work.mkdir();shutil.copyfile(ADF,work/'audited-final.adf');shutil.copyfile(SELF,work/'tool-snapshot.py')
    (work/'export.tcl').write_text(tcl,encoding='ascii',newline='\n')
    plan={'Schema':'camera-vga-offline-bitstream-plan-v1','PreparedUTC':utc(),'ProjectRoot':str(PROJECT),
          'WorkDirectory':str(work),'Target':TARGET,'FinalADFSHA256':ADF_SHA,'PhysicalAuditSHA256':AUDIT_SHA,
          'SourceInputCount':len(original['InputSHA256']),'CompiledInputCount':len(original['CompiledInputs']),
          'Command':[str(PDS),'-file',(work/'export.tcl').as_posix(),'-work_dir',work.as_posix(),'-project_name',TARGET],
          'ProjectInputSHA256':{str(p):h for p,h in watched.items()},
          'WorkInputSHA256':{n:sha(work/n) for n in ('audited-final.adf','tool-snapshot.py','export.tcl')},
          'ExpectedActualStages':STAGES,'MaximumSeconds':900,'PreparedOnly':True,'EDAExecutedByPreparer':False,
          'HardwareAccessed':False,'BitstreamRequested':True,'HardwareReleaseAllowed':False,
          'ExternalIOAccepted':False,'CDCPhysicalAccepted':False,'DiagnosticOnly':True,
          'Limits':'Offline camera candidate only. External DVP/HDMI AC and physical CDC need separate review; SRAM needs a new explicit power confirmation.'}
    require(not core.check_inputs(watched),'authority drift during preparation')
    write_json(work/'bitstream-plan.json',plan);return plan


def validate(work):
    work=work_path(work);plan=load(work/'bitstream-plan.json');original,watched=authority()
    expected={'Schema':'camera-vga-offline-bitstream-plan-v1','ProjectRoot':str(PROJECT),'WorkDirectory':str(work),
              'Target':TARGET,'FinalADFSHA256':ADF_SHA,'PhysicalAuditSHA256':AUDIT_SHA,
              'SourceInputCount':115,'CompiledInputCount':109,'ExpectedActualStages':STAGES,'MaximumSeconds':900,
              'PreparedOnly':True,'EDAExecutedByPreparer':False,'HardwareAccessed':False,'BitstreamRequested':True,
              'HardwareReleaseAllowed':False,'ExternalIOAccepted':False,'CDCPhysicalAccepted':False,'DiagnosticOnly':True}
    for k,v in expected.items():require(type(plan.get(k)) is type(v) and plan[k]==v,'bit plan identity differs: '+k)
    require(plan['ProjectInputSHA256']=={str(p):h for p,h in watched.items()},'bit plan complete input closure differs')
    tcl=render_tcl((BASE/'timing.tcl').read_text(encoding='ascii'),original['AliasWorkDirectory'],work)
    require((work/'export.tcl').read_bytes()==tcl.encode('ascii'),'bit Tcl recipe changed')
    require(plan['Command']==[str(PDS),'-file',(work/'export.tcl').as_posix(),'-work_dir',work.as_posix(),'-project_name',TARGET],
            'bit command differs from fixed direct-path invocation')
    require(set(plan['WorkInputSHA256'])=={'audited-final.adf','tool-snapshot.py','export.tcl'},'work file inventory differs')
    for n,h in plan['WorkInputSHA256'].items():require(sha(work/n)==h,'prepared bit input changed: '+n)
    require(sha(work/'audited-final.adf')==ADF_SHA and sha(work/'tool-snapshot.py')==sha(SELF),'final ADF/tool copy differs')
    return plan


def compare_native(report,exceptions):
    baseline=comparison.summaries(FINAL/(TARGET+'.rtr'));current=comparison.summaries(report)
    require(current==baseline,'fresh native clocks or timing summary differs')
    require(len(current[0])==10,'missing native timing table')
    require(all(r['FailingChecks']==0 and r['WorstSlackNS']>=0 and r['TotalNegativeSlackNS']==0
            for rows in current[0].values() for r in rows.values()),'fresh native timing failure')
    def false(path):
        with Path(path).open(encoding='gb18030') as stream:values=comparison.native.parse_false_paths(stream)
        return {k:Counter(json.dumps(r,sort_keys=True) for r in rows) for k,rows in values.items()}
    require(false(exceptions)==false(FINAL/(TARGET+'_exception.rtr')),'fresh false-path identities differ')
    require(comparison.exceptions(exceptions,set())==comparison.exceptions(FINAL/(TARGET+'_exception.rtr'),set()),
            'fresh non-false exception paths differ')
    return {'AllTenNativeTimingTablesPassed':True,'AllNativeSummariesAndClocksUnchanged':True,
            'AllExceptionPathsUnchanged':True,'NoDataSetupOrHoldFalsePaths':True}


def gate(work):
    work=work_path(work);validate(work);result=compare_native(work/REPORT,work/EXCEPTIONS);validate(work)
    result.update(Schema='camera-vga-pre-bit-gate-v1',GatePassed=True,CheckedUTC=utc(),FinalADFSHA256=ADF_SHA,
                  HardwareAccessed=False,HardwareReleaseAllowed=False,
                  EvidenceSHA256={n:sha(work/n) for n in ('bitstream-plan.json','audited-final.adf','export.tcl',REPORT,EXCEPTIONS)})
    write_json(work/'pre-bit-audit.json',result);return result


def actual_events(text):
    events=[]
    for line in text.splitlines():
        m=re.fullmatch(r'Process "([^"]+)" (started|done)\.',line.strip())
        if m:events.append((m[1],m[2]))
        elif line.strip().startswith('CAMERA_VGA_PRE_BIT_AUDIT_PASS'):
            require(line.strip()==MARKER,'wrong camera runtime gate marker');events.append(('Runtime gate','passed'))
        elif line.strip()==COMPLETE:events.append(('Bitstream','complete'))
    require(events==[('Report Timing','started'),('Report Timing','done'),('Runtime gate','passed'),
                     ('Generate Bitstream','started'),('Generate Bitstream','done'),('Bitstream','complete')],
            'native execution order must be fresh STA, CPU gate, bit, completion')
    return events


def bit_header(data):
    prefix=bytes.fromhex('00090ff00ff00ff00ff000')+b'PANGO MICROSYSTEMS, INC.\0\1'
    require(data.startswith(prefix),'wrong native bitstream prefix');offset=len(prefix);result={}
    for tag,name in zip(b'abcdef',('Design','Device','Date','Time','Generator','Version')):
        require(offset+3<=len(data) and data[offset]==tag,'missing bitstream field')
        count=int.from_bytes(data[offset+1:offset+3],'big')
        require(count>0 and offset+3+count<=len(data),'truncated bitstream field')
        raw=data[offset+3:offset+3+count]
        require(raw[-1:]==b'\0' and b'\0' not in raw[:-1],'invalid bitstream text field')
        result[name]=raw[:-1].decode('ascii');offset+=3+count
    require(data[offset:offset+3]==b'ghi','bitstream header terminator differs')
    for k,v in {'Design':TARGET,'Device':'Logos2-PG2L100H--6-FBG676','Generator':'Fabric Compiler','Version':'2023.2-SP3<154097>'}.items():
        require(result[k]==v,'camera bitstream identity differs: '+k)
    require(len(data)>1000000,'empty/truncated programming payload');return result


def verify(work):
    work=work_path(work);plan=validate(work);receipt=load(work/'execution-result.json')
    require(receipt.get('Schema')=='camera-vga-bitstream-execution-v1' and receipt.get('ExitCode')==0 and
            receipt.get('TimedOut') is False and receipt.get('StoppedForUnexpectedStage') is False and
            receipt.get('InputDrift')==[] and receipt.get('Diagnostics')==[] and receipt.get('Command')==plan['Command'] and
            receipt.get('FinalADFSHA256')==ADF_SHA,'native bit execution did not complete cleanly')
    for n,h in receipt['Artifacts'].items():
        path=core.canonical_file(work/n,work);require(sha(path)==h,'native bit artifact changed: '+n)
    text=(work/'stdout.log').read_text(encoding='gb18030');events=actual_events(text)
    result=compare_native(work/REPORT,work/EXCEPTIONS);audited=load(work/'pre-bit-audit.json')
    require(all(audited.get(k)==v for k,v in result.items()) and audited.get('GatePassed') is True and
            audited.get('FinalADFSHA256')==ADF_SHA,'runtime gate claim differs')
    require(audited['EvidenceSHA256']=={n:sha(work/n) for n in ('bitstream-plan.json','audited-final.adf','export.tcl',REPORT,EXCEPTIONS)},
            'runtime gate evidence changed')
    commands=[c for c in re.findall(r'(?m)^Executing : (gen_bit_stream .+)$',text) if not c.endswith(' successfully.')]
    require(len(commands)==1 and '-input_db_file '+(work/'audited-final.adf').as_posix() in commands[0],
            'native generation did not use final copied camera ADF')
    bgr=work/'generate_bitstream'/(TARGET+'.bgr')
    require(bgr.is_file() and 'Generating Programming File done.' in bgr.read_text(encoding='gb18030'),'bit report lacks completion')
    data=(work/BIT).read_bytes();header=bit_header(data);validate(work)
    return {'Schema':'camera-vga-offline-bitstream-verification-v1','Verified':True,'CheckedUTC':utc(),
            'FinalADFSHA256':ADF_SHA,'RuntimeGateBeforeGeneration':True,'ActualEvents':events,'NativeTiming':result,
            'Bitstream':{'Path':str(work/BIT),'SHA256':hashlib.sha256(data).hexdigest(),'Bytes':len(data),'Header':header},
            'EvidenceSHA256':{n:sha(work/n) for n in ('bitstream-plan.json','pre-bit-audit.json','execution-result.json','stdout.log','stderr.log',REPORT,EXCEPTIONS,BIT)},
            'VerifierSHA256':sha(SELF),'HardwareAccessed':False,'HardwareReleaseAllowed':False,
            'CDCPhysicalAccepted':False,'ExternalIOAccepted':False,'DiagnosticOnly':True}


def execute(work,maximum_seconds=900):
    work=work_path(work);plan=validate(work)
    require(type(maximum_seconds) is int and 30<=maximum_seconds<=900,'bounded execution must be 30..900 seconds')
    require(set(p.name for p in work.iterdir())=={'audited-final.adf','tool-snapshot.py','export.tcl','bitstream-plan.json'},
            'native execution requires a fresh prepared directory')
    watched={Path(p):h for p,h in plan['ProjectInputSHA256'].items()}
    watched.update({work/n:h for n,h in plan['WorkInputSHA256'].items()});watched[work/'bitstream-plan.json']=sha(work/'bitstream-plan.json')
    receipt={'Schema':'camera-vga-bitstream-execution-v1','StartedUTC':utc(),'Command':plan['Command'],
             'FinalADFSHA256':ADF_SHA,'HardwareAccessed':False,'HardwareReleaseAllowed':False,'TimedOut':False,
             'StoppedForUnexpectedStage':False,'MaximumSeconds':maximum_seconds}
    process=None;started=time.monotonic();write_json(work/'execution-start.json',receipt)
    try:
        with (work/'stdout.log').open('xb') as out,(work/'stderr.log').open('xb') as err:
            process=subprocess.Popen(plan['Command'],cwd=work,stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            while process.poll() is None:
                remaining=maximum_seconds-(time.monotonic()-started)
                if remaining<=0:receipt['TimedOut']=True;core.stop_owned(process);break
                try:process.wait(timeout=min(5,remaining))
                except subprocess.TimeoutExpired:pass
                text=(work/'stdout.log').read_text(encoding='gb18030')
                stages=re.findall(r'^Process "([^"]+)" started\.',text,re.M)
                if stages!=STAGES[:len(stages)]:receipt['StoppedForUnexpectedStage']=True;core.stop_owned(process);break
    except Exception as error:receipt['Error']=type(error).__name__+': '+str(error)
    finally:
        core.stop_owned(process)
        diagnostics=[]
        for p in work.rglob('*.log'):
            diagnostics.extend(str(p.relative_to(work))+': '+line.strip() for line in
                re.findall(r'(?m)^\s*(?:E:|F:|ERROR:|FATAL:|Traceback).*$',p.read_text(encoding='gb18030')))
        receipt.update(FinishedUTC=utc(),ElapsedSeconds=round(time.monotonic()-started,3),ExitCode=process.poll() if process else None,
                       InputDrift=core.check_inputs(watched),Diagnostics=diagnostics,
                       Artifacts={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file() and p.suffix in ('.log','.rtr','.sbit','.bgr','.tcl')})
        write_json(work/'execution-result.json',receipt)
    result=verify(work);write_json(work/'verification.json',result);return result


def main():
    p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group(required=True)
    for name in ('prepare','validate','execute','gate','verify'):m.add_argument('--'+name,type=Path)
    args=p.parse_args()
    if args.prepare:
        result=prepare(args.prepare);print(json.dumps({'PreparedOnly':True,'Command':result['Command']}))
    elif args.validate:
        result=validate(args.validate);print(json.dumps({'ValidationPassed':True,'HardwareAccessed':False,'Target':TARGET}))
    elif args.gate:gate(args.gate);print(MARKER)
    elif args.execute:
        result=execute(args.execute);print(json.dumps({'Verified':result['Verified'],'Bitstream':result['Bitstream']}))
    else:
        result=verify(args.verify);print(json.dumps({'Verified':result['Verified'],'Bitstream':result['Bitstream']}))


if __name__=='__main__':main()
