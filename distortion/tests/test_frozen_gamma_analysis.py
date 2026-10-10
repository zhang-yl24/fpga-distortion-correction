from pathlib import Path
import sys,unittest,zlib
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from frame_protocol import Frame
from gamma_triplets import GammaTriplet
from frozen_gamma_analysis import analyze,geometry

IDENTITY = [0,0,0,0,256,256,1<<30,1<<30,0,0,0,0,0]


def triplet(pixel,mode):
    before=np.full((4,8),pixel,dtype=np.uint16)
    exponent=(1,.65,1.45)[mode]
    t5=np.array([round((v/31)**exponent*31) for v in range(32)],dtype=np.uint16)
    t6=np.array([round((v/63)**exponent*63) for v in range(64)],dtype=np.uint16)
    after=(t5[before>>11]<<11)|(t6[(before>>5)&63]<<5)|t5[before&31]
    def packet(kind,value):
        payload=value.astype('<u2').tobytes()
        return Frame(8,4,16|((mode<<2) if kind==2 else 0)|kind,zlib.crc32(payload),payload)
    return GammaTriplet(1,mode,packet(0,before),packet(1,before),packet(2,after))


class AnalysisTests(unittest.TestCase):
    def test_dark_bright_neutral_exact_comparison(self):
        coords,mask=geometry(IDENTITY,8,4,0)
        for pixel,mode in ((0x1081,1),(0xffff,2),(0x7bef,0)):
            with self.subTest(mode=mode):
                result,_=analyze(triplet(pixel,mode),coords,mask,'synthetic_same_source')
                self.assertTrue(result['passed'])
                self.assertEqual(result['bypass_mismatched_pixels'],0)
                self.assertEqual(result['tone']['mismatched_pixels'],0)

    def test_mask_uses_geometry_not_black_pixel(self):
        coords,mask=geometry(IDENTITY,8,4,0)
        result,_=analyze(triplet(0,1),coords,mask,'synthetic_same_source')
        self.assertTrue(result['passed'])
        self.assertEqual(result['tone']['valid_samples'],32)

    def test_radius_boundary(self):
        coords,mask=geometry(IDENTITY,8,4,1<<22)
        self.assertFalse(mask[0,0]);self.assertFalse(mask[0,1]);self.assertFalse(mask[1,0])
        self.assertTrue(mask[1,1]);self.assertTrue(mask[0,2])
        self.assertEqual(coords[1,1,0],-(1<<23))

    def test_consistent_crc_does_not_hide_wrong_pixels(self):
        coords,mask=geometry(IDENTITY,8,4,0)
        t=triplet(0x1081,1)
        wrong=bytearray(t.before.payload);wrong[0]^=1
        t.before.payload=bytes(wrong);t.before.source_crc=zlib.crc32(wrong)
        result,_=analyze(t,coords,mask,'synthetic_same_source')
        self.assertFalse(result['passed']);self.assertEqual(result['bypass_mismatched_pixels'],1)

    def test_wrong_decision_is_failure_even_if_curve_matches(self):
        coords,mask=geometry(IDENTITY,8,4,0)
        result,_=analyze(triplet(0x1081,0),coords,mask,'synthetic_same_source')
        self.assertFalse(result['passed']);self.assertTrue(result['tone']['exact_tone_pixels_passed'])

    def test_untrusted_group_label_rejected(self):
        coords,mask=geometry(IDENTITY,8,4,0)
        t=triplet(0x1081,1);t.group_id=2
        with self.assertRaises(ValueError):analyze(t,coords,mask,'synthetic_same_source')

    def test_shape_mismatch_rejected(self):
        coords,mask=geometry(IDENTITY,7,4,0)
        with self.assertRaises(ValueError):analyze(triplet(0x1081,1),coords,mask,'synthetic_same_source')


if __name__=='__main__':unittest.main()
