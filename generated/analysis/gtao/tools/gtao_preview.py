r"""Offline check of the scene pass's AO math (rsx_vk_scenefx.comp): the classic 12-sample AO (Occlusion) and GTAO (Gtao +
the GtaoResolve spatial filter), ported to numpy, on a synthetic ray-cast scene (ground, a wall with a step, a sphere, a
box) seen by a pinhole camera. No game data. Checks: flat open ground stays ~1 (no self-occlusion), creases darken, the
sphere's contact darkens, nothing dark floats in the air (halo check). Also prints the GTAO of the analytic open plane
and of a 90-degree corner. usage: py -3 gtao_preview.py <out.png> [frames to accumulate, default 8]"""
import sys
import numpy as np
from PIL import Image

W, H = 640, 360
FOV = np.radians(60.0)
CAM = np.array([0.0, 1.6, -6.0])
TGT = np.array([0.0, 0.6, 2.0])
fw = TGT - CAM; fw /= np.linalg.norm(fw)
rt = np.cross(np.array([0, 1.0, 0]), fw); rt /= np.linalg.norm(rt)
up = np.cross(fw, rt)
th = np.tan(FOV / 2); asp = W / H


def rays(u, v):
    x = (u * 2 - 1) * th * asp; y = (1 - v * 2) * th
    d = fw[None] + x[..., None] * rt + y[..., None] * up
    return d / np.linalg.norm(d, axis=-1, keepdims=True)


def trace(o, d):
    """nearest hit t of: ground y=0, wall z=4 (x in -3..3, y<2.5), step box, sphere"""
    t = np.full(d.shape[:-1], np.inf)
    with np.errstate(divide='ignore', invalid='ignore'):
        tg = -o[1] / d[..., 1]; t = np.where((tg > 0) & (tg < t), tg, t)
        tw = (4.0 - o[2]) / d[..., 2]; p = o + tw[..., None] * d
        ok = (tw > 0) & (np.abs(p[..., 0]) < 3) & (p[..., 1] < 2.5) & (p[..., 1] > 0); t = np.where(ok & (tw < t), tw, t)
        # box x -2.6..-1.4, y 0..0.8, z 1..2 (slab test)
        lo = np.array([-2.6, 0.0, 1.0]); hi = np.array([-1.4, 0.8, 2.0])
        t1 = (lo - o) / d; t2 = (hi - o) / d
        tn = np.minimum(t1, t2).max(-1); tf = np.maximum(t1, t2).min(-1)
        ok = (tf >= tn) & (tn > 0); t = np.where(ok & (tn < t), tn, t)
        # sphere centre (1.5, 0.7, 1.5) r 0.7
        c = np.array([1.5, 0.7, 1.5]); oc = o - c
        b = (d * oc).sum(-1); cc = (oc * oc).sum() - 0.49; disc = b * b - cc
        ts = -b - np.sqrt(np.maximum(disc, 0)); ok = (disc > 0) & (ts > 0); t = np.where(ok & (ts < t), ts, t)
    return t


uu, vv = np.meshgrid((np.arange(W) + 0.5) / W, (np.arange(H) + 0.5) / H)
D = rays(uu, vv)
T = trace(CAM, D)
SKY = ~np.isfinite(T)
WP = CAM + np.where(SKY, 1e4, T)[..., None] * D


def world_at(u, v):
    x = np.clip((u * W).astype(int), 0, W - 1); y = np.clip((v * H).astype(int), 0, H - 1)
    return WP[y, x], SKY[y, x]


def project(p):
    q = p - CAM
    z = (q * fw).sum(-1); x = (q * rt).sum(-1) / np.maximum(z, 1e-6); y = (q * up).sum(-1) / np.maximum(z, 1e-6)
    return x / (th * asp) * 0.5 + 0.5, 0.5 - y / th * 0.5, z > 1e-6


def ign(px, py, t=0.0):
    return np.modf(52.9829189 * np.modf((px + t * 5.588238) * 0.06711056 + (py + t * 5.588238) * 0.00583715)[0])[0]


def normals():
    def g(dx, dy):
        x = np.clip(np.arange(W) + dx, 0, W - 1); y = np.clip(np.arange(H) + dy, 0, H - 1)
        return WP[y][:, x]
    dist = lambda p: np.linalg.norm(p - CAM, axis=-1)
    d0 = dist(WP)
    wr, wl, wd, wu = g(1, 0), g(-1, 0), g(0, 1), g(0, -1)
    dx = np.where((np.abs(dist(wr) - d0) < np.abs(dist(wl) - d0))[..., None], wr - WP, WP - wl)
    dy = np.where((np.abs(dist(wd) - d0) < np.abs(dist(wu) - d0))[..., None], wd - WP, WP - wu)
    n = np.cross(dy, dx); n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-9)
    flip = ((CAM - WP) * n).sum(-1) < 0
    return np.where(flip[..., None], -n, n)


N = normals()
DIST = np.linalg.norm(WP - CAM, axis=-1)
PX, PY = np.meshgrid(np.arange(W, dtype=float), np.arange(H, dtype=float))


