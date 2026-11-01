"""Independent OpenCV forward projection checks for bounded inverse geometry."""
from pathlib import Path
import sys
import math
import copy
import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import fisheye_forward_inverse as inv
from tools.calibrate_fisheye_profile import _domain, calibrate_observations
from test_calibrate_fisheye_profile import synthetic_dataset

K = np.array([[159., 0, 321.], [0, 160., 250.], [0, 0, 1.]])
D = np.array([.176, -.0101, -.0131, .0022])


def test_forward_roundtrip_across_radius_clip_boundary_and_center():
    angle = np.radians(np.linspace(0, 87.9, 61))
    azimuth = np.linspace(-math.pi, math.pi, 47)
    aa, pp = np.meshgrid(angle, azimuth)
    rays = np.stack([np.tan(aa)*np.cos(pp), np.tan(aa)*np.sin(pp), np.ones_like(aa)], axis=-1).reshape(-1, 1, 3)
    pixels, _ = cv2.fisheye.projectPoints(rays, np.zeros(3), np.zeros(3), K, D)
    recovered = inv.undistort_points(pixels, K, D, 88)
    np.testing.assert_allclose(recovered, rays[..., :2], rtol=1e-10, atol=1e-10)
    assert np.any(np.linalg.norm((pixels-K[:2,2])/np.diag(K)[:2], axis=-1) > math.pi/2)
    projected, _ = cv2.fisheye.projectPoints(np.concatenate([recovered, np.ones_like(recovered[..., :1])],axis=-1),
                                          np.zeros(3),np.zeros(3),K,D)
    np.testing.assert_allclose(projected,pixels,atol=1e-9,rtol=0)


def test_agrees_with_opencv_inside_its_supported_radius():
    rays=np.array([[[-.7,.3,1]], [[.2,.8,1]], [[0.,0.,1.]], [[1.1,-.2,1.]]])
    pixels,_=cv2.fisheye.projectPoints(rays,np.zeros(3),np.zeros(3),K,D)
    actual=inv.undistort_points(pixels,K,D,88)
    np.testing.assert_allclose(actual,cv2.fisheye.undistortPoints(pixels,K,D),atol=1e-8)


def test_known_far_off_axis_board_pose():
    world=np.zeros((1,54,3),np.float64)
    world[0,:,:2]=np.mgrid[0:6,0:9].T.reshape(-1,2)*10
    r=np.array([.1,-.15,.04]);t=np.array([620.,-40.,80.])
    pixels,_=cv2.fisheye.projectPoints(world,r,t,K,D)
    error,_=inv.validate_pose(world,pixels,K,D,88)
    assert error<1e-5
    assert np.linalg.norm((pixels-K[:2,2])/np.diag(K)[:2],axis=-1).max()>math.pi/2


@pytest.mark.parametrize('angle',[0,90,100,float('nan'),True])
def test_bad_angle_rejected(angle):
    with pytest.raises(ValueError):inv.domain(D,angle)


def test_nonmonotonic_and_near_zero_derivative_rejected():
    with pytest.raises(ValueError,match='monotone'):inv.domain([-1,0,0,0],88)
    # Derivative is (1-theta^2)^2, touches zero at theta=1 inside the interval.
    with pytest.raises(ValueError,match='monotone'):inv.domain([-2/3,1/5,0,0],88)


def test_outside_domain_rejected_without_clipping():
    rays=np.array([[[math.tan(math.radians(88.1)),0.,1.]]])
    pixels,_=cv2.fisheye.projectPoints(rays,np.zeros(3),np.zeros(3),K,D)
    with pytest.raises(ValueError,match='outside'):inv.undistort_points(pixels,K,D,88)


def test_exact_domain_boundary_and_tiny_radius():
    angle=math.radians(88)
    azimuth=np.linspace(-math.pi,math.pi,53)
    rays=np.stack([math.tan(angle)*np.cos(azimuth),math.tan(angle)*np.sin(azimuth),
                   np.ones_like(azimuth)],axis=-1).reshape(-1,1,3)
    rays=np.concatenate([rays,np.array([[[1e-12,-1e-12,1.]],[[0.,0.,1.]]])])
    pixels,_=cv2.fisheye.projectPoints(rays,np.zeros(3),np.zeros(3),K,D)
    np.testing.assert_allclose(inv.undistort_points(pixels,K,D,88),rays[...,:2],atol=1e-10,rtol=1e-10)


def test_invalid_intrinsics_or_pixels_rejected():
    bad=K.copy();bad[0,1]=.1
    with pytest.raises(ValueError):inv.undistort_points(np.array([[[321.,250.]]]),bad,D,88)
    with pytest.raises(ValueError):inv.undistort_points(np.array([[[float('nan'),250.]]]),K,D,88)


def test_explicit_inverse_gate_preserves_default():
    assert not _domain(K,D,(640,480),88)['supported_forward_domain_passed']
    result=_domain(K,D,(640,480),88,inv.METHOD)
    assert result['supported_forward_domain_passed']
    assert result['bounded_inverse_audit']['distorted_coordinates_clipped'] is False


def test_opt_in_profile_scope_and_heldout_isolation():
    manifest, observations, k,d=synthetic_dataset()
    manifest['model_scope']['inverse_method']=inv.METHOD
    manifest['model_scope']['physical_visibility']={'record':{'FullFrameCoverageClaimAllowed':False,'ExcludedCoverageCells':[[2,2]]}}
    clean=calibrate_observations(manifest,observations)
    assert clean['passed'] and not clean['candidate_ready_for_profile_review']
    assert clean['model_scope']==manifest['model_scope']
    np.testing.assert_allclose(clean['K'],k,atol=1e-4)
    np.testing.assert_allclose(clean['D'],d,atol=1e-5)
    bad=copy.deepcopy(observations);bad[-1]['corners'][0,13]+=[30.,-25.]
    changed=calibrate_observations(manifest,bad)
    np.testing.assert_array_equal(changed['K'],clean['K'])
    np.testing.assert_array_equal(changed['D'],clean['D'])
    assert not changed['passed'] and changed['held_out_max_rms_px']>1
