"""Texture packs for the draw engine (libs/video/rsx_texture_pack.h): upscale a texture dump with
Real-ESRGAN into a pack the game loads in place of the originals, with optional PBR maps.

  1. Dump:    run the game with RSX_TEX_DUMP=<dump dir> (each distinct texture once, <key>.dds).
  2. Upscale: py -3 texpack.py upscale --dump <dump dir> --pack <pack dir> [options]
  3. Play:    run the game with RSX_TEX_PACK=<pack dir>.

upscale options:
  --scale N       2, 3 or 4 (default 4).
  --model M       auto (default): Real-ESRGAN x4plus for 4x textures, realesr-animevideov3 at its native
                  2x/3x for textures kept below 4x (--scale, --max-size); x4plus: x4plus at 4x for all
                  (then a Lanczos reduction); fast: realesr-animevideov3 for all.
                  Tiny (<= 16 px), flat and normal-map textures are resized (Lanczos) instead, and exact
                  duplicates are copied. The GPU upscales one batch while the CPU writes the previous one.
  --max-size N    largest side of a replacement (default 4096); a texture that would exceed it is
                  upscaled less.
  --format F      bc (default: BC1 when opaque, BC3 with alpha) or rgba (32-bit, 4x the memory).
  --pbr           also write PBR maps for colour textures: <pack>/pbr/<key>.dds (BC3, RGB a
                  tangent-space detail normal, A roughness, at most 1024 a side), the file the game
                  reads under RSX_TEX_PBR=1 (rsx_pbr.h), and the <key>_n.png / _r.png sources.
  --esrgan EXE    realesrgan-ncnn-vulkan.exe (default build/thirdparty/realesrgan/...).
  --limit N, --force, --keep-work

  py -3 texpack.py pbr --pack <dir> [--force]   (re)build <pack>/pbr/<key>.dds from the PNGs
  py -3 texpack.py pbr --pack <dir> --from-pack [--strength 2] [--blur 0.5]
                  remake the PBR maps (and PNGs) from the pack's upscaled colour textures
  py -3 texpack.py stats --dump <dir> [--pack <dir>]

Alpha is upscaled on its own (Lanczos). Normal maps (mostly (128, 128, 255)) are renormalised after
upscaling. Keys, file layout and DDS headers follow rsx_texture_pack.h. Dumps and packs are game
assets: keep them private (build/, never committed)."""
from __future__ import annotations

import argparse
import os
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import shutil
import struct
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[4]
ESRGAN = ROOT / 'build' / 'thirdparty' / 'realesrgan' / 'realesrgan-ncnn-vulkan.exe'


# ---- DDS ----------------------------------------------------------------------------------------
def dds_header(fmt: str, w: int, h: int, levels: int) -> bytes:
    bc = fmt != 'rgba'
    flags = 0x1007 | (0x20000 if levels > 1 else 0) | (0x80000 if bc else 0x8)
    lin = level_bytes(fmt, w, h) if bc else w * 4
    hd = bytearray(128)
    hd[0:4] = b'DDS '
    struct.pack_into('<7I', hd, 4, 124, flags, h, w, lin, 0, levels)
    pf = 76
    if bc:
        struct.pack_into('<2I4s', hd, pf, 32, 0x4, b'DXT1' if fmt == 'bc1' else b'DXT5')
    else:
        struct.pack_into('<8I', hd, pf, 32, 0x41, 0, 32, 0xFF, 0xFF00, 0xFF0000, 0xFF000000)
    struct.pack_into('<I', hd, 108, 0x1000 | (0x400008 if levels > 1 else 0))
    return bytes(hd)


def level_bytes(fmt: str, w: int, h: int) -> int:
    if fmt == 'rgba':
        return w * h * 4
    return ((w + 3) // 4) * ((h + 3) // 4) * (8 if fmt == 'bc1' else 16)


def read_dump(path: Path) -> np.ndarray:
    """RGBA uint8 (h, w, 4) of a dumped texture (DXT1/3/5 or 32-bit RGBA, as the GPU received it)."""
    with Image.open(path) as im:
        return np.asarray(im.convert('RGBA'))


# ---- BC1 / BC3 encoding (PCA endpoints, nearest palette entry) -----------------------------------
def _to565(c):
    c = np.clip(np.rint(c), 0, 255).astype(np.int32)
    return ((c[..., 0] >> 3) << 11) | ((c[..., 1] >> 2) << 5) | (c[..., 2] >> 3)


def _from565(v):
    r = (v >> 11) & 31
    g = (v >> 5) & 63
    b = v & 31
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], -1).astype(np.float32)