def classic(radius=1.2, power=1.3, frame=0):
    r = radius * np.clip(DIST / 20, 1, 4)
    n = N
    t = np.cross(n, np.array([0, 1.0, 0])); alt = np.cross(n, np.array([1.0, 0, 0]))
    t = np.where((np.abs(n[..., 1]) < 0.9)[..., None], t, alt); t /= np.maximum(np.linalg.norm(t, axis=-1, keepdims=True), 1e-9)
    b = np.cross(n, t)
    rot = ign(PX, PY, frame) * 6.2831853
    occ = np.zeros((H, W)); K = 12
    for i in range(K):
        fi = (i + 0.5) / K; a = rot + i * 2.3999632; s = np.sqrt(fi)
        h = [np.cos(a) * s, np.sin(a) * s, np.sqrt(max(1 - fi, 0)) * 0.7 + 0.15]
        sp = WP + (t * h[0][..., None] + b * h[1][..., None] + n * h[2]) * (r * (0.25 + 0.75 * fi))[..., None]
        qu, qv, ok = project(sp)
        ok &= (qu >= 0) & (qu <= 1) & (qv >= 0) & (qv <= 1)
        sw, ssky = world_at(qu, qv)
        ds = np.linalg.norm(sw - CAM, axis=-1); dp = np.linalg.norm(sp - CAM, axis=-1)
        x = np.clip((np.abs(dp - ds) - r * 0.5) / r, 0, 1); rng = 1 - x * x * (3 - 2 * x)
        occ += np.where(ok & ~ssky & (ds < dp - 0.02 * r), rng, 0)
    return np.where(SKY, 1.0, np.clip(1 - occ / K, 0, 1) ** power)


def facos(x):
    a = np.abs(x); r = (-0.156583 * a + np.pi / 2) * np.sqrt(np.maximum(1 - a, 0)); return np.where(x >= 0, r, np.pi - r)


def gtao(radius=1.5, power=1.5, S=2, K=6, falloff=0.6, frame=0):
    P = WP; n_ = N
    V = CAM - P; V /= np.maximum(np.linalg.norm(V, axis=-1, keepdims=True), 1e-9)
    r = radius * np.clip(DIST / 20, 1, 4)
    def perp(a):
        a = a - V * (a * V).sum(-1, keepdims=True); return a / np.maximum(np.linalg.norm(a, axis=-1, keepdims=True), 1e-9)
    R = perp(world_at(uu + 1.0 / W, vv)[0] - P); U = perp(world_at(uu, vv + 1.0 / H)[0] - P)
    qr = project(P + R * r[..., None]); qu_ = project(P + U * r[..., None])
    ru = np.abs(qr[0] - uu); rv = np.abs(qu_[1] - vv)
    rpx = np.maximum(ru * W, rv * H)
    sc = np.minimum(1.0, 0.15 / np.maximum(rv, 1e-6)); ru *= sc; rv *= sc
    nS = np.modf(ign(PX, PY) + frame * 0.618034)[0]; nT = np.modf(ign(PY + 13, PX + 71) + frame * 0.754878)[0]
    fr = max(falloff, 0.05) * r
    vis = np.zeros((H, W))
    for s in range(S):
        phi = (s + nS) / S * np.pi
        dx, dy = np.cos(phi), np.sin(phi)
        Dw = R * dx[..., None] + U * dy[..., None]; Dw /= np.maximum(np.linalg.norm(Dw, axis=-1, keepdims=True), 1e-9)
        axis = np.cross(Dw, V); axis /= np.maximum(np.linalg.norm(axis, axis=-1, keepdims=True), 1e-9)
        Np = n_ - axis * (n_ * axis).sum(-1, keepdims=True); lNp = np.linalg.norm(Np, axis=-1)
        cosN = np.clip((Np * V).sum(-1) / np.maximum(lNp, 1e-9), -1, 1)
        n = np.where((Dw * Np).sum(-1) >= 0, 1.0, -1.0) * facos(cosN)
        lo0, lo1 = np.cos(n + np.pi / 2), np.cos(n - np.pi / 2)
        hc0, hc1 = lo0.copy(), lo1.copy()
        for k in range(K):
            t = ((k + nT) / K) ** 2; t = np.maximum(t, 1.0 / np.maximum(rpx, 1e-6))
            ou, ov = dx * ru * t, dy * rv * t
            for sign, lo, hc in ((1, lo0, hc0), (-1, lo1, hc1)):
                su, sv = uu + sign * ou, vv + sign * ov
                ok = (su >= 0) & (su <= 1) & (sv >= 0) & (sv <= 1)
                sw, ssky = world_at(su, sv)
                Hh = sw - P; l = np.linalg.norm(Hh, axis=-1)
                c = (Hh * V).sum(-1) / np.maximum(l, 1e-9)
                tb = np.clip(((Hh * n_).sum(-1) / np.maximum(l, 1e-9) - 0.03) / 0.03, 0, 1)   # TanBias
                c = lo + (c - lo) * np.clip((r - l) / fr, 0, 1) * tb
                np.maximum(hc, np.where(ok & ~ssky & (l > 1e-4), c, -9), out=hc)
        h0 = -facos(np.clip(hc1, -1, 1)); h1 = facos(np.clip(hc0, -1, 1))
        h0 = n + np.clip(h0 - n, -np.pi / 2, np.pi / 2); h1 = n + np.clip(h1 - n, -np.pi / 2, np.pi / 2)
        sn = np.sin(n)
        vis += lNp * ((cosN + 2 * h0 * sn - np.cos(2 * h0 - n)) + (cosN + 2 * h1 * sn - np.cos(2 * h1 - n))) * 0.25
    vis = np.clip(vis / S, 0, 2)          # linear and unclamped above 1 until after the accumulation (as the shader)
    vis = np.where(rpx < 2, 1.0, vis)
    return np.where(SKY, 1.0, vis)


