r"""Offline preview of the scene pass's colour grading (RSX_FX_GRADE) on a saved shot: the same white balance, saturation,
contrast and built-in tropical LUT math as rsx_vk_scenefx.comp / vk_fx_lut_build, applied to the whole frame (the HUD too,
which the game's pass would not touch). usage: py -3 grade_preview.py <shot> <out.png> [sat] [contrast] [wb_temp]"""
import sys
import numpy as np
from PIL import Image

def s2l(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def l2s(c): return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.maximum(c, 1e-9), 1 / 2.4) - 0.055)
def tropical(c):
    y = c @ np.array([0.2126, 0.7152, 0.0722])
    hi = (y * y * (3 - 2 * y))[..., None]; lo = 1 - hi
    c = c + hi * np.array([0.035, 0.010, -0.030]) + lo * np.array([-0.015, 0.005, 0.020])
    yy = (c @ np.array([0.2126, 0.7152, 0.0722]))[..., None]
    v = yy + (c - yy) * 1.08
    v = v + 0.06 * (v - 0.45) * (1 - np.abs(2 * v - 1))
    return np.clip(v, 0, 1)
src = np.asarray(Image.open(sys.argv[1]).convert('RGB'), dtype=np.float32) / 255
sat = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
con = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
t = float(sys.argv[5]) if len(sys.argv) > 5 else 0.0
wb = np.array([1 + 0.12 * t, 1.0, 1 - 0.12 * t])
c = l2s(np.clip(s2l(src) * wb, 0, 1))
y = (c @ np.array([0.2126, 0.7152, 0.0722]))[..., None]
c = np.clip((y + (c - y) * sat - 0.45) * con + 0.45, 0, 1)
c = tropical(c)
both = np.concatenate([src, c], axis=1)
Image.fromarray((both * 255 + 0.5).astype(np.uint8)).resize((both.shape[1] // 2, both.shape[0] // 2)).save(sys.argv[2])
ys, yd = (src @ np.array([0.2126, 0.7152, 0.0722])).mean() * 255, (c @ np.array([0.2126, 0.7152, 0.0722])).mean() * 255
print(f'mean luma {ys:.1f} -> {yd:.1f}; saved {sys.argv[2]} (left before, right after)')
