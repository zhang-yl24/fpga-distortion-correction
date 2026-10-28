"""Small image-only checks for the current board-inspection helper."""
from pathlib import Path
import importlib.util
import cv2
import numpy as np
import pytest

spec = importlib.util.spec_from_file_location('view_check', Path(__file__).resolve().parents[1]/'tools/check_calibration_view.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def board():
    image = np.full((400, 520, 3), 240, dtype=np.uint8)
    for y in range(9):
        for x in range(12):
            image[60+y*28:60+(y+1)*28, 70+x*28:70+(x+1)*28] = 25 if (x+y)%2 else 230
    return image


def test_twelve_by_nine_squares_have_eighty_eight_inner_corners():
    result = module.inspect_image(board(), 11, 8)
    assert result['complete_board_detected'] and len(result['corners']) == 88
    assert sum(map(sum, result['source_image_3x3_corner_counts'])) == 88
    assert 27 < result['adjacent_corner_spacing_px']['median'] < 29
    assert result['board_edge_sharpness']['horizontal']['mean_10_90_transition_width_px'] < 3
    assert not result['calibration_ready']


def test_square_count_cannot_be_used_as_inner_corner_count():
    result = module.inspect_image(board(), 12, 9)
    assert not result['complete_board_detected'] and result['corners'] == []


def test_blur_increases_the_measured_board_edge_width():
    image = board()
    clear = module.inspect_image(image, 11, 8)
    blurred = module.inspect_image(cv2.GaussianBlur(image, (0, 0), 2), 11, 8)
    assert blurred['complete_board_detected']
    assert blurred['board_edge_sharpness']['horizontal']['mean_10_90_transition_width_px'] > clear['board_edge_sharpness']['horizontal']['mean_10_90_transition_width_px'] + 2
    assert blurred['warnings']


def test_missing_board_does_not_become_a_calibration_view():
    result = module.inspect_image(np.zeros((240, 320, 3), dtype=np.uint8), 11, 8)
    assert not result['complete_board_detected'] and not result['calibration_ready']


def test_explicit_counts_are_not_boolean_or_unbounded():
    for cols in (True, 0, 33):
        with pytest.raises(ValueError):
            module.inspect_image(board(), cols, 8)
