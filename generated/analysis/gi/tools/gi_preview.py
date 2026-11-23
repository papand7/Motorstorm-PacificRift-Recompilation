r"""Offline preview of RSX_FX_GI (rsx_vk_scenefx.comp GiTrace + composite), numpy port on a synthetic ray-cast scene (no
game data): sunlit sand, a grey wall whose camera-facing side is in its own shadow, a reddish rock. The scene is shaded
as the game's lit programs do with BAKE=0 (albedo x (flat ambient + sun x N.L x shadow)), then the GI factor from this
frame's colour multiplies the ambient share (strength x mix(1, 0.35, sunlit)). Prints region means and writes
build/shots/ltcmp/gi_synthetic.png (left: without GI, middle: with GI, right: the factor x 0.5).
usage: py -3 gi_preview.py [strength]"""
import sys, pathlib
import numpy as np
from PIL import Image

W, H = 320, 180
STRENGTH = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
RADIUS, STEPS, SLICES, THICK = 3.0, 8, 2, 0.75
SKYSAT, GROUND, FMAX, FMIN = 0.2, 1.0, 1.6, 0.25

cam = np.array([0.0, 1.7, 0.0]); fwd = np.array([0.0, -0.12, 1.0]); fwd /= np.linalg.norm(fwd)
right = np.cross(np.array([0.0, 1.0, 0.0]), fwd); right /= np.linalg.norm(right)   # +x on screen
up = np.cross(fwd, right)
fov = np.tan(np.radians(30.0))
asp = W / H
sun = np.array([0.35, 0.6, 0.72]); sun /= np.linalg.norm(sun)   # from behind the wall (wall faces -z towards the camera)
sun_col = np.array([1.0, 0.93, 0.82]) * 1.6
amb_col = np.array([0.42, 0.5, 0.62]) * 0.55
sky_col = np.array([0.45, 0.6, 0.85])

BOX = (np.array([-2.0, 0.0, 8.0]), np.array([2.0, 3.0, 8.6]))
SPH = (np.array([2.6, 0.7, 5.0]), 0.8)

def ray_box(o, d, lo, hi):
    inv = 1.0 / np.where(np.abs(d) < 1e-9, 1e-9, d)
    t0 = (lo - o) * inv; t1 = (hi - o) * inv
    tn = np.minimum(t0, t1).max(-1); tf = np.maximum(t0, t1).min(-1)
    hit = (tf >= np.maximum(tn, 1e-4))
    return np.where(hit, np.where(tn > 1e-4, tn, tf), np.inf)

def ray_sph(o, d, c, r):
    oc = o - c; b = (oc * d).sum(-1); cc = (oc * oc).sum(-1) - r * r
    disc = b * b - cc
    s = np.sqrt(np.maximum(disc, 0)); t = -b - s
    t = np.where(t > 1e-4, t, -b + s)
    return np.where((disc > 0) & (t > 1e-4), t, np.inf)

def trace(o, d):
    tg = np.where(d[..., 1] < -1e-6, -o[..., 1] / np.where(d[..., 1] < -1e-6, d[..., 1], -1), np.inf)
    tb = ray_box(o, d, *BOX); ts = ray_sph(o, d, *SPH)
    t = np.minimum(np.minimum(tg, tb), ts)
    kind = np.where(t == tg, 0, np.where(t == tb, 1, 2)); kind = np.where(np.isinf(t), -1, kind)
    return t, kind

ys, xs = np.mgrid[0:H, 0:W]
u = (xs + 0.5) / W; v = (ys + 0.5) / H
dirs = fwd + (u * 2 - 1)[..., None] * fov * asp * right + (1 - v * 2)[..., None] * fov * up
dirs /= np.linalg.norm(dirs, axis=-1, keepdims=True)
t, kind = trace(np.broadcast_to(cam, dirs.shape), dirs)
sky = kind < 0
P = cam + dirs * np.where(sky, 1e4, t)[..., None]
N = np.zeros_like(P); N[..., 1] = 1.0
lo, hi = BOX
bn = np.zeros_like(P)
for ax in range(3):
    bn[..., ax] = np.where(np.abs(P[..., ax] - lo[ax]) < 1e-3, -1.0, np.where(np.abs(P[..., ax] - hi[ax]) < 1e-3, 1.0, 0.0))
