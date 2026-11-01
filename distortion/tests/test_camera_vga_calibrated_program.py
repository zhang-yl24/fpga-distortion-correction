"""CPU-only SRAM authorization and exact volatile Tcl checks."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera_vga_calibrated_program as p


def test_volatile_recipe_contains_exact_device_and_sram_only():
    file=p.prep.WORK/'bit-unused/generate_bitstream/camera_vga_calibrated_top.sbit'
    scripts=p.scripts(file)
    assert set(scripts)=={'scan','program'}
    assert 'cfg_program -device_index 0\n' in scripts['program']
    assert 'cfg_read_device_property -mode 3 -device_index 0\n' in scripts['program']
    assert file.as_posix() in scripts['program']
    assert all('flash' not in text.lower() for text in scripts.values())


@pytest.mark.parametrize('powered,notified,timeout',[
    (False,True,90),(True,False,90),(True,True,0),(True,True,301),(True,True,float('nan')),(True,True,True),
])
def test_invalid_session_flags_reject_before_any_hardware(powered,notified,timeout):
    with pytest.raises(ValueError):p.execution_authorization(powered,notified,timeout)


def test_existing_current_session_power_authorization_is_accepted():
    p.execution_authorization(True,True,90)


def test_flash_recipe_injection_rejected(monkeypatch):
    monkeypatch.setattr(p.hw,'_scripts',lambda *a:{'scan':'scan','program':'write_flash'})
    with pytest.raises(ValueError,match='SRAM'):p.scripts('unused')
