from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import run_camera720_stats_shared_monitor_sim as sim


def good():
    return {'Passed':True,'PCLKHalfPeriodPS':11905,'BadLineCase':0,'Configured':1,
            'RawAuthorize':0,'GoodFrames':2,'BadFrames':0,'LastLines':720,'LastBytes':2560,'Fault':0xc0}


def test_complete_good_halt_case():
    assert sim.observations('\n'.join(sim.GOOD_MARKERS),good(),11905,False)==good()


@pytest.mark.parametrize('field,value',[('GoodFrames',1),('LastLines',719),('LastBytes',2558),
    ('BadFrames',1),('RawAuthorize',1),('Fault',0),('Fault',0xc4),('PCLKHalfPeriodPS',10582),('BadLineCase',1)])
def test_good_case_cannot_hide_bad_geometry_or_missing_clock_stop(field,value):
    with pytest.raises(ValueError):
        sim.observations('\n'.join(sim.GOOD_MARKERS),{**good(),field:value},11905,False)


def test_missing_sticky_resume_and_fatal_are_rejected():
    for log in ('\n'.join(sim.GOOD_MARKERS[:-1]),'\n'.join(sim.GOOD_MARKERS)+'\nFatal: model assertion'):
        with pytest.raises(ValueError):sim.observations(log,good(),11905,False)


def test_short_line_must_never_authorize_and_must_report_exact_fault():
    bad={**good(),'BadLineCase':1,'GoodFrames':0,'Fault':0x12,'PCLKHalfPeriodPS':10582}
    sim.observations(sim.BAD_MARKER,bad,10582,True)
    for field,value in [('GoodFrames',1),('RawAuthorize',1),('Fault',0xc0),('Configured',0)]:
        with pytest.raises(ValueError):sim.observations(sim.BAD_MARKER,{**bad,field:value},10582,True)
