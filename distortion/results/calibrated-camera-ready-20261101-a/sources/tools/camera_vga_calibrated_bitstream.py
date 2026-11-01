"""Bound calibrated offline bit generation to explicit current-candidate evidence.

prepare/validate/verify are CPU-only. Explicit execute runs a fresh native STA,
then a CPU gate, then bit generation from the same copied ADF. No programming,
UART, physical routing edits, inherited candidate authority or board access.
"""
import argparse
import copy
from collections import Counter
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import run_camera_vga_calibrated_inspect as inspect
import audit_camera_vga_calibrated_io_cdc as interfaces
import audit_camera_vga_physical as timing
import audit_camera_vga_calibrated_io_cdc_native as native_io
import audit_camera_vga_calibrated_reset_effect as effect
import run_camera_vga_calibrated_derived_inspect as derived
import run_camera_vga_calibrated_physical as physical

prep=inspect.prep
require,sha=prep.require,prep.sha
SELF=Path(__file__).resolve()
PYTHON=prep.PROJECT.parent/'.venv/Scripts/python.exe'
REQUEST_SCHEMA='camera-vga-calibrated-bitstream-request-v1'
PLAN_SCHEMA='camera-vga-calibrated-bitstream-plan-v1'
EXEC_SCHEMA='camera-vga-calibrated-bitstream-execution-v1'
STAGES=['Report Timing','Generate Bitstream']
COMPLETE='CAMERA_VGA_CALIBRATED_BITSTREAM_COMPLETE'
REPORT='report_timing/'+prep.TARGET+'.rtr'
EXCEPTIONS='report_timing/'+prep.TARGET+'_exception.rtr'
BIT='generate_bitstream/'+prep.TARGET+'.sbit'


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


_AUTHORITY_CACHE = {}


def add(watched, path, digest=None, pds=None):
    return physical.add(watched, path, digest, pds)


def ref(value, watched, pds=None):
    return physical.binding(value, watched, pds)


def canonical_json(value):
    return json.loads(json.dumps(value))


def rehash_inputs(value, watched, pds, require_tools=True):
    require(isinstance(value.get('InputSHA256'), dict) and value['InputSHA256'], 'evidence input closure missing')
    for path, digest in value['InputSHA256'].items(): add(watched, path, digest, pds)
    if require_tools:
        require(isinstance(value.get('ToolSHA256'), dict) and value['ToolSHA256'], 'evidence tool closure missing')
        for path, digest in value['ToolSHA256'].items():
            require(value['InputSHA256'].get(path) == digest, 'tool is not input-bound')
            add(watched, path, digest, pds)


def passed_tables(report):
    tables, clocks = timing.summaries(report)
    require(set(tables) == {(c,k) for c in ('slow','fast') for k in ('setup','hold','recovery','removal','mpw')}
            and all(tables.values()) and clocks, 'all ten timing tables and clocks required')
    require(all(row['FailingChecks'] == 0 and row['WorstSlackNS'] >= 0 and row['TotalNegativeSlackNS'] == 0
                for rows in tables.values() for row in rows.values()), 'all ten timing tables must pass')
    return tables, clocks


def false_paths(path):
    with Path(path).open(encoding='gb18030') as stream: return timing.native.parse_false_paths(stream)


def reset_flags(application, claimed):
    require(application.get('Schema') == physical.SCHEMA and application.get('Target') == prep.TARGET
            and application.get('Mode') == 'save-reset' and application.get('ExecutionPassed') is True
            and 'Route' not in application and 'Request' not in application,
            'only a clean calibrated reset-only derivative is accepted')
    require(claimed.get('Schema') == effect.SCHEMA and claimed.get('Target') == prep.TARGET
            and all(claimed.get(k) is True for k in ('AuditPassed','ResetEffectVerified',
                'FunctionalGraphIdentical','AllFFPlacementsIdentical','RoutingUnchanged',
                'ExactResetExceptionUnionVerified','NoDataFalsePaths','AllInternalChecksMet',
                'ClockDefinitionsAndLoadsUnchanged','OtherExceptionsIdentical'))
            and claimed.get('ChangedNets') == [], 'complete reset-only effect audit required')


