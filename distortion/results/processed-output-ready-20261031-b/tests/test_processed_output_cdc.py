"""Mutations of real native synchronizer wiring must be rejected."""
from pathlib import Path
import copy
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import audit_processed_output_cdc as audit


@pytest.fixture(scope='module')
def graph():
    path=audit.EXPORT/'generate_netlist/processed_output_top_sim.v'
    if not path.is_file():
        pytest.skip('provenance-bound native export is local')
    return audit.physical.functional_export(path)


def test_actual_gray_and_scalar_inventory(graph):
    gray, scalar=audit.structures(graph)
    assert len(gray)==34 and len(scalar)==19
    assert all(row['SameBLE'] for row in gray)
    assert sum(row['SameSite'] for row in scalar)==16


@pytest.mark.parametrize('mutation',['clock','data','enable','fanout','placement','msb_source'])
def test_gray_path_mutations_are_rejected(graph,mutation):
    g=copy.deepcopy(graph)
    gray,_=audit.structures(g)
    row=gray[-1] if mutation=='msb_source' else gray[0]
    first,second=row['First'],row['Second']
    if mutation=='clock':g['Cells'][second]['Ports']['CK']='wrong_clock'
    elif mutation=='data':g['Cells'][second]['Ports']['D']="1'b0"
    elif mutation=='enable':g['Cells'][first]['Ports']['CE']="1'b0"
    elif mutation=='placement':g['FFPlacement'][second]['Site']='CLMA_1_1'
    elif mutation=='msb_source':g['Cells'][first]['Ports']['D']=g['Cells'][gray[-2]['First']]['Ports']['D']
    else:
        g['Cells']['escaped_first_stage']={'Primitive':'V_BUF','Parameters':{},
            'Ports':{'I':g['Cells'][first]['Ports']['Q'],'Z':'unexpected_escape'}}
    with pytest.raises(ValueError):audit.structures(g)


def test_gated_second_stage_truth_table_is_checked(graph):
    g=copy.deepcopy(graph)
    _,scalar=audit.structures(g)
    row=next(r for r in scalar if r['Label']=='system_failed_ref[0]')
    lut=g['Cells'][row['InterstageLogic']['Cell']]
    lut['Parameters']['INIT']="64'hFFFFFFFFFFFFFFFF"
    with pytest.raises(ValueError,match='interstage LUT'):
        audit.structures(g)


def test_actual_reset_replication_is_bounded(graph):
    result=audit.reset_structures(graph)
    assert result['PackedChains']==7
    assert result['CoreResetReplication']['SecondStageCount']==28
    assert len(result['CoreResetReplication']['EquivalentClearInverters'])==9


def test_reset_replica_may_not_use_an_independent_clear(graph):
    g=copy.deepcopy(graph)
    result=audit.reset_structures(g)
    cell=result['CoreResetReplication']['EquivalentClearInverters'][0]['Cell']
    g['Cells'][cell]['Ports']['I']='unrelated_clear'
    with pytest.raises(ValueError,match='same core-local release'):
        audit.reset_structures(g)


def test_reset_first_stage_may_not_feed_a_functional_consumer(graph):
    g=copy.deepcopy(graph)
    result=audit.reset_structures(g)
    q=result['CoreResetReplication']['FirstPorts']['Q']
    g['Cells']['escaped_reset_first']={'Primitive':'V_BUF','Parameters':{},
                                     'Ports':{'I':q,'Z':'escape_reset'}}
    with pytest.raises(ValueError,match='fanout'):
        audit.reset_structures(g)
