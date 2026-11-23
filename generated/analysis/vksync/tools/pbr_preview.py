"""Preview RSX_TEX_PBR on one pack texture offline: the colour lit by the race's sun with the PBR
normal bent in as the rewritten shader does (N + k*(0.5+0.5*rough)*(nx*T + ny*B), ground frame),
next to the flat (off) lighting, for several map settings (blur, map strength) and runtime
strengths k. Picks the sandiest textures when no key is given.

usage: py -3 pbr_preview.py <pack dir> <out.png> [key] [--sets blur:strength:k ...]"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from texpack import pbr_maps  # noqa: E402

SUN = np.array([-0.4981, -0.0436, 0.8660], np.float32)   # race sun (x, z, up) from [tex-pbr] sun


def shade(rgb, normal, rough, k):
    a = rgb.astype(np.float32) / 255.0
    if normal is None:
        nl = np.full(a.shape[:2], SUN[2], np.float32)
    else:
        n = normal.astype(np.float32) / 127.5 - 1.0
        kk = k * (0.5 + 0.5 * rough.astype(np.float32) / 255.0)
        v = np.stack([kk * n[..., 0], kk * n[..., 1], np.ones(n.shape[:2], np.float32)], 2)
        v /= np.linalg.norm(v, axis=2, keepdims=True)
        nl = np.clip(v @ SUN, 0.0, 1.0)
    lit = a * (0.45 + 0.75 * nl[..., None]) / (0.45 + 0.75 * SUN[2])
    return np.clip(lit * 255.0, 0, 255).astype(np.uint8)


def sandy(pack, n):
    out = []
    for f in sorted((pack / 'pbr').glob('*_n.png')):
        key = f.name[:-len('_n.png')]
        src = pack / (key + '.dds')
        if not src.exists():
            continue
        im = Image.open(src)
        im.draft('RGB', (64, 64))
        m = np.asarray(im.convert('RGB').resize((32, 32)), np.float32).reshape(-1, 3).mean(0)
        score = -abs(m[0] - 200) - abs(m[1] - 180) - abs(m[2] - 135)
        out.append((score, key))
    return [k for _, k in sorted(out, reverse=True)[:n]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pack')
    ap.add_argument('out')
    ap.add_argument('key', nargs='?')
    ap.add_argument('--sets', nargs='+', default=['0.5:8:2', '0.5:8:1', '2:8:1', '3:6:1'])
    ap.add_argument('--crop', type=int, default=320)
    a = ap.parse_args()
    pack = Path(a.pack)
    keys = [a.key] if a.key else sandy(pack, 2)
    rows = []
    for key in keys:
        im = Image.open(pack / (key + '.dds'))
        im.load()
        rgb = np.asarray(im.convert('RGB'))
        scale = rgb.shape[1] / int(key.split('x')[0])
        c = min(a.crop, rgb.shape[0], rgb.shape[1])
        crop = (slice(0, c), slice(0, c))
        tiles = [shade(rgb[crop], None, None, 0)]
        for s in a.sets:
            blur, strength, k = (float(x) for x in s.split(':'))
            normal, rough = pbr_maps(rgb, strength=strength, scale=scale, blur=blur)
            tiles.append(shade(rgb[crop], normal[crop], rough[crop], k))
        rows.append(np.concatenate([np.pad(t, ((4, 4), (4, 4), (0, 0)), constant_values=255) for t in tiles], 1))
        print(key, 'tiles: off,', ', '.join(f'blur {s.split(":")[0]} map {s.split(":")[1]} k {s.split(":")[2]}' for s in a.sets))
    Image.fromarray(np.concatenate(rows, 0)).save(a.out)
    print('saved', a.out)


if __name__ == '__main__':
    main()
