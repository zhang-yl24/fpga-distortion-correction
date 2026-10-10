"""Synthetic geometry verifies the calibration tool, not physical lens accuracy."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import cv2
import pytest
from tools.calibrate import fit, validate

@pytest.mark.parametrize('model',['brown','fisheye'])
def test_fit_and_held_out_pose(model):
    world=np.zeros((1,54,3),dtype=np.float64)
    world[0,:,:2]=np.mgrid[0:9,0:6].T.reshape(-1,2)*0.03
    k=np.array([[410.,0,319.5],[0,405.,239.5],[0,0,1.]])
    d=np.array([-0.12,0.025,0.001,-0.001,0.002]) if model=='brown' else np.array([-0.04,0.01,-0.001,0.0001])
    project=cv2.projectPoints if model=='brown' else cv2.fisheye.projectPoints
    points=[]
    for i in range(20):
        r=np.array([0.14*(i%4-1.5),0.16*(i%5-2),0.04*(i%3-1)])
        t=np.array([-0.12+0.035*(i%5-2),-0.075+0.025*(i%4-1.5),0.52+0.035*(i%6)])
        image,_=project(world,r,t,k,d)
        points.append(image.reshape(1,-1,2))
    rms,found_k,found_d,_,_=fit([world]*16,points[:16],(640,480),model)
    error=validate([world]*4,points[16:],found_k,found_d,model)
    assert rms<0.01
    assert max(error)<0.01
    np.testing.assert_allclose(found_k,k,atol=0.1)
