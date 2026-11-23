r"""Offline check of the RSX_FX_SSR trace (rsx_vk_scenefx.comp: HizRect / HizBuild / WaterLevelPass / SsrSurface /
SsrTrace / SsrApply, ripple 0) on a synthetic scene with a known camera and an analytic ground truth. No game data.
Scene: sand (y 0) sloping into a seabed (to y -0.6) under a water strip (z 5..15, the water plane y 0 written by no
depth, tag 1), a red wall behind it (z 22..26), a green post standing in the water, sky beyond.
Reports: water level estimate, hit agreement with the analytic mirror ray, and an image (scene | SSR | analytic).
usage: py -3 ssr_preview.py [out.png]"""
import sys, math
import numpy as np
from PIL import Image

W, H = 384, 216
import os
STEPS, LEVELS, THICK, MAXD = int(os.environ.get("STEPS", "32")), 5, 1.0, 400.0
kSky = 0.99999

# camera: eye, yaw 0 (looking +z), pitch down 8 degrees; D3D-style projection, depth = ndc z in [0, 1]
eye = np.array([0.0, 3.0, -10.0])
pitch = math.radians(-8.0)
fwd = np.array([0.0, math.sin(pitch), math.cos(pitch)]); right = np.array([1.0, 0.0, 0.0]); up = np.cross(fwd, right)
view = np.eye(4); view[0, :3] = right; view[1, :3] = up; view[2, :3] = fwd
view[:3, 3] = -view[:3, :3] @ eye
n, f, fovy, asp = 0.5, 2000.0, math.radians(60.0), W / H
proj = np.zeros((4, 4)); proj[0, 0] = 1.0 / (math.tan(fovy / 2) * asp); proj[1, 1] = 1.0 / math.tan(fovy / 2)
proj[2, 2] = f / (f - n); proj[2, 3] = -f * n / (f - n); proj[3, 2] = 1.0
M = proj @ view; Mi = np.linalg.inv(M)

def project(w):
    c = M @ np.append(w, 1.0)
    if c[3] <= 1e-6: return None
    nn = c[:3] / c[3]
    return np.array([nn[0] * 0.5 + 0.5, 0.5 - nn[1] * 0.5, nn[2]])

def world_at(uv, d):
    c = np.array([uv[0] * 2 - 1, 1 - uv[1] * 2, d, 1.0]); w = Mi @ c
    return w[:3] / w[3]

# ---- analytic scene ------------------------------------------------------------------------------------------
def ground_y(z): return np.where(z < 5.0, 0.0, np.where(z < 8.0, -0.6 * (z - 5.0) / 3.0, np.where(z <= 15.0, -0.6, 0.0)))
BOXES = [(np.array([-3.0, 0.0, 22.0]), np.array([3.0, 4.0, 26.0]), (0.85, 0.15, 0.1)),
         (np.array([3.5, -0.6, 10.0]), np.array([4.3, 3.0, 10.8]), (0.1, 0.7, 0.2))]
SAND, SEABED, SKY = (0.76, 0.68, 0.5), (0.45, 0.42, 0.35), (0.45, 0.65, 0.95)

def cast(o, d):
    """nearest opaque hit: (t, colour) or (inf, sky)"""
    best, col = math.inf, SKY
    for lo, hi, c in BOXES:
        with np.errstate(divide='ignore', invalid='ignore'):
            t0 = (lo - o) / d; t1 = (hi - o) / d
        tn = np.nanmax(np.minimum(t0, t1)); tf = np.nanmin(np.maximum(t0, t1))
        if tn <= tf and tf > 1e-4:
            t = tn if tn > 1e-4 else tf
            if t < best: best, col = t, c
    # height field: march (fine) then refine
    if d[1] < 0 or o[1] < 0.01:
        t, dt = 1e-3, 0.05
        prev = o[1] - ground_y(np.array(o[2]))
        while t < min(best, 600.0):
            p = o + d * t
            g = float(ground_y(np.array(p[2])))
            if p[1] <= g:
                lo_, hi_ = t - dt, t
                for _ in range(30):
                    m = 0.5 * (lo_ + hi_); pm = o + d * m
                    if pm[1] <= float(ground_y(np.array(pm[2]))): hi_ = m
                    else: lo_ = m
                if hi_ < best:
                    pz = (o + d * hi_)[2]
                    best, col = hi_, SEABED if 5.0 <= pz <= 15.0 else SAND
                break
            t += dt; dt = min(dt * 1.03, 2.0)
    return best, col

