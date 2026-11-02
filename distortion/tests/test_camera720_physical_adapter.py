"""Complete physical STA coverage is required; boundary inventory alone fails."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_bitstream as bit
import camera720_cdc_clm_native as physical
from test_camera720_cdc_native import query,parsed


@pytest.fixture
def physical_case(tmp_path,monkeypatch):
    def put(name,value):
        p=tmp_path/name;p.write_text(json.dumps(value));return p
    candidate={'Path':str(tmp_path/'candidate.adf'),'SHA256':'a'*64}
    export=put('export.json',{'Command':['unused-pds']})
    q=query();rows=[parsed(q,c) for c in q['Corners']]
    q['LogicalRelationships']=[0]
    oq=query(False);oq.update(Source='ordinary/CLK',LaunchOutput='ordinary/L5Q',Endpoint='ordinary_dst/I2',LogicalRelationships=[1])
    rows.extend(parsed(oq,c,k) for c in oq['Corners'] for k in oq['CheckKinds'])
    queries=[q,oq]
    value=physical.summary(queries,rows,[])
    plan={'Schema':physical.SCHEMA,'Producer':bit.binding(physical.SELF),'Target':bit.prep.TARGET,
        'CandidateADF':candidate,'BuildPlanSHA256':'b'*64,'OriginalBatchPlan':{'Path':'original','SHA256':'c'*64},
        'InspectionSeed':{'Path':'seed','SHA256':'d'*64},'Queries':queries}
    plan_path=put('plan.json',plan)
    value.update(Schema=physical.COVERAGE,Target=bit.prep.TARGET,Producer=plan['Producer'],
        CandidateADF=candidate,BuildPlanSHA256='b'*64,ExportReceipt=bit.binding(export),Plan=bit.binding(plan_path),
        OriginalBatchPlan=plan['OriginalBatchPlan'],InspectionSeed=plan['InspectionSeed'],
        Policy=physical.old.policy_reference(),LogicalRelationshipsRetained=2,
        AllLogicalRelationshipsStructurallyRepresented=True,EDAExecuted=False,
        NativeReceipts=[{'Path':'completed-receipt.json','SHA256':'e'*64}],
        NativeSTAContext={'Engine':'PDS 2023.2-SP3 build154097','Scope':'Native physical sequential endpoints',
            'ActualTcoRequired':True,'CriticalDiagnosticsRejected':True,'IndividualFFArcsEnumerated':False,
            'SharedClockAliasUsedAsCaptureFFProof':False},
        InputSHA256={str(plan_path):bit.sha(plan_path)})
    monkeypatch.setattr(bit,'ref',lambda item,*a:Path(item['Path']))
    monkeypatch.setattr(bit,'rehash_inputs',lambda *a:None)
    monkeypatch.setattr(bit,'merge',lambda *a:None)
    return value,plan,plan_path,export


def test_explicit_physical_producer_and_complete_diagnostic_scope(physical_case):
    value,plan,_,_=physical_case
    assert bit.audit_module(value,'cdc') is physical
    bit.cdc_flags(value,plan['CandidateADF'])
    changed={**value,'Schema':bit.LAUNCH_COVERAGE_SCHEMA}
    with pytest.raises(ValueError):bit.audit_module(changed,'cdc')
    changed={**value,'Producer':{**value['Producer'],'SHA256':'0'*64}}
    with pytest.raises(ValueError):bit.audit_module(changed,'cdc')


@pytest.mark.parametrize('key',('Complete','EnumeratedPathsTimingPassed','PhysicalCoverageComplete',
    'PhysicalBoundaryCoverageComplete','PhysicalBoundaryChecksPassed','AllLogicalRelationshipsStructurallyRepresented'))
def test_partial_or_boundary_only_claim_cannot_authorize(physical_case,key):
    value,plan,_,_=physical_case;value[key]=False
    with pytest.raises(ValueError):bit.cdc_flags(value,plan['CandidateADF'])


@pytest.mark.parametrize('key',('IndividualFFArcsEnumerated','PhysicalTimingAggregationProved','LogicalFFTimingAccepted',
    'TimingAccepted','NativeTimingAccepted','HardwareReleaseAllowed','HardwareAccessed','EDAExecuted'))
def test_unproved_scope_flags_are_never_inferred(physical_case,key):
    value,plan,_,_=physical_case;value[key]=True
    with pytest.raises(ValueError):bit.cdc_flags(value,plan['CandidateADF'])


@pytest.mark.parametrize('mutation',('wrong_candidate','wrong_policy','missing_case','missing_ordinary',
    'count','zero_ordinary','zero_logical','clock_alias','no_tco','critical_warning_allowed'))
def test_physical_gate_rejects_incomplete_or_changed_evidence(physical_case,mutation):
    value,plan,_,_=physical_case
    candidate=deepcopy(plan['CandidateADF'])
    if mutation=='wrong_candidate':value['CandidateADF']={'Path':'other','SHA256':'0'*64}
    elif mutation=='wrong_policy':value['Policy']={}
    elif mutation=='missing_case':value['MissingCases']=[{'Corner':'fast'}]
    elif mutation=='missing_ordinary':value['OrdinaryMissingCases']=[{'Kind':'hold'}]
    elif mutation=='count':value['CoveredCases']-=1
    elif mutation=='zero_ordinary':value['OrdinaryCoveredCases']=0
    elif mutation=='zero_logical':value['LogicalRelationshipsRetained']=0
    elif mutation=='clock_alias':value['NativeSTAContext']['SharedClockAliasUsedAsCaptureFFProof']=True
    elif mutation=='no_tco':value['NativeSTAContext']['ActualTcoRequired']=False
    else:value['NativeSTAContext']['CriticalDiagnosticsRejected']=False
    with pytest.raises(ValueError):bit.cdc_flags(value,candidate)


def test_adapter_recomputes_full_actual_collector_before_vendor_basis(physical_case,monkeypatch):
    value,plan,_,export=physical_case;calls=[]
    def audit(path,digest,receipts):
        calls.append(('audit',path,digest,receipts));return deepcopy(value),{}
    monkeypatch.setattr(physical,'audit_value',audit)
    monkeypatch.setattr(bit,'physical_sta_basis',lambda *a:calls.append(('basis',)))
    assert bit.recompute_cdc(value,export,{})==plan
    assert calls==[('audit',value['Plan']['Path'],value['Plan']['SHA256'],value['NativeReceipts']),('basis',)]


@pytest.mark.parametrize('mutation',('record_removed','mapping_changed','partial_result','producer_drift','export_drift','plan_missing'))
def test_recompute_cannot_be_replaced_by_saved_pass_flags(physical_case,monkeypatch,mutation):
    value,_,path,export=physical_case;actual=deepcopy(value)
    if mutation=='record_removed':actual['Records'].pop()
    elif mutation=='mapping_changed':actual['AllLogicalRelationshipsStructurallyRepresented']=False
    elif mutation=='partial_result':actual['PhysicalCoverageComplete']=False
    elif mutation=='producer_drift':value['Producer']['SHA256']='0'*64
    elif mutation=='export_drift':value['ExportReceipt']['SHA256']='0'*64
    else:value['InputSHA256'].pop(str(path))
    monkeypatch.setattr(physical,'audit_value',lambda *a:(actual,{}))
    monkeypatch.setattr(bit,'physical_sta_basis',lambda *a:pytest.fail('basis reached after invalid recomputation'))
    with pytest.raises(ValueError):bit.recompute_physical_cdc(value,export,{})


def test_additional_vendor_documents_remain_exact_single_files(tmp_path,monkeypatch):
    project=tmp_path/'repo'/'distortion';project.mkdir(parents=True)
    monkeypatch.setattr(bit.prep,'PROJECT',project)
    approved=tmp_path/'external'/'tcl.pdf';approved.parent.mkdir();approved.write_bytes(b'fixed manual')
    monkeypatch.setattr(bit,'CLM_DOCUMENTS',{approved:bit.sha(approved)})
    inputs={};bit.add(inputs,approved,bit.sha(approved));assert inputs=={approved:bit.sha(approved)}
    sibling=approved.with_name('other.pdf');sibling.write_bytes(approved.read_bytes())
    for path,digest in ((approved,None),(approved,'0'*64),(sibling,bit.sha(sibling)),
                        (approved.parent/'..'/'external'/'tcl.pdf',bit.sha(approved))):
        with pytest.raises(ValueError):bit.add({},path,digest)
