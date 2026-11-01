"""Invert a monotone four-coefficient fisheye polynomial on a declared forward domain.

Unlike OpenCV 4.11 undistortPoints this never clips distorted image radius to
pi/2. The physical ray angle is still strictly below pi/2. No rear rays,
out-of-domain extrapolation, skew, or automatic model/domain selection.
"""
import math
import cv2
import numpy as np

METHOD = 'bounded_monotone_bisection_v1'


def radial(theta, d):
    z = np.asarray(theta, dtype=np.float64)**2
    return theta*(1+z*(d[0]+z*(d[1]+z*(d[2]+z*d[3]))))


def domain(d, maximum_angle):
    d = np.asarray(d, dtype=np.float64).reshape(-1)
    if d.shape != (4,) or not np.isfinite(d).all():
        raise ValueError('four finite fisheye coefficients required')
    if (isinstance(maximum_angle, bool) or not isinstance(maximum_angle, (int, float))
            or not math.isfinite(maximum_angle) or not 0 < maximum_angle < 90):
        raise ValueError('forward angle must be finite and strictly between 0 and 90 degrees')
    theta = math.radians(maximum_angle)
    polynomial = np.array([1., 3*d[0], 5*d[1], 7*d[2], 9*d[3]])
    roots = np.polynomial.polynomial.polyroots(np.polynomial.polynomial.polyder(polynomial))
    candidates = [0., theta**2] + [float(z.real) for z in roots
        if abs(z.imag) < 1e-9 and 0 < z.real < theta**2]
    minimum = float(np.min(np.polynomial.polynomial.polyval(candidates, polynomial)))
    bound = float(radial(theta, d))
    if not math.isfinite(minimum) or minimum <= 1e-9 or not math.isfinite(bound) or bound <= 0:
        raise ValueError('fisheye radial polynomial must be strictly monotone on the entire declared domain')
    return {'method': METHOD, 'maximum_ray_angle_deg': float(maximum_angle),
        'maximum_distorted_radius': bound, 'minimum_radial_derivative': minimum,
        'iterations': 64, 'distorted_coordinates_clipped': False,
        'rear_hemisphere_supported': False}


def undistort_points(points, k, d, maximum_angle):
    audit = domain(d, maximum_angle)
    d = np.asarray(d, dtype=np.float64).reshape(4)
    k = np.asarray(k, dtype=np.float64)
    if (k.shape != (3, 3) or not np.isfinite(k).all() or min(k[0, 0], k[1, 1]) <= 0
            or not np.allclose(k[[0,1,2,2,2],[1,0,0,1,2]], [0,0,0,0,1], atol=1e-12, rtol=0)):
        raise ValueError('finite positive-focal zero-skew conventional intrinsics required')
    points = np.asarray(points, dtype=np.float64)
    if points.ndim < 2 or points.shape[-1] != 2 or not np.isfinite(points).all():
        raise ValueError('finite image points with final dimension 2 required')
    normalized = (points-k[:2, 2])/np.diag(k)[:2]
    radius = np.linalg.norm(normalized, axis=-1)
    boundary_roundoff = 16*np.finfo(np.float64).eps*(1+audit['maximum_distorted_radius'])
    if np.any(radius > audit['maximum_distorted_radius']+boundary_roundoff):
        raise ValueError('observed points outside declared forward inverse domain; no clipping or extrapolation')
    lo = np.zeros_like(radius)
    hi = np.full_like(radius, math.radians(maximum_angle))
    for _ in range(audit['iterations']):
        mid = (lo+hi)/2
        lower = radial(mid, d) < radius
        lo = np.where(lower, mid, lo)
        hi = np.where(lower, hi, mid)
    theta = (lo+hi)/2
    if np.any(np.abs(radial(theta, d)-radius) > 2e-12*(1+radius)):
        raise ValueError('bounded inverse did not meet radial round-trip tolerance')
    scale = np.divide(np.tan(theta), radius, out=np.ones_like(radius), where=radius != 0)
    result = normalized*scale[..., None]
    if not np.isfinite(result).all():
        raise ValueError('bounded inverse produced nonfinite rays')
    return result


def validate_pose(world, measured, k, d, maximum_angle):
    """Fix K/D and solve only one board pose; score in original source pixels."""
    rays = undistort_points(measured, k, d, maximum_angle)
    world = np.asarray(world, dtype=np.float64).reshape(-1, 3)
    ok, r, t = cv2.solvePnP(world, rays.reshape(-1, 1, 2), np.eye(3), None)
    if not ok or not np.isfinite(r).all() or not np.isfinite(t).all():
        raise ValueError('held-out pose solve failed')
    rotation, _ = cv2.Rodrigues(r)
    camera_points = world@rotation.T + t.reshape(1, 3)
    if np.any(camera_points[:, 2] <= 0):
        raise ValueError('board pose has points behind the camera')
    projected, _ = cv2.fisheye.projectPoints(world.reshape(1, -1, 3), r, t, k, d)
    delta = projected.reshape(-1, 2)-np.asarray(measured).reshape(-1, 2)
    return float(np.sqrt(np.mean(np.sum(delta**2, axis=1)))), rays
