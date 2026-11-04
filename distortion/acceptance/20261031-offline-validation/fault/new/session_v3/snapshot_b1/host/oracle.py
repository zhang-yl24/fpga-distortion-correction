"""Independent golden-image oracle. No imports from packet decoder/cycle model.

Uses the standard-library zlib implementation, not the RTL-style bit recurrence.
Input is a known expected image; do not generate the golden from readback bytes.
"""
from pathlib import Path
import zlib

def coordinates(width, height):
    if width < 4 or height < 4:
        raise ValueError('minimum supported golden geometry is 4x4')
    return ((0, 0), (width-1, 0), (0, height-1), (width-1, height-1),
            (width//2, height//2), (width//2-1, height//2),
            (width//2, height//2-1), (1, 1))

def expand_rgb565(data):
    if len(data) % 2:
        raise ValueError('RGB565 source must have an even byte count')
    out = bytearray()
    for i in range(0, len(data), 2):
        p = data[i] | (data[i+1] << 8)
        r, g, b = (p >> 11) & 31, (p >> 5) & 63, p & 31
        out.extend(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)))
    return bytes(out)

def signature(rgb888, width, height):
    if len(rgb888) != width * height * 3:
        raise ValueError('golden must contain exactly WIDTH*HEIGHT RGB888 pixels')
    samples = []
    for x, y in coordinates(width, height):
        offset = 3 * (y*width+x)
        samples.append((x, y, *rgb888[offset:offset+3]))
    return {'width': width, 'height': height, 'pixel_count': width*height,
            'pixel_crc': zlib.crc32(rgb888), 'samples': tuple(samples)}

def from_file(path, width, height, fmt='rgb888'):
    raw = Path(path).read_bytes()
    return signature(expand_rgb565(raw) if fmt == 'rgb565le' else raw, width, height)
