"""T169: what the race's bloom program does with MRT1, with and without sRGB output, using the RSXI pass snapshot of
the baseline (B3 f002192) and the exact arithmetic of fp_0074B181: mean(t1)^2 * 16. Prints whole-surface luminance
inputs. usage: py -3 exposure_loop_t169.py <snap00_pass_op0547_rt_01650000.bmp>"""
import sys
import numpy as np
from PIL import Image


def enc(c):
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(np.maximum(c, 1e-9), 1 / 2.4) - 0.055)


a = np.asarray(Image.open(sys.argv[1]).convert('RGB')).astype(float) / 255.0
w = np.array([0.212646, 0.715332, 0.0722046])   # c4 of fp_0074C781
hdr = a * 16.0                                   # the scene colour the FP exported to MRT1 (t1 = colour / 16)
base = np.clip(a, 0, 1) ** 2 * 16
fixed = enc(np.clip(a, 0, 1)) ** 2 * 16
for name, v in (('scene colour (t1 * 16)', hdr), ('bloom input, baseline', base), ('bloom input, sRGB output', fixed)):
    l = v @ w
    print(f'{name:28s} mean lum {l.mean():7.3f}  geometric mean {np.exp(np.log(np.maximum(l, 1e-3)).mean()):7.3f}  p99 {np.percentile(l, 99):7.3f}')
print('baseline underestimates the geometric mean by', round(float(np.exp((np.log(np.maximum(hdr @ w, 1e-3)) - np.log(np.maximum(base @ w, 1e-3))).mean())), 2), 'x')