def io_flags(proof, candidate_sha):
    require(proof.get('Schema') == native_io.SCHEMA and proof.get('Target') == prep.TARGET
            and proof.get('StructuralAuditPassed') is True and proof.get('NativeAuditPassed') is True
            and proof.get('CandidateADF', {}).get('SHA256') == candidate_sha,
            'complete current calibrated IO/CDC proof required')
    for key in ('NativeInterstageTimingComplete','GrayDatapathBoundComplete'):
        require(proof.get('Scope', {}).get(key) is True, 'IO/CDC proof incomplete: '+key)
    for key in ('FinalNativeSiteMappingPassed','FinalFunctionalPadSiteMappingPassed'):
        require(proof.get('Pins', {}).get(key) is True, 'final IO mapping missing: '+key)
    require(proof.get('InputDelays', {}).get('Passed') is True
            and proof['InputDelays'].get('NativeDelayCells') == 8
            and proof['InputDelays'].get('AllPadConsumersTraverseTheirOwnDelay') is True,
            'complete native camera input-delay proof required')


def require_io_query_commands(body, plan):
    grouped, _ = native_io.batch_body(plan)
    individual = ['report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {'
                  +q['Source']+'} -to {'+q['Endpoint']+'}' for q in plan['Queries']+plan['GrayCoverageQueries']]
    individual += ['show -dev_instance {'+site+'}' for site in plan['IOSites']]
    require(body == grouped or inspect.query_commands(body) == individual,
            'IO query commands differ from the actual graph inventory')


def recompute_interfaces(proof, export_path, export, plan_path, build, watched):
    """Re-evaluate final graph, every native timing case and actual pad mappings."""
    pds = Path(build['PDS']['Executable'])
    rehash_inputs(proof, watched, pds)
    structure_path = ref(proof['StructureProof'], watched, pds)
    query_path = add(watched, structure_path.parent/'query-plan.json',
                     proof['InputSHA256'].get(str(structure_path.parent/'query-plan.json')), pds)
    require(str(query_path) in proof['InputSHA256'], 'IO query inventory is not proof-bound')
    old, query_plan, bound = native_io.load_structure(structure_path, query_path)
    for path, digest in bound.items(): add(watched, path, digest, pds)
    netlist = interfaces.artifact(export_path, export, prep.TARGET+'_sim.v')
    require(old.get('ExportReceipt') == effect.file_binding(export_path)
            and old['ActualNetlist'] == effect.file_binding(netlist)
            and old['CandidateADF'] == proof['CandidateADF']
            and old['CandidateADF']['SHA256'] == export['SourceADFSHA256']
            and old['BuildPlanSHA256'] == sha(plan_path), 'IO structure is not the final candidate export')
    # Recompute initial Gray coverage from the exact receipt-bound final report.
    gr = ref(old['GrayCoverageReport'], watched, pds)
    rr = ref(old['ReportReceipt'], watched, pds)
    rr_value = read(rr)
    _, reported = native_io.native_receipt(rr, rr_value['Mode'], export['SourceADFSHA256'], sha(plan_path), watched)
    require(gr == interfaces.artifact(rr, reported, prep.TARGET+'_exception.rtr'), 'Gray report is not receipt-bound')
    fdc = add(watched, plan_path.parent/'compiled'/build['Constraints']['FDC'],
              build['InputSHA256'][build['Constraints']['FDC']], pds)
    constraints, groups, missing, _ = interfaces.gray_coverage(old['GrayBitSynchronizers'], gr, fdc)
    require(constraints == old['ConstraintInventory'] and groups == old['GrayPhysicalGroups']
            and missing == query_plan['MissingGrayCases'], 'recomputed initial Gray coverage differs')
    native_path = ref(proof['NativeReceipt'], watched, pds)
    stage, receipt, body_path = native_io.query_receipt(native_path, old, watched)
    require(receipt.get('SourceReceipt') == export['SourceReceipt'], 'IO query belongs to another reset application')
    require_io_query_commands(body_path.read_text(encoding='ascii'), query_plan)
    reports = [add(watched, stage.parent/name, digest, pds)
               for name, digest in receipt['Artifacts'].items() if name.endswith('.rtr')]
    require(reports, 'native query reports missing')
    rows, bounds, supplemental = native_io.collect_paths(reports, query_plan['Queries'], query_plan['GrayCoverageQueries'])
    gray = native_io.complete_gray(old, supplemental)
    paths = {'top':prep.PROJECT/prep.TOP, 'pcf':plan_path.parent/'device_map'/(prep.TARGET+'.pcf'),
             'prt':plan_path.parent/'place_route'/(prep.TARGET+'_prr_route_optimize.prt'),
             'official':prep.PROJECT/'platform/video_base/HDMI_IN_DDR3_HDMI_OUT_top.fdc',
             'cam_reference':prep.PROJECT/'board/raw_camera_capture_cam2_ref.fdc',
             'cam_pins':prep.PROJECT/'board/raw_camera_capture_cam2_ref-pins.json'}
    texts = {key:add(watched, path).read_text(encoding='utf-8-sig') for key,path in paths.items()}
    top, _ = interfaces.io_syntax(texts['top'])
    net, _ = interfaces.io_syntax(netlist.read_text(encoding='utf-8-sig'))
    pins = interfaces.io.pin_audit(top, fdc.read_text(), texts['pcf'], texts['prt'], net,
                                  texts['official'], texts['cam_reference'], json.loads(texts['cam_pins']))
    require(pins == old['Pins'], 'recomputed functional pad/site inventory differs')
    interfaces.io.apply_native_sites(pins, (stage.parent/'stdout.log').read_text(encoding='gb18030'))
    actual = {'InputDelays':old['InputDelays'], 'ActualNetlist':old['ActualNetlist'], 'Pins':pins,
              'GrayBitSynchronizers':old['GrayBitSynchronizers'], 'GrayPhysicalGroups':gray,
              'ScalarSynchronizers':old['ScalarSynchronizers'], 'ResetReleaseStructure':old['ResetReleaseStructure'],
              'InterstagePaths':rows, 'InterstageBounds':bounds, 'SupplementalGrayPaths':supplemental,
              'Summary':{'GrayBits':len(old['GrayBitSynchronizers']), 'GrayCornerCases':sum(len(g['Paths']) for g in gray),
                         'ScalarChains':len(old['ScalarSynchronizers']), 'ExactInterstagePairs':len(query_plan['Queries']),
                         'ExactInterstageCornerKindCases':len(query_plan['Queries'])*4, 'NativeInterstageVariants':len(rows),
                         'MinimumInterstageSetupNS':min((p['SlackNS'] for p in rows if p['Kind']=='setup'), default=None),
                         'MinimumInterstageHoldNS':min((p['SlackNS'] for p in rows if p['Kind']=='hold'), default=None),
                         'MaximumGrayArrivalNS':max(g['MaximumArrivalNS'] for g in gray), 'NativePinCount':pins['TopPortCount']}}
    require(all(canonical_json(value) == proof.get(key) for key,value in actual.items()),
            'recomputed final IO/CDC proof differs')
    for module in (native_io, interfaces, interfaces.delay_audit, native_io.syntax, native_io.syntax.path_syntax,
                   interfaces.cdc, interfaces.io, interfaces.io.pin_parser, interfaces.io.net_parser, interfaces.io.tx_parser):
        add(watched, module.__file__)
    return netlist


