from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path('D:\\GravityLRT\\thu\\semester_4.5\\FPGAchina\\fpga-distortion-correction\\distortion')/'tools'))
import hdmi_camera_fisheye_fill8r3s3_startup_timing as timing

SOURCE={'SourceFF':'power/FF0/FF','SourcePhysicalQ':'CLMS_1_2/Q0','SourceNativeOutputPin':'power/L6Q',
    'LaunchClock':'board27','CaptureClock':'ddrphy_sysclk'}


def block(corner,check):
    return ('Startpoint : power/CLK\nEndpoint : phase/RS\nPath Type : '
        +('max'if check=='Recovery'else'min')+' ('+corner+' corner)\n'
        ' Clock board27 (rising edge) 703.703 703.703 r\n'
        ' CLMS_1_2/Q0 tco 0.203 707.719 r power/L6Q\n'
        ' CLMA_3_4/RS r phase/RS\n Data arrival time 710.026\n'
        ' Clock ddrphy_sysclk (rising edge) 704.000 704.000 r\n'
        ' clock uncertainty -0.050 708.080\n '
        +check+' time -0.226 707.854\n Slack (VIOLATED) -2.172\n')


def test_bound_is_actual_tco_and_routed_data_delay_plus_primitive_check_not_slack(tmp_path,monkeypatch):
    report=tmp_path/'native.rtr';report.write_text(''.join(block(c,k)for c in('slow','fast')for k in('Recovery','Removal')))
    calls=[];original=timing.native.ref
    monkeypatch.setattr(timing.native,'ref',lambda p:(calls.append(p),original(p))[1])
    rows,missing=timing.extract(report,['CLMA_3_4/RS'],SOURCE)
    assert missing==[]and len(rows)==4 and calls==[report]
    assert all(r['PropagationNS']==2.510 and r['RequiredRecoveryNS']==.226
        and r['ClockUncertaintyNS']==.05 and r['TotalRequiredNS']==2.789 for r in rows)
    assert all(r['NativeReportLine']>0 and len(r['PathSHA256'])==64 for r in rows)


def test_missing_physical_consumer_or_corner_check_is_explicit(tmp_path):
    report=tmp_path/'native.rtr';report.write_text(block('slow','Recovery'))
    rows,missing=timing.extract(report,['CLMA_3_4/RS','CLMA_5_6/RS'],SOURCE)
    assert len(rows)==1 and len(missing)==7


@pytest.mark.parametrize('change',['physicalQ','captureclock','missinguncertainty','negativepropagation','mismatcheddelaytype','duplicate'])
def test_opaque_or_conflicting_native_timing_never_becomes_a_startup_bound(tmp_path,change):
    text=block('slow','Recovery')
    if change=='physicalQ':text=text.replace('CLMS_1_2/Q0','CLMS_7_8/Q0')
    elif change=='captureclock':text=text.replace('Clock ddrphy_sysclk','Clock pixel_clk')
    elif change=='missinguncertainty':text=text.replace(' clock uncertainty -0.050 708.080\n','')
    elif change=='negativepropagation':text=text.replace('Data arrival time 710.026','Data arrival time 706.000')
    elif change=='mismatcheddelaytype':text=text.replace('max (slow','min (slow')
    else:text+=text
    report=tmp_path/'native.rtr';report.write_text(text)
    with pytest.raises(ValueError):timing.extract(report,['CLMA_3_4/RS'],SOURCE)
