"""Independent controlled optical blur tests for the image-quality gate."""
import importlib.util
from pathlib import Path
import cv2
import numpy as np

spec=importlib.util.spec_from_file_location('quality',Path(__file__).resolve().parents[1]/'tools/check-chessboard-sharpness.py')
quality=importlib.util.module_from_spec(spec);spec.loader.exec_module(quality)


def board():
    image=np.full((180,240),220,dtype=np.float32)
    for y in range(7):
        for x in range(10):image[20+y*20:40+y*20,20+x*20:40+x*20]=30 if (x+y)%2 else 220
    corners=np.array([[(40+x*20,40+y*20)] for y in range(6) for x in range(9)],dtype=np.float32)
    return image,corners


def test_sensor_noise_is_not_mistaken_for_blur():
    image,corners=board();image+=np.random.default_rng(8).normal(0,10,image.shape).astype(np.float32)
    result=quality.sharpness(image,corners)
    assert result['measured_edges']>=80 and not result['quality_rejected']
    assert result['median_20_80_edge_width_px']<2


def test_optical_defocus_is_rejected():
    image,corners=board();image=cv2.GaussianBlur(image,(0,0),3)
    result=quality.sharpness(image,corners)
    assert result['quality_rejected'] and result['median_20_80_edge_width_px']>3


def test_insufficient_contrast_cannot_pass():
    image,corners=board();image=image*.05+100
    assert quality.sharpness(image,corners)['quality_rejected']