def authority(request_path):
    request_path = inspect.canonical(request_path, prep.WORK)
    cached = _AUTHORITY_CACHE.get(str(request_path))
    if cached is not None:
        require(not inspect.drift(cached['Watched']), 'cached bit authority input/tool drift')
        return copy.deepcopy(cached)
    watched = {}; add(watched, request_path); request = read(request_path)
    fields = {'Schema','Target','BuildPlan','CandidateADF','FinalInspectionReceipt','FinalIOCDCProof',
              'ResetApplicationReceipt','ResetEffectAudit'}
    require(set(request) == fields and request['Schema'] == REQUEST_SCHEMA and request['Target'] == prep.TARGET,
            'exact calibrated bit request schema/fields required')
    plan_path = ref(request['BuildPlan'], watched); build = read(plan_path); pds = Path(build['PDS']['Executable'])
    candidate = ref(request['CandidateADF'], watched); candidate_sha = sha(candidate)
    export_path = ref(request['FinalInspectionReceipt'], watched)
    application_path = ref(request['ResetApplicationReceipt'], watched); application = read(application_path)
    effect_path = ref(request['ResetEffectAudit'], watched); claimed_effect = read(effect_path)
    reset_flags(application, claimed_effect)
    routes = claimed_effect['RouteScopeEvidence']
    before_route = ref(routes['BaselineReceipt'], watched, pds)
    after_route = ref(routes['CandidateReceipt'], watched, pds)
    computed_effect = effect.run(application_path, export_path, before_route, after_route)
    compare = lambda value:canonical_json({k:v for k,v in value.items() if k != 'CreatedUTC'})
    require(compare(computed_effect) == compare(claimed_effect), 'current reset-only effect differs on recomputation')
    rehash_inputs(computed_effect, watched, pds)
    # effect.run has already rebound this exact export/application and all raw inputs.
    export = read(export_path)
    original = plan_path.parent/'place_route'/(prep.TARGET+'_pnr.adf')
    require(application['BuildPlan'] == str(plan_path) and application['BuildPlanSHA256'] == sha(plan_path)
            and application['SourceADF'] == str(original) and application['SourceADFSHA256'] == sha(original)
            and application['ResultADFSHA256'] == candidate_sha != sha(original)
            and computed_effect['ResultADF'] == effect.file_binding(candidate)
            and export['SourceADFSHA256'] == candidate_sha and export['BuildPlanSHA256'] == sha(plan_path)
            and sha(export_path.parent/'input.adf') == candidate_sha, 'bit derivative/export identities differ')
    report = effect.artifact(export_path, export, prep.TARGET+'.rtr', watched)
    exceptions = effect.artifact(export_path, export, prep.TARGET+'_exception.rtr', watched)
    passed_tables(report)
    require(all(not rows for (corner,kind),rows in false_paths(exceptions).items() if kind in ('setup','hold')),
            'data false paths cannot authorize a bitstream')
    proof_path = ref(request['FinalIOCDCProof'], watched); proof = read(proof_path)
    io_flags(proof, candidate_sha)
    netlist = recompute_interfaces(proof, export_path, export, plan_path, build, watched)
    require(proof['InputSHA256'].get(str(netlist)) == sha(netlist), 'IO proof does not bind final export')
    for path in (SELF,PYTHON,Path(inspect.__file__).resolve(),Path(derived.__file__).resolve(),
                 Path(physical.__file__).resolve(),Path(effect.__file__).resolve(),Path(timing.__file__).resolve(),
                 Path(timing.native.__file__).resolve(),Path(timing.hold.__file__).resolve()):add(watched, path)
    require(not inspect.drift(watched), 'bit authority input/tool drift')
    context = {'Request':request,'RequestPath':request_path,'Build':build,'PlanPath':plan_path,'Candidate':candidate,
               'CandidateSHA256':candidate_sha,'FinalReport':report,'FinalExceptions':exceptions,'Watched':watched}
    _AUTHORITY_CACHE[str(request_path)] = copy.deepcopy(context)
    return context


