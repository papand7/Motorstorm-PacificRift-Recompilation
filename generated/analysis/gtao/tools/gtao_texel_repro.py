r"""Offline repro of the Klt24 GTAO cross-hatch / wedge (rsx_vk_scenefx.comp Gtao + GtaoResolve spatial filter).

Unlike gtao_preview.py (which reads exact world positions per texel), this models what the GPU does: a 3840x1080
D24-quantised depth target (the game's 2x-wide scene), point-sampled (floor(u * size)) at arbitrary uv, and the world
position rebuilt at that *uv* (WorldAt(uv, d)), not at the texel the depth came from. The half-res AO pixel centre is
exactly on a scene-texel corner. Scene: sand ground seen from a crash camera 1.6 m up, pitched 28 deg down, with one
terrain triangle folded 3 deg (a concave crease the wedge suspect), and a box (the rider) for a real contact shadow.

  mode old: the shader as in Klt24 (exe c9161d3b)     mode new: texel-centre snapped depth + positions (the fix)
usage: py -3 gtao_texel_repro.py <outdir>  -> old.png new.png (AO^1.5 after the 4x4 bilateral) + stats"""
import sys, os
import numpy as np
from PIL import Image

W, H = 3840, 1080                       # scene target (2x wide)
FOVY = np.radians(50.0); TY = np.tan(FOVY / 2); TX = TY * 16 / 9
NEAR, FAR = 0.5, 3000.0
PITCH = np.radians(28.0)
CAMY = 1.6
f32 = np.float32

# view space: x right, y up, z forward. world: the camera at (0, CAMY, 0) pitched down.
cp, sp = np.cos(PITCH), np.sin(PITCH)
def w2v(p):   # world -> view
    q = p - np.array([0, CAMY, 0])
    return np.stack([q[..., 0], q[..., 1] * cp + q[..., 2] * sp, -q[..., 1] * sp + q[..., 2] * cp], -1)
def v2w(q):
    y = q[..., 1] * cp - q[..., 2] * sp; z = q[..., 1] * sp + q[..., 2] * cp
    return np.stack([q[..., 0], y + CAMY, z], -1)

def ray_dirs(u, v):
    x = (u * 2 - 1) * TX; y = (1 - v * 2) * TY
    d = np.stack([x, y, np.ones_like(x)], -1)
    return v2w(d) - v2w(np.zeros(3))

def trace(o, d):
    t = np.full(d.shape[:-1], np.inf)
    with np.errstate(divide='ignore', invalid='ignore'):
        gs = float(os.environ.get('GSLOPE', '0'))   # ground y = gs * x (a side slope)
        tg = (gs * o[0] - o[1]) / (d[..., 1] - gs * d[..., 0]); t = np.where((tg > 0), tg, t)
        # the folded triangle: points with x in a triangle (world xz) use the plane y = k * (z - z0) (k = tan 3 deg)
        p = o + tg[..., None] * d
        a, b, c = np.array([-1.6, 3.0]), np.array([0.6, 3.0]), np.array([-0.6, 6.5])
        def side(p1, p2, q): return (p2[0] - p1[0]) * (q[..., 1] - p1[1]) - (p2[1] - p1[1]) * (q[..., 0] - p1[0])
        xz = np.stack([p[..., 0], p[..., 2]], -1)
        s1, s2, s3 = side(a, b, xz), side(b, c, xz), side(c, a, xz)
        intri = ((s1 >= 0) & (s2 >= 0) & (s3 >= 0)) | ((s1 <= 0) & (s2 <= 0) & (s3 <= 0))
        k = np.tan(np.radians(3.0)); kx = np.tan(np.radians(float(os.environ.get('TILTX', '0'))))
        # plane through (x0, 0, 3) rising towards c (k) and sideways (kx): y = k (z - 3) + kx (x + 1.6); intersect the ray
        tt = (k * (o[2] - 3.0) + kx * (o[0] + 1.6) - o[1]) / (d[..., 1] - k * d[..., 2] - kx * d[..., 0])
        pt = o + tt[..., None] * d
        xz2 = np.stack([pt[..., 0], pt[..., 2]], -1)
        q1, q2, q3 = side(a, b, xz2), side(b, c, xz2), side(c, a, xz2)
        in2 = ((q1 >= 0) & (q2 >= 0) & (q3 >= 0)) | ((q1 <= 0) & (q2 <= 0) & (q3 <= 0))
        t = np.where(in2 & (tt > 0) & (tt < t), tt, t)
        # box (the rider) x 0.9..1.7, y 0..0.35, z 3.2..3.6
        lo = np.array([0.9, 0.0, 3.2]); hi = np.array([1.7, 0.35, 3.6])
        t1 = (lo - o) / d; t2 = (hi - o) / d
        tn = np.minimum(t1, t2).max(-1); tf = np.maximum(t1, t2).min(-1)
        ok = (tf >= tn) & (tn > 0); t = np.where(ok & (tn < t), tn, t)
    return t

