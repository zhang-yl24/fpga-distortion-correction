import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_cdc_clm_native as tool
from test_camera720_cdc_native import query,path,header


def make_query(s='src',output='L5Q',e='dst/I2'):
    q=query(output=output);q.update(Source=s+'/CLK',LaunchOutput=s+'/'+output,Endpoint=e)
    return q


def missing(qs):
    return [dict(q,Corner=c,Kind=k) for q in qs for c in q['Corners'] for k in q['CheckKinds']]


def test_grouping_keeps_one_exact_launch_per_source_clock():
    qs=[make_query(output=o) for o in ('L5Q','L6Q')]
    gs=tool.groups_for(qs,missing(qs))
    assert len(gs)==2
    assert all(len(g['SourceLaunches'])==1 for g in gs)
    assert {tuple(g['SourceLaunches'].values()) for g in gs}=={('src/L5Q',),('src/L6Q',)}


def test_large_grouping_bounded_without_losing_or_duplicating_identity():
    qs=[make_query('s'+str(s),'L5Q','d'+str(e)+'/I2') for s in range(9) for e in range(29)]
    gs=tool.groups_for(qs,missing(qs))
    observed=[tool.old.identity(q) for g in gs for q in g['ExpectedIdentities']]
    assert len(observed)==len(set(observed))==len(qs)
    assert set(observed)=={tool.old.identity(q) for q in qs}
    for g in gs:
        assert len(g['SourceLaunches'])<=4 and len(g['ExpectedIdentities'])<=64
        assert len(g['SourceLaunches'])*len(g['Endpoints'])<=64


def test_domains_never_mix_and_ordinary_missing_is_rejected():
    a=make_query('s1');b=make_query('s2');b['MaximumNS']=9
    gs=tool.groups_for([a,b],missing([a,b]));assert len(gs)==2
    q=query(False)
    with pytest.raises(ValueError,match='ordinary'):tool.groups_for([q],missing([q]))


def write_report(tmp_path,qs,cmd=None,launch=None,corners=('slow','fast')):
    gs=tool.groups_for(qs,missing(qs));assert len(gs)==1
    g=gs[0];p=tmp_path/'native.rtr'
    p.write_text(header()+'| Tcl Command : '+(cmd or g['Command'])+'\n'+
        ''.join(path(q,c,launch=launch) for q in qs for c in corners),encoding='ascii')
    return p,g


def test_group_through_retains_each_actual_tco(tmp_path):
    qs=[make_query('s1'),make_query('s2')]
    p,g=write_report(tmp_path,qs)
    rows,other=tool.inspect_report(p,g,qs)
    assert len(rows)==4 and not other
    assert {r['LaunchOutput'] for r in rows}=={'s1/L5Q','s2/L5Q'}


@pytest.mark.parametrize('option',['from','through','to'])
def test_partial_native_selector_drop_rejected(tmp_path,option):
    qs=[make_query('s1',e='d1/I2'),make_query('s2',e='d2/I2')]
    g=tool.groups_for(qs,missing(qs))[0]
    selected=sorted(tool.selector_set(g['Command'],option))
    cmd=g['Command'].replace('-'+option+' {'+' '.join(selected)+'}', '-'+option+' {'+selected[0]+'}')
    p,_=write_report(tmp_path,qs,cmd)
    with pytest.raises(ValueError,match='selector'):tool.inspect_report(p,g,qs)


def test_alternate_packed_output_is_not_credit(tmp_path):
    qs=[make_query()]
    p,g=write_report(tmp_path,qs,launch='src/L6Q')
    with pytest.raises(ValueError,match='escapes'):tool.inspect_report(p,g,qs)


def test_missing_launch_corner_remains_incomplete(tmp_path):
    qs=[make_query()];p,g=write_report(tmp_path,qs,corners=('slow',))
    rows,_=tool.inspect_report(p,g,qs)
    result=tool.summary(qs,rows,[])
    assert result['CoveredCases']==1 and result['ExpectedCases']==2
    assert not result['PhysicalBoundaryChecksPassed'] and not result['TimingAccepted']


def test_complete_boundary_does_not_claim_individual_ff_enumeration(tmp_path):
    qs=[make_query()];p,g=write_report(tmp_path,qs)
    rows,_=tool.inspect_report(p,g,qs);v=tool.summary(qs,rows,[])
    assert v['PhysicalBoundaryChecksPassed']
    assert v['IndividualFFArcsEnumerated'] is False and v['PhysicalTimingAggregationProved'] is False
    assert v['TimingAccepted'] is False and v['HardwareReleaseAllowed'] is False


def test_native_renderer_at_most_three_commands_and_one_init(tmp_path):
    q=make_query();g=tool.groups_for([q],missing([q]))[0]
    text=tool.render(tmp_path,[g]*3)
    assert text.count(tool.inspect.INIT)==1 and text.count('report_path_timing ')==3
    with pytest.raises(ValueError):tool.render(tmp_path,[g]*4)
    with pytest.raises(ValueError):tool.render(tmp_path,[])


def test_every_child_critical_warning_is_rejected(tmp_path):
    child=tmp_path/'child';child.mkdir();(child/'run.log').write_text('C: STA-3006: bad endpoint\n',encoding='ascii')
    assert tool.probe.scan_diagnostics(tmp_path)[0]['Log']=='child/run.log'


@pytest.mark.parametrize('which',['supplement','offset'])
def test_supplement_metadata_must_match_actual_derivation(which):
    inventory={'SameBLESupplement':{'LogicalRelationships':[{'SourceFF':'actual'}]}}
    mapping={'LogicalRelationships':[{},{}]}
    plan={'SameBLESupplement':copy.deepcopy(inventory['SameBLESupplement']),'SupplementalLogicalRelationshipOffset':2}
    tool.validate_supplement(plan,inventory,mapping)
    if which=='offset':plan['SupplementalLogicalRelationshipOffset']=3
    else:plan['SameBLESupplement']['LogicalRelationships'][0]['SourceFF']='invented'
    with pytest.raises(ValueError,match='supplemental'):tool.validate_supplement(plan,inventory,mapping)
