"""CPU-only authority, provenance and native-gate rejection cases."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_bitstream as bit


def header(target=bit.prep.TARGET,device='Logos2-PG2L100H--6-FBG676'):
    data=bytes.fromhex('00090ff00ff00ff00ff000')+b'PANGO MICROSYSTEMS, INC.\0\1'
    for tag,value in zip(b'abcdef',[target,device,'11/01/26','13:00:00','Fabric Compiler','2023.2-SP3<154097>']):
        raw=value.encode()+b'\0';data+=bytes([tag])+len(raw).to_bytes(2,'big')+raw
    return data+b'ghi'+b'\xff'*1000001


def test_bit_header_accepts_current_target_and_rejects_stale_bit():
    assert bit.bit_header(header())['Design']==bit.prep.TARGET
    for data in (b'bad',header()[:200],header('camera_vga_calibrated_top'),header(device='wrong-device')):
        with pytest.raises(ValueError):bit.bit_header(data)


def event_log():
    return '\n'.join(['Process "Report Timing" started.','Process "Report Timing" done.',
        'CAMERA720_GATE_PASS '+'a'*64,'Process "Generate Bitstream" started.',
        'Process "Generate Bitstream" done.',bit.COMPLETE])


def test_stage_order_requires_fresh_report_gate_and_one_bit_generation():
    assert len(bit.events(event_log(),'a'*64))==6
    for text in (event_log().replace('a'*64,'b'*64),
                 event_log().replace('CAMERA720_GATE_PASS '+'a'*64,''),
                 event_log()+'\nProcess "Generate Bitstream" started.',
                 event_log().replace('Process "Report Timing" done.','Process "Synthesize" started.')):
        with pytest.raises(ValueError):bit.events(text,'a'*64)


@pytest.mark.parametrize('row',[
    {'FailingChecks':1,'WorstSlackNS':0.1,'TotalNegativeSlackNS':0},
    {'FailingChecks':0,'WorstSlackNS':-0.001,'TotalNegativeSlackNS':0},
    {'FailingChecks':0,'WorstSlackNS':0.1,'TotalNegativeSlackNS':-0.001},
])
def test_native_gate_rejects_failure_even_if_other_values_look_good(monkeypatch,row):
    tables={(c,k):{('a','b'):row} for c in ('slow','fast') for k in ('setup','hold','recovery','removal','mpw')}
    monkeypatch.setattr(bit.timing,'summaries',lambda path:(tables,['clock']))
    with pytest.raises(ValueError,match='must pass'):bit.passed_tables('unused')


def test_native_gate_rejects_missing_corner_or_type(monkeypatch):
    monkeypatch.setattr(bit.timing,'summaries',lambda path:({('slow','setup'):{'row':{}}},['clock']))
    with pytest.raises(ValueError,match='all ten'):bit.passed_tables('unused')


def claims():
    candidate={'Path':'candidate.adf','SHA256':'a'*64}
    reset={'Schema':'camera720-reset-effect-v1','Target':bit.prep.TARGET,'CandidateADFSHA256':'a'*64,
        'RouteComparison':{'RoutingUnchanged':True,'ChangedNets':[],'NonconstraintSemanticsUnchanged':True}}
    reset.update({k:True for k in ('AuditPassed','ResetEffectVerified','AllInternalChecksMet','FunctionalGraphIdentical',
        'AllFFPlacementsIdentical','ExactResetExceptionUnionVerified','NoDataFalsePaths','ClockDefinitionsAndLoadsUnchanged')})
    cdc={'Schema':'camera720-cdc-native-coverage-v1','Target':bit.prep.TARGET,'CandidateADF':candidate,
        'Complete':True,'EnumeratedPathsTimingPassed':True,'NativeSiteMappingVerified':True,
        'EnumeratedPathsAndSitesPassed':True,'Violations':[],'MissingCases':[],'MissingPairCount':0,
        'NativeSiteError':None,'ExpectedCases':4,'CoveredCases':4}
    io={'Schema':'camera720-io-evidence-v1','Target':bit.prep.TARGET,'CandidateADF':candidate}
    io.update({k:True for k in ('AuditPassed','PinDeclarationsVerified','NativePadElectricalParametersVerified',
        'NativePinSitesVerified','InputDelayStructureVerified','TXMaximumPathsVerified','DVPReportedBudgetCoverageComplete')})
    return candidate,reset,cdc,io


@pytest.mark.parametrize('key',('AuditPassed','ResetEffectVerified','AllInternalChecksMet','FunctionalGraphIdentical',
    'AllFFPlacementsIdentical','ExactResetExceptionUnionVerified','NoDataFalsePaths','ClockDefinitionsAndLoadsUnchanged'))
def test_reset_gate_rejects_any_missing_proof(key):
    _,reset,_,_=claims();bit.reset_flags(reset,'a'*64);reset[key]=False
    with pytest.raises(ValueError):bit.reset_flags(reset,'a'*64)


@pytest.mark.parametrize('key',('Complete','EnumeratedPathsTimingPassed','NativeSiteMappingVerified','EnumeratedPathsAndSitesPassed'))
def test_cdc_gate_rejects_partial_coverage(key):
    candidate,_,cdc,_=claims();bit.cdc_flags(cdc,candidate);cdc[key]=False
    with pytest.raises(ValueError):bit.cdc_flags(cdc,candidate)


@pytest.mark.parametrize('key',('AuditPassed','PinDeclarationsVerified','NativePadElectricalParametersVerified',
    'NativePinSitesVerified','InputDelayStructureVerified','TXMaximumPathsVerified','DVPReportedBudgetCoverageComplete'))
def test_io_gate_rejects_unproved_pin_delay_or_budget(key):
    candidate,_,_,io=claims();bit.electrical_flags(io,candidate);io[key]=False
    with pytest.raises(ValueError):bit.electrical_flags(io,candidate)


def test_old_target_candidate_missing_case_and_changed_route_rejected():
    candidate,reset,cdc,io=claims()
    reset['RouteComparison']['ChangedNets']=['unexpected']
    with pytest.raises(ValueError):bit.reset_flags(reset,'a'*64)
    cdc['CoveredCases']=3
    with pytest.raises(ValueError):bit.cdc_flags(cdc,candidate)
    io['CandidateADF']={**candidate,'SHA256':'b'*64}
    with pytest.raises(ValueError):bit.electrical_flags(io,candidate)
    io['CandidateADF']=candidate;io['Target']='camera_vga_calibrated_top'
    with pytest.raises(ValueError):bit.electrical_flags(io,candidate)


def test_reuse_needs_all_three_explicit_exact_hash_anchors():
    reviewed={name:'a'*64 for name in ('ResetEffectAudit','FinalCDCProof','FinalIOProof')}
    request={name:{'SHA256':digest} for name,digest in reviewed.items()}
    bit.reviewed_anchors(reviewed,request)
    for value in ({}, {'ResetEffectAudit':'a'*64}, {**reviewed,'FinalCDCProof':'b'*64}, {**reviewed,'extra':'a'*64}):
        with pytest.raises(ValueError):bit.reviewed_anchors(value,request)


def test_rehash_rejects_changed_closure_and_missing_producer(tmp_path,monkeypatch):
    project=tmp_path/'distortion';tools=project/'tools';tools.mkdir(parents=True)
    monkeypatch.setattr(bit.prep,'PROJECT',project)
    producer=tools/'audit.py';producer.write_text('known source')
    evidence=project/'raw.json';evidence.write_text('raw result')
    value={'HardwareAccessed':False,'EDAExecuted':False,
        'InputSHA256':{str(producer):bit.sha(producer),str(evidence):bit.sha(evidence)}}
    bit.completed_audit(value,evidence,'audit.py',{},None)
    old=deepcopy(value);value['InputSHA256'].pop(str(producer))
    with pytest.raises(ValueError,match='producer'):bit.completed_audit(value,evidence,'audit.py',{},None)
    evidence.write_text('changed result')
    with pytest.raises(ValueError,match='hash differs'):bit.rehash_inputs(old,{},None)


def test_gate_rejects_report_mutation_while_cpu_parser_runs(tmp_path,monkeypatch):
    names=('bitstream-plan.json','audited-final.adf','bitstream.tcl',bit.REPORT,bit.EXCEPTIONS)
    for name in names:
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('before')
    monkeypatch.setattr(bit,'validate',lambda path:({}, {'CandidateSHA256':'a'*64}))
    def mutate(*args):
        (tmp_path/bit.REPORT).write_text('changed during parse');return {}
    monkeypatch.setattr(bit,'compare_native',mutate)
    with pytest.raises(ValueError,match='during gate'):bit.gate(tmp_path)
    assert not (tmp_path/'pre-bit-audit.json').exists()


@pytest.fixture
def sealed(tmp_path,monkeypatch):
    project=tmp_path/'distortion';work=project/'work/camera720-output';work.mkdir(parents=True)
    monkeypatch.setattr(bit.prep,'PROJECT',project);monkeypatch.setattr(bit.prep,'WORK',work)
    tool=project/'tools/camera720_bitstream.py';tool.parent.mkdir();tool.write_text('test validator bytes')
    python=tmp_path/'.venv/Scripts/python.exe';python.parent.mkdir(parents=True);python.write_bytes(b'not executable')
    monkeypatch.setattr(bit,'SELF',tool);monkeypatch.setattr(bit,'PYTHON',python)
    pds=tmp_path/'pds_shell.exe';pds.write_bytes(b'inert')
    def put(name,value):
        p=work/name;p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps(value) if isinstance(value,dict) else value);return p
    build=put('build/plan.json',{'PDS':{'Executable':str(pds)}})
    candidate=put('reset/input.adf','final candidate')
    report=put('export/report_timing/'+bit.prep.TARGET+'.rtr','passed report')
    exceptions=put('export/report_timing/'+bit.prep.TARGET+'_exception.rtr','exact exceptions')
    export=put('export/result.json',{'SourceADF':str(candidate),'SourceADFSHA256':bit.sha(candidate),
        'BuildPlanSHA256':bit.sha(build),'Artifacts':{p.relative_to(work/'export').as_posix():bit.sha(p) for p in (report,exceptions)}})
    paths={'BuildPlan':build,'CandidateADF':candidate,'FinalInspectionReceipt':export,
        'ResetApplicationReceipt':put('reset/result.json',{}),'ResetEffectAudit':put('effect.json',{}),
        'FinalCDCProof':put('cdc.json',{}),'FinalIOProof':put('io.json',{})}
    request={'Schema':bit.REQUEST_SCHEMA,'Target':bit.prep.TARGET,**{k:bit.binding(p) for k,p in paths.items()}}
    request_path=put('request.json',request)
    allpaths={request_path,build,candidate,report,exceptions,tool,python,pds,*paths.values()}
    context={'RequestPath':request_path,'PlanPath':build,'Candidate':candidate,'FinalReport':report,
        'FinalExceptions':exceptions,'Watched':{p:bit.sha(p) for p in allpaths}}
    monkeypatch.setattr(bit,'audit_authority',lambda *args:context)
    output=work/'authority.json';value=bit.prepare_authority(request_path,output)
    return output,value,candidate,tool


def test_authority_requires_caller_hash_and_rehashes_all_bound_inputs(sealed):
    path,value,candidate,tool=sealed
    result=bit.bind_authority(path,bit.sha(path));assert result['Candidate']==candidate
    with pytest.raises(ValueError,match='explicit authority'):bit.bind_authority(path,None)
    with pytest.raises(ValueError,match='hash differs'):bit.bind_authority(path,'0'*64)
    candidate.write_text('mutated ADF')
    with pytest.raises(ValueError,match='hash differs'):bit.bind_authority(path,bit.sha(path))


@pytest.mark.parametrize('change',('scope','producer','tool_inventory','request_candidate','missing_input'))
def test_authority_rejects_forged_scope_omitted_evidence_and_wrong_chain(sealed,change):
    path,value,candidate,tool=sealed
    if change=='scope':value['HardwareReleaseAllowed']=True
    elif change=='producer':value['ValidationMethod']['SHA256']='0'*64
    elif change=='tool_inventory':value['ToolSHA256']={}
    elif change=='request_candidate':value['CandidateADF']['SHA256']='1'*64
    else:value['InputSHA256'].pop(str(candidate))
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):bit.bind_authority(path,bit.sha(path))


@pytest.fixture
def reused(tmp_path,monkeypatch):
    """Exercise the reuse join; hash drift itself is separately checked above."""
    candidate,reset,cdc,io=claims()
    def put(name,value):
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value));return p
    app=put('application.json',{'Schema':bit.final.physical.SCHEMA,'Target':bit.prep.TARGET,
        'ExecutionPassed':True,'ResultADFSHA256':'a'*64,'BuildPlanSHA256':'b'*64,'Mode':'save-reset'})
    export=put('export.json',{})
    export_ref=bit.binding(export);app_ref=bit.binding(app)
    reset.update(Application=app_ref,FinalExport=export_ref,
        InputSHA256={str(app):bit.sha(app),str(export):bit.sha(export)})
    query={'Source':'meta/CLK','Endpoint':'sync/D','Clock':'board27',
        'CheckKinds':['setup','hold'],'Corners':['slow','fast']}
    initial,groups=bit.cdc.bodies([query],[])
    plan={'Schema':bit.cdc.SCHEMA,'Target':bit.prep.TARGET,'CandidateADF':candidate,
        'BuildPlanSHA256':'b'*64,'ExportReceipt':export_ref,'FinalExportReevaluated':True,
        'Queries':[query],'IOSites':[],'Groups':groups,'ExpectedCases':4,'InputSHA256':{'dummy':'d'*64},
        'QueryBodies':{f'query-{i:02}.tcl':bit.hashlib.sha256(t.encode('ascii')).hexdigest() for i,t in enumerate(initial)}}
    plan_path=put('batch-plan.json',plan)
    body=tmp_path/'query-body.tcl';body.write_text(initial[0])
    native_report=tmp_path/'native.rtr';native_report.write_text('receipt-bound native paths')
    records=[{'Source':'meta/CLK','Endpoint':'sync/D','Corner':corner,'Kind':kind,'SlackNS':0.1}
        for corner in ('slow','fast') for kind in ('setup','hold')]
    for record in records:
        record.update(Report=str(native_report),ReportLine=1,PathSHA256='a'*64)
    q=put('query.json',{})
    cdc.update(bit.cdc.coverage([query],records,[]),Records=records,BatchPlan=bit.binding(plan_path),
        NativeReceipts=[bit.binding(q)],InputSHA256={str(plan_path):bit.sha(plan_path),str(q):bit.sha(q),
            str(native_report):bit.sha(native_report)})
    io.update(ExportReceipt=export_ref,BuildPlanSHA256='b'*64,QueryReceipts=[bit.binding(q)],
        InputSHA256={str(q):bit.sha(q)})
    paths={'ResetEffectAudit':put('effect.json',reset),'FinalCDCProof':put('cdc.json',cdc),
        'FinalIOProof':put('io.json',io),'ResetApplicationReceipt':app,'FinalInspectionReceipt':export}
    request={'CandidateADF':candidate,'BuildPlan':{'SHA256':'b'*64},
        **{name:bit.binding(path) for name,path in paths.items()}}
    anchors={name:request[name]['SHA256'] for name in ('ResetEffectAudit','FinalCDCProof','FinalIOProof')}
    monkeypatch.setattr(bit,'completed_audit',lambda *a:None)
    monkeypatch.setattr(bit,'rehash_inputs',lambda *a:None)
    monkeypatch.setattr(bit,'ref',lambda value,*a:Path(value['Path']))
    monkeypatch.setattr(bit,'add',lambda watched,path,*a,**k:Path(path))
    monkeypatch.setattr(bit,'anchored_native',lambda *a:{'QueryBody':str(body),
        'InputSHA256':{str(body):bit.sha(body)},'Artifacts':{'native.rtr':bit.sha(native_report)}})
    return request,paths,anchors


@pytest.mark.parametrize('mutation',('application_candidate','export_build','cdc_candidate','cdc_negative','cdc_missing',
    'cdc_empty_receipts','cdc_unbound_record','io_build','io_export'))
def test_reused_audits_reject_cross_candidate_chain_or_bad_case(reused,mutation):
    request,paths,anchors=reused
    bit.reuse_completed(request,paths,{},None,anchors)
    key={'application_candidate':'ResetApplicationReceipt','export_build':'ResetApplicationReceipt',
        'cdc_candidate':'FinalCDCProof','cdc_negative':'FinalCDCProof','cdc_missing':'FinalCDCProof',
        'cdc_empty_receipts':'FinalCDCProof','cdc_unbound_record':'FinalCDCProof',
        'io_build':'FinalIOProof','io_export':'FinalIOProof'}[mutation]
    value=bit.read(paths[key])
    if mutation=='application_candidate':value['ResultADFSHA256']='0'*64
    elif mutation=='export_build':value['BuildPlanSHA256']='0'*64
    elif mutation=='cdc_candidate':value['CandidateADF']['SHA256']='0'*64
    elif mutation=='cdc_negative':value['Records'][0]['SlackNS']=-0.1
    elif mutation=='cdc_missing':value['Records'].pop()
    elif mutation=='cdc_empty_receipts':value['NativeReceipts']=[]
    elif mutation=='cdc_unbound_record':value['Records'][0]['Report']='other-candidate.rtr'
    elif mutation=='io_build':value['BuildPlanSHA256']='0'*64
    else:value['ExportReceipt']['SHA256']='0'*64
    paths[key].write_text(json.dumps(value))
    with pytest.raises(ValueError):bit.reuse_completed(request,paths,{},None,anchors)
