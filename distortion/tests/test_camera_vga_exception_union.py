from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import audit_camera_vga_exception_union as audit


def path(net='_N78',delay='0.200',arrival='1.300',slack='0.700',pct='66.667',lpct='33.333'):
    text=f'''Startpoint  : source/CLK
Endpoint    : target/D
Path Group  : capture
Path Type   : max (slow corner)
Path Class  : sequential timing path
Clock Skew  : 0.000
  Capture Clock Delay     : 0.000
  Launch Clock Delay      : 0.000
  Clock Pessimism Removal : 0.000
Timing Exception  : MultiCycle Path Setup -end 2
Exception constraint line number: 700
 Clock launch (rising edge) 0.000 0.000 r
 CLMA_1_2/CR0 tco 0.100 1.100 r source/Q
 net (fanout=1) {delay} {arrival} {net}
 CLMA_3_4/D r target/D
 Data arrival time {arrival} Logic Levels: 1
 Logic: 0.100ns({lpct}%), Route: {delay}ns({pct}%)
 Clock capture (rising edge) 2.000 2.000 r
 Setup time 0.000 2.000
 Data required time 2.000
 Data required time 2.000
 Data arrival time {arrival}
 Slack (MET) {slack}
'''
    return audit.record(text.splitlines(keepends=True),'fixture.rtr',1)


def change(row,old,new):
    return audit.record(''.join(row['Lines']).replace(old,new).splitlines(keepends=True),'mutation.rtr',1)


def sections(rows):
    return {('slow',str(i)):list(rows) if i==0 else [] for i in range(16)}


def test_repaired_net_delay_and_derived_slack_change():
    old=path();new=path(delay='0.500',arrival='1.600',slack='0.400',pct='83.333',lpct='16.667')
    result=audit.compare_path(old,new,True)
    assert result['ActualRepairedNets']==['_N78']
    assert result['SlackDeltaNS']==-0.3
    assert result['UnchangedRoutePrintedChanges']==[]


@pytest.mark.parametrize('old,new',[
    ('Clock capture (rising edge)','Clock capture (falling edge)'),
    ('MultiCycle Path Setup -end 2','MultiCycle Path Setup -end 3'),
    ('Data required time 2.000','Data required time 2.001'),
    ('tco 0.100','tco 0.101'),
    ('CLMA_3_4/D','CLMA_3_5/D'),
    ('Setup time 0.000','Setup time 0.001'),
    ('Clock Skew  : 0.000','Clock Skew  : 0.001'),
])
def test_no_waiver_for_clock_limit_cell_or_topology(old,new):
    baseline=path()
    with pytest.raises(ValueError):audit.compare_path(baseline,change(baseline,old,new),True)


def test_non_target_one_ps_requires_proved_same_route():
    old=path(net='unchanged')
    new=path(net='unchanged',delay='0.201',arrival='1.301',slack='0.699',pct='66.777',lpct='33.223')
    result=audit.compare_path(old,new,True)
    assert result['UnchangedRoutePrintedChanges'][0]['DeltaNS']==0.001
    with pytest.raises(ValueError):audit.compare_path(old,new,False)


def test_non_target_two_ps_rejected():
    old=path(net='unchanged')
    new=path(net='unchanged',delay='0.202',arrival='1.302',slack='0.698',pct='66.887',lpct='33.113')
    with pytest.raises(ValueError):audit.compare_path(old,new,True)


def test_invented_derived_slack_rejected():
    old=path();new=path(delay='0.500',arrival='1.600',slack='0.450',pct='83.333',lpct='16.667')
    with pytest.raises(ValueError):audit.compare_path(old,new,True)


def test_repaired_delay_does_not_permit_required_time_rounding():
    old=path();new=path(delay='0.500',arrival='1.600',slack='0.400',pct='83.333',lpct='16.667')
    with pytest.raises(ValueError):audit.compare_path(old,change(new,'Data required time 2.000','Data required time 2.001'),True)


def test_top_n_swap_completed_from_both_union_reports():
    old=path();new=path(delay='0.500',arrival='1.600',slack='0.400',pct='83.333',lpct='16.667')
    another=change(path(net='unchanged'),'source/','another/')
    result=audit.compare_records(sections([old]),sections([another]),[old,another],[new,another],True)
    assert result['ChangedIdentityCount']==2
    assert result['ComparedUnionPathCount']==2


def test_top_n_swap_without_both_exact_members_fails():
    old=path();another=change(path(net='unchanged'),'source/','another/')
    with pytest.raises(ValueError,match='union missing'):
        audit.compare_records(sections([old]),sections([another]),[old],[another],True)


def test_same_identity_with_missing_edge_variant_fails():
    old=path();new=change(old,'rising edge','falling edge')
    with pytest.raises(ValueError,match='union missing'):
        audit.compare_records(sections([old]),sections([new]),[old],[new],True)


def test_representative_count_does_not_hide_variant_loss():
    old=path();new=path(delay='0.500',arrival='1.600',slack='0.400',pct='83.333',lpct='16.667')
    extra=change(old,'CLMA_1_2/CR0','CLMA_9_2/CR0')
    with pytest.raises(ValueError,match='variant count changed'):
        audit.compare_records(sections([old]),sections([new]),[old,extra],[new],True)


def test_constraint_line_metadata_only_is_ignored():
    old=path();new=change(old,'line number: 700','line number: 850')
    assert old['SHA256']==new['SHA256']
    audit.compare_path(old,new,True)


def actual_write_variant():
    root=Path(__file__).resolve().parents[1]/'work/camera-vga-output'
    import json
    plan=json.loads((root/'exception-union-query-20261031-a.json').read_text())
    def get(stage):
        rows=audit.read_union(list((root/stage/'report_path_timing').rglob('*.rtr')),set(plan['Sources']),set(plan['Endpoints']))
        return next(r for r in rows if audit.parsed(r)['Source']==audit.WRITE_SOURCE and
                    audit.parsed(r)['Endpoint']==audit.WRITE_ENDPOINT and
                    audit.parsed(r)['Corner']=='fast' and audit.parsed(r)['Kind']=='hold')
    return get('physical-exception-baseline-20261031-a'),get('physical-final-report-20261031-a')


def test_observed_native_worst_switch_requires_all_independent_evidence():
    old,new=actual_write_variant()
    context={'FunctionalGraphIdentical':True,'AllFFPlacementsIdentical':True,'AllInternalChecksMet':True}
    result=audit.compare_worst_variant(old,new,context)
    assert result['NativeWorstTransitionRepresentativeChanged']
    assert not result['SameTransitionVariantProved']
    assert not result['OnlyRepairedNetDelayChanged']
    for k in context:
        with pytest.raises(ValueError):audit.compare_worst_variant(old,new,{**context,k:False})


@pytest.mark.parametrize('old,new',[
    ('MultiCycle Path Setup -end 2','MultiCycle Path Setup -end 3'),
    ('CLKROUTE_43/CR','CLKROUTE_44/CR'),
    ('_N78','_N79'),
    ('CLMA_357_840/Y2','CLMA_356_840/Y2'),
    ('phy_wrdata_d[3]','phy_wrdata_d[4]'),
    ('Clock phy_dq_sysclk_1 (rising edge)','Clock phy_dq_sysclk_1 (falling edge)'),
])
def test_observed_switch_never_waives_different_identity_or_connectivity(old,new):
    before,after=actual_write_variant()
    with pytest.raises(ValueError):
        audit.compare_worst_variant(before,change(after,old,new),
            {'FunctionalGraphIdentical':True,'AllFFPlacementsIdentical':True,'AllInternalChecksMet':True})