CAM = np.array([0.0, CAMY, 0.0])
uu, vv = np.meshgrid((np.arange(W) + 0.5) / W, (np.arange(H) + 0.5) / H)
D = ray_dirs(uu, vv)
T = trace(CAM, D)
WPv = w2v(CAM + np.where(np.isfinite(T), T, 1e5)[..., None] * D)
zv = WPv[..., 2]
dep = FAR / (FAR - NEAR) * (1 - NEAR / zv)
dep = np.where(np.isfinite(T), np.round(dep * (2 ** 24 - 1)) / (2 ** 24 - 1), 1.0).astype(np.float32)   # D24
KSKY = 0.99999

SUBTEX = os.environ.get('SUBTEX') == '1'   # GPU-like: coordinates rounded to 1/256 texel before the floor
def fetch_uv(u, v):   # point sampling at uv (floor(u * size), float32 as the GPU's coordinate maths)
    fx, fy = f32(u) * f32(W), f32(v) * f32(H)
    if SUBTEX: fx, fy = np.round(fx * 256) / 256, np.round(fy * 256) / 256
    x = np.clip(np.floor(fx).astype(int), 0, W - 1); y = np.clip(np.floor(fy).astype(int), 0, H - 1)
    return dep[y, x], x, y

def world_at(u, v, d):   # WorldAt: uv + depth -> world
    z = NEAR * FAR / (FAR - d * (FAR - NEAR))
    q = np.stack([(u * 2 - 1) * TX * z, (1 - v * 2) * TY * z, z], -1)
    return v2w(q)

def project(p):
    q = w2v(p); z = q[..., 2]
    return q[..., 0] / (z * TX) * 0.5 + 0.5, 0.5 - q[..., 1] / (z * TY) * 0.5, z > 1e-6

def ign(px, py, t=0.0):
    return np.modf(52.9829189 * np.modf((px + t * 5.588238) * 0.06711056 + (py + t * 5.588238) * 0.00583715)[0])[0]

def facos(x):
    a = np.abs(x); r = (-0.156583 * a + np.pi / 2) * np.sqrt(np.maximum(1 - a, 0)); return np.where(x >= 0, r, np.pi - r)

def nrm(v): return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)
def dot(a, b): return (a * b).sum(-1)

def normal_at(u, v, P, snap):
    tx, ty = 1.0 / W, 1.0 / H
    if snap:   # texel-centre neighbours (u, v already a texel centre)
        get = lambda du, dv: (lambda d: world_at(u + du, v + dv, d))(fetch_uv(u + du, v + dv)[0])
        d0 = fetch_uv(u, v)[0]
    else:
        get = lambda du, dv: world_at(u + du, v + dv, fetch_uv(u + du, v + dv)[0])
        d0 = fetch_uv(u, v)[0]
    dr, dl = fetch_uv(u + tx, v)[0], fetch_uv(u - tx, v)[0]
    dd, du_ = fetch_uv(u, v + ty)[0], fetch_uv(u, v - ty)[0]
    wr, wl, wd, wu = get(tx, 0), get(-tx, 0), get(0, ty), get(0, -ty)
    dx = np.where((np.abs(dr - d0) < np.abs(dl - d0))[..., None], wr - P, P - wl)
    dy = np.where((np.abs(dd - d0) < np.abs(du_ - d0))[..., None], wd - P, P - wu)
    n = nrm(np.cross(dy, dx))
    return np.where((dot(n, CAM - P) < 0)[..., None], -n, n)

