"""Reject wrong target bits and bypasses of upright native gate order."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera_vga_upright_bitstream as bit


def bitdata(target='camera_vga_upright_top'):
    out=bytes.fromhex('00090ff00ff00ff00ff000')+b'PANGO MICROSYSTEMS, INC.\0\1'
    for tag,value in zip(b'abcdef',[target,'Logos2-PG2L100H--6-FBG676','2026/10/31','12:34:56','Fabric Compiler','2023.2-SP3<154097>']):
        raw=value.encode()+b'\0';out+=bytes([tag])+len(raw).to_bytes(2,'big')+raw
    return out+b'ghi'+b'\xff'*1000001


def eventlog(digest):
    return '\n'.join(['Process "Report Timing" started.','Process "Report Timing" done.',
        'CAMERA_VGA_UPRIGHT_GATE_PASS '+digest,'Process "Generate Bitstream" started.',
        'Process "Generate Bitstream" done.',bit.COMPLETE])


def test_new_bit_header_accepts_only_upright_identity():
    assert bit.bit_header(bitdata())['Design']=='camera_vga_upright_top'
    with pytest.raises(ValueError,match='identity'):bit.bit_header(bitdata('camera_vga_output_top'))


@pytest.mark.parametrize('data',[b'invalid',bitdata()[:200],bitdata().replace(b'Logos2-PG2L100H--6-FBG676',b'Logos2-PG2L100H--5-FBG676')])
def test_header_rejects_truncation_wrong_device_and_prefix(data):
    with pytest.raises(ValueError):bit.bit_header(data)


def test_native_order_requires_gate_between_report_and_bit():
    digest='a'*64
    assert len(bit.events(eventlog(digest),digest))==6
    wrong=eventlog(digest).replace('CAMERA_VGA_UPRIGHT_GATE_PASS '+digest+'\n','')+'\nCAMERA_VGA_UPRIGHT_GATE_PASS '+digest
    with pytest.raises(ValueError,match='order'):bit.events(wrong,digest)


@pytest.mark.parametrize('change',[
    lambda t:t.replace('a'*64,'b'*64),
    lambda t:t.replace('Process "Report Timing" done.','Process "Synthesize" started.'),
    lambda t:t.replace('CAMERA_VGA_UPRIGHT_GATE_PASS '+'a'*64,'') ,
    lambda t:t+'\nProcess "Generate Bitstream" started.',
])
def test_wrong_marker_extra_stage_and_missing_gate_rejected(change):
    with pytest.raises(ValueError):bit.events(change(eventlog('a'*64)),'a'*64)


def test_recipe_uses_new_build_context_then_single_report_gate_and_bit():
    base=bit.prep.WORK/'pds-20261031-a'
    context={'PlanPath':base/'plan.json','CandidateSHA256':'a'*64}
    work=bit.prep.WORK/'bit-test-never-executed'
    text=bit.render(context,work)
    assert 'compile -top_module camera_vga_upright_top' in text
    assert text.count('report_timing -force_to_run')==1
    assert text.index('report_timing -force_to_run')<text.index('set checked [exec')<text.index('gen_bit_stream')
    assert text.count('gen_bit_stream')==1 and 'gen_netlist' not in text
    assert '-input_db_file {'+work.as_posix()+'/audited-final.adf}' in text
    for command in ('mpnr_report_timing','manual_route','set_false_path','cfg_program'):
        assert command not in text


def test_request_rejects_old_schema_without_touching_candidate(tmp_path,monkeypatch):
    p=tmp_path/'request.json';p.write_text(json.dumps({'Schema':'camera-vga-offline-bitstream-plan-v1'}))
    monkeypatch.setattr(bit,'add',lambda watched,path,*args,**kwargs:Path(path))
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
        bit.evidence({'InputSHA256':{'a':'a'*64},'ToolSHA256':{'other':'b'*64}}, {}, None)


def test_timing_gate_rejects_missing_tables_even_when_rows_pass(monkeypatch):
    monkeypatch.setattr(bit.timing,'summaries',lambda p:({('slow','setup'):{('a','b'):{'FailingChecks':0,'WorstSlackNS':0.1,'TotalNegativeSlackNS':0}}},['clock']))
    with pytest.raises(ValueError,match='all ten'):bit.passed_tables('not-opened')


def test_derived_export_requires_independent_binding_before_acceptance(tmp_path,monkeypatch):
    import types
    path=tmp_path/'result.json';path.write_text(json.dumps({'Schema':'camera-vga-upright-derived-inspection-v1'}))
    calls=[]
    value={'Target':bit.prep.TARGET,'Mode':'export','SourceADFSHA256':'a'*64,'BuildPlanSHA256':'b'*64}
    module=types.SimpleNamespace(__file__=__file__,bind_receipt=lambda p,w:(calls.append(p) or value))
    monkeypatch.setitem(sys.modules,'run_camera_vga_upright_derived_inspect',module)
    monkeypatch.setattr(bit,'add',lambda *args:None)
    assert bit.final_export(path,'a'*64,'b'*64,{})==value and calls==[path]
    value['Mode']='query'
    with pytest.raises(ValueError,match='identity'):bit.final_export(path,'a'*64,'b'*64,{})
