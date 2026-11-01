"""Pure parser checks; no EDA, physical candidate substitution or hardware."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import audit_camera_vga_calibrated_io_cdc as audit


def netlist(top='camera_vga_calibrated_top',site='CLMA_123_456'):
    return ('// PDS 2023.2-SP3<build 154097>\nmodule '+top+'\n(input clk);\n'
        'V_FFASYN /* '+site+' */ #(.INIT(1\'b0), .SET_RESET("RESET")) '
        '\\sync[0]/FF/FF (.CK(clk), .D(d), .Q(q), .SR(rst), .CE(1\'b1));\nendmodule\n')


def test_graph_accepts_actual_new_placement_and_count_without_old_inventory():
    g=audit.functional(netlist())
    assert len(g['Cells'])==len(g['FFPlacement'])==1
    assert g['FFPlacement']['sync[0]/FF/FF']['Site']=='CLMA_123_456'
    changed=audit.functional(netlist(site='CLMS_789_123'))
    assert changed['Cells']==g['Cells'] and changed['FFPlacement']!=g['FFPlacement']


@pytest.mark.parametrize('text',[
    netlist('camera_vga_output_top'),
    netlist()+'module extra(); endmodule\n',
    netlist().replace('/* CLMA_123_456 */',''),
    netlist().replace('2023.2-SP3<build 154097>','other version'),
    netlist().replace('endmodule',netlist().split('\n')[3]+'\nendmodule'),
])
def test_graph_rejects_wrong_identity_missing_placement_or_ambiguous_cells(text):
    with pytest.raises(ValueError):audit.functional(text)


def test_io_adapter_changes_only_module_declaration_and_records_both_text_hashes():
    original=netlist()
    adapted,proof=audit.io_syntax(original)
    assert adapted==original.replace('module camera_vga_calibrated_top','module camera_vga_output_top',1)
    assert proof['OriginalTextSHA256']!=proof['ParserTextSHA256']
    assert proof['InMemoryOnly'] and proof['OriginalFileUnmodified']
    assert original==netlist()


def test_actual_top_identity_adaptation_does_not_touch_init_or_ports():
    original=(audit.prep.PROJECT/audit.prep.TOP).read_text()
    adapted,_=audit.io_syntax(original)
    assert adapted.replace('module camera_vga_output_top','module camera_vga_calibrated_top',1)==original
    assert 'ov5640_cadence_upright_init' in adapted


@pytest.mark.parametrize('text',[netlist('camera_vga_output_top'),netlist()+'module camera_vga_calibrated_top(); endmodule'])
def test_io_adapter_rejects_wrong_or_duplicate_real_target(text):
    with pytest.raises(ValueError):audit.io_syntax(text)


def test_receipt_rejects_old_candidate_schema_before_parsing_any_artifacts(tmp_path,monkeypatch):
    path=tmp_path/'result.json'
    path.write_text(json.dumps({'Schema':'camera-vga-functional-export-v1','Target':'camera_vga_output_top'}))
    monkeypatch.setattr(audit,'bind_file',lambda watched,path,*args,**kw:Path(path))
    with pytest.raises(ValueError,match='identity'):
        audit.receipt(path,'export','a'*64,'b'*64,{})


def test_artifact_selects_main_exception_report_and_rejects_duplicate_names(tmp_path):
    receipt=tmp_path/'result.json'
    name='camera_vga_calibrated_top_exception.rtr'
    r={'Artifacts':{'report_timing/'+name:'a','report_path_timing/one/'+name:'b'}}
    assert audit.artifact(receipt,r,name)==tmp_path/'report_timing'/name
    r['Artifacts']['other/'+name]='c'
    with pytest.raises(ValueError,match='exactly once'):audit.artifact(receipt,r,name)
