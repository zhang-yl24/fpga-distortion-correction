from pathlib import Path
import sys,unittest,zlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from frame_protocol import Frame,FrameParser,encode
from gamma_triplets import GammaTripletAssembler


def frame(kind, mode=0, group=1, payload=b'\x00\x00'):
    return Frame(1,1,(group<<4)|(mode<<2)|kind,zlib.crc32(payload),payload)


class TripletTests(unittest.TestCase):
    def test_complete_chunked_crc_stream(self):
        stream=b''.join(encode(1,1,f.frame_id,f.payload) for f in (frame(0),frame(1),frame(2,mode=2)))
        parser=FrameParser();assembler=GammaTripletAssembler();results=[]
        for i in range(0,len(stream),7):
            for packet in parser.feed(stream[i:i+7]):
                result=assembler.feed(packet)
                if result:results.append(result)
        self.assertEqual(len(results),1);self.assertEqual(results[0].mode,2)
        self.assertEqual(parser.rejected,0);self.assertEqual(assembler.completed_groups,1)

    def test_incomplete_source_does_not_become_pair(self):
        a=GammaTripletAssembler();a.feed(frame(0));a.feed(frame(1));a.finish()
        self.assertEqual(a.completed_groups,0);self.assertEqual(a.incomplete_groups,1)

    def test_orphan_ignored_until_source(self):
        a=GammaTripletAssembler();self.assertIsNone(a.feed(frame(2,mode=1)))
        self.assertEqual(a.orphan_packets,1);self.assertEqual(a.completed_groups,0)

    def test_duplicate_rejected(self):
        a=GammaTripletAssembler();a.feed(frame(0))
        with self.assertRaises(ValueError):a.feed(frame(0))

    def test_cross_group_rejected(self):
        a=GammaTripletAssembler();a.feed(frame(0))
        with self.assertRaises(ValueError):a.feed(frame(1,group=2))

    def test_out_of_order_rejected(self):
        a=GammaTripletAssembler();a.feed(frame(0))
        with self.assertRaises(ValueError):a.feed(frame(2))

    def test_invalid_mode_rejected(self):
        for packet in (frame(0,mode=1),frame(2,mode=3),frame(3)):
            with self.assertRaises(ValueError):GammaTripletAssembler().feed(packet)

    def test_corrupt_payload_rejected(self):
        f=frame(0);f.source_crc^=1
        with self.assertRaises(ValueError):GammaTripletAssembler().feed(f)

    def test_replacement_drops_partial_group(self):
        a=GammaTripletAssembler();a.feed(frame(0));a.feed(frame(0,group=2))
        self.assertEqual(a.incomplete_groups,1);self.assertEqual(a.completed_groups,0)


if __name__=='__main__':unittest.main()
