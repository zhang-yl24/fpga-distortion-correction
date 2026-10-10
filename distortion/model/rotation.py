"""Independent fixed-point inverse-rotation and CORDIC parameter oracles."""
import math

def phase_from_degrees(angle):
    return math.floor(angle / 360 * (1 << 32) + .5) & 0xffffffff

def cordic(phase):
    z = phase if phase < (1 << 31) else phase - (1 << 32)
    negate = z > (1 << 30) or z < -(1 << 30)
    if negate:
        z = (phase - (1 << 31)) & 0xffffffff
        z = z if z < (1 << 31) else z - (1 << 32)
    x, y = 652032874, 0
    for i in range(24):
        delta = math.floor(math.atan(2**-i) / (2*math.pi) * (1 << 32) + .5)
        if z >= 0:
            x, y, z = x - (y >> i), y + (x >> i), z - delta
        else:
            x, y, z = x + (y >> i), y - (x >> i), z + delta
    return (-x, -y) if negate else (x, y)

def inverse_rotate(u, v, cx, cy, cosine, sine):
    x = ((cosine*(u-cx) + sine*(v-cy) + (1 << 29)) >> 30) + cx
    y = ((-sine*(u-cx) + cosine*(v-cy) + (1 << 29)) >> 30) + cy
    bad = not (-(1 << 23) <= x < (1 << 23) and -(1 << 23) <= y < (1 << 23))
    return (-(1 << 23), -(1 << 23), True) if bad else (x, y, False)