def _blocks(img: np.ndarray, ch: int) -> np.ndarray:
    h, w = img.shape[:2]
    ph, pw = (h + 3) // 4 * 4, (w + 3) // 4 * 4
    if (ph, pw) != (h, w):
        img = np.pad(img, ((0, ph - h), (0, pw - w), (0, 0)), mode='edge')
    return img.reshape(ph // 4, 4, pw // 4, 4, ch).transpose(0, 2, 1, 3, 4).reshape(-1, 16, ch)


def _bc1_color(bl: np.ndarray) -> np.ndarray:
    """(n, 16, 3) float32 -> (n, 8) uint8 colour blocks, four-colour mode."""
    n = bl.shape[0]
    mean = bl.mean(1)
    x = bl - mean[:, None, :]
    cov = np.einsum('nki,nkj->nij', x, x)
    v = np.ones((n, 3), np.float32)
    for _ in range(8):
        v = np.einsum('nij,nj->ni', cov, v)
        v /= np.linalg.norm(v, axis=1, keepdims=True) + 1e-12
    p = np.einsum('nki,ni->nk', x, v)
    e0 = np.clip(mean + v * p.max(1)[:, None], 0, 255)
    e1 = np.clip(mean + v * p.min(1)[:, None], 0, 255)
    c0, c1 = _to565(e0), _to565(e1)
    swap = c0 < c1
    c0, c1 = np.where(swap, c1, c0), np.where(swap, c0, c1)
    p0, p1 = _from565(c0), _from565(c1)
    pal = np.stack([p0, p1, (2 * p0 + p1) / 3, (p0 + 2 * p1) / 3], 1)              # (n, 4, 3)
    d = ((bl[:, :, None, :] - pal[:, None, :, :]) ** 2).sum(-1)                       # (n, 16, 4)
    idx = d.argmin(-1).astype(np.uint32)
    idx[c0 == c1] = 0
    bits = (idx << (2 * np.arange(16, dtype=np.uint32))).sum(1).astype(np.uint32)
    out = np.zeros((n, 8), np.uint8)
    out[:, 0:2] = c0.astype('<u2').view(np.uint8).reshape(n, 2)
    out[:, 2:4] = c1.astype('<u2').view(np.uint8).reshape(n, 2)
    out[:, 4:8] = bits.astype('<u4').view(np.uint8).reshape(n, 4)
    return out


def _bc3_alpha(al: np.ndarray) -> np.ndarray:
    """(n, 16) float32 alpha -> (n, 8) uint8 BC3 alpha blocks, eight-value mode."""
    n = al.shape[0]
    a0 = np.clip(np.rint(al.max(1)), 0, 255)
    a1 = np.clip(np.rint(al.min(1)), 0, 255)
    k = np.arange(8, dtype=np.float32)
    w0 = np.array([7, 0, 6, 5, 4, 3, 2, 1], np.float32) / 7.0
    pal = a0[:, None] * w0[None, :] + a1[:, None] * (1 - w0[None, :])                 # (n, 8)
    idx = np.abs(al[:, :, None] - pal[:, None, :]).argmin(-1).astype(np.uint64)
    idx[a0 == a1] = 0
    bits = (idx << (3 * np.arange(16, dtype=np.uint64))).sum(1).astype(np.uint64)
    out = np.zeros((n, 8), np.uint8)
    out[:, 0] = a0.astype(np.uint8)
    out[:, 1] = a1.astype(np.uint8)
    out[:, 2:8] = bits.astype('<u8').view(np.uint8).reshape(n, 8)[:, :6]
    del k
    return out


def encode(img: np.ndarray, fmt: str) -> bytes:
    if fmt == 'rgba':
        return np.ascontiguousarray(img).tobytes()
    bl = _blocks(img, 4).astype(np.float32)
    parts = []
    for s in range(0, bl.shape[0], 32768):
        b = bl[s:s + 32768]
        col = _bc1_color(b[:, :, :3])
        parts.append(col if fmt == 'bc1' else np.concatenate([_bc3_alpha(b[:, :, 3]), col], 1))
    return np.concatenate(parts, 0).tobytes()


def mip_chain(img: np.ndarray) -> list[np.ndarray]:
    out = [img]
    im = Image.fromarray(img, 'RGBA')
    w, h = im.size
    while w > 1 or h > 1:
        w, h = max(1, w // 2), max(1, h // 2)
        im = im.resize((w, h), Image.Resampling.BOX)
        out.append(np.asarray(im))
    return out


def write_dds(path: Path, img: np.ndarray, fmt: str) -> int:
    levels = mip_chain(img)
    h, w = img.shape[:2]
    data = [dds_header(fmt, w, h, len(levels))] + [encode(l, fmt) for l in levels]
    path.write_bytes(b''.join(data))
    return sum(len(d) for d in data)


# ---- classification, PBR --------------------------------------------------------------------------
def is_normal_map(rgb: np.ndarray) -> bool:
    m = rgb.reshape(-1, 3).astype(np.float32).mean(0)
    return m[2] > 170 and abs(m[0] - 128) < 40 and abs(m[1] - 128) < 40 and m[2] > m[0] + 40


def renormalise(rgb: np.ndarray) -> np.ndarray:
    n = rgb.astype(np.float32) / 127.5 - 1.0
    n /= np.linalg.norm(n, axis=2, keepdims=True) + 1e-6
    return np.clip(np.rint((n + 1.0) * 127.5), 0, 255).astype(np.uint8)


def pbr_maps(rgb: np.ndarray, strength: float = 2.0, scale: float = 1.0,
             blur: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
    """Normal (tangent space, +Z up) from luminance as height, roughness from local contrast.

    `scale` is the image's pixels per original texel (4 for a 4x upscale). Slopes are taken per
    original texel, so an upscale does not flatten the relief: measured per upscaled pixel they came
    out `scale` times too small (median |xy| 0.035 on build/texpack/ms2, which lit nothing visibly).
    The height is blurred over `blur` original texels, so BC block edges do not become bumps; a
    wider blur keeps only broad relief (soft sand instead of sharp grit)."""
    img = Image.fromarray(rgb, 'RGB').convert('L')
    from PIL import ImageFilter
    hgt = np.asarray(img.filter(ImageFilter.GaussianBlur(max(1.0, blur * scale))), np.float32) / 255.0
    gx = np.zeros_like(hgt)
    gy = np.zeros_like(hgt)
    gx[:, 1:-1] = (hgt[:, 2:] - hgt[:, :-2]) * scale
    gy[1:-1, :] = (hgt[2:, :] - hgt[:-2, :]) * scale
    n = np.stack([-gx * strength, -gy * strength, np.ones_like(hgt)], 2)
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    normal = np.clip(np.rint((n + 1.0) * 127.5), 0, 255).astype(np.uint8)
    return normal, rough_map(img)


def rough_map(img: Image.Image) -> np.ndarray:
    """Roughness from local contrast of the luminance image `img` (mode L), 3-pixel box windows."""
    from PIL import ImageFilter
    lum = np.asarray(img, np.float32) / 255.0
    mean = np.asarray(Image.fromarray((lum * 255).astype(np.uint8)).filter(ImageFilter.BoxBlur(3)), np.float32) / 255.0
    var = np.asarray(Image.fromarray(np.clip((lum - mean) ** 2 * 4 * 255, 0, 255).astype(np.uint8))
                     .filter(ImageFilter.BoxBlur(3)), np.float32) / 255.0
    rough = np.clip(0.55 + 0.45 * np.sqrt(var) * 4 - 0.25 * lum, 0.05, 1.0)
    return (rough * 255).astype(np.uint8)


PBR_MAX = 1024


def write_pbr_dds(path: Path, normal: np.ndarray, rough: np.ndarray) -> int:
    """The game's PBR map: BC3, RGB the normal, A the roughness, its larger side at most PBR_MAX."""
    rgba = np.dstack([normal, rough])
    h, w = rgba.shape[:2]
    if max(w, h) > PBR_MAX:
        k = PBR_MAX / max(w, h)
        im = Image.fromarray(rgba, 'RGBA').resize((max(1, round(w * k)), max(1, round(h * k))), Image.Resampling.BOX)
        rgba = np.asarray(im)
        rgba = np.dstack([renormalise(rgba[:, :, :3]), rgba[:, :, 3]])
    return write_dds(path, rgba, 'bc3')


def pbr_at_size(rgb: np.ndarray, scale: float) -> tuple[np.ndarray, np.ndarray]:
    """pbr_maps on the image shrunk to the PBR map's own size (larger side PBR_MAX) first: the map is
    stored at that size anyway, and the slopes and blur are per original texel, so the result is the
    same relief for far less work on a 4096 texture. Roughness (a fixed pixel window) is still measured at
    full size and shrunk, so it matches the old maps."""
    h, w = rgb.shape[:2]
    if max(w, h) <= PBR_MAX:
        return pbr_maps(rgb, scale=scale)
    k = PBR_MAX / max(w, h)
    size = (max(1, round(w * k)), max(1, round(h * k)))
    small = np.asarray(Image.fromarray(rgb, 'RGB').resize(size, Image.Resampling.BOX))
    normal, _ = pbr_maps(small, scale=max(scale * k, 1e-3))
    # roughness from local contrast over a fixed pixel window: measured at full size, then shrunk, as before
    rough = rough_map(Image.fromarray(rgb, 'RGB').convert('L'))
    return normal, np.asarray(Image.fromarray(rough, 'L').resize(size, Image.Resampling.BOX))


def _pbr_job(dump: str, pack: str) -> int:
    """One texture already in the pack: its PBR map from the pack's own upscaled image (worker process)."""
    f, pk = Path(dump), Path(pack)
    try:
        img = read_dump(f)
        if is_normal_map(img[:, :, :3]):
            return 0
        with Image.open(pk / f.name) as im:
            rgb = np.asarray(im.convert('RGB'))
    except Exception as e:
        print('skip PBR', f.name, e, flush=True)
        return 0
    n, rgh = pbr_at_size(rgb, rgb.shape[1] / img.shape[1])
    Image.fromarray(n, 'RGB').save(pk / 'pbr' / (f.stem + '_n.png'))
    Image.fromarray(rgh, 'L').save(pk / 'pbr' / (f.stem + '_r.png'))
    write_pbr_dds(pk / 'pbr' / (f.stem + '.dds'), n, rgh)
    return 1


MODELS = {'x4plus': 'realesrgan-x4plus',          # best detail; always runs at 4x (other scales: Lanczos of its output)
          'fast': 'realesr-animevideov3'}       # small model with native 2x/3x/4x, ~15x faster, softer detail


def esrgan_group(model: str, scale: int) -> str:
    """'<model>-<Real-ESRGAN scale>' for a texture of final `scale` under --model: x4plus always runs at
    4x; fast at the final scale; auto uses x4plus for 4x and fast (native 2x/3x, close to x4plus's 4x
    output reduced, at a fraction of the cost) for textures --scale or --max-size keep below 4x."""
    if model == 'x4plus' or (model == 'auto' and scale == 4):
        return 'x4plus-4'
    return f'fast-{scale}'
TINY = 16        # a texture whose larger side is at most this is resized, not upscaled by Real-ESRGAN
FLAT_SPAN = 8    # ... as is one whose RGB channels vary by at most this much (solid colours, faint gradients)


def target_scale(w: int, h: int, scale: int, max_size: int) -> int:
    while scale > 1 and max(w, h) * scale > max_size:
        scale -= 1
    return scale


def _plan_job(dump: str, work_in: str, scale_opt: int, max_size: int, model: str) -> tuple:
    """Read one dumped texture and decide how it is upscaled (worker process). Returns (key, kind, scale,
    digest, detail): kind 'ai' (its RGB written to <work_in>/<esrgan scale>/<key>.png), 'resize' (tiny,
    flat or a normal map: Lanczos only), 'none' (cannot be upscaled within --max-size) or 'skip'
    (unreadable; detail the error)."""
    f = Path(dump)
    try:
        img = read_dump(f)
    except Exception as e:   # a format PIL cannot read
        return f.stem, 'skip', 0, '', str(e)
    h, w = img.shape[:2]
    scale = target_scale(w, h, scale_opt, max_size)
    if scale < 2:
        return f.stem, 'none', scale, '', ''
    import hashlib
    digest = hashlib.blake2b(img.tobytes() + struct.pack('<2I', w, h), digest_size=16).hexdigest()
    rgb = img[:, :, :3]
    flat = int((rgb.reshape(-1, 3).max(0).astype(np.int16) - rgb.reshape(-1, 3).min(0)).max()) <= FLAT_SPAN
    if max(w, h) <= TINY or flat or is_normal_map(rgb):
        return f.stem, 'resize', scale, digest, ''
    d = Path(work_in) / esrgan_group(model, scale)
    d.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb, 'RGB').save(d / (f.stem + '.png'), compress_level=1)
    return f.stem, 'ai', scale, digest, ''


def _low_priority() -> None:
    """Worker processes run below normal priority, so Real-ESRGAN (which needs the CPU to feed the GPU) and
    the desktop stay responsive while they write DDS files."""
    try:
        if sys.platform == 'win32':
            import ctypes
            k = ctypes.windll.kernel32
            k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)   # BELOW_NORMAL_PRIORITY_CLASS
        else:
            os.nice(5)
    except Exception:
        pass


def _finish_job(key: str, dump: str, scale: int, out: str | None, pack: str, fmt_opt: str, pbr: bool) -> int:
    """One texture: its replacement DDS and, with pbr, its PBR map (worker process). `out` is Real-ESRGAN's
    output, or None to resize the dumped image (Lanczos). Bytes written; -1 when Real-ESRGAN's output is
    blank (a GPU failure: nothing is written, so the next run redoes it)."""
    pk = Path(pack)
    img = read_dump(Path(dump))
    h, w = img.shape[:2]
    W, H = w * scale, h * scale
    if out is None:
        up = Image.fromarray(np.ascontiguousarray(img[:, :, :3]), 'RGB').resize((W, H), Image.Resampling.LANCZOS)
    else:
        with Image.open(out) as im:
            up = im.convert('RGB')
        if up.getextrema() == ((0, 0), (0, 0), (0, 0)) and img[:, :, :3].max() > 0:
            return -1
        if up.size != (W, H):
            up = up.resize((W, H), Image.Resampling.LANCZOS)
    rgb = np.asarray(up)
    if is_normal_map(img[:, :, :3]):
        rgb = renormalise(rgb)
    alpha = np.asarray(Image.fromarray(img[:, :, 3], 'L').resize((W, H), Image.Resampling.LANCZOS))
    rgba = np.dstack([rgb, alpha])
    opaque = img[:, :, 3].min() >= 250
    fmt = 'rgba' if fmt_opt == 'rgba' else ('bc1' if opaque else 'bc3')
    total = write_dds(pk / (key + '.dds'), rgba, fmt)
    if pbr and not is_normal_map(img[:, :, :3]):
        n, rgh = pbr_at_size(rgb, scale)
        Image.fromarray(n, 'RGB').save(pk / 'pbr' / (key + '_n.png'))
        Image.fromarray(rgh, 'L').save(pk / 'pbr' / (key + '_r.png'))
        total += write_pbr_dds(pk / 'pbr' / (key + '.dds'), n, rgh)
    return total


# ---- commands ---------------------------------------------------------------------------------------
BATCH = 32   # textures per Real-ESRGAN run; progress is reported after each


def _key_px(key: str) -> int:
    """Guest pixels of a key "<w>x<h>_..." (progress weighting), 1 when the name does not parse."""
    try:
        w, h = key.split('_')[0].split('x')
        return int(w) * int(h)
    except ValueError:
        return 1


def cmd_upscale(a) -> int:
    dump, pack = Path(a.dump), Path(a.pack)
    pack.mkdir(parents=True, exist_ok=True)
    work = pack / '_work'
    files = sorted(dump.glob('*.dds'))
    todo = []
    pbr_only = []   # already upscaled (an earlier run, maybe without --pbr) but no PBR map yet
    for f in files:
        if not a.force and (pack / f.name).exists():
            if a.pbr and not (pack / 'pbr' / f.name).exists():
                pbr_only.append(f)
            continue
        if not a.limit or len(todo) < a.limit:
            todo.append(f)
    print(f'{len(files)} dumped, {len(todo)} to upscale', flush=True)
    if a.pbr:
        (pack / 'pbr').mkdir(exist_ok=True)
        made = 0
        if pbr_only:   # from the pack's own upscaled texture: no Real-ESRGAN run needed
            with ProcessPoolExecutor(max_workers=a.jobs) as ex:
                for k, r in enumerate(ex.map(_pbr_job, [str(f) for f in pbr_only], [str(pack)] * len(pbr_only),
                                             chunksize=1)):
                    made += r
                    if (k + 1) % 25 == 0:
                        print(f'PBR {k + 1}/{len(pbr_only)}', flush=True)
        if pbr_only:
            print(f'{made} PBR maps added for textures already in the pack', flush=True)
    # Pipeline: batch N runs on the GPU (Real-ESRGAN) while the worker pool writes the DDS/PBR files of
    # batch N-1 and reads/plans batch N+1. Textures that gain nothing from the network (tiny, flat, normal
    # maps) are resized; exact duplicates (same pixels under another key) are copied from their twin.
    if work.exists():
        shutil.rmtree(work)
    nb = (len(todo) + BATCH - 1) // BATCH
    st = {'total': 0, 'done': 0, 'seen': 0, 'px': 0, 'ai': 0, 'resized': 0, 'failed': 0}
    all_px = sum(_key_px(f.stem) for f in todo) or 1
    t0 = time.time()
    dups = []          # (key, twin key)
    seen_digest = {}
    models = str(Path(a.esrgan).parent / 'models')
    if todo and a.model != 'x4plus' and not all((Path(models) / f'realesr-animevideov3-x{s}.param').exists()
                                                for s in (2, 3, 4)):
        print('realesr-animevideov3 models not found: using realesrgan-x4plus for all', flush=True)
        a.model = 'x4plus'

    def esrgan(d: Path) -> str:
        """Real-ESRGAN over each scale group of a batch (GPU thread). '' or an error message."""
        for g in sorted((d / 'in').iterdir()) if (d / 'in').exists() else []:
            (d / 'out' / g.name).mkdir(parents=True, exist_ok=True)
            m, s = g.name.split('-')
            cmd = [str(a.esrgan), '-i', str(g), '-o', str(d / 'out' / g.name), '-n', MODELS[m],
                   '-s', s, '-f', 'png', '-m', models, '-j', '2:2:4']
            if a.gpu is not None:
                cmd += ['-g', str(a.gpu)]
            t1 = time.time()
            # above normal: under a busy CPU (the DDS workers) Real-ESRGAN otherwise feeds the GPU 2-3x slower
            r = subprocess.run(cmd, capture_output=True, text=True,
                               creationflags=0x8000 if sys.platform == 'win32' else 0)   # ABOVE_NORMAL_PRIORITY_CLASS
            if os.environ.get('TEXPACK_TIMING'):
                print(f'timing {d.name} {g.name}: {len(list(g.iterdir()))} textures, '
                      f'{sum(_key_px(p.stem) for p in g.iterdir()) / 1e6:.1f} Mpx, {time.time() - t1:.1f}s', flush=True)
            if r.returncode:
                return f'Real-ESRGAN failed (rc {r.returncode})\n{r.stderr[-2000:]}'
        return ''

    def plan(bi: int):
        d = work / f'b{bi}'
        fs = todo[bi * BATCH:(bi + 1) * BATCH]
        return d, fs, [pool.submit(_plan_job, str(f), str(d / 'in'), a.scale, a.max_size, a.model) for f in fs]

    def report(batch) -> None:
        d, fs, futs = batch
        for key, fut in futs:
            t = fut.result()
            if t < 0:
                st['failed'] += 1
                print('Real-ESRGAN gave a blank image for', key, '(left for the next run)', flush=True)
            else:
                st['total'] += t
                st['done'] += 1
        if not a.keep_work:
            shutil.rmtree(d, ignore_errors=True)
        st['seen'] += len(fs)
        st['px'] += sum(_key_px(f.stem) for f in fs)
        el = time.time() - t0
        eta = el / st['px'] * (all_px - st['px']) if st['px'] else 0   # by pixels: batches differ in size
        print(f'PROGRESS {st["seen"]}/{len(todo)} elapsed {el:.0f}s remaining about {eta / 60:.0f} min', flush=True)

    def finish_ai(batch):
        """Wait for a batch's Real-ESRGAN run, then queue its DDS/PBR writing. None on failure."""
        d, fs, metas, gf, futs = batch
        err = gf.result()
        if err:
            print(err, flush=True)
            return None
        twins = {k for k, _ in dups}
        for key, kind, s, _, _ in metas:
            if kind != 'ai' or key in twins:
                continue
            out = d / 'out' / esrgan_group(a.model, s) / (key + '.png')
            if not out.exists():
                print('no output for', key, flush=True)
                continue
            st['ai'] += 1
            futs.append((key, pool.submit(_finish_job, key, str(dump / (key + '.dds')), s, str(out), str(pack),
                                          a.format, bool(a.pbr))))
        return d, fs, futs

    rc = 0
    with ProcessPoolExecutor(max_workers=a.jobs, initializer=_low_priority) as pool,             ThreadPoolExecutor(max_workers=1) as gpu:
        nxt = plan(0) if nb else None
        prev = None        # (dir, files, metas, gpu future) of the batch on the GPU
        fin_prev = None    # (dir, files, [(key, future)]) of the batch being finished
        for bi in range(nb):
            d, fs, pf = nxt
            metas = [p.result() for p in pf]
            nxt = plan(bi + 1) if bi + 1 < nb else None   # read ahead while the GPU works
            for key, kind, s, digest, detail in metas:
                if kind == 'skip':
                    print('skip', key, detail, flush=True)
                elif kind in ('ai', 'resize'):
                    if digest in seen_digest:
                        dups.append((key, seen_digest[digest]))
                        png = d / 'in' / esrgan_group(a.model, s) / (key + '.png')
                        png.unlink(missing_ok=True)
                    else:
                        seen_digest[digest] = key
            gf = gpu.submit(esrgan, d)
            twins = {k for k, _ in dups}
            futs = [(key, pool.submit(_finish_job, key, str(dump / (key + '.dds')), s, None, str(pack),
                                      a.format, bool(a.pbr)))
                    for key, kind, s, _, _ in metas if kind == 'resize' and key not in twins]
            st['resized'] += len(futs)
            cur = (d, fs, metas, gf, futs)
            if prev is not None:
                fin = finish_ai(prev)
                if fin is None:
                    rc = 1
                    break
                if fin_prev is not None:
                    report(fin_prev)
                fin_prev = fin
            prev = cur
        if rc == 0 and prev is not None:
            fin = finish_ai(prev)
            if fin is None:
                rc = 1
            else:
                if fin_prev is not None:
                    report(fin_prev)
                report(fin)
    if rc:
        return rc
    for key, twin in dups:   # exact duplicates: the twin's files under this key
        if (pack / (twin + '.dds')).exists():
            shutil.copyfile(pack / (twin + '.dds'), pack / (key + '.dds'))
            st['done'] += 1
            for sfx in ('.dds', '_n.png', '_r.png'):
                if a.pbr and (pack / 'pbr' / (twin + sfx)).exists():
                    shutil.copyfile(pack / 'pbr' / (twin + sfx), pack / 'pbr' / (key + sfx))
    if not a.keep_work:
        shutil.rmtree(work, ignore_errors=True)
    if not todo:
        print('nothing to do', flush=True)
    print(f'{st["ai"]} upscaled by Real-ESRGAN ({a.model}), {st["resized"]} resized (tiny, flat or normal maps), '
          f'{len(dups)} duplicates copied', flush=True)
    print(f'{st["done"]} replacements written to {pack} ({st["total"] / 1e6:.0f} MB)', flush=True)
    return 0


def cmd_pbr(a) -> int:
    d = Path(a.pack) / 'pbr'
    done = total = 0
    if a.from_pack:
        # Remake the maps from the pack's own upscaled colour textures (<pack>/<key>.dds), the scale
        # being the replacement's width over the guest width in the key.
        mags = []
        for n in sorted(d.glob('*_n.png')):
            key = n.name[:-len('_n.png')]
            src = Path(a.pack) / (key + '.dds')
            if not src.exists():
                continue
            im = Image.open(src)
            im.load()
            rgb = np.asarray(im.convert('RGB'))
            scale = rgb.shape[1] / int(key.split('x')[0])
            normal, rough = pbr_maps(rgb, strength=a.strength, scale=scale, blur=a.blur)
            Image.fromarray(normal, 'RGB').save(n)
            Image.fromarray(rough, 'L').save(d / (key + '_r.png'))
            total += write_pbr_dds(d / (key + '.dds'), normal, rough)
            mags.append(float(np.abs(normal[:, :, :2].astype(np.float32) / 127.5 - 1.0).mean()))
            done += 1
        print(f'{done} PBR maps remade from the pack in {d} ({total / 1e6:.0f} MB), '
              f'mean |normal xy| median {np.median(mags) if mags else 0:.3f}')
        return 0
    for n in sorted(d.glob('*_n.png')):
        key = n.name[:-len('_n.png')]
        r = d / (key + '_r.png')
        out = d / (key + '.dds')
        if not r.exists() or (out.exists() and not a.force):
            continue
        normal = np.asarray(Image.open(n).convert('RGB'))
        rough = np.asarray(Image.open(r).convert('L'))
        total += write_pbr_dds(out, normal, rough)
        done += 1
    print(f'{done} PBR maps written to {d} ({total / 1e6:.0f} MB)')
    return 0


def cmd_stats(a) -> int:
    dump = Path(a.dump)
    files = sorted(dump.glob('*.dds'))
    by = {}
    for f in files:
        w, h = f.stem.split('_')[0].split('x')
        by.setdefault(f'{w}x{h}', 0)
        by[f'{w}x{h}'] += 1
    print(f'{len(files)} dumped textures, {sum(f.stat().st_size for f in files) / 1e6:.0f} MB')
    for k, v in sorted(by.items(), key=lambda kv: -kv[1])[:15]:
        print(f'  {k:>11}: {v}')
    if a.pack:
        pk = list(Path(a.pack).glob('*.dds'))
        print(f'pack: {len(pk)} replacements, {sum(f.stat().st_size for f in pk) / 1e6:.0f} MB')
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    u = sp.add_parser('upscale')
    u.add_argument('--dump', required=True)
    u.add_argument('--pack', required=True)
    u.add_argument('--scale', type=int, default=4, choices=(2, 3, 4))
    u.add_argument('--max-size', type=int, default=4096)
    u.add_argument('--format', default='bc', choices=('bc', 'rgba'))
    u.add_argument('--pbr', action='store_true')
    u.add_argument('--esrgan', default=str(ESRGAN))
    u.add_argument('--model', default='auto', choices=('auto', 'x4plus', 'fast'),
                   help='auto (default): x4plus for 4x, fast for textures kept to 2x/3x; x4plus: x4plus for all '
                        '(4x then Lanczos, about twice as slow for the same 2x result); fast: '
                        'realesr-animevideov3 for all (about 15x faster on the GPU, flatter at 4x)')
    u.add_argument('--gpu', type=int, default=None, help='Real-ESRGAN GPU id (default: its own choice)')
    u.add_argument('--limit', type=int, default=0)
    u.add_argument('--force', action='store_true')
    u.add_argument('--keep-work', action='store_true')
    u.add_argument('--jobs', type=int, default=max(1, (os.cpu_count() or 2) - 2),
                   help='worker processes for the DDS and PBR step (default: all cores but two)')
    b = sp.add_parser('pbr')
    b.add_argument('--pack', required=True)
    b.add_argument('--force', action='store_true')
    b.add_argument('--from-pack', action='store_true',
                   help='remake the normal and roughness from <pack>/<key>.dds instead of the PNGs')
    b.add_argument('--strength', type=float, default=2.0, help='normal strength per original texel')
    b.add_argument('--blur', type=float, default=0.5,
                   help='height blur in original texels (larger: softer, broader relief)')
    s = sp.add_parser('stats')
    s.add_argument('--dump', required=True)
    s.add_argument('--pack')
    a = ap.parse_args(argv)
    return {'upscale': cmd_upscale, 'pbr': cmd_pbr, 'stats': cmd_stats}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
