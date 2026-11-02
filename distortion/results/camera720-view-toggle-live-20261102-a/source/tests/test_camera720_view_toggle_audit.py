"""Negative structural checks for the new pad/synchronizer; no native tools."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import audit_camera720_view_toggle as audit
import camera720_view_toggle_build as build

ROOT = Path(__file__).resolve().parents[1]


def test_native_uart_accepts_output_buffer_or_constant_enabled_tristate():
    for primitive in ('V_OBUF','V_OBUFT'):
        audit.pad_connection('uart_txd',{'Primitive':primitive,'Pin':'O',
            'FunctionalPorts':{'T':"1'b0"}})
    for tristate in ("1'b1",'dynamic_enable'):
        with pytest.raises(ValueError):
            audit.pad_connection('uart_txd',{'Primitive':'V_OBUFT','Pin':'O',
                'FunctionalPorts':{'T':tristate}})


def inputs():
    base = ROOT/'results/camera720-stats-live-20261102-a/source/board'
    top = build.render_top((base/'camera720_calibrated_stats_delay_top.v').read_text(), '1234567890abcdef')
    fdc = build.render_fdc((base/'camera720-calibrated-stats-delay.fdc').read_text())
    return top,fdc


def fixture_graph():
    def ff(d,q,clock='core'):
        return {'Primitive':'V_FFSYN','Parameters':{'INIT':"1'b0",'SET_RESET':'"RESET"'},
                'Ports':dict(D=d,Q=q,CK=clock,CE="1'b1",SR="1'b0")}
    cells = {
        'key1_n_pad':{'Primitive':'V_IBUF','Parameters':{},'Ports':dict(I='key1_n',O='keybuf')},
        'view_control/key_sync[0]/FF0/FF':ff('keybuf','view_control/key_sync[0]'),
        'view_control/key_sync[1]/FF0/FF':ff('view_control/key_sync[0]','view_control/key_sync[1]'),
        'view_control/corrected_requested/FF0/FF':ff('view_control/key_sync[1]','corrected_requested'),
        'core_reset[1]/FF0/FF':ff("1'b1",'core_reset[1]'),
        'system/bank_core/engine/core/mapper/sfx/FF0/FF':ff('corrected_requested','mapper_sfx'),
        'led0':{'Primitive':'V_OBUF','Parameters':{},'Ports':dict(I='corrected_requested',O='led[0]')},
    }
    return cells


def graph(cells):
    value = audit.mux.Graph({'Cells':deepcopy(cells), 'ModuleDeclarations':'',
        'FFPlacement':{n:{'Site':'CLMA_'+str(i),'Attributes':''} for i,n in enumerate(cells) if '/FF' in n}})
    value.clock_cache = {'core':{'Domain':audit.CORE,'Root':'core','Trace':[]},
                         'foreign':{'Domain':'board27','Root':'foreign','Trace':[]}}
    return value


def test_full_declared_inventory_has_key_without_losing_uart_or_reset():
    ports,pins = audit.declared_inventory(*inputs())
    assert len(ports)==130
    assert pins['key1_n']==audit.KEY_ATTRIBUTES
    assert pins['reset_n']['LOC']=='C22'
    assert pins['uart_txd']['LOC']=='C24'


@pytest.mark.parametrize('mutation',[
    lambda s:s.replace('{p:key1_n} {PAP_IO_LOC} {C23}','{p:key1_n} {PAP_IO_LOC} {C22}'),
    lambda s:s.replace('{p:key1_n} {PAP_IO_PULLUP} {TRUE}','{p:key1_n} {PAP_IO_PULLUP} {FALSE}'),
    lambda s:s.replace('set_false_path -from [get_ports {key1_n}]','set_false_path -from [get_ports {key1_n}] -to [get_cells *]'),
    lambda s:s+'\nset_false_path -through [get_cells {view_control/*}]\n',
])
def test_bad_pin_or_overbroad_interstage_exception_rejected(mutation):
    top,fdc = inputs()
    with pytest.raises(ValueError):
        audit.declared_inventory(top,mutation(fdc))


def test_raw_pad_two_stages_and_frame_mapper_fanout_are_verified():
    result = audit.key_audit(graph(fixture_graph()))
    assert result['RawPadOnlyFeedsFirstD'] and result['FirstOnlyFeedsSecondD']
    assert result['Chain']['NativeQueries']
    assert not result['InterstageTimingAccepted']


def test_packed_key_stages_and_mode_q_alias_keep_exact_topology_checks():
    cells=fixture_graph()
    first='view_control/key_sync[0]/FF0/FF'
    old_second='view_control/key_sync[1]/FF0/FF'
    second='view_control/key_sync[0]/opit_srl/FFAPP3/FF'
    cells[second]=cells.pop(old_second)
    cells[first]['Ports']['Q']='physical_q3'
    cells[second]['Ports']['D']='physical_q3'
    mode='view_control/corrected_requested/FF0/FF'
    cells[mode]['Ports']['Q']='nt_led[0]'
    cells['led0']['Ports']['I']='nt_led[0]'
    cells['system/bank_core/engine/core/mapper/sfx/FF0/FF']['Ports']['D']='nt_led[0]'
    result=audit.key_audit(graph(cells))
    assert result['First']==first and result['Second']==second
    assert result['RawPadOnlyFeedsFirstD'] and result['FirstOnlyFeedsSecondD']


@pytest.mark.parametrize('sink,net',[
    ('view_control/corrected_requested/FF0/FF','keybuf'),
    ('view_control/corrected_requested/FF0/FF','view_control/key_sync[0]'),
    ('system/bank_core/engine/core/mapper/sfx/FF0/FF','keybuf'),
])
def test_pad_or_metastable_first_stage_bypass_rejected(sink,net):
    cells = fixture_graph()
    cells[sink]['Ports']['D'] = net
    with pytest.raises(ValueError):
        audit.key_audit(graph(cells))


def test_foreign_clock_and_mode_outside_mapper_rejected():
    cells = fixture_graph()
    cells['view_control/corrected_requested/FF0/FF']['Ports']['CK']='foreign'
    with pytest.raises(ValueError):
        audit.key_audit(graph(cells))
    cells = fixture_graph()
    cells['system/output_video/rgb/FF0/FF'] = cells.pop('system/bank_core/engine/core/mapper/sfx/FF0/FF')
    with pytest.raises(ValueError):
        audit.key_audit(graph(cells))
