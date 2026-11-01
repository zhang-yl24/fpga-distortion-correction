"""Reject wrong target bits and bypasses of calibrated native gate order."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera_vga_calibrated_bitstream as bit


def bitdata(target='camera_vga_calibrated_top'):
    out=bytes.fromhex('00090ff00ff00ff00ff000')+b'PANGO MICROSYSTEMS, INC.\0\1'
    for tag,value in zip(b'abcdef',[target,'Logos2-PG2L100H--6-FBG676','2026/10/31','12:34:56','Fabric Compiler','2023.2-SP3<154097>']):
        raw=value.encode()+b'\0';out+=bytes([tag])+len(raw).to_bytes(2,'big')+raw
    return out+b'ghi'+b'\xff'*1000001


def eventlog(digest):
    return '\n'.join(['Process "Report Timing" started.','Process "Report Timing" done.',
        'CAMERA_VGA_CALIBRATED_GATE_PASS '+digest,'Process "Generate Bitstream" started.',
        'Process "Generate Bitstream" done.',bit.COMPLETE])


def test_new_bit_header_accepts_only_calibrated_identity():
    assert bit.bit_header(bitdata())['Design']=='camera_vga_calibrated_top'
    with pytest.raises(ValueError,match='identity'):bit.bit_header(bitdata('camera_vga_output_top'))


@pytest.mark.parametrize('data',[b'invalid',bitdata()[:200],bitdata().replace(b'Logos2-PG2L100H--6-FBG676',b'Logos2-PG2L100H--5-FBG676')])
def test_header_rejects_truncation_wrong_device_and_prefix(data):
    with pytest.raises(ValueError):bit.bit_header(data)


def test_native_order_requires_gate_between_report_and_bit():
    digest='a'*64
    assert len(bit.events(eventlog(digest),digest))==6
    wrong=eventlog(digest).replace('CAMERA_VGA_CALIBRATED_GATE_PASS '+digest+'\n','')+'\nCAMERA_VGA_CALIBRATED_GATE_PASS '+digest
    with pytest.raises(ValueError,match='order'):bit.events(wrong,digest)


@pytest.mark.parametrize('change',[
    lambda t:t.replace('a'*64,'b'*64),
    lambda t:t.replace('Process "Report Timing" done.','Process "Synthesize" started.'),
    lambda t:t.replace('CAMERA_VGA_CALIBRATED_GATE_PASS '+'a'*64,'') ,
    lambda t:t+'\nProcess "Generate Bitstream" started.',
])
def test_wrong_marker_extra_stage_and_missing_gate_rejected(change):
    with pytest.raises(ValueError):bit.events(change(eventlog('a'*64)),'a'*64)


def test_recipe_uses_new_build_context_then_single_report_gate_and_bit(monkeypatch):
    base=bit.prep.WORK/'cpu-bit-render-never-executed'
    _, _, source = bit.prep.recipe(base)
    original_read = Path.read_text
    monkeypatch.setattr(Path, 'read_text', lambda self, *a, **kw: source.decode('ascii') if self == base/'timing.tcl' else original_read(self, *a, **kw))
    context={'PlanPath':base/'plan.json','CandidateSHA256':'a'*64}
    work=bit.prep.WORK/'bit-test-never-executed'
    text=bit.render(context,work)
    assert 'compile -top_module camera_vga_calibrated_top' in text
    assert text.count('report_timing -force_to_run')==1
    assert text.index('report_timing -force_to_run')<text.index('set checked [exec')<text.index('gen_bit_stream')
    assert text.count('gen_bit_stream')==1 and 'gen_netlist' not in text
    assert '-input_db_file {'+work.as_posix()+'/audited-final.adf}' in text
    for command in ('mpnr_report_timing','manual_route','set_false_path','cfg_program'):
        assert command not in text


def test_request_rejects_old_schema_without_touching_candidate(tmp_path,monkeypatch):
    p=tmp_path/'request.json';p.write_text(json.dumps({'Schema':'camera-vga-offline-bitstream-plan-v1'}))
    monkeypatch.setattr(bit,'add',lambda watched,path,*args,**kwargs:Path(path))
    monkeypatch.setattr(bit.inspect,'canonical',lambda path,*args:Path(path))
    with pytest.raises(ValueError,match='schema'):bit.authority(p)


def test_binding_requires_exact_path_hash_pair():
    with pytest.raises(ValueError,match='Path/SHA256'):bit.ref({'Path':'anything','SHA256':'a'*64,'Passed':True},{})
    with pytest.raises(ValueError,match='Path/SHA256'):bit.ref({'Path':'anything','SHA256':'not-a-hash'},{})


@pytest.mark.parametrize('row',[
    {'FailingChecks':1,'WorstSlackNS':0.1,'TotalNegativeSlackNS':0},
    {'FailingChecks':0,'WorstSlackNS':-0.001,'TotalNegativeSlackNS':0},
    {'FailingChecks':0,'WorstSlackNS':0.1,'TotalNegativeSlackNS':-0.001},
])
def test_timing_gate_rejects_inconsistent_failing_summary(monkeypatch,row):
    tables={(c,k):{('a','b'):row} for c in ('slow','fast') for k in ('setup','hold','recovery','removal','mpw')}
    monkeypatch.setattr(bit.timing,'summaries',lambda p:(tables,['clock']))
    with pytest.raises(ValueError,match='must pass'):bit.passed_tables('not-opened')


def test_evidence_rejects_tools_missing_from_input_inventory(monkeypatch):
    monkeypatch.setattr(bit,'add',lambda *args,**kwargs:None)
    with pytest.raises(ValueError,match='not input-bound'):
        bit.rehash_inputs({'InputSHA256':{'a':'a'*64},'ToolSHA256':{'other':'b'*64}}, {}, None)


def test_timing_gate_rejects_missing_tables_even_when_rows_pass(monkeypatch):
    monkeypatch.setattr(bit.timing,'summaries',lambda p:({('slow','setup'):{('a','b'):{'FailingChecks':0,'WorstSlackNS':0.1,'TotalNegativeSlackNS':0}}},['clock']))
    with pytest.raises(ValueError,match='all ten'):bit.passed_tables('not-opened')


def valid_reset_claim():
    application = {'Schema':bit.physical.SCHEMA, 'Target':bit.prep.TARGET, 'Mode':'save-reset', 'ExecutionPassed':True}
    effect = {'Schema':bit.effect.SCHEMA, 'Target':bit.prep.TARGET, 'ChangedNets':[]}
    effect.update({k:True for k in ('AuditPassed','ResetEffectVerified','FunctionalGraphIdentical',
        'AllFFPlacementsIdentical','RoutingUnchanged','ExactResetExceptionUnionVerified','NoDataFalsePaths',
        'AllInternalChecksMet','ClockDefinitionsAndLoadsUnchanged','OtherExceptionsIdentical')})
    return application, effect


@pytest.mark.parametrize('mutation', ['old_schema','route_schema','route_field','request_field','incomplete','changed_route','data_false_path'])
def test_reset_authority_rejects_old_route_and_incomplete_claims(mutation):
    application, effect = valid_reset_claim()
    bit.reset_flags(application, effect)
    if mutation == 'old_schema':application['Schema']='camera-vga-upright-diagnostic-reset-application-v1'
    elif mutation == 'route_schema':application['Schema']='camera-vga-calibrated-route-reset-application-v1'
    elif mutation == 'route_field':application['Route']=None
    elif mutation == 'request_field':application['Request']=None
    elif mutation == 'incomplete':effect['AllInternalChecksMet']=False
    elif mutation == 'changed_route':effect['ChangedNets']=['_N199']
    else:effect['NoDataFalsePaths']=False
    with pytest.raises(ValueError):bit.reset_flags(application, effect)


def valid_io_claim():
    return {'Schema':bit.native_io.SCHEMA, 'Target':bit.prep.TARGET, 'StructuralAuditPassed':True,
        'NativeAuditPassed':True, 'CandidateADF':{'SHA256':'a'*64},
        'Scope':{'NativeInterstageTimingComplete':True,'GrayDatapathBoundComplete':True},
        'Pins':{'FinalNativeSiteMappingPassed':True,'FinalFunctionalPadSiteMappingPassed':True},
        'InputDelays':{'Passed':True,'NativeDelayCells':8,'AllPadConsumersTraverseTheirOwnDelay':True}}


@pytest.mark.parametrize('mutation', ['old_candidate','old_schema','missing_hold','missing_gray','missing_sites','missing_pad','missing_delay','delay_count','bypass'])
def test_io_gate_rejects_incomplete_or_wrong_native_evidence(mutation):
    p=valid_io_claim();bit.io_flags(p,'a'*64)
    if mutation=='old_candidate':p['CandidateADF']['SHA256']='b'*64
    elif mutation=='old_schema':p['Schema']='camera-vga-upright-io-cdc-native-v1'
    elif mutation=='missing_hold':p['Scope']['NativeInterstageTimingComplete']=False
    elif mutation=='missing_gray':p['Scope']['GrayDatapathBoundComplete']=False
    elif mutation=='missing_sites':p['Pins']['FinalNativeSiteMappingPassed']=False
    elif mutation=='missing_pad':p['Pins']['FinalFunctionalPadSiteMappingPassed']=False
    elif mutation=='missing_delay':p['InputDelays']={}
    elif mutation=='delay_count':p['InputDelays']['NativeDelayCells']=7
    else:p['InputDelays']['AllPadConsumersTraverseTheirOwnDelay']=False
    with pytest.raises(ValueError):bit.io_flags(p,'a'*64)


def test_query_recompute_requires_every_actual_timing_pair_and_site():
    plan={'Queries':[{'Source':'sync0/CLK','Endpoint':'sync1/D','Clock':'camera_pclk'}],
          'GrayCoverageQueries':[],'IOSites':['IO_1_2']}
    grouped,_=bit.native_io.batch_body(plan);bit.require_io_query_commands(grouped,plan)
    for body in (grouped.replace('show -dev_instance {IO_1_2}\n',''),
                 grouped.replace('sync1/D','old/D'),grouped+'save_adif\n'):
        with pytest.raises(ValueError):bit.require_io_query_commands(body,plan)


def test_cache_is_process_local_rehashed_and_cannot_be_mutated_by_returned_context(tmp_path,monkeypatch):
    request=tmp_path/'request.json';request.write_text('{}')
    evidence=tmp_path/'input.bin';evidence.write_bytes(b'original')
    key=str(request);value={'Build':{'nested':['stable']},'Watched':{request:bit.sha(request),evidence:bit.sha(evidence)}}
    monkeypatch.setattr(bit.inspect,'canonical',lambda p,*a:Path(p))
    monkeypatch.setattr(bit,'_AUTHORITY_CACHE',{key:value})
    result=bit.authority(request);result['Build']['nested'].append('changed');result['Watched'].clear()
    assert bit.authority(request)['Build']=={'nested':['stable']}
    evidence.write_bytes(b'mutated')
    with pytest.raises(ValueError,match='cached.*drift'):bit.authority(request)
