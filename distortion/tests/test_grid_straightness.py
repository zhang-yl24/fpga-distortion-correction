import importlib.util
from pathlib import Path
import unittest
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('grid_metric',ROOT/'tools/check-grid-straightness.py')
metric=importlib.util.module_from_spec(spec);spec.loader.exec_module(metric)

class GridTests(unittest.TestCase):
    def test_perspective_preserves_grid(self):
        xy=np.array([(x,y) for y in range(6) for x in range(9)])
        H=np.array([[18,3,180],[2,19,130],[.025,.018,1]])
        q=np.c_[xy,np.ones(54)]@H.T;q=q[:,:2]/q[:,2,None]
        self.assertLess(metric.grid_residual(q)['equal_line_rms_px'],1e-10)
    def test_curved_grid_detected(self):
        xy=np.array([(20*x,20*y) for y in range(6) for x in range(9)],dtype=float)
        xy[:,1]+=.002*(xy[:,0]-80)**2
        self.assertGreater(metric.grid_residual(xy)['equal_line_rms_px'],1)
    def test_scale_normalization(self):
        xy=np.array([(20*x,20*y) for y in range(6) for x in range(9)],dtype=float)
        xy[:,1]+=.002*(xy[:,0]-80)**2
        a=metric.grid_residual(xy);b=metric.grid_residual(xy*3+17)
        self.assertAlmostEqual(b['equal_line_rms_px'],a['equal_line_rms_px']*3)
        self.assertAlmostEqual(b['equal_line_rms_fraction_of_span'],a['equal_line_rms_fraction_of_span'])
    def test_degenerate_rejected(self):
        with self.assertRaises(ValueError):metric.line_residual([[0,0]]*5)

if __name__=='__main__':unittest.main()
