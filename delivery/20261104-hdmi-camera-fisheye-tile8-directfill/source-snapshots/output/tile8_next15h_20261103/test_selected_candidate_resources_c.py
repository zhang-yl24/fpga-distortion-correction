"""Local pure checks only; no attribute(), public verify or actual graph replay."""
from copy import deepcopy
from pathlib import Path
import ast
import json
import pytest
import verify_selected_candidate_resources_c as c


def raw_fragment():
    return ({'Schema':'hdmi-camera-fisheye-tile8df8-build-v1','Target':c.TARGET},
        {'Schema':'hdmi-camera-fisheye-tile8df8-build-execution-v1','Target':c.TARGET,'BuildCompleted':True,
         'EDAExecuted':True,'ExitCode':0,'InputDrift':[],'NativeErrors':[],'TimedOut':False})


def test_saved_raw_metadata_fragment_is_accepted_without_running_provider():
    c.check_saved_raw_identity(*raw_fragment())


@pytest.mark.parametrize('field,value',[('Schema','old'),('Target','other'),('BuildCompleted',False),('EDAExecuted',False),
                                     ('ExitCode',2),('InputDrift',['changed']),('NativeErrors',['error']),('TimedOut',True)])
def test_saved_raw_failed_or_mismatched_metadata_rejected(field,value):
    args=raw_fragment();args[1][field]=value
    with pytest.raises(ValueError):c.check_saved_raw_identity(*args)


def test_pending_finalpins_reject_before_reading_candidate_or_baseline(monkeypatch):
    monkeypatch.setattr(c.authority,'PROVIDER_SHA256',None)
    with pytest.raises(ValueError,match='not frozen'):c.attribute('df8',c.CANDIDATES['df8'],False)


@pytest.mark.parametrize('candidate',['df9tp','df9tps4'])
def test_failed_candidates_cannot_be_final_resource_attribution(candidate):
    with pytest.raises(ValueError,match='only selected'):c.attribute(candidate,c.CANDIDATES[candidate],False)


def test_resource_c_contains_no_public_verify_or_audit_request_call():
    tree=ast.parse(Path(c.__file__).read_text(encoding='utf-8'))
    functions={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
    for name in ('attribute','saved_v3_release'):
        calls=[n.func for n in ast.walk(functions[name]) if isinstance(n,ast.Call)]
        assert not any(isinstance(f,ast.Attribute) and f.attr in ('verify','audit_request','verify_execution','validate') for f in calls)
    text=Path(c.__file__).read_text(encoding='utf-8')
    assert 'BitVerificationPublicAPIRecomputedByThisTool=False' in text
    assert 'SavedPublicVerificationChecked=True' in text
    assert "work / 'bit-v3-a'" in text and "work / 'program-v3-a/receipt.json'" in text


def test_resource_c_does_not_modify_legacy_b():
    assert c.sha(c.OUT/'verify_selected_candidate_resources_b.py')=='d7ed4e3275f5a263ec97f0a3977c7daf91afab2049cccf011d2b4624a257bacb'


def test_duplicate_saved_members_are_rejected(tmp_path):
    path=tmp_path/'local-fragment.json';path.write_text('{"ExitCode":0,"ExitCode":2}')
    with pytest.raises(ValueError,match='duplicate'):c.read(path)


@pytest.mark.parametrize('field',['Passed','STAAllTenPassed','NetlistEquivalent','AllFFPlacementsEquivalent','RoutesUnchanged'])
def test_resource_graph_placement_timing_require_each_flag(field):
    value={'Target':c.TARGET,**{name:True for name in ('Passed','STAAllTenPassed','NetlistEquivalent','AllFFPlacementsEquivalent','RoutesUnchanged')}}
    value[field]=False
    with pytest.raises(ValueError):c.final_flags(value)
