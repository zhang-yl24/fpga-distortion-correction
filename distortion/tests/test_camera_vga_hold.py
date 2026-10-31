"""Small native-dialect safety checks for the camera hold/route auditors."""
import copy
import importlib.util
from pathlib import Path
import sys

import pytest

TOOLS=Path(__file__).resolve().parents[1]/'tools'
sys.path.insert(0,str(TOOLS))
import audit_camera_vga_hold as hold
import audit_camera_vga_routes as routes


def trace(slack='-0.169'):
    return [line+'\n' for line in f'''Startpoint  : sensor/ICLKDIV
Endpoint    : read_ff/D
Path Group  : core_clk
Path Type   : min (slow corner)
Path Class  : sequential timing path
Clock Skew  : 2.676
  Capture Clock Delay : 5.515
  Launch Clock Delay : 2.615
 Clock sensor_clk (rising edge)
 IOLHR_364_768/RX_DATA[5] tco 0.259 4.874 f sensor/RX_DATA[5]
 net (fanout=1) 0.323 5.197 data [21]
 CLMS_345_769/CR3 td 0.087 5.284 f CLKROUTE_66/CR
 net (fanout=1) 0.239 5.523 _N101
 CLMA_351_774/M2 f read_ff/D
 Data arrival time 5.523
 Clock core_clk (rising edge)
 Hold time -0.049 5.692
 Slack (VIOLATED) {slack}'''.splitlines()]


def test_exact_hold_trace_preserves_real_pins_and_net():
    parsed=hold.parse_path(trace(),Path('actual.rtr'),100)
    assert parsed['SlackNS']==-0.169
    assert parsed['DataTrace'][-2]['Name']=='_N101'
    assert parsed['DataTrace'][-2]['FromRoutePin']=='CR3:CLMS_345_769'
    assert parsed['DataTrace'][-2]['ToRoutePin']=='M2:CLMA_351_774'
    assert parsed['DataTrace'][-1]['X']==351
    assert parsed['DataTrace'][-1]['Y']==774
    assert parsed['Kind']=='hold'


def test_reject_slack_state_disagreement():
    with pytest.raises(ValueError,match='slack sign'):
        hold.parse_path(trace('0.169'),Path('actual.rtr'),100)


def test_reject_unparsed_data_path_row():
    lines=trace();lines.insert(12,' UNKNOWN_NATIVE_RESOURCE\n')
    with pytest.raises(ValueError,match='unparsed data-path row'):
        hold.parse_path(lines,Path('actual.rtr'),100)


def test_reject_target_branch_and_changed_endpoint():
    expected={'FromRoutePin':'CR3:CLMS_345_769','ToRoutePin':'M2:CLMA_351_774'}
    source='(PORTREF CR3 (DEVINSTREF CLMS (SITEREF 345 769)))'
    sink='(PORTREF M2 (DEVINSTREF CLMA (SITEREF 351 774)))'
    valid=f'(NETANNOTATE (NETREF _N101) (ROUTE ({source} ({sink}))))'
    assert len(routes.linear_tree(routes.TOKEN.findall(valid),'_N101',expected))==2
    branched=f'(NETANNOTATE (NETREF _N101) (ROUTE ({source} ({sink}) ({sink}))))'
    with pytest.raises(ValueError,match='branches'):
        routes.linear_tree(routes.TOKEN.findall(branched),'_N101',expected)
    with pytest.raises(ValueError,match='endpoints differ'):
        routes.linear_tree(routes.TOKEN.findall(valid.replace('351 774','351 780')),'_N101',expected)


def inventory():
    return {'NonRouteSemanticSHA256':'same','ExcludedBlockSHA256':{'CDB':'constraints'},
            'TargetConnectivity':{'_N101':['driver','sink']},
            'NetAnnotations':{'_N101':'before','unrelated':'fixed'}}


def test_compare_accepts_only_requested_route_change():
    before=inventory();after=copy.deepcopy(before);after['NetAnnotations']['_N101']='after'
    assert routes.compare(before,after,{'_N101'})['ChangedNets']==['_N101']


def test_compare_rejects_incomplete_three_net_repair():
    before=inventory();after=copy.deepcopy(before)
    for name in ('_N188','_N78'):
        before['NetAnnotations'][name]='before';after['NetAnnotations'][name]='before'
    after['NetAnnotations']['_N101']='after'
    with pytest.raises(ValueError,match='incomplete requested repair'):
        routes.compare(before,after,{'_N101','_N188','_N78'})


@pytest.mark.parametrize('mutation,reason',[
    ('unrelated','unexpected changed routes'),('CDB','constraint block'),
    ('semantic','non-route semantic'),('logical','logical connectivity')])
def test_compare_rejects_unrelated_changes(mutation,reason):
    before=inventory();after=copy.deepcopy(before);after['NetAnnotations']['_N101']='after'
    if mutation=='unrelated':after['NetAnnotations']['unrelated']='changed'
    elif mutation=='CDB':after['ExcludedBlockSHA256']['CDB']='waiver'
    elif mutation=='semantic':after['NonRouteSemanticSHA256']='logic change'
    elif mutation=='logical':after['TargetConnectivity']['_N101']=['different','sink']
    with pytest.raises(ValueError,match=reason):routes.compare(before,after,{'_N101'})