def render(context,work):
    base=context['PlanPath'].parent
    rendered=inspect.render('export',(base/'timing.tcl').read_text(encoding='ascii'),base,work)
    boundary='report_timing -force_to_run -input_db_file '
    require(rendered.count(boundary)==1,'one fresh native report context required')
    prefix=rendered[:rendered.index(boundary)];w=work.as_posix();marker='CAMERA_VGA_CALIBRATED_GATE_PASS '+context['CandidateSHA256']
    return (prefix+boundary+'{'+w+'/audited-final.adf} -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n'
        'if {[info script] ne {}} {\n    set checked [exec {'+PYTHON.as_posix()+'} -B {'+SELF.as_posix()+'} --gate {'+w+'}]\n'
        '    puts $checked\n    if {[string first {'+marker+'} $checked] < 0} {error {Missing calibrated pre-bit gate}}\n'
        '    gen_bit_stream -force_to_run -input_db_file {'+w+'/audited-final.adf} -scbv {High Voltage} -unused_io_status UNUSED\n'
        '    puts {'+COMPLETE+'}\n    flush stdout\n}\n')


def recipe(request_path,work,maximum=900):
    work=prep.work_path(work);require(work.name.startswith('bit-'),'calibrated bit-* stage required')
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
    return plan


def validate(work):
    work=prep.work_path(work);plan=read(work/'bitstream-plan.json')
    expected,tcl,c=recipe(plan['Request']['Path'],work,plan['MaximumSeconds'])
    require(set(plan)==set(expected)|{'PreparedUTC'} and {k:v for k,v in plan.items() if k!='PreparedUTC'}==expected,'calibrated bit plan recipe drift')
    require((work/'bitstream.tcl').read_bytes()==tcl.encode('ascii') and sha(work/'audited-final.adf')==c['CandidateSHA256']
            and sha(work/'tool-snapshot.py')==sha(SELF),'calibrated bit prepared artifact drift')
    return plan,c


