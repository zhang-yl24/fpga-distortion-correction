from pathlib import Path
import struct
import sys
import zlib

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import hdmi_camera_fisheye_fps as fps


def packet(sequence=0,ticks=125000000,counters=None,flags=6):
    values=[60,12,5,4,30,25000000,1000,300,1300,20,10,0]
    if counters is not None:values=counters
    raw=fps.PACKET.pack(fps.MAGIC,2,flags,96,sequence,ticks,*values,0,0,fps.PROFILE_ID,fps.BUILD_ID,0)
    return raw[:92]+struct.pack('<I',zlib.crc32(raw[:92]))


def test_uart_layout_matches_production_offsets():
    p=fps.Parser();f=p.feed(packet())[0]
    assert fps.PACKET.size==96 and p.rejected==0 and f['source_frames']==60
    assert f['captured_frames']==12 and f['processed_frames']==5 and f['scan_refreshes']==30
    assert f['last_process_cycles']==25000000 and f['queries']==1300
    assert f['status_valid']and f['corrected_requested']and not f['failed']


@pytest.mark.parametrize('byte',[0,8,9,10,12,16,24,48,76,80,88,92,95])
def test_crc_corruption_recovers_in_arbitrary_chunks(byte):
    bad=bytearray(packet());bad[byte]^=0x80
    wire=b'partial old telemetry'+bad+packet(1,250000000)
    p=fps.Parser();out=[]
    for pos in range(0,len(wire),7):out+=p.feed(wire[pos:pos+7])
    assert len(out)==1 and out[0]['sequence']==1


def test_wrong_profile_rejected_even_with_recomputed_crc():
    raw=bytearray(packet());raw[80]^=1;raw[92:]=struct.pack('<I',zlib.crc32(raw[:92]))
    p=fps.Parser();assert p.feed(raw)==[]and p.rejected==1


def test_refresh_and_new_frame_rates_remain_separate():
    counts=[660,132,55,44,330,25000000,11000,3300,14300,220,110,0]
    p=fps.Parser();f=p.feed(packet()+packet(10,1375000000,counts))
    s=fps.summarize(f)
    assert s['hardware_window_seconds']==10
    assert s['source_frames_per_second']==60 and s['scan_refreshes_per_second']==30
    assert s['processed_frames_per_second']==5 and s['unique_presented_frames_per_second']==4
    assert s['last_process_seconds']==.2


def test_counter_wrap_is_valid_but_timer_reset_is_rejected():
    start=[0xfffffff0]*12;end=[4]*12
    f=fps.Parser().feed(packet(counters=start)+packet(1,250000000,end))
    assert fps.summarize(f)['processed_frames_per_second']==20
    f[1]['core_ticks']=1
    with pytest.raises(ValueError,match='reset'):fps.summarize(f)


@pytest.mark.parametrize('flags',[2,7])
def test_mode_changes_or_pipeline_failure_invalidate_window(flags):
    f=fps.Parser().feed(packet()+packet(1,250000000,flags=flags))
    with pytest.raises(ValueError):fps.summarize(f)
