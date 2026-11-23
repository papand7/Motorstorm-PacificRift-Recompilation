r"""Offline preview of RSX_FX_FOG (the height fog of rsx_vk_scenefx.comp, pass 2) on existing enhanced-mode shots.
The shots have no depth, so the distance is a HYPOTHESIS: flat ground at 2 m below a camera with a 50 degree vertical
field, the horizon at the centre row; above the horizon, pixels that are not blue count as far geometry (300 m) and blue
ones as sky (6000 m, x0.35 as the shader). The fog math and the sky-colour blend follow the shader; the sun's scatter
and the shafts (which need the depth of the occluders) are not modelled: their bound is printed instead.
usage: py -3 -I fog_preview.py <out_dir> <shot.bmp> [<shot.bmp> ...]"""
import sys, pathlib, math
import numpy as np
from PIL import Image

D0, FALLOFF, BASE_REL, SCAT, WARM = 0.0010, 0.03, -15.0, 0.6, 0.6
TINT = np.array([0.78, 0.74, 0.66])
CAM_H, FOV_V = 2.0, math.radians(50.0)
SKY_DIST, SKY_K = 6000.0, 0.35


def s2l(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def l2s(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1.0 / 2.4) - 0.055)


def run(path, out):
    img = np.asarray(Image.open(path).convert('RGB'), dtype=np.float64) / 255.0
    H, W, _ = img.shape
    f = (H * 0.5) / math.tan(FOV_V * 0.5)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    dx, dy, dz = (xx + 0.5 - W * 0.5) / f, -(yy + 0.5 - H * 0.5) / f, np.ones_like(xx)
    n = np.sqrt(dx * dx + dy * dy + dz * dz)
    dx, dy = dx / n, dy / n
    below = dy < -1e-4
    dist_ground = np.where(below, CAM_H / np.maximum(-dy, 1e-6), 0.0)
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    blue = (b - r > 0.05) & (b >= g * 0.95) & (yy < H * 0.6)
    sky = (~below) & blue
    dist = np.where(below, dist_ground, np.where(sky, SKY_DIST, 300.0))
    # the shader: od = d0 exp(-k y0) dist integ, y0 = cam.y - (cam.y + base) = -base
    k, y0 = FALLOFF, CAM_H   # world base = the ground plane (y 0), camera CAM_H above it
    e = k * dy * dist
    integ = np.where(np.abs(e) > 1e-4, (1.0 - np.exp(-e)) / np.where(np.abs(e) > 1e-4, e, 1.0), 1.0)
    od = np.maximum(D0 * math.exp(-k * y0) * dist * integ, 0.0)
    fogf = 1.0 - np.exp(-od)
    fogf = np.where(sky, fogf * SKY_K, fogf)
    lin = s2l(img)
    sky_mean_lin = lin[sky].mean(axis=0) if sky.any() else np.array([0.78, 0.74, 0.66])
    hc = l2s(sky_mean_lin)                       # the fog colour: the sky average (sRGB), as FogColour
    lw = np.array([0.2126, 0.7152, 0.0722])
    tint = np.clip(TINT * (hc @ lw) / max(TINT @ lw, 0.05), 0, 1)
    h = np.where(sky, 1e4, CAM_H + dy * dist)                 # height above the base
    warm = WARM * np.exp(-k * np.maximum(h, 0.0))
    fc = np.where(sky[..., None], hc, hc * (1 - warm[..., None]) + tint * warm[..., None])
    out_img = img * (1.0 - fogf[..., None]) + fc * fogf[..., None]
    ground = below & ~sky
    def stats(a, m):
        if not m.any():
            return None
        px = a[m]
        chroma = (px.max(axis=1) - px.min(axis=1)).mean() * 255.0
        return px.mean(axis=0) * 255.0, px.mean() * 255.0, chroma
    res = {}
    for name, m in (('sky', sky), ('ground', ground), ('all', np.ones_like(sky))):
        res[name] = (stats(img, m), stats(out_img, m))
    # the shafts' bound: at most 0.12 of sun light (display), halved on sky, gated off above luma 0.85
    shaft_bound = 0.10 * 255.0
    pathlib.Path(out).mkdir(parents=True, exist_ok=True)
    stem = pathlib.Path(path).stem + '_' + pathlib.Path(path).parent.name
    Image.fromarray((out_img * 255.0 + 0.5).clip(0, 255).astype(np.uint8)).save(pathlib.Path(out) / (stem + '_fog.png'))
    print(f'{path}  {W}x{H}  sky px {sky.mean()*100:.1f}%  ground px {ground.mean()*100:.1f}%  fog colour (sRGB) '
          f'{np.round(hc * 255).astype(int).tolist()}  fog mean at ground {fogf[ground].mean()*100 if ground.any() else 0:.1f}%')
    for name in ('sky', 'ground', 'all'):
        a, bb = res[name]
        if a is None:
            print(f'  {name:6s} none'); continue
        (ma, la, ca), (mb, lb, cb) = a, bb
        print(f'  {name:6s} mean RGB {np.round(ma,1).tolist()} -> {np.round(mb,1).tolist()}  luma {la:.1f} -> {lb:.1f} '
              f'(d {lb-la:+.1f})  chroma {ca:.1f} -> {cb:.1f}')
    print(f'  shafts bound: at most +{shaft_bound:.0f}/255 per channel on dark pixels, +{0.25*shaft_bound:.0f} on sky (not previewed)')


if __name__ == '__main__':
    for p in sys.argv[2:]:
        run(p, sys.argv[1])
