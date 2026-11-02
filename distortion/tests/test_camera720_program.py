"""No hardware: require current session power and exact volatile SRAM Tcl."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_program as program


def test_sram_scripts_use_verified_bit_and_never_flash():
    path=program.prep.WORK/'bit-unused/generate_bitstream/camera720_transport_top.sbit'
    scripts=program.scripts(path)
    assert set(scripts)=={'scan','program'}
    assert path.as_posix() in scripts['program']
    assert 'cfg_program -device_index 0\n' in scripts['program']
    assert 'cfg_read_device_property -mode 3 -device_index 0\n' in scripts['program']
    assert all('flash' not in text.lower() for text in scripts.values())


@pytest.mark.parametrize('powered,notified,timeout',[
    (False,True,90),(True,False,90),(True,True,0),(True,True,301),
    (True,True,float('nan')),(True,True,float('inf')),(True,True,True),
])
def test_invalid_power_notification_or_timeout_rejected_before_hardware(monkeypatch,powered,notified,timeout):
    monkeypatch.setattr(program,'validate',lambda *a:pytest.fail('must reject before validation or hardware'))
    with pytest.raises(ValueError):
        program.execute('unused',board_powered=powered,user_notified=notified,timeout=timeout)


def test_current_session_confirmation_can_be_reused():
    program.execution_authorization(True,True,90)


def test_flash_injection_rejected(monkeypatch):
    monkeypatch.setattr(program.hw,'_scripts',lambda *a:{'scan':'scan','program':'write_flash'})
    with pytest.raises(ValueError,match='SRAM'):program.scripts('unused')