N = np.where((kind == 1)[..., None], bn, N)
sn = (P - SPH[0]) / SPH[1]
N = np.where((kind == 2)[..., None], sn, N)
N /= np.maximum(np.linalg.norm(N, axis=-1, keepdims=True), 1e-6)
alb = np.where((kind == 0)[..., None], np.array([0.8, 0.62, 0.42]), np.where((kind == 1)[..., None], np.array([0.55, 0.55, 0.55]), np.array([0.6, 0.32, 0.24])))
ts_, _ = trace(P + N * 1e-3, np.broadcast_to(sun, P.shape))
shadow = np.isinf(ts_).astype(float)
ndl = np.clip((N * sun).sum(-1), 0, 1)
lin = alb * (amb_col + sun_col * (ndl * shadow)[..., None])
lin = np.where(sky[..., None], sky_col, lin)
lin = np.clip(lin, 0, 1)
dist = np.where(sky, 1e9, np.linalg.norm(P - cam, axis=-1))

def project(X):
    rel = X - cam
    z = (rel * fwd).sum(-1)
    px = (rel * right).sum(-1) / (z * fov * asp); py = (rel * up).sum(-1) / (z * fov)
    return (px + 1) * 0.5, (1 - py) * 0.5, z

# GI (half res, as pass 4)
hw, hh = W // 2, H // 2
F = np.ones((hh, hw, 3))
skyR = np.maximum(np.full(3, sky_col @ np.array([0.2126, 0.7152, 0.0722])) * (1 - SKYSAT) + sky_col * SKYSAT, 0.02)
gnd = lin[~sky].mean(0) * GROUND
rng = np.random.default_rng(1)
for j in range(hh):
    for i in range(hw):
        y, x = j * 2, i * 2
        if sky[y, x]: continue
        p0, n0, d0 = P[y, x], N[y, x], dist[y, x]
        V = (cam - p0) / d0
        sc = np.clip(d0 / 20, 1, 3); r = RADIUS * sc; th = THICK * sc
        Rw = right - V * (right @ V); Rw /= np.linalg.norm(Rw)
        Uw = -up - V * (-up @ V); Uw /= np.linalg.norm(Uw)
        uv0 = np.array(project(p0)[:2])
        qr = np.array(project(p0 + Rw * r)[:2]); qu = np.array(project(p0 + Uw * r)[:2])
        ruv = np.array([abs(qr[0] - uv0[0]), abs(qu[1] - uv0[1])])
        rpx = max(ruv[0] * W, ruv[1] * H)
        ruv *= min(1.0, 0.25 / max(ruv[1], 1e-6))
        nS, nT = rng.random(), rng.random()
        E = np.zeros(3); ws = 0.0
        for s in range(SLICES):
            phi = (s + nS) / SLICES * np.pi
            dr = np.array([np.cos(phi), np.sin(phi)])
            Dw = Rw * dr[0] + Uw * dr[1]
            Dp = Dw - V * (Dw @ V); Dp /= np.linalg.norm(Dp)
            axis = np.cross(Dp, V); axis /= np.linalg.norm(axis)
            Np = n0 - axis * (n0 @ axis); lNp = np.linalg.norm(Np)
            if lNp < 1e-4: continue
            nn = np.arctan2(Np @ Dp, Np @ V)
            occ = 0; Es = np.zeros(3)
            for k in range(STEPS if rpx >= 2 else 0):
                tt = max(((k + nT) / STEPS) ** 2, 1.0 / rpx)
                for sg in (1, -1):
                    su = uv0 + sg * dr * ruv * tt
                    if su.min() < 0 or su.max() > 1: continue
                    sx, sy = min(int(su[0] * W), W - 1), min(int(su[1] * H), H - 1)
                    if sky[sy, sx]: continue
                    Hv = P[sy, sx] - p0; l = np.linalg.norm(Hv)
                    if l < 1e-3 or l > r: continue
                    Hb = Hv - V * th
                    af, ab = np.arctan2(Hv @ Dp, Hv @ V), np.arctan2(Hb @ Dp, Hb @ V)
                    t0 = np.clip((min(af, ab) - nn + np.pi / 2) / np.pi, 0, 1); t1 = np.clip((max(af, ab) - nn + np.pi / 2) / np.pi, 0, 1)
                    b0, b1 = min(int(t0 * 32), 31), min(int(np.ceil(t1 * 32)), 32)
                    if b1 <= b0: continue
                    cnt = b1 - b0
                    mask = (((1 << cnt) - 1) << b0) & 0xFFFFFFFF
                    nb = mask & ~occ & 0xFFFFFFFF
                    if not nb: continue
                    w = 0.5 * (np.cos(t0 * np.pi) - np.cos(t1 * np.pi)) * bin(nb).count('1') / cnt
                    Es += lin[sy, sx] * w; occ |= mask
            for b in range(32):
                if occ >> b & 1: continue
                beta = (b + 0.5) / 32 * np.pi - np.pi / 2
                a = nn + beta
                dw = V * np.cos(a) + Dp * np.sin(a)
                Es += (skyR if dw[1] >= 0 else gnd) * np.cos(beta) * np.pi / 64
            E += Es * lNp; ws += lNp
        if ws < 1e-4: continue
        f = E / ws / skyR
        lf = f @ np.array([0.2126, 0.7152, 0.0722])
        F[j, i] = f * np.clip(lf, FMIN, FMAX) / max(lf, 1e-4)