def gtao(mode, frame=0, S=2, K=6, radius=1.5, falloff=0.6):
    hw, hh = W // 2, H // 2
    ax, ay = np.meshgrid(np.arange(hw), np.arange(hh))
    u = (ax + 0.5) / hw; v = (ay + 0.5) / hh
    snap = mode == 'new'
    if snap:   # the texel the GPU's point sample of the centre picks, at its own centre
        cx = np.minimum(ax * 2 + 1, W - 1); cy = np.minimum(ay * 2 + 1, H - 1)
        u = (cx + 0.5) / W; v = (cy + 0.5) / H
    d, cxi, cyi = fetch_uv(u, v)
    P = world_at(u, v, d)
    toC = CAM - P; dist = np.linalg.norm(toC, axis=-1); V = toC / dist[..., None]
    N = normal_at(u, v, P, snap)
    r = radius * np.clip(dist / 20.0, 1, 4)
    def tex_dir(du, dv):
        Q = world_at(u + du, v + dv, d) - P; Q = Q - V * dot(Q, V)[..., None]; return nrm(Q)
    R = tex_dir(1.0 / W, 0); U = tex_dir(0, 1.0 / H)
    qrx, _, _ = project(P + R * r[..., None]); _, quy, _ = project(P + U * r[..., None])
    rux, ruy = np.abs(qrx - u), np.abs(quy - v)
    rpx = np.maximum(rux * W, ruy * H)
    sc = np.minimum(1.0, 0.15 / np.maximum(ruy, 1e-6)); rux, ruy = rux * sc, ruy * sc
    nS = np.modf(ign(ax, ay) + frame * 0.618034)[0]
    nT = np.modf(ign(ay + 13.0, ax + 71.0) + frame * 0.754878)[0]
    fr = falloff * r
    vis = np.zeros_like(dist)
    for s in range(S):
        phi = (s + nS) / S * np.pi
        dx, dy = np.cos(phi), np.sin(phi)
        dux, duy = dx * rux, dy * ruy
        Dw = nrm(R * dx[..., None] + U * dy[..., None])
        axis = nrm(np.cross(Dw, V))
        Np = N - axis * dot(N, axis)[..., None]; lNp = np.linalg.norm(Np, axis=-1)
        cosN = np.clip(dot(Np, V) / np.maximum(lNp, 1e-9), -1, 1)
        n = np.where(dot(Dw, Np) >= 0, 1.0, -1.0) * facos(cosN)
        lo0, lo1 = np.cos(n + np.pi / 2), np.cos(n - np.pi / 2)
        hc = [lo0.copy(), lo1.copy()]
        lpx = np.sqrt((dux * W) ** 2 + (duy * H) ** 2)
        for k in range(K):
            t = (k + nT) / K; t = t * t
            t = np.maximum(t, 1.0 / (lpx if snap else rpx))
            for side, sg in ((0, 1.0), (1, -1.0)):
                su, sv = u + sg * dux * t, v + sg * duy * t
                inb = (su >= 0) & (su <= 1) & (sv >= 0) & (sv <= 1)
                sd, sx, sy = fetch_uv(su, sv)
                if snap:
                    su, sv = (sx + 0.5) / W, (sy + 0.5) / H
                    inb &= ~((sx == cxi) & (sy == cyi))
                Hv = world_at(su, sv, sd) - P; l = np.linalg.norm(Hv, axis=-1)
                ok = inb & (sd < KSKY) & (l > 1e-4)
                tb = np.clip((dot(Hv, N) / np.maximum(l, 1e-9) - 0.03) / 0.03, 0, 1)
                cand = (1 - np.clip((r - l) / fr, 0, 1) * tb) * [lo0, lo1][side] + np.clip((r - l) / fr, 0, 1) * tb * dot(Hv, V) / np.maximum(l, 1e-9)
                hc[side] = np.where(ok, np.maximum(hc[side], cand), hc[side])
        h0 = -facos(hc[1]); h1 = facos(hc[0])
        h0 = n + np.clip(h0 - n, -np.pi / 2, np.pi / 2); h1 = n + np.clip(h1 - n, -np.pi / 2, np.pi / 2)
        sn = np.sin(n)
        vs = lNp * ((cosN + 2 * h0 * sn - np.cos(2 * h0 - n)) + (cosN + 2 * h1 * sn - np.cos(2 * h1 - n))) * 0.25
        vis += np.where(lNp < 1e-4, 0, vs)
    vis = np.clip(vis / S, 0, 2)
    vis = np.where(d >= KSKY, 1.0, vis)
    return vis, dist, N

def resolve(vis, dist, N, frame=0):
    o = -1 if frame % 2 == 0 else -2
    hh, hw = vis.shape
    sw = np.zeros_like(vis); s1 = np.zeros_like(vis)
    for j in range(4):
        for i in range(4):
            yy = np.clip(np.arange(hh)[:, None] + j + o, 0, hh - 1); xx = np.clip(np.arange(hw)[None] + i + o, 0, hw - 1)
            s = vis[yy, xx]; g = dist[yy, xx]; ns = N[yy, xx]
            w = np.exp(-np.abs(g - dist) / np.maximum(dist * 0.02, 0.02)) * np.clip(dot(ns, N), 0, 1) ** 8
            sw += w; s1 += s * w
    return s1 / np.maximum(sw, 1e-4)

out = sys.argv[1] if len(sys.argv) > 1 else '.'
os.makedirs(out, exist_ok=True)
ground = (np.abs(WPv[1::2, 1::2, 1]) < 50)   # placeholder mask, refined below
for mode in ('old', 'new'):
    acc = None
    for fr in range(int(os.environ.get('FRAMES', '8'))):
        vis, dist, N = gtao(mode, fr)
        a = resolve(vis, dist, N, fr)
        acc = a if acc is None else acc + a
        if fr == 0: one = a
    acc /= int(os.environ.get('FRAMES', '8'))
    for name, img in (('1f', one), ('8f', acc)):
        ao = np.clip(img, 0, 1) ** 1.5
        Image.fromarray((ao * 255).astype(np.uint8)).save(os.path.join(out, f'{mode}_{name}.png'))
        # open ground: the lower-left area away from the box and the triangle
        reg = ao[380:540, 0:500]
        print(f'{mode} {name}: open ground mean {reg.mean():.3f}  p01 {np.percentile(reg, 1):.3f}  '
              f'frac<0.85 {(reg < 0.85).mean():.4f}  whole-image frac<0.85 {(ao < 0.85).mean():.4f}')
