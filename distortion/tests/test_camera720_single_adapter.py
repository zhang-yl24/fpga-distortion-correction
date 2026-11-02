"""Recovery reuses full physical verification without weakening parent provenance."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_bitstream as bit
import camera720_cdc_single as single
from test_camera720_physical_adapter import physical_case


@pytest.fixture
def recovery_case(physical_case,tmp_path,monkeypatch):
    value,parent,parent_path,export=physical_case
    monkeypatch.setattr(single.prep,'WORK',tmp_path)
    monkeypatch.setattr(single,'PARENT_PLAN',parent_path.name)
    monkeypatch.setattr(single,'PARENT_SHA',bit.sha(parent_path))
    recovery={'Schema':single.PLAN_SCHEMA,'Producer':bit.binding(single.SELF),
        'ParentPlan':bit.binding(parent_path),'ParentProducer':bit.binding(single.parent.SELF),
        'PreservedPartialReceipts':[single.parent.fixed(single.PARTIAL,single.PARTIAL_SHA)],
        'CandidateADF':parent['CandidateADF'],'BuildPlanSHA256':parent['BuildPlanSHA256'],
        'InspectionSeed':parent['InspectionSeed'],'Queries':parent['Queries']}
    path=tmp_path/'recovery.json';path.write_text(json.dumps(recovery))
    value.update(Schema=single.COVERAGE_SCHEMA,Producer=bit.binding(single.SELF),Plan=bit.binding(path),
        ParentPlan=recovery['ParentPlan'],ParentProducer=recovery['ParentProducer'],
        PreservedPartialReceipts=recovery['PreservedPartialReceipts'])
    value['InputSHA256'][str(path)]=bit.sha(path)
    return value,recovery,parent,path,export


def test_single_dispatch_preserves_complete_physical_policy(recovery_case):
    value,_,parent,_,_=recovery_case
    assert bit.audit_module(value,'cdc') is single
    bit.cdc_flags(value,parent['CandidateADF'])
    for schema in (bit.CLM_COVERAGE_SCHEMA,bit.LAUNCH_COVERAGE_SCHEMA):
        with pytest.raises(ValueError):bit.audit_module({**value,'Schema':schema},'cdc')


def test_single_full_audit_receives_recovery_plan_and_basis_receives_parent(recovery_case,monkeypatch):
    value,recovery,parent,_,export=recovery_case;calls=[]
    def audit(path,digest,receipts):
        calls.append(('audit',path,digest,receipts));return deepcopy(value),{}
    monkeypatch.setattr(single,'audit_value',audit)
    monkeypatch.setattr(bit,'physical_sta_basis',lambda v,p,*a:calls.append(('basis',p)))
    assert bit.recompute_cdc(value,export,{})==recovery
    assert calls==[('audit',value['Plan']['Path'],value['Plan']['SHA256'],value['NativeReceipts']),('basis',parent)]


@pytest.mark.parametrize('mutation',('parent_digest','parent_producer','partial_receipt','missing_parent_closure',
    'different_queries','parent_candidate','different_original','partial_coverage','changed_actual'))
def test_single_adapter_rejects_broken_parent_partial_or_actual_coverage(recovery_case,monkeypatch,mutation):
    value,recovery,parent,path,export=recovery_case;actual=deepcopy(value)
    if mutation=='parent_digest':value['ParentPlan']={**value['ParentPlan'],'SHA256':'0'*64}
    elif mutation=='parent_producer':value['ParentProducer']={**value['ParentProducer'],'SHA256':'0'*64}
    elif mutation=='partial_receipt':value['PreservedPartialReceipts']=[]
    elif mutation=='missing_parent_closure':value['InputSHA256'].pop(value['ParentPlan']['Path'])
    elif mutation=='different_queries':
        recovery['Queries']=[];path.write_text(json.dumps(recovery))
    elif mutation=='parent_candidate':value['CandidateADF']={**value['CandidateADF'],'SHA256':'0'*64}
    elif mutation=='different_original':value['OriginalBatchPlan']={}
    elif mutation=='partial_coverage':value['PhysicalCoverageComplete']=False
    else:actual['Records'].pop()
    monkeypatch.setattr(single,'audit_value',lambda *a:(actual,{}))
    monkeypatch.setattr(bit,'physical_sta_basis',lambda *a:pytest.fail('vendor basis reached after broken recovery chain'))
    with pytest.raises(ValueError):bit.recompute_physical_cdc(value,export,{})
