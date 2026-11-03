"""T107: sRGB transfer helpers shared by the T107 pixel tools (IEC 61966-2-1)."""


def s2l(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def l2s(v):
    v = min(max(v, 0.0), 1.0)
    return 255.0 * (v * 12.92 if v < 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055)