def compare_native(c,report,exceptions):
    require(passed_tables(report)==passed_tables(c['FinalReport']),'fresh timing summary/clock identities differ')
    normalize=lambda d:{k:Counter(json.dumps(r,sort_keys=True) for r in v) for k,v in d.items()}
    require(normalize(false_paths(exceptions))==normalize(false_paths(c['FinalExceptions'])),'fresh false-path identities differ')
    require(timing.exceptions(exceptions,set())==timing.exceptions(c['FinalExceptions'],set()),'fresh non-false exception paths differ')
    return {'AllTenTimingTablesPassed':True,'ClockAndSummaryIdentityPreserved':True,'AllExceptionPathsPreserved':True}


def gate(work):
    plan,c=validate(work);work=Path(work);checks=compare_native(c,work/REPORT,work/EXCEPTIONS);validate(work)
    result={'Schema':'camera-vga-calibrated-pre-bit-gate-v1','GatePassed':True,'Target':prep.TARGET,
        'CandidateADFSHA256':c['CandidateSHA256'],'CheckedUTC':prep.utc(),**checks,
        'EvidenceSHA256':{n:sha(work/n) for n in ('bitstream-plan.json','audited-final.adf','bitstream.tcl',REPORT,EXCEPTIONS)}}
    inspect.diagnostic.write(work/'pre-bit-audit.json',result);return result


def events(text,digest):
    result=[];marker='CAMERA_VGA_CALIBRATED_GATE_PASS '+digest
    for line in text.splitlines():
        line=line.strip();m=re.fullmatch(r'Process "([^"]+)" (started|done)\.',line)
        if m:result.append(m.groups())
        elif line.startswith('CAMERA_VGA_CALIBRATED_GATE_PASS'):
            require(line==marker,'wrong calibrated gate marker');result.append(('Runtime gate','passed'))
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
        require(values[k]==v,'calibrated bit identity differs: '+k)
    return values


def verify(work):
    plan,c=validate(work);work=Path(work);receipt=read(work/'execution-result.json')
    require(receipt.get('Schema')==EXEC_SCHEMA and receipt.get('ExitCode')==0 and receipt.get('InputDrift')==[]
            and receipt.get('Diagnostics')==[] and not receipt.get('Error') and receipt.get('TimedOut') is False
            and receipt.get('StoppedForUnexpectedStage') is False and receipt.get('Command')==plan['Command']
            and receipt.get('CandidateADFSHA256')==c['CandidateSHA256'] and receipt.get('Cleanup',{}).get('Complete') is True,'unclean calibrated bit execution')
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
    return {'Schema':'camera-vga-calibrated-bitstream-verification-v1','Verified':True,'Target':prep.TARGET,'CheckedUTC':prep.utc(),
        'CandidateADFSHA256':c['CandidateSHA256'],'NativeTiming':checks,'ActualEvents':actual,
        'Bitstream':{'Path':str(work/BIT),'SHA256':sha(work/BIT),'Bytes':len(data),'Header':header},
        'EvidenceSHA256':{n:sha(work/n) for n in ('bitstream-plan.json','pre-bit-audit.json','execution-result.json','stdout.log','stderr.log',REPORT,EXCEPTIONS,BIT)},
        'VerifierSHA256':sha(SELF),'HardwareAccessed':False,'HardwareReleaseAllowed':False,'ExternalACTimingAccepted':False,'DiagnosticOnly':True}


def execute(work):
    plan,c=validate(work);work=Path(work);require(os.name=='nt','native calibrated bit execution requires Windows')
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
            if process.poll() is None:result['Cleanup']=inspect.diagnostic.cleanup.stop_owned_tree(process,work,'bounded calibrated bit')
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
        r=gate(a.gate);print('CAMERA_VGA_CALIBRATED_GATE_PASS '+r['CandidateADFSHA256'])
    elif a.validate:
        r,_=validate(a.validate);print(json.dumps({'Validated':True,'Target':prep.TARGET,'EDAExecuted':False}))
    else:
        r=execute(a.execute) if a.execute else verify(a.verify)
        print(json.dumps({'Verified':r['Verified'],'Bitstream':r['Bitstream']}))


if __name__=='__main__':main()