# a 5x5 box denoise (the resolve's spatial part, without the bilateral weights: the scene is smooth)
Fp = np.pad(F, ((2, 2), (2, 2), (0, 0)), mode='edge')
Fd = sum(Fp[a:a + hh, b:b + hw] for a in range(5) for b in range(5)) / 25.0
Ff = np.repeat(np.repeat(Fd, 2, 0), 2, 1)
sunlit = np.clip(ndl * 2, 0, 1) * shadow
k = np.clip(STRENGTH * (1 - 0.65 * sunlit), 0, 1)[..., None]
out = np.where(sky[..., None], lin, lin * (1 + (Ff - 1) * k))

def srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)
lum = lambda c: (srgb(c) * 255) @ np.array([0.2126, 0.7152, 0.0722])
wall = (kind == 1) & (N[..., 2] < -0.5)
gsh = (kind == 0) & (shadow < 0.5)
gsun = (kind == 0) & (shadow > 0.5)
for name, m in (('wall front (in shadow)', wall), ('ground in shadow', gsh), ('ground sunlit', gsun), ('whole image', np.ones_like(sky))):
    a, b = srgb(lin[m]).mean(0) * 255, srgb(out[m]).mean(0) * 255
    print(f'{name:24s} before rgb {a.round(1)} luma {lum(lin[m]).mean():6.1f}   after rgb {b.round(1)} luma {lum(out[m]).mean():6.1f}')
print('GI factor on the wall front (mean rgb):', Ff[wall].mean(0).round(3), ' on open sunlit ground:', Ff[gsun].mean(0).round(3))
img = np.concatenate([srgb(lin), srgb(out), np.clip(Ff * 0.5, 0, 1)], axis=1)
dst = pathlib.Path(__file__).resolve().parents[4] / 'build' / 'shots' / 'ltcmp'
dst.mkdir(parents=True, exist_ok=True)
Image.fromarray((img * 255 + 0.5).astype(np.uint8)).resize((W * 3 * 2, H * 2), Image.NEAREST).save(dst / 'gi_synthetic.png')
print('wrote', dst / 'gi_synthetic.png')
