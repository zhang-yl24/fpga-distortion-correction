import copy
from pathlib import Path
import sys

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_cdc_single as tool
from test_camera720_cdc_clm_native import make_query,missing
from test_camera720_cdc_native import path,header


def test_each_group_has_exact_one_clock_and_one_launch_with_full_membership():
    qs=[make_query('s'+str(s),o,'d'+str(i)+'/I2')for s in range(3)for o in ('L5Q','L6Q')for i in range(28)]
    gs=tool.groups_for(qs,missing(qs));assert len(gs)==6
    assert all(len(g['SourceLaunches'])==1 and len(g['Endpoints'])==28 for g in gs)
    ids=[tool.parent.old.identity(q)for g in gs for q in g['ExpectedIdentities']]
    assert len(ids)==len(set(ids))==len(qs)
    assert set(ids)=={tool.parent.old.identity(q)for q in qs}


def test_partial_case_coverage_preserved_and_only_missing_identity_requeried():
    qs=[make_query(e='d0/I2'),make_query(e='d1/I2'),make_query(e='d2/I2')]
    records=[tool.parent.old.parse_record(path(q,c).splitlines(True),'r.rtr',1,q)for q in qs[:2]for c in ('slow','fast')]
    records.append(tool.parent.old.parse_record(path(qs[2],'slow').splitlines(True),'r.rtr',1,qs[2]))
    before=tool.parent.summary(qs,records,[]);assert before['CoveredCases']==5
    groups=tool.groups_for(qs,before['MissingCases'])
    assert len(groups)==1 and groups[0]['Endpoints']==['d2/I2']
    records.append(tool.parent.old.parse_record(path(qs[2],'fast').splitlines(True),'r.rtr',1,qs[2]))
    assert tool.parent.summary(qs,records,[])['PhysicalBoundaryChecksPassed']


def test_four_command_batch_and_reject_multi_source_or_fifth(tmp_path):
    qs=[make_query('s'+str(i))for i in range(4)];gs=tool.groups_for(qs,missing(qs))
    text=tool.render(tmp_path,gs);assert text.count('report_path_timing ')==4 and text.count(tool.inspect.INIT)==1
    with pytest.raises(ValueError):tool.render(tmp_path,gs+[gs[0]])
    bad=copy.deepcopy(gs[0]);bad['SourceLaunches']['extra/CLK']='extra/L5Q'
    with pytest.raises(ValueError,match='one source'):tool.render(tmp_path,[bad])


def test_single_source_report_missing_corner_never_assumed_complete(tmp_path):
    q=make_query();g=tool.groups_for([q],missing([q]))[0];p=tmp_path/'timing.rtr'
    p.write_text(header()+'| Tcl Command : '+g['Command']+'\n'+path(q,'slow'),encoding='ascii')
    records,_=tool.parent.inspect_report(p,g,[q])
    c=tool.parent.summary([q],records,[])
    assert c['CoveredCases']==1 and c['PhysicalBoundaryChecksPassed']is False


def test_more_than64_endpoints_chunked_without_identity_loss():
    qs=[make_query(e='d'+str(i)+'/I2')for i in range(65)]
    gs=tool.groups_for(qs,missing(qs));assert sorted(len(g['Endpoints'])for g in gs)==[1,64]


def test_unrecognized_missing_identity_rejected():
    q=make_query();bad=dict(q,Source='unknown/CLK')
    with pytest.raises(ValueError,match='loses'):tool.groups_for([q],missing([bad]))
