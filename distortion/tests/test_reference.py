import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
import pytest
from model.reference import inverse_map, remap_fixed, bilinear_u8


def test_identity_and_borders():
    img=np.arange(60,dtype=np.uint8).reshape(4,5,3)
    x,y=np.meshgrid(np.arange(5),np.arange(4))
    np.testing.assert_array_equal(remap_fixed(img,x,y),img)
    result=remap_fixed(np.full((2,2),100,dtype=np.uint8),
                       np.array([[-0.5,1.5,-2,3.0]]),np.array([[0.5,0.5,0,0]]))
    np.testing.assert_array_equal(result,[[50,50,0,0]])


def test_fraction_extremes_and_constant():
    f=np.arange(256)[:,None]
    g=np.arange(256)[None,:]
    out=bilinear_u8(255,255,255,255,f,g)
    assert np.all(out==255)
    assert int(bilinear_u8(0,255,255,0,128,128))==128
    assert int(bilinear_u8(19,200,100,255,0,0))==19


@pytest.mark.parametrize('model',['brown','fisheye'])
@pytest.mark.parametrize('angle',[0,17,-45,90])
def test_map_matches_direct_opencv_projection(model,angle):
    k=[[220,0,159.5],[0,225,119.5],[0,0,1]]
    d=[-0.18,0.04,0.001,-0.002,0.003] if model=='brown' else [-0.03,0.002,0.0001,0]
    calibration={'model':model,'image_size':[320,240],'K':k,'D':d}
    mx,my=inverse_map(calibration,angle_deg=angle)
    points=np.array([[0,0],[319,239],[160,120],[12,212]],dtype=float)
    a=np.deg2rad(angle); cx,cy=159.5,119.5
    u=np.cos(a)*(points[:,0]-cx)+np.sin(a)*(points[:,1]-cy)+cx
    v=-np.sin(a)*(points[:,0]-cx)+np.cos(a)*(points[:,1]-cy)+cy
    rays=(np.linalg.inv(np.array(k))@np.stack([u,v,np.ones(len(u))])).T.reshape(-1,1,3)
    project=cv2.fisheye.projectPoints if model=='fisheye' else cv2.projectPoints
    expected,_=project(rays,np.zeros(3),np.zeros(3),np.array(k,dtype=float),np.array(d))
    actual=np.stack([mx[points[:,1].astype(int),points[:,0].astype(int)],
                     my[points[:,1].astype(int),points[:,0].astype(int)]],axis=1)
    np.testing.assert_allclose(actual,expected.reshape(-1,2),atol=2e-5)


def test_mapping_quantization_against_float64_formula():
    rng=np.random.default_rng(20261004)
    img=rng.integers(0,256,(64,80,3),dtype=np.uint8)
    mx=rng.uniform(-2,82,(64,80)); my=rng.uniform(-2,66,(64,80))
    # Independent float oracle using the SAME quantized coordinates.
    qx=np.floor(mx*256+0.5)/256; qy=np.floor(my*256+0.5)/256
    expected=np.zeros((64,80,3),dtype=float)
    ix=np.floor(qx).astype(int); iy=np.floor(qy).astype(int)
    for dx,dy in ((0,0),(1,0),(0,1),(1,1)):
        xx,yy=ix+dx,iy+dy
        valid=(xx>=0)&(xx<80)&(yy>=0)&(yy<64)
        wx=(qx-ix) if dx else (1-(qx-ix))
        wy=(qy-iy) if dy else (1-(qy-iy))
        expected+=img[np.clip(yy,0,63),np.clip(xx,0,79)]*(wx*wy*valid)[...,None]
    np.testing.assert_array_equal(remap_fixed(img,mx,my),np.floor(expected+0.5).astype(np.uint8))


def test_nonfinite_rejected():
    with pytest.raises(ValueError): remap_fixed(np.zeros((2,2),np.uint8),np.array([[np.nan]]),np.zeros((1,1)))