def resolve(raw, frame):
    """GtaoResolve's spatial part: 4x4 bilateral, distance + normal weights"""
    o = -1 if frame % 2 == 0 else -2
    sw = np.zeros((H, W)); s1 = np.zeros((H, W))
    for j in range(4):
        for i in range(4):
            y = np.clip(np.arange(H) + j + o, 0, H - 1); x = np.clip(np.arange(W) + i + o, 0, W - 1)
            s = raw[y][:, x]; ds = DIST[y][:, x]; ns = N[y][:, x]
            w = np.exp(-np.abs(ds - DIST) / np.maximum(DIST * 0.02, 0.02)) * np.clip((ns * N).sum(-1), 0, 1) ** 8
            sw += w; s1 += s * w
    return np.where(SKY, 1.0, s1 / sw)


frames = int(sys.argv[2]) if len(sys.argv) > 2 else 8
old = classic()
POW = 1.5
fin = lambda x: np.clip(x, 0, 1) ** POW   # the composite: clamp, then the power
g1 = gtao(frame=0)
print('GTAO open-ground linear mean, 2 slices, 1 frame: %.3f; 16 slices: %.3f' % (
    g1[(np.abs(WP[..., 1]) < 1e-3) & (np.abs(WP[..., 0]) < 0.6) & (WP[..., 2] > -2) & (WP[..., 2] < 0.5)].mean(),
    gtao(S=16)[(np.abs(WP[..., 1]) < 1e-3) & (np.abs(WP[..., 0]) < 0.6) & (WP[..., 2] > -2) & (WP[..., 2] < 0.5)].mean()))
acc = None
for f in range(frames):   # static camera: the temporal blend is a running 1/n average of the resolved frames
    rr = resolve(gtao(frame=f), f)
    acc = rr if acc is None else acc + (rr - acc) / min(f + 1, 8)
noisy = fin(resolve(g1, 0)); acc = fin(acc); g1 = fin(g1)

def stat(name, img, m):
    print(f'{name:28s} open ground {img[m["ground"]].mean():.3f}  wall crease {img[m["crease"]].mean():.3f}  '
          f'sphere contact {img[m["contact"]].mean():.3f}  in front of wall (halo) {img[m["halo"]].mean():.3f}')

# masks from the world positions
g = (np.abs(WP[..., 1]) < 1e-3) & ~SKY
m = {
    'ground': g & (np.abs(WP[..., 0]) < 0.6) & (WP[..., 2] > -2) & (WP[..., 2] < 0.5),
    'crease': g & (np.abs(WP[..., 0]) < 1.0) & (WP[..., 2] > 3.6),
    'contact': g & (np.hypot(WP[..., 0] - 1.5, WP[..., 2] - 1.5) < 0.45),
    'halo': g & (np.abs(WP[..., 0]) < 0.6) & (WP[..., 2] > 1.0) & (WP[..., 2] < 2.3),
}
stat('classic (raw)', old, m)
stat('GTAO raw, 1 frame', g1, m)
stat('GTAO + 4x4 bilateral', noisy, m)
stat(f'GTAO + filter + {frames} frames', acc, m)
# analytic checks: GTAO of an open plane is 1; Lambert-weighted visibility of a 90-degree corner seen head-on ~0.75-0.8
print('noise (std of open ground): classic %.3f, GTAO raw %.3f, filtered %.3f, accumulated %.3f' % (
    old[m['ground']].std(), g1[m['ground']].std(), noisy[m['ground']].std(), acc[m['ground']].std()))
shade = lambda a: np.clip(np.where(SKY, 0.8, 0.25 + 0.6 * np.clip(-(N * np.array([0.3, -0.8, 0.5])).sum(-1), 0, 1) * 0.6 + 0.4 * 0.75), 0, 1) * np.where(SKY, 1.0, 1 - 0.6 * (1 - a))
row1 = np.concatenate([old, acc], 1)
row2 = np.concatenate([shade(old), shade(acc)], 1)
img = np.concatenate([row1, row2], 0)
Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(sys.argv[1])
print('saved', sys.argv[1], '(top: AO term, bottom: on a flat-shaded scene at strength 0.6; left classic, right GTAO)')