def water_t(o, d):
    if abs(d[1]) < 1e-6: return math.inf
    t = -o[1] / d[1]
    if t <= 1e-4: return math.inf
    z = (o + d * t)[2]
    return t if 5.0 <= z <= 15.0 else math.inf

depth = np.ones((H, W)); colour = np.zeros((H, W, 3)); tag = np.zeros((H, W), np.uint8)
for y in range(H):
    for x in range(W):
        uv = np.array([(x + 0.5) / W, (y + 0.5) / H])
        wp = world_at(uv, 0.5); d = wp - eye; d /= np.linalg.norm(d)
        t, c = cast(eye, d)
        colour[y, x] = c
        if t < math.inf: depth[y, x] = project(eye + d * t)[2]
        if water_t(eye, d) < t: tag[y, x] = 1; colour[y, x] = 0.5 * np.array(c) + 0.5 * np.array([0.1, 0.3, 0.4])

# ---- the shader, ported ----------------------------------------------------------------------------------------
w0, h0 = (W + 1) // 2, (H + 1) // 2
def hiz_rect(L):
    if L == 0: return 0, 0, w0, h0
    w, h, yy = w0, h0, 0
    for i in range(1, L + 1):
        w, h = (w + 1) // 2, (h + 1) // 2
        if i < L: yy += h
    return w0, yy, w, h
