import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from slanted_edge_analysis import measure,capture_pixels
import numpy as np
from scipy.special import erf

def edge(sigma=1.5,angle=5,phase=.23):
    y,x=np.mgrid[:128,:128];s=np.tan(np.deg2rad(angle))
    d=(x-64-s*(y-64)-phase)/np.sqrt(1+s*s)
    return 30+180*.5*(1+erf(d/(np.sqrt(2)*sigma)))

class SlantedEdgeTests(unittest.TestCase):
    def test_known_gaussian_transfer(self):
        for sigma in (1,1.5,2,3):
            with self.subTest(sigma=sigma):
                actual=measure(edge(sigma))['mtf50_cycles_per_pixel']
                truth=np.sqrt(np.log(2))/(np.sqrt(2)*np.pi*sigma)
                self.assertLess(abs(actual-truth)/truth,.05)
    def test_more_blur_reduces_mtf(self):
        self.assertGreater(measure(edge(1))['mtf50_cycles_per_pixel'],measure(edge(2))['mtf50_cycles_per_pixel'])
    def test_phase_and_transpose(self):
        a=measure(edge(phase=0))['mtf50_cycles_per_pixel']
        b=measure(edge(phase=.6).T)['mtf50_cycles_per_pixel']
        self.assertLess(abs(a-b)/a,.025)
    def test_reverse_contrast(self):
        a=edge();self.assertAlmostEqual(measure(a)['mtf50_cycles_per_pixel'],measure(255-a)['mtf50_cycles_per_pixel'],places=8)
    def test_flat_roi_rejected(self):
        with self.assertRaises(ValueError):measure(np.full((128,128),80))
    def test_bad_slant_rejected(self):
        for angle in (0,15):
            with self.subTest(angle=angle),self.assertRaises(ValueError):measure(edge(angle=angle))
    def test_invalid_roi_rejected(self):
        for image in (np.zeros((16,16)),np.full((128,128),np.nan)):
            with self.assertRaises(ValueError):measure(image)
    def test_clipped_edge_rejected(self):
        a=edge();a=(a-a.min())/(a.max()-a.min())*255
        with self.assertRaises(ValueError):measure(a)
    def test_curved_edge_rejected(self):
        y,x=np.mgrid[:128,:128];s=np.tan(np.deg2rad(5))
        d=x-64-s*(y-64)-3*np.sin(y/18)
        a=30+90*(1+erf(d/(np.sqrt(2)*1.5)))
        with self.assertRaises(ValueError):measure(a)
    def test_internal_pattern_is_not_optical(self):
        group=Path(__file__).resolve().parents[1]/'captures/gamma-triplets/sensor-colorbars-d5-fixed-20261008/group-00000001'
        with self.assertRaises(ValueError):capture_pixels(group,'raw',[0,0,128,128])

if __name__=='__main__':unittest.main()
