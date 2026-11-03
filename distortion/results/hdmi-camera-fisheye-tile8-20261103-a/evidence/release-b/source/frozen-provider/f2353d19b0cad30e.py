"""Candidate-specific source and pure parser rejection checks; no EDA."""
import ast
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import hdmi_camera_fisheye_tile8_audit as a
import hdmi_camera_fisheye_tile8_protocol as p
import hdmi_camera_fisheye_tile8_warnings as w
import hdmi_camera_fisheye_fill8r3s3_audit as old


@pytest.mark.parametrize('role,old,new', [
    ('Engine','wire use_tiles=cfg_corrected;', "wire use_tiles=1'b0;"),
    ('Engine','tiled_mode<=use_tiles;', 'tiled_mode<=cfg_corrected^1\'b1;'),
    ('Engine','.frame_tiled(use_tiles)', '.frame_tiled(cfg_corrected^1\'b1)'),
    ('Engine','if(!tiled_mode)', 'if(!cfg_corrected)'),
    ('Engine','DRAIN: if(writer_done)', 'DRAIN: if(writer_pixels==WIDTH*HEIGHT)'),
    ('Engine','core_failed || writer_failed', 'core_failed'),
    ('Writer','state==ADDRESS;', 'state==ADDRESS && !failed;'),
    ('Writer','state==ADDRESS && awready', 'state==ADDRESS && awready && !failed'),
    ('Writer','if(failed || tag_error)state<=FAULT;', 'if(failed)state<=FAULT;'),
    ('Writer','read_index<STRIPE_PIXELS && issued<256', 'read_index<STRIPE_PIXELS'),
    ('Writer','stripe_full[drain_bank]<=0;', 'stripe_full[collect_bank]<=0;'),
    ('Writer','if(tiled && read_last)', 'if(tiled && read_enable)'),
    ('Writer','if(state!=ADDRESS && state!=WRITE)state<=FAULT;', 'state<=FAULT;'),
    ('Writer','DRAIN:if(drain==31)', 'DRAIN:if(drain==0)'),
])
def test_candidate_mode_drain_and_bank_contract_mutation_is_rejected(role, old, new):
    text=(p.build.ROOT/p.CONTRACTS[role]['Source']).read_text(encoding='utf-8-sig')
    assert old in text
    with pytest.raises(ValueError,match='unreviewed complete source'):
        p.contract(role,text.replace(old,new,1))


def test_only_reviewed_engine_and_bank_transformations_are_replayed():
    watched={};result=p.reviewed_candidate_changes(watched)
    assert result['Passed'] is True and len(result['BankAndEngineChanges'])==2
    assert result['ActualNativeMemoryResetCDCAndAllTenTimingStillRequired'] is True
    assert len(watched)==4


def test_warning_inventory_is_candidate_scoped_and_cannot_accept_inherited_s3():
    assert len(w.INVENTORY_SHA)==64 and w.sha(w.INVENTORY)==w.INVENTORY_SHA
    assert w.INVENTORY.parent==w.build.WORK
    assert w.SCHEMA=='hdmi-camera-fisheye-tile8-source-warning-review-v1'
    inventory=w.read(w.INVENTORY)
    assert inventory['Schema']=='hdmi-camera-fisheye-tile8-warning-inventory-v1'
    assert inventory['BuildPlan']['Path']==str(w.build.WORK/'build-a/plan.json')
    assert inventory['SourceBuildReceipt']['SHA256']==w.sha(w.build.WORK/'build-a/execution-result.json')


def test_original_lexer_AST_is_preserved_exactly():
    def function(module,name):
        tree=ast.parse(Path(module.__file__).read_text(encoding='utf-8-sig'))
        node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name)
        node.name='atoms'
        return ast.dump(node,include_attributes=False)
    assert function(a,'_atoms_uncached')==function(old,'atoms')


def test_cache_uses_exact_strings_and_caller_cannot_modify_reused_results():
    a.atoms.cache_clear()
    first=a.atoms('n[3:0]');first.append('foreign')
    second=a.atoms('n[3:0]')
    assert second==old.atoms('n[3:0]') and second is not first
    a.atoms(' n[3:0] ')
    info=a.atoms.cache_info()
    assert info.misses==2 and info.hits==1 and info.maxsize==65536


def test_parser_errors_are_not_cached():
    a.atoms.cache_clear()
    for _ in range(2):
        with pytest.raises(ValueError,match='unsupported scalar'):a.atoms('invalid[')
    assert a.atoms.cache_info().misses==2 and a.atoms.cache_info().currsize==0


@pytest.mark.parametrize('value',[None,5,[],{}])
def test_non_string_dispatch_preserves_original_errors(value):
    def outcome(function):
        try:return ('value',function(value))
        except Exception as error:return ('error',type(error),str(error))
    assert outcome(a.atoms)==outcome(old.atoms)


def test_cache_does_not_change_graph_projection_or_allow_mutable_poisoning():
    models={'V_FFSYN':{'Ports':{'Q':'OUTPUT','D':'INPUT','CK':'INPUT','CE':'INPUT','SR':'INPUT'},'Reference':{}},
            'V_LUT6CARRY':{'Ports':{**{f'I{i}':'INPUT' for i in range(6)},'CIN':'INPUT','Z':'OUTPUT','Z5':'OUTPUT','COUT':'OUTPUT'},'Reference':{}}}
    ff={'Primitive':'V_FFSYN','Parameters':{'LRS_EN':'"TRUE"','SET_RESET':'"RESET"','INIT':"1'b0"},
        'Ports':{'Q':'source','D':"1'b0",'CE':"1'b1",'SR':"1'b0",'CK':'core'}}
    cells={'s':ff,'lut':{'Primitive':'V_LUT6CARRY','Parameters':{'INIT':"64'hAAAAAAAAAAAAAAAA",'I5_TO_LUT':'"FALSE"'},
           'Ports':{'I0':'source',**{f'I{i}':"1'b0" for i in range(1,6)},'CIN':'','Z':'copy','Z5':'','COUT':''}}}
    clocks={'core':{'Generated':False,'Target':'core','Name':'core','PeriodNS':8.,'Master':'core'}}
    left=old.Graph({'Cells':cells,'FFPlacement':{}},{},clocks,models)
    right=a.Graph({'Cells':cells,'FFPlacement':{}},{},clocks,models)
    for net in ('source','copy'):
        assert right.support(net)==left.support(net)
        assert right.expression(net)==left.expression(net)
    a.atoms('source').append('poison')
    assert right.support('copy')=={'ff:s'}
