"""Camera-model inverse maps and bit-exact sampling contract for the FPGA.

The final FPGA mapper must compute coordinates; this host map is an oracle.
Coordinates: signed pixel units, 8 fraction bits, nearest ties toward +infinity.
Border: each out-of-frame neighbour is zero (OpenCV BORDER_CONSTANT).
"""
import cv2
import numpy as np


def inverse_map(calibration, output_size=None, angle_deg=0.0):
    size = tuple(output_size or calibration['image_size'])
    k = np.array(calibration['K'], dtype=np.float64)
    d = np.array(calibration['D'], dtype=np.float64)
    new_k = np.array(calibration.get('output_K', calibration['K']), dtype=np.float64)
    if calibration['model'] == 'fisheye':
        mx, my = cv2.fisheye.initUndistortRectifyMap(k, d, np.eye(3), new_k, size, cv2.CV_32FC1)
    elif calibration['model'] == 'brown':
        mx, my = cv2.initUndistortRectifyMap(k, d, None, new_k, size, cv2.CV_32FC1)
    else:
        raise ValueError('model must be fisheye or brown')
    if angle_deg:
        # Compute a composed map by projecting the rotated output rays directly,
        # avoiding a second image-resampling pass.
        w, h = size
        x, y = np.meshgrid(np.arange(w), np.arange(h))
        a = np.deg2rad(angle_deg)
        u = np.cos(a)*(x-(w-1)/2) + np.sin(a)*(y-(h-1)/2) + (w-1)/2
        v = -np.sin(a)*(x-(w-1)/2) + np.cos(a)*(y-(h-1)/2) + (h-1)/2
        rays = np.linalg.inv(new_k) @ np.stack([u.ravel(), v.ravel(), np.ones(w*h)])
        points = rays.T.reshape(-1, 1, 3)
        if calibration['model'] == 'fisheye':
            projected, _ = cv2.fisheye.projectPoints(points, np.zeros(3), np.zeros(3), k, d)
        else:
            projected, _ = cv2.projectPoints(points, np.zeros(3), np.zeros(3), k, d)
        mx = projected[:, 0, 0].reshape(h, w).astype(np.float32)
        my = projected[:, 0, 1].reshape(h, w).astype(np.float32)
    return mx, my


def bilinear_u8(p00, p10, p01, p11, fx, fy):
    """Integer oracle; channels are handled independently, no intermediate round."""
    p00, p10, p01, p11 = [np.asarray(p, dtype=np.int64) for p in (p00,p10,p01,p11)]
    fx, fy = np.asarray(fx, dtype=np.int64), np.asarray(fy, dtype=np.int64)
    h0 = p00*(256-fx) + p10*fx
    h1 = p01*(256-fx) + p11*fx
    return ((h0*(256-fy) + h1*fy + 32768) >> 16).astype(np.uint8)


def remap_fixed(image, mx, my):
    if not (np.isfinite(mx).all() and np.isfinite(my).all()):
        raise ValueError('mapping coordinates must be finite')
    qx = np.floor(np.asarray(mx, dtype=np.float64)*256 + 0.5).astype(np.int64)
    qy = np.floor(np.asarray(my, dtype=np.float64)*256 + 0.5).astype(np.int64)
    ix, iy = qx >> 8, qy >> 8
    fx, fy = qx & 255, qy & 255
    h, w = image.shape[:2]
    def gather(dx, dy):
        xx, yy = ix+dx, iy+dy
        valid = (xx>=0)&(xx<w)&(yy>=0)&(yy<h)
        values = image[np.clip(yy,0,h-1), np.clip(xx,0,w-1)]
        return values * (valid[...,None] if image.ndim==3 else valid)
    if image.ndim == 3:
        fx, fy = fx[...,None], fy[...,None]
    return bilinear_u8(gather(0,0),gather(1,0),gather(0,1),gather(1,1),fx,fy)
