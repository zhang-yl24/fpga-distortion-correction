"""Current raw release gates reject incomplete/mismatched evidence before EDA."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_raw_bitstream as bit
import camera720_raw_program as program


def test_target_matches_capture_provider_and_full_raw_contract():
    import camera720_capture as capture
    assert bit.prep.TARGET == capture.TARGET == program.prep.TARGET
    assert bit.CONTRACT == capture.CONTRACT
    assert capture.providers() == (bit,program)


def test_bit_header_rejects_old_transport_and_truncated_payload():
    prefix=bytes.fromhex('00090ff00ff00ff00ff000')+b'PANGO MICROSYSTEMS, INC.\0\1'
    def build(name):
        data=prefix
        for tag,value in zip(b'abcdef',(name,'Logos2-PG2L100H--6-FBG676','11/01/26','18:00:00','Fabric Compiler','2023.2-SP3<154097>')):
            text=value.encode()+b'\0';data+=bytes([tag])+len(text).to_bytes(2,'big')+text
        return data+b'ghi'+b'\xff'*1000001
    assert bit.bit_header(build(bit.prep.TARGET))['Design']==bit.prep.TARGET
    with pytest.raises(ValueError):bit.bit_header(build('camera720_transport_top'))
    with pytest.raises(ValueError):bit.bit_header(build(bit.prep.TARGET)[:200])


def test_gate_stage_order_is_mandatory():
    h='a'*64
    lines=['Process "Report Timing" started.','Process "Report Timing" done.',
           'CAMERA720_CURRENT_RAW_GATE_PASS '+h,'Process "Generate Bitstream" started.',
           'Process "Generate Bitstream" done.',bit.COMPLETE]
    assert len(bit.events('\n'.join(lines),h))==6
    for i in range(len(lines)):
        with pytest.raises(ValueError):bit.events('\n'.join(lines[:i]+lines[i+1:]),h)
    with pytest.raises(ValueError):bit.events('\n'.join(lines),'b'*64)


def test_cdc_missing_wrong_candidate_and_counts_fail():
    reference={'Path':'final','SHA256':'a'*64}
    row={'Schema':'camera720-current-raw-cdc-audit-v1','Target':bit.prep.TARGET,
         'FinalCandidateADFSHA256':'b'*64,'ExportReceipt':reference,'ScopedDigitalChecksPassed':True,
         'Missing':[],'Violations':[],'ExpectedCases':10,'ObservedCases':10}
    row.update(Pins={'TopPortCount':128,'CAM2Pins':14,'DDRMemoryPins':71,
        **{k:True for k in ('DeclarationAndSourceBuildMappingPassed','FinalFunctionalPortConnectionsPassed',
            'FinalFunctionalPadSiteMappingPassed','FinalNativeSiteMappingPassed','FinalNativeElectricalAttributesVerified')}},
        NativeElectricalParameters={'Passed':True,'Ports':128},
        DVP={'ReportedBudgetCoverageComplete':True,'ExpectedPortCornerKindCases':40,'CoveredCases':40,'MissingCases':[]},
        TX={'Vendor49CommandsIdentical':True,'NativeMaximumPaths':[{'Port':p,'Corner':c,'DelayType':'max'}
            for p in {*(f'{color}_out[{i}]' for color in 'rgb' for i in range(8)),
                      'hs_out','vs_out','de_out','pix_clk'} for c in ('slow','fast')]})
    bit.cdc_flags(row,'b'*64,reference)
    for key,value in [('Missing',['case']),('Violations',['late']),('ObservedCases',9),
                      ('ExpectedCases',0),('Target','camera720_transport_top'),('ScopedDigitalChecksPassed',False)]:
        with pytest.raises(ValueError):bit.cdc_flags({**row,key:value},'b'*64,reference)
    for key in ('Pins','NativeElectricalParameters','DVP','TX'):
        with pytest.raises(ValueError):bit.cdc_flags({**row,key:{}},'b'*64,reference)
    incomplete={**row['TX'],'NativeMaximumPaths':row['TX']['NativeMaximumPaths'][:-1]}
    with pytest.raises(ValueError):bit.cdc_flags({**row,'TX':incomplete},'b'*64,reference)


def test_reset_waiver_cannot_hide_data_or_modify_routes():
    row={'Target':bit.prep.TARGET,'CandidateADFSHA256':'b'*64,
         'RouteComparison':{'RoutingUnchanged':True,'ChangedNets':[]}}
    keys=('AuditPassed','ExactResetExceptionUnionVerified','NoDataFalsePaths','FunctionalGraphIdentical',
          'AllFFPlacementsIdentical','ClockDefinitionsAndLoadsUnchanged','AllInternalChecksMet',
          'DataTimingChecksPreserved','VendorSameConfigurationVerified')
    row.update({k:True for k in keys});bit.reset_flags(row,'b'*64)
    for key in keys:
        with pytest.raises(ValueError):bit.reset_flags({**row,key:False},'b'*64)
    with pytest.raises(ValueError):bit.reset_flags({**row,'RouteComparison':{'RoutingUnchanged':True,'ChangedNets':['_N46']}},'b'*64)


def test_all_ten_native_tables_required(monkeypatch):
    tables={(c,k):{'pair':{'FailingChecks':0,'WorstSlackNS':0.02,'TotalNegativeSlackNS':0}}
            for c in ('slow','fast') for k in ('setup','hold','recovery','removal','mpw')}
    monkeypatch.setattr(bit.timing,'summaries',lambda p:(tables,{'clock':'declared'}))
    bit.passed_tables('unused')
    tables[('fast','recovery')]['pair']['FailingChecks']=1
    with pytest.raises(ValueError):bit.passed_tables('unused')
    tables.pop(('fast','recovery'))
    with pytest.raises(ValueError):bit.passed_tables('unused')


def test_authority_requires_explicit_digest():
    with pytest.raises(ValueError):bit.bind_authority('unused',None)


def test_changed_audit_cannot_be_replaced_by_flags():
    bit.same_saved({'Data':[1],'CreatedUTC':'old','InputSHA256':{}},{'Data':[1],'CreatedUTC':'new','InputSHA256':{}})
    with pytest.raises(ValueError):bit.same_saved({'Data':[1]},{'Data':[2]})


def test_program_scripts_only_scan_and_sram():
    p=bit.prep.WORK/('bit-test/generate_bitstream/'+bit.prep.TARGET+'.sbit')
    scripts=program.scripts(p)
    assert set(scripts)=={'scan','program'} and p.as_posix() in scripts['program']
    assert all('flash' not in s.lower() for s in scripts.values())


@pytest.mark.parametrize('powered,notified,timeout',[(False,True,90),(True,False,90),(True,True,0),
    (True,True,301),(True,True,float('nan')),(True,True,float('inf')),(True,True,True)])
def test_program_invalid_authorization_rejected_before_validation(monkeypatch,powered,notified,timeout):
    monkeypatch.setattr(program,'validate',lambda *a:pytest.fail('validation must not run'))
    with pytest.raises(ValueError):program.execute('unused',board_powered=powered,user_notified=notified,timeout=timeout)


def test_current_authorization_reusable():
    program.execution_authorization(True,True,90)


def test_critical_sta_diagnostic_blocks_before_bit_gate(monkeypatch,tmp_path):
    monkeypatch.setattr(bit,'validate',lambda p:({},{}))
    monkeypatch.setattr(bit.inspect,'scan_diagnostics',lambda p:['C:STA-3006 invalid path'])
    monkeypatch.setattr(bit,'compare_native',lambda *a:pytest.fail('timing comparison must not mask a critical log'))
    with pytest.raises(ValueError,match='before bit generation'):bit.gate(tmp_path)
