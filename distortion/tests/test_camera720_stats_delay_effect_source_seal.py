"""Final effect source authority cannot substitute a different application."""
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_delay_repaired_reset_effect as effect
import camera720_stats_delay_repaired_final_inspect as final


@pytest.mark.parametrize('wrong_authority_receipt,wrong_final_receipt',[(True,False),(False,True)])
def test_effect_matches_sealed_application_and_final_candidate_before_graph(
        tmp_path,monkeypatch,wrong_authority_receipt,wrong_final_receipt):
    application=tmp_path/'application.json';application.write_text('{}')
    authority=tmp_path/'authority.json'
    ref=effect.ref(application)
    authority.write_text(json.dumps({'SourceReceipt':{} if wrong_authority_receipt else ref}))
    export=tmp_path/'export.json';export.write_text(json.dumps({'Schema':final.SCHEMA}))
    value={'SourceAuthority':effect.ref(authority),'Mode':'export',
        'SourceReceipt':{} if wrong_final_receipt else ref,'SourceADFSHA256':'a'*64}
    monkeypatch.setattr(final,'bind_receipt',lambda p:(value,{}))
    monkeypatch.setattr(final,'bind_authority',lambda *a:({'ResultADFSHA256':'a'*64},{}))
    monkeypatch.setattr(effect.physical,'bind_completed',lambda *a:pytest.fail('repeat upstream semantic audit'))
    monkeypatch.setattr(effect.physical,'functional',lambda *a:pytest.fail('bad ancestry reached graph parser'))
    with pytest.raises(ValueError,match='another'):
        effect.audit_value(application,export)
