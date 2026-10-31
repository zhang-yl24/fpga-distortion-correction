"""CPU-only measured single-branch and exact reset sequencing checks."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import run_camera_vga_upright_route_reset as r

TARGET={'Net':'_N127','FromRoutePin':'CR2:CLMS_351_799','ToRoutePin':'M3:CLMA_339_750'}
PINS='ZDNE[0]:SRB_300_744>IDNE[0]:SRB_306_750;'


def row(**kw):return {'Net':'_N127','Branch':'M3:CLMA_339_750','Pins':PINS,**kw}


def test_exact_measured_single_branch_accepts_one_waypoint_pair():
    commands=r.route_commands(row(),TARGET,{})
    assert commands[1]=='unroute -branch {_N127:M3:CLMA_339_750;}'
    assert commands[2]=='manual_route -net {_N127} -branch {M3:CLMA_339_750} -pins {'+PINS+'}'
    assert all('set_false_path' not in c for c in commands)


@pytest.mark.parametrize('change',[
    {'Net':'_N101'},{'Branch':'M3:CLMA_339_751'},
    {'Pins':'ZDNE[0]:SRB_300_744>IDNE[0]:SRB_306_750;ZDNE[2]:SRB_300_744>IDNE[2]:SRB_306_750;'},
    {'Pins':'ZDNE[0]:SRB_300_744>IDNE[0]:SRB_306_750>ZDNE[2]:SRB_300_744>IDNE[2]:SRB_306_750;'},
    {'Pins':'ZDNE[0]:SRB_300_744>ZDNE[0]:SRB_300_744;'},
    {'Pins':'x; exec bad'}, {'Unexpected':'field'},
])
def test_old_net_wrong_branch_multilist_repetition_and_injection_rejected(change):
    with pytest.raises(ValueError):r.route_commands(row(**change),TARGET,{})


def test_occupied_waypoint_rejected_even_if_same_target_net():
    with pytest.raises(ValueError,match='occupied'):
        r.route_commands(row(),TARGET,{'ZDNE[0]:SRB_300_744':['_N127']})


def test_combined_save_has_one_init_before_exact_route_reset_and_no_second_sta():
    commands=r.route_commands(row(),TARGET,{})
    reset='set_false_path -from [get_pins -hierarchical -regexp {^(reset/CLK)$}] -to [get_pins -hierarchical -regexp {^(stage/RS)$}]'
    text=r.render(commands,[reset],r.prep.WORK/'cpu-never-run')
    assert text.count('mpnr_report_timing')==1 and text.count('save_adif')==1
    assert text.index(r.physical.INIT)<text.index('manual_route')<text.index(reset)<text.index('save_adif')<text.index('.switch_db')
    assert 'gen_bit_stream' not in text and 'compile ' not in text


def test_route_only_save_never_generates_reset_waiver():
    text=r.render(r.route_commands(row(),TARGET,{}),[],r.prep.WORK/'cpu-never-run')
    assert 'set_false_path' not in text and 'mpnr_report_timing' not in text
    assert 'save_adif' in text and 'route-dump.txt' in text


def test_success_requires_actual_names_saved_readback_and_no_timing_stage():
    v={'Schema':r.SCHEMA,'ExitCode':0,'EDAExecuted':True,'TimedOut':False,'StoppedForUnexpectedStage':False,
       'InputDrift':[],'Diagnostics':[],'ActualEvents':[],'CompletionMarker':True,'InitializationPreservedADF':True,
       'ApplicationNativeNamesVerified':True,'SavedADFReadbackMatches':True,'ResultADFChanged':True,'Cleanup':{'Complete':True}}
    assert r.execution_ok(v)
    for key in ('ApplicationNativeNamesVerified','SavedADFReadbackMatches','InitializationPreservedADF'):
        assert not r.execution_ok({**v,key:False})
    assert not r.execution_ok({**v,'ActualEvents':[['Report Timing','started']]})
