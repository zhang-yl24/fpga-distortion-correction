"""CPU-only authority, provenance and native-gate rejection cases."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_bitstream as bit


@pytest.mark.parametrize('schema,expected',[
    ('camera720-calibrated-stats-final-inspection-v1','camera720_stats_final_inspect'),
])
def test_final_provider_uses_only_explicit_current_schemas(tmp_path,monkeypatch,schema,expected):
    path=tmp_path/'receipt.json';path.write_text(json.dumps({'Schema':schema}))
    monkeypatch.setattr(bit,'module',lambda name:name)
    assert bit.final_provider(path)==expected
    path.write_text(json.dumps({'Schema':'camera720-current-raw-inspection-v1'}))
    with pytest.raises(ValueError,match='unsupported final'):bit.final_provider(path)


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
        'CAMERA720_CALIBRATED_STATS_GATE_PASS '+'a'*64,'Process "Generate Bitstream" started.',
        'Process "Generate Bitstream" done.',bit.COMPLETE])


def test_stage_order_requires_fresh_report_gate_and_one_bit_generation():
    assert len(bit.events(event_log(),'a'*64))==6
    for text in (event_log().replace('a'*64,'b'*64),
                 event_log().replace('CAMERA720_CALIBRATED_STATS_GATE_PASS '+'a'*64,''),
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


def good_cdc():
    pins={'TopPortCount':129,'CAM2Pins':14,'DDRMemoryPins':71}
    pins.update({key:True for key in ('DeclarationAndSourceBuildMappingPassed','FinalFunctionalPortConnectionsPassed',
        'FinalFunctionalPadSiteMappingPassed','FinalNativeSiteMappingPassed','FinalNativeElectricalAttributesVerified')})
    ports={*(f'{c}_out[{i}]' for c in 'rgb' for i in range(8)),'hs_out','vs_out','de_out','pix_clk'}
    return {'Schema':'camera720-calibrated-stats-cdc-proof-v1','Target':bit.prep.TARGET,
        'CandidateADFSHA256':'a'*64,'ExportReceipt':{'Path':'final.json','SHA256':'b'*64},
        'ScopedDigitalChecksPassed':True,'Missing':[],'Violations':[],'ExpectedCases':2486,'ObservedCases':2486,
        'StatisticsDomain':{'ActualStatisticsFFs':444,'Clock':'ddrphy_sysclk',
            'AllStatisticsSequentialInputsSameCoreDomain':True,
            'NoStatisticsFeedbackToVideoRegistersOrOtherPads':True},
        'UART':{'Port':'uart_txd','Attributes':dict(LOC='C24',VCCIO='3.3',STANDARD='LVCMOS33',DRIVE='4',SLEW='SLOW'),
            'ActualNativeLaunches':['core_statistics/tx/CLK'],'NativeMaximumPaths':[
                {'Source':'core_statistics/tx/CLK','Corner':c} for c in ('slow','fast')],
            'ExpectedMaximumCases':2,'ObservedMaximumCases':2,'Missing':[],
            'LaunchCoverageComplete':True,'NativeElectricalParametersVerified':True,
            'ExternalACAccepted':False,'ReceiverSamplingBudgetSpecified':False},
        'Pins':pins,'NativeElectricalParameters':{'Passed':True,'Ports':129},
        'DVP':{'ReportedBudgetCoverageComplete':True,'ExpectedPortCornerKindCases':40,'CoveredCases':40,'MissingCases':[]},
        'TX':{'Vendor49CommandsIdentical':True,'NativeMaximumPaths':[
            {'Port':port,'Corner':corner,'DelayType':'max'} for port in sorted(ports) for corner in ('slow','fast')]}}


def test_complete_cdc_and_all_io_are_required_together():
    value=good_cdc();bit.cdc_flags(value,'a'*64,value['ExportReceipt'])


@pytest.mark.parametrize('path,bad',[
    (('Schema',),'camera720-current-raw-cdc-audit-v1'),(('Target',),'camera720_transport_top'),
    (('CandidateADFSHA256',),'c'*64),(('ExportReceipt',),{'Path':'stale.json','SHA256':'b'*64}),
    (('ScopedDigitalChecksPassed',),False),(('Missing',),['one']),(('Violations',),['delay']),
    (('ExpectedCases',),True),(('ExpectedCases',),0),(('ObservedCases',),2485),
    (('Pins','TopPortCount'),127),(('Pins','CAM2Pins'),13),(('Pins','DDRMemoryPins'),70),
    (('Pins','DeclarationAndSourceBuildMappingPassed'),False),(('Pins','FinalFunctionalPortConnectionsPassed'),False),
    (('Pins','FinalFunctionalPadSiteMappingPassed'),False),(('Pins','FinalNativeSiteMappingPassed'),False),
    (('Pins','FinalNativeElectricalAttributesVerified'),False),
    (('NativeElectricalParameters','Passed'),False),(('NativeElectricalParameters','Ports'),127),
    (('DVP','ReportedBudgetCoverageComplete'),False),(('DVP','ExpectedPortCornerKindCases'),39),
    (('DVP','CoveredCases'),39),(('DVP','MissingCases'),['one']),
    (('TX','Vendor49CommandsIdentical'),False),(('TX','NativeMaximumPaths'),[]),
])
def test_cdc_or_io_gap_rejects_bit_authority(path,bad):
    value=good_cdc();reference=deepcopy(value['ExportReceipt']);node=value
    for key in path[:-1]:node=node[key]
    node[path[-1]]=bad
    with pytest.raises(ValueError):bit.cdc_flags(value,'a'*64,reference)


def test_one_missing_fast_tx_path_cannot_hide_in_duplicate_count():
    value=good_cdc();paths=value['TX']['NativeMaximumPaths'];paths[-1]=dict(paths[0])
    assert len(paths)==56
    with pytest.raises(ValueError,match='HDMI'):bit.cdc_flags(value,'a'*64,value['ExportReceipt'])


@pytest.fixture
def authority(tmp_path,monkeypatch):
    project=tmp_path/'project';project.mkdir()
    monkeypatch.setattr(bit.prep,'PROJECT',project)
    monkeypatch.setattr(bit,'SELF',project/'validator.py')
    monkeypatch.setattr(bit,'PYTHON',project/'python.exe')
    def write(path,value):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value) if isinstance(value,dict) else value,encoding='utf-8')
        return path
    write(bit.SELF,'validator');write(bit.PYTHON,'runtime')
    paths={key:write(project/(key+'.json'),{}) for key in bit.REQUEST_FIELDS-{'Schema','Target'}}
    write(paths['BuildPlan'],{'Target':bit.prep.TARGET})
    write(paths['CandidateADF'],'native candidate')
    report=write(project/bit.REPORT,'timing report');exceptions=write(project/bit.EXCEPTIONS,'native exceptions')
    request={'Schema':bit.REQUEST_SCHEMA,'Target':bit.prep.TARGET,
             **{key:bit.binding(path) for key,path in paths.items()}}
    export={'SourceADFSHA256':bit.sha(paths['CandidateADF']),'SourceADF':str(paths['CandidateADF']),
            'BuildPlanSHA256':bit.sha(paths['BuildPlan']),'SourceReceipt':request['ResetApplicationReceipt'],
            'Artifacts':{bit.REPORT:bit.sha(report),bit.EXCEPTIONS:bit.sha(exceptions)}}
    write(paths['FinalInspectionReceipt'],export);request['FinalInspectionReceipt']=bit.binding(paths['FinalInspectionReceipt'])
    request_path=write(project/'request.json',request)
    leaf=write(project/'extra-bound-source.v','module source; endmodule')
    closure={str(path):bit.sha(path) for path in [*paths.values(),report,exceptions,request_path,leaf,bit.SELF,bit.PYTHON]}
    seed={'Schema':bit.AUTHORITY_SCHEMA,'Target':bit.prep.TARGET,'FullVerificationCompleted':True,'DiagnosticOnly':True,
        'ValidationMethod':{'Function':'camera720_stats_bitstream.audit_authority','Path':str(bit.SELF),'SHA256':bit.sha(bit.SELF)},
        'EDAExecuted':False,'HardwareAccessed':False,'HardwareReleaseAllowed':False,'ExternalACTimingAccepted':False,
        'OpticalCorrectionAccepted':False,'InputSHA256':closure,
        'ToolSHA256':{p:h for p,h in closure.items() if Path(p).suffix in ('.py','.exe')},
        'Request':bit.binding(request_path),'BuildPlan':request['BuildPlan'],'CandidateADF':request['CandidateADF'],
        'FinalReport':bit.binding(report),'FinalExceptions':bit.binding(exceptions)}
    path=project/'authority.json'
    def seal():write(path,seed);return bit.sha(path)
    return {'path':path,'seed':seed,'seal':seal,'leaf':leaf,'paths':paths,'request':request,'request_path':request_path,'write':write}


def test_completed_authority_rehashes_whole_closure_without_running_native(authority):
    a=authority;value=bit.bind_authority(a['path'],a['seal']())
    assert a['leaf'] in value['Watched']
    assert value['CandidateSHA256']==bit.sha(a['paths']['CandidateADF'])


def test_authority_detects_non_primary_source_drift(authority):
    a=authority;digest=a['seal']();a['leaf'].write_text('changed source')
    with pytest.raises(ValueError,match='closure drift'):bit.bind_authority(a['path'],digest)


def test_explicit_authority_sha_is_required_and_rechecked(authority):
    a=authority;a['seal']()
    for digest in ('','not-a-hash','0'*64):
        with pytest.raises(ValueError):bit.bind_authority(a['path'],digest)


@pytest.mark.parametrize('field,bad',[
    ('Schema','old-authority'),('Target','camera720_transport_top'),('FullVerificationCompleted',False),
    ('DiagnosticOnly',False),('HardwareAccessed',True),('OpticalCorrectionAccepted',True),
    ('InputSHA256',{}),('ToolSHA256',{}),
])
def test_authority_shape_or_authority_expansion_rejected(authority,field,bad):
    a=authority;a['seed'][field]=bad
    with pytest.raises(ValueError):bit.bind_authority(a['path'],a['seal']())


def test_authority_cannot_omit_one_request_evidence_from_closure(authority):
    a=authority;a['seed']['InputSHA256'].pop(str(a['paths']['SystemSimulation']))
    with pytest.raises(ValueError,match='omitted'):bit.bind_authority(a['path'],a['seal']())


def test_request_extra_field_rejected_even_with_updated_hash(authority):
    a=authority;a['request']['ExtraCommand']='program hardware';a['write'](a['request_path'],a['request'])
    a['seed']['Request']=bit.binding(a['request_path']);a['seed']['InputSHA256'][str(a['request_path'])]=bit.sha(a['request_path'])
    with pytest.raises(ValueError,match='sealed request'):bit.bind_authority(a['path'],a['seal']())




@pytest.mark.parametrize('field,value',[
    ('StatisticsDomain',{}),('UART',{}),
])
def test_statistics_and_uart_are_not_inherited_from_video_only_proof(field,value):
    proof=good_cdc();proof[field]=value
    with pytest.raises(ValueError):bit.cdc_flags(proof,'a'*64,proof['ExportReceipt'])


def test_uart_duplicate_corner_cannot_hide_missing_fast_launch():
    proof=good_cdc();proof['UART']['NativeMaximumPaths'][1]=dict(proof['UART']['NativeMaximumPaths'][0])
    with pytest.raises(ValueError,match='both corners'):bit.cdc_flags(proof,'a'*64,proof['ExportReceipt'])


def test_statistics_feedback_rejected():
    proof=good_cdc();proof['StatisticsDomain']['NoStatisticsFeedbackToVideoRegistersOrOtherPads']=False
    with pytest.raises(ValueError,match='nonfeedback'):bit.cdc_flags(proof,'a'*64,proof['ExportReceipt'])