hiz = np.full((h0, w0 + (w0 + 1) // 2), -1e30)
for L in range(LEVELS):
    ox, oy, lw, lh = hiz_rect(L)
    for y in range(lh):
        for x in range(lw):
            m = 1.0
            for j in range(2):
                for i in range(2):
                    if L == 0: m = min(m, depth[min(y * 2 + j, H - 1), min(x * 2 + i, W - 1)])
                    else:
                        px, py, pw, ph = hiz_rect(L - 1)
                        m = min(m, hiz[py + min(y * 2 + j, ph - 1), px + min(x * 2 + i, pw - 1)])
            hiz[oy + y, ox + x] = m
def hiz_load(L, cx, cy):
    ox, oy, lw, lh = hiz_rect(L)
    return hiz[oy + min(max(cy, 0), lh - 1), ox + min(max(cx, 0), lw - 1)]

# water level (WaterLevelPass, 64x32 samples)
hi, cnt = -1e30, 0
for j in range(32):
    for i in range(64):
        uv = np.array([(i + 0.5) / 64, (j + 0.5) / 32]); px = (int(uv[0] * W), int(uv[1] * H))
        if tag[px[1], px[0]] != 1: continue
        d = depth[px[1], px[0]]
        if d >= kSky: continue
        hi = max(hi, world_at(uv, d)[1]); cnt += 1
wl = hi if cnt >= 4 else -1e30

def view_dir(uv): v = world_at(uv, 0.5) - eye; return v / np.linalg.norm(v)
def surface(uv, d, tg):
    if tg == 1:
        dr = view_dir(uv)
        if wl > -1e29 and dr[1] < -1e-3 and eye[1] > wl: return eye + dr * ((wl - eye[1]) / dr[1]), np.array([0.0, 1.0, 0.0])
        if d < kSky: return world_at(uv, d), np.array([0.0, 1.0, 0.0])
    return None, None

def sample(img, uv):
    x = min(max(int(uv[0] * W), 0), W - 1); y = min(max(int(uv[1] * H), 0), H - 1)
    return img[y, x]

def trace(ax, ay):
    hs = np.array([w0, h0], float); uv = (np.array([ax, ay]) + 0.5) / hs
    tg = 0
    for j in range(2):
        for i in range(2):
            if tg == 0: tg = tag[min(ay * 2 + j, H - 1), min(ax * 2 + i, W - 1)]
    if tg == 0: return None
    d = sample(depth, uv)
    P, N = surface(uv, d, tg)
    if P is None: return None
    V = eye - P; dist = np.linalg.norm(V); V /= dist
    R = -V - 2 * np.dot(-V, N) * N
    fcam = 1 - np.clip((np.dot(R, V) - 0.2) / 0.4, 0, 1) ** 2 * (3 - 2 * np.clip((np.dot(R, V) - 0.2) / 0.4, 0, 1))
    Lr = max(dist, 30.0) * 3.0
    w0c = (M @ np.append(P, 1))[3]; w1c = (M @ np.append(P + R * Lr, 1))[3]; wmin = max(w0c * 0.05, 1e-3)
    if w1c < wmin: Lr *= (w0c - wmin) / max(w0c - w1c, 1e-6)
    a, b = project(P), project(P + R * Lr)
    res = (P, R, None)
    if a is None or b is None or fcam <= 0: return res
    o = a[:2] * hs; dl = (b[:2] - a[:2]) * hs; z0 = a[2]; dz = b[2] - a[2]; ln = np.linalg.norm(dl)
    tmax = 1.0
    for k in range(2):
        if dl[k] > 1e-6: tmax = min(tmax, (hs[k] - o[k]) / dl[k])
        elif dl[k] < -1e-6: tmax = min(tmax, -o[k] / dl[k])
    if ln * tmax < 1.0: return res
    sdir = np.array([1.0 if dl[0] >= 0 else 0.0, 1.0 if dl[1] >= 0 else 0.0])
    inv = np.array([1 / dl[0] if abs(dl[0]) > 1e-6 else 1e12, 1 / dl[1] if abs(dl[1]) > 1e-6 else 1e12])
    tmin = 1 / ln; t = 1.5 / ln; lv = 0
    for _ in range(STEPS):
        if t >= tmax: break
        cs = float(1 << lv); pp = o + dl * t; cell = np.floor(pp / cs)
        tt = ((cell + sdir) * cs - o) * inv
        tex = min(max(min(tt), t + 0.01 * tmin), tmax)
        zmin = hiz_load(lv, int(cell[0]), int(cell[1]))
        za, zb = z0 + dz * t, z0 + dz * tex
        if zmin >= kSky or max(za, zb) < zmin: t = tex; lv = min(lv + 1, LEVELS - 1); continue
        if lv > 0: lv -= 1; continue
        th = t + (tex - t) * np.clip((zmin - za) / max(zb - za, 1e-9), 0, 1) if za < zmin else t
        q = (o + dl * th) / hs
        sd = sample(depth, q)
        if sd < kSky:
            ds = np.linalg.norm(world_at(q, sd) - eye); dr = np.linalg.norm(world_at(q, z0 + dz * th) - eye)
            thick = max(0.35, ds * 0.025) * THICK
            if -0.1 * thick < dr - ds < thick: return (P, R, q)
        t = tex
    return res

agree = miss = false_hit = both_sky = 0; errs = []; missc = {}
ssr = np.zeros((h0, w0, 4)); truth = np.zeros((h0, w0, 4))
for ay in range(h0):
    for ax in range(w0):
        r = trace(ax, ay)
        if r is None: continue
        P, R, q = r
        t, c = cast(P + R * 1e-3, R)
        tp = project(P + R * t) if t < math.inf else None
        on = tp is not None and 0 <= tp[0] <= 1 and 0 <= tp[1] <= 1
        # visible on screen = not occluded in the depth buffer (what SSR can find at best)
        vis = on and abs(sample(depth, tp[:2]) - tp[2]) < 2e-4
        if t < math.inf: truth[ay, ax] = (*c, 1.0)
        if q is not None:
            ssr[ay, ax] = (*sample(colour, q), 1.0)
            if vis: agree += 1; errs.append(np.linalg.norm((q - tp[:2]) * [W, H]))
            else: false_hit += 1
        else:
            if vis: miss += 1; missc[c] = missc.get(c, 0) + 1
            elif t == math.inf: both_sky += 1
print(f'water level estimate {wl:.3f} (true 0.0, {cnt} samples); tagged half-res pixels traced')
print(f'hits matching the analytic mirror ray: {agree}, median error {np.median(errs) if errs else float("nan"):.2f} px, '
      f'p95 {np.percentile(errs, 95) if errs else float("nan"):.2f} px')
print('misses by true surface colour:', missc)
print(f'misses where the analytic hit is visible on screen: {miss}; hits where the truth is off-screen/occluded/sky: '
      f'{false_hit}; both sky/off-screen: {both_sky}')

def comp(src):
    out = colour.copy()
    for y in range(H):
        for x in range(W):
            if tag[y, x] != 1: continue
            s = src[min(y // 2, h0 - 1), min(x // 2, w0 - 1)]
            if s[3] <= 0: continue
            uv = np.array([(x + 0.5) / W, (y + 0.5) / H]); P, N = surface(uv, depth[y, x], 1)
            V = eye - P; V /= np.linalg.norm(V)
            F = 0.02 + 0.98 * (1 - max(np.dot(N, V), 0)) ** 5
            k = min(F * s[3], 1.0)
            out[y, x] = out[y, x] * (1 - k) + s[:3] * k
    return out
img = np.concatenate([colour, comp(ssr), comp(truth)], axis=1)
o = sys.argv[1] if len(sys.argv) > 1 else 'ssr_synthetic.png'
Image.fromarray((np.clip(img, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8)).resize((W * 3 * 2, H * 2), Image.NEAREST).save(o)
print('wrote', o)
