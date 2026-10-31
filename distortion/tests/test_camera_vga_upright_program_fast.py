"""CPU-only fast SRAM handoff and pre-hardware boundary checks."""
from pathlib import Path
import json
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera_vga_upright_program_fast as p


@pytest.mark.parametrize('powered,notified,timeout',[
    (False,True,90),(True,False,90),(True,True,0),(True,True,301),(True,True,float('inf')),(True,True,True),
])
def test_authorization_rejected_before_any_native_action(powered,notified,timeout,monkeypatch):
    monkeypatch.setattr(p,'validate',lambda *a:pytest.fail('validation/hardware entered before authorization'))
    with pytest.raises(ValueError):p.execute('unused',board_powered=powered,user_notified=notified,timeout=timeout)


def test_current_session_authorization_accepted_without_new_power_cycle():
    p.authorization(True,True,90)


def test_tcl_is_exact_native_sram_recipe_without_flash():
    f=p.prep.WORK/'bit-fast-unused/generate_bitstream/camera_vga_upright_top.sbit'
    scripts=p.scripts(f)
    assert scripts==p.hw._scripts({'bitstream_path':str(f)},'1MHz')
    assert scripts['program'].count('cfg_program -device_index 0\n')==1
    assert 'cfg_read_device_property -mode 3' in scripts['program']
    assert all('flash' not in v.lower() for v in scripts.values())


def test_flash_script_rejected(monkeypatch):
    monkeypatch.setattr(p.hw,'_scripts',lambda *a:{'scan':'scan','program':'write_flash'})
    with pytest.raises(ValueError,match='SRAM'):p.scripts('unused')


def test_fast_program_never_calls_original_full_authority(monkeypatch):
    def fail(*args,**kwargs):pytest.fail('full authority must not run through fast program')
    monkeypatch.setattr(p.bit.bit,'authority',fail)
    monkeypatch.setattr(p.bit,'verify',lambda work:(_ for _ in ()).throw(ValueError('fast verifier sentinel')))
    with pytest.raises(ValueError,match='fast verifier sentinel'):
        p.recipe(p.prep.WORK/'bit-fast-unused',p.prep.WORK/'program-unused')


def test_saved_verification_json_roundtrip_preserves_exact_events():
    current={'CheckedUTC':'now','ActualEvents':[('Report Timing','started'),('Report Timing','done')],
             'Bitstream':{'SHA256':'a'*64},'Verified':True}
    saved=json.loads(json.dumps(current));saved['CheckedUTC']='then'
    p.verification_equal(saved,current)
    saved['ActualEvents'][0][0]='Synthesize'
    with pytest.raises(ValueError,match='differs'):p.verification_equal(saved,current)


def test_saved_verification_roundtrip_does_not_ignore_any_other_field():
    current={'CheckedUTC':'now','Bitstream':{'SHA256':'a'*64},'Verified':True}
    changed=json.loads(json.dumps(current));changed['Bitstream']['SHA256']='b'*64
    with pytest.raises(ValueError):p.verification_equal(changed,current)
