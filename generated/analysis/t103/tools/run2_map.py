"""T103: where are the even-phase duplicated pixel pairs? Prints a coarse grid
(cell = 80x45 px) of run-2 share for horizontal (H) and vertical (V) runs, and
the even/odd phase split of each. Usage: run2_map.py <bmp>"""
import sys
sys.path.insert(0, __file__.rsplit('\\', 1)[0].rsplit('/', 1)[0])
from bb_stats import load_bmp  # noqa: E402

p = sys.argv[1]
w, h, img = load_bmp(p)
CW, CH = 80, 45
gx, gy = w // CW, h // CH


def ok(c):
    return 8 <= max(c) < 255


for axis in ('H', 'V'):
    cnt = [[0] * gx for _ in range(gy)]
    tex = [[0] * gx for _ in range(gy)]
    even = odd = 0
    for y in range(1, h - 2):
        for x in range(1, w - 2):
            b = img[y][x]
            if not ok(b):
                continue
            if axis == 'H':
                a, c, d, k = img[y][x - 1], img[y][x + 1], img[y][x + 2], x
            else:
                a, c, d, k = img[y - 1][x], img[y + 1][x], img[y + 2][x], y
            tex[y // CH][x // CW] += 1
            if a != b and b == c and c != d:
                cnt[y // CH][x // CW] += 1
                if k & 1: odd += 1
                else: even += 1
    print(f"{axis}: even {even} odd {odd}  (share per cell x100, '.' = <50 textured px)")
    for j in range(gy):
        print(' '.join(f"{100*cnt[j][i]//tex[j][i]:3d}" if tex[j][i] >= 50 else '  .' for i in range(gx)))
