"""Release joins reject incomplete launch coverage and broadened provenance."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_bitstream as bit
import camera720_cdc_native as native


def test_launch_producer_cannot_impersonate_old_schema_or_omit_binding():
    value={'Schema':native.COVERAGE_SCHEMA,'Producer':bit.binding(native.SELF)}
    assert bit.audit_module(value,'cdc') is native
    for changed in ({**value,'Schema':'camera720-cdc-native-coverage-v1'},
                    {**value,'Producer':{**value['Producer'],'SHA256':'0'*64}},
                    {'Plan':{}},{'EndpointInventory':{}},{'Producer':None}):
        with pytest.raises(ValueError):bit.audit_module(changed,'cdc')


def test_only_one_exact_canonical_manual_digest_extends_external_scope(tmp_path,monkeypatch):
    project=tmp_path/'repository'/'distortion';project.mkdir(parents=True)
    monkeypatch.setattr(bit.prep,'PROJECT',project)
    manual=tmp_path/'vendor'/'guide.pdf';manual.parent.mkdir();manual.write_bytes(b'approved document')
    monkeypatch.setattr(bit,'NATIVE_MANUAL',manual)
    monkeypatch.setattr(bit,'NATIVE_MANUAL_SHA',bit.sha(manual))
    watched={};bit.add(watched,manual,bit.sha(manual))
    assert watched=={manual:bit.sha(manual)}
    other=manual.with_name('unapproved.pdf');other.write_bytes(manual.read_bytes())
    for path,digest in ((manual,None),(manual,'0'*64),(other,bit.sha(other)),
                        (manual.parent/'..'/'vendor'/'guide.pdf',bit.sha(manual))):
        with pytest.raises(ValueError):bit.add({},path,digest)
    bit.rehash_inputs({'InputSHA256':{str(manual):bit.sha(manual)}},{})
    manual.write_bytes(b'changed document')
    with pytest.raises(ValueError):bit.add({},manual,bit.NATIVE_MANUAL_SHA)


@pytest.fixture
def launch_case(tmp_path,monkeypatch):
    def put(name,value):
        path=tmp_path/name;path.write_text(json.dumps(value),encoding='utf-8');return path
    candidate={'Path':str(tmp_path/'candidate.adf'),'SHA256':'a'*64}
    application={'Path':str(tmp_path/'application.json'),'SHA256':'b'*64}
    export=put('export.json',{'Command':['pds.exe'],'SourceReceipt':application})
    seed=put('seed.json',{})
    original=put('original.json',{})
    report=tmp_path/'original.rtr';report.write_text('receipt-bound native report')
    extra_report=tmp_path/'supplement.rtr';extra_report.write_text('receipt-bound supplemental report')
    supplemental_receipt=put('supplement.json',{'SourceReceipt':application})
    constraints={'RelevantStatements':[
        {'Line':811,'Text':'set_max_delay -datapath_only -from [get_clocks {a}] -to [get_clocks {b}] 8.0'},
        {'Line':812,'Text':'set_min_delay -from [get_clocks {a}] -to [get_clocks {b}] 0.0'}],
        'PeriodsNS':{'a':20.833,'b':37.037}}
    relationship={'SourceNativeClockPin':'src/CLK','SourceNativeOutputPin':'src/L5Q',
        'SourceClock':'a','DestinationClock':'b','NativeBoundaries':[{'Endpoint':'dst/I2'}]}
    query={'Source':'src/CLK','LaunchOutput':'src/L5Q','Endpoint':'dst/I2','LogicalRelationships':[0],
        'Requirements':{'CheckKinds':['max-delay','min-delay'],'Corners':['slow','fast'],
            'SourceClock':'a','DestinationClock':'b','MaximumNS':8.0,'MinimumNS':0.0,'SourcePeriodNS':20.833}}
    inventory={'Schema':'camera720-native-endpoints-v1','CandidateADF':candidate,'BuildPlanSHA256':'c'*64,
        'ExportReceipt':bit.binding(export),'MappingPassed':True,'NativeTimingAccepted':False,
        'LogicalRelationships':[relationship],'Queries':[query],'SameBLEInterstageInventory':[{'label':'same BLE'}],
        'InputSHA256':{str(native.mapping_tool.SELF):bit.sha(native.mapping_tool.SELF),str(original):bit.sha(original)}}
    inventory_path=put('inventory.json',inventory)
    supplement_query=deepcopy(query);supplement_query.update(LaunchOutput='src/L6Q',Endpoint='dst/I3',
        Requirements={'Clock':'a','CheckKinds':['setup','hold'],'Corners':['slow','fast']})
    supplement_row=deepcopy(relationship);supplement_row.update(SourceNativeOutputPin='src/L6Q',
        DestinationClock='a',NativeBoundaries=[{'Endpoint':'dst/I3'}])
    supplement={'Schema':'camera720-sameble-supplement-v1','Producer':bit.binding(native.sameble.SELF),
        'Mapper':bit.binding(native.mapping_tool.SELF),'CandidateADF':candidate,'BuildPlanSHA256':'c'*64,
        'LogicalRelationships':[supplement_row],'Queries':[supplement_query],
        'StructuralClassificationPassed':True,'NativeTimingAccepted':False,'HardwareReleaseAllowed':False}
    augmented=deepcopy(inventory);augmented['LogicalRelationships'].append(supplement_row)
    q=deepcopy(supplement_query);q['LogicalRelationships']=[1];augmented['Queries'].append(q)
    queries=native.normalize_queries(augmented,constraints)
    initial=native.coverage(queries,[],[])
    groups=native.groups_for(queries,initial['MissingCases'],64);bodies=native.query_bodies(groups,3)
    plan={'Schema':native.SCHEMA,'Target':bit.prep.TARGET,'Producer':bit.binding(native.SELF),
        'Policy':native.policy_reference(),'CoverageAssumedFromGrouping':False,'EDAExecuted':False,
        'HardwareAccessed':False,'TimingAccepted':False,'HardwareReleaseAllowed':False,
        'EndpointInventory':bit.binding(inventory_path),'OriginalBatchPlan':bit.binding(original),
        'InspectionSeed':bit.binding(seed),'CandidateADF':candidate,'BuildPlanSHA256':'c'*64,
        'SameBLESupplement':supplement,'SupplementalProducer':bit.binding(native.sameble.SELF),
        'SupplementalLogicalRelationshipOffset':1,'Queries':queries,'InitialEvidence':[bit.binding(export)],
        'InitialCoverage':initial,'InitialReports':[bit.binding(report)],'ExcludedInitialReports':[],
        'MaximumExpectedIdentitiesPerGroup':64,'MaximumTimingCommandsPerBody':3,'Groups':groups,
        'QueryBodies':{n:hashlib.sha256(t.encode('ascii')).hexdigest() for n,t in bodies.items()}}
    for name,body in bodies.items():(tmp_path/name).write_text(body,encoding='ascii')
    plan['InputSHA256']={str(bit.NATIVE_MANUAL):bit.NATIVE_MANUAL_SHA}
    for item in (plan['OriginalBatchPlan'],plan['EndpointInventory'],plan['InspectionSeed'],bit.binding(export),
                 plan['Producer'],plan['SupplementalProducer'],bit.binding(native.mapping_tool.SELF)):
        plan['InputSHA256'][item['Path']]=item['SHA256']
    plan_path=put('plan.json',plan)
    old={'ExportReceipt':bit.binding(export),'CandidateADF':candidate,'BuildPlanSHA256':'c'*64,'Constraints':constraints}
    rows=[]
    for q in queries:
        for corner in q['Corners']:
            for kind in q['CheckKinds']:
                r={k:q[k] for k in native.IDENTITY}
                r.update(Corner=corner,Kind=kind,SlackNS=0.1,ArrivalNS=2.0,Report=str(report),ReportLine=1,
                    PathSHA256='d'*64,Launch={'LaunchOutput':q['LaunchOutput']},HoldAnalysisSuppressed='Clock' not in q)
                if 'Clock' in q:r['Clock']=q['Clock']
                else:r.update(BoundNS=8.0,MinDelayNotAccepted=True)
                rows.append(r)
    inventory['SameBLESupplement']=supplement
    value=native.output_value(old,inventory,queries,rows,[],[])
    value.update(Plan=bit.binding(plan_path),EndpointInventory=plan['EndpointInventory'],
        OriginalBatchPlan=plan['OriginalBatchPlan'],InspectionSeed=plan['InspectionSeed'],
        NativeReceipts=[bit.binding(export),bit.binding(supplemental_receipt)],ExcludedReports=[],
        InvalidPins=[],RemainingGroups=[],RemainingBodies={},
        InputSHA256={str(plan_path):bit.sha(plan_path),str(export):bit.sha(export),
            str(supplemental_receipt):bit.sha(supplemental_receipt),str(report):bit.sha(report),str(extra_report):bit.sha(extra_report)})
    monkeypatch.setattr(bit,'rehash_inputs',lambda *a:None)
    monkeypatch.setattr(bit,'merge',lambda *a:None)
    monkeypatch.setattr(bit,'ref',lambda value,*a:Path(value['Path']))
    monkeypatch.setattr(bit,'add',lambda watched,path,*a,**k:Path(path))
    monkeypatch.setattr(bit.inspect,'canonical',lambda path,*a:Path(path))
    monkeypatch.setattr(native.grouped,'bind_original',lambda *a:old)
    context=('bound seed','bound native plan',{})
    monkeypatch.setattr(native.grouped,'bind_seed',lambda *a:context)
    calls=[]
    def bind_reports(receipts,*args,**kwargs):
        calls.append((receipts,args,kwargs))
        if receipts==plan['InitialEvidence']:return [report],receipts,[],[]
        return [extra_report],receipts,[],[]
    monkeypatch.setattr(native,'bind_reports',bind_reports)
    return value,plan,plan_path,export,application,calls


def test_actual_launch_contract_requires_two_crossing_and_four_ordinary_cases(launch_case):
    value,plan,_,export,app,calls=launch_case
    bit.cdc_flags(value,plan['CandidateADF'])
    assert bit.reuse_launch_cdc(value,export,{},app)==plan
    assert value['ExpectedCases']==6 and len(calls)==2
    assert calls[0][2]['initial_commands']==[native.timing_command('src/CLK','dst/I3')]
    assert calls[1][1][-1]==plan['Groups']


@pytest.mark.parametrize('key',('Complete','EnumeratedPathsTimingPassed','HoldAnalysisSuppressedForDatapathOnly','MinDelayNotAccepted'))
def test_launch_flags_reject_incomplete_or_changed_native_policy(launch_case,key):
    value,plan,*_=launch_case;value[key]=False
    with pytest.raises(ValueError):bit.cdc_flags(value,plan['CandidateADF'])


@pytest.mark.parametrize('key',('NativeSiteMappingVerified','NativeElectricalSettingsVerified','SameBLEInternalTimingAccepted',
    'TimingAccepted','HardwareReleaseAllowed','HardwareAccessed','EDAExecuted'))
def test_launch_flags_do_not_overclaim_independent_checks(launch_case,key):
    value,plan,*_=launch_case;value[key]=True
    with pytest.raises(ValueError):bit.cdc_flags(value,plan['CandidateADF'])


@pytest.mark.parametrize('mutation',('launch','missing_hold','negative','unbound_report','wrong_clock','minimum',
    'changed_bound','suppression','tco','reordered_receipts','duplicate_receipts','policy','plan_sha_closure','offset'))
def test_reviewed_launch_faults_are_rejected(launch_case,mutation):
    value,plan,path,export,app,_=launch_case
    if mutation=='launch':value['Records'][0]['LaunchOutput']='src/L4Q'
    elif mutation=='missing_hold':value['Records']=[r for r in value['Records'] if r['Kind']!='hold']
    elif mutation=='negative':value['Records'][0]['SlackNS']=-0.1
    elif mutation=='unbound_report':value['Records'][0]['Report']='unbound.rtr'
    elif mutation=='wrong_clock':next(r for r in value['Records'] if 'Clock' in r)['Clock']='b'
    elif mutation=='minimum':value['Records'][0]['Kind']='min-delay'
    elif mutation=='changed_bound':value['Records'][0]['BoundNS']=9.0
    elif mutation=='suppression':value['Records'][0]['HoldAnalysisSuppressed']=False
    elif mutation=='tco':value['Records'][0]['Launch']['LaunchOutput']='src/L6Q'
    elif mutation=='reordered_receipts':value['NativeReceipts'].reverse()
    elif mutation=='duplicate_receipts':value['NativeReceipts'].append(value['NativeReceipts'][1])
    elif mutation=='policy':value['Policy']={**value['Policy'],'SHA256':'0'*64}
    elif mutation=='plan_sha_closure':value['InputSHA256'][str(path)]='0'*64
    else:value['SupplementalLogicalRelationshipOffset']=0
    with pytest.raises(ValueError):bit.reuse_launch_cdc(value,export,{},app)


def test_full_launch_recompute_uses_exact_plan_hash_and_only_new_receipts(launch_case,monkeypatch):
    value,plan,_,export,_,_=launch_case;calls=[]
    def audit(path,digest,receipts):
        calls.append((path,digest,receipts));return deepcopy(value),{},{}
    monkeypatch.setattr(native,'audit_value',audit)
    assert bit.recompute_cdc(value,export,{})==plan
    assert calls==[(value['Plan']['Path'],value['Plan']['SHA256'],value['NativeReceipts'][1:])]
    monkeypatch.setattr(native,'audit_value',lambda *a:(deepcopy(value),{}, {'missing.tcl':'query'}))
    with pytest.raises(ValueError,match='supplemental'):bit.recompute_cdc(value,export,{})
