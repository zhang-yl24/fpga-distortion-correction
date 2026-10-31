"""Adversarial CPU tests for exact reset and single-route effect boundaries."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import audit_camera_vga_upright_reset_effect as effect


def timing():
    data=('data_source','data_destination');reset=('reset_source','reset_destination')
    base={};final={}
    for corner in ('slow','fast'):
        for kind in effect.native.KINDS:
            key=(corner,kind);pair=('clock',) if kind=='mpw' else data
            base[key]={pair:{'WorstSlackNS':1.0,'TotalNegativeSlackNS':0.0,'FailingChecks':0,'TotalChecks':100}}
            final[key]=deepcopy(base[key])
            if kind in ('recovery','removal'):
                base[key][reset]={'WorstSlackNS':-1.0 if kind=='recovery' else 1.0,
                    'TotalNegativeSlackNS':-2.0 if kind=='recovery' else 0.0,
                    'FailingChecks':2 if kind=='recovery' else 0,'TotalChecks':2}
    inv={'Groups':[{'Corner':c,'LaunchClock':reset[0],'CaptureClock':reset[1],
                    'Complete':True,'ObservedLogicalChecks':2} for c in ('slow','fast')]}
    return base,final,inv,data,reset


def test_only_measured_reset_groups_are_removed():
    b,a,i,_,_=timing();summary,changes=effect.compare_timing(b,a,i,set())
    assert len(summary)==10 and changes==[]
    assert summary['fast_removal']['RemovedResetChecks']==2


@pytest.mark.parametrize('change', ['data_count','data_slack','unexpected_pair','remaining_failure','reset_count'])
def test_timing_rejects_unrequested_waivers_and_failures(change):
    b,a,i,data,reset=timing()
    if change=='data_count':a['slow','hold'][data]['TotalChecks']=99
    if change=='data_slack':a['slow','setup'][data]['WorstSlackNS']=1.1
    if change=='unexpected_pair':a['fast','hold'][('other','clock')]={**a['fast','hold'][data]}
    if change=='remaining_failure':a['slow','hold'][data]['WorstSlackNS']=-0.01
    if change=='reset_count':b['slow','recovery'][reset]['TotalChecks']=3
    with pytest.raises(ValueError):effect.compare_timing(b,a,i,set())


def test_only_explicit_route_pair_may_change_while_counts_stay_timed():
    b,a,i,data,_=timing();a['slow','hold'][data]['WorstSlackNS']=0.05
    summary,changes=effect.compare_timing(b,a,i,{data})
    assert changes[0]['Kind']=='hold' and summary['slow_hold']['TotalChecks']==100
    a['slow','hold'][data]['TotalChecks']=99
    with pytest.raises(ValueError):effect.compare_timing(b,a,i,{data})


def route():
    before={'NetAnnotations':{'new_net':'old','stable_net':'same'},'TargetConnectivity':{'new_net':['source','sink']},'RouteCount':2}
    after=deepcopy(before);after['NetAnnotations']['new_net']='new'
    separated={'NonConstraintNonRouteSHA256':'same semantic token hash'}
    return before,after,separated


def test_combined_route_is_reported_honestly():
    b,a,s=route();r=effect.compare_routes(b,a,s,s,{'new_net'})
    assert r['RoutingUnchanged'] is False and r['OnlyRequestedRoutingChanges'] is True
    assert r['ChangedNets']==['new_net']


@pytest.mark.parametrize('change',['other_net','missing_net','connectivity','semantics','no_requested_change'])
def test_route_effect_rejects_additional_modifications(change):
    b,a,s=route();after_scope=dict(s)
    if change=='other_net':a['NetAnnotations']['stable_net']='different'
    if change=='missing_net':del a['NetAnnotations']['stable_net']
    if change=='connectivity':a['TargetConnectivity']['new_net']=['wrong','sink']
    if change=='semantics':after_scope['NonConstraintNonRouteSHA256']='changed'
    if change=='no_requested_change':a=deepcopy(b)
    with pytest.raises(ValueError):effect.compare_routes(b,a,s,after_scope,{'new_net'})


def false_paths():
    fields={'Source':'actual_reset/CLK','Endpoint':'actual_sync/RS','LaunchClock':'board','CaptureClock':'ddr',
            'LaunchEdge':'rising','CaptureEdge':'rising'}
    inv={'Corners':{c:{'Checks':[{'NativeVariants':[dict(fields)]}]} for c in ('slow','fast')}}
    base={(c,k):[] for c in ('slow','fast') for k in ('setup','hold','recovery','removal')}
    final=deepcopy(base)
    for corner in ('slow','fast'):
        for kind in ('recovery','removal'):
            final[corner,kind]=[{**fields,'LaunchDataTransition':'r','NativePathSignature':corner+kind}]
    return base,final,inv


def test_exact_reset_false_paths_are_required_in_both_corners():
    b,a,i=false_paths();r=effect.compare_false_paths(b,a,i)
    assert r['slow_recovery']['UniqueClockAndPinChecks']==1


@pytest.mark.parametrize('change',['data_falsepath','missing_reset','extra_reset','duplicate_variant','baseline_waiver'])
def test_false_path_union_rejects_broadening_or_missing_evidence(change):
    b,a,i=false_paths()
    if change=='data_falsepath':a['slow','setup']=deepcopy(a['slow','recovery'])
    if change=='missing_reset':a['fast','removal']=[]
    if change=='extra_reset':a['slow','recovery'].append({**a['slow','recovery'][0],'Endpoint':'extra/RS'})
    if change=='duplicate_variant':a['slow','recovery']*=2
    if change=='baseline_waiver':b['slow','setup']=deepcopy(a['slow','recovery'])
    with pytest.raises(ValueError):effect.compare_false_paths(b,a,i)


def test_nonfalse_exceptions_do_not_silently_allow_native_topn_changes():
    before={(str(i),'kind'):[{'SHA256':'exact semantic path'}] for i in range(16)}
    after=deepcopy(before);assert len(effect.nonfalse_equal(before,after))==16
    after['0','kind'][0]['SHA256']='different native member'
    with pytest.raises(ValueError,match='two-sided evidence'):effect.nonfalse_equal(before,after)
