"""py -3 -I test_rider_eye.py: rider_eye reads a synthetic vehicle node block and places the eye from the hands."""
import struct
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from rider_eye import eye_camera, node_positions


def mat(tx, ty, tz):
    return struct.pack('>16f', 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, tx, ty, tz, 1)


def package(names, mats, stray=False):
    """matrices, a hash-table gap, the name table (optionally one stray name after the nodes), a header"""
    table = b'\x00'.join(n.encode() for n in names + (['STRAY_NAME'] if stray else [])) + b'\x00\x00>EVOSBIG \x00'
    return b'\x11' * 7 + b''.join(mats) + b'\xaa' * 40 + table


NAMES = ['|BODY_COL', '|BODY_COL|BODY', '|BODY_COL|BODY|HANDLE_BARS', '|BODY_COL|BODY|HANDLE_BARS|left_hand',
         '|BODY_COL|BODY|HANDLE_BARS|right_hand']
MATS = [mat(0, 0.5, 0), mat(0, 0, 0), mat(0, 1.0, 0.3), mat(0.35, 0.2, -0.1), mat(-0.35, 0.2, -0.1)]

for stray in (False, True):
    p = node_positions(package(NAMES, MATS, stray))
    assert len(p) == 5, (stray, len(p))
    lh = p['|BODY_COL|BODY|HANDLE_BARS|left_hand']
    assert all(abs(a - b) < 1e-5 for a, b in zip(lh, (0.35, 1.7, 0.2))), lh
    # hands at x +-0.35 (mean 0), y 1.7 - BODY_COL 0.5 = 1.2 (+ up 0.45), z 0.2 (camera z = -(0.2 - back 0.45) = 0.25)
    e = eye_camera(p, 0.45, 0.45)
    assert e is not None and abs(e[0]) < 1e-6 and abs(e[1] - 1.65) < 1e-6 and abs(e[2] - 0.25) < 1e-6, e

assert node_positions(b'no nodes here') == {}
assert eye_camera({'|BODY_COL': (0, 0, 0)}, 0.4, 0.4) is None          # no hands: the caller keeps the default
print('test_rider_eye: OK')
