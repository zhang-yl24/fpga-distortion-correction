"""New-build identity, frame-rate accounting, corruption and wrap checks."""
import struct,sys,unittest,zlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import hdmi_camera_fisheye_fps as fps

def packet(sequence=0,ticks=125000000,counters=None,build=None,profile=None,flags=6):
    values=counters or [60,60,60,59,60,1800000,1000,300,1300,60,1,0]
    raw=fps.PACKET.pack(fps.MAGIC,2,flags,96,sequence,ticks,*values,0,0,
                        fps.PROFILE_ID if profile is None else profile,
                        fps.BUILD_ID if build is None else build,0)
    return raw[:92]+struct.pack('<I',zlib.crc32(raw[:92]))

class Protocol(unittest.TestCase):
    def test_new_identity(self):
        self.assertEqual(fps.BUILD_ID,0x11036003)
        frame=fps.Parser().feed(packet())[0]
        self.assertEqual(frame['build_id'],'11036003')
        self.assertEqual(frame['profile_id'],'ed59f83e3cfbc77b')

    def test_explicit_candidate_requires_exact_identity(self):
        self.assertEqual(len(fps.SUPPORTED_BUILD_IDS),24)
        for selected in sorted(fps.SUPPORTED_BUILD_IDS):
            p=fps.Parser(selected)
            self.assertEqual(len(p.feed(packet(build=selected))),1)
            wrong=0x11036009 if selected!=0x11036009 else fps.BUILD_ID
            self.assertEqual(p.feed(packet(build=wrong)),[])
            self.assertEqual(p.rejected,1)
            self.assertEqual(fps.build_id_argument(f'{selected:08x}'),selected)
        for invalid in (0x11036001,0x11030001,0,0xffffffff,-1,True):
            with self.assertRaises(ValueError):fps.Parser(invalid)

    def test_summary_rejects_mixed_or_unselected_identity(self):
        selected=0x11036009
        frames=fps.Parser(selected).feed(packet(build=selected)+packet(1,250000000,build=selected))
        self.assertEqual(fps.summarize(frames,selected)['expected_build_id'],'11036009')
        with self.assertRaisesRegex(ValueError,'identity'):fps.summarize(frames)
        frames[1]['build_id']='11036002'
        with self.assertRaisesRegex(ValueError,'identity'):fps.summarize(frames,selected)
        frames[1]['build_id']='11036009';frames[1]['profile_id']='0000000000000000'
        with self.assertRaisesRegex(ValueError,'identity'):fps.summarize(frames,selected)

    def test_old_build_and_different_calibration_rejected(self):
        for data in [packet(build=0x11030001),packet(build=0x11036002),packet(profile=fps.PROFILE_ID^1)]:
            p=fps.Parser();self.assertEqual(p.feed(data),[]);self.assertEqual(p.rejected,1)

    def test_refresh_does_not_hide_repeated_frames(self):
        a=[60,60,50,48,60,1800000,1000,300,1300,60,12,0]
        b=[660,660,550,528,660,1800000,11000,3300,14300,660,132,0]
        frames=fps.Parser().feed(packet(counters=a)+packet(10,1375000000,b))
        summary=fps.summarize(frames)
        self.assertEqual(summary['scan_refreshes_per_second'],60)
        self.assertEqual(summary['processed_frames_per_second'],50)
        self.assertEqual(summary['unique_presented_frames_per_second'],48)
        self.assertEqual(summary['scan_repeat_frames_per_second'],12)

    def test_fragmented_corruption_recovers(self):
        for index in [0,8,9,10,12,16,24,48,76,80,88,92,95]:
            bad=bytearray(packet());bad[index]^=0x80
            data=b'noise'+bad+packet(1,250000000);parser=fps.Parser();frames=[]
            for offset in range(0,len(data),7):frames.extend(parser.feed(data[offset:offset+7]))
            self.assertEqual(len(frames),1);self.assertEqual(frames[0]['sequence'],1)

    def test_counter_wrap_and_epoch_rejection(self):
        frames=fps.Parser().feed(packet(counters=[0xfffffff0]*12)+packet(1,250000000,[4]*12))
        self.assertEqual(fps.summarize(frames)['processed_frames_per_second'],20)
        frames[-1]['core_ticks']=1
        with self.assertRaises(ValueError):fps.summarize(frames)

    def test_mode_or_fault_changes_invalidate_measurement(self):
        for flag in (2,7):
            frames=fps.Parser().feed(packet()+packet(1,250000000,flags=flag))
            with self.assertRaises(ValueError):fps.summarize(frames)

if __name__=='__main__':unittest.main()
