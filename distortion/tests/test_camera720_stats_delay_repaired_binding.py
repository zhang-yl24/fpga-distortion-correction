"""Focused current hold/reset ancestry checks; no EDA or hardware."""
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_delay_derived_inspect as derived
import camera720_stats_delay_repaired_reset_apply as apply
import camera720_stats_delay_sealed_receipts as sealed


def test_only_explicit_current_hold_provider_is_used(monkeypatch):
    schema='camera720-calibrated-stats-delay-hold-route-application-v1'
    provider=SimpleNamespace(SCHEMA=schema,
        __file__=str(derived.prep.PROJECT/'tools/camera720_stats_delay_hold_route.py'),
        bind_completed=lambda p,w:{'ActualResult':str(p)})
    monkeypatch.setitem(sys.modules,'camera720_stats_delay_hold_route',provider)
    monkeypatch.setattr(derived.physical,'read',lambda p:{'Schema':schema})
    monkeypatch.setattr(derived.physical,'add',lambda *a:None)
    assert derived.bind_source('current.json',{})=={'ActualResult':'current.json'}
    provider.__file__='wrong-location.py'
    with pytest.raises(ValueError,match='provider identity'):derived.bind_source('current.json',{})


@pytest.mark.parametrize('schema',['camera720-calibrated-stats-hold-route-application-v1',
    'camera720-calibrated-stats-delay-reset-application-v1',
    'camera720-current-raw-reset-application-v1',None])
def test_stale_or_nonroute_provider_is_not_accepted(monkeypatch,schema):
    monkeypatch.setattr(derived.physical,'read',lambda p:{'Schema':schema})
    with pytest.raises(ValueError,match='only exact'):derived.bind_source('receipt',{})


@pytest.mark.parametrize('digest',[None,'','a'*63,'g'*64])
def test_explicit_source_digest_is_required_before_full_binding(monkeypatch,digest):
    monkeypatch.setattr(derived.prep,'work_path',lambda p:Path(p))
    monkeypatch.setattr(derived,'bind_source',lambda *a:pytest.fail('invalid SHA reached full binder'))
    with pytest.raises(ValueError,match='explicit completed'):derived.recipe('p',digest,Path('stage'),'query')


@pytest.fixture
def ancestry(tmp_path,monkeypatch):
    monkeypatch.setattr(apply.prep,'WORK',tmp_path)
    paths={name:tmp_path/(name+'.json') for name in ('proof','route','export','report')}
    for p in paths.values():p.write_text('{}')
    refs={k:apply.ref(p) for k,p in paths.items()}
    authority=tmp_path/'authority.json';authority.write_text(json.dumps({'SourceReceipt':refs['route']}))
    request={'Schema':apply.REQUEST_SCHEMA,'Target':apply.prep.TARGET,'ResetProof':refs['proof'],
             'RouteApplication':refs['route'],'BaselineExport':refs['export'],'BaselineReport':refs['report'],
             'SourceAuthority':apply.ref(authority)}
    request_path=tmp_path/'request.json';request_path.write_text(json.dumps(request))
    original={'SourceADF':{'Path':'original.adf','SHA256':'a'*64},'BuildPlan':'build.json',
              'BuildPlanSHA256':'b'*64,'ExportReceipt':refs['export']}
    route={'SourceADFSHA256':'a'*64,'BuildPlan':'build.json','BuildPlanSHA256':'b'*64,
           'OriginalExportReceipt':refs['export'],'ExactResetCommands':[],'ResetProof':None,
           'ResultADFSHA256':'c'*64}
    common={'SourceReceipt':refs['route'],'SourceADFSHA256':'c'*64,'BuildPlan':'build.json',
            'BuildPlanSHA256':'b'*64}
    export={**common,'Mode':'export'};report={**common,'Mode':'report'}
    monkeypatch.setattr(apply.proof,'verify',lambda p:(original,{}))
    monkeypatch.setattr(sealed.fast,'bind_authority',lambda *a:(route,{},{}))
    monkeypatch.setattr(sealed,'bind_receipt',lambda p,*a:(export if p==paths['export'] else report,{}))
    monkeypatch.setattr(apply,'functional',lambda p:pytest.fail('bad ancestry reached large graph parse'))
    return SimpleNamespace(path=request_path,route=route,export=export,report=report,original=original,authority=authority)


def test_source_authority_must_bind_exact_route_application(ancestry):
    a=ancestry;a.authority.write_text(json.dumps({'SourceReceipt':{'Path':'other.json','SHA256':'0'*64}}))
    r=apply.read(a.path);r['SourceAuthority']=apply.ref(a.authority);a.path.write_text(json.dumps(r))
    with pytest.raises(ValueError,match='another route application'):apply.bind_request(a.path)


@pytest.mark.parametrize('field,bad',[('SourceADFSHA256','d'*64),('BuildPlan','other.json'),
    ('BuildPlanSHA256','e'*64),('OriginalExportReceipt',{}),('ExactResetCommands',['set_false_path fake']),
    ('ResetProof',{})])
def test_repaired_candidate_must_descend_from_actual_proved_original(ancestry,field,bad):
    ancestry.route[field]=bad
    with pytest.raises(ValueError,match='unscoped descendant'):apply.bind_request(ancestry.path)


@pytest.mark.parametrize('field,bad',[('Mode','export'),('SourceReceipt',{}),
    ('SourceADFSHA256','d'*64),('BuildPlan','other.json'),('BuildPlanSHA256','e'*64)])
def test_fresh_report_must_be_same_repaired_candidate(ancestry,field,bad):
    ancestry.report[field]=bad
    with pytest.raises(ValueError,match='another route candidate'):apply.bind_request(ancestry.path)


def test_readonly_report_cannot_modify_constraints_or_route():
    body=derived.render('report','',Path('build'),Path('stage'))
    assert body.count(derived.INIT)==1
    for token in ('save_adif','set_false_path','manual_route','unroute','gen_bit_stream'):
        assert token not in body
